"""Intent Deciphering Agent for extracting and validating user assumptions.

This agent analyzes user input to extract:
- Structured assumptions that need confirmation
- Intent classification with confidence scores
- Multi-intent decomposition for complex requests
- Parameter extraction for action execution

Implements NFR-PERF-003: Intent deciphering latency tracking.
"""

import logging
import uuid
from typing import Any

from pydantic import BaseModel, Field

from app.agents.base import BaseAgent
from app.context.models import Assumption, AssumptionCategory
from app.telemetry import track_intent_decipher

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

    DEFAULT_AUTO_EXECUTE_CONFIDENCE_THRESHOLD = 0.95
    DEFAULT_ASSUMPTION_CONFIDENCE_THRESHOLD = 0.7
    DEFAULT_CONFIDENCE_THRESHOLD = DEFAULT_AUTO_EXECUTE_CONFIDENCE_THRESHOLD

    def __init__(
        self,
        gateway: Any | None = None,
        model: str | None = None,
        temperature: float = 0.3,  # Lower temperature for more consistent classification
        confidence_threshold: float = DEFAULT_AUTO_EXECUTE_CONFIDENCE_THRESHOLD,
        assumption_confidence_threshold: float = DEFAULT_ASSUMPTION_CONFIDENCE_THRESHOLD,
    ) -> None:
        """Initialize the Intent Decipherer Agent.

        Args:
            gateway: Gateway client instance. If None, uses singleton.
            model: Model identifier for Gateway.
            temperature: Sampling temperature (lower for more deterministic classification).
            confidence_threshold: Threshold for auto-execution recommendation.
            assumption_confidence_threshold: Threshold for assumptions requiring confirmation.
        """
        super().__init__(gateway=gateway, model=model, temperature=temperature)
        self.confidence_threshold = confidence_threshold
        self.assumption_confidence_threshold = assumption_confidence_threshold

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

        Implements NFR-PERF-003: Tracks intent deciphering latency.

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
            # Track intent deciphering latency with telemetry
            with track_intent_decipher(
                agent_name="IntentDeciphererAgent",
                model=self.model,
                command_length=len(user_input),
            ):
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
        auto_execute_threshold = self.confidence_threshold
        assumption_threshold = self.assumption_confidence_threshold
        return f"""You are an Intent Decipherer for a canvas-based agentic workspace.

Your task is to analyze user input and extract structured information.

IMPORTANT: You MUST respond with ONLY valid JSON matching this exact schema:
{{
  "primary_intent": {{
    "name": "string (e.g., 'research', 'create', 'analyze', 'chat')",
    "confidence": number between 0.0 and 1.0,
    "description": "string describing what the user wants"
  }},
  "alternative_intents": [
    {{"name": "string", "confidence": number, "description": "string"}}
  ],
  "assumptions": [
    {{"text": "string", "confidence": number, "category": "context|intent|parameter|other"}}
  ],
  "parameters": [
    {{"name": "string", "value": "string", "confidence": number, "source": "explicit|inferred|default"}}
  ],
  "sub_intents": [
    {{"id": "uuid", "description": "string", "intent_type": "string", "dependencies": [], "confidence": number}}
  ],
  "should_auto_execute": boolean,
  "reasoning": "string explaining your analysis"
}}

Confidence thresholds:
- >= {auto_execute_threshold:.2f}: Very confident, can auto-execute
- {assumption_threshold:.2f} to < {auto_execute_threshold:.2f}: Confident, but confirm assumptions
- < {assumption_threshold:.2f}: Low confidence, must ask user

Set should_auto_execute to true ONLY when:
- Primary intent confidence >= {auto_execute_threshold:.2f}
- No assumptions with confidence < {assumption_threshold:.2f}
- Required parameters are present

DO NOT include any text before or after the JSON. Output ONLY the JSON object."""

    def _build_user_prompt(self, user_input: str) -> str:
        """Build the user prompt from the input."""
        return f"""Analyze this user input and respond with JSON only:

"{user_input}"

Return the JSON object with primary_intent, assumptions, parameters, sub_intents, should_auto_execute, and reasoning."""

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
