"""Structured payload exported from the SQLite store and consumed by the renderer.

Contract surfaces:

  - candidates           one row per scored profile
  - runs                 one row per workflow run
  - feedback_themes      detected themes that influenced future runs
  - general_feedback     workflow-level feedback (not per-candidate)
  - ashby_exclusions     duplicate / exclusion records from Ashby
  - hired_seed_profiles  reference profiles used as positive seed signal
  - workflow_settings    cadence / next_run_at / batch_size / channels

Forward-compatible fields are optional; the renderer must tolerate older
payloads that omit them.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

SCHEMA_VERSION: int = 1

# `skipped` is preserved for backward compatibility with older exports that
# carried a Skip button; the current UI does not surface a Skip option and
# new bundles should only produce {unreviewed, yes, no, maybe}.
# See references/scoring_and_feedback.md.
ReviewState = Literal[
    "unreviewed",
    "yes",
    "no",
    "maybe",
    "skipped",
]

TenureRisk = Literal["none", "low", "medium", "high"]

InternalHistoryStatus = Literal[
    "none",
    "prior_employee",
    "current_employee",
    "known_conflict",
    "unknown",
]

CompanyQualityTier = Literal["tier_1", "tier_2", "tier_3", "tier_4", "unknown"]

AshbyCheckStatus = Literal["checked", "partial", "unavailable"]
AshbyMatchStatus = Literal["clear", "possible_duplicate", "excluded", "unknown"]
AshbyMatchConfidence = Literal["high", "medium", "low", "none"]

RunCadence = Literal["manual", "hourly", "daily", "weekly", "pause"]
RunStatus = Literal["pending", "running", "complete", "failed", "partial"]

FeedbackSource = Literal["candidate", "general", "system"]


@dataclass
class ScoreBreakdown:
    """Score component breakdown rendered in the candidate detail panel."""

    recent_relevant_experience: float | None = None
    role_domain_fit: float | None = None
    company_signal: float | None = None
    location_fit: float | None = None
    seniority_fit: float | None = None
    tenure_signal: float | None = None
    evidence_strength: float | None = None
    notes: str | None = None


@dataclass
class AshbyStatus:
    """Per-candidate Ashby duplicate check status.

    Renderer never displays raw internal IDs; only human-readable
    `match_reason` and the normalized status/confidence pair.
    """

    check_status: AshbyCheckStatus = "unavailable"
    match_status: AshbyMatchStatus = "unknown"
    match_confidence: AshbyMatchConfidence = "none"
    match_reason: str | None = None


@dataclass
class Candidate:
    """One scored sourced profile as exported from SQLite."""

    candidate_id: str
    full_name: str
    profile_url: str | None = None
    headline: str | None = None
    current_title: str | None = None
    current_company: str | None = None
    location: str | None = None

    # Score normalized to 1-10 by the renderer; raw upstream score
    # preserved for debugging.
    score: float | None = None
    raw_score: float | None = None
    predicted_rating: float | None = None
    score_breakdown: ScoreBreakdown | None = None
    score_cap_reasons: list[str] = field(default_factory=list)

    # Review state and review-time metadata.
    review_state: ReviewState = "unreviewed"
    review_decided_at: str | None = None
    reviewer: str | None = None

    # Run + provenance.
    first_found_run_id: str | None = None
    last_seen_run_id: str | None = None

    # Forward-compatible recency / domain / tenure / company tier signals.
    recent_relevant_experience: str | None = None
    recent_relevance_window: str | None = None
    recent_relevance_score: float | None = None
    company_quality_tier: CompanyQualityTier = "unknown"
    company_quality_notes: str | None = None
    current_role_start_date: str | None = None
    current_role_tenure_months: int | None = None
    tenure_risk: TenureRisk = "none"
    tenure_notes: str | None = None
    internal_history_status: InternalHistoryStatus = "none"

    # Ashby duplicate check.
    ashby: AshbyStatus = field(default_factory=AshbyStatus)

    # Free-form evidence shown in detail view.
    main_reason_for_fit: str | None = None
    main_concern: str | None = None
    evidence_bullets: list[str] = field(default_factory=list)
    concerns: list[str] = field(default_factory=list)
    draft_outreach: str | None = None

    # External links (Slack thread, Sheet row, etc.). Slack IDs and raw
    # internal URLs are accepted but the renderer scrubs known private
    # fragments before display — see `formatting.py`.
    profile_links: dict[str, str] = field(default_factory=dict)

    # Feedback collected on this candidate so far. Each entry is a
    # short reason code from the dropdown plus optional free text.
    feedback_reason_codes: list[str] = field(default_factory=list)
    feedback_reason_labels: list[str] = field(default_factory=list)
    feedback_free_text: str | None = None


@dataclass
class Run:
    """One workflow run summary."""

    run_id: str
    label: str | None = None
    run_number: int | None = None
    status: RunStatus = "complete"
    started_at: str | None = None
    finished_at: str | None = None
    candidate_count: int = 0
    reviewed_count: int = 0
    batch_size: int | None = None
    quality_threshold: float | None = None
    notes: str | None = None


@dataclass
class FeedbackTheme:
    """A detected feedback theme that influenced (or will influence)
    future runs. Themes are derived from per-candidate and general
    feedback by an upstream LLM step — the renderer only displays them.
    """

    theme_id: str
    label: str
    detected_in_run_id: str | None = None
    applied_to_run_id: str | None = None
    source: FeedbackSource = "candidate"
    description: str | None = None
    action_taken: str | None = None
    created_at: str | None = None
    example_candidate_ids: list[str] = field(default_factory=list)


@dataclass
class GeneralFeedback:
    """Workflow-level feedback not tied to a single candidate."""

    feedback_id: str
    submitted_at: str | None = None
    reviewer: str | None = None
    reason_codes: list[str] = field(default_factory=list)
    free_text: str | None = None
    applied_to_run_id: str | None = None


@dataclass
class AshbyExclusion:
    """An exclusion entry surfaced from Ashby.

    UI rendering rules (see references/ashby_dedupe_rules.md):
      - candidate_name shown first
      - reason / status shown second
      - dates are human-readable
      - raw internal IDs are not shown by default
      - repeated reason labels are deduped at render time
    """

    exclusion_id: str
    candidate_name: str
    reason: str | None = None
    status: str | None = None
    excluded_at: str | None = None
    source: str | None = None


@dataclass
class HiredSeedProfile:
    """A hired-candidate reference profile used as positive seed
    signal for sourcing. The renderer shows these in a sidebar so the
    reviewer can sanity-check what 'good' looks like for this role.
    Always synthetic / opt-in — never includes real candidate PII from
    closed deals unless explicitly approved by recruiting.
    """

    profile_id: str
    full_name: str
    role: str | None = None
    company: str | None = None
    profile_url: str | None = None
    summary: str | None = None
    tags: list[str] = field(default_factory=list)


@dataclass
class WorkflowSettings:
    """Cadence + run controls. Stored in SQLite; the UI displays the
    current values and offers controls to change them but writes go
    back through the workflow, not through the static UI bundle.
    """

    run_cadence: RunCadence = "manual"
    cadence_scheduled: bool = False
    timezone: str | None = None
    status_text: str | None = None
    next_run_at: str | None = None
    last_run_at: str | None = None
    batch_size: int | None = None
    quality_threshold: float | None = None
    notification_channels: list[str] = field(default_factory=list)
    review_ui_url: str | None = None
    sheet_export_url: str | None = None
    progress_state: str | None = None


@dataclass
class ReviewBundle:
    """Top-level container the renderer consumes.

    Produced from the SQLite export. Versioned by `schema_version`;
    older payloads with missing optional fields render with empty /
    sentinel values rather than raising.
    """

    schema_version: int = SCHEMA_VERSION
    generated_at: str | None = None
    role_label: str | None = None
    role_brief: str | None = None
    candidates: list[Candidate] = field(default_factory=list)
    runs: list[Run] = field(default_factory=list)
    feedback_themes: list[FeedbackTheme] = field(default_factory=list)
    general_feedback: list[GeneralFeedback] = field(default_factory=list)
    ashby_exclusions: list[AshbyExclusion] = field(default_factory=list)
    hired_seed_profiles: list[HiredSeedProfile] = field(default_factory=list)
    workflow_settings: WorkflowSettings = field(default_factory=WorkflowSettings)
