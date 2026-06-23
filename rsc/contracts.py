from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field


class RoleType(str, Enum):
    PLANNER = "planner"
    CRITIC = "critic"
    VERIFIER = "verifier"
    REVISER = "reviser"
    SYNTHESIZER = "synthesizer"


class MemoryStage(str, Enum):
    FAIL = "fail"
    INVESTIGATE = "investigate"
    VERIFY = "verify"
    DISTILL = "distill"
    CONSULT = "consult"
    COMPRESSED_SUMMARY = "compressed_summary"


class LoopStatus(str, Enum):
    RUNNING = "running"
    PASSED = "passed"
    EXHAUSTED = "exhausted"
    ERROR = "error"


class SkillReadiness(str, Enum):
    READY = "ready"
    DEGRADED = "degraded"
    BLOCKED = "blocked"


class RubricCriterion(BaseModel):
    model_config = ConfigDict(extra="forbid")
    label: str
    description: str


class ClaudeState(BaseModel):
    model_config = ConfigDict(extra="forbid")
    values_and_principles: str = ""
    response_style: str = ""
    constraints: list[str] = Field(default_factory=list)
    conduct_rules: list[str] = Field(default_factory=list)
    source_file: str = "claude.md"


class MemoryState(BaseModel):
    model_config = ConfigDict(extra="forbid")
    user_facts: dict[str, Any] = Field(default_factory=dict)
    preferences: list[str] = Field(default_factory=list)
    history_summary: str = ""
    ongoing_context: str = ""
    distilled_rules: list[str] = Field(default_factory=list)
    source_file: str = "memory.md"
    last_updated: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class SkillState(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str
    task_specific_rules: list[str] = Field(default_factory=list)
    domain_knowledge: str = ""
    conventions: list[str] = Field(default_factory=list)
    templates: dict[str, str] = Field(default_factory=dict)
    source_file: str


class ArtifactRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")
    artifact_id: str
    role: RoleType
    turn: int
    content: str
    can_invoke_model: bool = False
    metadata: dict[str, Any] = Field(default_factory=dict)


class SearchRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")
    query: str
    content: str
    provider: str = ""
    turn: int = 0
    metadata: dict[str, Any] = Field(default_factory=dict)


class SelectedSkill(BaseModel):
    model_config = ConfigDict(extra="forbid")
    skill_id: str
    name: str
    score: float = Field(ge=0.0)
    semantic_score: float = Field(default=0.0, ge=0.0)
    lexical_score: float = Field(default=0.0, ge=0.0)
    readiness: SkillReadiness = SkillReadiness.READY
    reason: str = ""
    source_file: str = ""
    content_excerpt: str = ""
    references_loaded: list[str] = Field(default_factory=list)
    missing_capabilities: list[str] = Field(default_factory=list)
    degraded_capabilities: list[str] = Field(default_factory=list)


class ArtifactState(BaseModel):
    model_config = ConfigDict(extra="forbid")
    current_plan: Optional[str] = None
    intermediate_results: list[str] = Field(default_factory=list)
    decisions: list[str] = Field(default_factory=list)
    metrics: dict[str, Any] = Field(default_factory=dict)
    artifacts: list[ArtifactRecord] = Field(default_factory=list)
    search_results: list[SearchRecord] = Field(default_factory=list)
    selected_skills: list[SelectedSkill] = Field(default_factory=list)
    current_turn: int = 0
    session_id: str = ""


class ComposedState(BaseModel):
    model_config = ConfigDict(extra="forbid")
    claude: ClaudeState
    memory: MemoryState
    skill: SkillState
    artifact: ArtifactState
    composed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class RoleInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    task: str
    rubric: list[RubricCriterion]
    role: RoleType
    prior_output: Optional[str] = None
    composed_state: ComposedState
    turn: int
    session_id: str
    depth: int = 0
    inject_diversity: bool = False
    prior_verdict_critique: Optional[str] = None
    original_task: Optional[str] = None


class RoleOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    role: RoleType
    content: str
    artifacts: list[ArtifactRecord] = Field(default_factory=list)
    tokens_used_input: int = 0
    tokens_used_output: int = 0
    elapsed_seconds: float = 0.0
    error: Optional[str] = None


class EvalVerdict(BaseModel):
    model_config = ConfigDict(extra="forbid")
    passed: bool
    score: float = Field(ge=0.0, le=1.0)
    per_criterion: dict[str, bool] = Field(default_factory=dict)
    critique: str = ""
    root_causes: str = ""
    suggested_fix: str = ""


class LoopTurnRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")
    turn: int
    role_outputs: dict[str, str] = Field(default_factory=dict)
    verdict: Optional[EvalVerdict] = None
    elapsed_seconds: float = 0.0
    recursive_results: dict[str, str] = Field(default_factory=dict)


class LoopResult(BaseModel):
    model_config = ConfigDict(extra="forbid")
    session_id: str
    parent_session_id: Optional[str] = None
    task: str
    final_output: str
    status: LoopStatus
    turns_used: int
    final_score: float
    turns: list[LoopTurnRecord] = Field(default_factory=list)
    memory_rules_added: list[str] = Field(default_factory=list)
    total_tokens_input: int = 0
    total_tokens_output: int = 0


class MemoryEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")
    entry_id: str = Field(default_factory=lambda: str(uuid4()))
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    task_hint: str
    stage: MemoryStage
    content: str
    session_id: str
