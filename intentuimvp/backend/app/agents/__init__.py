"""Agent module for IntentUI.

All agents inherit from BaseAgent and use Gateway for LLM calls.
"""

from app.agents.base import AgentError, BaseAgent

__all__ = ["BaseAgent", "AgentError"]
