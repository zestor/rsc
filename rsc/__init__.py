"""Recursive Scaffolded Cognition (RSC) public API."""

from .artifact_protocol import ArtifactParser
from .config import RSCConfig
from .context_manager import ContextManager
from .contracts import (
    ArtifactRecord,
    ArtifactState,
    ClaudeState,
    ComposedState,
    EvalVerdict,
    LoopResult,
    LoopStatus,
    LoopTurnRecord,
    MemoryEntry,
    MemoryStage,
    MemoryState,
    RoleInput,
    RoleOutput,
    RoleType,
    RubricCriterion,
    SkillState,
    SearchRecord,
    SelectedSkill,
    SkillReadiness,
)
from .evaluator import Evaluator
from .exceptions import ArtifactParseError, ConfigurationError, StateLoadError
from .loop_orchestrator import LoopOrchestrator
from .openai_responses_adapter import OpenAIResponsesClientAdapter
from .openrouter_adapter import OpenRouterClientAdapter, openrouter_provider_options
from .prompt_assembler import ROLE_SECTIONS, PromptAssembler
from .role_agent import RoleAgent
from .role_search_planner import (
    ROLE_SEARCH_LENSES,
    RoleSearchPlanner,
    planner_should_search,
)
from .search_inference import SearchOverInference
from .search_provider import (
    FirecrawlSearchProvider,
    FunctionSearchProvider,
    HTTPMarkdownSearchProvider,
    SearchProvider,
    SearchProviderError,
)
from .skill_runtime import (
    CapabilityBroker,
    HybridSkillRouter,
    ReferenceLoader,
    SkillDiscovery,
    build_skill_router,
)
from .state_loader import StateLoader
from .state_manager import StateManager
from .web_api import create_app

__all__ = [
    "RoleType",
    "MemoryStage",
    "LoopStatus",
    "RubricCriterion",
    "ClaudeState",
    "MemoryState",
    "SkillState",
    "ArtifactRecord",
    "ArtifactState",
    "ComposedState",
    "RoleInput",
    "RoleOutput",
    "EvalVerdict",
    "LoopTurnRecord",
    "LoopResult",
    "MemoryEntry",
    "SearchRecord",
    "SelectedSkill",
    "SkillReadiness",
    "StateLoadError",
    "ArtifactParseError",
    "ConfigurationError",
    "StateLoader",
    "StateManager",
    "PromptAssembler",
    "ArtifactParser",
    "RoleAgent",
    "Evaluator",
    "SearchOverInference",
    "LoopOrchestrator",
    "OpenAIResponsesClientAdapter",
    "OpenRouterClientAdapter",
    "openrouter_provider_options",
    "SearchProvider",
    "FirecrawlSearchProvider",
    "FunctionSearchProvider",
    "HTTPMarkdownSearchProvider",
    "SearchProviderError",
    "CapabilityBroker",
    "HybridSkillRouter",
    "ReferenceLoader",
    "SkillDiscovery",
    "build_skill_router",
    "create_app",
]
