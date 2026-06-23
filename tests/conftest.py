from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pytest


@dataclass
class FakeUsage:
    prompt_tokens: int = 10
    completion_tokens: int = 20


@dataclass
class FakeMessage:
    content: str
    role: str = "assistant"


@dataclass
class FakeChoice:
    message: FakeMessage
    finish_reason: str = "stop"


@dataclass
class FakeCompletion:
    choices: list[FakeChoice]
    usage: FakeUsage = field(default_factory=FakeUsage)


@dataclass
class FakeDelta:
    content: str


@dataclass
class FakeStreamChoice:
    delta: FakeDelta
    finish_reason: str = ""


@dataclass
class FakeStreamChunk:
    choices: list[FakeStreamChoice]


@dataclass
class FakeEmbedding:
    embedding: list[float]


@dataclass
class FakeEmbeddingResponse:
    data: list[FakeEmbedding]


class FakeLLMClient:
    def __init__(
        self,
        responses: list[str] | None = None,
        usage: FakeUsage | None = None,
        embedding_vectors: list[list[float]] | None = None,
    ) -> None:
        self._responses = list(responses or [])
        self._embedding_vectors = list(embedding_vectors or [])
        self.usage = usage or FakeUsage()
        self.call_log: list[dict[str, Any]] = []
        self.model = "gpt-4o"

    def set_response(self, content: str) -> None:
        self._responses.insert(0, content)

    def set_responses(self, contents: list[str]) -> None:
        self._responses = list(contents)

    @property
    def chat(self):
        return self

    @property
    def completions(self):
        return self

    @property
    def embeddings(self):
        return self

    def create(self, **kwargs) -> FakeCompletion | FakeEmbeddingResponse:
        self.call_log.append(kwargs)
        if "input" in kwargs:
            inputs = kwargs["input"]
            vectors = [
                (
                    self._embedding_vectors.pop(0)
                    if self._embedding_vectors
                    else [float(index + 1), 0.0]
                )
                for index, _ in enumerate(inputs)
            ]
            return FakeEmbeddingResponse(
                data=[FakeEmbedding(vector) for vector in vectors]
            )
        content = self._responses.pop(0) if self._responses else ""
        return FakeCompletion(
            choices=[FakeChoice(message=FakeMessage(content=content))], usage=self.usage
        )


@pytest.fixture
def state_dir(tmp_path: Path) -> Path:
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
