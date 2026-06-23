from __future__ import annotations

import hashlib
import math
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping

import yaml
from pydantic import BaseModel, ConfigDict, Field

from .contracts import SelectedSkill, SkillReadiness
from .retry import retry_call

TOKEN_RE = re.compile(r"[A-Za-z0-9_./+-]+")
REFERENCE_RE = re.compile(r"\[[^\]]+\]\((?P<target>[^)]+)\)")


CAPABILITY_KEYWORDS: dict[str, tuple[str, ...]] = {
    "web_search": ("web search", "browser", "crawl", "scrape", "search result"),
    "shell": ("shell", "terminal", "cli", "command line", "subprocess"),
    "python": ("python", "pytest", "pip", "pydantic"),
    "node": ("node", "npm", "javascript", "typescript"),
    "office": ("docx", "pptx", "xlsx", "pdf", "office", "pandoc", "soffice"),
    "external_connector": ("connector", "salesforce", "slack", "github api"),
    "credentials": ("api key", "credential", "oauth", "token", "secret"),
    "human_approval": ("human approval", "approval", "confirm before"),
    "private_data": ("private data", "personal data", "phi", "pii"),
    "schema_contract": ("schema", "json schema", "contract"),
    "state_persistence": ("state", "persistence", "cache", "sqlite"),
    "template_renderer": ("template", "render", "jinja"),
    "qa_required": ("test", "qa", "validate", "verification"),
}

BLOCKING_CAPABILITIES = {"credentials", "human_approval", "private_data"}


class SkillDocument(BaseModel):
    model_config = ConfigDict(extra="forbid")
    skill_id: str
    name: str
    path: str
    relative_path: str
    family: str
    front_matter: dict[str, Any] = Field(default_factory=dict)
    content: str = ""
    checksum: str
    tags: list[str] = Field(default_factory=list)
    dependencies: list[str] = Field(default_factory=list)
    references: list[str] = Field(default_factory=list)

    @property
    def search_text(self) -> str:
        front_matter_text = " ".join(
            str(value) for value in self.front_matter.values() if value is not None
        )
        return " ".join(
            [
                self.skill_id,
                self.name,
                self.family,
                " ".join(self.tags),
                " ".join(self.dependencies),
                front_matter_text,
                self.content,
            ]
        )


@dataclass(frozen=True)
class CapabilityReport:
    readiness: SkillReadiness
    required: tuple[str, ...] = ()
    available: tuple[str, ...] = ()
    missing: tuple[str, ...] = ()
    degraded: tuple[str, ...] = ()


@dataclass(frozen=True)
class LoadedReference:
    path: str
    checksum: str
    content: str


@dataclass
class SkillRouteResult:
    selected: list[SelectedSkill]
    discovered_count: int
    routed_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class SkillDiscovery:
    def __init__(self, roots: Iterable[str | Path]) -> None:
        self.roots = [Path(root).expanduser() for root in roots]

    def discover(self) -> list[SkillDocument]:
        documents: list[SkillDocument] = []
        seen: set[str] = set()
        for root in self.roots:
            if not root.exists():
                continue
            skill_files = [root] if root.name == "SKILL.md" else root.rglob("SKILL.md")
            for skill_file in sorted(skill_files):
                resolved = str(skill_file.resolve())
                if resolved in seen:
                    continue
                seen.add(resolved)
                documents.append(self._load_document(root, skill_file))
        return documents

    def _load_document(self, root: Path, skill_file: Path) -> SkillDocument:
        raw = skill_file.read_text(encoding="utf-8")
        front_matter, content = _parse_front_matter(raw)
        relative = _relative_skill_path(root, skill_file)
        skill_id = relative.removesuffix("/SKILL.md").replace("/", ".")
        if skill_id == "SKILL.md":
            skill_id = skill_file.parent.name
        title = _first_markdown_heading(content) or str(
            front_matter.get("name", skill_id)
        )
        dependencies = _string_list(front_matter.get("dependencies"))
        dependencies.extend(_infer_dependencies(content))
        references = _string_list(front_matter.get("references"))
        references.extend(_extract_reference_links(content))
        return SkillDocument(
            skill_id=skill_id,
            name=title,
            path=str(skill_file),
            relative_path=relative,
            family=skill_id.split(".", 1)[0],
            front_matter=front_matter,
            content=content.strip(),
            checksum=hashlib.sha256(raw.encode("utf-8")).hexdigest(),
            tags=_string_list(front_matter.get("tags")),
            dependencies=sorted(set(dependencies)),
            references=sorted(set(references)),
        )


class CapabilityBroker:
    def __init__(self, available: Iterable[str] | None = None) -> None:
        self.available = set(available or default_capabilities())

    def resolve(self, skill: SkillDocument) -> CapabilityReport:
        required = set(skill.dependencies) | set(_infer_dependencies(skill.search_text))
        missing = sorted(required - self.available)
        blocked = sorted(set(missing) & BLOCKING_CAPABILITIES)
        degraded = [capability for capability in missing if capability not in blocked]
        if blocked:
            readiness = SkillReadiness.BLOCKED
        elif degraded:
            readiness = SkillReadiness.DEGRADED
        else:
            readiness = SkillReadiness.READY
        return CapabilityReport(
            readiness=readiness,
            required=tuple(sorted(required)),
            available=tuple(sorted(required & self.available)),
            missing=tuple(missing),
            degraded=tuple(degraded),
        )


class ReferenceLoader:
    def __init__(self, max_reference_chars: int = 4000) -> None:
        self.max_reference_chars = max_reference_chars

    def load(self, skill: SkillDocument) -> list[LoadedReference]:
        base = Path(skill.path).parent
        loaded: list[LoadedReference] = []
        for raw_reference in skill.references:
            reference = raw_reference.split("#", 1)[0].strip()
            if not reference or "://" in reference:
                continue
            path = (base / reference).resolve()
            try:
                path.relative_to(base.resolve())
            except ValueError:
                continue
            if not path.exists() or not path.is_file():
                continue
            content = path.read_text(encoding="utf-8", errors="replace")
            loaded.append(
                LoadedReference(
                    path=str(path),
                    checksum=hashlib.sha256(content.encode("utf-8")).hexdigest(),
                    content=content[: self.max_reference_chars],
                )
            )
        return loaded


class HybridSkillRouter:
    def __init__(
        self,
        skills: list[SkillDocument],
        *,
        capability_broker: CapabilityBroker | None = None,
        reference_loader: ReferenceLoader | None = None,
        embedding_client=None,
        embedding_model: str = "text-embedding-3-large",
        semantic_weight: float = 0.55,
        lexical_weight: float = 0.35,
        vector_size: int = 2048,
    ) -> None:
        self.skills = skills
        self.capability_broker = capability_broker or CapabilityBroker()
        self.reference_loader = reference_loader or ReferenceLoader()
        self.embedding_client = embedding_client
        self.embedding_model = embedding_model
        self.semantic_weight = semantic_weight
        self.lexical_weight = lexical_weight
        self.vector_size = vector_size
        self._skill_lexical_vectors = [
            hashing_vectorize(skill.search_text, vector_size) for skill in skills
        ]
        self._skill_embeddings = self._embed_many(
            [skill.search_text for skill in skills]
        )

    def route(self, task: str, *, top_k: int = 3) -> SkillRouteResult:
        query_vector = hashing_vectorize(task, self.vector_size)
        query_embedding = self._embed_one(task)
        ranked: list[tuple[float, SelectedSkill]] = []
        for index, skill in enumerate(self.skills):
            lexical = cosine_similarity(
                query_vector, self._skill_lexical_vectors[index]
            )
            semantic = (
                cosine_similarity(query_embedding, self._skill_embeddings[index])
                if query_embedding
                else 0.0
            )
            exact_bonus = _exact_match_bonus(task, skill)
            report = self.capability_broker.resolve(skill)
            readiness_bonus = {
                SkillReadiness.READY: 0.08,
                SkillReadiness.DEGRADED: -0.08,
                SkillReadiness.BLOCKED: -0.3,
            }[report.readiness]
            score = max(
                0.0,
                self.semantic_weight * semantic
                + self.lexical_weight * lexical
                + exact_bonus
                + readiness_bonus,
            )
            references = self.reference_loader.load(skill)[:3]
            reason = _selection_reason(skill, lexical, semantic, report)
            selected = SelectedSkill(
                skill_id=skill.skill_id,
                name=skill.name,
                score=round(score, 4),
                semantic_score=round(semantic, 4),
                lexical_score=round(lexical, 4),
                readiness=report.readiness,
                reason=reason,
                source_file=skill.path,
                content_excerpt=_excerpt(skill.content, references),
                references_loaded=[reference.path for reference in references],
                missing_capabilities=list(report.missing),
                degraded_capabilities=list(report.degraded),
            )
            ranked.append((score, selected))
        ranked.sort(key=lambda item: item[0], reverse=True)
        return SkillRouteResult(
            selected=[selected for _, selected in ranked[: max(1, top_k)]],
            discovered_count=len(self.skills),
        )

    def _embed_many(self, texts: list[str]) -> list[list[float]]:
        if self.embedding_client is None or not texts:
            return [[] for _ in texts]
        try:
            response = retry_call(
                lambda: self.embedding_client.embeddings.create(
                    model=self.embedding_model,
                    input=texts,
                )
            )
        except (AttributeError, RuntimeError, TypeError, ValueError):
            return [[] for _ in texts]
        return [list(item.embedding) for item in response.data]

    def _embed_one(self, text: str) -> list[float]:
        if self.embedding_client is None:
            return []
        try:
            response = retry_call(
                lambda: self.embedding_client.embeddings.create(
                    model=self.embedding_model,
                    input=[text],
                )
            )
        except (AttributeError, RuntimeError, TypeError, ValueError):
            return []
        return list(response.data[0].embedding) if response.data else []


def build_skill_router(
    roots: Iterable[str | Path],
    *,
    available_capabilities: Iterable[str] | None = None,
    embedding_client=None,
    embedding_model: str = "text-embedding-3-large",
) -> HybridSkillRouter | None:
    documents = SkillDiscovery(roots).discover()
    if not documents:
        return None
    return HybridSkillRouter(
        documents,
        capability_broker=CapabilityBroker(available_capabilities),
        embedding_client=embedding_client,
        embedding_model=embedding_model,
    )


def default_capabilities() -> set[str]:
    return {
        "file_read",
        "python",
        "qa_required",
        "schema_contract",
        "shell",
        "state_persistence",
        "template_renderer",
        "web_search",
    }


def capabilities_from_config(config) -> set[str]:
    capabilities = default_capabilities()
    if getattr(config, "search_provider", "none") == "none":
        capabilities.discard("web_search")
    return capabilities


def hashing_vectorize(text: str, vector_size: int = 2048) -> dict[int, float]:
    vector: dict[int, float] = {}
    for token in _tokens(text):
        digest = hashlib.blake2b(token.encode("utf-8"), digest_size=8).digest()
        bucket = int.from_bytes(digest, "big") % vector_size
        vector[bucket] = vector.get(bucket, 0.0) + 1.0
    return vector


def cosine_similarity(
    left: Mapping[int, float] | list[float], right: Mapping[int, float] | list[float]
) -> float:
    if not left or not right:
        return 0.0
    if isinstance(left, Mapping) and isinstance(right, Mapping):
        shared = set(left) & set(right)
        dot = sum(left[key] * right[key] for key in shared)
        left_norm = math.sqrt(sum(value * value for value in left.values()))
        right_norm = math.sqrt(sum(value * value for value in right.values()))
    else:
        left_list = list(left)  # type: ignore[arg-type]
        right_list = list(right)  # type: ignore[arg-type]
        length = min(len(left_list), len(right_list))
        dot = sum(left_list[index] * right_list[index] for index in range(length))
        left_norm = math.sqrt(sum(value * value for value in left_list))
        right_norm = math.sqrt(sum(value * value for value in right_list))
    if left_norm == 0.0 or right_norm == 0.0:
        return 0.0
    return dot / (left_norm * right_norm)


def _parse_front_matter(text: str) -> tuple[dict[str, Any], str]:
    if not text.startswith("---"):
        return {}, text
    parts = text.split("---", 2)
    if len(parts) < 3:
        return {}, text
    parsed = yaml.safe_load(parts[1]) or {}
    return (parsed if isinstance(parsed, dict) else {}), parts[2]


def _relative_skill_path(root: Path, skill_file: Path) -> str:
    try:
        return skill_file.relative_to(root).as_posix()
    except ValueError:
        return skill_file.name


def _first_markdown_heading(content: str) -> str | None:
    for line in content.splitlines():
        stripped = line.strip()
        if stripped.startswith("# "):
            return stripped[2:].strip()
    return None


def _string_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, Iterable):
        return [str(item) for item in value if item]
    return [str(value)]


def _extract_reference_links(content: str) -> list[str]:
    return [match.group("target") for match in REFERENCE_RE.finditer(content)]


def _infer_dependencies(text: str) -> list[str]:
    lowered = text.lower()
    inferred = []
    for capability, keywords in CAPABILITY_KEYWORDS.items():
        if any(keyword in lowered for keyword in keywords):
            inferred.append(capability)
    return inferred


def _tokens(text: str) -> list[str]:
    return [match.group(0).lower() for match in TOKEN_RE.finditer(text)]


def _exact_match_bonus(task: str, skill: SkillDocument) -> float:
    task_tokens = set(_tokens(task))
    if not task_tokens:
        return 0.0
    skill_terms = set(_tokens(skill.skill_id.replace(".", " "))) | set(
        _tokens(skill.name)
    )
    overlap = task_tokens & skill_terms
    return min(0.12, 0.03 * len(overlap))


def _selection_reason(
    skill: SkillDocument,
    lexical: float,
    semantic: float,
    report: CapabilityReport,
) -> str:
    status = report.readiness.value
    signals = []
    if lexical > 0.0:
        signals.append("lexical match")
    if semantic > 0.0:
        signals.append("semantic match")
    if not signals:
        signals.append("fallback ranking")
    if report.missing:
        signals.append(f"missing {', '.join(report.missing)}")
    return f"{skill.skill_id} selected by {', '.join(signals)}; readiness={status}."


def _excerpt(content: str, references: list[LoadedReference]) -> str:
    parts = [content.strip()[:1400]]
    for reference in references:
        parts.append(
            f"Reference {Path(reference.path).name}:\n{reference.content[:800]}"
        )
    return "\n\n".join(part for part in parts if part).strip()
