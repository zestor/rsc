#!/usr/bin/env node
/*
 * Load a ReviewBundle JSON (the renderer's `review_bundle.json` output) into
 * the SQLite store the server reads. Idempotent: existing candidate rows keyed
 * by `candidate_id` are updated in place, preserving the reviewer's
 * `review_state`, `status`, and `feedback` columns. Other tables (runs,
 * feedback_themes, ashby_exclusions, hired_seed_profiles, workflow_settings,
 * general_feedback) are refreshed wholesale to track the latest workflow run.
 *
 * Usage:
 *   node scripts/seed.js path/to/review_bundle.json
 *   BUNDLE=path/to/review_bundle.json node scripts/seed.js
 *
 * Pass `--reset` to drop existing reviewer state (a fresh run); default behavior
 * preserves it across reseeds.
 */
const fs = require("fs");
const path = require("path");
const Database = require("better-sqlite3");

const DB_PATH =
  process.env.DB_PATH || path.join(__dirname, "..", "data", "candidates.db");
const args = process.argv.slice(2).filter((a) => a !== "--reset");
const reset = process.argv.includes("--reset");
const bundlePath = args[0] || process.env.BUNDLE;
if (!bundlePath) {
  console.error("usage: node scripts/seed.js [--reset] <review_bundle.json>");
  process.exit(2);
}
const dataDir = path.dirname(DB_PATH);
fs.mkdirSync(dataDir, { recursive: true });

const bundle = JSON.parse(fs.readFileSync(bundlePath, "utf-8"));
const db = new Database(DB_PATH);
db.pragma("journal_mode = WAL");

require("../server/index.js");

if (reset) {
  db.exec(
    "DELETE FROM candidates; DELETE FROM runs; DELETE FROM feedback_themes; DELETE FROM ashby_exclusions; DELETE FROM hired_seed_profiles;",
  );
  db.prepare(
    "UPDATE general_feedback SET content = '', updated_at = CURRENT_TIMESTAMP WHERE id = 1",
  ).run();
  db.prepare(
    "UPDATE workflow_settings SET settings_json = '{}' WHERE id = 1",
  ).run();
}

const REVIEW_STATES = new Set(["yes", "maybe", "no", "pending"]);

function wireReviewState(raw) {
  if (raw == null) return "pending";
  const v = String(raw).toLowerCase().trim();
  if (v === "unreviewed" || v === "") return "pending";
  return REVIEW_STATES.has(v) ? v : "pending";
}

function statusForReview(rs, explicit) {
  if (explicit) return explicit;
  if (rs === "yes" || rs === "maybe") return "reviewed";
  if (rs === "no") return "rejected";
  return "new";
}

const upsertCandidate = db.prepare(`
  INSERT INTO candidates (
    candidate_id, full_name, headline, current_company, current_title,
    location, profile_url, score, predicted_rating, first_found_run_id,
    sourcing_run, bundle_blob, review_state, status, feedback
  ) VALUES (
    @candidate_id, @full_name, @headline, @current_company, @current_title,
    @location, @profile_url, @score, @predicted_rating, @first_found_run_id,
    @sourcing_run, @bundle_blob, @review_state, @status, @feedback
  )
  ON CONFLICT(candidate_id) DO UPDATE SET
    full_name = excluded.full_name,
    headline = excluded.headline,
    current_company = excluded.current_company,
    current_title = excluded.current_title,
    location = excluded.location,
    profile_url = excluded.profile_url,
    score = excluded.score,
    predicted_rating = excluded.predicted_rating,
    first_found_run_id = excluded.first_found_run_id,
    sourcing_run = excluded.sourcing_run,
    bundle_blob = excluded.bundle_blob,
    updated_at = CURRENT_TIMESTAMP
`);

const candidates = Array.isArray(bundle.candidates) ? bundle.candidates : [];
const tx = db.transaction((rows) => {
  for (const c of rows) {
    const rs = wireReviewState(c.review_state);
    upsertCandidate.run({
      candidate_id: c.candidate_id || null,
      full_name: c.full_name || "",
      headline: c.headline || null,
      current_company: c.current_company || null,
      current_title: c.current_title || null,
      location: c.location || null,
      profile_url: c.profile_url || null,
      score: c.score ?? null,
      predicted_rating: c.predicted_rating ?? null,
      first_found_run_id: c.first_found_run_id || null,
      sourcing_run: c.first_found_run || null,
      bundle_blob: JSON.stringify(c),
      review_state: rs,
      status: statusForReview(rs, c.status),
      feedback: c.feedback_free_text || c.feedback || "",
    });
  }
});
tx(candidates);

const generalFeedback = Array.isArray(bundle.general_feedback)
  ? bundle.general_feedback
  : [];
if (generalFeedback.length) {
  const latest = generalFeedback[generalFeedback.length - 1];
  if (latest && typeof latest.free_text === "string") {
    db.prepare(
      "UPDATE general_feedback SET content = ?, updated_at = CURRENT_TIMESTAMP WHERE id = 1",
    ).run(latest.free_text);
  }
}

const runs = Array.isArray(bundle.runs) ? bundle.runs : [];
db.exec("DELETE FROM runs");
const upsertRun = db.prepare(
  "INSERT OR REPLACE INTO runs (run_id, label, started_at, completed_at, run_number) VALUES (?, ?, ?, ?, ?)",
);
db.transaction(() => {
  for (const r of runs) {
    if (!r || !r.run_id) continue;
    upsertRun.run(
      r.run_id,
      r.label || null,
      r.started_at || null,
      r.completed_at || null,
      r.run_number ?? null,
    );
  }
})();

const themes = Array.isArray(bundle.feedback_themes)
  ? bundle.feedback_themes
  : [];
db.exec("DELETE FROM feedback_themes");
const upsertTheme = db.prepare(
  `INSERT OR REPLACE INTO feedback_themes
     (theme_id, label, source, detected_in_run_id, applied_to_run_id, action_taken, description, created_at)
   VALUES (?, ?, ?, ?, ?, ?, ?, ?)`,
);
db.transaction(() => {
  for (const t of themes) {
    if (!t || !t.theme_id) continue;
    upsertTheme.run(
      t.theme_id,
      t.label || "(no theme)",
      t.source || null,
      t.detected_in_run_id || null,
      t.applied_to_run_id || null,
      t.action_taken || null,
      t.description || null,
      t.created_at || null,
    );
  }
})();

const exclusions = Array.isArray(bundle.ashby_exclusions)
  ? bundle.ashby_exclusions
  : [];
db.exec("DELETE FROM ashby_exclusions");
const upsertExcl = db.prepare(
  `INSERT OR REPLACE INTO ashby_exclusions
     (exclusion_id, candidate_name, reason, status, source, excluded_at)
   VALUES (?, ?, ?, ?, ?, ?)`,
);
db.transaction(() => {
  for (const e of exclusions) {
    if (!e || !e.exclusion_id) continue;
    upsertExcl.run(
      e.exclusion_id,
      e.candidate_name || "",
      e.reason || null,
      e.status || null,
      e.source || null,
      e.excluded_at || null,
    );
  }
})();

const seeds = Array.isArray(bundle.hired_seed_profiles)
  ? bundle.hired_seed_profiles
  : [];
db.exec("DELETE FROM hired_seed_profiles");
const upsertSeed = db.prepare(
  `INSERT OR REPLACE INTO hired_seed_profiles
     (profile_id, full_name, role, company, profile_url, summary)
   VALUES (?, ?, ?, ?, ?, ?)`,
);
db.transaction(() => {
  for (const s of seeds) {
    if (!s || !s.profile_id) continue;
    upsertSeed.run(
      s.profile_id,
      s.full_name || "",
      s.role || null,
      s.company || null,
      s.profile_url || null,
      s.summary || null,
    );
  }
})();

if (bundle.workflow_settings && typeof bundle.workflow_settings === "object") {
  db.prepare("UPDATE workflow_settings SET settings_json = ? WHERE id = 1").run(
    JSON.stringify(bundle.workflow_settings),
  );
}

console.log(
  `seeded ${candidates.length} candidates / ${runs.length} runs / ${themes.length} themes / ${exclusions.length} ashby exclusions into ${DB_PATH} from ${bundlePath}`,
);
