from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed

from .contracts import RoleInput, RoleOutput, RoleType
from .evaluator import Evaluator
from .role_agent import RoleAgent


class SearchOverInference:
    def __init__(
        self, planner_agent: RoleAgent, evaluator: Evaluator, n_candidates: int = 3
    ) -> None:
        if not (2 <= n_candidates <= 5):
            raise ValueError(f"n_candidates must be in [2, 5], got {n_candidates}")
        self.planner_agent = planner_agent
        self.evaluator = evaluator
        self.n_candidates = n_candidates

    def generate_best(self, planner_input: RoleInput) -> RoleOutput:
        candidates: list[tuple[int, RoleOutput]] = []
        with self.planner_agent.temperature_override(RoleType.PLANNER, 0.7):
            with ThreadPoolExecutor(max_workers=self.n_candidates) as executor:
                futures = {
                    executor.submit(self.planner_agent.invoke, planner_input): index
                    for index in range(self.n_candidates)
                }
                for future in as_completed(futures):
                    index = futures[future]
                    if future.exception() is None:
                        candidates.append((index, future.result()))
                    else:
                        candidates.append(
                            (
                                index,
                                RoleOutput(
                                    role=RoleType.PLANNER,
                                    content="",
                                    error="candidate failed",
                                ),
                            )
                        )
        if not candidates:
            return RoleOutput(
                role=RoleType.PLANNER, content="", error="no candidates generated"
            )
        with ThreadPoolExecutor(max_workers=self.n_candidates) as executor:
            grade_futures = {
                executor.submit(
                    self.evaluator.grade,
                    planner_input.task,
                    planner_input.rubric,
                    output.content,
                    planner_input.turn,
                ): (
                    index,
                    output,
                )
                for index, output in candidates
            }
            scored = []
            for future in as_completed(grade_futures):
                index, output = grade_futures[future]
                if future.exception() is None:
                    verdict = future.result()
                    scored.append((verdict.score, len(output.content), index, output))
                else:
                    scored.append((0.0, len(output.content), index, output))
        scored.sort(key=lambda item: (-item[0], item[1], item[2]))
        return scored[0][3]
