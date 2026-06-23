from __future__ import annotations

import re

from .contracts import ArtifactRecord, RoleType
from .exceptions import ArtifactParseError

ARTIFACT_PATTERN = re.compile(
    r'<!--ARTIFACT:START id="(?P<id>[^"]+)" recurse="(?P<recurse>true|false)" -->'
    r"(?P<content>.+?)"
    r'<!--ARTIFACT:END id="(?P=id)" -->',
    re.DOTALL,
)
DECISION_PATTERN = re.compile(r"<!--DECISION:\s*(?P<text>.+?)\s*-->", re.DOTALL)


class ArtifactParser:
    def extract(self, text: str, role: RoleType, turn: int) -> list[ArtifactRecord]:
        seen: set[str] = set()
        artifacts: list[ArtifactRecord] = []
        for match in ARTIFACT_PATTERN.finditer(text):
            artifact_id = match.group("id")
            if artifact_id in seen:
                raise ArtifactParseError(
                    f"Duplicate artifact_id in role output: {artifact_id}"
                )
            seen.add(artifact_id)
            artifacts.append(
                ArtifactRecord(
                    artifact_id=artifact_id,
                    role=role,
                    turn=turn,
                    content=match.group("content"),
                    can_invoke_model=match.group("recurse") == "true",
                )
            )
        return artifacts

    def extract_decisions(self, text: str) -> list[str]:
        return [
            match.group("text").strip() for match in DECISION_PATTERN.finditer(text)
        ]

    @staticmethod
    def inject_recursive_result(
        text: str, artifact_id: str, recursive_result: str
    ) -> str:
        pattern = re.compile(
            r'<!--ARTIFACT:START id="'
            + re.escape(artifact_id)
            + r'" recurse="(?:true|false)" -->'
            r".+?"
            r'<!--ARTIFACT:END id="' + re.escape(artifact_id) + r'" -->',
            re.DOTALL,
        )
        replacement = f"## Recursive Result: {artifact_id}\n{recursive_result}"
        return pattern.sub(replacement, text)
