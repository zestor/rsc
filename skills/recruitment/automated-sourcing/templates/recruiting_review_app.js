// Automated Sourcing review UI driver.
//
// Production / workflow mode: the page is served by the scaffolded review-app
// (see recruitment/automated-sourcing/server-template/). On startup the JS fetches
// every read section from the SQLite-backed API and re-renders against that.
// Every Yes/Maybe/No click PATCHes /api/candidates/{ref}; the "Save general
// feedback" button PUTs /api/general-feedback. Writes never have a local
// fallback — they surface "Save failed — retry" on any non-2xx.
//
// Static preview mode: when the page is opened from disk or served by a host
// that does not implement the API, the read calls fail and the UI falls back
// to the embedded #review-bundle JSON for the initial render. Click handlers
// still attempt the PATCH/PUT and visibly fail; the preview is for visual QA
// only and must not be used as the actual review surface.
//
// API base resolution: the `__PORT_3000__` token is replaced by the
// website-deployment pipeline with the proxy path that routes back to the
// sandbox-side Express server. While the token is still literal (local dev,
// any non-deployed render) the helper falls back to `http://localhost:3000`,
// which is also where `npm start` binds during workflow review. Every fetch
// goes through `apiUrl(path)` — never bare `/api/...` — so the same bundle
// works in both modes without rebuilding.
(() => {
  "use strict";

  const REVIEW_GROUP_ORDER = ["unreviewed", "yes", "maybe", "no"];
  const UI_REVIEW_STATES = new Set(["yes", "maybe", "no", "unreviewed"]);

  function reviewStateFromWire(wire) {
    if (!wire) return "unreviewed";
    const v = String(wire).toLowerCase().trim();
    if (v === "pending" || v === "") return "unreviewed";
    return UI_REVIEW_STATES.has(v) ? v : "unreviewed";
  }

  function normalizeCandidateWire(row) {
    // Single funnel: every candidate that enters state.candidates flows
    // through here, so wire-shaped `pending` can never leak into groupKey,
    // the chip, or the detail panel and create a second "Pending" group
    // alongside the real `unreviewed` one.
    if (!row || typeof row !== "object") return row;
    return { ...row, review_state: reviewStateFromWire(row.review_state) };
  }

  function reviewStateOf(c) {
    // Single read funnel. The local mirror wins (last user click), then
    // c.review_state which is already normalized at entry; `reviewStateFromWire`
    // is a final safety net for any path that bypasses normalization.
    if (!c) return "unreviewed";
    const local = state && state.localReviews && state.localReviews[c.candidate_id];
    if (local && local.review_state) return reviewStateFromWire(local.review_state);
    return reviewStateFromWire(c.review_state);
  }

  const API_PORT_PLACEHOLDER = "__PORT_3000__";
  const API_BASE = API_PORT_PLACEHOLDER.startsWith("__")
    ? "http://localhost:3000"
    : API_PORT_PLACEHOLDER.replace(/\/$/, "");

  function apiUrl(path) {
    return API_BASE + path;
  }

  const bundleEl = document.getElementById("review-bundle");
  let bundle;
  try {
    bundle = JSON.parse((bundleEl && bundleEl.textContent) || "{}");
  } catch (err) {
    console.error("review-bundle JSON parse failed", err);
    bundle = {};
  }
  const state = {
    candidates: (Array.isArray(bundle.candidates) ? bundle.candidates : []).map(
      (row) => normalizeCandidateWire(row),
    ),
    activeIndex: -1,
    selectedId: null,
    filter: "all",
    search: "",
    groupBy: "review_state",
    localReviews: Object.create(null),
    apiAvailable: null,
  };

  async function fetchJson(path) {
    const resp = await fetch(apiUrl(path));
    if (!resp.ok) {
      throw new Error(`HTTP ${resp.status}`);
    }
    return resp.json();
  }

  function mergeApiCandidates(rows) {
    const byId = new Map(state.candidates.map((c) => [c.candidate_id, c]));
    state.candidates = rows.map((row) => {
      const normalized = normalizeCandidateWire(row);
      const prior = byId.get(normalized.candidate_id) || {};
      const local = state.localReviews[normalized.candidate_id];
      return {
        ...prior,
        ...normalized,
        // Local clicks made during a slow bootstrap must not be clobbered by
        // the server snapshot that started before them. Without `local`, the
        // server value (already normalized) wins — that's the source of
        // truth for the canonical post-refresh state.
        review_state: local ? local.review_state : normalized.review_state,
        feedback_free_text:
          (local && local.feedback_free_text) || normalized.feedback || "",
      };
    });
  }

  async function bootstrapFromApi() {
    const results = await Promise.allSettled([
      fetchJson("/api/candidates"),
      fetchJson("/api/general-feedback"),
      fetchJson("/api/runs"),
      fetchJson("/api/feedback-themes"),
      fetchJson("/api/ashby-exclusions"),
      fetchJson("/api/hired-seed-profiles"),
      fetchJson("/api/workflow-settings"),
    ]);
    const [
      candidates,
      generalFeedback,
      runs,
      themes,
      exclusions,
      seeds,
      workflowSettings,
    ] = results;
    const apiUp = results.every((r) => r.status === "fulfilled");
    state.apiAvailable = apiUp;
    if (candidates.status === "fulfilled" && Array.isArray(candidates.value)) {
      mergeApiCandidates(candidates.value);
    }
    if (generalFeedback.status === "fulfilled" && generalFeedback.value) {
      bundle.general_feedback = [
        {
          feedback_id: "current",
          free_text: generalFeedback.value.content || "",
          submitted_at: generalFeedback.value.updated_at || null,
        },
      ];
    }
    if (runs.status === "fulfilled" && Array.isArray(runs.value)) {
      bundle.runs = runs.value;
    }
    if (themes.status === "fulfilled" && Array.isArray(themes.value)) {
      bundle.feedback_themes = themes.value;
    }
    if (exclusions.status === "fulfilled" && Array.isArray(exclusions.value)) {
      bundle.ashby_exclusions = exclusions.value;
    }
    if (seeds.status === "fulfilled" && Array.isArray(seeds.value)) {
      bundle.hired_seed_profiles = seeds.value;
    }
    if (
      workflowSettings.status === "fulfilled" &&
      workflowSettings.value &&
      typeof workflowSettings.value === "object"
    ) {
      bundle.workflow_settings = workflowSettings.value;
    }
    if (!apiUp) {
      console.warn(
        "[automated-sourcing] API not fully available; rendering bundled preview snapshot for visual QA only",
      );
    } else {
      // Visible diagnostic for the reviewer's DevTools so a future stale
      // page can be debugged quickly: counts per UI state plus the API
      // base in use confirm that the live merge actually ran.
      const counts = state.candidates.reduce((acc, c) => {
        const k = reviewStateOf(c);
        acc[k] = (acc[k] || 0) + 1;
        return acc;
      }, Object.create(null));
      console.info(
        "[automated-sourcing] bootstrap merged " +
          state.candidates.length +
          " candidates from API (" +
          API_BASE +
          "):",
        counts,
      );
    }
  }

  const $ = (id) => document.getElementById(id);

  const SCORE_RING_RADIUS = 18;
  const SCORE_RING_DETAIL_RADIUS = 26;
  const SCORE_RING_VIEWBOX = "0 0 44 44";
  const SCORE_RING_DETAIL_VIEWBOX = "0 0 64 64";

  function scoreBand(score) {
    if (score == null) return "";
    if (score >= 9) return "strong";
    if (score >= 7) return "maybe";
    return "weak";
  }

  function renderScoreRing(el, score, variant) {
    const detail = variant === "detail";
    const radius = detail ? SCORE_RING_DETAIL_RADIUS : SCORE_RING_RADIUS;
    const viewBox = detail ? SCORE_RING_DETAIL_VIEWBOX : SCORE_RING_VIEWBOX;
    const cx = detail ? 32 : 22;
    const cy = cx;
    const circumference = 2 * Math.PI * radius;
    const fraction = score == null ? 0 : Math.max(0, Math.min(1, score / 10));
    const offset = circumference * (1 - fraction);
    el.classList.add("score-ring");
    if (detail) el.classList.add("score-ring-detail");
    el.setAttribute("data-band", scoreBand(score));
    el.innerHTML =
      '<svg viewBox="' + viewBox + '" aria-hidden="true">' +
      '<circle class="ring-track" cx="' + cx + '" cy="' + cy + '" r="' + radius + '"></circle>' +
      '<circle class="ring-fill" cx="' + cx + '" cy="' + cy + '" r="' + radius + '"' +
      ' stroke-dasharray="' + circumference.toFixed(2) + '"' +
      ' stroke-dashoffset="' + offset.toFixed(2) + '"></circle>' +
      '</svg>' +
      '<span class="ring-center">' + (score == null ? "—" : String(score)) + '</span>';
  }

  function renderSidebar() {
    const ws = bundle.workflow_settings || {};
    const wsView = ws.view || {};
    $("ws-scheduled").textContent =
      wsView.scheduled_text || (ws.cadence_scheduled ? "Scheduled" : "Manual only");
    $("ws-cadence").textContent = wsView.cadence_label || ws.run_cadence || "manual";
    $("ws-last-run").textContent =
      wsView.last_run_text || formatTimestamp(ws.last_run_at) || "—";
    $("ws-next-run").textContent =
      wsView.next_run_text || formatTimestamp(ws.next_run_at) || "—";
    $("ws-timezone").textContent = wsView.timezone_text || ws.timezone || "—";
    $("ws-batch").textContent =
      wsView.batch_text || (ws.batch_size != null ? String(ws.batch_size) : "—");
    $("ws-channels").textContent =
      wsView.channels_text || (ws.notification_channels || []).join(", ") || "—";
    const statusEl = $("ws-status-text");
    if (statusEl)
      statusEl.textContent = humanizeEmbeddedTimestamps(
        wsView.status_text || ws.status_text || "",
      );
    const latestRunEl = $("latest-run");
    if (latestRunEl && wsView.header_run_summary) {
      latestRunEl.textContent = wsView.header_run_summary;
    }
    const sheet = $("ws-sheet");
    if (ws.sheet_export_url) {
      sheet.href = ws.sheet_export_url;
      sheet.textContent = "Sheet export";
    } else {
      sheet.style.display = "none";
    }
    const reviewUrl = $("ws-review-url");
    if (ws.review_ui_url) {
      reviewUrl.href = ws.review_ui_url;
      reviewUrl.textContent = "Review URL";
    } else {
      reviewUrl.style.display = "none";
    }

    const themes = bundle.feedback_themes || [];
    const themeList = $("theme-list");
    themeList.innerHTML = "";
    for (const t of themes) {
      themeList.appendChild(buildThemeRow(t));
    }
    if (!themes.length) {
      themeList.innerHTML = '<li class="muted">No themes yet.</li>';
    }

    const seeds = bundle.hired_seed_profiles || [];
    const seedList = $("seed-list");
    seedList.innerHTML = "";
    for (const s of seeds) {
      const li = document.createElement("li");
      const name = document.createElement("div");
      name.className = "theme-label";
      name.textContent = s.full_name;
      li.appendChild(name);
      const sub = document.createElement("div");
      sub.className = "theme-source";
      sub.textContent = [s.role, s.company].filter(Boolean).join(" · ");
      if (sub.textContent) li.appendChild(sub);
      if (s.summary) {
        const desc = document.createElement("div");
        desc.className = "theme-desc";
        desc.textContent = s.summary;
        li.appendChild(desc);
      }
      seedList.appendChild(li);
    }
    if (!seeds.length) {
      seedList.innerHTML = '<li class="muted">None.</li>';
    }

    const excl = bundle.ashby_exclusions || [];
    const exclList = $("exclusion-list");
    exclList.innerHTML = "";
    for (const e of excl) {
      const view = e.view || {};
      const li = document.createElement("li");
      const name = document.createElement("span");
      name.className = "exclusion-name";
      name.textContent = view.primary_line || e.candidate_name;
      li.appendChild(name);
      if (view.secondary_line) {
        const reason = document.createElement("span");
        reason.className = "exclusion-reason";
        reason.textContent = view.secondary_line;
        li.appendChild(reason);
      }
      if (view.tertiary_line) {
        const when = document.createElement("span");
        when.className = "exclusion-when";
        when.textContent = view.tertiary_line;
        li.appendChild(when);
      }
      exclList.appendChild(li);
    }
    if (!excl.length) {
      exclList.innerHTML = '<li class="muted">None.</li>';
    }

    renderGeneralFeedback();
  }

  function renderGeneralFeedback() {
    const ta = $("general-feedback-text");
    const meta = $("general-feedback-meta");
    if (!ta || !meta) return;
    const entries = bundle.general_feedback || [];
    const latest = entries.length ? entries[entries.length - 1] : null;
    if (!latest) {
      ta.value = "";
      ta.placeholder = "No general feedback recorded yet.";
      meta.textContent = "Not yet provided.";
      return;
    }
    const view = latest.view || {};
    ta.value = view.free_text != null ? view.free_text : latest.free_text || "";
    const metaParts = [];
    if (view.submitted_at_text) {
      metaParts.push(`Updated ${view.submitted_at_text}`);
    } else if (latest.submitted_at) {
      metaParts.push(`Updated ${formatTimestamp(latest.submitted_at)}`);
    }
    const appliedLabel = view.applied_run_label
      ? view.applied_run_label
      : latest.applied_to_run_id
      ? runLabelFor(latest.applied_to_run_id)
      : "";
    if (appliedLabel) {
      metaParts.push(`Applied in ${appliedLabel}`);
    }
    meta.textContent = metaParts.join(" · ");
  }

  function setSaving(status) {
    if (!status) return;
    status.textContent = "Saving…";
    status.className = "save-status";
    status.title = "";
  }

  function setSaved(status) {
    if (!status) return;
    status.textContent = "Saved";
    status.className = "save-status save-success";
    status.title = "";
  }

  function setSaveFailed(status, err) {
    if (!status) return;
    status.textContent = "Save failed — retry";
    status.className = "save-status save-error";
    status.title = `Save failed: ${err && err.message ? err.message : err}`;
  }

  async function sendJson(path, method, body) {
    const resp = await fetch(apiUrl(path), {
      method,
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    if (!resp.ok) {
      throw new Error(`HTTP ${resp.status}`);
    }
    return resp.json().catch(() => ({}));
  }

  function wireReviewState(uiState) {
    return uiState === "unreviewed" ? "pending" : uiState;
  }

  async function saveGeneralFeedback() {
    const ta = $("general-feedback-text");
    const status = $("general-feedback-status");
    if (!ta) return;
    const content = ta.value;
    setSaving(status);
    try {
      const row = await sendJson("/api/general-feedback", "PUT", { content });
      if (row && typeof row.content === "string") ta.value = row.content;
      setSaved(status);
    } catch (err) {
      setSaveFailed(status, err);
    }
  }

  function formatTimestamp(value) {
    if (!value) return "";
    const s = String(value);
    let trimmed = s.replace("T", " ").split(".")[0];
    if (trimmed.includes("+") && trimmed.indexOf("+") >= 10) {
      trimmed = trimmed.split("+", 1)[0].trim();
    }
    if (trimmed.endsWith("Z")) trimmed = trimmed.slice(0, -1);
    const parts = trimmed.split(" ");
    if (parts.length === 2 && parts[1].length >= 5) {
      return `${parts[0]} ${parts[1].slice(0, 5)}`;
    }
    return trimmed.trim();
  }

  const META_LINE_SEPARATORS_RE = /[\s·•|/,\-–—]+/g;
  const META_LINE_TOKEN_RE = /[^a-z0-9]+/g;
  const META_LINE_JOINER_WORDS = new Set(["at", "in", "for", "of", "the", "and"]);

  function metaLineSignature(text) {
    return String(text || "").replace(META_LINE_SEPARATORS_RE, "").toLowerCase();
  }

  function metaLineTokens(text) {
    return String(text || "")
      .toLowerCase()
      .split(META_LINE_TOKEN_RE)
      .filter((t) => t && !META_LINE_JOINER_WORDS.has(t));
  }

  function metaLinesDuplicate(headline, currentLine) {
    if (!headline || !currentLine) return false;
    if (metaLineSignature(headline) === metaLineSignature(currentLine)) return true;
    const headlineTokens = metaLineTokens(headline);
    if (headlineTokens.length === 0) return false;
    const currentSet = new Set(metaLineTokens(currentLine));
    return headlineTokens.every((t) => currentSet.has(t));
  }

  const ISO_TIMESTAMP_RE =
    /\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:?\d{2})?/g;

  function humanizeEmbeddedTimestamps(text) {
    if (!text) return "";
    return String(text).replace(ISO_TIMESTAMP_RE, (m) => formatTimestamp(m) || m);
  }

  function buildThemeRow(t) {
    const view = t.view || {};
    const li = document.createElement("li");
    li.className = "theme-row";

    const header = document.createElement("div");
    header.className = "theme-row-header";
    const source = document.createElement("span");
    source.className = "theme-row-source";
    source.textContent = view.source_label || "Feedback";
    header.appendChild(source);
    if (view.run_relation && view.run_label) {
      const run = document.createElement("span");
      run.className = "theme-row-run";
      run.textContent = `${view.run_relation} ${view.run_label}`;
      header.appendChild(run);
    }
    if (view.created_at_text) {
      const when = document.createElement("span");
      when.className = "theme-row-when";
      when.textContent = view.created_at_text;
      header.appendChild(when);
    }
    li.appendChild(header);

    const label = document.createElement("div");
    label.className = "theme-row-label";
    label.textContent = view.label_text || t.label || "(no theme)";
    li.appendChild(label);

    if (view.action_text) {
      const action = document.createElement("div");
      action.className = "theme-row-action";
      const actionLabel = document.createElement("strong");
      actionLabel.textContent = "Action — ";
      action.appendChild(actionLabel);
      action.appendChild(document.createTextNode(view.action_text));
      li.appendChild(action);
    }

    return li;
  }

  function currentList() {
    const term = state.search.trim().toLowerCase();
    return state.candidates.filter((c) => {
      const reviewState = reviewStateOf(c);
      if (state.filter !== "all" && reviewState !== state.filter) return false;
      if (!term) return true;
      const hay = [
        c.full_name,
        c.current_title,
        c.current_company,
        c.location,
        c.headline,
      ]
        .filter(Boolean)
        .join(" ")
        .toLowerCase();
      return hay.includes(term);
    });
  }

  function buildRow(c, idx) {
    const li = document.createElement("li");
    li.className = "candidate-row";
    const reviewState = reviewStateOf(c);
    if (reviewState && reviewState !== "unreviewed") li.classList.add("reviewed");
    if (state.activeIndex === idx) li.classList.add("active");
    li.dataset.idx = String(idx);

    const ring = document.createElement("span");
    renderScoreRing(ring, c.score, "row");

    const main = document.createElement("div");
    main.className = "candidate-row-main";
    const name = document.createElement("div");
    name.className = "candidate-name";
    name.textContent = c.full_name;
    const sub = document.createElement("div");
    sub.className = "candidate-sub";
    sub.textContent = [c.current_title, c.current_company, c.location]
      .filter(Boolean)
      .join(" · ");
    main.appendChild(name);
    main.appendChild(sub);
    if (c.profile_url) {
      const link = document.createElement("a");
      link.className = "candidate-link";
      link.href = c.profile_url;
      link.target = "_blank";
      link.rel = "noopener noreferrer";
      link.textContent = "LinkedIn";
      link.addEventListener("click", (e) => e.stopPropagation());
      main.appendChild(link);
    }

    const tags = document.createElement("div");
    tags.className = "candidate-tags";
    const view = c.view || {};
    const viewTags = Array.isArray(view.tags) ? view.tags : null;
    if (viewTags) {
      for (const t of viewTags.filter((t) => !isStatefulChipTag(t))) {
        tags.appendChild(makeTag(t.label, t.mood));
      }
    } else {
      if (c.tenure_risk && c.tenure_risk !== "none") {
        tags.appendChild(makeTag(`tenure: ${c.tenure_risk}`, "warn"));
      }
      if (c.internal_history_status && c.internal_history_status !== "none") {
        tags.appendChild(makeTag(`internal: ${c.internal_history_status}`, "warn"));
      }
      if (c.ashby && c.ashby.match_status) {
        const mood =
          c.ashby.match_status === "clear"
            ? "good"
            : c.ashby.match_status === "excluded"
            ? "bad"
            : c.ashby.match_status === "possible_duplicate"
            ? "warn"
            : "";
        tags.appendChild(makeTag(`Ashby: ${c.ashby.match_status}`, mood));
      }
      if (c.company_quality_tier && c.company_quality_tier !== "unknown") {
        tags.appendChild(makeTag(c.company_quality_tier.replace("_", " ")));
      }
    }
    tags.appendChild(
      makeTag(
        reviewDecisionLabel(reviewState || "unreviewed"),
        "review-state " + (reviewState || "unreviewed"),
      ),
    );

    li.appendChild(ring);
    li.appendChild(main);
    li.appendChild(tags);
    li.addEventListener("click", () => selectIndex(idx));
    return li;
  }

  function groupKey(c) {
    if (state.groupBy === "review_state") {
      // reviewStateOf is the single read funnel — pending/unreviewed always
      // collapse to the same canonical `unreviewed` bucket, never two
      // "Pending" headers.
      return reviewStateOf(c);
    }
    if (state.groupBy === "found_run") {
      return c.first_found_run_id || c.first_found_run || "";
    }
    return null;
  }

  function groupLabel(key) {
    if (state.groupBy !== "review_state") return key;
    // Group header uses the same human labels as the card chip
    // (Pending / Yes / Maybe / No) so the UI never shows both
    // "Unreviewed" and "Pending" for the same state.
    return reviewDecisionLabel(key || "unreviewed");
  }

  function runLabelFor(runId) {
    if (!runId) return "Earlier run";
    const labels = (bundle.view && bundle.view.run_labels) || {};
    if (labels[runId]) return labels[runId];
    const runs = bundle.runs || [];
    const match = runs.find((r) => r.run_id === runId);
    if (match && match.label) return match.label;
    return "Earlier run";
  }

  function renderFeed() {
    const list = $("candidate-list");
    list.innerHTML = "";
    const filtered = currentList();
    if (!filtered.length) {
      list.innerHTML = '<li class="muted">No candidates match.</li>';
      return;
    }
    if (state.groupBy === "none") {
      filtered.forEach((c, idx) => list.appendChild(buildRow(c, idx)));
      return;
    }
    const groups = new Map();
    filtered.forEach((c, idx) => {
      const key = groupKey(c);
      if (!groups.has(key)) groups.set(key, []);
      groups.get(key).push({ c, idx });
    });
    const orderedKeys = [...groups.keys()].sort((a, b) => {
      if (state.groupBy === "review_state") {
        return REVIEW_GROUP_ORDER.indexOf(a) - REVIEW_GROUP_ORDER.indexOf(b);
      }
      return String(a).localeCompare(String(b));
    });
    for (const key of orderedKeys) {
      const rows = groups.get(key) || [];
      const header = document.createElement("li");
      header.className = "candidate-group-header";
      const left = document.createElement("span");
      left.className = "candidate-group-label";
      left.textContent =
        state.groupBy === "found_run" ? runLabelFor(key) : groupLabel(key);
      const right = document.createElement("span");
      right.className = "candidate-group-count";
      right.textContent = String(rows.length);
      header.appendChild(left);
      header.appendChild(right);
      list.appendChild(header);
      for (const { c, idx } of rows) {
        list.appendChild(buildRow(c, idx));
      }
    }
  }

  function makeTag(text, mood) {
    const tag = document.createElement("span");
    tag.className = "tag" + (mood ? " " + mood : "");
    tag.textContent = text;
    return tag;
  }

  const REVIEW_STATE_KEYS = ["yes", "maybe", "no", "unreviewed", "pending"];

  function reviewDecisionLabels() {
    const view = bundle.view || {};
    const apiLabels = view.review_decision_labels || {};
    return {
      yes: "Yes",
      maybe: "Maybe",
      no: "No",
      unreviewed: "Pending",
      pending: "Pending",
      ...apiLabels,
    };
  }

  function reviewDecisionLabel(state) {
    const labels = reviewDecisionLabels();
    return labels[state] || labels.unreviewed;
  }

  function isStatefulChipTag(tag) {
    if (!tag || !tag.label) return false;
    const label = String(tag.label).trim().toLowerCase();
    const labels = reviewDecisionLabels();
    for (const key of REVIEW_STATE_KEYS) {
      if (label === key) return true;
      if (label === String(labels[key] || "").toLowerCase()) return true;
    }
    return false;
  }

  function selectIndex(idx) {
    const filtered = currentList();
    if (!filtered.length) {
      state.activeIndex = -1;
      state.selectedId = null;
      renderFeed();
      clearDetail();
      return;
    }
    const clamped = Math.max(0, Math.min(filtered.length - 1, idx));
    state.activeIndex = clamped;
    const selected = filtered[clamped];
    state.selectedId = selected.candidate_id;
    renderFeed();
    renderDetail(selected);
    hydrateCandidateFromApi(selected);
  }

  async function hydrateCandidateFromApi(c) {
    const ref = candidateRef(c);
    if (!ref) return;
    try {
      const full = normalizeCandidateWire(
        await fetchJson(`/api/candidates/${encodeURIComponent(ref)}`),
      );
      // The user may have clicked Yes/Maybe/No between selectIndex firing and
      // this hydrate landing. The in-memory local decision is newer than the
      // server echo we're holding, so prefer it when reconciling.
      const local = state.localReviews[c.candidate_id];
      const reviewState = local ? local.review_state : full.review_state;
      const merged = {
        ...c,
        ...full,
        review_state: reviewState,
        feedback_free_text:
          (local && local.feedback_free_text) ||
          full.feedback ||
          c.feedback_free_text ||
          "",
      };
      const idx = state.candidates.findIndex(
        (x) => x.candidate_id === merged.candidate_id,
      );
      if (idx >= 0) state.candidates[idx] = merged;
      if (state.selectedId === merged.candidate_id) {
        renderDetail(merged);
      }
    } catch (err) {
      console.warn(
        "[automated-sourcing] candidate hydrate failed:",
        err && err.message ? err.message : err,
      );
    }
  }

  function step(delta) {
    const filtered = currentList();
    if (!filtered.length) return;
    const next = Math.max(0, Math.min(filtered.length - 1, state.activeIndex + delta));
    selectIndex(next);
  }

  function reconcileSelection() {
    const filtered = currentList();
    if (!filtered.length) {
      state.activeIndex = -1;
      renderFeed();
      clearDetail();
      return;
    }
    const idx =
      state.selectedId == null
        ? -1
        : filtered.findIndex((c) => c.candidate_id === state.selectedId);
    selectIndex(idx >= 0 ? idx : 0);
  }

  function clearDetail() {
    const card = $("detail");
    const empty = $("detail-empty");
    if (card) card.classList.add("hidden");
    if (empty) empty.classList.remove("hidden");
  }

  function renderDetail(c) {
    $("detail-empty").classList.add("hidden");
    const card = $("detail");
    card.classList.remove("hidden");

    $("d-name").textContent = c.full_name;
    const view = c.view || {};
    const currentLine =
      view.current_line ||
      [c.current_title, c.current_company, c.location].filter(Boolean).join(" · ");
    let headlineText = view.headline_text;
    if (headlineText === undefined) {
      headlineText = (c.headline || "").trim();
    }
    if (headlineText && metaLinesDuplicate(headlineText, currentLine)) {
      headlineText = "";
    }
    const headlineEl = $("d-headline");
    headlineEl.textContent = headlineText;
    headlineEl.style.display = headlineText ? "" : "none";
    $("d-current").textContent = currentLine;

    renderScoreRing($("d-score-ring"), c.score, "detail");
    $("d-predicted").textContent =
      c.predicted_rating != null ? `predicted ${c.predicted_rating}` : "";

    setTag("d-recency", c.recent_relevance_window ? `recency: ${c.recent_relevance_window}` : null);
    setTag(
      "d-company-tier",
      c.company_quality_tier && c.company_quality_tier !== "unknown"
        ? `company: ${c.company_quality_tier.replace("_", " ")}`
        : null
    );
    setTag("d-tenure", c.tenure_risk && c.tenure_risk !== "none" ? `tenure: ${c.tenure_risk}` : null, "warn");
    setTag(
      "d-internal",
      c.internal_history_status && c.internal_history_status !== "none"
        ? `internal: ${c.internal_history_status}`
        : null,
      "warn"
    );
    if (c.ashby && c.ashby.match_status) {
      const a = c.ashby;
      const mood =
        a.match_status === "clear" ? "good" : a.match_status === "excluded" ? "bad" : "warn";
      const text =
        `Ashby: ${a.match_status}` +
        (a.match_confidence && a.match_confidence !== "none" ? ` (${a.match_confidence})` : "") +
        (a.match_reason ? ` — ${a.match_reason}` : "");
      setTag("d-ashby", text, mood);
    } else {
      setTag("d-ashby", null);
    }

    $("d-reason").textContent = c.main_reason_for_fit || "—";
    const mainConcern = mainConcernText(c);
    $("d-concern").textContent = mainConcern || "None";

    fillList("d-evidence", c.evidence_bullets);
    const bullets = concernBullets(c);
    fillList("d-concerns", bullets, { hideWhenEmpty: !mainConcern });

    const profile = $("d-profile-top");
    if (profile) {
      if (c.profile_url) {
        profile.href = c.profile_url;
        profile.style.display = "";
      } else {
        profile.style.display = "none";
      }
    }
    const links = $("d-links");
    if (links) {
      links.innerHTML = "";
      for (const [label, url] of Object.entries(c.profile_links || {})) {
        const a = document.createElement("a");
        a.className = "btn-link";
        a.href = url;
        a.target = "_blank";
        a.rel = "noopener";
        a.textContent = label;
        links.appendChild(a);
      }
    }

    renderFeedbackBlock(c);
  }

  function setTag(id, text, mood) {
    const el = $(id);
    el.className = "tag" + (mood ? " " + mood : "");
    if (text) {
      el.textContent = text;
      el.style.display = "";
    } else {
      el.style.display = "none";
    }
  }

  function fillList(id, items, opts) {
    const ul = $(id);
    ul.innerHTML = "";
    let list;
    if (Array.isArray(items)) {
      list = items;
    } else if (items == null || items === "") {
      list = [];
    } else {
      list = [String(items)];
    }
    for (const item of list) {
      const li = document.createElement("li");
      li.textContent = item;
      ul.appendChild(li);
    }
    if (!list.length) {
      if (opts && opts.hideWhenEmpty) {
        ul.style.display = "none";
        return;
      }
      ul.innerHTML = '<li class="muted">None</li>';
    }
    ul.style.display = "";
  }

  const MEANINGLESS_CONCERNS = new Set([
    "",
    "—",
    "-",
    "none",
    "no concern",
    "no concerns",
    "none identified",
    "n/a",
    "na",
    "null",
    "no concerns identified",
    "no concerns noted",
  ]);

  function isMeaningfulConcern(text) {
    if (text == null) return false;
    return !MEANINGLESS_CONCERNS.has(String(text).trim().toLowerCase());
  }

  function coerceBulletList(value) {
    if (value == null) return [];
    if (Array.isArray(value)) return value.map(String).filter(isMeaningfulConcern);
    const s = String(value).trim();
    if (!s) return [];
    return isMeaningfulConcern(s) ? [s] : [];
  }

  function concernBullets(c) {
    const view = c.view || {};
    if (view.concern_bullets !== undefined) return coerceBulletList(view.concern_bullets);
    return coerceBulletList(c.concerns);
  }

  function mainConcernText(c) {
    const view = c.view || {};
    if (view.main_concern_text !== undefined && view.main_concern_text !== null) {
      return String(view.main_concern_text);
    }
    if (isMeaningfulConcern(c.main_concern)) return String(c.main_concern).trim();
    const bullets = concernBullets(c);
    if (!bullets.length) return "";
    if (bullets.length === 1) return bullets[0];
    return bullets.map((b) => "• " + b).join("\n");
  }

  function renderFeedbackBlock(c) {
    // Read-only: do NOT populate state.localReviews here. localReviews is the
    // "user clicked this since page load" mirror. mergeApiCandidates and
    // hydrateCandidateFromApi treat its presence as proof of a click and
    // skip the server-wins reconciliation — so creating an entry just
    // because the user is *viewing* a card would freeze the candidate at
    // its embedded-bundle review_state and ignore the API.
    const reviewState = reviewStateOf(c);
    const feedback =
      (state.localReviews[c.candidate_id] &&
        state.localReviews[c.candidate_id].feedback_free_text) ||
      c.feedback_free_text ||
      "";
    const labelMap = (bundle.view && bundle.view.review_decision_labels) || {
      yes: "Yes",
      maybe: "Maybe",
      no: "No",
    };
    document.querySelectorAll(".review-actions [data-decision]").forEach((btn) => {
      btn.classList.toggle("active", btn.dataset.decision === reviewState);
      const decision = btn.dataset.decision;
      if (labelMap[decision]) btn.textContent = labelMap[decision];
    });
    $("d-free-text").value = feedback;
  }

  async function patchCandidate(candidateRef, body, statusElId) {
    const status = $(statusElId);
    setSaving(status);
    try {
      const row = await sendJson(
        `/api/candidates/${encodeURIComponent(candidateRef)}`,
        "PATCH",
        body
      );
      setSaved(status);
      return row;
    } catch (err) {
      setSaveFailed(status, err);
      return null;
    }
  }

  function candidateRef(c) {
    return c.candidate_id || c.profile_url;
  }

  function applyReviewStateLocally(c, decision) {
    const local =
      state.localReviews[c.candidate_id] ||
      (state.localReviews[c.candidate_id] = {
        review_state: "unreviewed",
        feedback_free_text: "",
      });
    local.review_state = decision;
    // Mirror onto state.candidates so every render path (cards, groupKey,
    // detail panel, filtered list) reads the same value — never just the
    // pre-bootstrap wire value. We assign in place so the array identity is
    // stable and selectIndex/active-index references keep pointing to the
    // same row across re-renders.
    const stateRow = state.candidates.find(
      (x) => x.candidate_id === c.candidate_id,
    );
    if (stateRow) {
      stateRow.review_state = decision;
      c.review_state = decision;
    }
    return local;
  }

  function applyServerCandidateRow(row) {
    if (!row || !row.candidate_id) return;
    const normalized = normalizeCandidateWire(row);
    const idx = state.candidates.findIndex(
      (x) => x.candidate_id === normalized.candidate_id,
    );
    if (idx < 0) return;
    const merged = {
      ...state.candidates[idx],
      ...normalized,
      feedback_free_text:
        row.feedback != null
          ? row.feedback
          : state.candidates[idx].feedback_free_text || "",
    };
    state.candidates[idx] = merged;
    // Reconcile the local mirror so a click that already advanced local
    // state doesn't get clobbered by the server echo.
    const local = state.localReviews[merged.candidate_id];
    if (local) {
      local.review_state = merged.review_state;
      if (row.feedback != null) local.feedback_free_text = row.feedback;
    }
  }

  function setDecision(decision) {
    const c = activeCandidate();
    if (!c) return;
    const local = applyReviewStateLocally(c, decision);
    renderFeed();
    renderFeedbackBlock(c);
    patchCandidate(
      candidateRef(c),
      { review_state: wireReviewState(local.review_state) },
      "review-save-status"
    ).then((row) => {
      if (!row) return;
      applyServerCandidateRow(row);
      if (state.selectedId === c.candidate_id) renderFeedbackBlock(c);
      renderFeed();
    });
  }

  function activeCandidate() {
    if (state.selectedId) {
      const byId = state.candidates.find(
        (x) => x.candidate_id === state.selectedId,
      );
      if (byId) return byId;
    }
    const filtered = currentList();
    return filtered[state.activeIndex] || null;
  }

  function saveAndNext() {
    const c = activeCandidate();
    if (c) {
      const local =
        state.localReviews[c.candidate_id] ||
        (state.localReviews[c.candidate_id] = {
          review_state: c.review_state || "unreviewed",
          feedback_free_text: c.feedback_free_text || "",
        });
      local.feedback_free_text = $("d-free-text").value;
      patchCandidate(
        candidateRef(c),
        { feedback: local.feedback_free_text },
        "save-status"
      ).then((row) => {
        if (row) applyServerCandidateRow(row);
      });
    }
    renderFeed();
    step(1);
  }

  function bindControls() {
    document.querySelectorAll(".review-actions [data-decision]").forEach((btn) => {
      btn.addEventListener("click", () => setDecision(btn.dataset.decision));
    });
    $("save-next").addEventListener("click", saveAndNext);
    $("search").addEventListener("input", (e) => {
      state.search = e.target.value;
      reconcileSelection();
    });
    $("review-filter").addEventListener("change", (e) => {
      state.filter = e.target.value;
      reconcileSelection();
    });
    const groupByEl = $("group-by");
    if (groupByEl) {
      groupByEl.addEventListener("change", (e) => {
        state.groupBy = e.target.value;
        reconcileSelection();
      });
    }
    const gfSave = $("general-feedback-save");
    if (gfSave) gfSave.addEventListener("click", saveGeneralFeedback);
    $("theme-toggle").addEventListener("click", () => {
      const cur = document.documentElement.getAttribute("data-theme");
      document.documentElement.setAttribute(
        "data-theme",
        cur === "dark" ? "light" : "dark"
      );
    });
    const showWorkflow = $("show-workflow-data");
    if (showWorkflow) {
      showWorkflow.addEventListener("click", (e) => {
        const target = document.getElementById("ops-section");
        if (target) {
          e.preventDefault();
          target.scrollIntoView({ behavior: "smooth", block: "start" });
        }
      });
    }
    document.addEventListener("keydown", (e) => {
      if (e.target && /^(INPUT|TEXTAREA)$/.test(e.target.tagName)) return;
      if (e.key === "j" || e.key === "ArrowDown") {
        e.preventDefault();
        step(1);
      } else if (e.key === "k" || e.key === "ArrowUp") {
        e.preventDefault();
        step(-1);
      } else if (e.key === "Enter") {
        e.preventDefault();
        saveAndNext();
      } else if (e.key === "y") {
        setDecision("yes");
      } else if (e.key === "n") {
        setDecision("no");
      } else if (e.key === "m") {
        setDecision("maybe");
      }
    });
  }

  function renderAll() {
    renderSidebar();
    renderFeed();
    reconcileSelection();
  }

  renderAll();
  bindControls();
  bootstrapFromApi()
    .catch((err) => {
      console.warn("[automated-sourcing] bootstrap failed:", err && err.message ? err.message : err);
    })
    .finally(renderAll);
})();
