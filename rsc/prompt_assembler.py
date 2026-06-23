from __future__ import annotations

import json
import re
from copy import deepcopy

import tiktoken

from .contracts import ComposedState, RoleInput, RoleType, RubricCriterion

#: Sections included in each role's system prompt. Every section must earn
#: its place — no section is included by default.
ROLE_SECTIONS: dict[RoleType, set[str]] = {
    RoleType.PLANNER: {
        "BEHAVIORAL CONSTITUTION",
        "CONSTRAINTS",
        "CONDUCT RULES",
        "LEARNED RULES",
        "ONGOING CONTEXT",
        "HISTORY SUMMARY",
        "SKILL",
        "TASK-SPECIFIC RULES",
        "CONVENTIONS",
        "TEMPLATES",
        "DOMAIN KNOWLEDGE",
        "SELECTED SKILLS",
        "SEARCH RESULTS",
    },
    RoleType.CRITIC: {
        "BEHAVIORAL CONSTITUTION",
        "CONSTRAINTS",
        "CONDUCT RULES",
        "LEARNED RULES",
        "SKILL",
        "TASK-SPECIFIC RULES",
        "CONVENTIONS",
    },
    RoleType.VERIFIER: {
        "BEHAVIORAL CONSTITUTION",
        "CONSTRAINTS",
        "CONDUCT RULES",
        "LEARNED RULES",
        "SKILL",
        "TASK-SPECIFIC RULES",
        "CONVENTIONS",
    },
    RoleType.REVISER: {
        "BEHAVIORAL CONSTITUTION",
        "CONSTRAINTS",
        "CONDUCT RULES",
        "LEARNED RULES",
        "SKILL",
        "TASK-SPECIFIC RULES",
        "CONVENTIONS",
        "DOMAIN KNOWLEDGE",
        "SEARCH RESULTS",
    },
    RoleType.SYNTHESIZER: {
        "BEHAVIORAL CONSTITUTION",
        "CONSTRAINTS",
        "CONDUCT RULES",
        "RESPONSE STYLE",
        "LEARNED RULES",
        "ONGOING CONTEXT",
        "SKILL",
        "TASK-SPECIFIC RULES",
        "CONVENTIONS",
        "TEMPLATES",
        "DOMAIN KNOWLEDGE",
    },
}

ROLE_SYSTEM_PROMPTS: dict[RoleType, str] = {
    RoleType.PLANNER: """
You are the PLANNER agent in a recursive orchestration loop.
Your only job is to decompose the task into a precise implementation plan.

Required output sections:
## Approach
2-4 sentences explaining the strategy.

## Steps
A numbered list with as many items as the task genuinely requires. Do not cap the number of steps for complex tasks. Each item must include:
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
- For broad or complex tasks, decompose thoroughly even if that requires a long task list.
- Output valid GitHub-flavored Markdown.
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
- Output valid GitHub-flavored Markdown.
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
- Output valid GitHub-flavored Markdown.
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
Output valid GitHub-flavored Markdown.
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
- Unless the user explicitly requests a brief or concise answer, prefer comprehensive long-form answers. For broad or complex questions, target up to 30,000 words by default, organized with clear sections, summaries, evidence, and conclusions. Do not shorten purely for convenience.
- Output valid GitHub-flavored Markdown with clear headings, lists, tables, links, and fenced code blocks where useful.
""".strip(),
}

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

COMPRESS_SYSTEM_PROMPT = """
You are compressing old memory ledger entries into a durable summary.
Preserve reusable lessons, recurring failure modes, and stable user preferences.
Discard noise, repetition, and one-off execution details.

Return markdown bullets grouped by stage.
Be concise and loss-aware.
""".strip()

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

DIVERSITY_INJECTION_TEXT = (
    "Challenge your own prior assumptions. Generate a materially different "
    "approach from previous failed turns while still satisfying the same rubric."
)


class PromptAssembler:
    def __init__(
        self,
        model: str,
        max_input_tokens_per_call: int = 12000,
        learned_rules_threshold: int = 15,
    ) -> None:
        self.model = model
        self.max_input_tokens_per_call = max_input_tokens_per_call
        self._learned_rules_threshold = learned_rules_threshold
        try:
            self._enc = tiktoken.encoding_for_model(model)
        except KeyError:
            self._enc = tiktoken.get_encoding("cl100k_base")

    def count_tokens(self, text: str) -> int:
        return len(self._enc.encode(text))

    def format_rubric(self, rubric: list[RubricCriterion]) -> str:
        return "\n".join(
            f"{index}. [{criterion.label}] {criterion.description}"
            for index, criterion in enumerate(rubric, start=1)
        )

    def build_role_system_prompt(self, role_input: RoleInput) -> str:
        return self._build_role_system_prompt(
            role_input, self.max_input_tokens_per_call
        )

    def build_role_system_prompt_for_role(
        self, state: ComposedState, role: RoleType
    ) -> str:
        """Build system prompt from a composed state and role (no RoleInput).

        Used by ContextManager to measure token counts without a full
        RoleInput. Renders only the sections relevant to ``role``.
        """
        role_prompt = ROLE_SYSTEM_PROMPTS[role]
        return f"{self._render_composed_state(state, role)}\n\n---\n\n{role_prompt}".strip()

    def build_role_messages(self, role_input: RoleInput) -> tuple[str, str]:
        user = self.build_role_user_message(role_input)
        user_tokens = self.count_tokens(user)
        system_budget = max(1, self.max_input_tokens_per_call - user_tokens)
        system = self._build_role_system_prompt(role_input, system_budget)
        return system, user

    def _build_role_system_prompt(
        self, role_input: RoleInput, token_budget: int
    ) -> str:
        state = deepcopy(role_input.composed_state)
        role_prompt = ROLE_SYSTEM_PROMPTS[role_input.role]
        prompt = f"{self._render_composed_state(state, role_input.role)}\n\n---\n\n{role_prompt}".strip()
        if self.count_tokens(prompt) <= token_budget:
            return prompt
        return self._truncate_prompt_to_budget(
            state, role_prompt, token_budget, role_input.role
        )

    def build_role_user_message(self, role_input: RoleInput) -> str:
        rubric = self.format_rubric(role_input.rubric)
        if role_input.role == RoleType.PLANNER:
            message = f"TASK:\n{role_input.task}\n\nRUBRIC:\n{rubric}"
            if role_input.inject_diversity:
                message += f"\n\nDIVERSITY INSTRUCTION:\n{DIVERSITY_INJECTION_TEXT}"
            return message
        if role_input.role == RoleType.CRITIC:
            return f"PLANNER OUTPUT:\n{role_input.prior_output or ''}\n\nTASK:\n{role_input.task}\n\nRUBRIC:\n{rubric}"
        if role_input.role == RoleType.VERIFIER:
            return f"PLANNER OUTPUT:\n{role_input.prior_output or ''}\n\nTASK:\n{role_input.task}\n\nRUBRIC:\n{rubric}"
        if role_input.role in {RoleType.REVISER, RoleType.SYNTHESIZER}:
            prior = role_input.prior_output or ""
            return (
                f"{prior}\n\nRUBRIC:\n{rubric}" if "\nRUBRIC:\n" not in prior else prior
            )
        raise ValueError(f"Unsupported role: {role_input.role}")

    def build_reviser_prior_output(
        self,
        planner_output: str,
        critic_output: str,
        verifier_output: str,
        prior_verdict_critique: str | None,
        recursive_results: dict[str, str],
        inject_diversity: bool,
        original_task: str | None,
        task: str | None = None,
        rubric: list[RubricCriterion] | None = None,
        synthesizer_enabled: bool = True,
    ) -> str:
        display_task = task or original_task or ""
        original = original_task or display_task
        critique = prior_verdict_critique or "None"
        recursion = self._format_recursive_results(recursive_results)
        diversity = DIVERSITY_INJECTION_TEXT if inject_diversity else "None"
        rubric_text = self.format_rubric(rubric or [])
        final_output_addendum = ""
        if not synthesizer_enabled:
            final_output_addendum = (
                "\n\nIMPORTANT: No synthesizer stage will run after you. "
                "You are producing the FINAL output that will be delivered "
                "directly to the user. After addressing all issues above, "
                "write a complete, well-structured, polished response. "
                "Do not leave TODOs, placeholders, partial sections, or "
                "meta-commentary about what would happen next.\n\n"
                "Unless the user explicitly requests a brief or concise answer, "
                "prefer comprehensive long-form answers. For broad or complex "
                "questions, target up to 30,000 words by default, organized with "
                "clear sections, summaries, evidence, and conclusions. "
                "Do not shorten purely for convenience."
            )
        return (
            f"TASK:\n{display_task}\n\n"
            f"ORIGINAL TASK:\n{original}\n\n"
            f"PLAN:\n{planner_output}\n\n"
            f"CRITIQUE:\n{critic_output}\n\n"
            f"VERIFICATION:\n{verifier_output}\n\n"
            f"PRIOR EVALUATOR CRITIQUE:\n{critique}\n\n"
            f"RECURSIVE RESULTS:\n{recursion}\n\n"
            f"DIVERSITY INSTRUCTION:\n{diversity}\n\n"
            f"RUBRIC:\n{rubric_text}"
            f"{final_output_addendum}"
        )

    def build_synthesizer_prior_output(
        self,
        revised_output: str,
        prior_verdict_critique: str | None,
        recursive_results: dict[str, str],
        task: str | None = None,
        rubric: list[RubricCriterion] | None = None,
    ) -> str:
        critique = prior_verdict_critique or "None"
        recursion = self._format_recursive_results(recursive_results)
        rubric_text = self.format_rubric(rubric or [])
        return (
            f"TASK:\n{task or ''}\n\n"
            f"REVISED OUTPUT:\n{revised_output}\n\n"
            f"PRIOR EVALUATOR CRITIQUE:\n{critique}\n\n"
            f"RECURSIVE RESULTS:\n{recursion}\n\n"
            f"RUBRIC:\n{rubric_text}"
        )

    def build_evaluator_messages(
        self,
        task: str,
        rubric: list[RubricCriterion],
        output: str,
    ) -> tuple[str, str]:
        user = f"TASK:\n{task}\n\nRUBRIC:\n{self.format_rubric(rubric)}\n\nSUBMITTED OUTPUT:\n{output}"
        return EVALUATOR_SYSTEM_PROMPT, user

    def build_distill_messages(self, task: str, loop_turns: list) -> tuple[str, str]:
        lines = ["TASK:", task, "", "LOOP SUMMARY:"]
        for turn in loop_turns:
            score = turn.verdict.score if turn.verdict else 0.0
            critique = (turn.verdict.critique if turn.verdict else "")[:200]
            lines.append(f"Turn {turn.turn}: score={score}, critique={critique}")
        return DISTILL_SYSTEM_PROMPT, "\n".join(lines)

    def build_compress_messages(
        self, entries_by_stage: dict[str, list[str]]
    ) -> tuple[str, str]:
        sections: list[str] = []
        for stage, entries in entries_by_stage.items():
            sections.append(f"## {stage}")
            sections.extend(f"- {entry}" for entry in entries)
        return COMPRESS_SYSTEM_PROMPT, "\n".join(sections)

    def verifier_output_score(self, verifier_content: str) -> float:
        if not isinstance(verifier_content, str):
            return 0.0
        pass_count = 0
        total_count = 0
        for line in verifier_content.splitlines():
            stripped = line.strip()
            if not stripped.startswith("|") or not stripped.endswith("|"):
                continue
            cells = [cell.strip() for cell in stripped.strip("|").split("|")]
            if len(cells) < 3:
                continue
            if cells[0].upper() == "ITEM" or re.fullmatch(r"[-: ]+", cells[1]):
                continue
            verdict = cells[1].upper()
            if verdict not in {"PASS", "FAIL", "UNCERTAIN"}:
                continue
            total_count += 1
            if verdict == "PASS":
                pass_count += 1
        if total_count == 0:
            return 0.0
        return round(pass_count / total_count, 4)

    def _truncate_prompt_to_budget(
        self,
        state: ComposedState,
        role_prompt: str,
        token_budget: int | None = None,
        role: RoleType = RoleType.PLANNER,
    ) -> str:
        budget = token_budget or self.max_input_tokens_per_call

        def render() -> str:
            return f"{self._render_composed_state(state, role)}\n\n---\n\n{role_prompt}".strip()

        prompt = render()
        while (
            self.count_tokens(prompt) > budget and state.artifact.intermediate_results
        ):
            state.artifact.intermediate_results.pop(0)
            prompt = render()
        while self.count_tokens(prompt) > budget and state.artifact.decisions:
            state.artifact.decisions.pop(0)
            prompt = render()
        while (
            self.count_tokens(prompt) > budget
            and len(state.memory.distilled_rules) > 15
        ):
            state.memory.distilled_rules.pop(0)
            prompt = render()
        if self.count_tokens(prompt) > budget:
            state.memory.history_summary = ""
            prompt = render()
        while self.count_tokens(prompt) > budget and state.artifact.selected_skills:
            state.artifact.selected_skills.pop()
            prompt = render()
        while self.count_tokens(prompt) > budget and state.skill.domain_knowledge:
            text = state.skill.domain_knowledge
            state.skill.domain_knowledge = text[: max(0, int(len(text) * 0.75))]
            prompt = render()
            if len(text) == len(state.skill.domain_knowledge):
                break
        return prompt

    def _render_composed_state(
        self, state: ComposedState, role: RoleType = RoleType.PLANNER
    ) -> str:
        allowed = ROLE_SECTIONS.get(role, ROLE_SECTIONS[RoleType.PLANNER])
        sections: list[tuple[str, str]] = []
        claude = state.claude
        memory = state.memory
        skill = state.skill
        artifact = state.artifact
        if "BEHAVIORAL CONSTITUTION" in allowed:
            self._append_section(
                sections, "BEHAVIORAL CONSTITUTION", claude.values_and_principles
            )
        if "CONSTRAINTS" in allowed:
            self._append_section(
                sections, "CONSTRAINTS", self._bullets(claude.constraints)
            )
        if "CONDUCT RULES" in allowed:
            self._append_section(
                sections, "CONDUCT RULES", self._bullets(claude.conduct_rules)
            )
        if "RESPONSE STYLE" in allowed:
            self._append_section(sections, "RESPONSE STYLE", claude.response_style)
        if "LEARNED RULES" in allowed:
            rules = memory.distilled_rules[-15:]
            if len(rules) > self._learned_rules_threshold:
                rules = rules[-10:]
            self._append_section(sections, "LEARNED RULES", self._bullets(rules))
        if "ONGOING CONTEXT" in allowed:
            self._append_section(sections, "ONGOING CONTEXT", memory.ongoing_context)
        if "HISTORY SUMMARY" in allowed:
            self._append_section(sections, "HISTORY SUMMARY", memory.history_summary)
        if any(s.startswith("SKILL") for s in allowed):
            self._append_section(sections, f"SKILL: {skill.name}", "")
        if "TASK-SPECIFIC RULES" in allowed:
            self._append_section(
                sections,
                "TASK-SPECIFIC RULES",
                self._bullets(skill.task_specific_rules),
            )
        if "CONVENTIONS" in allowed:
            self._append_section(
                sections, "CONVENTIONS", self._bullets(skill.conventions)
            )
        if "TEMPLATES" in allowed:
            templates = "\n".join(
                f"{key}: {value.splitlines()[0] if value.splitlines() else ''}..."
                for key, value in skill.templates.items()
            )
            self._append_section(sections, "TEMPLATES", templates)
        if "DOMAIN KNOWLEDGE" in allowed:
            self._append_section(sections, "DOMAIN KNOWLEDGE", skill.domain_knowledge)
        if "SELECTED SKILLS" in allowed:
            self._append_section(
                sections, "SELECTED SKILLS", self._format_selected_skills(artifact)
            )
        if "SEARCH RESULTS" in allowed:
            self._append_section(
                sections, "SEARCH RESULTS", self._format_search_results(artifact, role)
            )
        if "CURRENT PLAN" in allowed:
            self._append_section(sections, "CURRENT PLAN", artifact.current_plan or "")
        if "INTERMEDIATE RESULTS" in allowed:
            self._append_section(
                sections,
                "INTERMEDIATE RESULTS",
                "\n".join(artifact.intermediate_results),
            )
        if "DECISIONS MADE" in allowed:
            self._append_section(
                sections, "DECISIONS MADE", "\n".join(artifact.decisions)
            )
        # METRICS is never included in any role's system prompt
        return "\n\n".join(
            f"## {heading}\n{body}" if body else f"## {heading}"
            for heading, body in sections
        )

    @staticmethod
    def _append_section(
        sections: list[tuple[str, str]], heading: str, body: str
    ) -> None:
        if body or heading.startswith("SKILL: "):
            sections.append((heading, body.strip()))

    @staticmethod
    def _bullets(items: list[str]) -> str:
        return "\n".join(f"- {item}" for item in items if item)

    @staticmethod
    def _format_recursive_results(recursive_results: dict[str, str]) -> str:
        if not recursive_results:
            return "None"
        return "\n\n".join(
            f"## {artifact_id}\n{result}"
            for artifact_id, result in recursive_results.items()
        )

    @staticmethod
    def _format_search_results(artifact, role: RoleType = RoleType.PLANNER) -> str:
        """Format search results, filtered to only this role's results.

        Each SearchRecord carries metadata["role"] (set by RoleSearchPlanner)
        or defaults to "planner" (baseline results from _inject_search_context).
        """
        role_value = role.value
        role_results = [
            result
            for result in artifact.search_results
            if result.metadata.get("role", "planner") == role_value
        ]
        if not role_results:
            return ""
        sections = []
        for index, result in enumerate(role_results, start=1):
            provider = f" provider={result.provider}" if result.provider else ""
            sections.append(
                f"### Search {index}: {result.query}{provider}\n{result.content}"
            )
        return "\n\n".join(sections)

    @staticmethod
    def _format_selected_skills(artifact) -> str:
        if not artifact.selected_skills:
            return ""
        sections = []
        for index, skill in enumerate(artifact.selected_skills, start=1):
            missing = ", ".join(skill.missing_capabilities) or "none"
            degraded = ", ".join(skill.degraded_capabilities) or "none"
            references = "\n".join(f"- {path}" for path in skill.references_loaded)
            parts = [
                f"### Skill {index}: {skill.skill_id}",
                f"Name: {skill.name}",
                f"Score: {skill.score}",
                f"Readiness: {skill.readiness.value}",
                f"Reason: {skill.reason}",
                f"Missing capabilities: {missing}",
                f"Degraded capabilities: {degraded}",
            ]
            if references:
                parts.append(f"Loaded references:\n{references}")
            if skill.content_excerpt:
                parts.append(f"Instructions excerpt:\n{skill.content_excerpt}")
            sections.append("\n".join(parts))
        return "\n\n".join(sections)
