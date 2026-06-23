"""Deterministic renderer for the Automated Sourcing recruiting review UI."""

from __future__ import annotations

import argparse
import dataclasses
import hashlib
import json
import re
import shutil
import sys
from collections.abc import Iterable
from dataclasses import asdict
from pathlib import Path
from typing import Any

from schemas import (
    SCHEMA_VERSION,
    AshbyExclusion,
    AshbyStatus,
    Candidate,
    FeedbackTheme,
    GeneralFeedback,
    HiredSeedProfile,
    ReviewBundle,
    Run,
    ScoreBreakdown,
    WorkflowSettings,
)

__all__ = (
    "normalize_score",
    "score_band",
    "predicted_rating_text",
    "humanize_iso_timestamp",
    "humanize_iso_timestamps_in_text",
    "humanize_run_label",
    "normalize_ashby_exclusion",
    "normalize_candidate",
    "normalize_bundle",
    "load_bundle",
    "validate_bundle",
    "render_bundle",
    "HTML_TEMPLATE",
    "CSS_TEMPLATE",
    "JS_TEMPLATE",
)

TEMPLATES_DIR = Path(__file__).parent / "templates"
SHARED_UI_DIR = Path(__file__).parent.parent / "shared" / "ui"
HTML_TEMPLATE = TEMPLATES_DIR / "recruiting_review_app.html"
CSS_TEMPLATE = TEMPLATES_DIR / "recruiting_review_app.css"
JS_TEMPLATE = TEMPLATES_DIR / "recruiting_review_app.js"
TOKENS_CSS = SHARED_UI_DIR / "tokens.css"

CADENCE_LABELS: dict[str, str] = {
    "manual": "Manual only",
    "hourly": "Hourly",
    "daily": "Daily",
    "weekly": "Weekly",
    "pause": "Paused",
}

ASHBY_STATUS_LABELS: dict[str, str] = {
    "clear": "Clear",
    "possible_duplicate": "Possible duplicate",
    "excluded": "Excluded",
    "unknown": "Unknown",
}

ASHBY_STATUS_MOODS: dict[str, str] = {
    "clear": "good",
    "excluded": "bad",
    "possible_duplicate": "warn",
    "unknown": "",
}

COMPANY_TIER_LABELS: dict[str, str] = {
    "tier_1": "Tier 1",
    "tier_2": "Tier 2",
    "tier_3": "Tier 3",
    "tier_4": "Tier 4",
    "unknown": "",
}

REVIEW_DECISION_LABELS: dict[str, str] = {
    "yes": "Yes",
    "maybe": "Maybe",
    "no": "No",
    "unreviewed": "Pending",
}

SAVE_LABEL: str = "Saved"

GROUP_BY_OPTIONS: tuple[tuple[str, str], ...] = (
    ("review_state", "Review state"),
    ("found_run", "Found run"),
    ("none", "None"),
)
DEFAULT_GROUP_BY: str = "review_state"

PREDICTED_RATING_DENOMINATOR: int = 10


class RendererError(ValueError):
    """Raised when the input bundle is structurally invalid."""


def normalize_score(raw: float | int | None) -> float | None:
    """Clamp a score to the 1-10 band the UI expects.

    The upstream sourcer may emit scores on a 0-100 or 0-1 scale; we
    project them to 1-10 so the renderer is robust to scale drift.
    """
    if raw is None:
        return None
    try:
        value = float(raw)
    except (TypeError, ValueError):
        return None
    if 0.0 <= value < 1.0:
        value = value * 10.0
    if value > 10.0:
        value = value / 10.0 if value <= 100.0 else 10.0
    value = max(1.0, min(10.0, value))
    return round(value, 1)


def score_band(score: float | None) -> str:
    if score is None:
        return ""
    if score >= 9:
        return "strong"
    if score >= 7:
        return "maybe"
    return "weak"


def predicted_rating_text(score: float | None) -> str:
    if score is None:
        return ""
    return f"predicted {score}/{PREDICTED_RATING_DENOMINATOR}"


def humanize_iso_timestamp(value: str | None) -> str:
    """Render an ISO-8601 timestamp as ``YYYY-MM-DD HH:MM`` for sidebar display.

    Why: SQLite exports emit timestamps like ``2026-05-19T07:09:57.081098+00:00``
    that overflow narrow sidebar cells when rendered raw. We strip sub-second
    precision and the offset before showing them.
    """
    if not value:
        return ""
    text = str(value).strip()
    if not text:
        return ""
    ts = text.replace("T", " ").split(".")[0]
    if "+" in ts and ts.index("+") >= 10:
        ts = ts.split("+", 1)[0].rstrip()
    if ts.endswith("Z"):
        ts = ts[:-1]
    parts = ts.split(" ")
    if len(parts) == 2 and len(parts[1]) >= 5:
        ts = f"{parts[0]} {parts[1][:5]}"
    return ts.strip()


_ISO_TIMESTAMP_IN_TEXT_RE = re.compile(
    r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(?::\d{2})?(?:\.\d+)?(?:Z|[+-]\d{2}:?\d{2})?"
)


def humanize_iso_timestamps_in_text(value: str | None) -> str:
    """Replace each ISO-8601 datetime embedded in free text with its humanized form.

    Why: upstream-built status / note strings (e.g. ``"Last completion 2026-05-19T07:09:57.081098+00:00"``)
    must never surface raw ISO strings in the UI chrome. This is the renderer-side
    scrubber that catches stray timestamps inside arbitrary text fields.
    """
    if not value:
        return ""
    return _ISO_TIMESTAMP_IN_TEXT_RE.sub(
        lambda m: humanize_iso_timestamp(m.group(0)), str(value)
    )


def humanize_run_label(
    run_id: str, started_at: str | None, run_number: int | None = None
) -> str:
    """Produce a stable human-readable label for a run.

    Never surfaces raw internal run ids. Prefers ``Run <n> · <date>`` when a
    run number is known, falls back to ``Run · <date>`` when only the start
    time is known, and to a generic ``Run`` only when nothing else is
    available.
    """
    ts = humanize_iso_timestamp(started_at)
    if run_number is not None and ts:
        return f"Run {run_number} · {ts}"
    if run_number is not None:
        return f"Run {run_number}"
    if ts:
        return f"Run · {ts}"
    return "Run"


def _dedupe_preserve_order(items: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for item in items:
        key = item.strip()
        if not key or key in seen:
            continue
        seen.add(key)
        out.append(key)
    return out


def _coerce_bullets(value: Any) -> list[str]:
    """Coerce a free-form evidence / concerns input into a list of clean strings.

    Why: SQLite exports often store list-like fields as a single JSON-encoded
    string (e.g. ``'["bullet 1", "bullet 2"]'``). The prior renderer treated
    them as plain text and produced one bullet that was the raw JSON literal.
    Accept lists, JSON-encoded list strings, and plain text with newline /
    bullet-character separators.
    """
    if value is None:
        return []
    if isinstance(value, list):
        return _dedupe_preserve_order(str(item) for item in value if item is not None)
    text = str(value).strip()
    if not text:
        return []
    if text.startswith("[") and text.endswith("]"):
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError:
            parsed = None
        if isinstance(parsed, list):
            return _dedupe_preserve_order(
                str(item).strip() for item in parsed if item is not None
            )
    lines = [
        line.strip().lstrip("-*•").strip()
        for line in text.replace("\r\n", "\n").split("\n")
    ]
    return _dedupe_preserve_order(lines)


def normalize_feedback_theme(theme: FeedbackTheme) -> FeedbackTheme:
    return FeedbackTheme(
        theme_id=theme.theme_id,
        label=theme.label.strip(),
        detected_in_run_id=theme.detected_in_run_id,
        applied_to_run_id=theme.applied_to_run_id,
        source=theme.source,
        description=(theme.description or None) and theme.description.strip(),
        action_taken=(theme.action_taken or None) and theme.action_taken.strip(),
        created_at=theme.created_at,
        example_candidate_ids=list(theme.example_candidate_ids),
    )


def normalize_ashby_exclusion(excl: AshbyExclusion) -> AshbyExclusion:
    """Drop raw internal IDs from display fields and normalize the
    human-readable surface (candidate_name first, then reason/status,
    then date). The source `exclusion_id` is retained on the dataclass
    for traceability but not surfaced to the UI by default.
    """
    reason = (excl.reason or "").strip() or None
    status = (excl.status or "").strip() or None
    source = (excl.source or "").strip() or None
    return AshbyExclusion(
        exclusion_id=excl.exclusion_id,
        candidate_name=excl.candidate_name.strip(),
        reason=reason,
        status=status,
        excluded_at=excl.excluded_at,
        source=source,
    )


def _flatten_bullets(items: Any) -> list[str]:
    """Flatten any JSON-array-encoded entries in a bullet list back to bullets.

    Accepts the schema-typed ``list[str]`` plus a raw string fallback for
    payloads that arrive with a single free-form value (e.g. an LLM emitted
    ``concerns: "None; candidate is …"`` instead of a list). Iterating a bare
    string would otherwise produce one bullet per character.
    """
    if items is None:
        return []
    if isinstance(items, str):
        return _coerce_bullets(items)
    out: list[str] = []
    for item in items:
        out.extend(_coerce_bullets(item))
    return _dedupe_preserve_order(out)


_MEANINGLESS_CONCERN_VALUES: frozenset[str] = frozenset(
    {
        "",
        "—",
        "-",
        "none",
        "no concerns",
        "no concern",
        "none identified",
        "n/a",
        "na",
        "null",
        "no concerns identified",
        "no concerns noted",
    }
)


def _is_meaningful_concern(text: str | None) -> bool:
    """Return True when a concern string carries real information."""
    if text is None:
        return False
    return text.strip().lower() not in _MEANINGLESS_CONCERN_VALUES


def _clean_concerns(items: list[str]) -> list[str]:
    """Flatten and drop placeholder-like concern entries."""
    return [c for c in _flatten_bullets(items) if _is_meaningful_concern(c)]


def _main_concern_text(c: Candidate) -> str:
    """Return the best human-readable concern text for the detail panel.

    Preference order: a meaningful ``main_concern`` field, then a single
    concern bullet joined cleanly, then an empty string when nothing is
    informative. Always returns plain text — never JSON or list syntax.
    """
    if _is_meaningful_concern(c.main_concern):
        return (c.main_concern or "").strip()
    cleaned = _clean_concerns(c.concerns)
    if not cleaned:
        return ""
    if len(cleaned) == 1:
        return cleaned[0]
    return "\n".join(f"• {item}" for item in cleaned)


DRAFT_OUTREACH_ARTIFACT_RE = re.compile(
    r"I came across your work on\s+Currently\s+",
    re.IGNORECASE,
)


def _clean_draft_outreach(text: str | None) -> str | None:
    """Strip a known upstream template artifact from draft outreach text.

    Why: outreach drafts that splice the candidate's role line into a
    "your work on …" phrase produce sentences like "I came across your work
    on Currently a Senior Software Engineer at Meta in London." We never
    rewrite the draft, but we cut that exact template fragment so the
    static UI doesn't surface a clearly broken sentence.
    """
    if not text:
        return text
    cleaned = DRAFT_OUTREACH_ARTIFACT_RE.sub("I came across your work — ", text)
    return cleaned.strip() or None


def normalize_candidate(c: Candidate) -> Candidate:
    return dataclasses.replace(
        c,
        score=normalize_score(c.score) if c.score is not None else None,
        raw_score=c.score if c.raw_score is None else c.raw_score,
        evidence_bullets=_flatten_bullets(c.evidence_bullets),
        concerns=_clean_concerns(c.concerns),
        main_concern=(c.main_concern or "").strip()
        if _is_meaningful_concern(c.main_concern)
        else None,
        draft_outreach=_clean_draft_outreach(c.draft_outreach),
    )


def normalize_bundle(bundle: ReviewBundle) -> ReviewBundle:
    """Apply all per-field normalizations to a bundle in place-safe form."""
    candidates = [normalize_candidate(c) for c in bundle.candidates]
    runs = [
        dataclasses.replace(
            r,
            label=r.label or humanize_run_label(r.run_id, r.started_at, r.run_number),
        )
        for r in bundle.runs
    ]
    themes = [normalize_feedback_theme(t) for t in bundle.feedback_themes]
    exclusions = [normalize_ashby_exclusion(e) for e in bundle.ashby_exclusions]
    # Dedupe exclusions by (candidate_name, reason, status, excluded_at).
    seen: set[tuple[str, str | None, str | None, str | None]] = set()
    deduped: list[AshbyExclusion] = []
    for e in exclusions:
        key = (e.candidate_name.lower(), e.reason, e.status, e.excluded_at)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(e)
    settings = bundle.workflow_settings
    if settings.run_cadence not in CADENCE_LABELS:
        settings = dataclasses.replace(settings, run_cadence="manual")
    return ReviewBundle(
        schema_version=bundle.schema_version or SCHEMA_VERSION,
        generated_at=bundle.generated_at,
        role_label=bundle.role_label,
        role_brief=bundle.role_brief,
        candidates=candidates,
        runs=runs,
        feedback_themes=themes,
        general_feedback=list(bundle.general_feedback),
        ashby_exclusions=deduped,
        hired_seed_profiles=list(bundle.hired_seed_profiles),
        workflow_settings=settings,
    )


def _from_dict(cls, data: Any):
    """Recursive dataclass-from-dict for our schema.

    Skips dataclasses too deep for stdlib introspection by inspecting
    field type hints lazily. Tolerates unknown / missing fields.
    """
    if data is None:
        try:
            return cls()
        except TypeError:
            return None
    if not dataclasses.is_dataclass(cls):
        return data
    field_types = {f.name: f.type for f in dataclasses.fields(cls)}
    kwargs: dict[str, Any] = {}
    for name, raw in data.items():
        if name not in field_types:
            continue
        kwargs[name] = raw
    # Hand-rolled coercion for nested dataclasses we know about.
    for name, target in _NESTED_FIELDS.get(cls.__name__, {}).items():
        if name not in kwargs:
            continue
        raw = kwargs[name]
        if raw is None:
            kwargs.pop(name)
            continue
        if isinstance(raw, dict):
            kwargs[name] = _from_dict(target, raw)
        elif isinstance(raw, list):
            kwargs[name] = [
                _from_dict(target, x) if isinstance(x, dict) else x for x in raw
            ]
    return cls(**kwargs)


_NESTED_FIELDS: dict[str, dict[str, type]] = {
    "Candidate": {
        "score_breakdown": ScoreBreakdown,
        "ashby": AshbyStatus,
    },
    "ReviewBundle": {
        "candidates": Candidate,
        "runs": Run,
        "feedback_themes": FeedbackTheme,
        "general_feedback": GeneralFeedback,
        "ashby_exclusions": AshbyExclusion,
        "hired_seed_profiles": HiredSeedProfile,
        "workflow_settings": WorkflowSettings,
    },
}


def load_bundle(payload: dict[str, Any]) -> ReviewBundle:
    if not isinstance(payload, dict):
        raise RendererError("bundle payload must be an object")
    return _from_dict(ReviewBundle, payload)


def validate_bundle(bundle: ReviewBundle) -> list[str]:
    """Return human-readable warnings (not errors) for missing fields.

    The renderer never raises on warnings; the workflow can choose to
    block sending if any warnings are present.
    """
    warnings: list[str] = []
    seen_ids: set[str] = set()
    for idx, c in enumerate(bundle.candidates):
        if not c.candidate_id:
            warnings.append(f"candidate[{idx}] missing candidate_id")
        elif c.candidate_id in seen_ids:
            warnings.append(f"candidate[{idx}] duplicate candidate_id={c.candidate_id}")
        else:
            seen_ids.add(c.candidate_id)
        if not c.full_name:
            warnings.append(f"candidate[{c.candidate_id or idx}] missing full_name")
        if c.score is None:
            warnings.append(f"candidate[{c.candidate_id or idx}] missing score")
    return warnings


def _candidate_tags(c: Candidate) -> list[dict[str, str]]:
    """Pre-build the list-view tag chips so the JS doesn't have to.

    Each tag is `{label, mood}` where mood is `good|warn|bad|""`. The review
    state is intentionally not included — the renderer's JS always derives a
    single live review-state chip from the in-memory state so it reflects
    Yes/Maybe/No clicks immediately. Baking a second one here would produce
    a duplicate chip after a reviewer changes their decision.
    """
    tags: list[dict[str, str]] = []
    if c.tenure_risk and c.tenure_risk != "none":
        tags.append({"label": f"tenure: {c.tenure_risk}", "mood": "warn"})
    if c.internal_history_status and c.internal_history_status != "none":
        tags.append({"label": f"internal: {c.internal_history_status}", "mood": "warn"})
    if c.ashby and c.ashby.match_status and c.ashby.match_status != "unknown":
        tags.append(
            {
                "label": (
                    f"Ashby: {ASHBY_STATUS_LABELS.get(c.ashby.match_status, c.ashby.match_status)}"
                ),
                "mood": ASHBY_STATUS_MOODS.get(c.ashby.match_status, ""),
            }
        )
    tier_label = COMPANY_TIER_LABELS.get(c.company_quality_tier or "", "")
    if tier_label:
        tags.append({"label": tier_label, "mood": ""})
    return tags


_META_LINE_SEPARATORS_RE = re.compile(r"[\s·•|/,\-–—]+")


def _meta_line_signature(text: str) -> str:
    """Return a comparable signature for two title/company/location lines.

    Why: the headline LLMs emit and the locally-joined ``current_line`` often
    carry the same three fields but with different separators (``·`` vs ``-``
    vs ``, ``). A naive ``==`` check leaves both renderings in the detail
    panel side by side. Stripping separators + lowercasing collapses every
    semantically-equivalent rendering to a single signature.
    """
    return _META_LINE_SEPARATORS_RE.sub("", text or "").lower()


def _candidate_view(c: Candidate) -> dict[str, Any]:
    score_display = "—" if c.score is None else str(c.score)
    current_line = " · ".join(
        [s for s in (c.current_title, c.current_company, c.location) if s]
    )
    headline = (c.headline or "").strip()
    headline_text = (
        headline
        if headline
        and _meta_line_signature(headline) != _meta_line_signature(current_line)
        else ""
    )
    main_concern_text = _main_concern_text(c)
    concern_bullets = _clean_concerns(c.concerns)
    return {
        "score_display": score_display,
        "score_band": score_band(c.score),
        "predicted_rating_text": predicted_rating_text(c.predicted_rating),
        "tags": _candidate_tags(c),
        "headline_text": headline_text,
        "current_line": current_line,
        "main_concern_text": main_concern_text,
        "concern_bullets": concern_bullets,
        "ashby_label": (
            ASHBY_STATUS_LABELS.get(c.ashby.match_status, "")
            if c.ashby and c.ashby.match_status
            else ""
        ),
        "ashby_mood": (
            ASHBY_STATUS_MOODS.get(c.ashby.match_status, "")
            if c.ashby and c.ashby.match_status
            else ""
        ),
    }


def _workflow_view(s: WorkflowSettings) -> dict[str, Any]:
    scheduled = s.cadence_scheduled and s.run_cadence not in ("manual", "pause")
    last_run_text = humanize_iso_timestamp(s.last_run_at) or "—"
    next_run_human = humanize_iso_timestamp(s.next_run_at)
    next_run_text = next_run_human or ("Next run not available" if scheduled else "—")
    timezone_text = s.timezone or "—"
    return {
        "scheduled_text": "Scheduled" if scheduled else "Manual only",
        "cadence_label": CADENCE_LABELS.get(s.run_cadence, "Manual only"),
        "channels_text": ", ".join(s.notification_channels) or "—",
        "batch_text": "—" if s.batch_size is None else str(s.batch_size),
        "threshold_text": (
            "—" if s.quality_threshold is None else str(s.quality_threshold)
        ),
        "last_run_text": last_run_text,
        "next_run_text": next_run_text,
        "timezone_text": timezone_text,
        "status_text": humanize_iso_timestamps_in_text(s.status_text),
        "is_scheduled": scheduled,
        "header_run_summary": _header_run_summary(
            scheduled=scheduled,
            last_run_text=last_run_text,
            next_run_human=next_run_human,
        ),
    }


def _header_run_summary(
    *,
    scheduled: bool,
    last_run_text: str,
    next_run_human: str,
) -> str:
    parts: list[str] = []
    if last_run_text and last_run_text != "—":
        parts.append(f"Last run {last_run_text}")
    if scheduled and next_run_human:
        parts.append(f"next {next_run_human}")
    elif scheduled and not next_run_human:
        parts.append("next unavailable")
    if not parts:
        return "No runs yet"
    return " · ".join(parts)


def _ashby_exclusion_view(e: AshbyExclusion) -> dict[str, Any]:
    return {
        "primary_line": e.candidate_name,
        "secondary_line": " · ".join([s for s in (e.reason, e.status) if s]),
        "tertiary_line": humanize_iso_timestamp(e.excluded_at),
    }


FEEDBACK_SOURCE_LABELS: dict[str, str] = {
    "candidate": "From candidate feedback",
    "general": "From general feedback",
    "system": "Auto-detected",
}


def _feedback_theme_view(
    t: FeedbackTheme, run_labels: dict[str, str]
) -> dict[str, Any]:
    applied = run_labels.get(t.applied_to_run_id or "", "")
    detected = run_labels.get(t.detected_in_run_id or "", "")
    run_label = applied or detected or ""
    created_text = humanize_iso_timestamp(t.created_at)
    return {
        "source_label": FEEDBACK_SOURCE_LABELS.get(t.source, "Feedback"),
        "run_label": run_label,
        "run_relation": "Applied in"
        if applied
        else ("Detected in" if detected else ""),
        "label_text": t.label or "(no theme)",
        "action_text": t.action_taken or "",
        "created_at_text": "" if run_label else created_text,
    }


def _general_feedback_view(
    g: GeneralFeedback, run_labels: dict[str, str]
) -> dict[str, Any]:
    applied = run_labels.get(g.applied_to_run_id or "", "")
    return {
        "free_text": g.free_text or "",
        "submitted_at_text": humanize_iso_timestamp(g.submitted_at),
        "applied_run_label": applied,
    }


def _build_view_payload(bundle: ReviewBundle) -> dict[str, Any]:
    """Attach `view` sub-objects to a normalized bundle's JSON form."""
    payload = asdict(bundle)
    run_labels = {
        r.run_id: r.label or humanize_run_label(r.run_id, r.started_at, r.run_number)
        for r in bundle.runs
    }
    for c_dict, c_obj in zip(payload["candidates"], bundle.candidates, strict=True):
        c_dict["view"] = _candidate_view(c_obj)
    payload["workflow_settings"]["view"] = _workflow_view(bundle.workflow_settings)
    for e_dict, e_obj in zip(
        payload["ashby_exclusions"], bundle.ashby_exclusions, strict=True
    ):
        e_dict["view"] = _ashby_exclusion_view(e_obj)
    for t_dict, t_obj in zip(
        payload["feedback_themes"], bundle.feedback_themes, strict=True
    ):
        t_dict["view"] = _feedback_theme_view(t_obj, run_labels)
    for g_dict, g_obj in zip(
        payload["general_feedback"], bundle.general_feedback, strict=True
    ):
        g_dict["view"] = _general_feedback_view(g_obj, run_labels)
    payload["view"] = {
        "review_decision_labels": dict(REVIEW_DECISION_LABELS),
        "cadence_label": CADENCE_LABELS.get(
            bundle.workflow_settings.run_cadence, "Manual only"
        ),
        "save_label": SAVE_LABEL,
        "role_label": bundle.role_label or "",
        "role_subtitle": _role_subtitle(bundle),
        "group_by_options": list(GROUP_BY_OPTIONS),
        "default_group_by": DEFAULT_GROUP_BY,
        "run_labels": run_labels,
    }
    return payload


_ROLE_LABEL_BOUNDARY_CHARS = frozenset(" \t-—:·,;|/()[]")


def _role_subtitle(bundle: ReviewBundle) -> str:
    """Return the role subtitle for the header without duplicating the role label.

    Why: the prior template piped `role_brief` straight under the role title.
    When the brief happens to start with the role name (e.g. exports that
    emit "Role: <title>" or just the role title), it renders the title twice.

    Only trim the label prefix when the following character is a separator
    or end-of-string. Without that boundary check, a label like "Engineer"
    would mis-trim "Engineering at Acme — payments focus" to "ing at Acme…".
    """
    label = (bundle.role_label or "").strip()
    brief = (bundle.role_brief or "").strip()
    if not brief:
        return ""
    candidate = brief
    if candidate.lower().startswith("role:"):
        candidate = candidate.split(":", 1)[1].strip()
    if label and candidate.lower().startswith(label.lower()):
        after = candidate[len(label) : len(label) + 1]
        if not after or after in _ROLE_LABEL_BOUNDARY_CHARS:
            candidate = candidate[len(label) :].lstrip(" -—:·,;|/\t")
    return candidate


def _asset_hash() -> str:
    """Short deterministic fingerprint over the JS + CSS template contents.

    Why: deployed static hosts (CDNs, browsers) aggressively cache the
    immutable-looking ``recruiting_review_app.{js,css}`` paths, so a fresh
    deploy with a corrected JS can still serve the *old* JS to a reviewer
    who hit the page before. Appending ``?v=<hash>`` busts the cache
    whenever the renderer changes shape — but stays stable across deploys
    of the same renderer so the static output is still byte-identical for
    the same input bundle + same template version.
    """
    h = hashlib.sha1()
    h.update(JS_TEMPLATE.read_bytes())
    h.update(b"\0")
    h.update(CSS_TEMPLATE.read_bytes())
    h.update(b"\0")
    h.update(TOKENS_CSS.read_bytes())
    return h.hexdigest()[:12]


def render_bundle(bundle: ReviewBundle, output_dir: Path) -> dict[str, Path]:
    """Write the static UI bundle to `output_dir`.

    Returns the map of artifact name -> path.
    """
    normalized = normalize_bundle(bundle)
    output_dir.mkdir(parents=True, exist_ok=True)
    serialized = json.dumps(
        _build_view_payload(normalized), sort_keys=True, separators=(",", ":")
    )
    # Escape `</script` to keep the payload safe inside a <script> tag.
    safe = serialized.replace("</", "<\\/")
    html_template = HTML_TEMPLATE.read_text(encoding="utf-8")
    role_label = normalized.role_label or "Automated Sourcing Review"
    role_subtitle = _role_subtitle(normalized)
    latest_run_text = _workflow_view(normalized.workflow_settings)["header_run_summary"]
    has_candidates = bool(normalized.candidates)
    initial_empty_class = "" if not has_candidates else "hidden"
    initial_detail_class = "" if has_candidates else "hidden"
    asset_hash = _asset_hash()
    html = (
        html_template.replace("{{ROLE_LABEL}}", _html_escape(role_label))
        .replace("{{ROLE_BRIEF}}", _html_escape(role_subtitle))
        .replace("{{LATEST_RUN_TEXT}}", _html_escape(latest_run_text))
        .replace("{{INITIAL_EMPTY_CLASS}}", initial_empty_class)
        .replace("{{INITIAL_DETAIL_CLASS}}", initial_detail_class)
        .replace("{{ASSET_HASH}}", asset_hash)
        .replace("{{BUNDLE_JSON}}", safe)
    )
    out_html = output_dir / "recruiting_review_app.html"
    out_css = output_dir / "recruiting_review_app.css"
    out_tokens_css = output_dir / "tokens.css"
    out_js = output_dir / "recruiting_review_app.js"
    out_data = output_dir / "review_bundle.json"
    out_html.write_text(html, encoding="utf-8")
    shutil.copyfile(CSS_TEMPLATE, out_css)
    shutil.copyfile(TOKENS_CSS, out_tokens_css)
    shutil.copyfile(JS_TEMPLATE, out_js)
    out_data.write_text(serialized, encoding="utf-8")
    return {
        "html": out_html,
        "css": out_css,
        "tokens_css": out_tokens_css,
        "js": out_js,
        "data": out_data,
    }


def _html_escape(value: str) -> str:
    return (
        value.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&#39;")
    )


def _sample_bundle() -> ReviewBundle:
    """Synthetic sample used when no input is supplied. Never contains
    real candidate data, Slack IDs, or workflow secrets.
    """
    return ReviewBundle(
        generated_at="2026-05-18T09:00:00Z",
        role_label="Billing Infrastructure Engineer (sample)",
        role_brief="Recent billing/payments experience required.",
        candidates=[
            Candidate(
                candidate_id="sample-1",
                full_name="Alex Sample",
                profile_url="https://example.com/profiles/alex-sample",
                headline="Senior backend engineer focused on billing systems",
                current_title="Senior Software Engineer",
                current_company="ExampleCo",
                location="Remote (US)",
                score=9.2,
                raw_score=92,
                predicted_rating=8.8,
                recent_relevant_experience="Led billing reliability work 2024-2026.",
                recent_relevance_window="0-2y",
                recent_relevance_score=9.5,
                company_quality_tier="tier_2",
                current_role_tenure_months=18,
                tenure_risk="none",
                ashby=AshbyStatus(
                    check_status="checked",
                    match_status="clear",
                    match_confidence="high",
                    match_reason="No LinkedIn or name match in Ashby.",
                ),
                main_reason_for_fit="Recent billing infra ownership.",
                main_concern="Company is smaller than typical pool.",
                evidence_bullets=[
                    "Owned billing pipeline rewrite (blog post 2025).",
                    "Talk at PaymentsConf 2024 on idempotency.",
                ],
                concerns=["Smaller team than typical FAANG pool."],
                draft_outreach=(
                    "Hi Alex — saw your work on billing reliability at "
                    "ExampleCo. Open to a quick chat about a senior billing "
                    "infra role?"
                ),
                profile_links={"Sheet row": "https://example.com/sheet#row-1"},
                first_found_run_id="run-2026-05-18-001",
            ),
            Candidate(
                candidate_id="sample-2",
                full_name="Sam Example",
                profile_url="https://example.com/profiles/sam-example",
                current_title="Staff Engineer",
                current_company="Acme Payments",
                location="New York, NY",
                score=7.4,
                predicted_rating=7.0,
                company_quality_tier="tier_2",
                current_role_tenure_months=2,
                tenure_risk="high",
                tenure_notes="Started Acme Payments 2 months ago.",
                ashby=AshbyStatus(
                    check_status="partial",
                    match_status="possible_duplicate",
                    match_confidence="low",
                    match_reason="Name match only; no LinkedIn URL available.",
                ),
                main_reason_for_fit="Payments depth and seniority.",
                main_concern="Just switched roles.",
                evidence_bullets=[
                    "Maintains widely-used open source payments library."
                ],
                first_found_run_id="run-2026-05-18-001",
            ),
        ],
        runs=[
            Run(
                run_id="run-2026-05-18-001",
                status="complete",
                started_at="2026-05-18T08:30:00Z",
                finished_at="2026-05-18T08:42:00Z",
                candidate_count=2,
                batch_size=10,
                quality_threshold=8.0,
            ),
        ],
        feedback_themes=[
            FeedbackTheme(
                theme_id="theme-1",
                label="Prefer 0-3y billing experience over older billing experience.",
                detected_in_run_id="run-2026-05-17-003",
                applied_to_run_id="run-2026-05-18-001",
                source="candidate",
                description="Reviewers flagged candidates with billing work older than 5 years.",
                example_candidate_ids=["sample-2"],
            ),
        ],
        general_feedback=[
            GeneralFeedback(
                feedback_id="gf-1",
                submitted_at="2026-05-17T18:00:00Z",
                reason_codes=["not_recent_enough"],
                free_text="Tighten recency cap for billing-specific roles.",
                applied_to_run_id="run-2026-05-18-001",
            ),
        ],
        ashby_exclusions=[
            AshbyExclusion(
                exclusion_id="excl-1",
                candidate_name="Pat Duplicate",
                reason="Already in pipeline",
                status="excluded",
                excluded_at="2026-05-17",
                source="ashby",
            ),
            AshbyExclusion(
                exclusion_id="excl-2",
                candidate_name="Pat Duplicate",
                reason="Already in pipeline",
                status="excluded",
                excluded_at="2026-05-17",
                source="ashby",
            ),
        ],
        hired_seed_profiles=[
            HiredSeedProfile(
                profile_id="seed-1",
                full_name="Hired Reference (synthetic)",
                role="Senior Billing Engineer",
                company="Reference Co",
                summary="Owned billing platform; deep payments background.",
                tags=["billing", "senior"],
            ),
        ],
        workflow_settings=WorkflowSettings(
            run_cadence="daily",
            cadence_scheduled=True,
            timezone="America/Los_Angeles",
            status_text="On schedule — next run in ~12h.",
            next_run_at="2026-05-19 09:00",
            last_run_at="2026-05-18 08:30",
            batch_size=10,
            quality_threshold=8.0,
            notification_channels=["slack: #recruiting-automated-sourcing"],
            review_ui_url="https://example.com/review/sample",
            sheet_export_url="https://example.com/sheet/sample",
        ),
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--input",
        type=Path,
        help="Path to a ReviewBundle JSON file. If omitted, a sample bundle is rendered.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("dist"),
        help="Output directory for the static UI bundle.",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Exit non-zero if validation warnings are present.",
    )
    args = parser.parse_args(argv)
    if args.input:
        payload = json.loads(args.input.read_text(encoding="utf-8"))
        bundle = load_bundle(payload)
    else:
        bundle = _sample_bundle()
    warnings = validate_bundle(bundle)
    paths = render_bundle(bundle, args.output)
    print(f"renderer: wrote {len(paths)} files to {args.output}")
    for name, path in paths.items():
        print(f"  {name}: {path}")
    if warnings:
        print(f"renderer: {len(warnings)} warning(s):", file=sys.stderr)
        for w in warnings:
            print(f"  - {w}", file=sys.stderr)
        if args.strict:
            return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
