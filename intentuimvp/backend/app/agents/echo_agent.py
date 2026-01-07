"""Simple echo agent for vertical slice testing.

This agent proves the end-to-end flow from input through Gateway
to structured output. It echoes back the user's input with metadata.
"""

import logging
from datetime import UTC, datetime

from pydantic import BaseModel

from app.agents.base import AgentError, BaseAgent

logger = logging.getLogger(__name__)


class EchoResponse(BaseModel):
    """Structured response model for EchoAgent.

    Attributes:
        original: The original user input text.
        echo: The echoed response from the agent.
        timestamp: When the response was generated (UTC).
    """

    original: str
    echo: str
    timestamp: datetime


class EchoAgent(BaseAgent):
    """Simple echo agent that repeats user input through the Gateway.

    This agent serves as a minimal working example proving that:
    - BaseAgent can be extended
    - Gateway calls work end-to-end
    - Structured outputs are properly validated

    Example:
        agent = EchoAgent()
        response = await agent.run({"prompt": "Hello, world!"})
        # Returns: {"original": "Hello, world!", "echo": "...", "timestamp": ...}
    """

    async def run(self, input_data: dict) -> dict:
        """Run the echo agent with the given input.

        Args:
            input_data: Must contain 'prompt' key with user text.

        Returns:
            Dictionary with 'original', 'echo', and 'timestamp' keys.

        Raises:
            AgentError: If Gateway call fails and fallback is unavailable.
        """
        prompt = input_data.get("prompt", "")
        if not isinstance(prompt, str):
            prompt = str(prompt)

        messages = [
            {
                "role": "system",
                "content": "You are an echo agent. Your job is to repeat back "
                "whatever the user says, exactly as they said it. Return a JSON "
                "object with 'original' (the input), 'echo' (same as original), "
                "and 'timestamp' (ISO 8601 format).",
            },
            {"role": "user", "content": prompt},
        ]

        try:
            response = await self.generate_structured(
                messages=messages,
                response_model=EchoResponse,
            )

            logger.info("EchoAgent succeeded", extra={"prompt_length": len(prompt)})

            return {
                "original": response.original,
                "echo": response.echo,
                "timestamp": response.timestamp.isoformat(),
            }

        except AgentError:
            logger.warning("Gateway call failed, using fallback", exc_info=True)

            # Fallback: simple local echo without Gateway
            return {
                "original": prompt,
                "echo": f"[fallback] {prompt}",
                "timestamp": datetime.now(UTC).isoformat(),
            }
