"""Judge Agent for evaluating and synthesizing multi-perspective research.

This agent implements the LLM-as-Judge workflow:
- Evaluates multiple perspectives on quality, relevance, depth, and insightfulness
- Scores and ranks perspectives based on objective criteria
- Identifies and resolves conflicts between perspectives
- Synthesizes the best insights from each perspective
- Provides transparent reasoning for all judgments
"""

import logging
import uuid
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel, Field

from app.agents.base import BaseAgent
from app.gateway.client import GatewayClient

logger = logging.getLogger(__name__)


# Judge evaluation models


class PerspectiveScore(BaseModel):
    """Detailed score for a single perspective."""

    perspective: str = Field(description="Name of the perspective")
    display_name: str = Field(description="Human-readable name")
    relevance: float = Field(
        ge=0.0, le=1.0, description="How relevant is this perspective to the query?"
    )
    depth: float = Field(
        ge=0.0, le=1.0, description="How deep and thorough is the analysis?"
    )
    quality: float = Field(
        ge=0.0, le=1.0, description="What is the overall quality of reasoning?"
    )
    insightfulness: float = Field(
        ge=0.0, le=1.0, description="How novel and insightful are the findings?"
    )
    overall_score: float = Field(
        ge=0.0, le=1.0, description="Weighted overall score"
    )
    rationale: str = Field(description="Explanation for the scoring")
    key_insights: list[str] = Field(
        default_factory=list, description="Top insights from this perspective"
    )
    weaknesses: list[str] = Field(
        default_factory=list, description="Identified weaknesses or gaps"
    )


class Conflict(BaseModel):
    """A conflict identified between perspectives."""

    conflict_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    type: str = Field(description="Type of conflict (contradiction, tension, gap)")
    perspectives: list[str] = Field(description="Perspectives involved in the conflict")
    description: str = Field(description="Description of the conflict")
    resolution: str = Field(description="How the conflict was resolved")
    priority: str = Field(
        description="Priority level (high, medium, low)"
    )


class JudgmentMetadata(BaseModel):
    """Metadata about the judgment process."""

    query: str = Field(description="Original research query")
    total_perspectives: int = Field(description="Number of perspectives evaluated")
    conflicts_identified: int = Field(description="Number of conflicts found")
    conflicts_resolved: int = Field(description="Number of conflicts resolved")
    total_insights_extracted: int = Field(description="Total insights extracted")
    top_perspective: str = Field(description="Highest-ranked perspective")
    judgment_criteria: list[str] = Field(
        default_factory=list, description="Criteria used for judgment"
    )
    transparency_notes: list[str] = Field(
        default_factory=list, description="Notes about the judgment process"
    )


class JudgeSynthesis(BaseModel):
    """Final synthesis from the Judge Agent."""

    executive_summary: str = Field(description="Executive summary of findings")
    key_insights: list[str] = Field(description="Key insights from synthesis")
    recommendations: list[str] = Field(description="Actionable recommendations")
    confidence: float = Field(
        ge=0.0, le=1.0, description="Overall confidence in findings"
    )
    confidence_rationale: str = Field(description="Explanation of confidence level")
    risks: list[dict[str, str]] = Field(description="Identified risks by perspective")
    open_questions: list[str] = Field(description="Areas for further investigation")
    perspective_scores: list[PerspectiveScore] = Field(
        description="Scores for each perspective"
    )
    conflicts: list[Conflict] = Field(description="Conflicts identified and resolved")
    metadata: JudgmentMetadata = Field(description="Judgment process metadata")


@dataclass
class JudgeConfig:
    """Configuration for Judge Agent."""

    # Scoring weights
    relevance_weight: float = 0.3
    depth_weight: float = 0.25
    quality_weight: float = 0.25
    insightfulness_weight: float = 0.2

    # Minimum thresholds
    min_score_threshold: float = 0.4

    # Conflict detection
    detect_conflicts: bool = True
    conflict_threshold: float = 0.3  # Difference in scores to flag potential conflict


class JudgeAgent(BaseAgent):
    """Agent for evaluating and synthesizing multi-perspective research.

    The Judge Agent:
    1. Evaluates each perspective against objective criteria
    2. Scores perspectives on relevance, depth, quality, and insightfulness
    3. Identifies and resolves conflicts between perspectives
    4. Extracts and ranks the best insights from each perspective
    5. Synthesizes findings into a comprehensive report
    6. Provides complete transparency about the judgment process

    Usage:
        agent = JudgeAgent()
        synthesis = await agent.judge(
            query="What are the implications of AI in healthcare?",
            perspective_results=[...]
        )
    """

    def __init__(
        self,
        gateway: GatewayClient | None = None,
        model: str = "openai/gpt-4o",
        temperature: float = 0.3,
        config: JudgeConfig | None = None,
    ) -> None:
        """Initialize the Judge Agent.

        Args:
            gateway: Gateway client instance.
            model: Model identifier for Gateway.
            temperature: Sampling temperature (lower for more consistent judgments).
            config: Judge configuration.
        """
        super().__init__(gateway=gateway, model=model, temperature=temperature)
        self.config = config or JudgeConfig()

    async def run(self, input_data: dict[str, Any]) -> dict[str, Any]:
        """Run the judge agent with the given input.

        Args:
            input_data: Must contain 'query' and 'perspective_results' keys.

        Returns:
            JudgeSynthesis as dictionary.
        """
        query = input_data.get("query", "")
        perspective_results = input_data.get("perspective_results", [])

        if not query:
            raise ValueError("Input data must contain 'query' field")
        if not perspective_results:
            raise ValueError("Input data must contain 'perspective_results' field")

        synthesis = await self.judge(query, perspective_results)
        return synthesis.model_dump()

    async def judge(
        self,
        query: str,
        perspective_results: list[dict[str, Any]],
    ) -> JudgeSynthesis:
        """Evaluate and synthesize multiple perspective analyses.

        Args:
            query: Original research query.
            perspective_results: Results from perspective agents.

        Returns:
            JudgeSynthesis with evaluated and synthesized findings.
        """
        logger.info(f"Starting judgment for query: {query}")

        # Step 1: Score each perspective
        scores = await self._score_perspectives(query, perspective_results)

        # Step 2: Identify and resolve conflicts
        conflicts = await self._identify_and_resolve_conflicts(
            query, perspective_results, scores
        )

        # Step 3: Extract best insights from top perspectives
        top_insights = self._extract_top_insights(scores)

        # Step 4: Generate final synthesis
        synthesis = await self._generate_synthesis(
            query, scores, conflicts, top_insights
        )

        logger.info(f"Judgment completed. Top perspective: {synthesis.metadata.top_perspective}")

        return synthesis

    async def _score_perspectives(
        self,
        query: str,
        perspective_results: list[dict[str, Any]],
    ) -> list[PerspectiveScore]:
        """Score each perspective on objective criteria.

        Args:
            query: Research query.
            perspective_results: Perspective analysis results.

        Returns:
            List of PerspectiveScore objects.
        """
        scores = []

        for persp in perspective_results:
            name = persp.get("name", "")
            display_name = persp.get("display_name", persp.get("name", name))
            analysis = persp.get("analysis", "")

            score = await self._evaluate_single_perspective(
                query, name, display_name, analysis
            )
            scores.append(score)

        # Sort by overall score
        scores.sort(key=lambda s: s.overall_score, reverse=True)
        return scores

    async def _evaluate_single_perspective(
        self,
        query: str,
        name: str,
        display_name: str,
        analysis: str,
    ) -> PerspectiveScore:
        """Evaluate a single perspective on multiple dimensions.

        Args:
            query: Research query.
            name: Perspective identifier.
            display_name: Human-readable name.
            analysis: The perspective's analysis text.

        Returns:
            PerspectiveScore with detailed evaluation.
        """
        system_prompt = """You are an impartial Research Judge. Your role is to evaluate perspective analyses on objective criteria.

Evaluate the perspective analysis on four dimensions:
1. **Relevance** (0-1): How directly does this address the research query?
2. **Depth** (0-1): How thorough and comprehensive is the analysis?
3. **Quality** (0-1): What is the quality of reasoning and evidence?
4. **Insightfulness** (0-1): How novel, valuable, and actionable are the insights?

Also provide:
- Rationale: Explain your scoring
- Key insights: List the top 3-5 best insights from this perspective
- Weaknesses: Identify any gaps, biases, or areas for improvement

Calculate overall_score as a weighted average:
overall_score = 0.3*relevance + 0.25*depth + 0.25*quality + 0.2*insightfulness

Return your evaluation as JSON:
{
  "relevance": 0.85,
  "depth": 0.75,
  "quality": 0.80,
  "insightfulness": 0.70,
  "overall_score": 0.78,
  "rationale": "...",
  "key_insights": ["...", "..."],
  "weaknesses": ["...", "..."]
}

Be objective, fair, and thorough in your evaluation."""

        user_prompt = f"""Evaluate the following perspective analysis:

**Research Query**: {query}

**Perspective**: {display_name}

**Analysis**:
{analysis[:3000]}  {"[Truncated for evaluation]" if len(analysis) > 3000 else ""}

Provide your evaluation as valid JSON."""

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        try:
            response = await self.generate(messages=messages)
            content = response["choices"][0]["message"]["content"]

            import json

            parsed = json.loads(content)

            # Validate overall_score calculation
            calculated_overall = (
                self.config.relevance_weight * parsed.get("relevance", 0.5)
                + self.config.depth_weight * parsed.get("depth", 0.5)
                + self.config.quality_weight * parsed.get("quality", 0.5)
                + self.config.insightfulness_weight * parsed.get("insightfulness", 0.5)
            )

            # Use calculated score if it differs significantly
            if abs(calculated_overall - parsed.get("overall_score", 0)) > 0.1:
                parsed["overall_score"] = calculated_overall

            return PerspectiveScore(
                perspective=name,
                display_name=display_name,
                relevance=parsed.get("relevance", 0.5),
                depth=parsed.get("depth", 0.5),
                quality=parsed.get("quality", 0.5),
                insightfulness=parsed.get("insightfulness", 0.5),
                overall_score=parsed.get("overall_score", calculated_overall),
                rationale=parsed.get("rationale", "No rationale provided"),
                key_insights=parsed.get("key_insights", []),
                weaknesses=parsed.get("weaknesses", []),
            )

        except Exception as e:
            logger.warning(f"Perspective evaluation failed for {name}: {e}")

            # Return default score
            return PerspectiveScore(
                perspective=name,
                display_name=display_name,
                relevance=0.5,
                depth=0.5,
                quality=0.5,
                insightfulness=0.5,
                overall_score=0.5,
                rationale=f"Evaluation failed: {str(e)}",
                key_insights=[],
                weaknesses=["Evaluation failed"],
            )

    async def _identify_and_resolve_conflicts(
        self,
        query: str,
        perspective_results: list[dict[str, Any]],
        scores: list[PerspectiveScore],
    ) -> list[Conflict]:
        """Identify and resolve conflicts between perspectives.

        Args:
            query: Research query.
            perspective_results: Original perspective results.
            scores: Scored perspectives.

        Returns:
            List of resolved conflicts.
        """
        if not self.config.detect_conflicts:
            return []

        # Build perspective map with proper typing
        persp_map: dict[str, dict[str, Any]] = {}
        for s in scores:
            analysis = ""
            for p in perspective_results:
                if p.get("name") == s.perspective:
                    analysis = p.get("analysis", "")
                    break
            persp_map[s.perspective] = {"score": s, "analysis": analysis}

        # Detect conflicts based on score differences and content analysis
        conflicts = []

        # Check for contradictions between top perspectives
        top_perspectives = scores[:3]
        for i, p1 in enumerate(top_perspectives):
            for p2 in top_perspectives[i + 1:]:
                analysis1 = persp_map[p1.perspective]["analysis"]
                analysis2 = persp_map[p2.perspective]["analysis"]
                conflict = await self._check_for_conflict(
                    query, p1, p2, str(analysis1), str(analysis2)
                )
                if conflict:
                    conflicts.append(conflict)

        return conflicts

    async def _check_for_conflict(
        self,
        query: str,
        p1: PerspectiveScore,
        p2: PerspectiveScore,
        analysis1: str,
        analysis2: str,
    ) -> Conflict | None:
        """Check for conflicts between two perspectives.

        Args:
            query: Research query.
            p1, p2: The two perspectives to compare.
            analysis1, analysis2: Their analysis texts.

        Returns:
            Conflict object if conflict found, None otherwise.
        """
        system_prompt = """You are a Conflict Detection Specialist. Identify whether two perspectives are in conflict.

Conflict types:
- **contradiction**: Direct opposition of claims or conclusions
- **tension**: Subtle disagreements that can be reconciled
- **gap**: Different areas of focus that aren't necessarily conflicting

If a conflict is found, describe it and suggest a resolution.

Return as JSON:
{
  "has_conflict": true/false,
  "type": "contradiction/tension/gap",
  "description": "...",
  "resolution": "..."
}

Only flag actual conflicts, not normal differences in perspective."""

        user_prompt = f"""Check for conflicts between these two perspectives:

**Research Query**: {query}

**Perspective 1: {p1.display_name}**
Score: {p1.overall_score:.2f}
Analysis: {analysis1[:1500]}

**Perspective 2: {p2.display_name}**
Score: {p2.overall_score:.2f}
Analysis: {analysis2[:1500]}

Analyze for conflicts and return valid JSON."""

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        try:
            response = await self.generate(messages=messages)
            content = response["choices"][0]["message"]["content"]

            import json

            parsed = json.loads(content)

            if not parsed.get("has_conflict", False):
                return None

            return Conflict(
                type=parsed.get("type", "gap"),
                perspectives=[p1.perspective, p2.perspective],
                description=parsed.get("description", "Conflict detected"),
                resolution=parsed.get("resolution", "Acknowledged as differing perspectives"),
                priority="high" if parsed.get("type") == "contradiction" else "medium",
            )

        except Exception as e:
            logger.warning(f"Conflict detection failed: {e}")
            return None

    def _extract_top_insights(self, scores: list[PerspectiveScore]) -> dict[str, list[str]]:
        """Extract top insights from scored perspectives.

        Args:
            scores: List of scored perspectives.

        Returns:
            Dictionary mapping perspective names to their top insights.
        """
        insights = {}

        for score in scores:
            if score.overall_score >= self.config.min_score_threshold:
                insights[score.perspective] = score.key_insights

        return insights

    async def _generate_synthesis(
        self,
        query: str,
        scores: list[PerspectiveScore],
        conflicts: list[Conflict],
        top_insights: dict[str, list[str]],
    ) -> JudgeSynthesis:
        """Generate the final synthesis report.

        Args:
            query: Research query.
            scores: Scored perspectives.
            conflicts: Identified conflicts.
            top_insights: Top insights by perspective.

        Returns:
            Complete JudgeSynthesis.
        """
        # Build synthesis context
        scores_summary = self._build_scores_summary(scores)
        insights_summary = self._build_insights_summary(top_insights)
        conflicts_summary = self._build_conflicts_summary(conflicts)

        system_prompt = """You are a Master Research Synthesizer. Create a comprehensive synthesis from judged perspective analyses.

Your synthesis should:
1. Combine the strongest insights across all perspectives
3. Provide clear, actionable recommendations
4. Acknowledge limitations and uncertainties
5. Balance different viewpoints appropriately
6. Address any conflicts identified

Return as JSON:
{
  "executive_summary": "2-3 paragraphs",
  "key_insights": ["5-7 key insights"],
  "recommendations": ["3-5 actionable recommendations"],
  "confidence": 0.0-1.0,
  "confidence_rationale": "explain confidence level",
  "risks": [{"perspective": "...", "risk": "..."}],
  "open_questions": ["3-5 questions for further research"]
}

Prioritize quality and depth over quantity. Be specific and actionable."""

        user_prompt = f"""Create a synthesis from the following judged research:

**Research Query**: {query}

**Perspective Rankings**:
{scores_summary}

**Key Insights by Perspective**:
{insights_summary}

**Conflicts Identified and Resolved**:
{conflicts_summary}

Create a comprehensive synthesis as valid JSON."""

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        try:
            response = await self.generate(messages=messages)
            content = response["choices"][0]["message"]["content"]

            import json

            parsed = json.loads(content)

            # Build metadata
            metadata = JudgmentMetadata(
                query=query,
                total_perspectives=len(scores),
                conflicts_identified=len(conflicts),
                conflicts_resolved=sum(1 for c in conflicts if c.resolution),
                total_insights_extracted=sum(len(i) for i in top_insights.values()),
                top_perspective=scores[0].perspective if scores else "none",
                judgment_criteria=[
                    f"Relevance (weight: {self.config.relevance_weight})",
                    f"Depth (weight: {self.config.depth_weight})",
                    f"Quality (weight: {self.config.quality_weight})",
                    f"Insightfulness (weight: {self.config.insightfulness_weight})",
                ],
                transparency_notes=[
                    f"Minimum score threshold: {self.config.min_score_threshold}",
                    "Perspectives scored independently then ranked",
                    "Conflicts detected through comparative analysis",
                    "Top insights extracted from perspectives above threshold",
                ],
            )

            return JudgeSynthesis(
                executive_summary=parsed.get("executive_summary", ""),
                key_insights=parsed.get("key_insights", []),
                recommendations=parsed.get("recommendations", []),
                confidence=parsed.get("confidence", 0.6),
                confidence_rationale=parsed.get("confidence_rationale", ""),
                risks=parsed.get("risks", []),
                open_questions=parsed.get("open_questions", []),
                perspective_scores=scores,
                conflicts=conflicts,
                metadata=metadata,
            )

        except Exception as e:
            logger.error(f"Synthesis generation failed: {e}")

            # Return fallback synthesis
            return JudgeSynthesis(
                executive_summary=f"Research synthesis for query: {query}. Evaluated {len(scores)} perspectives.",
                key_insights=[],
                recommendations=["Review individual perspective analyses"],
                confidence=0.5,
                confidence_rationale=f"Synthesis failed: {str(e)}",
                risks=[],
                open_questions=[],
                perspective_scores=scores,
                conflicts=conflicts,
                metadata=JudgmentMetadata(
                    query=query,
                    total_perspectives=len(scores),
                    conflicts_identified=len(conflicts),
                    conflicts_resolved=0,
                    total_insights_extracted=0,
                    top_perspective=scores[0].perspective if scores else "none",
                    judgment_criteria=[],
                    transparency_notes=["Synthesis failed - using raw data"],
                ),
            )

    def _build_scores_summary(self, scores: list[PerspectiveScore]) -> str:
        """Build a summary of perspective scores."""
        lines = []
        for s in scores:
            lines.append(
                f"- {s.display_name} (overall: {s.overall_score:.2f}): "
                f"relevance={s.relevance:.2f}, depth={s.depth:.2f}, "
                f"quality={s.quality:.2f}, insightfulness={s.insightfulness:.2f}"
            )
        return "\n".join(lines)

    def _build_insights_summary(self, insights: dict[str, list[str]]) -> str:
        """Build a summary of top insights."""
        lines = []
        for persp, persp_insights in insights.items():
            lines.append(f"\n**{persp}**:")
            for insight in persp_insights[:3]:
                lines.append(f"  - {insight}")
        return "\n".join(lines)

    def _build_conflicts_summary(self, conflicts: list[Conflict]) -> str:
        """Build a summary of conflicts."""
        if not conflicts:
            return "No conflicts detected."

        lines = []
        for c in conflicts:
            lines.append(f"\n- **{c.type.upper()}** ({', '.join(c.perspectives)}):")
            lines.append(f"  Description: {c.description}")
            lines.append(f"  Resolution: {c.resolution}")
            lines.append(f"  Priority: {c.priority}")
        return "\n".join(lines)


# Singleton instance
_agent: JudgeAgent | None = None


def get_judge_agent() -> JudgeAgent:
    """Get the singleton Judge Agent instance.

    Returns:
        Judge Agent instance.
    """
    global _agent
    if _agent is None:
        _agent = JudgeAgent()
    return _agent
