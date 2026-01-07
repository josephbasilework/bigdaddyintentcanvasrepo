"""Agent module for IntentUI.

All agents inherit from BaseAgent and use Gateway for LLM calls.
"""

from app.agents.base import AgentError, BaseAgent
from app.agents.echo_agent import EchoAgent, EchoResponse
from app.agents.intent_decipherer import IntentDeciphererAgent, get_intent_decipherer
from app.agents.orchestrator import (
    AgentMetadata,
    AgentOrchestrator,
    AgentRegistry,
    WorkflowStep,
    get_orchestrator,
    get_registry,
)
from app.agents.perspective_agent import PerspectiveAgent, get_perspective_agent
from app.agents.research_agent import ResearchAgent, ResearchConfig, get_research_agent
from app.agents.safety import (
    ActionCategory,
    ActionRiskLevel,
    SafetyCheckResult,
    SafetyGuardrails,
    get_safety,
)
from app.agents.synthesis_agent import (
    SynthesisAgent,
    SynthesisConfig,
    SynthesisInput,
    SynthesisResult,
    get_synthesis_agent,
)
from app.agents.tools import (
    ToolExecutionResult,
    ToolManager,
    ToolRecommendation,
    call_tool,
    get_tool_manager,
)

__all__ = [
    # Core
    "BaseAgent",
    "AgentError",
    # Echo agent
    "EchoAgent",
    "EchoResponse",
    # Intent Decipherer
    "IntentDeciphererAgent",
    "get_intent_decipherer",
    # Orchestrator
    "AgentMetadata",
    "AgentOrchestrator",
    "AgentRegistry",
    "WorkflowStep",
    "get_orchestrator",
    "get_registry",
    # Safety
    "ActionCategory",
    "ActionRiskLevel",
    "SafetyCheckResult",
    "SafetyGuardrails",
    "get_safety",
    # Tools
    "ToolExecutionResult",
    "ToolManager",
    "ToolRecommendation",
    "call_tool",
    "get_tool_manager",
    # Research Agent
    "ResearchAgent",
    "ResearchConfig",
    "get_research_agent",
    # Perspective Agent
    "PerspectiveAgent",
    "get_perspective_agent",
    # Synthesis Agent
    "SynthesisAgent",
    "SynthesisConfig",
    "SynthesisInput",
    "SynthesisResult",
    "get_synthesis_agent",
]
