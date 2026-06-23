from __future__ import annotations

from rsc.config import RSCConfig
from rsc.contracts import RubricCriterion
from rsc.runtime import build_orchestrator


def main() -> None:
    config = RSCConfig.from_env()
    orchestrator = build_orchestrator(config)
    rubric = [
        RubricCriterion(
            label="complete",
            description="The answer fully satisfies the requested task.",
        ),
        RubricCriterion(
            label="correct",
            description="The answer is logically consistent and executable where applicable.",
        ),
    ]
    result = orchestrator.run(
        task="Write a Python function parse_date(s: str) -> datetime.date for YYYY-MM-DD, MMDDYYYY, and DD-Mon-YYYY.",
        rubric=rubric,
        skill_name="coding",
    )
    print(result.status)
    print(result.final_score)
    print(result.turns_used)
    print(result.final_output)


if __name__ == "__main__":
    main()
