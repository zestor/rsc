# RECURSIVE SCAFFOLDED COGNITION (RSC)
## Python Developer Design Specification
### Version 2.2 | June 2026

---

> **Document Purpose**: This specification is the authoritative, implementation-complete reference for building a Recursive Scaffolded Cognition (RSC) system in Python using OpenAI Responses, OpenAI-compatible chat clients, or OpenRouter. Every class, interface, data contract, prompt assembly rule, file schema, failure mode, and state transition behavior required for implementation is defined here. A developer receiving this document requires no external clarification before beginning implementation. If an implementation deviates from this document, that deviation is a bug unless explicitly versioned.

> **Version 2.2 Changes from 2.1**: Added skill-aware routing from recursive `SKILL.md` libraries, including checksum discovery, hybrid embedding plus HashingVectorizer-style lexical cosine intent scoring, top-K selected skills, capability readiness (`ready`, `degraded`, `blocked`), local reference loading, prompt injection under `## SELECTED SKILLS`, and `skill.route`/`skill.selected` logs. OpenAI defaults now target `gpt-5.5` through the Responses API using developer/user input blocks, text verbosity, reasoning effort/summary, stored responses, and include fields.

---

# PART 0 — CONCEPTUAL FOUNDATION

## 0.1 Core Thesis

A frozen LLM is stateless across API calls. It has no intrinsic continuity of memory, identity, task state, or procedural persistence between invocations. Those properties must be externalized into the harness.

The RSC system reconstructs cognition at runtime from four sources:

```text
[FROZEN MODEL] + [INJECTED STATE] + [ROUTED SKILLS & MEMORY] + [SEARCH CONTEXT] + [RECURSIVE ORCHESTRATION]
= DYNAMIC, EXTERNALIZED COGNITION
```

The harness owns persistence, orchestration, evaluation, recursion, and state mutation. The model owns inference only.

## 0.2 Formal Model

RSC is a state transition system:

```text
x_t      = (u_t, s_t)
y_t      = f(x_t)
s_{t+1}  = g(s_t, y_t, a_t)
```

Where:
- `u_t` = user task input at time `t`
- `s_t` = injected state at time `t`
- `y_t` = LLM output at time `t`
- `a_t` = artifacts, tool results, and evaluator outputs produced during time `t`
- `f()` = frozen LLM inference function
- `g()` = deterministic harness-owned state update function

The implementation must preserve this separation. The LLM never mutates persistent state directly.

## 0.3 Orchestration Principle

The five canonical roles are:
- Planner
- Critic
- Verifier
- Reviser
- Synthesizer

Each role is a separate LLM invocation with:
- a separate system prompt,
- a fresh message list,
- no hidden conversation history,
- only explicitly passed prior content.

This independence is mandatory. The orchestrator may assemble prior outputs into a single user message for a downstream role, but it may not pass the full prior message history.

## 0.4 Search Context Principle

If a `SearchProvider` is configured, the harness MUST perform search for the task before the first Planner invocation for that run, regardless of whether the user explicitly asks for search. The provider returns markdown-structured content. The harness stores that content in `ArtifactState.search_results`, renders it into every role system prompt, and logs `search.complete`. The LLM never directly calls the search service and never mutates search state.

Search providers that perform outbound web requests MUST enforce a configurable request concurrency limit. The default limit is `2` concurrent web requests, matching the lowest Firecrawl plan. Higher plans may configure up to `50` concurrent requests via `SEARCH_MAX_CONCURRENCY`.

## 0.5 Skill Routing Principle

If a skill router is configured, the harness MUST discover skills recursively from configured `SKILL_LIBRARY_PATHS`, score the user task against the indexed skill corpus, select the top-K matching skills, resolve each selected skill's capability readiness, load local declared references, store the result in `ArtifactState.selected_skills`, and inject the selected skill context before the first Planner invocation. Skill routing is harness-owned context. The LLM does not choose skills by itself and does not mutate the skill registry.

---

# PART 1 — SYSTEM ARCHITECTURE

## 1.1 State Layers

The system injects six state layers into every role call:

1. **claude.md** — behavioral constitution
2. **memory.md** — persistent state across sessions
3. **state skill file** — local task-specific procedural expertise
4. **selected skill bundle** — routed skills, readiness, references, and instruction excerpts
5. **search results** — markdown context returned by the configured search provider
6. **artifact_state.json** — current run execution state

These are assembled into a single `ComposedState` object and then rendered into the system prompt via the prompt assembly rules in Part 4.

## 1.2 High-Level Execution Graph

```text
Task Input
   |
   v
SearchProvider.search(task) if configured
    |
    v
HybridSkillRouter.route(task) if configured
    |
    v
ComposedState = StateLoader.load(...)
   |
   v
Planner -> Critic -> Verifier -> Reviser -> Synthesizer
   |
   v
Evaluator
   |
   +--> pass: finish loop
   |
   +--> fail: append memory, update critique, next turn
   |
   +--> recurse artifacts (after full cycle, bounded)
```

## 1.3 Architectural Authority Rules

The following authority rules are normative:

1. This specification text overrides diagrams.
2. Executable pseudocode overrides prose summaries.
3. Explicit routing rules override generic "prior output" behavior.
4. Structured file schema rules override any informal markdown examples.
5. Artifact markers are the only valid recursion trigger mechanism.

---

# PART 2 — CANONICAL FILE SCHEMAS

## 2.1 Required State Directory Layout

```text
state/
├── claude.md
├── memory.md
├── memory_ledger.json
├── artifact_state.json
└── skills/
    ├── default.md
    ├── coding.md
    ├── research.md
    └── ...
```

## 2.2 Canonical Markdown File Format

All markdown state files that map to structured models MUST use this format:

1. YAML front matter delimited by `---` at top of file.
2. Optional markdown body after the closing `---`.
3. The front matter contains machine-readable fields.
4. The markdown body contains human-readable elaboration.
5. `StateLoader` is responsible for parsing both front matter and body.

Example:

```md
---
constraints:
  - Never fabricate facts.
conduct_rules:
  - Ask clarifying questions when critical information is missing.
response_style: concise and technical
---
# Optional Notes
Additional human-maintained explanation can live here.
```

## 2.3 `claude.md` Schema

Canonical front matter:

```yaml
---
values_and_principles: |
  Prefer truth over fluency.
  Prefer explicit uncertainty over guessed certainty.
response_style: |
  Concise, technically precise, and implementation-oriented.
constraints:
  - Never fabricate APIs, filenames, or interfaces.
  - Preserve role independence.
conduct_rules:
  - State assumptions explicitly.
  - Escalate ambiguity rather than hiding it.
---
```

Mapping rules:
- `values_and_principles` -> `ClaudeState.values_and_principles`
- `response_style` -> `ClaudeState.response_style`
- `constraints` -> `ClaudeState.constraints`
- `conduct_rules` -> `ClaudeState.conduct_rules`
- markdown body, if present, is appended to `values_and_principles` under `## Supplemental Constitution Notes`

## 2.4 `memory.md` Schema

Canonical front matter:

```yaml
---
history_summary: |
  User prefers implementation-ready outputs.
ongoing_context: |
  Current project is building Recursive Scaffolded Cognition.
distilled_rules:
  - Always normalize rubric criteria into stable labels.
  - Reviser must receive planner, critic, and verifier outputs together.
preferences:
  - Technical writing preferred.
user_facts:
  location: Denver, North Carolina, US
---
```

Mapping rules:
- `history_summary` -> `MemoryState.history_summary`
- `ongoing_context` -> `MemoryState.ongoing_context`
- `distilled_rules` -> `MemoryState.distilled_rules`
- `preferences` -> `MemoryState.preferences`
- `user_facts` -> `MemoryState.user_facts`
- markdown body is ignored for prompt injection but retained when rewriting the file

## 2.5 Skill File Schema

Skill files live in `state/skills/{name}.md`.

Canonical front matter:

```yaml
---
name: coding
task_specific_rules:
  - All functions must have type annotations.
  - Use Python 3.11 syntax.
domain_knowledge: |
  Prefer standard library unless external dependency is justified.
conventions:
  - Use dataclasses only when mutability is explicit.
  - Favor pure functions for state transforms.
templates:
  function_docstring: |
    Args:
      ...
---
```

Mapping rules:
- `name` -> `SkillState.name`
- `task_specific_rules` -> `SkillState.task_specific_rules`
- `domain_knowledge` -> `SkillState.domain_knowledge`
- `conventions` -> `SkillState.conventions`
- `templates` -> `SkillState.templates`

## 2.6 `artifact_state.json` Schema

`artifact_state.json` MUST be pure JSON and conform exactly to `ArtifactState`.

No markdown format is permitted for Layer 4.

## 2.7 `memory_ledger.json` Schema

`memory_ledger.json` MUST be a JSON array of `MemoryEntry` objects. File-level schema:

```json
{
  "schema_version": "1.0",
  "entries": []
}
```

This wrapper object is mandatory. The ledger is not a bare array.

---

# PART 3 — DATA CONTRACTS

```python
# ============================================================
# FILE: rsc/contracts.py
# ============================================================
from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional
from uuid import uuid4

from pydantic import BaseModel, Field, ConfigDict


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


class RubricCriterion(BaseModel):
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


class ArtifactState(BaseModel):
    model_config = ConfigDict(extra="forbid")
    current_plan: Optional[str] = None
    intermediate_results: list[str] = Field(default_factory=list)
    decisions: list[str] = Field(default_factory=list)
    metrics: dict[str, Any] = Field(default_factory=dict)
    artifacts: list[ArtifactRecord] = Field(default_factory=list)
    search_results: list[SearchRecord] = Field(default_factory=list)
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
```

### 3.1 Contract Rules

1. All models use `extra="forbid"`.
2. Rubrics are always passed as `list[RubricCriterion]`, never raw strings.
3. `ArtifactRecord` is defined before `ArtifactState`; no forward-ref rebuild is required.
4. `RoleOutput` does not contain recursion flags. Artifacts alone control recursion.
5. All timestamps are timezone-aware UTC datetimes.

---

# PART 4 — PROMPT ASSEMBLY

## 4.1 Prompt Assembly Ownership

Prompt assembly is owned by a dedicated component:

```python
# ============================================================
# FILE: rsc/prompt_assembler.py
# ============================================================

class PromptAssembler:
    """Owns all system and user message construction for every LLM call."""
```

No other component may construct prompts ad hoc.

## 4.2 Token Budget Policy

The system MUST enforce prompt budgets before every LLM call.

### Token Counting Method

Token counting MUST use `tiktoken` with the encoding for the configured model. The encoding is resolved once at `PromptAssembler.__init__` using `tiktoken.encoding_for_model(model)`. If the model is not recognized by tiktoken, fall back to `tiktoken.get_encoding("cl100k_base")`. The fallback is silent (no warning).

```python
import tiktoken

class PromptAssembler:
    def __init__(self, model: str, max_input_tokens_per_call: int = 12000) -> None:
        self.max_input_tokens_per_call = max_input_tokens_per_call
        try:
            self._enc = tiktoken.encoding_for_model(model)
        except KeyError:
            self._enc = tiktoken.get_encoding("cl100k_base")

    def count_tokens(self, text: str) -> int:
        """Return token count for a string using the model's tiktoken encoding."""
        return len(self._enc.encode(text))
```

Defaults:
- `max_input_tokens_per_call = 12000`
- `max_output_tokens_per_call = 4000`
- `max_total_tokens_per_session = 120000`

If the assembled prompt exceeds `max_input_tokens_per_call`, the assembler truncates in this order:

1. Oldest `artifact.intermediate_results`
2. Oldest `artifact.decisions`
3. Oldest `memory.distilled_rules` beyond newest 15
4. `memory.history_summary`
5. `skill.domain_knowledge` tail

The following must never be truncated completely:
- `claude.constraints`
- `claude.conduct_rules`
- current task
- role system prompt
- latest `artifact.current_plan` if present

## 4.3 `ComposedState` Rendering Rules

Rendered sections appear in this exact order:

1. Behavioral Constitution
2. Constraints
3. Conduct Rules
4. Response Style
5. Learned Rules (latest 15)
6. Ongoing Context
7. History Summary
8. Skill Name
9. Task-Specific Rules
10. Conventions
11. Templates Summary
12. Domain Knowledge
13. Search Results
14. Current Plan
15. Intermediate Results (latest N after truncation)
16. Decisions Made (latest N after truncation)
17. Metrics Summary

## 4.4 Role System Prompts

```python
ROLE_SYSTEM_PROMPTS: dict[RoleType, str] = {
    RoleType.PLANNER: """
You are the PLANNER agent in a recursive orchestration loop.
Your only job is to decompose the task into a precise implementation plan.

Required output sections:
## Approach
2-4 sentences explaining the strategy.

## Steps
A numbered list. Each item must include:
- action
- expected output
- success criterion

## Risks
Top 3 implementation risks.

## Success Definition
A precise definition of what constitutes completion.

Rules:
- Do not execute.
- Do not critique.
- Do not synthesize.
- Use the injected skill and memory state.
- If the task is under-specified, state the missing assumption explicitly.
""".strip(),

    RoleType.CRITIC: """
You are the CRITIC agent in a recursive orchestration loop.
Your only job is to identify weaknesses, missing assumptions, hidden failure modes,
and underspecified implementation details in the planner output.

Output format:
A numbered list of issues.
Each issue must begin with:
[SEVERITY: HIGH|MED|LOW]

Rules:
- Do not rewrite.
- Do not solve.
- Do not synthesize.
- Be adversarial and exhaustive.
- Prefer concrete implementation gaps over vague complaints.
""".strip(),

    RoleType.VERIFIER: """
You are the VERIFIER agent in a recursive orchestration loop.
Your only job is to check correctness, logic, structural completeness, and rubric compliance.

Output format:
A markdown table with columns:
| ITEM | VERDICT | REASON |

VERDICT must be exactly one of:
- PASS
- FAIL
- UNCERTAIN

Rules:
- Evaluate the planner output independently of the critic.
- Flag factual uncertainty explicitly.
- Check for contradictions, missing structure, and rubric misses.
- Do not rewrite.
""".strip(),

    RoleType.REVISER: """
You are the REVISER agent in a recursive orchestration loop.
Your only job is to improve the planner output using the critic output, verifier output,
prior evaluator critique if provided, and recursive results if provided.

Required behavior:
- Address every HIGH and MED critic issue.
- Correct every verifier FAIL.
- Incorporate prior evaluator critique where present.
- Keep scope fixed unless a missing dependency prevents correctness.
- If an issue cannot be resolved, state why explicitly.

Output:
Return the full revised document, not a diff.
For every changed section, add an inline annotation of the form:
<!-- REVISED: reason -->
""".strip(),

    RoleType.SYNTHESIZER: """
You are the SYNTHESIZER agent in a recursive orchestration loop.
Your only job is to produce the final clean deliverable.

Rules:
- Remove all revision annotations and meta-commentary.
- Produce a self-contained output.
- Do not assume the caller has seen earlier stages.
- Apply the behavioral constitution's response style.
- If recursive sub-results were provided, integrate them naturally.
- If artifacts remain in the final output, list them explicitly at the end.
""".strip(),
}
```

## 4.5 Distillation Prompt

```python
DISTILL_SYSTEM_PROMPT = """
You are extracting long-term reusable learning from a completed orchestration loop.
Your job is to produce 1 to 3 distilled rules that are:
- generalizable to future tasks,
- implementation-relevant,
- not specific to one task instance,
- short enough to inject into future prompts.

Return JSON:
{
  "rules": ["rule 1", "rule 2"]
}

Reject:
- task-specific facts,
- one-off content details,
- stylistic trivia,
- duplicates of already known rules.
""".strip()
```

## 4.6 Memory Compression Prompt

```python
COMPRESS_SYSTEM_PROMPT = """
You are compressing old memory ledger entries into a durable summary.
Preserve reusable lessons, recurring failure modes, and stable user preferences.
Discard noise, repetition, and one-off execution details.

Return markdown bullets grouped by stage.
Be concise and loss-aware.
""".strip()
```

## 4.7 Diversity Injection Text

```python
DIVERSITY_INJECTION_TEXT = (
    "Challenge your own prior assumptions. Generate a materially different "
    "approach from previous failed turns while still satisfying the same rubric."
)
```

Injection location: `DIVERSITY_INJECTION_TEXT` is appended to the **user message** for the Planner role call, as a final line after the rubric block, when `inject_diversity=True`. It is never injected into the system prompt. The exact format appended to the planner user message is:

```text
DIVERSITY INSTRUCTION:
Challenge your own prior assumptions. Generate a materially different approach from previous failed turns while still satisfying the same rubric.
```

## 4.8 Evaluator System Prompt

```python
EVALUATOR_SYSTEM_PROMPT = """
You are a strict, independent grading agent.
Grade the submitted output solely against the rubric.
You do not know how the output was produced.

Return a JSON object with exactly these fields:
{
  "passed": bool,
  "score": float,
  "per_criterion": {"criterion_label": true},
  "critique": string,
  "root_causes": string,
  "suggested_fix": string
}

Rules:
- passed=true only if every rubric criterion passes.
- per_criterion keys must exactly match the provided rubric labels.
- critique must cite concrete failures in the submitted output.
- if passed=true, critique must be the empty string.
- do not grade on style unless explicitly required by the rubric.
- score = true_count / criterion_count.
""".strip()
```

## 4.9 User Message Templates

These templates are mandatory.

Planner user message:

```text
TASK:
{task}

RUBRIC:
{formatted_rubric}
```

If `inject_diversity=True`, append after RUBRIC:

```text

DIVERSITY INSTRUCTION:
Challenge your own prior assumptions. Generate a materially different approach from previous failed turns while still satisfying the same rubric.
```

Critic user message:

```text
PLANNER OUTPUT:
{planner_output}

TASK:
{task}

RUBRIC:
{formatted_rubric}
```

Verifier user message:

```text
PLANNER OUTPUT:
{planner_output}

TASK:
{task}

RUBRIC:
{formatted_rubric}
```

Reviser user message:

```text
TASK:
{task}

ORIGINAL TASK:
{original_task_if_turn_ge_3_else_task}

PLAN:
{planner_output}

CRITIQUE:
{critic_output}

VERIFICATION:
{verifier_output}

PRIOR EVALUATOR CRITIQUE:
{prior_verdict_critique_or_none}

RECURSIVE RESULTS:
{recursive_results_or_none}

DIVERSITY INSTRUCTION:
{diversity_text_or_none}

RUBRIC:
{formatted_rubric}
```

Synthesizer user message:

```text
TASK:
{task}

REVISED OUTPUT:
{revised_output}

PRIOR EVALUATOR CRITIQUE:
{prior_verdict_critique_or_none}

RECURSIVE RESULTS:
{recursive_results_or_none}

RUBRIC:
{formatted_rubric}
```

Evaluator user message:

```text
TASK:
{task}

RUBRIC:
{formatted_rubric}

SUBMITTED OUTPUT:
{output}
```

### 4.10 Rubric Formatting

`formatted_rubric` in all templates is produced by `PromptAssembler.format_rubric(rubric: list[RubricCriterion]) -> str`:

```python
def format_rubric(self, rubric: list[RubricCriterion]) -> str:
    lines = []
    for i, criterion in enumerate(rubric, start=1):
        lines.append(f"{i}. [{criterion.label}] {criterion.description}")
    return "\n".join(lines)
```

### 4.11 Optional Placeholder Rendering

When a template field is `None` or empty, the following sentinel strings are substituted:

| Field | Sentinel when absent |
|---|---|
| `prior_verdict_critique_or_none` | `"None"` |
| `recursive_results_or_none` | `"None"` |
| `diversity_text_or_none` | `"None"` |
| `original_task_if_turn_ge_3_else_task` | value of `task` when `turn < 3` |

The section header is always rendered even when the value is `"None"`. This ensures the model always sees the same structural template and learns to ignore absent fields.

---

# PART 5 — COMPONENT SPECIFICATIONS

## 5.0 `PromptAssembler` Full Interface

```python
# ============================================================
# FILE: rsc/prompt_assembler.py
# ============================================================
import re
import tiktoken
from rsc.contracts import RoleType, RoleInput, ComposedState, RubricCriterion


class PromptAssembler:
    """
    Owns all system and user message construction for every LLM call.
    No other component may construct prompts ad hoc.
    """

    def __init__(self, model: str, max_input_tokens_per_call: int = 12000) -> None:
        """
        Args:
            model: The LLM model name used for tiktoken encoding resolution.
            max_input_tokens_per_call: Hard token budget for assembled system prompts.
        """
        self.model = model
        self.max_input_tokens_per_call = max_input_tokens_per_call
        try:
            self._enc = tiktoken.encoding_for_model(model)
        except KeyError:
            self._enc = tiktoken.get_encoding("cl100k_base")

    def count_tokens(self, text: str) -> int:
        """Return tiktoken token count for the given text string."""
        return len(self._enc.encode(text))

    def format_rubric(self, rubric: list[RubricCriterion]) -> str:
        """
        Render rubric as a numbered list string.
        Format: "{n}. [{label}] {description}"
        Returns empty string for empty rubric.
        """
        ...

    def build_role_system_prompt(self, role_input: RoleInput) -> str:
        """
        Assemble the full system prompt for a role call.

        Combines:
          1. ComposedState rendering (Sections 1–16 of Part 4.3)
          2. Role-specific system prompt from ROLE_SYSTEM_PROMPTS[role_input.role]

        The ComposedState section appears FIRST, followed by a separator line
        "---", then the role system prompt.

        Applies token budget truncation (Part 4.2) before returning.

        Args:
            role_input: The RoleInput for this call. role_input.composed_state
                        is the sole source of injected state.

        Returns:
            str: The fully assembled system prompt, within token budget.
        """
        ...

    def build_role_user_message(self, role_input: RoleInput) -> str:
        """
        Assemble the user message for a role call using templates from Part 4.9.

        Dispatches on role_input.role to select the correct template.
        For PLANNER: appends DIVERSITY_INJECTION_TEXT block if
            role_input.inject_diversity is True.
        For REVISER: calls build_reviser_prior_output() internally and
            uses its result as the template body.
        For SYNTHESIZER: calls build_synthesizer_prior_output() internally.

        Args:
            role_input: The full RoleInput. prior_output field provides the
                        assembled combined context for REVISER and SYNTHESIZER.

        Returns:
            str: Fully assembled user message string.
        """
        ...

    def build_reviser_prior_output(
        self,
        planner_output: str,
        critic_output: str,
        verifier_output: str,
        prior_verdict_critique: str | None,
        recursive_results: dict[str, str],
        inject_diversity: bool,
        original_task: str | None,
    ) -> str:
        """
        Assemble the combined prior_output string passed to the Reviser role.

        Uses the Reviser user message template from Part 4.9.
        Applies sentinel substitution from Part 4.11 for absent fields.

        recursive_results formatting:
          If dict is empty, field value is "None".
          If non-empty, format each entry as:
            "## {artifact_id}\n{result}"
          and join with double newline.

        Args:
            planner_output: Raw planner content string.
            critic_output: Raw critic content string.
            verifier_output: Raw verifier content string.
            prior_verdict_critique: Evaluator critique from the prior turn, or None.
            recursive_results: Dict mapping artifact_id -> recursive loop final_output.
            inject_diversity: Whether to include DIVERSITY_INJECTION_TEXT.
            original_task: Original task string for turn >= 3; None for turn < 3.

        Returns:
            str: Fully assembled reviser combined input block.
        """
        ...

    def build_synthesizer_prior_output(
        self,
        revised_output: str,
        prior_verdict_critique: str | None,
        recursive_results: dict[str, str],
    ) -> str:
        """
        Assemble the combined prior_output string passed to the Synthesizer role.

        Uses the Synthesizer user message template from Part 4.9.
        Applies sentinel substitution from Part 4.11 for absent fields.
        recursive_results formatting is identical to build_reviser_prior_output().

        Args:
            revised_output: Raw reviser content string.
            prior_verdict_critique: Evaluator critique from the prior turn, or None.
            recursive_results: Dict mapping artifact_id -> recursive loop final_output.

        Returns:
            str: Fully assembled synthesizer combined input block.
        """
        ...

    def build_evaluator_messages(
        self,
        task: str,
        rubric: list[RubricCriterion],
        output: str,
    ) -> tuple[str, str]:
        """
        Return (system_prompt, user_message) for the evaluator call.

        system_prompt = EVALUATOR_SYSTEM_PROMPT (no ComposedState injection).
        user_message = Evaluator template from Part 4.9.

        Args:
            task: The original task string.
            rubric: The rubric list.
            output: The synthesizer output to grade.

        Returns:
            tuple[str, str]: (system_prompt, user_message)
        """
        ...

    def build_distill_messages(
        self,
        task: str,
        loop_turns: list,  # list[LoopTurnRecord]
    ) -> tuple[str, str]:
        """
        Return (system_prompt, user_message) for the distillation call.

        system_prompt = DISTILL_SYSTEM_PROMPT.
        user_message = structured summary of loop turns formatted as:

          TASK:
          {task}

          LOOP SUMMARY:
          Turn {n}: score={score}, critique={critique[:200]}
          ...

        Args:
            task: The original task string.
            loop_turns: All LoopTurnRecord objects from the completed run.

        Returns:
            tuple[str, str]: (system_prompt, user_message)
        """
        ...

    def build_compress_messages(
        self,
        entries_by_stage: dict[str, list[str]],
    ) -> tuple[str, str]:
        """
        Return (system_prompt, user_message) for the memory compression call.

        system_prompt = COMPRESS_SYSTEM_PROMPT.
        user_message = entries grouped by stage, formatted as:

          ## {stage}
          - {entry.content}
          ...

        Args:
            entries_by_stage: Dict mapping stage name -> list of content strings.

        Returns:
            tuple[str, str]: (system_prompt, user_message)
        """
        ...

    def verifier_output_score(self, verifier_content: str) -> float:
        """
        Parse the verifier markdown table and compute a structural pass score.

        Parsing algorithm:
          1. Find all lines that match the table row pattern:
             | {item} | {verdict} | {reason} |
             The header row and separator row (---|---|---) are ignored.
          2. For each data row, extract the VERDICT cell (second pipe-delimited token).
          3. Strip whitespace from the verdict token and uppercase it.
          4. Count:
             - pass_count: rows where verdict == "PASS"
             - total_count: all non-header, non-separator rows
          5. If total_count == 0, return 0.0.
          6. score = pass_count / total_count
          7. Return score as float rounded to 4 decimal places.

        UNCERTAIN is treated as neither PASS nor FAIL for scoring purposes —
        it does not increment pass_count but does increment total_count.

        This method never raises. On any parse error, return 0.0.

        Args:
            verifier_content: Raw string output from the Verifier role.

        Returns:
            float: Score in [0.0, 1.0]. Returns 0.0 if no table rows found
                   or on any parse error.

        Example:
            Input table:
              | ITEM | VERDICT | REASON |
              |------|---------|--------|
              | step 1 | PASS | looks good |
              | step 2 | FAIL | missing detail |
              | step 3 | UNCERTAIN | cannot verify |
            Returns: 0.3333 (1 PASS out of 3 total rows)
        """
        ...
```

### 5.0.1 `render_composed_state` internal method

This private method is called by `build_role_system_prompt` to produce the ComposedState section. The output sections follow the order in Part 4.3. Each section uses this exact heading and separator pattern:

```text
## BEHAVIORAL CONSTITUTION
{values_and_principles}

## CONSTRAINTS
- {constraint_1}
- {constraint_2}

## CONDUCT RULES
- {rule_1}

## RESPONSE STYLE
{response_style}

## LEARNED RULES
- {rule_1}
- ...

## ONGOING CONTEXT
{ongoing_context}

## HISTORY SUMMARY
{history_summary}

## SKILL: {skill_name}

## TASK-SPECIFIC RULES
- {rule_1}

## CONVENTIONS
- {convention_1}

## TEMPLATES
{template_key}: {template_value_first_line_only}...

## DOMAIN KNOWLEDGE
{domain_knowledge}

## SEARCH RESULTS
### Search {n}: {query} provider={provider}
{markdown_search_content}

## CURRENT PLAN
{current_plan_or_empty}

## INTERMEDIATE RESULTS
{intermediate_results_joined_newline}

## DECISIONS MADE
{decisions_joined_newline}

## METRICS
{metrics_json_compact}
```

Sections with no content (empty string, empty list, or None value) are omitted entirely — the heading is not rendered for empty sections.

## 5.1 `StateLoader`

```python
# ============================================================
# FILE: rsc/state_loader.py
# ============================================================
from pathlib import Path
import json
import yaml

from rsc.contracts import (
    ClaudeState, MemoryState, SkillState, ArtifactState,
    ComposedState, MemoryEntry, MemoryStage,
)
from rsc.exceptions import StateLoadError


class StateLoader:
    def __init__(self, base_dir: str | Path) -> None:
        """
        Args:
            base_dir: Root directory containing claude.md, memory.md,
                      memory_ledger.json, artifact_state.json, and skills/.
        """
        self.base_dir = Path(base_dir)
        self.skills_dir = self.base_dir / "skills"

    def load(self, skill_name: str, artifact: ArtifactState) -> ComposedState:
        """
        Load and compose all four state layers.

        Args:
            skill_name: Name of skill file to load (e.g. "coding" resolves to
                        state/skills/coding.md).
            artifact: The current in-memory ArtifactState for this run.
                      This value is authoritative; artifact_state.json is NOT read.

        Returns:
            ComposedState with all four layers populated.

        Raises:
            StateLoadError: If any state file has malformed YAML front matter.
        """
        claude = self._load_claude()
        memory = self._load_memory()
        skill = self._load_skill(skill_name)
        return ComposedState(
            claude=claude,
            memory=memory,
            skill=skill,
            artifact=artifact,
        )

    def _load_claude(self) -> ClaudeState:
        """
        Load state/claude.md. Returns empty ClaudeState if file does not exist.
        Raises StateLoadError on YAML parse failure.
        """
        ...

    def _load_memory(self) -> MemoryState:
        """
        Load state/memory.md. Returns empty MemoryState if file does not exist.
        Raises StateLoadError on YAML parse failure.
        """
        ...

    def _load_skill(self, skill_name: str) -> SkillState:
        """
        Load state/skills/{skill_name}.md.
        Returns SkillState(name=skill_name, source_file=...) with all other
        fields at defaults if file does not exist.
        Raises StateLoadError on YAML parse failure.
        """
        ...

    @staticmethod
    def _parse_front_matter(text: str) -> tuple[dict, str]:
        """
        Parse YAML front matter from a markdown file.

        Args:
            text: Full file content.

        Returns:
            (front_matter_dict, markdown_body)
            If no front matter delimiters found, returns ({}, full_text).

        Raises:
            StateLoadError: If front matter YAML is malformed.
        """
        ...
```

### `StateLoader` rules

1. Missing files produce empty-but-valid layer objects.
2. YAML front matter parse errors raise `StateLoadError`; they are not silently ignored.
3. Missing optional fields are filled by model defaults.
4. `artifact_state.json` is not read by `load()`; the passed `artifact` object is authoritative for the current run.
5. `StateLoader` is stateless and performs no caching.
6. Whenever distilled rules are injected into a session, the orchestrator MUST append a `CONSULT` memory entry for auditability after successful load.

## 5.2 `StateManager` Full Interface

```python
# ============================================================
# FILE: rsc/state_manager.py
# ============================================================
from pathlib import Path
from typing import Any
import json
import os
import tempfile

from rsc.contracts import (
    ArtifactState, RoleOutput, RoleType, MemoryEntry, MemoryState,
    MemoryStage, LoopTurnRecord,
)
from rsc.exceptions import ConfigurationError


class StateManager:
    """
    Owns all persistent state writes and artifact-state transitions.
    All writes are atomic (write-fsync-rename) with exclusive file locking.
    """

    def __init__(
        self,
        base_dir: str | Path,
        client=None,
        max_ledger_entries: int = 500,
        embedder_enabled: bool = False,
        embedder_model: str = "text-embedding-3-large",
    ) -> None:
        """
        Args:
            base_dir: Root state directory. Must exist before construction.
            client: OpenAI-compatible client, required only if distill_to_memory()
                    or compress_memory() will be called. May be None if those
                    methods will not be used (e.g., in unit tests).
            max_ledger_entries: Trigger threshold for compress_memory().
                                Default 500.
            embedder_enabled: If True, use semantic similarity for deduplication
                              in distill_to_memory(). Default False.
            embedder_model: Embedding model name used when embedder_enabled=True.
                            Default "text-embedding-3-large".

        Raises:
            ConfigurationError: If file locking is not available on the platform.
        """
        self.base_dir = Path(base_dir)
        self.client = client
        self.max_ledger_entries = max_ledger_entries
        self.embedder_enabled = embedder_enabled
        self.embedder_model = embedder_model
        self._ledger_path = self.base_dir / "memory_ledger.json"
        self._memory_path = self.base_dir / "memory.md"
        self._artifact_path = self.base_dir / "artifact_state.json"
        self._verify_file_locking()

    def _verify_file_locking(self) -> None:
        """
        Verify that file locking is available on this platform.
        Raises ConfigurationError if neither fcntl nor portalocker is importable.
        Called at __init__ time so failure is immediate at startup.
        """
        ...

    def update_artifact_state(
        self,
        current: ArtifactState,
        role_output: RoleOutput,
        turn: int,
    ) -> ArtifactState:
        """
        Pure function. Returns a new ArtifactState reflecting the role output.

        Mutation rules:
          - current_turn = turn
          - If role_output.role == PLANNER: current_plan = role_output.content
          - Append one intermediate result string:
              "[{turn}:{role_output.role.value}] {role_output.content[:1000]}"
          - Extract decisions from markers of the form:
              <!--DECISION: some text -->
            Append each extracted decision text to decisions list.
          - Update metrics dict with:
              last_role = role_output.role.value
              last_elapsed_seconds = role_output.elapsed_seconds
              tokens_input_cumulative = current.metrics.get("tokens_input_cumulative", 0)
                                        + role_output.tokens_used_input
              tokens_output_cumulative = current.metrics.get("tokens_output_cumulative", 0)
                                         + role_output.tokens_used_output
          - Append role_output.artifacts in order to artifacts list.
          - Never delete artifacts.

        Args:
            current: The current ArtifactState (immutable input).
            role_output: The output from the completed role call.
            turn: The current turn number (1-indexed).

        Returns:
            ArtifactState: A new ArtifactState instance. current is not mutated.
        """
        ...

    def save_artifact_state(self, state: ArtifactState) -> None:
        """
        Atomically write ArtifactState to artifact_state.json.
        Acquires exclusive file lock before writing.
        Uses write-fsync-rename atomic pattern.

        Args:
            state: The ArtifactState to persist.

        Raises:
            IOError: On write failure.
        """
        ...

    def append_memory_entry(self, entry: MemoryEntry) -> None:
        """
        Append a MemoryEntry to memory_ledger.json and re-render memory.md.

        Steps:
          1. Acquire exclusive lock on memory_ledger.json.
          2. Read current ledger.
          3. Append entry to entries list.
          4. Atomically write ledger.
          5. Re-render and atomically write memory.md (Section 5.8 template).
          6. Release lock.
          7. If ledger entry count > max_ledger_entries, call compress_memory().

        Args:
            entry: The MemoryEntry to append.

        Raises:
            IOError: On any write failure. Never silently swallowed.
        """
        ...

    def distill_to_memory(
        self,
        task: str,
        loop_turns: list[LoopTurnRecord],
        client,
    ) -> list[str]:
        """
        Extract generalizable rules from a completed loop and persist them.

        Steps:
          1. Build distillation messages via PromptAssembler.build_distill_messages().
          2. Call LLM with DISTILL_SYSTEM_PROMPT at temperature=0.0,
             response_format={"type": "json_object"}.
          3. Parse JSON of form {"rules": [...]}.
          4. Remove empty strings from rules list.
          5. Deduplicate against existing distilled_rules in memory.md:
             a. Normalize: strip, lowercase.
             b. Reject exact normalized duplicates.
             c. If embedder_enabled=True: reject rules with cosine similarity
                >= 0.92 against any existing rule.
          6. For each surviving rule, call append_memory_entry() with
             stage=DISTILL. This triggers memory.md re-render automatically.
          7. Return the list of rules that were actually appended.

        Re-render note: Because each call to append_memory_entry() re-renders
        memory.md, the final memory.md state after distill_to_memory() reflects
        ALL newly distilled rules. There is no separate re-render step required
        by the caller.

        Args:
            task: The task string (used as task_hint in MemoryEntry).
            loop_turns: All LoopTurnRecord objects from the completed run.
            client: OpenAI-compatible client for the distillation LLM call.

        Returns:
            list[str]: Rules that were successfully appended. May be empty
                       if all candidates were deduplicated.

        Raises:
            IOError: On write failure (propagated from append_memory_entry).
        """
        ...

    def compress_memory(self) -> None:
        """
        Compress the oldest ledger entries into a single COMPRESSED_SUMMARY entry.

        Trigger: Called automatically by append_memory_entry() when
                 len(entries) > max_ledger_entries after append.

        Algorithm:
          1. Acquire exclusive lock on memory_ledger.json.
          2. Load full ledger.
          3. Select oldest 400 entries that are NOT of stage COMPRESSED_SUMMARY.
          4. Group selected entries by stage value.
          5. Call LLM with COMPRESS_SYSTEM_PROMPT and entries_by_stage.
             Use temperature=0.0. client must not be None.
          6. Parse returned markdown bullets as compressed content string.
          7. Build one MemoryEntry(stage=COMPRESSED_SUMMARY, content=compressed).
          8. Remove the 400 selected entries from ledger; append the new summary.
          9. Atomically write ledger.
          10. Re-render and atomically write memory.md.
          11. Release lock.

        Raises:
            ConfigurationError: If self.client is None.
            IOError: On write failure.
        """
        ...

    def _atomic_write_json(self, path: Path, data: Any) -> None:
        """
        Write JSON data atomically to path using write-fsync-rename pattern.
        Acquires exclusive file lock on path before writing.
        """
        ...

    def _atomic_write_text(self, path: Path, text: str) -> None:
        """
        Write text data atomically to path using write-fsync-rename pattern.
        Acquires exclusive file lock on path before writing.
        """
        ...

    def _render_memory_md(self, entries: list[dict]) -> str:
        """
        Render the full memory.md content from the current ledger entries.
        Uses the template in Section 5.8.
        """
        ...
```

### `StateManager` rules (supplement to method docstrings)

1. `update_artifact_state()` is pure and never touches the filesystem.
2. `save_artifact_state()` is the only method that writes `artifact_state.json`.
3. Every method that writes a file acquires an exclusive lock first.
4. If `client` is `None` at construction time and `distill_to_memory()` or `compress_memory()` is called, raise `ConfigurationError` immediately.
5. The `_prompt_assembler` instance used by `distill_to_memory()` and `compress_memory()` is constructed internally with the same model as the `client` default. If a custom assembler is needed, pass it via constructor parameter.

## 5.3 Atomic Write Rules

All writes are atomic:
1. Write to temp file in same directory as target using `tempfile.NamedTemporaryFile(dir=target.parent, delete=False)`.
2. Call `f.flush()` then `os.fsync(f.fileno())` on the temp file before closing.
3. Call `os.replace(temp_path, target_path)` — this is atomic on POSIX and Windows (Python 3.3+).

## 5.4 File Locking Rules

This implementation is required to be single-process safe.

Before writing `memory.md`, `memory_ledger.json`, or `artifact_state.json`, `StateManager` MUST acquire an exclusive file lock using one of:
- `fcntl.flock(fd, fcntl.LOCK_EX)` on POSIX
- `portalocker.lock(f, portalocker.LOCK_EX)` cross-platform

Lock acquisition pattern:

```python
import fcntl  # POSIX only

def _acquire_lock(self, path: Path):
    """Returns an open file descriptor with exclusive lock held."""
    fd = open(path, "a+b")
    fcntl.flock(fd, fcntl.LOCK_EX)
    return fd

def _release_lock(self, fd) -> None:
    fcntl.flock(fd, fcntl.LOCK_UN)
    fd.close()
```

For cross-platform compatibility, use `portalocker` if `fcntl` is not available (e.g., Windows). `_verify_file_locking()` in `__init__` checks for at least one of these and raises `ConfigurationError` if neither is importable.

## 5.5 `append_memory_entry()` Behavior (normative)

- Append the entry to `memory_ledger.json`
- Re-render `memory.md` using template in Section 5.8
- Raise `IOError` on write failure
- Never silently swallow exceptions
- After appending, check `len(entries) > self.max_ledger_entries`; if true, call `compress_memory()`

## 5.6 `distill_to_memory()` Re-render Behavior (normative)

`distill_to_memory()` calls `append_memory_entry()` once per surviving rule. Each `append_memory_entry()` call re-renders `memory.md`. The final state of `memory.md` after `distill_to_memory()` returns reflects all newly distilled rules. **The caller does not need to trigger any additional re-render.**

### Deduplication rule

Near-duplicate threshold:
- normalized exact match: `rule.strip().lower() == existing.strip().lower()`
- OR semantic similarity >= `0.92` using the configured embedder (when `embedder_enabled=True`)

If `embedder_enabled=False`, only normalized exact-match deduplication is applied.

## 5.7 `compress_memory()` (normative)

Trigger: when `len(entries) > max_ledger_entries` (default `500`) after an append.

Algorithm:
1. Select oldest 400 entries excluding prior `COMPRESSED_SUMMARY` entries.
2. Group by `stage`.
3. Summarize with `COMPRESS_SYSTEM_PROMPT`.
4. Replace selected entries in ledger with one `COMPRESSED_SUMMARY` entry.
5. Re-render `memory.md` with a `## Compressed History` section.

## 5.8 `memory.md` Render Template

Rendered exactly as:

```md
# Memory State
Last updated: {iso_timestamp}

## Compressed History
{compressed_summary_or_empty}

## Distilled Rules
- {rule1}
- {rule2}

## Ongoing Context
{ongoing_context}

## History Summary
{history_summary}

## Recent Failures
- {recent_fail_1}
- {recent_fail_2}
```

Only `Distilled Rules`, `Ongoing Context`, and `History Summary` are injected into prompts. `Compressed History` and `Recent Failures` are written to the file for human review but are NOT injected into LLM system prompts.

`Recent Failures` is populated from the 5 most recent `FAIL`-stage entries (by timestamp descending), using `entry.content` as the bullet text.

## 5.9 `RoleAgent`

```python
# ============================================================
# FILE: rsc/role_agent.py
# ============================================================

class RoleAgent:
    def __init__(
        self,
        client,
        model: str,
        prompt_assembler: PromptAssembler,
        artifact_parser: ArtifactParser,
        temperature_map: dict[RoleType, float] | None = None,
        max_output_tokens: int = 4000,
    ) -> None:
        """
        Args:
            client: OpenAI-compatible client instance.
            model: Model name string passed to chat completions API.
            prompt_assembler: Injected PromptAssembler instance.
            artifact_parser: Injected ArtifactParser instance.
            temperature_map: Override per-role temperatures. Missing keys use defaults.
            max_output_tokens: max_tokens parameter for all role completions.
        """
        ...

    def invoke(self, role_input: RoleInput) -> RoleOutput:
        """
        Execute one role call against the LLM.

        Message construction:
          system = prompt_assembler.build_role_system_prompt(role_input)
          user   = prompt_assembler.build_role_user_message(role_input)
          messages = [
              {"role": "system", "content": system},
              {"role": "user", "content": user},
          ]

        No assistant history is ever passed.

        API call:
          client.chat.completions.create(
              model=self.model,
              messages=messages,
              temperature=self._temperature_map[role_input.role],
              max_tokens=self.max_output_tokens,
          )

        Post-call:
          - Record elapsed wall time via time.perf_counter().
          - Extract token counts from response.usage.
          - Run artifact_parser.extract(response_content, role_input.role, role_input.turn).
          - Return RoleOutput.

        Error handling:
          RateLimitError    -> exponential backoff: [1s, 2s, 4s], max 3 retries
          APITimeoutError   -> retry once after 2s
          ContentFilterError -> return RoleOutput(role=..., content="", error=str(e))
          all others        -> raise immediately

        Args:
            role_input: Fully constructed RoleInput.

        Returns:
            RoleOutput with content, artifacts, token counts, elapsed time.
        """
        ...
```

### Default temperatures

```python
DEFAULT_TEMPERATURE_MAP: dict[RoleType, float] = {
    RoleType.PLANNER: 0.4,
    RoleType.CRITIC: 0.2,
    RoleType.VERIFIER: 0.0,
    RoleType.REVISER: 0.3,
    RoleType.SYNTHESIZER: 0.2,
}
```

## 5.10 `ArtifactParser`

```python
# ============================================================
# FILE: rsc/artifact_protocol.py
# ============================================================
import re
from rsc.contracts import ArtifactRecord, RoleType
from rsc.exceptions import ArtifactParseError

ARTIFACT_PATTERN = re.compile(
    r'<!--ARTIFACT:START id="(?P<id>[^"]+)" recurse="(?P<recurse>true|false)" -->'
    r'(?P<content>.+?)'
    r'<!--ARTIFACT:END id="(?P=id)" -->',
    re.DOTALL,
)

DECISION_PATTERN = re.compile(r'<!--DECISION:\s*(?P<text>.+?)\s*-->', re.DOTALL)


class ArtifactParser:
    def extract(
        self,
        text: str,
        role: RoleType,
        turn: int,
    ) -> list[ArtifactRecord]:
        """
        Extract all artifact blocks from a role output string.

        Rules:
          1. Extract all non-overlapping blocks matching ARTIFACT_PATTERN.
          2. Preserve order of appearance.
          3. artifact_id must be unique within one role output;
             raise ArtifactParseError on duplicate artifact_id.
          4. can_invoke_model = True only when recurse="true".
          5. Artifact content excludes the marker tags.

        Args:
            text: Raw role output content.
            role: The role that produced this output.
            turn: The current turn number.

        Returns:
            list[ArtifactRecord]: Ordered list of extracted artifacts.

        Raises:
            ArtifactParseError: On duplicate artifact_id within one output.
        """
        ...

    def extract_decisions(self, text: str) -> list[str]:
        """
        Extract all decision text from <!--DECISION: ... --> markers.

        Args:
            text: Raw role output content.

        Returns:
            list[str]: Decision text strings in order of appearance.
        """
        return [m.group("text") for m in DECISION_PATTERN.finditer(text)]

    @staticmethod
    def inject_recursive_result(
        text: str,
        artifact_id: str,
        recursive_result: str,
    ) -> str:
        """
        Replace the full artifact marker block for artifact_id with the
        recursive result.

        Replacement format:
          ## Recursive Result: {artifact_id}
          {recursive_result}

        Both START and END marker tags are removed. No artifact markers
        remain in the returned text.

        Args:
            text: Text containing artifact markers.
            artifact_id: The artifact_id to replace.
            recursive_result: The final_output from the recursive loop.

        Returns:
            str: Text with the specified artifact block replaced.
        """
        ...
```

## 5.11 `Evaluator`

```python
# ============================================================
# FILE: rsc/evaluator.py
# ============================================================
from rsc.contracts import EvalVerdict, RubricCriterion
from rsc.prompt_assembler import PromptAssembler


class Evaluator:
    def __init__(
        self,
        client,
        model: str,
        prompt_assembler: PromptAssembler,
    ) -> None:
        """
        Args:
            client: OpenAI-compatible client.
            model: Model name for grading calls. Recommended: a cheaper/faster
                   model than the loop model when using a separate evaluator.
            prompt_assembler: Used only for build_evaluator_messages().
        """
        ...

    def grade(
        self,
        task: str,
        rubric: list[RubricCriterion],
        output: str,
        turn: int,
    ) -> EvalVerdict:
        """
        Grade output against rubric. Never raises.

        API call:
          client.chat.completions.create(
              model=self.model,
              messages=[{"role": "system", ...}, {"role": "user", ...}],
              temperature=0.0,
              response_format={"type": "json_object"},
          )

        On success: parse JSON into EvalVerdict.
        On malformed JSON: return EvalVerdict(
            passed=False, score=0.0,
            per_criterion={c.label: False for c in rubric},
            critique=f"Malformed evaluator response: {raw[:200]}",
            root_causes="Evaluator returned non-JSON output.",
            suggested_fix="Retry or inspect model output format.",
        )
        Missing rubric labels in per_criterion are treated as False.

        Args:
            task: The original task string.
            rubric: The rubric list.
            output: The synthesizer output to grade.
            turn: Current turn number (for logging context only).

        Returns:
            EvalVerdict: Always returns a valid EvalVerdict. Never raises.
        """
        ...
```

### `Evaluator.grade()` rules

1. Uses exactly two messages: system + user.
2. Uses `temperature=0.0`.
3. Uses `response_format={"type": "json_object"}` when supported.
4. Never receives prior conversation history.
5. Never raises. Always returns `EvalVerdict`.
6. On malformed JSON, returns `passed=False`, `score=0.0`, and stores raw snippet in critique.
7. Missing rubric labels in `per_criterion` are treated as `False`.

## 5.12 `SearchOverInference`

```python
# ============================================================
# FILE: rsc/search_inference.py
# ============================================================
from concurrent.futures import ThreadPoolExecutor, as_completed
from rsc.contracts import RoleInput, RoleOutput
from rsc.role_agent import RoleAgent
from rsc.evaluator import Evaluator


class SearchOverInference:
    def __init__(
        self,
        planner_agent: RoleAgent,
        evaluator: Evaluator,
        n_candidates: int = 3,
    ) -> None:
        """
        Args:
            planner_agent: RoleAgent used to generate candidate plans.
                           Invoked with temperature=0.7 overriding normal map.
            evaluator: Evaluator used to grade each candidate.
            n_candidates: Number of candidate plans to generate. Must be in [2, 5].

        Raises:
            ValueError: If n_candidates not in [2, 5].
        """
        if not (2 <= n_candidates <= 5):
            raise ValueError(f"n_candidates must be in [2, 5], got {n_candidates}")
        self.planner_agent = planner_agent
        self.evaluator = evaluator
        self.n_candidates = n_candidates

    def generate_best(self, planner_input: RoleInput) -> RoleOutput:
        """
        Generate n_candidates planner outputs and return the best-scoring one.

        Concurrency model:
          Candidates are generated using concurrent.futures.ThreadPoolExecutor
          with max_workers=n_candidates. This is the ONLY place in the v1.0
          implementation where concurrency is permitted. All other calls are
          strictly sequential (synchronous).

          Temperature override: each candidate call uses temperature=0.7,
          regardless of the DEFAULT_TEMPERATURE_MAP value for PLANNER.
          This override is implemented by temporarily substituting the
          temperature for the planner role within this method only.

        Grading: each candidate is graded independently by self.evaluator.grade().
        Grading calls are also concurrent within the same ThreadPoolExecutor.

        Selection:
          1. Highest score wins.
          2. Tie-breaker 1: lowest len(candidate.content).
          3. Tie-breaker 2: earliest candidate index (0-based generation order).

        Args:
            planner_input: RoleInput for the planner role. This input is
                           passed to each candidate call without modification
                           (temperature override is applied internally).

        Returns:
            RoleOutput: The best-scoring candidate's RoleOutput.
                        If all candidates fail with errors, returns the first
                        candidate regardless of score.
        """
        ...
```

### Concurrency posture (normative)

The RSC system is **synchronous by default**. All role calls in the main loop execute sequentially. `concurrent.futures.ThreadPoolExecutor` is permitted only within `SearchOverInference.generate_best()` for parallel candidate generation and grading. Search providers may use a semaphore-style concurrency limiter to cap outbound web requests according to the configured plan limit, but they must not spawn background workers or make search execution asynchronous. No other use of `asyncio`, `multiprocessing`, or ad hoc concurrency is permitted in v2.1. This is an explicit design decision to simplify state management; streaming and distributed execution are non-goals for v2.1 (see Part 13).

Latency implications: A single loop turn with 5 roles at ~3s per call = ~15s per turn. With `max_turns=5`, worst case is ~75s. This is acceptable for v1.0 batch usage. Real-time or streaming use cases are deferred to v2.0+.

---

# PART 6 — LOOP ORCHESTRATOR

## 6.1 Constructor

```python
# ============================================================
# FILE: rsc/loop_orchestrator.py
# ============================================================
from uuid import uuid4
from time import perf_counter

from rsc.contracts import (
    ArtifactState, EvalVerdict, LoopResult, LoopStatus,
    LoopTurnRecord, MemoryEntry, MemoryStage, RoleInput, RoleType, RubricCriterion,
)


class LoopOrchestrator:
    def __init__(
        self,
        client,
        model: str,
        state_loader,
        state_manager,
        role_agent,
        evaluator,
        prompt_assembler,
        search_over_inference=None,
        search_provider=None,
        search_max_results: int = 5,
        max_turns: int = 5,
        max_depth: int = 3,
        pass_threshold: float = 1.0,
        max_total_tokens_per_session: int = 120000,
    ) -> None:
        assert max_turns <= 10
        self.client = client
        self.model = model
        self.state_loader = state_loader
        self.state_manager = state_manager
        self.role_agent = role_agent
        self.evaluator = evaluator
        self.prompt_assembler = prompt_assembler
        self.search_over_inference = search_over_inference
        self.search_provider = search_provider
        self.search_max_results = search_max_results
        self.max_turns = max_turns
        self.max_depth = max_depth
        self.pass_threshold = pass_threshold
        self.max_total_tokens_per_session = max_total_tokens_per_session
```

## 6.2 Canonical Role Routing Rules

These rules are mandatory and override any generic `prev_output` logic:

- Planner receives: task + rubric
- Critic receives: planner output only
- Verifier receives: planner output only (never critic output)
- Reviser receives: planner + critic + verifier + prior evaluator critique + recursive results + diversity injection if active
- Synthesizer receives: revised output + prior evaluator critique + recursive results

## 6.3 Canonical Run Algorithm

```python
LOOP_SEQUENCE = [
    RoleType.PLANNER,
    RoleType.CRITIC,
    RoleType.VERIFIER,
    RoleType.REVISER,
    RoleType.SYNTHESIZER,
]


def run(
    self,
    task: str,
    rubric: list[RubricCriterion],
    skill_name: str,
    session_id: str | None = None,
    parent_session_id: str | None = None,
    depth: int = 0,
) -> LoopResult:
    assert depth <= self.max_depth

    session_id = session_id or str(uuid4())
    artifact_state = ArtifactState(session_id=session_id, current_turn=0)

    if self.search_provider is not None:
        markdown = self.search_provider.search(task, max_results=self.search_max_results)
        artifact_state.search_results.append(SearchRecord(
            query=task,
            content=markdown,
            provider=getattr(self.search_provider, "name", self.search_provider.__class__.__name__),
            turn=0,
        ))

    loop_turns: list[LoopTurnRecord] = []
    prior_verdict_critique: str | None = None
    total_tokens_input = 0
    total_tokens_output = 0

    for turn in range(1, self.max_turns + 1):
        turn_start = perf_counter()
        inject_diversity = False
        recursive_results: dict[str, str] = {}

        if len(loop_turns) >= 3:
            recent_scores = [t.verdict.score for t in loop_turns[-3:] if t.verdict is not None]
            if len(recent_scores) == 3 and (max(recent_scores) - min(recent_scores) < 0.05):
                inject_diversity = True

        composed_state = self.state_loader.load(skill_name=skill_name, artifact=artifact_state)

        planner_input = RoleInput(
            task=task,
            rubric=rubric,
            role=RoleType.PLANNER,
            prior_output=None,
            composed_state=composed_state,
            turn=turn,
            session_id=session_id,
            depth=depth,
            inject_diversity=inject_diversity,
            prior_verdict_critique=prior_verdict_critique,
            original_task=task,
        )

        if (
            self.search_over_inference is not None
            and turn >= 3
            and prior_verdict_critique is not None
            and len(loop_turns) > 0
            and loop_turns[-1].verdict is not None
            and loop_turns[-1].verdict.score < 0.5
        ):
            planner_output = self.search_over_inference.generate_best(planner_input)
        else:
            planner_output = self.role_agent.invoke(planner_input)

        artifact_state = self.state_manager.update_artifact_state(artifact_state, planner_output, turn)
        total_tokens_input += planner_output.tokens_used_input
        total_tokens_output += planner_output.tokens_used_output

        critic_output = self.role_agent.invoke(RoleInput(
            task=task,
            rubric=rubric,
            role=RoleType.CRITIC,
            prior_output=planner_output.content,
            composed_state=composed_state,
            turn=turn,
            session_id=session_id,
            depth=depth,
            inject_diversity=inject_diversity,
            prior_verdict_critique=prior_verdict_critique,
            original_task=task,
        ))
        artifact_state = self.state_manager.update_artifact_state(artifact_state, critic_output, turn)
        total_tokens_input += critic_output.tokens_used_input
        total_tokens_output += critic_output.tokens_used_output

        verifier_output = self.role_agent.invoke(RoleInput(
            task=task,
            rubric=rubric,
            role=RoleType.VERIFIER,
            prior_output=planner_output.content,
            composed_state=composed_state,
            turn=turn,
            session_id=session_id,
            depth=depth,
            inject_diversity=inject_diversity,
            prior_verdict_critique=prior_verdict_critique,
            original_task=task,
        ))
        artifact_state = self.state_manager.update_artifact_state(artifact_state, verifier_output, turn)
        total_tokens_input += verifier_output.tokens_used_input
        total_tokens_output += verifier_output.tokens_used_output

        verifier_zero = self.prompt_assembler.verifier_output_score(verifier_output.content) == 0.0

        if verifier_zero and self.search_over_inference is not None:
            planner_output = self.search_over_inference.generate_best(planner_input)
            critic_output = self.role_agent.invoke(RoleInput(
                task=task,
                rubric=rubric,
                role=RoleType.CRITIC,
                prior_output=planner_output.content,
                composed_state=composed_state,
                turn=turn,
                session_id=session_id,
                depth=depth,
                inject_diversity=True,
                prior_verdict_critique=prior_verdict_critique,
                original_task=task,
            ))
            verifier_output = self.role_agent.invoke(RoleInput(
                task=task,
                rubric=rubric,
                role=RoleType.VERIFIER,
                prior_output=planner_output.content,
                composed_state=composed_state,
                turn=turn,
                session_id=session_id,
                depth=depth,
                inject_diversity=True,
                prior_verdict_critique=prior_verdict_critique,
                original_task=task,
            ))

        reviser_combined_input = self.prompt_assembler.build_reviser_prior_output(
            planner_output=planner_output.content,
            critic_output=critic_output.content,
            verifier_output=verifier_output.content,
            prior_verdict_critique=prior_verdict_critique,
            recursive_results=recursive_results,
            inject_diversity=inject_diversity,
            original_task=task if turn >= 3 else None,
        )

        reviser_output = self.role_agent.invoke(RoleInput(
            task=task,
            rubric=rubric,
            role=RoleType.REVISER,
            prior_output=reviser_combined_input,
            composed_state=composed_state,
            turn=turn,
            session_id=session_id,
            depth=depth,
            inject_diversity=inject_diversity,
            prior_verdict_critique=prior_verdict_critique,
            original_task=task,
        ))
        artifact_state = self.state_manager.update_artifact_state(artifact_state, reviser_output, turn)
        total_tokens_input += reviser_output.tokens_used_input
        total_tokens_output += reviser_output.tokens_used_output

        pending_recursive_artifacts = [a for a in reviser_output.artifacts if a.can_invoke_model]

        for artifact in pending_recursive_artifacts:
            if depth < self.max_depth:
                recursive_loop_result = self.run(
                    task=artifact.content,
                    rubric=rubric,
                    skill_name=skill_name,
                    session_id=f"{session_id}-r{depth+1}-{artifact.artifact_id}",
                    parent_session_id=session_id,
                    depth=depth + 1,
                )
                recursive_results[artifact.artifact_id] = recursive_loop_result.final_output

        synthesizer_input = self.prompt_assembler.build_synthesizer_prior_output(
            revised_output=reviser_output.content,
            prior_verdict_critique=prior_verdict_critique,
            recursive_results=recursive_results,
        )

        synthesizer_output = self.role_agent.invoke(RoleInput(
            task=task,
            rubric=rubric,
            role=RoleType.SYNTHESIZER,
            prior_output=synthesizer_input,
            composed_state=composed_state,
            turn=turn,
            session_id=session_id,
            depth=depth,
            inject_diversity=inject_diversity,
            prior_verdict_critique=prior_verdict_critique,
            original_task=task,
        ))
        artifact_state = self.state_manager.update_artifact_state(artifact_state, synthesizer_output, turn)
        total_tokens_input += synthesizer_output.tokens_used_input
        total_tokens_output += synthesizer_output.tokens_used_output

        if (total_tokens_input + total_tokens_output) > self.max_total_tokens_per_session:
            final_output = synthesizer_output.content
            verdict = EvalVerdict(
                passed=False,
                score=0.0,
                per_criterion={c.label: False for c in rubric},
                critique="Session token budget exhausted.",
                root_causes="Cumulative token usage exceeded max_total_tokens_per_session.",
                suggested_fix="Reduce state size, max_turns, recursion, or candidate search.",
            )
            loop_turns.append(LoopTurnRecord(
                turn=turn,
                role_outputs={
                    "planner": planner_output.content,
                    "critic": critic_output.content,
                    "verifier": verifier_output.content,
                    "reviser": reviser_output.content,
                    "synthesizer": synthesizer_output.content,
                },
                verdict=verdict,
                elapsed_seconds=perf_counter() - turn_start,
                recursive_results=recursive_results,
            ))
            return LoopResult(
                session_id=session_id,
                parent_session_id=parent_session_id,
                task=task,
                final_output=final_output,
                status=LoopStatus.EXHAUSTED,
                turns_used=len(loop_turns),
                final_score=0.0,
                turns=loop_turns,
                memory_rules_added=[],
                total_tokens_input=total_tokens_input,
                total_tokens_output=total_tokens_output,
            )

        final_output = synthesizer_output.content
        verdict = self.evaluator.grade(task=task, rubric=rubric, output=final_output, turn=turn)

        turn_record = LoopTurnRecord(
            turn=turn,
            role_outputs={
                "planner": planner_output.content,
                "critic": critic_output.content,
                "verifier": verifier_output.content,
                "reviser": reviser_output.content,
                "synthesizer": synthesizer_output.content,
            },
            verdict=verdict,
            elapsed_seconds=perf_counter() - turn_start,
            recursive_results=recursive_results,
        )
        loop_turns.append(turn_record)

        if verdict.passed and verdict.score >= self.pass_threshold:
            rules = self.state_manager.distill_to_memory(task, loop_turns, self.client)
            return LoopResult(
                session_id=session_id,
                parent_session_id=parent_session_id,
                task=task,
                final_output=final_output,
                status=LoopStatus.PASSED,
                turns_used=len(loop_turns),
                final_score=verdict.score,
                turns=loop_turns,
                memory_rules_added=rules,
                total_tokens_input=total_tokens_input,
                total_tokens_output=total_tokens_output,
            )

        self.state_manager.append_memory_entry(MemoryEntry(
            task_hint=task[:80],
            stage=MemoryStage.FAIL,
            content=verdict.critique,
            session_id=session_id,
        ))
        self.state_manager.append_memory_entry(MemoryEntry(
            task_hint=task[:80],
            stage=MemoryStage.INVESTIGATE,
            content=verdict.root_causes,
            session_id=session_id,
        ))
        prior_verdict_critique = verdict.critique

    rules = self.state_manager.distill_to_memory(task, loop_turns, self.client)
    return LoopResult(
        session_id=session_id,
        parent_session_id=parent_session_id,
        task=task,
        final_output=final_output,
        status=LoopStatus.EXHAUSTED,
        turns_used=len(loop_turns),
        final_score=loop_turns[-1].verdict.score if loop_turns[-1].verdict else 0.0,
        turns=loop_turns,
        memory_rules_added=rules,
        total_tokens_input=total_tokens_input,
        total_tokens_output=total_tokens_output,
    )
```

## 6.4 Canonical Loop Rules

1. If a `SearchProvider` is configured, search runs before the first state load and every role receives the markdown search context through `ComposedState`.
2. `ComposedState` is loaded once per turn, not per role.
3. Verifier receives planner output, never critic output.
4. Reviser receives the combined block, never only the verifier output.
5. Recursive artifacts are processed after Reviser, before Synthesizer.
6. Recursive calls are bounded by `max_depth`.
7. If `depth == max_depth`, recursive artifacts are ignored.
8. Prior evaluator critique is carried across turns.
9. Original task is re-injected into Reviser starting at turn 3.
10. Stagnation over the last 3 turns activates diversity injection.
11. Session token budget exhaustion returns `LoopStatus.EXHAUSTED`.

---

# PART 7 — MEMORY LIFECYCLE

## 7.1 Lifecycle Stages

```text
FAIL -> INVESTIGATE -> VERIFY -> DISTILL -> CONSULT
```

Rules:
- `FAIL` appended immediately on failed verdict
- `INVESTIGATE` appended immediately after `FAIL`
- `VERIFY` appended only if later evidence confirms the root cause
- `DISTILL` appended post-loop from distillation process
- `CONSULT` appended when a distilled rule is injected into a new run

## 7.2 CONSULT Audit Rule

For each run, if one or more distilled rules are injected, append one `CONSULT` entry containing the exact rules consulted.

## 7.3 VERIFY Rule

`VERIFY` is optional. It may be appended only when a failed root cause from a prior entry is later confirmed by repeated failure evidence.

---

# PART 8 — FAILURE MODES AND GUARDRAILS

| Failure Mode | Detection | Mitigation |
|---|---|---|
| Error amplification | last 3 evaluator scores within 0.05 and all below pass threshold | inject `DIVERSITY_INJECTION_TEXT` |
| Recursive hallucination | distillation output duplicates or contradicts existing rules | deduplicate, optionally reject rule |
| Context drift | turn >= 3 and repeated failure persists | re-inject original task into Reviser input |
| Epistemic fragility | verifier structural score == 0.0 | rerun planner via `SearchOverInference` and repeat critic/verifier |
| Computational explosion | `depth >= max_depth` or token/session budget exceeded | hard-stop recursion or return exhausted |

## 8.1 Semantic Similarity for Contradiction Detection

If an embedder is configured, contradiction review is triggered when a proposed distilled rule has similarity >= `0.92` to an existing rule but normalized text differs materially.

Absent an embedder, contradiction detection is manual-only and no automated contradiction claim is permitted.

---

# PART 9 — LOGGING AND OBSERVABILITY

## 9.1 Logging Format

All logs MUST be structured JSON emitted via Python's standard `logging` module with a custom `logging.Formatter` that serializes to JSON.

Required fields on every event:
- `event`
- `timestamp` (ISO 8601 UTC)
- `session_id`
- `depth`

## 9.2 Required Events

- `session.start`
- `search.skip`
- `search.start`
- `turn.start`
- `state.load.complete`
- `role.start`
- `role.retry`
- `role.complete`
- `role.error`
- `artifact.update`
- `artifact.save`
- `evaluator.start`
- `evaluator.complete`
- `verdict.complete`
- `turn.complete`
- `memory.append`
- `memory.distill.start`
- `memory.distill.complete`
- `memory.compress`
- `memory.compress.start`
- `memory.compress.skip`
- `search.complete`
- `skill.route.skip`
- `skill.route.start`
- `skill.route`
- `skill.selected`
- `skill.route.complete`
- `recursion.start`
- `recursion.complete`
- `session.complete`
- `session.error`

Verbose event payloads include full text where available plus `chars`, `line_count`, `sha256`, and `preview`, plus token estimates, model names, rubric labels, selected skills, search result counts, artifact counts, cumulative token usage, verdict details, and explicit `success` flags where applicable. Logs must not include API keys or credentials. The default runtime logger writes JSONL records to `./rsc/logs/rsc-YYYY-MM-DD.jsonl` and selects the file by the current UTC date for every emitted event.

## 9.3 Role Completion Log Fields

On `role.complete`, include:
- `role`
- `turn`
- `elapsed_seconds`
- `tokens_used_input`
- `tokens_used_output`
- `artifact_count`

## 9.4 Logger Naming

All RSC components use the logger name `rsc`. Sub-loggers follow the pattern `rsc.{component}`:
- `rsc.state_loader`
- `rsc.state_manager`
- `rsc.role_agent`
- `rsc.evaluator`
- `rsc.loop_orchestrator`
- `rsc.search_inference`

The calling application configures log level and handlers. RSC components never configure handlers; they only call `logging.getLogger("rsc.{component}")`.

---

# PART 10 — ENVIRONMENT CONFIGURATION

```bash
OPENAI_BASE_URL=https://api.openai.com/v1
OPENAI_API_KEY=sk-...
OPENAI_USE_RESPONSES_API=true
OPENAI_TEXT_VERBOSITY=medium
OPENAI_REASONING_EFFORT=medium
OPENAI_REASONING_SUMMARY=auto
OPENAI_STORE=true
OPENAI_INCLUDE=reasoning.encrypted_content,web_search_call.action.sources
LLM_PROVIDER=openai
OPENROUTER_API_KEY=
OPENROUTER_PROVIDER_ZDR=false
OPENROUTER_PROVIDER_ONLY=fireworks,wafer,cloudflare,friendli
OPENROUTER_APP_TITLE=Recursive Scaffolded Cognition
LOOP_MODEL=gpt-5.5
EVAL_MODEL=gpt-5.5
MAX_TURNS=5
MAX_DEPTH=3
PASS_THRESHOLD=1.0
N_CANDIDATES=3
STATE_DIR=./state
LOG_LEVEL=INFO
MAX_INPUT_TOKENS_PER_CALL=12000
MAX_OUTPUT_TOKENS_PER_CALL=4000
MAX_TOTAL_TOKENS_PER_SESSION=120000
EMBEDDER_ENABLED=false
EMBEDDER_MODEL=text-embedding-3-large
SEARCH_ENDPOINT=
SEARCH_PROVIDER=firecrawl
SEARCH_METHOD=POST
SEARCH_MAX_RESULTS=5
SEARCH_MAX_CONCURRENCY=2
FIRECRAWL_API_KEY=
FIRECRAWL_SEARCH_ENDPOINT=https://api.firecrawl.dev/v2/search
FIRECRAWL_MAX_AGE_MS=172800000
SKILL_LIBRARY_PATHS=../code-change-handoff/skill-details-bundle/skills,../code-change-handoff/design_context/skills,../code-change-handoff/skills
SKILL_TOP_K=3
```

Rules:
- all values have defaults except `OPENAI_API_KEY`
- `LLM_PROVIDER` must be `openai` or `openrouter`; OpenRouter uses `OPENROUTER_API_KEY` and `OpenRouterClientAdapter`
- OpenAI uses `OpenAIResponsesClientAdapter` by default and maps internal system prompts to Responses API `developer` input blocks
- OpenRouter model defaults to `z-ai/glm-5.2` when `LLM_PROVIDER=openrouter` and `LOOP_MODEL` is unset
- `OPENROUTER_PROVIDER_ONLY` is restricted to `fireworks`, `wafer`, `cloudflare`, and `friendli`; `cloudfare` is accepted as an alias for `cloudflare`
- `SEARCH_ENDPOINT` is optional; when present, the example wires `HTTPMarkdownSearchProvider`
- `SEARCH_PROVIDER=firecrawl` wires `FirecrawlSearchProvider`, which calls `/v2/search`, requests `sources=["web"]`, `scrapeOptions.formats=["markdown"]`, and formats returned JSON into markdown context
- `FIRECRAWL_API_KEY` MUST be supplied via environment or `.env`; it MUST NOT be hardcoded in source files
- `SEARCH_MAX_CONCURRENCY` controls concurrent outbound search requests and must be in `[2, 50]`
- invalid numeric config fails fast at startup with `ConfigurationError`
- `PASS_THRESHOLD` must be in `[0.0, 1.0]`
- `MAX_DEPTH` must be in `[0, 10]`
- `MAX_TURNS` must be in `[1, 10]`

---

# PART 11 — MINIMAL RUNNABLE EXAMPLE

```python
# ============================================================
# FILE: examples/run_loop.py
# ============================================================
import os
from openai import OpenAI

from rsc.contracts import RubricCriterion
from rsc.state_loader import StateLoader
from rsc.state_manager import StateManager
from rsc.prompt_assembler import PromptAssembler
from rsc.artifact_protocol import ArtifactParser
from rsc.role_agent import RoleAgent
from rsc.evaluator import Evaluator
from rsc.search_inference import SearchOverInference
from rsc.loop_orchestrator import LoopOrchestrator

client = OpenAI(
    base_url=os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1"),
    api_key=os.environ["OPENAI_API_KEY"],
)

loop_model = os.getenv("LOOP_MODEL", "gpt-5.5")
state_loader = StateLoader(base_dir=os.getenv("STATE_DIR", "./state"))
state_manager = StateManager(
    base_dir=os.getenv("STATE_DIR", "./state"),
    client=client,
    max_ledger_entries=500,
    embedder_enabled=os.getenv("EMBEDDER_ENABLED", "false").lower() == "true",
    embedder_model=os.getenv("EMBEDDER_MODEL", "text-embedding-3-large"),
)
prompt_assembler = PromptAssembler(
    model=loop_model,
    max_input_tokens_per_call=int(os.getenv("MAX_INPUT_TOKENS_PER_CALL", "12000")),
)
artifact_parser = ArtifactParser()
role_agent = RoleAgent(
    client=client,
    model=loop_model,
    prompt_assembler=prompt_assembler,
    artifact_parser=artifact_parser,
    max_output_tokens=int(os.getenv("MAX_OUTPUT_TOKENS_PER_CALL", "4000")),
)
evaluator = Evaluator(
    client=client,
    model=os.getenv("EVAL_MODEL", "gpt-5.5"),
    prompt_assembler=prompt_assembler,
)
search_over_inference = SearchOverInference(
    planner_agent=role_agent,
    evaluator=evaluator,
    n_candidates=int(os.getenv("N_CANDIDATES", "3")),
)

orchestrator = LoopOrchestrator(
    client=client,
    model=loop_model,
    state_loader=state_loader,
    state_manager=state_manager,
    role_agent=role_agent,
    evaluator=evaluator,
    prompt_assembler=prompt_assembler,
    search_over_inference=search_over_inference,
    max_turns=int(os.getenv("MAX_TURNS", "5")),
    max_depth=int(os.getenv("MAX_DEPTH", "3")),
    pass_threshold=float(os.getenv("PASS_THRESHOLD", "1.0")),
    max_total_tokens_per_session=int(os.getenv("MAX_TOTAL_TOKENS_PER_SESSION", "120000")),
)

rubric = [
    RubricCriterion(label="name", description="Named exactly parse_date"),
    RubricCriterion(label="signature", description="Accepts str and returns datetime.date"),
    RubricCriterion(label="format_ymd", description="Handles YYYY-MM-DD"),
    RubricCriterion(label="format_mmddyyyy", description="Handles MMDDYYYY"),
    RubricCriterion(label="format_dd_mon_yyyy", description="Handles DD-Mon-YYYY"),
    RubricCriterion(label="errors", description="Raises ValueError for invalid input with descriptive message"),
    RubricCriterion(label="typing", description="Has type annotations"),
    RubricCriterion(label="docstring", description="Has docstring listing all three formats"),
    RubricCriterion(label="syntax", description="Is valid Python 3.11 syntax"),
]

result = orchestrator.run(
    task=(
        "Write a Python function parse_date(s: str) -> datetime.date that handles "
        "YYYY-MM-DD, MMDDYYYY, and DD-Mon-YYYY (e.g. 15-Jan-2024), and raises "
        "ValueError for unrecognized formats."
    ),
    rubric=rubric,
    skill_name="coding",
)

print(result.status)
print(result.final_score)
print(result.turns_used)
print(result.final_output)
```

---

# PART 12 — TESTING SPECIFICATION

## 12.1 Required Tests

```python
# ============================================================
# FILE: tests/test_loop_orchestrator.py
# ============================================================

def test_evaluator_independent_context():
    """Evaluator uses exactly [system, user] messages."""


def test_role_agent_uses_fresh_context_per_role():
    """Every role call uses exactly [system, user] messages."""


def test_verifier_receives_planner_not_critic():
    """Verifier prior_output equals planner output exactly."""


def test_reviser_receives_combined_input():
    """Reviser input contains PLAN, CRITIQUE, and VERIFICATION blocks."""


def test_synthesizer_receives_prior_verdict_on_turn_gt_1():
    """Prior evaluator critique is included in synthesizer input for later turns."""


def test_state_loaded_once_per_turn_not_per_role():
    """StateLoader.load call count equals number of turns used."""


def test_recursive_artifacts_processed_after_reviser_before_synthesizer():
    """Recursive results are available to Synthesizer, not mid-role."""


def test_max_depth_guard_ignores_recursive_artifacts():
    """At max depth, recurse=true artifacts are ignored."""


def test_score_stagnation_triggers_diversity_injection():
    """Three nearly identical low scores activate diversity injection."""


def test_verifier_zero_score_triggers_search_over_inference():
    """Circuit breaker reruns planner through search strategy."""


def test_memory_append_only_except_compression_replacement():
    """Ledger only appends, except explicit compression replacement event."""


def test_distill_to_memory_runs_once_post_loop():
    """Distillation runs exactly once on pass or exhaustion."""


def test_consult_entries_written_when_rules_injected():
    """Consult audit entries are added for injected distilled rules."""


def test_prompt_budget_truncation_order():
    """Prompt truncation removes lower-priority sections first."""


def test_token_budget_exhaustion_returns_exhausted_status():
    """Run halts with EXHAUSTED when session budget is exceeded."""


def test_role_temperatures_match_defaults():
    """PLANNER=0.4, CRITIC=0.2, VERIFIER=0.0, REVISER=0.3, SYNTHESIZER=0.2."""
```

## 12.2 Test Strategy Requirements

1. Mock LLM clients for all unit tests.
2. Use golden-message tests for prompt assembly.
3. Use temp directories for all state file tests.
4. Use deterministic fixture outputs for recursive artifact tests.
5. Assert exact routing semantics, not approximate behavior.

## 12.3 Test Harness Specification

### Mock Client Interface

All unit tests use `FakeLLMClient`, a synchronous mock with the following interface:

```python
# ============================================================
# FILE: tests/conftest.py
# ============================================================
from dataclasses import dataclass, field
from typing import Any


@dataclass
class FakeUsage:
    prompt_tokens: int = 10
    completion_tokens: int = 20


@dataclass
class FakeChoice:
    message: "FakeMessage"
    finish_reason: str = "stop"


@dataclass
class FakeMessage:
    content: str
    role: str = "assistant"


@dataclass
class FakeCompletion:
    choices: list[FakeChoice]
    usage: FakeUsage = field(default_factory=FakeUsage)


class FakeLLMClient:
    """
    Synchronous mock LLM client for unit testing.
    Responses are pre-programmed via a queue or a callable.
    """

    def __init__(self, responses: list[str] | None = None) -> None:
        """
        Args:
            responses: List of response strings returned in order.
                       If exhausted, raises IndexError.
                       If None, always returns empty string.
        """
        self._responses = list(responses or [])
        self.call_log: list[dict[str, Any]] = []

    def set_response(self, content: str) -> None:
        """Prepend a single response to the queue."""
        self._responses.insert(0, content)

    def set_responses(self, contents: list[str]) -> None:
        """Replace the response queue."""
        self._responses = list(contents)

    @property
    def chat(self):
        return self

    @property
    def completions(self):
        return self

    def create(self, **kwargs) -> FakeCompletion:
        """
        Consume the next response from the queue.
        Records the call in self.call_log for assertion in tests.
        """
        self.call_log.append(kwargs)
        content = self._responses.pop(0) if self._responses else ""
        return FakeCompletion(
            choices=[FakeChoice(message=FakeMessage(content=content))],
            usage=FakeUsage(),
        )
```

### Golden Message Fixture Format

Golden message fixtures are stored as JSON files in `tests/fixtures/golden/`.

File naming convention: `{component}_{test_name}.json`

Example: `tests/fixtures/golden/prompt_assembler_planner_basic.json`

File format:

```json
{
  "description": "Human-readable test description",
  "inputs": {
    "task": "...",
    "rubric": [{"label": "...", "description": "..."}],
    "role": "planner",
    "inject_diversity": false,
    "prior_verdict_critique": null,
    "composed_state": { ... }
  },
  "expected": {
    "system_prompt_contains": ["## BEHAVIORAL CONSTITUTION", "## CONSTRAINTS"],
    "user_message_exact": "TASK:\n...\n\nRUBRIC:\n..."
  }
}
```

Assertion rules:
- `system_prompt_contains`: all listed substrings must appear in the assembled system prompt.
- `user_message_exact`: the user message must equal this string exactly (after stripping trailing whitespace).

### Token Counting in Tests

Token counting for `test_prompt_budget_truncation_order` uses `tiktoken` with encoding `cl100k_base` and the model `gpt-4o`. Tests that verify truncation behavior must set `max_input_tokens_per_call` to a value small enough to trigger truncation with the test fixture, and verify that the truncated sections are lower-priority sections (per Part 4.2 order).

### Temp Directory Fixture

```python
import pytest
import tempfile
import shutil
from pathlib import Path


@pytest.fixture
def state_dir(tmp_path: Path) -> Path:
    """
    Provides a temporary state directory pre-populated with minimal
    valid state files for testing StateLoader and StateManager.
    """
    (tmp_path / "skills").mkdir()
    (tmp_path / "claude.md").write_text(
        "---\nconstraints:\n  - test constraint\nconduct_rules:\n  - test rule\n---\n"
    )
    (tmp_path / "memory.md").write_text(
        "---\nhistory_summary: test\ndistilled_rules: []\n---\n"
    )
    (tmp_path / "memory_ledger.json").write_text(
        '{"schema_version": "1.0", "entries": []}'
    )
    (tmp_path / "skills" / "default.md").write_text(
        "---\nname: default\ntask_specific_rules: []\n---\n"
    )
    return tmp_path
```

---

# PART 13 — NON-GOALS

The following are out of scope for Version 2.2:
- asynchronous execution (except within `SearchOverInference.generate_best()`)
- distributed state stores
- multi-process shared-memory orchestration without file locking
- automatic tool selection inside role outputs
- vector-database-backed memory retrieval
- streaming token output
- OpenTelemetry or external observability integration (structured JSON logs are provided; integration is the caller's responsibility)

These may be added in a future version, but must not be implied by this version.

---

# PART 14 — VERSIONING RULES

Any change to the following requires a version bump:
- data contract fields
- file schemas
- routing semantics
- prompt templates
- state mutation semantics
- recursion timing
- evaluator JSON format

Patch-level changes may clarify wording without changing behavior.

---

# PART 15 — FINAL IMPLEMENTATION CHECKLIST

An implementation is conformant to Version 2.2 only if all of the following are true:

- It parses canonical state file schemas exactly as specified.
- It uses typed contracts exactly as specified.
- It routes role inputs exactly as specified.
- It uses fresh context windows for every role and evaluator call.
- It processes recursive artifacts only through artifact markers.
- It enforces token budgets and truncation order using tiktoken.
- It writes state atomically with file locking.
- It logs required structured events.
- It implements the memory lifecycle exactly as specified.
- `distill_to_memory()` triggers memory.md re-render via `append_memory_entry()` per rule.
- `verifier_output_score()` uses the PASS/FAIL/UNCERTAIN table parsing algorithm exactly as specified.
- `SearchOverInference.generate_best()` uses `ThreadPoolExecutor` for concurrent candidate generation only.
- It passes the required tests using `FakeLLMClient` and golden fixtures.

---

# PART 16 — PACKAGE MANIFEST

## 16.1 Project Structure

```text
rsc/
├── pyproject.toml
├── README.md
├── state/
│   ├── claude.md
│   ├── memory.md
│   ├── memory_ledger.json
│   ├── artifact_state.json
│   └── skills/
│       ├── default.md
│       ├── coding.md
│       └── research.md
├── rsc/
│   ├── __init__.py
│   ├── contracts.py
│   ├── exceptions.py
│   ├── state_loader.py
│   ├── state_manager.py
│   ├── prompt_assembler.py
│   ├── artifact_protocol.py
│   ├── role_agent.py
│   ├── evaluator.py
│   ├── openrouter_adapter.py
│   ├── search_inference.py
│   ├── search_provider.py
│   └── loop_orchestrator.py
├── examples/
│   └── run_loop.py
└── tests/
    ├── conftest.py
    ├── fixtures/
    │   └── golden/
    └── test_loop_orchestrator.py
```

## 16.2 `pyproject.toml`

```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "rsc"
version = "2.2.0"
description = "Recursive Scaffolded Cognition — Python orchestration harness"
requires-python = ">=3.11"
dependencies = [
    "openai>=1.30.0",
    "pydantic>=2.7.0,<3.0.0",
    "pyyaml>=6.0.1",
    "tiktoken>=0.7.0",
    "portalocker>=2.8.2",
]

[project.optional-dependencies]
embedder = [
    "numpy>=1.26.0",
]
openrouter = [
    "openrouter",
]
dev = [
    "pytest>=8.2.0",
    "pytest-cov>=5.0.0",
]

[tool.pytest.ini_options]
testpaths = ["tests"]
python_files = ["test_*.py"]
python_functions = ["test_*"]
addopts = "--tb=short"

[tool.hatch.build.targets.wheel]
packages = ["rsc"]
```

### Dependency Decision Notes

| Package | Version | Rationale |
|---|---|---|
| `openai` | >=1.30.0 | v1.x SDK interface; `client.chat.completions.create()` API |
| `pydantic` | >=2.7.0,<3 | `ConfigDict` and v2 model syntax throughout contracts.py |
| `pyyaml` | >=6.0.1 | YAML front matter parsing in StateLoader |
| `tiktoken` | >=0.7.0 | Token counting in PromptAssembler |
| `portalocker` | >=2.8.2 | Cross-platform file locking fallback for non-POSIX |
| `numpy` | optional | Required only when `EMBEDDER_ENABLED=true` for cosine similarity |

`fcntl` is a Python standard library module (POSIX only). It does not appear in dependencies. `portalocker` is the cross-platform fallback and is always installed as a core dependency to ensure `_verify_file_locking()` passes on all platforms.

## 16.3 `rsc/__init__.py` — Public API

```python
# ============================================================
# FILE: rsc/__init__.py
# ============================================================
"""
Recursive Scaffolded Cognition (RSC)
Public API surface for version 2.1.
"""

from rsc.contracts import (
    RoleType,
    MemoryStage,
    LoopStatus,
    RubricCriterion,
    ClaudeState,
    MemoryState,
    SkillState,
    ArtifactRecord,
    SearchRecord,
    ArtifactState,
    ComposedState,
    RoleInput,
    RoleOutput,
    EvalVerdict,
    LoopTurnRecord,
    LoopResult,
    MemoryEntry,
)
from rsc.exceptions import StateLoadError, ArtifactParseError, ConfigurationError
from rsc.state_loader import StateLoader
from rsc.state_manager import StateManager
from rsc.prompt_assembler import PromptAssembler
from rsc.artifact_protocol import ArtifactParser
from rsc.role_agent import RoleAgent
from rsc.evaluator import Evaluator
from rsc.openrouter_adapter import OpenRouterClientAdapter, openrouter_provider_options
from rsc.search_inference import SearchOverInference
from rsc.search_provider import (
    SearchProvider,
    FirecrawlSearchProvider,
    FunctionSearchProvider,
    HTTPMarkdownSearchProvider,
    SearchProviderError,
)
from rsc.loop_orchestrator import LoopOrchestrator

__all__ = [
    # Contracts
    "RoleType", "MemoryStage", "LoopStatus", "RubricCriterion",
    "ClaudeState", "MemoryState", "SkillState", "ArtifactRecord",
    "SearchRecord", "ArtifactState", "ComposedState", "RoleInput", "RoleOutput",
    "EvalVerdict", "LoopTurnRecord", "LoopResult", "MemoryEntry",
    # Exceptions
    "StateLoadError", "ArtifactParseError", "ConfigurationError",
    # Components
    "StateLoader", "StateManager", "PromptAssembler", "ArtifactParser",
    "RoleAgent", "Evaluator", "SearchOverInference", "SearchProvider",
    "FirecrawlSearchProvider", "FunctionSearchProvider", "HTTPMarkdownSearchProvider", "SearchProviderError",
    "OpenRouterClientAdapter", "openrouter_provider_options", "LoopOrchestrator",
]
```

## 16.4 `rsc/exceptions.py`

```python
# ============================================================
# FILE: rsc/exceptions.py
# ============================================================

class RSCError(Exception):
    """Base class for all RSC exceptions."""


class StateLoadError(RSCError):
    """Raised when a state file has malformed YAML front matter."""


class ArtifactParseError(RSCError):
    """Raised when artifact extraction finds duplicate artifact_id."""


class ConfigurationError(RSCError):
    """Raised on invalid configuration at startup."""
```

---

**End of Specification — RSC Version 2.1**
