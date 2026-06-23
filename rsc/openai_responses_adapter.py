from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .retry import retry_call


@dataclass
class AdapterUsage:
    prompt_tokens: int = 0
    completion_tokens: int = 0


@dataclass
class AdapterMessage:
    content: str
    role: str = "assistant"


@dataclass
class AdapterChoice:
    message: AdapterMessage
    finish_reason: str = "stop"


@dataclass
class AdapterCompletion:
    choices: list[AdapterChoice]
    usage: AdapterUsage = field(default_factory=AdapterUsage)


class OpenAIResponsesClientAdapter:
    def __init__(
        self,
        client,
        *,
        text_verbosity: str = "medium",
        reasoning_effort: str = "medium",
        reasoning_summary: str = "auto",
        store: bool = True,
        include: list[str] | None = None,
    ) -> None:
        self.client = client
        self.text_verbosity = text_verbosity
        self.reasoning_effort = reasoning_effort
        self.reasoning_summary = reasoning_summary
        self.store = store
        self.include = include or [
            "reasoning.encrypted_content",
            "web_search_call.action.sources",
        ]
        self.chat = _ChatNamespace(self)
        self.embeddings = client.embeddings

    def create_response(self, **kwargs) -> AdapterCompletion:
        messages = kwargs.get("messages", [])
        text_format = _response_text_format(kwargs.get("response_format"))
        response = retry_call(
            lambda: self.client.responses.create(
                model=kwargs["model"],
                input=_messages_to_responses_input(messages),
                text={"format": text_format, "verbosity": self.text_verbosity},
                reasoning={
                    "effort": self.reasoning_effort,
                    "summary": self.reasoning_summary,
                },
                tools=[],
                store=self.store,
                include=self.include,
                max_output_tokens=kwargs.get("max_tokens"),
            )
        )
        return AdapterCompletion(
            choices=[
                AdapterChoice(message=AdapterMessage(content=_response_text(response)))
            ],
            usage=_response_usage(response),
        )


class _ChatNamespace:
    def __init__(self, adapter: OpenAIResponsesClientAdapter) -> None:
        self.completions = _CompletionsNamespace(adapter)


class _CompletionsNamespace:
    def __init__(self, adapter: OpenAIResponsesClientAdapter) -> None:
        self.adapter = adapter

    def create(self, **kwargs) -> AdapterCompletion:
        return self.adapter.create_response(**kwargs)


def _messages_to_responses_input(
    messages: list[dict[str, str]],
) -> list[dict[str, Any]]:
    response_input = []
    for message in messages:
        role = (
            "developer"
            if message.get("role") == "system"
            else message.get("role", "user")
        )
        response_input.append(
            {
                "role": role,
                "content": [
                    {
                        "type": "input_text",
                        "text": message.get("content") or "",
                    }
                ],
            }
        )
    return response_input


def _response_text_format(response_format) -> dict[str, str]:
    if response_format and response_format.get("type") == "json_object":
        return {"type": "json_object"}
    return {"type": "text"}


def _response_text(response) -> str:
    output_text = getattr(response, "output_text", None)
    if isinstance(output_text, str):
        return output_text
    output = getattr(response, "output", None) or []
    parts: list[str] = []
    for item in output:
        for content in getattr(item, "content", []) or []:
            text = getattr(content, "text", None)
            if isinstance(text, str):
                parts.append(text)
    return "".join(parts)


def _response_usage(response) -> AdapterUsage:
    usage = getattr(response, "usage", None)
    return AdapterUsage(
        prompt_tokens=int(getattr(usage, "input_tokens", 0) or 0),
        completion_tokens=int(getattr(usage, "output_tokens", 0) or 0),
    )
