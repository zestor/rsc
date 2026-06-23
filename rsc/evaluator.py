from __future__ import annotations

# pylint: disable=broad-exception-caught

import json

from .contracts import EvalVerdict, RubricCriterion
from .observability import get_logger, log_event, text_summary
from .prompt_assembler import PromptAssembler
from .retry import retry_call


class Evaluator:
    def __init__(
        self,
        client,
        model: str,
        prompt_assembler: PromptAssembler,
        context_manager=None,
    ) -> None:
        self.client = client
        self.model = model
        self.prompt_assembler = prompt_assembler
        self.context_manager = context_manager
        self._logger = get_logger("evaluator")

    def grade(
        self, task: str, rubric: list[RubricCriterion], output: str, turn: int
    ) -> EvalVerdict:
        malformed_root_cause = "Evaluator returned non-JSON output."
        system, user = self.prompt_assembler.build_evaluator_messages(
            task, rubric, output
        )
        log_event(
            self._logger,
            "evaluator.start",
            session_id="",
            depth=0,
            turn=turn,
            model=self.model,
            task=text_summary(task),
            submitted_output=text_summary(output),
            system_prompt=text_summary(system),
            user_message=text_summary(user),
            rubric_labels=[criterion.label for criterion in rubric],
            estimated_system_tokens=self.prompt_assembler.count_tokens(system),
            estimated_user_tokens=self.prompt_assembler.count_tokens(user),
        )
        raw = ""
        try:
            response = retry_call(
                lambda: self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": system},
                        {"role": "user", "content": user},
                    ],
                    temperature=0.0,
                    response_format={"type": "json_object"},
                ),
                on_retry=lambda exc, attempt, delay: log_event(
                    self._logger,
                    "evaluator.retry",
                    session_id="",
                    depth=0,
                    turn=turn,
                    model=self.model,
                    error_type=exc.__class__.__name__,
                    error=str(exc),
                    attempt=attempt,
                    delay_seconds=delay,
                ),
            )
            raw = response.choices[0].message.content or "{}"
            payload = json.loads(raw)
            per_criterion = {
                criterion.label: bool(
                    payload.get("per_criterion", {}).get(criterion.label, False)
                )
                for criterion in rubric
            }
            true_count = sum(1 for passed in per_criterion.values() if passed)
            score = float(
                payload.get("score", true_count / len(rubric) if rubric else 0.0)
            )
            passed = bool(payload.get("passed", False)) and all(per_criterion.values())
            verdict = EvalVerdict(
                passed=passed,
                score=max(0.0, min(1.0, score)),
                per_criterion=per_criterion,
                critique="" if passed else str(payload.get("critique", "")),
                root_causes=str(payload.get("root_causes", "")),
                suggested_fix=str(payload.get("suggested_fix", "")),
            )
            usage = getattr(response, "usage", None)
            log_event(
                self._logger,
                "evaluator.complete",
                session_id="",
                depth=0,
                turn=turn,
                model=self.model,
                passed=verdict.passed,
                score=verdict.score,
                per_criterion=verdict.per_criterion,
                true_count=true_count,
                criterion_count=len(rubric),
                raw_response=text_summary(raw),
                critique=text_summary(verdict.critique),
                root_causes=text_summary(verdict.root_causes),
                suggested_fix=text_summary(verdict.suggested_fix),
                tokens_used_input=getattr(usage, "prompt_tokens", 0),
                tokens_used_output=getattr(usage, "completion_tokens", 0),
                success=True,
            )
            return verdict
        except json.JSONDecodeError:
            malformed_root_cause = "Evaluator returned non-JSON output."
        except Exception as exc:
            malformed_root_cause = f"Evaluator call failed: {exc.__class__.__name__}."
        verdict = EvalVerdict(
            passed=False,
            score=0.0,
            per_criterion={criterion.label: False for criterion in rubric},
            critique=f"Malformed evaluator response: {raw[:200]}",
            root_causes=malformed_root_cause,
            suggested_fix="Retry or inspect model output format.",
        )
        log_event(
            self._logger,
            "evaluator.complete",
            session_id="",
            depth=0,
            turn=turn,
            model=self.model,
            passed=False,
            score=0.0,
            per_criterion=verdict.per_criterion,
            raw_response=text_summary(raw),
            critique=text_summary(verdict.critique),
            root_causes=text_summary(verdict.root_causes),
            suggested_fix=text_summary(verdict.suggested_fix),
            success=False,
        )
        return verdict
