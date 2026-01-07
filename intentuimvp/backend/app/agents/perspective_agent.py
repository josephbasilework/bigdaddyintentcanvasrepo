"""Perspective Agent for LLM-as-judge patterns.

This agent provides:
- Multiple perspective analysis on a topic
- Objective evaluation of claims and arguments
- Bias detection and mitigation
- Structured comparison of viewpoints
"""

import logging
import uuid
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel, Field

from app.agents.base import BaseAgent

logger = logging.getLogger(__name__)


# Perspective models
class Perspective(BaseModel):
    """A single perspective on a topic."""

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str = Field(description="Name of this perspective")
    description: str = Field(description="Description of the viewpoint")
    stance: str = Field(description="Overall stance (pro, con, neutral)")
    arguments: list[str] = Field(description="Key arguments from this perspective")
    evidence: list[str] = Field(default_factory=list, description="Supporting evidence")
    confidence: float = Field(ge=0.0, le=1.0, description="Confidence in this perspective")
    strengths: list[str] = Field(default_factory=list)
    weaknesses: list[str] = Field(default_factory=list)


class BiasAnalysis(BaseModel):
    """Analysis of potential biases."""

    detected_biases: list[str] = Field(default_factory=list)
    bias_explanations: list[str] = Field(default_factory=list)
    mitigation_suggestions: list[str] = Field(default_factory=list)
    overall_bias_rating: str = Field(default="unknown", description="low, medium, high")


class PerspectiveEvaluation(BaseModel):
    """Result of perspective analysis."""

    topic: str = Field(description="Topic being evaluated")
    perspectives: list[Perspective] = Field(description="All perspectives analyzed")
    consensus_points: list[str] = Field(default_factory=list)
    disagreement_points: list[str] = Field(default_factory=list)
    bias_analysis: BiasAnalysis = Field(description="Analysis of biases")
    recommendation: str = Field(description="Overall assessment")
    confidence: float = Field(ge=0.0, le=1.0)


@dataclass
class PerspectiveConfig:
    """Configuration for perspective agent."""

    num_perspectives: int = 3
    include_bias_analysis: bool = True
    require_evidence: bool = True


class PerspectiveAgent(BaseAgent):
    """Agent for analyzing multiple perspectives on a topic.

    The perspective agent uses LLM-as-judge patterns to:
    1. Generate diverse perspectives on a topic
    2. Analyze arguments from each viewpoint
    3. Identify consensus and disagreement
    4. Detect and analyze potential biases
    5. Provide balanced recommendations

    Usage:
        agent = PerspectiveAgent()
        evaluation = await agent.evaluate("Should AI development continue unregulated?")
    """

    DEFAULT_PERSPECTIVES = [
        "utilitarian",
        "deontological",
        "virtue_ethics",
        "precautionary",
        "innovation_focused",
        "stakeholder_focused",
    ]

    def __init__(
        self,
        gateway: Any | None = None,
        model: str = "openai/gpt-4o",
        temperature: float = 0.5,
        config: PerspectiveConfig | None = None,
    ) -> None:
        """Initialize the Perspective Agent.

        Args:
            gateway: Gateway client instance.
            model: Model identifier for Gateway.
            temperature: Sampling temperature.
            config: Perspective analysis configuration.
        """
        super().__init__(gateway=gateway, model=model, temperature=temperature)
        self.config = config or PerspectiveConfig()

    async def run(self, input_data: dict[str, Any]) -> dict[str, Any]:
        """Run the agent with the given input.

        Args:
            input_data: Must contain 'topic' key.

        Returns:
            PerspectiveEvaluation as dictionary.
        """
        topic = input_data.get("topic", "")
        if not topic:
            raise ValueError("Input data must contain 'topic' field")

        custom_perspectives = input_data.get("perspectives", None)

        evaluation = await self.evaluate(topic, custom_perspectives)
        return evaluation.model_dump()

    async def evaluate(
        self,
        topic: str,
        perspectives: list[str] | None = None,
    ) -> PerspectiveEvaluation:
        """Evaluate multiple perspectives on a topic.

        Args:
            topic: Topic to analyze.
            perspectives: Optional list of perspective types to use.

        Returns:
            PerspectiveEvaluation with analysis.
        """
        # Select perspectives
        perspective_names = (
            perspectives[: self.config.num_perspectives]
            if perspectives
            else self.DEFAULT_PERSPECTIVES[: self.config.num_perspectives]
        )

        # Generate each perspective
        perspective_objs: list[Perspective] = []
        for name in perspective_names:
            perspective = await self._generate_perspective(topic, name)
            perspective_objs.append(perspective)

        # Analyze consensus and disagreement
        consensus_points = await self._find_consensus(perspective_objs)
        disagreement_points = await self._find_disagreements(perspective_objs)

        # Bias analysis
        bias_analysis = (
            await self._analyze_biases(topic, perspective_objs)
            if self.config.include_bias_analysis
            else BiasAnalysis()
        )

        # Generate recommendation
        recommendation = await self._generate_recommendation(
            topic, perspective_objs, consensus_points, disagreement_points
        )

        # Calculate overall confidence
        confidence = self._calculate_confidence(perspective_objs)

        return PerspectiveEvaluation(
            topic=topic,
            perspectives=perspective_objs,
            consensus_points=consensus_points,
            disagreement_points=disagreement_points,
            bias_analysis=bias_analysis,
            recommendation=recommendation,
            confidence=confidence,
        )

    async def _generate_perspective(
        self, topic: str, perspective_type: str
    ) -> Perspective:
        """Generate a single perspective on the topic.

        Args:
            topic: Topic to analyze.
            perspective_type: Type of perspective to generate.

        Returns:
            Perspective with analysis.
        """
        system_prompt = f"""You are an analyst providing a {perspective_type} perspective.

Your task is to analyze the given topic fairly from this specific viewpoint.
- Present strong arguments supporting this perspective
- Acknowledge limitations or weaknesses of this view
- Provide evidence or reasoning where applicable
- Be honest about uncertainty

Return your analysis as JSON with:
- name: perspective name
- description: brief description
- stance: pro/con/neutral
- arguments: array of key arguments (3-5)
- evidence: array of supporting points
- confidence: how confident in this view (0-1)
- strengths: array of strengths
- weaknesses: array of weaknesses"""

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Topic: {topic}"},
        ]

        try:
            response = await self.generate(messages=messages)
            content = response["choices"][0]["message"]["content"]

            import json

            parsed = json.loads(content)

            return Perspective(
                name=perspective_type,
                description=parsed.get("description", ""),
                stance=parsed.get("stance", "neutral"),
                arguments=parsed.get("arguments", []),
                evidence=parsed.get("evidence", []),
                confidence=parsed.get("confidence", 0.5),
                strengths=parsed.get("strengths", []),
                weaknesses=parsed.get("weaknesses", []),
            )

        except Exception as e:
            logger.warning(f"Perspective generation failed for {perspective_type}: {e}")

            # Return fallback
            return Perspective(
                name=perspective_type,
                description=f"Analysis from {perspective_type} viewpoint",
                stance="neutral",
                arguments=["Analysis unavailable"],
                confidence=0.3,
                strengths=[],
                weaknesses=["Generation failed"],
            )

    async def _find_consensus(
        self, perspectives: list[Perspective]
    ) -> list[str]:
        """Find points of consensus across perspectives.

        Args:
            perspectives: List of perspectives to analyze.

        Returns:
            List of consensus points.
        """
        # Find common themes using LLM
        all_args_text = "\n".join(
            [
                f"Perspective {i+1} ({p.name}):\n" + "\n".join(p.arguments)
                for i, p in enumerate(perspectives)
            ]
        )

        system_prompt = """Analyze the perspectives and identify points of consensus or agreement.

Look for:
- Common themes across all perspectives
- Shared concerns or values
- Overlapping recommendations
- Universal principles

Return as JSON with a "consensus_points" array of strings."""

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": all_args_text},
        ]

        try:
            response = await self.generate(messages=messages)
            content = response["choices"][0]["message"]["content"]

            import json

            parsed = json.loads(content)
            return parsed.get("consensus_points", [])

        except Exception:
            return []

    async def _find_disagreements(
        self, perspectives: list[Perspective]
    ) -> list[str]:
        """Find points of disagreement across perspectives.

        Args:
            perspectives: List of perspectives to analyze.

        Returns:
            List of disagreement points.
        """
        all_args_text = "\n".join(
            [
                f"Perspective {i+1} ({p.name}):\n" + "\n".join(p.arguments)
                for i, p in enumerate(perspectives)
            ]
        )

        system_prompt = """Analyze the perspectives and identify points of disagreement or conflict.

Look for:
- Fundamental differences in approach
- Contradictory recommendations
- Divergent values or priorities
- Areas requiring trade-offs

Return as JSON with a "disagreement_points" array of strings."""

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": all_args_text},
        ]

        try:
            response = await self.generate(messages=messages)
            content = response["choices"][0]["message"]["content"]

            import json

            parsed = json.loads(content)
            return parsed.get("disagreement_points", [])

        except Exception:
            return []

    async def _analyze_biases(
        self, topic: str, perspectives: list[Perspective]
    ) -> BiasAnalysis:
        """Analyze potential biases in the perspectives.

        Args:
            topic: The topic being analyzed.
            perspectives: List of perspectives.

        Returns:
            BiasAnalysis with findings.
        """
        perspectives_summary = "\n".join(
            [f"- {p.name}: {', '.join(p.arguments[:3])}" for p in perspectives]
        )

        system_prompt = """Analyze the given perspectives for potential biases.

Consider:
- Representation bias: Are important viewpoints missing?
- Confirmation bias: Are perspectives cherry-picking evidence?
- Framing bias: How is the topic being framed?
- Anchoring bias: Is there over-reliance on certain information?

Return as JSON with:
- detected_biases: array of bias types found
- bias_explanations: array of explanations
- mitigation_suggestions: array of suggestions
- overall_bias_rating: "low", "medium", or "high" """

        messages = [
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": f"Topic: {topic}\n\nPerspectives:\n{perspectives_summary}",
            },
        ]

        try:
            response = await self.generate(messages=messages)
            content = response["choices"][0]["message"]["content"]

            import json

            parsed = json.loads(content)

            return BiasAnalysis(
                detected_biases=parsed.get("detected_biases", []),
                bias_explanations=parsed.get("bias_explanations", []),
                mitigation_suggestions=parsed.get("mitigation_suggestions", []),
                overall_bias_rating=parsed.get("overall_bias_rating", "medium"),
            )

        except Exception:
            return BiasAnalysis(
                detected_biases=[],
                bias_explanations=["Bias analysis failed"],
                mitigation_suggestions=[],
                overall_bias_rating="unknown",
            )

    async def _generate_recommendation(
        self,
        topic: str,
        perspectives: list[Perspective],
        consensus: list[str],
        disagreements: list[str],
    ) -> str:
        """Generate a balanced recommendation.

        Args:
            topic: The topic.
            perspectives: All perspectives.
            consensus: Consensus points.
            disagreements: Disagreement points.

        Returns:
            Recommendation text.
        """
        system_prompt = """Generate a balanced, thoughtful recommendation based on multiple perspectives.

Your recommendation should:
- Acknowledge the complexity of the issue
- Weigh the different perspectives fairly
- Highlight consensus where it exists
- Address disagreements constructively
- Provide practical guidance

Return 2-3 paragraphs of recommendation."""

        context = f"""Topic: {topic}

Consensus Points:
{chr(10).join(f'- {c}' for c in consensus)}

Areas of Disagreement:
{chr(10).join(f'- {d}' for d in disagreements)}

Perspectives: {len(perspectives)} viewpoints analyzed"""

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": context},
        ]

        try:
            response = await self.generate(messages=messages)
            return response["choices"][0]["message"]["content"]

        except Exception:
            return "Unable to generate recommendation due to processing error."

    def _calculate_confidence(self, perspectives: list[Perspective]) -> float:
        """Calculate overall confidence based on perspective confidences.

        Args:
            perspectives: List of perspectives.

        Returns:
            Overall confidence score.
        """
        if not perspectives:
            return 0.0

        return sum(p.confidence for p in perspectives) / len(perspectives)


# Singleton instance
_agent: PerspectiveAgent | None = None


def get_perspective_agent() -> PerspectiveAgent:
    """Get the singleton Perspective Agent instance.

    Returns:
        Perspective Agent instance.
    """
    global _agent
    if _agent is None:
        _agent = PerspectiveAgent()
    return _agent
