from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml

from .contracts import (
    ArtifactState,
    ClaudeState,
    ComposedState,
    MemoryState,
    SkillState,
)
from .exceptions import StateLoadError


class StateLoader:
    def __init__(self, base_dir: str | Path) -> None:
        self.base_dir = Path(base_dir)
        self.skills_dir = self.base_dir / "skills"

    def load(self, skill_name: str, artifact: ArtifactState) -> ComposedState:
        return ComposedState(
            claude=self._load_claude(),
            memory=self._load_memory(),
            skill=self._load_skill(skill_name),
            artifact=artifact,
        )

    def _load_claude(self) -> ClaudeState:
        path = self.base_dir / "claude.md"
        if not path.exists():
            return ClaudeState(source_file=str(path))
        front_matter, body = self._parse_front_matter(path.read_text())
        data = dict(front_matter)
        if body.strip():
            existing = data.get("values_and_principles", "")
            suffix = f"## Supplemental Constitution Notes\n{body.strip()}"
            data["values_and_principles"] = f"{existing}\n\n{suffix}".strip()
        data["source_file"] = str(path)
        return ClaudeState(**data)

    def _load_memory(self) -> MemoryState:
        path = self.base_dir / "memory.md"
        if not path.exists():
            return MemoryState(source_file=str(path))
        text = path.read_text()
        front_matter, body = self._parse_front_matter(text)
        data: dict[str, Any] = dict(front_matter)
        if not front_matter:
            data.update(self._parse_rendered_memory_md(body))
        data["source_file"] = str(path)
        return MemoryState(**data)

    def _load_skill(self, skill_name: str) -> SkillState:
        path = self.skills_dir / f"{skill_name}.md"
        if not path.exists():
            return SkillState(name=skill_name, source_file=str(path))
        front_matter, _ = self._parse_front_matter(path.read_text())
        data = dict(front_matter)
        data.setdefault("name", skill_name)
        data["source_file"] = str(path)
        return SkillState(**data)

    @staticmethod
    def _parse_front_matter(text: str) -> tuple[dict, str]:
        if not text.startswith("---"):
            return {}, text
        parts = text.split("---", 2)
        if len(parts) < 3:
            return {}, text
        try:
            front_matter = yaml.safe_load(parts[1]) or {}
        except yaml.YAMLError as exc:
            raise StateLoadError(f"Malformed YAML front matter: {exc}") from exc
        if not isinstance(front_matter, dict):
            raise StateLoadError("YAML front matter must be a mapping")
        return front_matter, parts[2]

    @staticmethod
    def _parse_rendered_memory_md(text: str) -> dict[str, Any]:
        data: dict[str, Any] = {}

        def section(name: str) -> str:
            pattern = re.compile(
                rf"^## {re.escape(name)}\n(?P<body>.*?)(?=^## |\Z)",
                re.DOTALL | re.MULTILINE,
            )
            match = pattern.search(text)
            return match.group("body").strip() if match else ""

        distilled = [
            line[2:].strip()
            for line in section("Distilled Rules").splitlines()
            if line.startswith("- ")
        ]
        data["distilled_rules"] = distilled
        data["ongoing_context"] = section("Ongoing Context")
        data["history_summary"] = section("History Summary")
        return data
