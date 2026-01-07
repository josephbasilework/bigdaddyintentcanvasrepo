"""Synthesis Agent for combining multiple perspectives and outputs.

This agent provides:
- Synthesis of multiple agent outputs
- Conflict resolution and reconciliation
- Structured combination of information
- Meta-analysis of research results
"""

import logging
import uuid
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel, Field

from app.agents.base import BaseAgent

logger = logging.getLogger(__name__)


# Synthesis models
class SynthesisInput(BaseModel):
    """An input to be synthesized."""

    source: str = Field(description="Source of this input (agent name, etc.)")
    content: str = Field(description="The content to synthesize")
    confidence: float = Field(
        ge=0.0, le=1.0, default=0.5, description="Confidence in this input"
    )
    metadata: dict[str, Any] = Field(default_factory=dict)


class SynthesisConflict(BaseModel):
    """A conflict detected during synthesis."""

    conflict_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    description: str = Field(description="Description of the conflict")
    sources: list[str] = Field(description="Sources involved in the conflict")
    resolution: str | None = Field(default=None, description="How it was resolved")
    resolution_confidence: float = Field(
        ge=0.0, le=1.0, default=0.5, description="Confidence in the resolution"
    )


class SynthesisResult(BaseModel):
    """Result of synthesis process."""

    synthesized_content: str = Field(description="The synthesized output")
    key_points: list[str] = Field(description="Key points from synthesis")
    conflicts: list[SynthesisConflict] = Field(description="Conflicts found and resolved")
    confidence: float = Field(ge=0.0, le=1.0, description="Overall confidence")
    sources_used: list[str] = Field(description="Sources included in synthesis")
    synthesis_method: str = Field(description="Method used for synthesis")
    caveats: list[str] = Field(
        default_factory=list, description="Caveats and limitations"
    )


@dataclass
class SynthesisConfig:
    """Configuration for synthesis agent."""

    method: str = "weighted"  # weighted, consensus, aggregation
    conflict_resolution: str = "merge"  # merge, prioritize, flag
    min_confidence_threshold: float = 0.3


class SynthesisAgent(BaseAgent):
    """Agent for synthesizing multiple inputs into a coherent output.

    The synthesis agent:
    1. Combines outputs from multiple agents
    2. Detects and resolves conflicts
    3. Identifies consensus and divergence
    4. Provides structured synthesis with confidence scoring
    5. Documents caveats and limitations

    Usage:
        agent = SynthesisAgent()
        result = await agent.synthesize([
            SynthesisInput(source="research", content="...", confidence=0.8),
            SynthesisInput(source="perspective", content="...", confidence=0.7),
        ])
    """

    def __init__(
        self,
        gateway: Any | None = None,
        model: str = "openai/gpt-4o",
        temperature: float = 0.4,
        config: SynthesisConfig | None = None,
    ) -> None:
        """Initialize the Synthesis Agent.

        Args:
            gateway: Gateway client instance.
            model: Model identifier for Gateway.
            temperature: Sampling temperature.
            config: Synthesis configuration.
        """
        super().__init__(gateway=gateway, model=model, temperature=temperature)
        self.config = config or SynthesisConfig()

    async def run(self, input_data: dict[str, Any]) -> dict[str, Any]:
        """Run the agent with the given input.

        Args:
            input_data: Must contain 'inputs' key with list of SynthesisInput.

        Returns:
            SynthesisResult as dictionary.
        """
        inputs_raw = input_data.get("inputs", [])
        if not inputs_raw:
            raise ValueError("Input data must contain 'inputs' field")

        # Convert dicts to SynthesisInput if needed
        inputs = [
            SynthesisInput(**i) if isinstance(i, dict) else i for i in inputs_raw
        ]

        result = await self.synthesize(inputs)
        return result.model_dump()

    async def synthesize(
        self,
        inputs: list[SynthesisInput],
        method: str | None = None,
    ) -> SynthesisResult:
        """Synthesize multiple inputs into a coherent output.

        Args:
            inputs: List of SynthesisInput to combine.
            method: Optional synthesis method override.

        Returns:
            SynthesisResult with synthesized content.
        """
        if not inputs:
            return SynthesisResult(
                synthesized_content="No inputs to synthesize",
                key_points=[],
                conflicts=[],
                confidence=0.0,
                sources_used=[],
                synthesis_method="none",
                caveats=["No inputs provided"],
            )

        method = method or self.config.method

        # Detect conflicts
        conflicts = await self._detect_conflicts(inputs)

        # Resolve conflicts
        resolved_conflicts = await self._resolve_conflicts(
            conflicts, self.config.conflict_resolution
        )

        # Perform synthesis based on method
        if method == "weighted":
            synthesis = await self._weighted_synthesis(inputs)
        elif method == "consensus":
            synthesis = await self._consensus_synthesis(inputs)
        elif method == "aggregation":
            synthesis = await self._aggregation_synthesis(inputs)
        else:
            synthesis = await self._llm_synthesis(inputs)

        # Extract key points
        key_points = await self._extract_key_points(inputs, synthesis)

        # Calculate confidence
        confidence = self._calculate_confidence(inputs, resolved_conflicts)

        # Identify caveats
        caveats = self._identify_caveats(inputs, resolved_conflicts)

        return SynthesisResult(
            synthesized_content=synthesis,
            key_points=key_points,
            conflicts=resolved_conflicts,
            confidence=confidence,
            sources_used=[i.source for i in inputs],
            synthesis_method=method,
            caveats=caveats,
        )

    async def _detect_conflicts(
        self, inputs: list[SynthesisInput]
    ) -> list[SynthesisConflict]:
        """Detect conflicts between inputs.

        Args:
            inputs: List of inputs to analyze.

        Returns:
            List of detected conflicts.
        """
        if len(inputs) < 2:
            return []

        # Build comparison text
        inputs_text = "\n\n".join(
            [
                f"Source: {i.source}\nContent: {i.content}\nConfidence: {i.confidence}"
                for i in inputs
            ]
        )

        system_prompt = """Analyze the given inputs for conflicts, contradictions, or significant disagreements.

Look for:
- Direct contradictions in facts or claims
- Incompatible conclusions
- Divergent recommendations
- Conflicting values or priorities

Return your analysis as JSON with a "conflicts" array where each conflict has:
- description: clear description of the conflict
- sources: array of source names involved"""

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": inputs_text},
        ]

        try:
            response = await self.generate(messages=messages)
            content = response["choices"][0]["message"]["content"]

            import json

            parsed = json.loads(content)

            conflicts = []
            for c in parsed.get("conflicts", []):
                conflicts.append(
                    SynthesisConflict(
                        description=c.get("description", ""),
                        sources=c.get("sources", []),
                    )
                )

            return conflicts

        except Exception as e:
            logger.warning(f"Conflict detection failed: {e}")
            return []

    async def _resolve_conflicts(
        self,
        conflicts: list[SynthesisConflict],
        resolution_method: str,
    ) -> list[SynthesisConflict]:
        """Resolve detected conflicts.

        Args:
            conflicts: List of conflicts to resolve.
            resolution_method: Method for resolution.

        Returns:
            List of conflicts with resolutions.
        """
        if not conflicts:
            return []

        for conflict in conflicts:
            if resolution_method == "merge":
                conflict.resolution = "Merged by acknowledging different viewpoints"
                conflict.resolution_confidence = 0.7
            elif resolution_method == "prioritize":
                # Prioritize higher confidence source
                if len(conflict.sources) >= 2:
                    conflict.resolution = "Prioritized based on confidence"
                    conflict.resolution_confidence = 0.6
                else:
                    conflict.resolution = "Unable to resolve"
                    conflict.resolution_confidence = 0.3
            else:  # flag
                conflict.resolution = "Flagged for user review"
                conflict.resolution_confidence = 0.5

        return conflicts

    async def _weighted_synthesis(self, inputs: list[SynthesisInput]) -> str:
        """Perform weighted synthesis based on confidence.

        Args:
            inputs: List of inputs to synthesize.

        Returns:
            Synthesized content.
        """
        # Sort by confidence
        sorted_inputs = sorted(inputs, key=lambda x: x.confidence, reverse=True)

        system_prompt = """Synthesize the following inputs into a coherent response.

Weight higher-confidence inputs more heavily, but still acknowledge lower-confidence inputs.
- Integrate information smoothly
- Attribute ideas to their sources
- Maintain a clear, organized structure
- Highlight the most confident findings"""

        inputs_text = "\n\n".join(
            [
                f"Source: {i.source} (confidence: {i.confidence})\n{i.content}"
                for i in sorted_inputs
            ]
        )

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": inputs_text},
        ]

        try:
            response = await self.generate(messages=messages)
            return response["choices"][0]["message"]["content"]

        except Exception as e:
            logger.error(f"Weighted synthesis failed: {e}")
            return "Synthesis failed"

    async def _consensus_synthesis(self, inputs: list[SynthesisInput]) -> str:
        """Perform consensus-based synthesis.

        Args:
            inputs: List of inputs to synthesize.

        Returns:
            Synthesized content focusing on consensus.
        """
        system_prompt = """Synthesize the following inputs by focusing on consensus and agreement.

Your goal is to:
- Identify common themes across all inputs
- Emphasize points of agreement
- Note areas of divergence without overemphasizing them
- Create a unified view that represents shared understanding"""

        inputs_text = "\n\n".join(
            [f"Source: {i.source}\n{i.content}" for i in inputs]
        )

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": inputs_text},
        ]

        try:
            response = await self.generate(messages=messages)
            return response["choices"][0]["message"]["content"]

        except Exception as e:
            logger.error(f"Consensus synthesis failed: {e}")
            return "Synthesis failed"

    async def _aggregation_synthesis(self, inputs: list[SynthesisInput]) -> str:
        """Perform simple aggregation synthesis.

        Args:
            inputs: List of inputs to synthesize.

        Returns:
            Aggregated content.
        """
        sections = []
        for inp in inputs:
            sections.append(f"## From {inp.source}\n\n{inp.content}\n")

        return "\n".join(sections)

    async def _llm_synthesis(self, inputs: list[SynthesisInput]) -> str:
        """Perform LLM-based synthesis.

        Args:
            inputs: List of inputs to synthesize.

        Returns:
            Synthesized content.
        """
        return await self._weighted_synthesis(inputs)

    async def _extract_key_points(
        self, inputs: list[SynthesisInput], synthesis: str
    ) -> list[str]:
        """Extract key points from synthesis.

        Args:
            inputs: Original inputs.
            synthesis: Synthesized content.

        Returns:
            List of key points.
        """
        system_prompt = """Extract 5-7 key points from the following synthesis.

Each point should:
- Capture an important insight
- Be clear and concise
- Represent the synthesis accurately

Return as a JSON array of strings."""

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": synthesis},
        ]

        try:
            response = await self.generate(messages=messages)
            content = response["choices"][0]["message"]["content"]

            import json

            points = json.loads(content)
            return points if isinstance(points, list) else []

        except Exception:
            # Fallback: extract sentences
            import re

            sentences = re.split(r"[.!?]+", synthesis)
            return [s.strip() for s in sentences if s.strip()][:5]

    def _calculate_confidence(
        self, inputs: list[SynthesisInput], conflicts: list[SynthesisConflict]
    ) -> float:
        """Calculate overall confidence in synthesis.

        Args:
            inputs: Input items.
            conflicts: Resolved conflicts.

        Returns:
            Confidence score.
        """
        if not inputs:
            return 0.0

        # Base confidence from inputs
        base_confidence = sum(i.confidence for i in inputs) / len(inputs)

        # Reduce confidence based on unresolved conflicts
        unresolved = sum(1 for c in conflicts if c.resolution_confidence < 0.5)
        if unresolved > 0:
            base_confidence *= 0.8

        return max(0.0, min(1.0, base_confidence))

    def _identify_caveats(
        self, inputs: list[SynthesisInput], conflicts: list[SynthesisConflict]
    ) -> list[str]:
        """Identify caveats and limitations.

        Args:
            inputs: Input items.
            conflicts: Conflicts.

        Returns:
            List of caveats.
        """
        caveats = []

        # Low confidence warning
        avg_confidence = sum(i.confidence for i in inputs) / len(inputs) if inputs else 0
        if avg_confidence < 0.6:
            caveats.append(
                f"Low average confidence in source inputs ({avg_confidence:.2f})"
            )

        # Conflict warnings
        if conflicts:
            unresolved = sum(1 for c in conflicts if c.resolution_confidence < 0.5)
            if unresolved > 0:
                caveats.append(f"{unresolved} conflicts remain unresolved")

        # Small sample warning
        if len(inputs) < 3:
            caveats.append("Limited number of sources analyzed")

        return caveats


# Singleton instance
_agent: SynthesisAgent | None = None


def get_synthesis_agent() -> SynthesisAgent:
    """Get the singleton Synthesis Agent instance.

    Returns:
        Synthesis Agent instance.
    """
    global _agent
    if _agent is None:
        _agent = SynthesisAgent()
    return _agent
