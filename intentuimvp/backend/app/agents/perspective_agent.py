"""Perspective Agent for LLM-as-judge patterns (FR-012).

This agent provides:
- Multiple perspective analysis on a topic (skeptic, advocate, synthesizer)
- Sequential perspective execution with 30s timeout per perspective
- Graceful failure handling (proceed with available perspectives)
- Structured comparison of viewpoints per PRD FR-012

PRD Reference: FR-012 Multi-Judge Compute (LLM-as-Judge) + Synthesis
Default Perspectives:
1. skeptic - Challenges claims, looks for weak evidence
2. advocate - Steelmans the argument, finds supporting evidence
3. synthesizer - Identifies common ground and key tensions
"""

import asyncio
import logging
import uuid
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel, Field

from app.agents.base import BaseAgent

logger = logging.getLogger(__name__)

# FR-012: Timeout per perspective is 30 seconds
PERSPECTIVE_TIMEOUT = 30.0


# Perspective models
class Perspective(BaseModel):
    """A single perspective on a topic (FR-012)."""

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str = Field(description="Name of this perspective")
    description: str = Field(description="Description of the viewpoint")
    stance: str = Field(description="Overall stance (pro, con, neutral)")
    arguments: list[str] = Field(description="Key arguments from this perspective")
    evidence: list[str] = Field(default_factory=list, description="Supporting evidence")
    confidence: float = Field(ge=0.0, le=1.0, description="Confidence in this perspective")
    strengths: list[str] = Field(default_factory=list)
    weaknesses: list[str] = Field(default_factory=list)
    failed: bool = Field(default=False, description="True if perspective generation failed")
    failure_reason: str | None = Field(default=None, description="Reason for failure")


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
    """Agent for analyzing multiple perspectives on a topic (FR-012).

    The perspective agent uses LLM-as-judge patterns to:
    1. Generate diverse perspectives on a topic (sequential execution)
    2. Analyze arguments from each viewpoint
    3. Identify consensus and disagreement
    4. Detect and analyze potential biases
    5. Provide balanced recommendations
    6. Handle failures gracefully (proceed with available perspectives)

    FR-012 Default Perspectives:
    1. skeptic - Challenges claims, looks for weak evidence
    2. advocate - Steelmans the argument, finds supporting evidence
    3. synthesizer - Identifies common ground and key tensions

    Usage:
        agent = PerspectiveAgent()
        evaluation = await agent.evaluate("Should AI development continue unregulated?")
    """

    # FR-012: Default perspectives for multi-judge compute
    DEFAULT_PERSPECTIVES = [
        "skeptic",      # Challenges claims, looks for weak evidence
        "advocate",     # Steelmans the argument, finds supporting evidence
        "synthesizer",  # Identifies common ground and key tensions
    ]

    def __init__(
        self,
        gateway: Any | None = None,
        model: str | None = None,
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
        """Evaluate multiple perspectives on a topic (FR-012).

        FR-012 Implementation:
        - Sequential execution (single model)
        - 30 second timeout per perspective
        - If perspective fails: proceed with available, note in output

        Args:
            topic: Topic to analyze.
            perspectives: Optional list of perspective types to use.

        Returns:
            PerspectiveEvaluation with analysis.
        """
        # FR-012: Select perspectives (configurable 1-3)
        perspective_names = (
            perspectives[: self.config.num_perspectives]
            if perspectives
            else self.DEFAULT_PERSPECTIVES[: self.config.num_perspectives]
        )

        # FR-012: Generate each perspective sequentially with timeout
        # If perspective fails: proceed with available perspectives
        perspective_objs: list[Perspective] = []
        for name in perspective_names:
            try:
                # FR-012: 30 second timeout per perspective
                perspective = await asyncio.wait_for(
                    self._generate_perspective(topic, name),
                    timeout=PERSPECTIVE_TIMEOUT,
                )
                perspective_objs.append(perspective)
                logger.info(
                    f"Perspective '{name}' generated successfully",
                    extra={"perspective": name, "confidence": perspective.confidence},
                )
            except TimeoutError:
                # FR-012: If perspective fails, note in output and proceed
                logger.warning(
                    f"Perspective '{name}' timed out after {PERSPECTIVE_TIMEOUT}s",
                    extra={"perspective": name, "timeout": PERSPECTIVE_TIMEOUT},
                )
                perspective_objs.append(
                    Perspective(
                        name=name,
                        description="Perspective generation timed out",
                        stance="neutral",
                        arguments=[f"Timed out after {PERSPECTIVE_TIMEOUT}s"],
                        confidence=0.0,
                        failed=True,
                        failure_reason=f"Timeout after {PERSPECTIVE_TIMEOUT}s",
                    )
                )
            except Exception as e:
                # FR-012: If perspective fails, note in output and proceed
                logger.warning(
                    f"Perspective '{name}' generation failed: {e}",
                    extra={"perspective": name, "error": str(e)},
                    exc_info=True,
                )
                perspective_objs.append(
                    Perspective(
                        name=name,
                        description="Perspective generation failed",
                        stance="neutral",
                        arguments=["Generation failed"],
                        confidence=0.0,
                        failed=True,
                        failure_reason=str(e),
                    )
                )

        # Filter out failed perspectives for analysis
        successful_perspectives = [p for p in perspective_objs if not p.failed]

        # Only run consensus/disagreement if we have at least 2 successful perspectives
        if len(successful_perspectives) >= 2:
            consensus_points = await self._find_consensus(successful_perspectives)
            disagreement_points = await self._find_disagreements(successful_perspectives)
        else:
            consensus_points = []
            disagreement_points = []
            logger.info(
                "Skipping consensus/disagreement analysis due to insufficient successful perspectives",
                extra={"successful_count": len(successful_perspectives)},
            )

        # Bias analysis (only if we have successful perspectives)
        bias_analysis = (
            await self._analyze_biases(topic, successful_perspectives)
            if self.config.include_bias_analysis and successful_perspectives
            else BiasAnalysis()
        )

        # Generate recommendation
        recommendation = await self._generate_recommendation(
            topic, successful_perspectives, consensus_points, disagreement_points
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
        """Generate a single perspective on the topic (FR-012).

        FR-012 Perspective Types:
        - skeptic: Challenges claims, looks for weak evidence
        - advocate: Steelmans the argument, finds supporting evidence
        - synthesizer: Identifies common ground and key tensions

        Args:
            topic: Topic to analyze.
            perspective_type: Type of perspective to generate.

        Returns:
            Perspective with analysis.

        Raises:
            Exception: If generation fails (caller handles gracefully).
        """
        # FR-012: Specific prompts for each perspective type
        system_prompts = {
            "skeptic": """You are a SKEPTIC analyst. Your role is to:
- Challenge claims and look for weak evidence
- Question assumptions and identify logical fallacies
- Point out what's missing or inadequately supported
- Find counterarguments and alternative explanations
- Be rigorous about evidence quality""",
            "advocate": """You are an ADVOCATE analyst. Your role is to:
- Steelman the argument (present the strongest version)
- Find supporting evidence and strong reasoning
- Highlight the best aspects of the position
- Give the view its fairest, most compelling presentation
- Assume good faith and charitable interpretation""",
            "synthesizer": """You are a SYNTHESIZER analyst. Your role is to:
- Identify common ground across different viewpoints
- Find areas of agreement and shared values
- Highlight key tensions and trade-offs
- Bridge divides and find middle ground
- Focus on what unites rather than divides""",
        }

        # Get the appropriate prompt, defaulting to a generic one
        system_prompt = system_prompts.get(
            perspective_type,
            f"""You are a {perspective_type} analyst.
Your task is to analyze the given topic fairly from this specific viewpoint.
- Present strong arguments supporting this perspective
- Acknowledge limitations or weaknesses of this view
- Provide evidence or reasoning where applicable
- Be honest about uncertainty""",
        )

        system_prompt += """

Return your analysis as JSON with:
- name: perspective name (use the perspective type)
- description: brief description of this viewpoint
- stance: pro/con/neutral regarding the topic
- arguments: array of key arguments (3-5)
- evidence: array of supporting points or evidence
- confidence: how confident in this view (0-1)
- strengths: array of strengths of this perspective
- weaknesses: array of weaknesses or limitations"""

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Topic: {topic}"},
        ]

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
