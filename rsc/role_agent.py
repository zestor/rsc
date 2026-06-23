from __future__ import annotations

import time
from contextlib import contextmanager
from types import SimpleNamespace
from typing import Iterator

from .artifact_protocol import ArtifactParser
from .contracts import RoleInput, RoleOutput, RoleType
from .observability import get_logger, log_event, text_summary
from .prompt_assembler import PromptAssembler
from .retry import retry_call

DEFAULT_TEMPERATURE_MAP: dict[RoleType, float] = {
    RoleType.PLANNER: 0.4,
    RoleType.CRITIC: 0.2,
    RoleType.VERIFIER: 0.0,
    RoleType.REVISER: 0.3,
    RoleType.SYNTHESIZER: 0.2,
}


class RoleAgent:
    def __init__(
        self,
        client,
        model: str,
        prompt_assembler: PromptAssembler,
        artifact_parser: ArtifactParser,
        temperature_map: dict[RoleType, float] | None = None,
        max_output_tokens: int = 4000,
        context_manager=None,
    ) -> None:
        self.client = client
        self.model = model
        self.prompt_assembler = prompt_assembler
        self.artifact_parser = artifact_parser
        self._temperature_map = dict(DEFAULT_TEMPERATURE_MAP)
        if temperature_map:
            self._temperature_map.update(temperature_map)
        self.max_output_tokens = max_output_tokens
        self.context_manager = context_manager
        self._logger = get_logger("role_agent")

    def invoke(self, role_input: RoleInput) -> RoleOutput:
        # Enforce context window budget before building messages.
        # Only modifies composed_state (system prompt data); user message
        # data is never touched.
        if self.context_manager is not None:
            composed_state, exhausted = self.context_manager.enforce_budget(
                composed_state=role_input.composed_state,
                role=role_input.role,
                session_id=role_input.session_id,
                depth=role_input.depth,
                turn=role_input.turn,
            )
            if exhausted:
                elapsed = 0.0
                log_event(
                    self._logger,
                    "role.complete",
                    session_id=role_input.session_id,
                    depth=role_input.depth,
                    role=role_input.role.value,
                    turn=role_input.turn,
                    elapsed_seconds=elapsed,
                    tokens_used_input=0,
                    tokens_used_output=0,
                    artifact_count=0,
                    error="context_exhausted",
                    error_type="ContextExhausted",
                    success=False,
                )
                return RoleOutput(
                    role=role_input.role,
                    content="",
                    error="context_exhausted",
                    elapsed_seconds=elapsed,
                )
            role_input = role_input.model_copy(
                update={"composed_state": composed_state}
            )
        system, user = self.prompt_assembler.build_role_messages(role_input)
        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ]
        system_tokens = self.prompt_assembler.count_tokens(system)
        user_tokens = self.prompt_assembler.count_tokens(user)
        started = time.perf_counter()
        log_event(
            self._logger,
            "role.start",
            session_id=role_input.session_id,
            depth=role_input.depth,
            role=role_input.role.value,
            turn=role_input.turn,
            model=self.model,
            temperature=self._temperature_map[role_input.role],
            max_output_tokens=self.max_output_tokens,
            task=text_summary(role_input.task),
            prior_output=text_summary(role_input.prior_output),
            system_prompt=text_summary(system),
            user_message=text_summary(user),
            estimated_system_tokens=system_tokens,
            estimated_user_tokens=user_tokens,
            estimated_input_tokens=system_tokens + user_tokens,
            rubric_labels=[criterion.label for criterion in role_input.rubric],
            selected_skill_ids=[
                skill.skill_id
                for skill in role_input.composed_state.artifact.selected_skills
            ],
            search_result_count=len(role_input.composed_state.artifact.search_results),
            artifact_count=len(role_input.composed_state.artifact.artifacts),
            intermediate_result_count=len(
                role_input.composed_state.artifact.intermediate_results
            ),
            decision_count=len(role_input.composed_state.artifact.decisions),
        )
        try:
            response = self._create_with_retries(role_input, messages)
        except Exception as exc:
            if exc.__class__.__name__ == "ContentFilterError":
                elapsed = time.perf_counter() - started
                log_event(
                    self._logger,
                    "role.complete",
                    session_id=role_input.session_id,
                    depth=role_input.depth,
                    role=role_input.role.value,
                    turn=role_input.turn,
                    elapsed_seconds=elapsed,
                    tokens_used_input=0,
                    tokens_used_output=0,
                    artifact_count=0,
                    error=str(exc),
                    error_type=exc.__class__.__name__,
                    success=False,
                )
                return RoleOutput(
                    role=role_input.role,
                    content="",
                    error=str(exc),
                    elapsed_seconds=elapsed,
                )
            raise
        message = response.choices[0].message
        content = message.content or ""
        reasoning = getattr(message, "reasoning", "") or ""
        artifacts = self.artifact_parser.extract(
            content, role_input.role, role_input.turn
        )
        usage = getattr(response, "usage", None)
        elapsed = time.perf_counter() - started
        log_event(
            self._logger,
            "role.complete",
            session_id=role_input.session_id,
            depth=role_input.depth,
            role=role_input.role.value,
            turn=role_input.turn,
            elapsed_seconds=elapsed,
            tokens_used_input=getattr(usage, "prompt_tokens", 0),
            tokens_used_output=getattr(usage, "completion_tokens", 0),
            artifact_count=len(artifacts),
            artifact_ids=[artifact.artifact_id for artifact in artifacts],
            output=text_summary(content),
            reasoning=text_summary(reasoning) if reasoning else None,
            finish_reason=getattr(response.choices[0], "finish_reason", ""),
            success=True,
        )
        return RoleOutput(
            role=role_input.role,
            content=content,
            artifacts=artifacts,
            tokens_used_input=getattr(usage, "prompt_tokens", 0),
            tokens_used_output=getattr(usage, "completion_tokens", 0),
            elapsed_seconds=elapsed,
        )

    def _create_with_retries(
        self, role_input: RoleInput, messages: list[dict[str, str]]
    ):
        def operation():
            try:
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    temperature=self._temperature_map[role_input.role],
                    max_tokens=self.max_output_tokens,
                    stream=True,
                )
            except TypeError:
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    temperature=self._temperature_map[role_input.role],
                    max_tokens=self.max_output_tokens,
                )
            return self._completion_from_response(response, role_input)

        def on_retry(exc: BaseException, retry_number: int, delay: float) -> None:
            log_event(
                self._logger,
                "role.retry",
                session_id=role_input.session_id,
                depth=role_input.depth,
                role=role_input.role.value,
                turn=role_input.turn,
                error_type=exc.__class__.__name__,
                error=str(exc),
                attempt=retry_number,
                delay_seconds=delay,
            )

        try:
            return retry_call(operation, on_retry=on_retry)
        except Exception as exc:
            log_event(
                self._logger,
                "role.error",
                session_id=role_input.session_id,
                depth=role_input.depth,
                role=role_input.role.value,
                turn=role_input.turn,
                error_type=exc.__class__.__name__,
                error=str(exc),
            )
            raise

    def _completion_from_response(self, response, role_input: RoleInput):
        if hasattr(response, "choices") or isinstance(response, dict):
            return response
        chunks: list[str] = []
        reasoning_chunks: list[str] = []
        text_buffer: list[str] = []
        reasoning_buffer: list[str] = []
        sequence = 0
        finish_reason = "stop"
        for chunk in response:
            delta = self._stream_delta_text(chunk)
            reasoning = self._stream_reasoning_text(chunk)
            finish_reason = self._stream_finish_reason(chunk) or finish_reason
            if not delta and not reasoning:
                continue
            if delta:
                chunks.append(delta)
                text_buffer.append(delta)
            if reasoning:
                reasoning_chunks.append(reasoning)
                reasoning_buffer.append(reasoning)
            buffered_text = "".join(text_buffer)
            buffered_reasoning = "".join(reasoning_buffer)
            if self._should_flush_stream_buffer(
                buffered_text
            ) or self._should_flush_stream_buffer(buffered_reasoning):
                sequence += 1
                self._log_stream_delta(
                    role_input,
                    buffered_text,
                    sequence,
                    reasoning=buffered_reasoning,
                )
                text_buffer = []
                reasoning_buffer = []
        if text_buffer or reasoning_buffer:
            sequence += 1
            self._log_stream_delta(
                role_input,
                "".join(text_buffer),
                sequence,
                reasoning="".join(reasoning_buffer),
            )
        content = "".join(chunks)
        reasoning_content = "".join(reasoning_chunks)
        return SimpleNamespace(
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(
                        content=content,
                        reasoning=reasoning_content,
                    ),
                    finish_reason=finish_reason,
                )
            ],
            usage=SimpleNamespace(prompt_tokens=0, completion_tokens=0),
        )

    def _log_stream_delta(
        self,
        role_input: RoleInput,
        delta: str,
        sequence: int,
        *,
        reasoning: str = "",
    ) -> None:
        payload = {
            "session_id": role_input.session_id,
            "depth": role_input.depth,
            "role": role_input.role.value,
            "turn": role_input.turn,
            "sequence": sequence,
        }
        if delta:
            payload["delta"] = text_summary(delta)
        if reasoning:
            payload["reasoning"] = text_summary(reasoning)
        log_event(
            self._logger,
            "role.delta",
            **payload,
        )

    @staticmethod
    def _should_flush_stream_buffer(buffered: str) -> bool:
        return bool(buffered) and (len(buffered) >= 80 or "\n" in buffered)

    @staticmethod
    def _stream_delta_text(chunk) -> str:
        if isinstance(chunk, dict):
            choices = chunk.get("choices") or []
            if choices:
                delta = choices[0].get("delta") or {}
                message = choices[0].get("message") or {}
                return str(delta.get("content") or message.get("content") or "")
            return str(chunk.get("content") or chunk.get("text") or "")
        choices = getattr(chunk, "choices", None)
        if choices:
            delta = getattr(choices[0], "delta", None)
            if isinstance(delta, dict):
                return str(delta.get("content") or "")
            content = getattr(delta, "content", None)
            if content is not None:
                return str(content)
            message = getattr(choices[0], "message", None)
            if message is not None:
                return str(getattr(message, "content", "") or "")
        for attr in ("content", "text", "output_text"):
            value = getattr(chunk, attr, None)
            if value is not None:
                return str(value)
        return ""

    @classmethod
    def _stream_reasoning_text(cls, chunk) -> str:
        if isinstance(chunk, dict):
            choices = chunk.get("choices") or []
            if choices:
                delta = choices[0].get("delta") or {}
                message = choices[0].get("message") or {}
                return cls._reasoning_from_payload(
                    delta
                ) or cls._reasoning_from_payload(message)
            return cls._reasoning_from_payload(chunk)
        choices = getattr(chunk, "choices", None)
        if choices:
            delta = getattr(choices[0], "delta", None)
            message = getattr(choices[0], "message", None)
            return cls._reasoning_from_payload(delta) or cls._reasoning_from_payload(
                message
            )
        return cls._reasoning_from_payload(chunk)

    @classmethod
    def _reasoning_from_payload(cls, payload) -> str:
        if payload is None:
            return ""
        if isinstance(payload, dict):
            reasoning = payload.get("reasoning") or payload.get("reasoning_content")
            if reasoning:
                return str(reasoning)
            return cls._reasoning_details_text(payload.get("reasoning_details"))
        reasoning = getattr(payload, "reasoning", None) or getattr(
            payload, "reasoning_content", None
        )
        if reasoning:
            return str(reasoning)
        return cls._reasoning_details_text(getattr(payload, "reasoning_details", None))

    @staticmethod
    def _reasoning_details_text(details) -> str:
        if not details:
            return ""
        parts: list[str] = []
        for item in details:
            if isinstance(item, dict):
                text = item.get("text") or item.get("summary")
            else:
                text = getattr(item, "text", None) or getattr(item, "summary", None)
            if text:
                parts.append(str(text))
        return "\n\n".join(parts)

    @staticmethod
    def _stream_finish_reason(chunk) -> str:
        if isinstance(chunk, dict):
            choices = chunk.get("choices") or []
            return str(choices[0].get("finish_reason") or "") if choices else ""
        choices = getattr(chunk, "choices", None)
        if choices:
            return str(getattr(choices[0], "finish_reason", "") or "")
        return ""

    @contextmanager
    def temperature_override(
        self, role: RoleType, temperature: float
    ) -> Iterator[None]:
        original = self._temperature_map[role]
        self._temperature_map[role] = temperature
        try:
            yield
        finally:
            self._temperature_map[role] = original
