"""Research Agent for deep investigations and information gathering.

This agent performs:
- Multi-step research workflows
- Web search and information synthesis
- Source verification and citation
- Structured research reports
"""

import logging
import uuid
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel, Field

from app.agents.base import BaseAgent
from app.agents.tools import get_tool_manager

logger = logging.getLogger(__name__)


# Research models
class ResearchSource(BaseModel):
    """A source cited in research."""

    url: str = Field(description="URL of the source")
    title: str = Field(description="Title of the source")
    snippet: str = Field(description="Relevant excerpt from the source")
    credibility_score: float = Field(
        ge=0.0, le=1.0, description="Credibility assessment"
    )


class ResearchStep(BaseModel):
    """A step in the research process."""

    step_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    query: str = Field(description="Search query or research question")
    results_count: int = Field(description="Number of results found")
    key_findings: list[str] = Field(default_factory=list)
    sources: list[ResearchSource] = Field(default_factory=list)


class ResearchReport(BaseModel):
    """Complete research report."""

    topic: str = Field(description="Research topic/question")
    summary: str = Field(description="Executive summary of findings")
    key_points: list[str] = Field(description="Key points discovered")
    detailed_findings: str = Field(description="Detailed findings")
    sources: list[ResearchSource] = Field(description="All sources cited")
    steps: list[ResearchStep] = Field(description="Research steps taken")
    confidence: float = Field(
        ge=0.0, le=1.0, description="Confidence in findings"
    )
    limitations: list[str] = Field(
        default_factory=list, description="Known limitations"
    )
    follow_up_questions: list[str] = Field(
        default_factory=list, description="Suggested follow-up questions"
    )


@dataclass
class ResearchConfig:
    """Configuration for research agent."""

    max_sources: int = 10
    max_steps: int = 5
    min_credibility_threshold: float = 0.5
    include_verification: bool = True


class ResearchAgent(BaseAgent):
    """Agent for conducting deep research on topics.

    The research agent:
    1. Decomposes research questions into sub-queries
    2. Executes multi-step web searches
    3. Synthesizes findings from multiple sources
    4. Provides structured reports with citations
    5. Identifies limitations and follow-up questions

    Usage:
        agent = ResearchAgent()
        report = await agent.research("What are the latest developments in AI?")
    """

    def __init__(
        self,
        gateway: Any | None = None,
        model: str = "openai/gpt-4o",
        temperature: float = 0.4,
        config: ResearchConfig | None = None,
    ) -> None:
        """Initialize the Research Agent.

        Args:
            gateway: Gateway client instance.
            model: Model identifier for Gateway.
            temperature: Sampling temperature.
            config: Research configuration.
        """
        super().__init__(gateway=gateway, model=model, temperature=temperature)
        self.config = config or ResearchConfig()
        self.tool_manager = get_tool_manager()

    async def run(self, input_data: dict[str, Any]) -> dict[str, Any]:
        """Run the agent with the given input.

        Args:
            input_data: Must contain 'query' key with research question.

        Returns:
            ResearchReport as dictionary.
        """
        query = input_data.get("query", "")
        if not query:
            raise ValueError("Input data must contain 'query' field")

        max_steps = input_data.get("max_steps", self.config.max_steps)

        report = await self.research(query, max_steps=max_steps)
        return report.model_dump()

    async def research(
        self, query: str, max_steps: int | None = None
    ) -> ResearchReport:
        """Conduct research on a given topic.

        Args:
            query: Research question or topic.
            max_steps: Maximum number of research steps.

        Returns:
            ResearchReport with findings.
        """
        max_steps = max_steps or self.config.max_steps
        steps: list[ResearchStep] = []
        all_sources: list[ResearchSource] = []

        # Step 1: Decompose the query
        sub_queries = await self._decompose_query(query)

        # Step 2: Execute searches for each sub-query
        for sub_query in sub_queries[:max_steps]:
            step_result = await self._execute_research_step(sub_query)
            steps.append(step_result)
            all_sources.extend(step_result.sources)

        # Deduplicate sources
        seen_urls = set()
        unique_sources: list[ResearchSource] = []
        for source in all_sources:
            if source.url not in seen_urls:
                seen_urls.add(source.url)
                unique_sources.append(source)

        all_sources = unique_sources[: self.config.max_sources]

        # Step 3: Synthesize findings
        report = await self._synthesize_report(query, steps, all_sources)
        return report

    async def _decompose_query(self, query: str) -> list[str]:
        """Decompose a research query into sub-queries.

        Args:
            query: Main research query.

        Returns:
            List of sub-queries to research.
        """
        system_prompt = """You are a research assistant. Break down the given research query into 3-5 specific sub-queries that will help thoroughly answer the main question.

Each sub-query should:
- Be specific and search-engine friendly
- Address a different aspect of the topic
- Help build a comprehensive understanding

Return your response as a JSON object with a "sub_queries" array containing strings."""

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Research query: {query}"},
        ]

        try:
            response = await self.generate(messages=messages)
            content = response["choices"][0]["message"]["content"]

            import json

            parsed = json.loads(content)
            return parsed.get("sub_queries", [query])

        except Exception as e:
            logger.warning(f"Query decomposition failed: {e}")
            return [query]

    async def _execute_research_step(self, query: str) -> ResearchStep:
        """Execute a single research step.

        Args:
            query: Search query for this step.

        Returns:
            ResearchStep with findings.
        """
        # Use the web_search tool
        try:
            result = await self.tool_manager.execute_tool(
                "web_search", {"query": query, "num_results": 5}
            )

            if result.success:
                search_results = result.output
                sources: list[ResearchSource] = []
                key_findings: list[str] = []

                for item in search_results.get("results", []):
                    sources.append(
                        ResearchSource(
                            url=item.get("url", ""),
                            title=item.get("title", ""),
                            snippet=item.get("snippet", ""),
                            credibility_score=0.7,  # Default score
                        )
                    )
                    key_findings.append(item.get("title", ""))

                return ResearchStep(
                    query=query,
                    results_count=len(sources),
                    key_findings=key_findings,
                    sources=sources,
                )

        except Exception as e:
            logger.warning(f"Research step failed for query '{query}': {e}")

        # Return empty step on failure
        return ResearchStep(
            query=query, results_count=0, key_findings=[], sources=[]
        )

    async def _synthesize_report(
        self,
        topic: str,
        steps: list[ResearchStep],
        sources: list[ResearchSource],
    ) -> ResearchReport:
        """Synthesize a research report from findings.

        Args:
            topic: Original research topic.
            steps: Research steps executed.
            sources: All sources collected.

        Returns:
            ResearchReport.
        """
        # Build context from findings
        findings_text = "\n\n".join(
            [
                f"Query: {step.query}\nFindings: {', '.join(step.key_findings)}"
                for step in steps
            ]
        )

        sources_text = "\n".join(
            [
                f"- {s.title}: {s.url}\n  {s.snippet[:200]}..."
                for s in sources[:5]
            ]
        )

        system_prompt = """You are a research analyst. Synthesize the research findings into a comprehensive report.

Your report should include:
1. A clear executive summary (2-3 paragraphs)
2. Key points (5-7 bullet points)
3. Detailed findings (structured analysis)
4. Assessment of confidence in the findings
5. Known limitations or gaps
6. Suggested follow-up questions

Be objective, cite sources appropriately, and acknowledge uncertainty."""

        user_prompt = f"""Research Topic: {topic}

Findings from Research Steps:
{findings_text}

Key Sources:
{sources_text}

Synthesize this into a comprehensive research report. Return as JSON with fields: summary, key_points (array), detailed_findings, confidence (0-1), limitations (array), follow_up_questions (array)."""

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        try:
            response = await self.generate(messages=messages)
            content = response["choices"][0]["message"]["content"]

            import json

            parsed = json.loads(content)

            return ResearchReport(
                topic=topic,
                summary=parsed.get("summary", "Research synthesis failed"),
                key_points=parsed.get("key_points", []),
                detailed_findings=parsed.get(
                    "detailed_findings", findings_text
                ),
                sources=sources,
                steps=steps,
                confidence=parsed.get("confidence", 0.5),
                limitations=parsed.get("limitations", []),
                follow_up_questions=parsed.get("follow_up_questions", []),
            )

        except Exception as e:
            logger.error(f"Report synthesis failed: {e}")

            # Return basic report
            return ResearchReport(
                topic=topic,
                summary=f"Research conducted on {topic}. Found {len(sources)} sources.",
                key_points=[f"{len(steps)} research steps completed"],
                detailed_findings=findings_text,
                sources=sources,
                steps=steps,
                confidence=0.5,
                limitations=["Synthesis failed, using raw findings"],
                follow_up_questions=[],
            )


# Singleton instance
_agent: ResearchAgent | None = None


def get_research_agent() -> ResearchAgent:
    """Get the singleton Research Agent instance.

    Returns:
        Research Agent instance.
    """
    global _agent
    if _agent is None:
        _agent = ResearchAgent()
    return _agent
