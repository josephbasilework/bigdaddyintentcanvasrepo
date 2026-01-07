"""Agent module for IntentUI.

All agents inherit from BaseAgent and use Gateway for LLM calls.
"""

from app.agents.base import AgentError, BaseAgent
from app.agents.echo_agent import EchoAgent, EchoResponse

__all__ = ["BaseAgent", "AgentError", "EchoAgent", "EchoResponse"]
