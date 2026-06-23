from __future__ import annotations

from dataclasses import dataclass, field
from importlib import import_module
from typing import Any

from .exceptions import ConfigurationError
from .retry import retry_call


@dataclass
class AdapterUsage:
    prompt_tokens: int = 0
    completion_tokens: int = 0


@dataclass
class AdapterMessage:
    content: str
    role: str = "assistant"
    reasoning: str = ""


@dataclass
class AdapterChoice:
    message: AdapterMessage
    finish_reason: str = "stop"


@dataclass
class AdapterCompletion:
    choices: list[AdapterChoice]
    usage: AdapterUsage = field(default_factory=AdapterUsage)


class OpenRouterClientAdapter:
    def __init__(
        self,
        *,
        api_key: str,
        model: str = "z-ai/glm-5.2",
        provider: dict[str, Any] | None = None,
        x_open_router_title: str = "",
        reasoning_effort: str = "medium",
        sdk=None,
    ) -> None:
        if not api_key and sdk is None:
            raise ConfigurationError("OPENROUTER_API_KEY is required")
        self.model = model
        self.provider = provider or {}
        self.reasoning_effort = reasoning_effort
        self.sdk = sdk or self._create_sdk(
            api_key=api_key,
            x_open_router_title=x_open_router_title,
        )
        self.chat = _OpenRouterChat(self)

    def close(self) -> None:
        close = getattr(self.sdk, "close", None)
        if callable(close):
            close()

    def __enter__(self) -> "OpenRouterClientAdapter":
        enter = getattr(self.sdk, "__enter__", None)
        if callable(enter):
            entered = enter()
            if entered is not None:
                self.sdk = entered
        return self

    def __exit__(self, exc_type, exc, traceback) -> bool:
        exit_method = getattr(self.sdk, "__exit__", None)
        if callable(exit_method):
            return bool(exit_method(exc_type, exc, traceback))
        self.close()
        return False

    @staticmethod
    def _create_sdk(
        *,
        api_key: str,
        x_open_router_title: str,
    ):
        try:
            module = import_module("openrouter")
        except ImportError as exc:
            raise ConfigurationError(
                "Install the OpenRouter SDK with `pip install openrouter` to use LLM_PROVIDER=openrouter"
            ) from exc
        OpenRouter = getattr(module, "OpenRouter")
        kwargs: dict[str, str] = {"api_key": api_key}
        if x_open_router_title:
            kwargs["x_open_router_title"] = x_open_router_title
        return OpenRouter(**kwargs)


class _OpenRouterChat:
    def __init__(self, adapter: OpenRouterClientAdapter) -> None:
        self.completions = _OpenRouterCompletions(adapter)


class _OpenRouterCompletions:
    def __init__(self, adapter: OpenRouterClientAdapter) -> None:
        self._adapter = adapter

    def create(self, **kwargs) -> AdapterCompletion:
        request_kwargs = {
            "messages": kwargs["messages"],
            "model": kwargs["model"],
            "stream": bool(kwargs.get("stream", False)),
        }
        optional_kwargs = {
            "provider": self._adapter.provider or None,
            "temperature": kwargs.get("temperature"),
            "max_tokens": kwargs.get("max_tokens"),
            "response_format": kwargs.get("response_format"),
            "reasoning": {"effort": self._adapter.reasoning_effort},
        }
        request_kwargs.update(
            {key: value for key, value in optional_kwargs.items() if value is not None}
        )
        response = retry_call(lambda: self._adapter.sdk.chat.send(**request_kwargs))
        if request_kwargs["stream"]:
            return response
        return _to_completion(response)


def openrouter_provider_options(
    *,
    zdr: bool = False,
    only: tuple[str, ...] | list[str] | None = None,
) -> dict[str, Any]:
    provider: dict[str, Any] = {}
    if zdr:
        provider["zdr"] = True
    if only:
        provider["only"] = list(only)
    return provider


def _to_completion(response: Any) -> AdapterCompletion:
    return AdapterCompletion(
        choices=[
            AdapterChoice(
                message=AdapterMessage(
                    content=_extract_content(response),
                    reasoning=_extract_reasoning(response),
                )
            )
        ],
        usage=_extract_usage(response),
    )


def _extract_content(response: Any) -> str:
    if isinstance(response, dict):
        choices = response.get("choices") or []
        if choices:
            message = choices[0].get("message", {})
            return str(message.get("content", ""))
        return str(response.get("content") or response.get("output_text") or "")
    choices = getattr(response, "choices", None)
    if choices:
        message = getattr(choices[0], "message", None)
        if isinstance(message, dict):
            return str(message.get("content", ""))
        return str(getattr(message, "content", ""))
    for attr in ("content", "output_text", "text"):
        value = getattr(response, attr, None)
        if value is not None:
            return str(value)
    return str(response or "")


def _extract_usage(response: Any) -> AdapterUsage:
    usage = (
        response.get("usage", {})
        if isinstance(response, dict)
        else getattr(response, "usage", None)
    )
    if usage is None:
        return AdapterUsage()
    if isinstance(usage, dict):
        return AdapterUsage(
            prompt_tokens=int(usage.get("prompt_tokens", 0) or 0),
            completion_tokens=int(usage.get("completion_tokens", 0) or 0),
        )
    return AdapterUsage(
        prompt_tokens=int(getattr(usage, "prompt_tokens", 0) or 0),
        completion_tokens=int(getattr(usage, "completion_tokens", 0) or 0),
    )


def _extract_reasoning(response: Any) -> str:
    if isinstance(response, dict):
        choices = response.get("choices") or []
        if choices:
            return _reasoning_from_message(choices[0].get("message", {}))
        return _reasoning_from_message(response)
    choices = getattr(response, "choices", None)
    if choices:
        return _reasoning_from_message(getattr(choices[0], "message", None))
    return _reasoning_from_message(response)


def _reasoning_from_message(message: Any) -> str:
    if message is None:
        return ""
    if isinstance(message, dict):
        reasoning = message.get("reasoning") or message.get("reasoning_content")
        if reasoning:
            return str(reasoning)
        return _reasoning_details_text(message.get("reasoning_details"))
    reasoning = getattr(message, "reasoning", None) or getattr(
        message, "reasoning_content", None
    )
    if reasoning:
        return str(reasoning)
    return _reasoning_details_text(getattr(message, "reasoning_details", None))


def _reasoning_details_text(details: Any) -> str:
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
