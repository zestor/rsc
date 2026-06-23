from __future__ import annotations

import json
import math
import os
import tempfile
from collections import defaultdict
from contextlib import contextmanager
from datetime import datetime, timezone
from importlib.util import find_spec
from pathlib import Path
from typing import Any, Iterator

from .artifact_protocol import ArtifactParser
from .contracts import ArtifactState, MemoryEntry, MemoryStage, RoleOutput, RoleType
from .exceptions import ConfigurationError
from .observability import get_logger, log_event, model_dump_summary, text_summary
from .prompt_assembler import PromptAssembler
from .retry import retry_call


class StateManager:
    def __init__(
        self,
        base_dir: str | Path,
        client=None,
        max_ledger_entries: int = 500,
        embedder_enabled: bool = False,
        embedder_model: str = "text-embedding-3-large",
        prompt_assembler: PromptAssembler | None = None,
    ) -> None:
        self.base_dir = Path(base_dir)
        self.client = client
        self.max_ledger_entries = max_ledger_entries
        self.embedder_enabled = embedder_enabled
        self.embedder_model = embedder_model
        self._ledger_path = self.base_dir / "memory_ledger.json"
        self._memory_path = self.base_dir / "memory.md"
        self._artifact_path = self.base_dir / "artifact_state.json"
        self._prompt_assembler = prompt_assembler or PromptAssembler("gpt-5.5")
        self._artifact_parser = ArtifactParser()
        self._logger = get_logger("state_manager")
        self._verify_file_locking()

    def _verify_file_locking(self) -> None:
        if find_spec("fcntl") is not None:
            self._lock_backend = "fcntl"
            return
        if find_spec("portalocker") is not None:
            self._lock_backend = "portalocker"
            return
        raise ConfigurationError("File locking requires fcntl or portalocker")

    def update_artifact_state(
        self, current: ArtifactState, role_output: RoleOutput, turn: int
    ) -> ArtifactState:
        before_metrics = dict(current.metrics)
        data = current.model_dump()
        data["current_turn"] = turn
        if role_output.role == RoleType.PLANNER:
            data["current_plan"] = role_output.content
        data["intermediate_results"] = list(current.intermediate_results) + [
            f"[{turn}:{role_output.role.value}] {role_output.content[:1000]}"
        ]
        data["decisions"] = list(
            current.decisions
        ) + self._artifact_parser.extract_decisions(role_output.content)
        metrics = dict(current.metrics)
        metrics.update(
            {
                "last_role": role_output.role.value,
                "last_elapsed_seconds": role_output.elapsed_seconds,
                "tokens_input_cumulative": metrics.get("tokens_input_cumulative", 0)
                + role_output.tokens_used_input,
                "tokens_output_cumulative": metrics.get("tokens_output_cumulative", 0)
                + role_output.tokens_used_output,
            }
        )
        data["metrics"] = metrics
        data["artifacts"] = list(current.artifacts) + list(role_output.artifacts)
        updated = ArtifactState.model_validate(data)
        log_event(
            self._logger,
            "artifact.update",
            session_id=current.session_id,
            depth=0,
            turn=turn,
            role=role_output.role.value,
            role_output=text_summary(role_output.content),
            role_error=role_output.error,
            decisions_added=len(updated.decisions) - len(current.decisions),
            artifacts_added=len(updated.artifacts) - len(current.artifacts),
            intermediate_results_added=len(updated.intermediate_results)
            - len(current.intermediate_results),
            metrics_before=before_metrics,
            metrics_after=updated.metrics,
            artifact_state=model_dump_summary(updated),
        )
        return updated

    def save_artifact_state(self, state: ArtifactState) -> None:
        self._atomic_write_json(self._artifact_path, state.model_dump(mode="json"))
        log_event(
            self._logger,
            "artifact.save",
            session_id=state.session_id,
            depth=0,
            path=str(self._artifact_path),
            artifact_state=model_dump_summary(state),
            artifact_count=len(state.artifacts),
            search_result_count=len(state.search_results),
            selected_skill_count=len(state.selected_skills),
        )

    def append_memory_entry(self, entry: MemoryEntry) -> None:
        self.base_dir.mkdir(parents=True, exist_ok=True)
        with self._locked(self._ledger_path):
            ledger = self._read_ledger()
            ledger["entries"].append(entry.model_dump(mode="json"))
            self._write_json_unlocked(self._ledger_path, ledger)
            self._write_text_unlocked(
                self._memory_path, self._render_memory_md(ledger["entries"])
            )
            entry_count = len(ledger["entries"])
            ledger_summary = model_dump_summary(ledger)
        if entry_count > self.max_ledger_entries:
            self.compress_memory()
        log_event(
            self._logger,
            "memory.append",
            session_id=entry.session_id,
            depth=0,
            stage=entry.stage.value,
            entry_id=entry.entry_id,
            entry_count=entry_count,
            task_hint=text_summary(entry.task_hint),
            content=text_summary(entry.content),
            ledger=ledger_summary,
            memory_path=str(self._memory_path),
            ledger_path=str(self._ledger_path),
        )

    def distill_to_memory(self, task: str, loop_turns: list, client=None) -> list[str]:
        active_client = client or self.client
        if active_client is None:
            raise ConfigurationError("distill_to_memory requires a client")
        system, user = self._prompt_assembler.build_distill_messages(task, loop_turns)
        log_event(
            self._logger,
            "memory.distill.start",
            session_id=self._session_id(loop_turns),
            depth=0,
            task=text_summary(task),
            turn_count=len(loop_turns),
            model=getattr(active_client, "model", "gpt-5.5"),
            system_prompt=text_summary(system),
            user_message=text_summary(user),
            estimated_system_tokens=self._prompt_assembler.count_tokens(system),
            estimated_user_tokens=self._prompt_assembler.count_tokens(user),
        )
        response = retry_call(
            lambda: active_client.chat.completions.create(
                model=getattr(active_client, "model", "gpt-5.5"),
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                temperature=0.0,
                response_format={"type": "json_object"},
            ),
            on_retry=lambda exc, attempt, delay: log_event(
                self._logger,
                "memory.distill.retry",
                session_id=self._session_id(loop_turns),
                depth=0,
                error_type=exc.__class__.__name__,
                error=str(exc),
                attempt=attempt,
                delay_seconds=delay,
            ),
        )
        raw = response.choices[0].message.content or "{}"
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            payload = {"rules": []}
        candidate_rules = [
            str(rule).strip() for rule in payload.get("rules", []) if str(rule).strip()
        ]
        existing_rules = self._current_distilled_rules()
        existing = {rule.strip().lower() for rule in existing_rules}
        appended: list[str] = []
        for rule in candidate_rules:
            normalized = rule.strip().lower()
            if normalized in existing or self._is_semantic_duplicate(
                rule, existing_rules, active_client
            ):
                continue
            self.append_memory_entry(
                MemoryEntry(
                    task_hint=task[:80],
                    stage=MemoryStage.DISTILL,
                    content=rule,
                    session_id=self._session_id(loop_turns),
                )
            )
            existing.add(normalized)
            existing_rules.append(rule)
            appended.append(rule)
        log_event(
            self._logger,
            "memory.distill.complete",
            session_id=self._session_id(loop_turns),
            depth=0,
            raw_response=text_summary(raw),
            candidate_rule_count=len(candidate_rules),
            appended_rule_count=len(appended),
            appended_rules=[text_summary(rule) for rule in appended],
            success=True,
        )
        return appended

    def compress_memory(self) -> None:
        if self.client is None:
            raise ConfigurationError("compress_memory requires a client")
        with self._locked(self._ledger_path):
            ledger = self._read_ledger()
            entries = ledger["entries"]
            selected = [
                entry
                for entry in entries
                if entry.get("stage") != MemoryStage.COMPRESSED_SUMMARY.value
            ][:400]
            if not selected:
                log_event(
                    self._logger,
                    "memory.compress.skip",
                    session_id="memory",
                    depth=0,
                    reason="no_non_summary_entries",
                    entry_count=len(entries),
                )
                return
            selected_ids = {entry["entry_id"] for entry in selected}
            grouped: dict[str, list[str]] = defaultdict(list)
            for entry in selected:
                grouped[entry.get("stage", "unknown")].append(entry.get("content", ""))
            system, user = self._prompt_assembler.build_compress_messages(dict(grouped))
            log_event(
                self._logger,
                "memory.compress.start",
                session_id="memory",
                depth=0,
                selected_count=len(selected),
                grouped_stage_counts={
                    stage: len(items) for stage, items in grouped.items()
                },
                system_prompt=text_summary(system),
                user_message=text_summary(user),
            )
            response = retry_call(
                lambda: self.client.chat.completions.create(
                    model=getattr(self.client, "model", "gpt-5.5"),
                    messages=[
                        {"role": "system", "content": system},
                        {"role": "user", "content": user},
                    ],
                    temperature=0.0,
                ),
                on_retry=lambda exc, attempt, delay: log_event(
                    self._logger,
                    "memory.compress.retry",
                    session_id="memory",
                    depth=0,
                    error_type=exc.__class__.__name__,
                    error=str(exc),
                    attempt=attempt,
                    delay_seconds=delay,
                ),
            )
            compressed = response.choices[0].message.content or ""
            summary = MemoryEntry(
                task_hint="memory compression",
                stage=MemoryStage.COMPRESSED_SUMMARY,
                content=compressed,
                session_id="memory",
            )
            ledger["entries"] = [
                entry for entry in entries if entry.get("entry_id") not in selected_ids
            ]
            ledger["entries"].append(summary.model_dump(mode="json"))
            self._write_json_unlocked(self._ledger_path, ledger)
            self._write_text_unlocked(
                self._memory_path, self._render_memory_md(ledger["entries"])
            )
            log_event(
                self._logger,
                "memory.compress",
                session_id="memory",
                depth=0,
                compressed_count=len(selected),
                compressed=text_summary(compressed),
                remaining_entry_count=len(ledger["entries"]),
                ledger=model_dump_summary(ledger),
                success=True,
            )

    def _atomic_write_json(self, path: Path, data: Any) -> None:
        with self._locked(path):
            self._write_json_unlocked(path, data)

    def _atomic_write_text(self, path: Path, text: str) -> None:
        with self._locked(path):
            self._write_text_unlocked(path, text)

    def _render_memory_md(self, entries: list[dict]) -> str:
        timestamp = datetime.now(timezone.utc).isoformat()
        compressed = "\n".join(
            entry.get("content", "")
            for entry in entries
            if entry.get("stage") == MemoryStage.COMPRESSED_SUMMARY.value
        )
        rules = [
            entry.get("content", "")
            for entry in entries
            if entry.get("stage") == MemoryStage.DISTILL.value
        ]
        failures = [
            entry.get("content", "")
            for entry in reversed(entries)
            if entry.get("stage") == MemoryStage.FAIL.value
        ][:5]
        distilled = "\n".join(f"- {rule}" for rule in rules)
        recent_failures = "\n".join(f"- {failure}" for failure in failures)
        return (
            f"# Memory State\nLast updated: {timestamp}\n\n"
            f"## Compressed History\n{compressed}\n\n"
            f"## Distilled Rules\n{distilled}\n\n"
            f"## Ongoing Context\n\n\n"
            f"## History Summary\n\n\n"
            f"## Recent Failures\n{recent_failures}\n"
        )

    @contextmanager
    def _locked(self, path: Path) -> Iterator[None]:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.touch(exist_ok=True)
        handle = open(path, "a+b")
        try:
            if self._lock_backend == "fcntl":
                import fcntl

                fcntl.flock(handle, fcntl.LOCK_EX)
            else:
                import portalocker

                portalocker.lock(handle, portalocker.LOCK_EX)
            yield
        finally:
            if self._lock_backend == "fcntl":
                import fcntl

                fcntl.flock(handle, fcntl.LOCK_UN)
            else:
                import portalocker

                portalocker.unlock(handle)
            handle.close()

    def _read_ledger(self) -> dict[str, Any]:
        if not self._ledger_path.exists() or self._ledger_path.stat().st_size == 0:
            return {"schema_version": "1.0", "entries": []}
        with self._ledger_path.open() as handle:
            data = json.load(handle)
        data.setdefault("schema_version", "1.0")
        data.setdefault("entries", [])
        return data

    def _write_json_unlocked(self, path: Path, data: Any) -> None:
        self._write_text_unlocked(path, json.dumps(data, indent=2, sort_keys=True))

    def _write_text_unlocked(self, path: Path, text: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = None
        try:
            with tempfile.NamedTemporaryFile(
                "w", dir=path.parent, delete=False
            ) as handle:
                temp_path = Path(handle.name)
                handle.write(text)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temp_path, path)
        finally:
            if temp_path is not None and temp_path.exists():
                temp_path.unlink()

    def _current_distilled_rules(self) -> list[str]:
        ledger = self._read_ledger()
        return [
            entry.get("content", "")
            for entry in ledger["entries"]
            if entry.get("stage") == MemoryStage.DISTILL.value
        ]

    def _is_semantic_duplicate(
        self, rule: str, existing_rules: list[str] | None = None, client=None
    ) -> bool:
        if not self.embedder_enabled:
            return False
        active_client = client or self.client
        if active_client is None:
            raise ConfigurationError("embedder deduplication requires a client")
        candidates = (
            existing_rules
            if existing_rules is not None
            else self._current_distilled_rules()
        )
        if not candidates:
            return False
        vectors = self._embed_texts([rule, *candidates], active_client)
        candidate_vector = vectors[0]
        return any(
            self._cosine_similarity(candidate_vector, existing_vector) >= 0.92
            for existing_vector in vectors[1:]
        )

    def _embed_texts(self, texts: list[str], client) -> list[list[float]]:
        response = retry_call(
            lambda: client.embeddings.create(model=self.embedder_model, input=texts),
            on_retry=lambda exc, attempt, delay: log_event(
                self._logger,
                "memory.embedding.retry",
                session_id="memory",
                depth=0,
                error_type=exc.__class__.__name__,
                error=str(exc),
                attempt=attempt,
                delay_seconds=delay,
            ),
        )
        return [list(item.embedding) for item in response.data]

    @staticmethod
    def _cosine_similarity(left: list[float], right: list[float]) -> float:
        numerator = sum(a * b for a, b in zip(left, right))
        left_norm = math.sqrt(sum(a * a for a in left))
        right_norm = math.sqrt(sum(b * b for b in right))
        if left_norm == 0.0 or right_norm == 0.0:
            return 0.0
        return numerator / (left_norm * right_norm)

    @staticmethod
    def _session_id(loop_turns: list) -> str:
        return (
            "session"
            if not loop_turns
            else getattr(loop_turns[-1], "session_id", "session")
        )
