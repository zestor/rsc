from __future__ import annotations

import json
import logging
import queue
import re
import threading
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Iterator
from uuid import uuid4

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field

from .config import RSCConfig
from .contracts import LoopResult, RubricCriterion
from .document_converter import (
    DocumentChunk,
    chunk_converted_documents,
    convert_document_to_markdown,
    documents_to_prompt_context,
)
from .observability import JSONFormatter
from .runtime import build_orchestrator


class RubricItemRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    label: str = Field(min_length=1)
    description: str = Field(min_length=1)


class RunRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    task: str = Field(min_length=1)
    skill_name: str | None = None
    rubric: list[RubricItemRequest] = Field(default_factory=list)


class RunResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    session_id: str
    status: str
    final_score: float
    turns_used: int
    final_output: str
    total_tokens_input: int
    total_tokens_output: int
    memory_rules_added: list[str]
    turns: list[dict]


class ModeOption(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    label: str
    description: str


Runner = Callable[[RunRequest], LoopResult | RunResponse | dict]


def create_app(
    *,
    runner: Runner | None = None,
    static_dir: str | Path | None = None,
    config_factory: Callable[[], RSCConfig] | None = None,
) -> FastAPI:
    fastapi_app = FastAPI(title="Recursive Scaffolded Cognition", version="2.2.0")
    static_path = (
        Path(static_dir) if static_dir else Path(__file__).parent / "web" / "static"
    )
    config_factory = config_factory or (
        lambda: RSCConfig.from_env(require_api_key=False)
    )

    assets_path = static_path / "assets"
    if assets_path.exists():
        fastapi_app.mount("/assets", StaticFiles(directory=assets_path), name="assets")

    @fastapi_app.get("/api/health")
    def health() -> dict:
        return {"ok": True, "ui_available": (static_path / "index.html").exists()}

    @fastapi_app.get("/api/config")
    def safe_config() -> dict:
        config = config_factory()
        return {
            "llm_provider": config.llm_provider,
            "loop_model": config.loop_model,
            "eval_model": config.eval_model,
            "search_provider": config.search_provider,
            "search_max_results": config.search_max_results,
            "skill_top_k": config.skill_top_k,
            "state_dir": str(config.state_dir),
            "log_dir": str(config.log_dir),
            "skill_routing": (
                "automatic"
                if config.skill_library_paths
                else "automatic-with-default-fallback"
            ),
            "skill_library_paths": [str(path) for path in config.skill_library_paths],
            "models": _model_options(config),
            "modes": [mode.model_dump() for mode in _mode_options()],
            "ui_available": (static_path / "index.html").exists(),
        }

    @fastapi_app.post("/api/runs", response_model=RunResponse)
    def run_task(request: RunRequest) -> RunResponse:
        try:
            result = (
                runner(request) if runner is not None else _run_with_config(request)
            )
            return _to_run_response(result)
        except HTTPException:
            raise
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    @fastapi_app.post("/api/runs/stream")
    async def run_task_stream(
        task: str = Form(...),
        mode: str = Form("answer"),
        model: str | None = Form(None),
        rubric_json: str = Form("[]"),
        files: list[UploadFile] = File(default=[]),
    ) -> StreamingResponse:
        file_payloads = [
            {
                "filename": upload.filename or "attachment",
                "media_type": upload.content_type or "",
                "content": await upload.read(),
            }
            for upload in files
            if upload.filename
        ]

        def event_stream() -> Iterator[str]:
            yield _sse(
                "run.accepted",
                {"mode": mode, "model": model, "file_count": len(file_payloads)},
            )
            event_queue: queue.Queue[dict | None] = queue.Queue()
            worker = threading.Thread(
                target=_run_stream_worker,
                args=(
                    event_queue,
                    task,
                    mode,
                    model,
                    rubric_json,
                    file_payloads,
                    runner,
                    config_factory,
                ),
                daemon=True,
            )
            worker.start()
            while True:
                event = event_queue.get()
                if event is None:
                    break
                yield _sse(event["event"], event.get("data", {}))

        return StreamingResponse(event_stream(), media_type="text/event-stream")

    def _run_with_config(request: RunRequest) -> LoopResult:
        config = config_factory()
        orchestrator = build_orchestrator(config)
        rubric = [
            RubricCriterion(label=item.label, description=item.description)
            for item in request.rubric
        ] or _default_rubric()
        return orchestrator.run(
            task=request.task,
            rubric=rubric,
            skill_name=request.skill_name or "default",
        )

    @fastapi_app.get("/{path:path}", response_class=HTMLResponse)
    def spa(path: str = "") -> str:
        del path
        index = static_path / "index.html"
        if index.exists():
            return index.read_text(encoding="utf-8")
        return _missing_ui_html()

    return fastapi_app


def _default_rubric() -> list[RubricCriterion]:
    return [
        RubricCriterion(
            label="complete",
            description="The answer fully satisfies the requested task.",
        ),
        RubricCriterion(
            label="correct",
            description="The answer is logically consistent and executable where applicable.",
        ),
    ]


def _mode_options() -> list[ModeOption]:
    return [
        ModeOption(
            id="answer",
            label="Answer",
            description="Direct researched answer with citations when available.",
        ),
        ModeOption(
            id="research",
            label="Research",
            description="Deeper synthesis using search and attached documents.",
        ),
        ModeOption(
            id="write",
            label="Write",
            description="Draft structured long-form prose from the prompt and attachments.",
        ),
        ModeOption(
            id="code",
            label="Code",
            description="Implementation-oriented reasoning with verification criteria.",
        ),
    ]


def _model_options(config: RSCConfig) -> list[dict[str, str]]:
    return [
        {
            "provider": config.llm_provider,
            "model": config.loop_model,
            "label": f"Default: {config.loop_model}",
        }
    ]


def _run_stream_worker(
    event_queue: queue.Queue[dict | None],
    task: str,
    mode: str,
    model: str | None,
    rubric_json: str,
    file_payloads: list[dict],
    runner: Runner | None,
    config_factory: Callable[[], RSCConfig],
) -> None:
    handler = _QueueLogHandler(event_queue)
    logger = logging.getLogger("rsc")
    logger.addHandler(handler)
    try:
        run_id = str(uuid4())
        _emit_activity(
            event_queue,
            "Preparing your request",
            "Reading attachments and building a run plan.",
            step=1,
            total=8,
            status="active",
        )
        event_queue.put(
            {
                "event": "attachments.convert.start",
                "data": {"file_count": len(file_payloads)},
            }
        )
        documents = [
            convert_document_to_markdown(
                payload["filename"],
                payload["content"],
                media_type=payload["media_type"],
            )
            for payload in file_payloads
        ]
        event_queue.put(
            {
                "event": "attachments.convert.complete",
                "data": {"documents": [document.summary() for document in documents]},
            }
        )
        chunks = chunk_converted_documents(
            documents, target_chars=8000, overlap_chars=500
        )
        event_queue.put(
            {
                "event": "decomposition.plan",
                "data": {
                    "chunk_count": len(chunks),
                    "chunks": [chunk.summary() for chunk in chunks],
                    "strategy": "sequential" if len(chunks) > 1 else "single-pass",
                },
            }
        )
        _emit_activity(
            event_queue,
            "Decomposed context",
            _decomposition_detail(chunks),
            step=2,
            total=8,
            status="complete",
        )
        request = RunRequest(
            task=_compose_task(task, mode, documents_to_prompt_context(documents)),
            rubric=_rubric_items_from_json(rubric_json),
        )
        if runner is not None:
            _emit_activity(
                event_queue,
                "Starting RSC",
                "Using injected test runner.",
                step=3,
                total=8,
                status="active",
            )
            event_queue.put({"event": "rsc.run.start", "data": {"runner": "injected"}})
            result = runner(request)
        else:
            config = config_factory()
            if model:
                config = replace(config, loop_model=model, eval_model=model)
            artifact_dir = config.state_dir / "web_runs" / run_id
            artifact_dir.mkdir(parents=True, exist_ok=True)
            _write_json(
                artifact_dir / "manifest.json",
                {
                    "run_id": run_id,
                    "created_at": datetime.now(timezone.utc).isoformat(),
                    "mode": mode,
                    "model": config.loop_model,
                    "task": task,
                    "documents": [document.summary() for document in documents],
                    "chunks": [chunk.summary() for chunk in chunks],
                },
            )
            event_queue.put(
                {
                    "event": "artifacts.store.ready",
                    "data": {"run_id": run_id, "artifact_dir": str(artifact_dir)},
                }
            )
            _emit_activity(
                event_queue,
                "Starting RSC",
                f"Using {config.llm_provider} model {config.loop_model} in {mode} mode.",
                step=3,
                total=8,
                status="active",
            )
            event_queue.put(
                {
                    "event": "rsc.run.start",
                    "data": {
                        "provider": config.llm_provider,
                        "model": config.loop_model,
                        "mode": mode,
                        "search_provider": config.search_provider,
                    },
                }
            )
            orchestrator = build_orchestrator(config)
            rubric = [
                RubricCriterion(label=item.label, description=item.description)
                for item in request.rubric
            ] or _default_rubric()
            result = _run_with_optional_chunking(
                event_queue=event_queue,
                orchestrator=orchestrator,
                task=task,
                mode=mode,
                chunks=chunks,
                has_documents=bool(documents),
                fallback_task=request.task,
                rubric=rubric,
                artifact_dir=artifact_dir,
                search_query=task,
            )
        response = _to_run_response(result)
        _emit_activity(
            event_queue,
            "Finished",
            f"Final status {response.status}; score {response.final_score:.2f}; turns {response.turns_used}.",
            step=8,
            total=8,
            status="complete",
        )
        event_queue.put(
            {"event": "rsc.run.complete", "data": response.model_dump(mode="json")}
        )
    except (RuntimeError, ValueError, OSError, TypeError, json.JSONDecodeError) as exc:
        event_queue.put(
            {
                "event": "rsc.run.error",
                "data": {"error": str(exc), "error_type": exc.__class__.__name__},
            }
        )
    finally:
        logger.removeHandler(handler)
        event_queue.put(None)


def _run_with_optional_chunking(
    *,
    event_queue: queue.Queue[dict | None],
    orchestrator,
    task: str,
    mode: str,
    chunks: list[DocumentChunk],
    has_documents: bool,
    fallback_task: str,
    rubric: list[RubricCriterion],
    artifact_dir: Path,
    search_query: str,
) -> LoopResult:
    if not has_documents:
        _write_text(artifact_dir / "single-pass-task.md", fallback_task)
        return orchestrator.run(task=fallback_task, rubric=rubric, skill_name="default")

    if not chunks:
        _write_text(artifact_dir / "empty-attachment-task.md", fallback_task)
        return orchestrator.run(
            task=_empty_attachment_task(search_query, fallback_task),
            rubric=rubric,
            skill_name="default",
        )

    if getattr(orchestrator, "search_provider", None) is not None:
        orchestrator.search_provider = _ScopedSearchProvider(
            orchestrator.search_provider, search_query
        )

    chunk_summaries: list[str] = []
    total = len(chunks)
    for index, chunk in enumerate(chunks, start=1):
        chunk_dir = artifact_dir / "chunks" / f"{index:04d}-{chunk.chunk_id}"
        chunk_dir.mkdir(parents=True, exist_ok=True)
        _write_text(chunk_dir / "source.md", chunk.markdown)
        _emit_activity(
            event_queue,
            f"Verifying section {index} of {total}",
            f"{chunk.filename}: {chunk.word_count} words. Storing source and checking this section before global synthesis.",
            step=3 + min(index, 3),
            total=8,
            status="active",
            extra={"chunk_id": chunk.chunk_id, "index": index, "total": total},
        )
        event_queue.put(
            {
                "event": "chunk.verify.start",
                "data": {"chunk": chunk.summary(), "index": index, "total": total},
            }
        )
        chunk_task = _chunk_task(task, mode, chunk)
        _write_text(chunk_dir / "task.md", chunk_task)
        chunk_result = orchestrator.run(
            task=chunk_task,
            rubric=_chunk_rubric(),
            skill_name="default",
            session_id=f"chunk-{chunk.chunk_id}",
        )
        _write_text(chunk_dir / "result.md", chunk_result.final_output)
        summary = _chunk_result_summary(index, chunk, chunk_result)
        _write_text(chunk_dir / "summary.md", summary)
        _write_json(
            chunk_dir / "metadata.json",
            {
                "chunk": chunk.summary(),
                "status": chunk_result.status.value,
                "score": chunk_result.final_score,
                "turns_used": chunk_result.turns_used,
                "result_chars": len(chunk_result.final_output),
            },
        )
        chunk_summaries.append(summary)
        event_queue.put(
            {
                "event": "chunk.verify.complete",
                "data": {
                    "chunk_id": chunk.chunk_id,
                    "index": index,
                    "total": total,
                    "status": chunk_result.status.value,
                    "score": chunk_result.final_score,
                    "artifact_path": str(chunk_dir / "summary.md"),
                    "summary": _short_text(summary, 900),
                },
            }
        )

    _emit_activity(
        event_queue,
        "Synthesizing final answer",
        f"Combining {len(chunk_summaries)} verified section results into one coherent response.",
        step=7,
        total=8,
        status="active",
    )
    joined_chunk_summaries = _bounded_join(chunk_summaries, max_chars=22000)
    final_task = (
        "Mode: synthesize final answer from verified sections.\n\n"
        "# Original User Request\n"
        f"{task.strip()}\n\n"
        "# Verified Section Findings\n"
        f"{joined_chunk_summaries}\n\n"
        "# Required Final Response\n"
        "Write a coherent final answer with a concise summary, section-level findings, contradictions or gaps, and a conclusion."
    )
    _write_text(artifact_dir / "final-synthesis-task.md", final_task)
    _write_text(artifact_dir / "section-summaries.md", "\n\n".join(chunk_summaries))
    return orchestrator.run(task=final_task, rubric=rubric, skill_name="default")


def _chunk_result_summary(index: int, chunk: DocumentChunk, result: LoopResult) -> str:
    return (
        f"## Section {index}: {chunk.filename} ({chunk.chunk_id})\n"
        f"Words: {chunk.word_count}\n"
        f"Status: {result.status.value}\n"
        f"Score: {result.final_score}\n"
        f"Turns: {result.turns_used}\n\n"
        f"### Section Findings Summary\n{_short_text(result.final_output, 2600)}"
    )


def _chunk_task(task: str, mode: str, chunk: DocumentChunk) -> str:
    return (
        f"Mode: {mode}; sequential document verification.\n\n"
        "# Original User Request\n"
        f"{task.strip()}\n\n"
        f"# Document Section {chunk.index} of {chunk.total}: {chunk.filename}\n"
        f"Chunk ID: {chunk.chunk_id}\n"
        f"Words: {chunk.word_count}\n\n"
        f"{chunk.markdown}\n\n"
        "# Section Task\n"
        "Verify this section against the user request. Extract relevant findings, note conflicts, identify missing evidence, and summarize what this section contributes to the final answer."
    )


def _empty_attachment_task(task: str, fallback_task: str) -> str:
    return (
        "Mode: attachment-aware processing.\n\n"
        "The user attached one or more documents, but no extractable text was found after conversion.\n\n"
        "# Original User Request\n"
        f"{task.strip()}\n\n"
        "# Original Prepared Task Metadata\n"
        f"{_short_text(fallback_task, 3000)}"
    )


def _chunk_rubric() -> list[RubricCriterion]:
    return [
        RubricCriterion(
            label="section_findings",
            description="Extracts relevant findings from this section.",
        ),
        RubricCriterion(
            label="grounded", description="Grounds claims in the section text."
        ),
        RubricCriterion(
            label="usable_summary",
            description="Provides a usable summary for final synthesis.",
        ),
    ]


class _QueueLogHandler(logging.Handler):
    def __init__(self, event_queue: queue.Queue[dict | None]) -> None:
        super().__init__(logging.INFO)
        self.event_queue = event_queue
        self.setFormatter(JSONFormatter())

    def emit(self, record: logging.LogRecord) -> None:
        try:
            payload = json.loads(self.format(record))
            if payload.get("event") == "role.delta":
                self.event_queue.put(
                    {
                        "event": "role.delta",
                        "data": {
                            "role": payload.get("role", ""),
                            "turn": payload.get("turn", 0),
                            "sequence": payload.get("sequence", 0),
                            "delta": payload.get("delta", {}),
                            "reasoning": payload.get("reasoning", {}),
                        },
                    }
                )
            if payload.get("event") == "role.complete":
                role = payload.get("role", "")
                output = payload.get("output", {}) or {}
                reasoning = payload.get("reasoning", {}) or {}
                self.event_queue.put(
                    {
                        "event": "role.complete",
                        "data": {
                            "role": role,
                            "turn": payload.get("turn", 0),
                            "text": output.get("text", ""),
                            "chars": output.get("chars", 0),
                            "tokens_used_input": payload.get("tokens_used_input", 0),
                            "tokens_used_output": payload.get("tokens_used_output", 0),
                            "elapsed_seconds": payload.get("elapsed_seconds", 0.0),
                            "success": payload.get("success", True),
                            "reasoning_text": reasoning.get("text", ""),
                            "reasoning_chars": reasoning.get("chars", 0),
                        },
                    }
                )
                if role == "planner":
                    tasks = _planner_tasks_from_output(output.get("text", ""))
                    if tasks:
                        self.event_queue.put(
                            {
                                "event": "planner.tasks",
                                "data": {
                                    "turn": payload.get("turn", 0),
                                    "tasks": tasks,
                                },
                            }
                        )
            activity = _activity_from_log(payload)
            if activity is not None:
                self.event_queue.put(activity)
            self.event_queue.put(
                {"event": f"log.{payload.get('event', 'event')}", "data": payload}
            )
        except (TypeError, ValueError, json.JSONDecodeError):
            self.handleError(record)


def _planner_tasks_from_output(output: str) -> list[dict[str, str]]:
    if not output.strip():
        return []
    steps = _markdown_section(output, "Steps") or output
    tasks: list[dict[str, str]] = []
    for line in steps.splitlines():
        stripped = line.strip()
        match = re.match(r"^(?:\d+[.)]|[-*])\s+(?P<title>.+)$", stripped)
        if not match:
            continue
        title = re.sub(r"\s+", " ", match.group("title")).strip()
        title = re.sub(r"^\*\*|\*\*$", "", title)
        if title:
            tasks.append(
                {
                    "id": f"task-{len(tasks) + 1}",
                    "title": title,
                    "status": "pending",
                }
            )
    return tasks


def _markdown_section(markdown: str, heading: str) -> str:
    pattern = re.compile(
        rf"^##\s+{re.escape(heading)}\s*\n(?P<body>.*?)(?=^##\s+|\Z)",
        re.MULTILINE | re.DOTALL | re.IGNORECASE,
    )
    match = pattern.search(markdown)
    return match.group("body").strip() if match else ""


def _emit_activity(
    event_queue: queue.Queue[dict | None],
    title: str,
    detail: str,
    *,
    step: int,
    total: int,
    status: str,
    extra: dict | None = None,
) -> None:
    payload = {
        "title": title,
        "detail": detail,
        "step": step,
        "total": total,
        "progress": round(step / total, 4),
        "status": status,
    }
    if extra:
        payload.update(extra)
    event_queue.put({"event": "activity.update", "data": payload})


def _activity_from_log(payload: dict) -> dict | None:
    event = payload.get("event", "")
    role = payload.get("role", "")
    if event == "search.start":
        query = payload.get("query", {}).get("preview", "")
        role = payload.get("role", "")
        title = f"Searching the web ({role})" if role else "Searching the web"
        return {
            "event": "activity.update",
            "data": {
                "title": title,
                "detail": f"Query: {query}",
                "status": "active",
                "step": 3,
                "total": 8,
                "progress": 0.375,
            },
        }
    if event == "search.plan":
        role = payload.get("role", "planner")
        query_count = payload.get("query_count", 0)
        queries = payload.get("queries", [])
        detail = f"{query_count} queries planned"
        if queries:
            detail += f": {', '.join(str(q) for q in queries[:3])}"
        return {
            "event": "activity.update",
            "data": {
                "title": f"Planning search queries ({role})",
                "detail": detail,
                "status": "active",
                "step": 3,
                "total": 8,
                "progress": 0.375,
            },
        }
    if event == "search.complete":
        result_count = payload.get("result_count", 0)
        preview = payload.get("content", {}).get("preview", "")
        role = payload.get("role", "")
        title = f"Search complete ({role})" if role else "Search complete"
        return {
            "event": "activity.update",
            "data": {
                "title": title,
                "detail": f"Retrieved {result_count} search context record(s). {preview}",
                "status": "complete",
                "step": 4,
                "total": 8,
                "progress": 0.5,
            },
        }
    if event == "local_search.start":
        role = payload.get("role", "")
        return {
            "event": "activity.update",
            "data": {
                "title": f"Searching local context ({role})" if role else "Searching local context",
                "detail": "Looking for relevant content from prior chats...",
                "status": "active",
                "step": 3,
                "total": 8,
                "progress": 0.375,
                "source": "local_vector",
            },
        }
    if event == "local_search.complete":
        role = payload.get("role", "")
        result_count = payload.get("result_count", 0)
        trigger = payload.get("trigger", "")
        return {
            "event": "activity.update",
            "data": {
                "title": f"Local context retrieved ({role})" if role else "Local context retrieved",
                "detail": f"Found {result_count} relevant chunks from prior chats (triggered by: {trigger})",
                "status": "complete",
                "step": 4,
                "total": 8,
                "progress": 0.5,
                "source": "local_vector",
                "result_count": result_count,
            },
        }
    if event == "search.role_batch.complete":
        role = payload.get("role", "unknown")
        record_count = payload.get("record_count", 0)
        query_count = payload.get("query_count", 0)
        elapsed = payload.get("elapsed_seconds", 0.0)
        return {
            "event": "activity.update",
            "data": {
                "title": f"{role.title()} search complete",
                "detail": f"{record_count} results from {query_count} queries ({elapsed:.1f}s)",
                "status": "complete",
                "step": 4,
                "total": 8,
                "progress": 0.5,
            },
        }
    if event == "context.summarize":
        section = payload.get("section", "context")
        tokens_before = payload.get("tokens_before", 0)
        cache_hit = payload.get("cache_hit", False)
        if cache_hit:
            return {
                "event": "activity.update",
                "data": {
                    "title": "Context cache hit",
                    "detail": f"Using cached summary for {section}",
                    "status": "complete",
                    "step": 3,
                    "total": 8,
                    "progress": 0.375,
                },
            }
        return {
            "event": "activity.update",
            "data": {
                "title": f"Summarizing {section}",
                "detail": f"Compressing {tokens_before} tokens of {section} context to create precise and concise search context without missing key details.",
                "status": "active",
                "step": 3,
                "total": 8,
                "progress": 0.375,
            },
        }
    if event == "context.summarize.complete":
        section = payload.get("section", "context")
        tokens_before = payload.get("tokens_before", 0)
        tokens_after = payload.get("tokens_after", 0)
        return {
            "event": "activity.update",
            "data": {
                "title": f"Summarized {section}",
                "detail": f"{tokens_before} → {tokens_after} tokens",
                "status": "complete",
                "step": 3,
                "total": 8,
                "progress": 0.375,
            },
        }
    if event == "context.enforce":
        role = payload.get("role", "unknown")
        steps_fired = payload.get("steps_fired", [])
        input_before = payload.get("input_tokens_before", 0)
        input_after = payload.get("input_tokens_after", 0)
        exhausted = payload.get("exhausted", False)
        if exhausted:
            return None  # context.exhausted handles this
        detail = f"Compressed {input_before} → {input_after} tokens"
        if steps_fired:
            detail += f" ({', '.join(steps_fired)})"
        return {
            "event": "activity.update",
            "data": {
                "title": f"Compressing context ({role})",
                "detail": detail,
                "status": "complete",
                "step": 3,
                "total": 8,
                "progress": 0.375,
            },
        }
    if event == "context.exhausted":
        role = payload.get("role", "unknown")
        input_after = payload.get("input_tokens_after_all_steps", 0)
        budget = payload.get("input_budget", 0)
        return {
            "event": "activity.update",
            "data": {
                "title": f"Context exhausted ({role})",
                "detail": f"Still {input_after} tokens after all compression (budget: {budget})",
                "status": "error",
                "step": 3,
                "total": 8,
                "progress": 0.375,
            },
        }
    if event == "skill.selected":
        return {
            "event": "activity.update",
            "data": {
                "title": "Selected skill context",
                "detail": f"{payload.get('skill_id')} ({payload.get('readiness')}) score {payload.get('score')}",
                "status": "complete",
                "step": 4,
                "total": 8,
                "progress": 0.5,
            },
        }
    if event == "search.query_generation.start":
        model = payload.get("model", "")
        return {
            "event": "activity.update",
            "data": {
                "title": "Generating search queries",
                "detail": f"Asking {model} to plan search queries...",
                "status": "active",
                "step": 3,
                "total": 8,
                "progress": 0.375,
            },
        }
    if event == "search.query_generation.complete":
        query_count = payload.get("query_count", 0)
        elapsed = payload.get("elapsed_seconds", 0.0)
        return {
            "event": "activity.update",
            "data": {
                "title": "Search queries generated",
                "detail": f"{query_count} queries ready ({elapsed:.1f}s)",
                "status": "complete",
                "step": 3,
                "total": 8,
                "progress": 0.375,
            },
        }
    if event == "evaluator.start":
        model = payload.get("model", "")
        turn = payload.get("turn", 0)
        return {
            "event": "activity.update",
            "data": {
                "title": f"Evaluating response (turn {turn})",
                "detail": f"Grading output with {model}...",
                "status": "active",
                "step": 7,
                "total": 8,
                "progress": 0.875,
            },
        }
    if event == "search_inference.start":
        trigger = payload.get("trigger", "")
        return {
            "event": "activity.update",
            "data": {
                "title": "Running search-over-inference",
                "detail": f"Retrying with search context (triggered by: {trigger})",
                "status": "active",
                "step": 5,
                "total": 8,
                "progress": 0.625,
            },
        }
    if event == "memory.distill.start":
        model = payload.get("model", "")
        turn_count = payload.get("turn_count", 0)
        return {
            "event": "activity.update",
            "data": {
                "title": "Distilling lessons learned",
                "detail": f"Extracting reusable knowledge from {turn_count} turns...",
                "status": "active",
                "step": 8,
                "total": 8,
                "progress": 0.95,
            },
        }
    if event == "role.start":
        return {
            "event": "activity.update",
            "data": {
                "title": f"{str(role).title()} is working",
                "detail": _role_start_detail(payload),
                "status": "active",
                "step": _role_step(role),
                "total": 8,
                "progress": _role_step(role) / 8,
            },
        }
    if event == "role.complete":
        output = payload.get("output", {})
        return {
            "event": "activity.update",
            "data": {
                "title": f"{str(role).title()} response",
                "detail": output.get("preview", ""),
                "status": "complete",
                "step": _role_step(role),
                "total": 8,
                "progress": _role_step(role) / 8,
                "chars": output.get("chars", 0),
            },
        }
    if event == "evaluator.complete":
        return {
            "event": "activity.update",
            "data": {
                "title": "Evaluation complete",
                "detail": f"Passed={payload.get('passed')} score={payload.get('score')}",
                "status": "complete",
                "step": 7,
                "total": 8,
                "progress": 0.875,
            },
        }
    if event == "session.complete":
        return {
            "event": "activity.update",
            "data": {
                "title": "Run complete",
                "detail": f"Status {payload.get('status')} with score {payload.get('final_score')}",
                "status": "complete",
                "step": 8,
                "total": 8,
                "progress": 1.0,
            },
        }
    return None


def _role_step(role: str) -> int:
    return {
        "planner": 4,
        "critic": 5,
        "verifier": 5,
        "reviser": 6,
        "synthesizer": 7,
    }.get(role, 4)


def _role_start_detail(payload: dict) -> str:
    tokens = payload.get("estimated_input_tokens", 0)
    selected = payload.get("selected_skill_ids", [])
    search_count = payload.get("search_result_count", 0)
    return f"Input estimate {tokens} tokens; skills {selected or 'default'}; search records {search_count}."


def _decomposition_detail(chunks: list[DocumentChunk]) -> str:
    if not chunks:
        return (
            "No attachments to decompose; using the question and live search context."
        )
    if len(chunks) == 1:
        return f"1 document section prepared ({chunks[0].word_count} words)."
    return f"{len(chunks)} document sections prepared for sequential verification."


def _short_text(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    return f"{text[:limit]}..."


def _bounded_join(items: list[str], max_chars: int) -> str:
    selected: list[str] = []
    total = 0
    omitted = 0
    for item in items:
        addition = len(item) + 2
        if selected and total + addition > max_chars:
            omitted += 1
            continue
        selected.append(item)
        total += addition
    if omitted:
        selected.append(
            f"\n\n## Omitted Section Summaries\n{omitted} section summaries were stored as artifacts but omitted from this final prompt budget."
        )
    return "\n\n".join(selected)


class _ScopedSearchProvider:
    def __init__(self, inner, query: str) -> None:
        self.inner = inner
        self.query = query
        self.name = f"{getattr(inner, 'name', inner.__class__.__name__)}-scoped"
        self._cache: dict[str, str] = {}

    def search(self, query: str, *, max_results: int = 5) -> str:
        selected_query = query if len(query) <= 500 else self.query
        if selected_query not in self._cache:
            self._cache[selected_query] = self.inner.search(
                selected_query, max_results=max_results
            )
        return self._cache[selected_query]


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8"
    )


def _compose_task(task: str, mode: str, attachment_context: str) -> str:
    mode_instruction = {
        "answer": "Mode: answer the question directly and clearly.",
        "research": "Mode: synthesize a research-grade answer using search and attachments.",
        "write": "Mode: produce polished prose using the attached source context.",
        "code": "Mode: reason as an implementation task with explicit verification.",
    }.get(mode, f"Mode: {mode}")
    parts = [mode_instruction, "", "# User Question", task.strip()]
    if attachment_context:
        parts.extend(["", attachment_context])
    return "\n".join(parts)


def _rubric_items_from_json(raw: str) -> list[RubricItemRequest]:
    if not raw.strip():
        return []
    data = json.loads(raw)
    if not isinstance(data, list):
        raise ValueError("rubric_json must be a JSON list")
    return [RubricItemRequest.model_validate(item) for item in data]


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, default=str)}\n\n"


def _to_run_response(result: LoopResult | RunResponse | dict) -> RunResponse:
    if isinstance(result, RunResponse):
        return result
    if isinstance(result, dict):
        return RunResponse.model_validate(result)
    return RunResponse(
        session_id=result.session_id,
        status=result.status.value,
        final_score=result.final_score,
        turns_used=result.turns_used,
        final_output=result.final_output,
        total_tokens_input=result.total_tokens_input,
        total_tokens_output=result.total_tokens_output,
        memory_rules_added=result.memory_rules_added,
        turns=[turn.model_dump(mode="json") for turn in result.turns],
    )


def _missing_ui_html() -> str:
    return """
<!doctype html>
<html lang="en">
  <head><meta charset="utf-8"><title>RSC UI</title></head>
  <body>
    <main style="font-family: system-ui; max-width: 720px; margin: 4rem auto; line-height: 1.5;">
      <h1>RSC UI is not built yet</h1>
      <p>Run <code>npm install</code> and <code>npm run build</code> in the <code>ui</code> folder, then restart FastAPI.</p>
    </main>
  </body>
</html>
""".strip()


app = create_app()
