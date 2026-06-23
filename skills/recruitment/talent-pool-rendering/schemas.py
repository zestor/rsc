"""TalentPoolBundle schema — input contract for the preview renderer."""

from __future__ import annotations

from dataclasses import dataclass, field

SCHEMA_VERSION: str = "1"

TIER_HOT: str = "hot"
TIER_WARM: str = "warm"
TIER_WATCH: str = "watch"
TIER_COLD: str = "cold"
TIER_LABELS: dict[str, str] = {
    TIER_HOT: "Hot",
    TIER_WARM: "Warm",
    TIER_WATCH: "Watch",
    TIER_COLD: "Cold",
}
TIER_ORDER: tuple[str, ...] = (TIER_HOT, TIER_WARM, TIER_WATCH, TIER_COLD)


@dataclass(frozen=True)
class Source:
    title: str
    url: str


@dataclass(frozen=True)
class Signal:
    name: str
    weight: float
    score: float
    rationale: str = ""
    weighted_contribution: float = 0.0
    sources: tuple[Source, ...] = ()


@dataclass(frozen=True)
class CompanySnapshot:
    name: str
    slug: str = ""
    stability: str = ""
    summary: str = ""
    sources: tuple[Source, ...] = ()


@dataclass(frozen=True)
class MethodologySignal:
    key: str
    label: str
    weight: float
    direction: str = ""


@dataclass(frozen=True)
class Methodology:
    formula: str = ""
    total_weight: float = 0.0
    tier_cutoffs: dict[str, str] = field(default_factory=dict)
    signals: tuple[MethodologySignal, ...] = ()


@dataclass(frozen=True)
class Run:
    run_id: str
    started_at: str
    finished_at: str = ""
    label: str = ""
    notes: str = ""


@dataclass(frozen=True)
class TierThresholds:
    hot: float = 70.0
    warm: float = 55.0
    watch: float = 40.0


@dataclass(frozen=True)
class WorkflowSettings:
    role_label: str = ""
    role_subtitle: str = ""
    cadence_label: str = "Manual only"
    last_refreshed_at: str = ""


@dataclass(frozen=True)
class Candidate:
    candidate_id: str
    full_name: str
    headline: str = ""
    current_title: str = ""
    current_company: str = ""
    location: str = ""
    profile_url: str = ""
    final_score: float = 0.0
    tier: str = TIER_COLD
    signals: tuple[Signal, ...] = ()
    tags: tuple[str, ...] = ()
    found_run_id: str = ""


@dataclass(frozen=True)
class TalentPoolBundle:
    schema_version: str = SCHEMA_VERSION
    workflow: WorkflowSettings = field(default_factory=WorkflowSettings)
    tier_thresholds: TierThresholds = field(default_factory=TierThresholds)
    runs: tuple[Run, ...] = ()
    candidates: tuple[Candidate, ...] = ()
    companies: tuple[CompanySnapshot, ...] = ()
    methodology: Methodology = field(default_factory=Methodology)
