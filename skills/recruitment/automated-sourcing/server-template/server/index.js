const path = require("path");
const express = require("express");
const rateLimit = require("express-rate-limit");
const Database = require("better-sqlite3");

const DB_PATH =
  process.env.DB_PATH || path.join(__dirname, "..", "data", "candidates.db");
const PORT = Number(process.env.PORT || 3000);
const PUBLIC_DIR = path.join(__dirname, "..", "public");

const db = new Database(DB_PATH);
db.pragma("journal_mode = WAL");
db.exec(`
  CREATE TABLE IF NOT EXISTS candidates (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    candidate_id TEXT UNIQUE,
    full_name TEXT NOT NULL,
    headline TEXT,
    current_company TEXT,
    current_title TEXT,
    location TEXT,
    profile_url TEXT UNIQUE,
    score REAL,
    predicted_rating REAL,
    review_state TEXT NOT NULL DEFAULT 'pending',
    status TEXT NOT NULL DEFAULT 'new',
    feedback TEXT NOT NULL DEFAULT '',
    first_found_run_id TEXT,
    sourcing_run TEXT,
    bundle_blob TEXT,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
  );
  CREATE TABLE IF NOT EXISTS general_feedback (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    content TEXT NOT NULL DEFAULT '',
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
  );
  INSERT OR IGNORE INTO general_feedback (id, content) VALUES (1, '');
  CREATE TABLE IF NOT EXISTS runs (
    run_id TEXT PRIMARY KEY,
    label TEXT,
    started_at TEXT,
    completed_at TEXT,
    run_number INTEGER
  );
  CREATE TABLE IF NOT EXISTS feedback_themes (
    theme_id TEXT PRIMARY KEY,
    label TEXT NOT NULL,
    source TEXT,
    detected_in_run_id TEXT,
    applied_to_run_id TEXT,
    action_taken TEXT,
    description TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
  );
  CREATE TABLE IF NOT EXISTS ashby_exclusions (
    exclusion_id TEXT PRIMARY KEY,
    candidate_name TEXT NOT NULL,
    reason TEXT,
    status TEXT,
    source TEXT,
    excluded_at TEXT
  );
  CREATE TABLE IF NOT EXISTS hired_seed_profiles (
    profile_id TEXT PRIMARY KEY,
    full_name TEXT NOT NULL,
    role TEXT,
    company TEXT,
    profile_url TEXT,
    summary TEXT
  );
  CREATE TABLE IF NOT EXISTS workflow_settings (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    settings_json TEXT NOT NULL DEFAULT '{}'
  );
  INSERT OR IGNORE INTO workflow_settings (id, settings_json) VALUES (1, '{}');
`);

const app = express();
app.use(express.json({ limit: "256kb" }));

// Serve static files with cache-control matched to how each asset can change.
// HTML changes every render and must NEVER be cached — a stale HTML pointing
// to an old JS bundle is the same as serving stale JS. JS/CSS are
// fingerprinted by the renderer (?v=<hash>) so they can cache long-term.
app.use(
  express.static(PUBLIC_DIR, {
    etag: true,
    setHeaders: (res, filePath) => {
      if (filePath.endsWith(".html")) {
        res.setHeader("Cache-Control", "no-store, must-revalidate");
      }
    },
  }),
);

// Permissive CORS for /api/* so a statically-deployed frontend can call the
// proxied sandbox backend from a different origin. The sandbox runtime itself
// gates network access; widening CORS here only relaxes the browser's
// same-origin check for the review UI.
app.use("/api/", (req, res, next) => {
  res.setHeader("Access-Control-Allow-Origin", "*");
  res.setHeader("Access-Control-Allow-Methods", "GET,POST,PUT,PATCH,DELETE,OPTIONS");
  res.setHeader("Access-Control-Allow-Headers", "Content-Type,Authorization");
  // API responses must never be cached by browsers or intermediate CDNs —
  // reviewer state changes from one PATCH to the next and a cached GET
  // would surface a stale review_state on the next page load.
  res.setHeader("Cache-Control", "no-store, must-revalidate");
  if (req.method === "OPTIONS") return res.status(204).end();
  return next();
});

const rateLimitDisabled = process.env.RATE_LIMIT_DISABLED === "1";
const apiReadLimiter = rateLimit({
  windowMs: 60_000,
  max: 300,
  standardHeaders: true,
  legacyHeaders: false,
  skip: () => rateLimitDisabled,
});
const apiWriteLimiter = rateLimit({
  windowMs: 60_000,
  max: 60,
  standardHeaders: true,
  legacyHeaders: false,
  skip: () => rateLimitDisabled,
});
app.use("/api/", (req, res, next) => {
  const limiter = req.method === "GET" ? apiReadLimiter : apiWriteLimiter;
  return limiter(req, res, next);
});

const REVIEW_STATES = new Set(["yes", "maybe", "no", "pending"]);
const STATUSES = new Set([
  "new",
  "reviewed",
  "contacted",
  "rejected",
  "archived",
]);

function applyStatusMapping(reviewState, currentStatus) {
  if (reviewState === "yes" || reviewState === "maybe") return "reviewed";
  if (reviewState === "no") return "rejected";
  return currentStatus;
}

function findCandidate(rawRef) {
  if (/^\d+$/.test(rawRef)) {
    const row = db
      .prepare("SELECT * FROM candidates WHERE id = ?")
      .get(Number(rawRef));
    if (row) return row;
  }
  const byCandidateId = db
    .prepare("SELECT * FROM candidates WHERE candidate_id = ?")
    .get(rawRef);
  if (byCandidateId) return byCandidateId;
  if (/^https?:/i.test(rawRef)) {
    const rows = db
      .prepare("SELECT * FROM candidates WHERE profile_url = ? LIMIT 2")
      .all(rawRef);
    if (rows.length > 1) return { __ambiguous: true };
    return rows[0] || null;
  }
  return null;
}

function expandBundleBlob(row) {
  if (!row || !row.bundle_blob) return row;
  let bundle = {};
  try {
    bundle = JSON.parse(row.bundle_blob) || {};
  } catch {
    bundle = {};
  }
  const { bundle_blob, ...rest } = row;
  return { ...bundle, ...rest, feedback_free_text: row.feedback || "" };
}

app.get("/api/candidates", (_req, res) => {
  const rows = db
    .prepare(
      `SELECT id, candidate_id, full_name, headline, current_company, current_title,
              location, profile_url, score, predicted_rating, review_state,
              status, feedback, first_found_run_id, sourcing_run
       FROM candidates
       ORDER BY (score IS NULL), score DESC, id DESC
       LIMIT 500`,
    )
    .all();
  res.json(rows);
});

app.get("/api/candidates/:ref", (req, res) => {
  const found = findCandidate(req.params.ref);
  if (!found) return res.status(404).json({ error: "not found" });
  if (found.__ambiguous) {
    return res
      .status(400)
      .json({ error: "profile_url did not uniquely identify a candidate" });
  }
  res.json(expandBundleBlob(found));
});

app.patch("/api/candidates/:ref", (req, res) => {
  const found = findCandidate(req.params.ref);
  if (!found) return res.status(404).json({ error: "not found" });
  if (found.__ambiguous) {
    return res
      .status(400)
      .json({ error: "profile_url did not uniquely identify a candidate" });
  }
  const { review_state, status, feedback } = req.body || {};
  if (review_state !== undefined && !REVIEW_STATES.has(review_state)) {
    return res.status(400).json({ error: "invalid review_state" });
  }
  if (status !== undefined && !STATUSES.has(status)) {
    return res.status(400).json({ error: "invalid status" });
  }
  const nextReview = review_state ?? found.review_state;
  const nextStatus =
    status !== undefined
      ? status
      : applyStatusMapping(nextReview, found.status);
  db.prepare(
    `UPDATE candidates SET
       review_state = @review_state,
       status = @status,
       feedback = COALESCE(@feedback, feedback),
       updated_at = CURRENT_TIMESTAMP
     WHERE id = @id`,
  ).run({
    id: found.id,
    review_state: nextReview,
    status: nextStatus,
    feedback: feedback === undefined ? null : feedback ?? "",
  });
  const row = db.prepare("SELECT * FROM candidates WHERE id = ?").get(found.id);
  res.json(expandBundleBlob(row));
});

app.get("/api/general-feedback", (_req, res) => {
  const row = db
    .prepare(
      "SELECT content, updated_at FROM general_feedback WHERE id = 1",
    )
    .get();
  res.json(row || { content: "", updated_at: null });
});

app.put("/api/general-feedback", (req, res) => {
  const content = String((req.body && req.body.content) || "");
  db.prepare(
    "UPDATE general_feedback SET content = ?, updated_at = CURRENT_TIMESTAMP WHERE id = 1",
  ).run(content);
  const row = db
    .prepare(
      "SELECT content, updated_at FROM general_feedback WHERE id = 1",
    )
    .get();
  res.json(row);
});

app.get("/api/runs", (_req, res) => {
  res.json(
    db
      .prepare(
        "SELECT run_id, label, started_at, completed_at, run_number FROM runs ORDER BY run_number DESC NULLS LAST, started_at DESC",
      )
      .all(),
  );
});

app.get("/api/feedback-themes", (_req, res) => {
  res.json(
    db
      .prepare(
        `SELECT theme_id, label, source, detected_in_run_id, applied_to_run_id,
                action_taken, description, created_at
         FROM feedback_themes
         ORDER BY created_at DESC, theme_id DESC`,
      )
      .all(),
  );
});

app.get("/api/ashby-exclusions", (_req, res) => {
  res.json(
    db
      .prepare(
        `SELECT exclusion_id, candidate_name, reason, status, source, excluded_at
         FROM ashby_exclusions
         ORDER BY excluded_at DESC, exclusion_id DESC`,
      )
      .all(),
  );
});

app.get("/api/hired-seed-profiles", (_req, res) => {
  res.json(
    db
      .prepare(
        "SELECT profile_id, full_name, role, company, profile_url, summary FROM hired_seed_profiles ORDER BY profile_id DESC",
      )
      .all(),
  );
});

app.get("/api/workflow-settings", (_req, res) => {
  const row = db
    .prepare("SELECT settings_json FROM workflow_settings WHERE id = 1")
    .get();
  let parsed = {};
  try {
    parsed = JSON.parse((row && row.settings_json) || "{}");
  } catch {
    parsed = {};
  }
  res.json(parsed);
});

const HOST = process.env.HOST || "0.0.0.0";

if (require.main === module) {
  app.listen(PORT, HOST, () =>
    console.log(`automated-sourcing review app listening on http://${HOST}:${PORT}`),
  );
}

module.exports = { app, db };
