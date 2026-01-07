"""Intent Deciphering Agent for extracting and validating user assumptions.

This agent analyzes user input to extract:
- Structured assumptions that need confirmation
- Intent classification with confidence scores
- Multi-intent decomposition for complex requests
- Parameter extraction for action execution
"""

import logging
import uuid
from typing import Any

from pydantic import BaseModel, Field

from app.agents.base import BaseAgent
from app.context.models import Assumption, AssumptionCategory

logger = logging.getLogger(__name__)


# Request/Response models for Intent Deciphering
class IntentClassification(BaseModel):
    """Classified intent with confidence score."""

    name: str = Field(description="Name of the intent (e.g., 'research', 'create', 'analyze')")
    confidence: float = Field(ge=0.0, le=1.0, description="Confidence score for this intent")
    description: str = Field(description="Human-readable description of the intent")


class ExtractedParameter(BaseModel):
    """A parameter extracted from user input."""

    name: str = Field(description="Parameter name")
    value: str = Field(description="Extracted or inferred value")
    confidence: float = Field(ge=0.0, le=1.0, description="Confidence in this extraction")
    source: str = Field(description="Where this value came from (explicit, inferred, default)")


class SubIntent(BaseModel):
    """A decomposed sub-intent from a complex request."""

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    description: str = Field(description="Description of this sub-intent")
    intent_type: str = Field(description="Type of this sub-intent")
    dependencies: list[str] = Field(default_factory=list, description="IDs of dependent sub-intents")
    confidence: float = Field(ge=0.0, le=1.0)


class IntentDecipheringResult(BaseModel):
    """Result from intent deciphering agent."""

    primary_intent: IntentClassification
    alternative_intents: list[IntentClassification] = Field(default_factory=list)
    assumptions: list[dict] = Field(default_factory=list)
    parameters: list[dict] = Field(default_factory=list)
    sub_intents: list[dict] = Field(default_factory=list)
    should_auto_execute: bool = Field(
        description="Whether to auto-execute based on confidence threshold"
    )
    reasoning: str = Field(description="Explanation of the deciphering process")


class IntentDeciphererAgent(BaseAgent):
    """Agent for deciphering user intent and extracting assumptions.

    This agent uses the Gateway to analyze user input and extract:
    - Primary intent classification
    - Assumptions that need user confirmation
    - Parameters for execution
    - Sub-intents for complex workflows
    - Recommendation on auto-execution

    Usage:
        agent = IntentDeciphererAgent()
        result = await agent.decipher("Create a chart showing sales data")
    """

    DEFAULT_CONFIDENCE_THRESHOLD = 0.8

    def __init__(
        self,
        gateway: Any | None = None,
        model: str = "openai/gpt-4o",
        temperature: float = 0.3,  # Lower temperature for more consistent classification
        confidence_threshold: float = DEFAULT_CONFIDENCE_THRESHOLD,
    ) -> None:
        """Initialize the Intent Decipherer Agent.

        Args:
            gateway: Gateway client instance. If None, uses singleton.
            model: Model identifier for Gateway.
            temperature: Sampling temperature (lower for more deterministic classification).
            confidence_threshold: Threshold for auto-execution recommendation.
        """
        super().__init__(gateway=gateway, model=model, temperature=temperature)
        self.confidence_threshold = confidence_threshold

    async def run(self, input_data: dict[str, Any]) -> dict[str, Any]:
        """Run the agent with the given input.

        Args:
            input_data: Must contain 'text' key with user input.

        Returns:
            IntentDecipheringResult as dictionary.
        """
        text = input_data.get("text", "")
        if not text:
            raise ValueError("Input data must contain 'text' field")

        result = await self.decipher(text)
        return result.model_dump()

    async def decipher(self, user_input: str) -> IntentDecipheringResult:
        """Decipher the user's intent from their input.

        Args:
            user_input: The user's text input.

        Returns:
            IntentDecipheringResult with extracted information.
        """
        system_prompt = self._build_system_prompt()
        user_prompt = self._build_user_prompt(user_input)

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        try:
            result = await self.generate_structured(
                messages=messages,
                response_model=IntentDecipheringResult,
            )
            return result

        except Exception as e:
            logger.error(f"Intent deciphering failed: {e}", exc_info=True)
            # Return safe fallback
            return self._fallback_result(user_input, str(e))

    def _build_system_prompt(self) -> str:
        """Build the system prompt for intent deciphering."""
        return """You are an Intent Decipherer for a canvas-based agentic workspace.

Your task is to analyze user input and extract:
1. **Primary Intent**: What the user wants to do (research, create, analyze, etc.)
2. **Assumptions**: Things you're inferring that need confirmation
3. **Parameters**: Extracted values for execution
4. **Sub-intents**: For complex requests, break them into smaller steps

Categories for assumptions:
- context: Assumptions about the user's context or workspace state
- intent: Assumptions about what the user wants to accomplish
- parameter: Assumptions about specific values or parameters
- other: Other types of assumptions

Confidence scores:
- 0.9-1.0: Very confident, can auto-execute
- 0.7-0.9: Confident, but may want confirmation for assumptions
- 0.5-0.7: Moderate confidence, should ask for clarification
- <0.5: Low confidence, must ask user

Auto-execution should only be recommended when:
- Primary intent confidence >= 0.8
- No high-risk assumptions (confidence < 0.7) exist
- Required parameters are present with good confidence

Provide clear, structured output that helps the system understand and validate user intent."""

    def _build_user_prompt(self, user_input: str) -> str:
        """Build the user prompt from the input."""
        return f"""Analyze this user input:

"{user_input}"

Extract the primary intent, any assumptions you're making, parameters, and sub-intents.
Provide confidence scores and reasoning for your analysis."""

    def _fallback_result(
        self, user_input: str, error_message: str
    ) -> IntentDecipheringResult:
        """Return a safe fallback result when deciphering fails.

        Args:
            user_input: The original user input.
            error_message: Error message to include in reasoning.

        Returns:
            Minimal IntentDecipheringResult.
        """
        return IntentDecipheringResult(
            primary_intent=IntentClassification(
                name="chat",
                confidence=0.5,
                description="Fallback to general chat due to processing error",
            ),
            should_auto_execute=False,
            reasoning=f"Intent deciphering encountered an error: {error_message}",
        )

    def create_assumption(
        self,
        text: str,
        confidence: float,
        category: AssumptionCategory | str,
        explanation: str | None = None,
    ) -> Assumption:
        """Factory method to create an Assumption with proper validation.

        Args:
            text: The assumption text.
            confidence: Confidence score (0-1).
            category: Category of the assumption.
            explanation: Optional explanation.

        Returns:
            Validated Assumption instance.
        """
        if isinstance(category, str):
            category = AssumptionCategory(category)

        return Assumption(
            id=str(uuid.uuid4()),
            text=text,
            confidence=confidence,
            category=category.value,
            explanation=explanation,
        )

    async def batch_decipher(
        self, inputs: list[str]
    ) -> list[IntentDecipheringResult]:
        """Decipher multiple user inputs efficiently.

        Args:
            inputs: List of user input strings.

        Returns:
            List of IntentDecipheringResult.
        """
        # For now, process sequentially
        # Could be optimized with batch Gateway calls if supported
        results = []
        for input_text in inputs:
            result = await self.decipher(input_text)
            results.append(result)
        return results


# Singleton instance
_agent: IntentDeciphererAgent | None = None


def get_intent_decipherer() -> IntentDeciphererAgent:
    """Get the singleton Intent Decipherer Agent instance.

    Returns:
        Intent Decipherer Agent instance.
    """
    global _agent
    if _agent is None:
        _agent = IntentDeciphererAgent()
    return _agent
