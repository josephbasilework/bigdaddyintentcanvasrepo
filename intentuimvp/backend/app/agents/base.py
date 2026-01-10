"""Base class for all PydanticAI agents.

All agents MUST inherit from BaseAgent and use self.gateway for LLM calls.
Direct provider SDK imports (OpenAI, Anthropic, etc.) are PROHIBITED.
"""

import json
import logging
from abc import ABC, abstractmethod
from typing import Any, TypeVar

from pydantic import BaseModel, ValidationError

from app.gateway.client import GatewayClient, GatewayClientError

logger = logging.getLogger(__name__)

# Generic type for Pydantic response models
T = TypeVar("T", bound=BaseModel)


class AgentError(Exception):
    """Base exception for agent errors."""

    pass


class BaseAgent(ABC):
    """Base class for all PydanticAI agents.

    Enforces Gateway-only pattern and provides structured output validation.

    Subclasses MUST:
    - Override the run() method
    - Use self.gateway for all LLM calls (never direct provider SDKs)
    - Define response models using Pydantic for structured output
    """

    def __init__(
        self,
        gateway: GatewayClient | None = None,
        model: str = "openai/gpt-4o",
        temperature: float = 0.7,
    ) -> None:
        """Initialize the agent.

        Args:
            gateway: Gateway client instance. If None, uses singleton.
            model: Model identifier for Gateway (e.g., "openai/gpt-4o").
            temperature: Sampling temperature (0.0 to 1.0).
        """
        if gateway is None:
            from app.gateway.client import get_gateway_client

            gateway = get_gateway_client()

        self.gateway = gateway
        self.model = model
        self.temperature = temperature

    @abstractmethod
    async def run(self, input_data: dict[str, Any]) -> dict[str, Any]:
        """Run the agent with the given input.

        Subclasses MUST implement this method to define agent behavior.

        Args:
            input_data: Input data for the agent (prompt, context, etc.).

        Returns:
            Agent output as a dictionary. Should be serializable.

        Raises:
            AgentError: If agent execution fails.
        """
        pass

    async def generate(
        self,
        messages: list[dict[str, Any]],
        model: str | None = None,
        temperature: float | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Generate a completion via the Gateway.

        Convenience method for subclasses to call the Gateway.

        Args:
            messages: Chat messages in OpenAI format.
            model: Override model. Defaults to self.model.
            temperature: Override temperature. Defaults to self.temperature.
            **kwargs: Additional Gateway parameters.

        Returns:
            Response JSON from the Gateway.

        Raises:
            AgentError: If Gateway request fails.
        """
        try:
            response = await self.gateway.generate(
                model=model or self.model,
                messages=messages,
                temperature=temperature or self.temperature,
                **kwargs,
            )
            return response

        except GatewayClientError as e:
            logger.error("Gateway request failed", exc_info=True)
            raise AgentError(f"Agent execution failed: {e}") from e

    async def generate_structured(
        self,
        messages: list[dict[str, Any]],
        response_model: type[T],
        **kwargs: Any,
    ) -> T:
        """Generate a structured response validated against a Pydantic model.

        Args:
            messages: Chat messages in OpenAI format.
            response_model: Pydantic model class for response validation.
            **kwargs: Additional Gateway parameters.

        Returns:
            Validated instance of response_model.

        Raises:
            AgentError: If generation or validation fails.
        """
        response = await self.generate(messages, **kwargs)

        # Extract content from Gateway response
        # Gateway returns OpenAI-compatible format
        try:
            content = response["choices"][0]["message"]["content"]
        except (KeyError, IndexError) as e:
            logger.error("Unexpected Gateway response format", extra={"response": response})
            raise AgentError(f"Invalid Gateway response format: {e}") from e

        # Parse and validate against response model
        try:
            # Assuming Gateway returns JSON in content
            parsed = json.loads(content)
            return response_model.model_validate(parsed)

        except (json.JSONDecodeError, ValidationError) as e:
            logger.error(
                "Failed to validate structured response",
                extra={"content": content[:200]},  # Truncate for logging
            )
            raise AgentError(f"Structured response validation failed: {e}") from e
