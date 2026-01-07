"""Agent Orchestrator with registry pattern for coordinating multiple agents.

The orchestrator provides:
- Dynamic agent discovery and registration
- Workflow composition and execution
- Agent dependency management
- Concurrent execution with isolation
- Lifecycle hooks (pre/post execution)
"""

import asyncio
import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.agents.base import BaseAgent

logger = logging.getLogger(__name__)


# Type aliases for hooks
AgentHook = Callable[[str, dict[str, Any]], Awaitable[None]]
AgentPredicate = Callable[[str, dict[str, Any]], bool]


@dataclass
class AgentMetadata:
    """Metadata for a registered agent."""

    name: str
    agent_class: type[BaseAgent]
    description: str
    capabilities: list[str] = field(default_factory=list)
    default_model: str = "openai/gpt-4o"
    default_temperature: float = 0.7
    singleton: bool = True
    requires_confirmation: bool = False
    max_concurrent: int = 10


class AgentExecutionResult(BaseModel):
    """Result from executing an agent."""

    agent_name: str
    success: bool
    output: dict[str, Any] = Field(default_factory=dict)
    error: str | None = None
    duration_ms: float = 0.0


class WorkflowStep(BaseModel):
    """A single step in an agent workflow."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    agent_name: str
    step_id: str = ""
    input_data: dict[str, Any] = Field(default_factory=dict)
    depends_on: list[str] = Field(default_factory=list)
    continue_on_error: bool = False
    condition: AgentPredicate | None = None


class WorkflowResult(BaseModel):
    """Result from executing a workflow."""

    success: bool
    steps: list[AgentExecutionResult] = Field(default_factory=list)
    total_duration_ms: float = 0.0
    errors: list[str] = Field(default_factory=list)


class AgentRegistry:
    """Registry for managing available agents."""

    def __init__(self) -> None:
        """Initialize the agent registry."""
        self._agents: dict[str, AgentMetadata] = {}
        self._singletons: dict[str, BaseAgent] = {}
        self._semaphores: dict[str, asyncio.Semaphore] = {}
        self._lock = asyncio.Lock()

    def register(self, metadata: AgentMetadata) -> None:
        """Register an agent with the orchestrator.

        Args:
            metadata: Agent metadata including class and configuration.
        """
        if metadata.name in self._agents:
            logger.warning(f"Agent {metadata.name} already registered, overwriting")

        self._agents[metadata.name] = metadata
        self._semaphores[metadata.name] = asyncio.Semaphore(metadata.max_concurrent)

        logger.info(
            f"Registered agent: {metadata.name}",
            extra={"capabilities": metadata.capabilities},
        )

    def unregister(self, name: str) -> None:
        """Unregister an agent.

        Args:
            name: Agent name to unregister.
        """
        self._agents.pop(name, None)
        self._singletons.pop(name, None)
        self._semaphores.pop(name, None)
        logger.info(f"Unregistered agent: {name}")

    def get(self, name: str) -> AgentMetadata | None:
        """Get agent metadata by name.

        Args:
            name: Agent name.

        Returns:
            AgentMetadata if found, None otherwise.
        """
        return self._agents.get(name)

    def list_agents(
        self, capability: str | None = None
    ) -> list[AgentMetadata]:
        """List all registered agents, optionally filtered by capability.

        Args:
            capability: Optional capability filter.

        Returns:
            List of AgentMetadata.
        """
        agents = list(self._agents.values())
        if capability:
            agents = [a for a in agents if capability in a.capabilities]
        return agents

    async def get_instance(self, name: str) -> BaseAgent:
        """Get an agent instance, using singleton if configured.

        Args:
            name: Agent name.

        Returns:
            BaseAgent instance.

        Raises:
            ValueError: If agent not registered.
        """
        metadata = self.get(name)
        if not metadata:
            raise ValueError(f"Agent not registered: {name}")

        if metadata.singleton:
            async with self._lock:
                if name not in self._singletons:
                    self._singletons[name] = metadata.agent_class(
                        model=metadata.default_model,
                        temperature=metadata.default_temperature,
                    )
                return self._singletons[name]

        return metadata.agent_class(
            model=metadata.default_model,
            temperature=metadata.default_temperature,
        )

    def get_semaphore(self, name: str) -> asyncio.Semaphore:
        """Get concurrency semaphore for an agent.

        Args:
            name: Agent name.

        Returns:
            Semaphore for controlling concurrent execution.
        """
        return self._semaphores.get(name, asyncio.Semaphore(10))


class AgentOrchestrator:
    """Orchestrator for coordinating multiple agents.

    Provides workflow composition, parallel execution, and lifecycle management.
    """

    def __init__(self, registry: AgentRegistry | None = None) -> None:
        """Initialize the orchestrator.

        Args:
            registry: Agent registry. If None, creates a new one.
        """
        self.registry = registry or AgentRegistry()
        self._pre_hooks: list[AgentHook] = []
        self._post_hooks: list[AgentHook] = []

    def register_agent(self, metadata: AgentMetadata) -> None:
        """Register an agent with the orchestrator.

        Args:
            metadata: Agent metadata.
        """
        self.registry.register(metadata)

    def add_pre_hook(self, hook: AgentHook) -> None:
        """Add a pre-execution hook.

        Args:
            hook: Async function called before agent execution.
        """
        self._pre_hooks.append(hook)

    def add_post_hook(self, hook: AgentHook) -> None:
        """Add a post-execution hook.

        Args:
            hook: Async function called after agent execution.
        """
        self._post_hooks.append(hook)

    async def execute_agent(
        self,
        name: str,
        input_data: dict[str, Any],
        timeout: float | None = None,
    ) -> AgentExecutionResult:
        """Execute a single agent.

        Args:
            name: Agent name to execute.
            input_data: Input data for the agent.
            timeout: Optional timeout in seconds.

        Returns:
            AgentExecutionResult with output or error.
        """
        import time

        metadata = self.registry.get(name)
        if not metadata:
            return AgentExecutionResult(
                agent_name=name,
                success=False,
                error=f"Agent not registered: {name}",
            )

        # Check if confirmation is required
        if metadata.requires_confirmation:
            input_data["_requires_confirmation"] = True

        # Run pre-hooks
        for hook in self._pre_hooks:
            try:
                await hook(name, input_data)
            except Exception as e:
                logger.warning(f"Pre-hook failed for {name}: {e}")

        start_time = time.time()
        semaphore = self.registry.get_semaphore(name)

        try:
            async with semaphore:
                agent = await self.registry.get_instance(name)

                if timeout:
                    result = await asyncio.wait_for(
                        agent.run(input_data), timeout=timeout
                    )
                else:
                    result = await agent.run(input_data)

                duration_ms = (time.time() - start_time) * 1000

                exec_result = AgentExecutionResult(
                    agent_name=name,
                    success=True,
                    output=result,
                    duration_ms=duration_ms,
                )

        except TimeoutError:
            duration_ms = (time.time() - start_time) * 1000
            exec_result = AgentExecutionResult(
                agent_name=name,
                success=False,
                error=f"Execution timed out after {timeout}s",
                duration_ms=duration_ms,
            )
            logger.error(f"Agent {name} timed out", extra={"timeout": timeout})

        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            exec_result = AgentExecutionResult(
                agent_name=name,
                success=False,
                error=str(e),
                duration_ms=duration_ms,
            )
            logger.error(f"Agent {name} failed", exc_info=True)

        # Run post-hooks
        for hook in self._post_hooks:
            try:
                await hook(name, {"input": input_data, "result": exec_result})
            except Exception as e:
                logger.warning(f"Post-hook failed for {name}: {e}")

        return exec_result

    async def execute_workflow(
        self,
        steps: list[WorkflowStep],
        parallel: bool = False,
        timeout: float | None = None,
    ) -> WorkflowResult:
        """Execute a workflow of agent steps.

        Args:
            steps: List of workflow steps to execute.
            parallel: If True, execute independent steps in parallel.
            timeout: Optional timeout per step in seconds.

        Returns:
            WorkflowResult with all step results.
        """
        import time

        start_time = time.time()
        results: list[AgentExecutionResult] = []
        errors: list[str] = []

        # Build dependency graph
        completed: set[str] = set()
        step_results: dict[str, AgentExecutionResult] = {}

        for step in steps:
            if not step.step_id:
                step.step_id = f"step_{len(results)}"

        if parallel:
            # Execute independent steps in parallel
            while len(completed) < len(steps):
                ready_steps = [
                    s
                    for s in steps
                    if s.step_id not in completed
                    and all(d in completed for d in s.depends_on)
                    and (s.condition is None or s.condition(s.agent_name, s.input_data))
                ]

                if not ready_steps:
                    remaining = [s.step_id for s in steps if s.step_id not in completed]
                    errors.append(f"Circular dependencies detected: {remaining}")
                    break

                # Execute ready steps in parallel
                coroutines = [
                    self._execute_workflow_step(s, timeout, step_results)
                    for s in ready_steps
                ]
                step_results_list = await asyncio.gather(
                    *coroutines, return_exceptions=True
                )

                for step, result in zip(ready_steps, step_results_list):
                    if isinstance(result, Exception):
                        errors.append(f"{step.step_id}: {result}")
                        if not step.continue_on_error:
                            break
                    else:
                        step_results[step.step_id] = result  # type: ignore
                        results.append(result)  # type: ignore
                    completed.add(step.step_id)

        else:
            # Execute sequentially
            for step in steps:
                # Check dependencies
                if not all(d in completed for d in step.depends_on):
                    errors.append(f"{step.step_id}: Dependencies not satisfied")
                    continue

                # Check condition
                if step.condition and not step.condition(
                    step.agent_name, step.input_data
                ):
                    logger.info(f"Skipping {step.step_id}: Condition not met")
                    continue

                result = await self._execute_workflow_step(step, timeout, step_results)
                step_results[step.step_id] = result
                results.append(result)

                if not result.success and not step.continue_on_error:
                    errors.append(result.error or "Unknown error")
                    break

                completed.add(step.step_id)

        total_duration_ms = (time.time() - start_time) * 1000
        success = all(r.success for r in results) and not errors

        return WorkflowResult(
            success=success,
            steps=results,
            total_duration_ms=total_duration_ms,
            errors=errors,
        )

    async def _execute_workflow_step(
        self,
        step: WorkflowStep,
        timeout: float | None,
        previous_results: dict[str, AgentExecutionResult],
    ) -> AgentExecutionResult:
        """Execute a single workflow step.

        Args:
            step: Workflow step to execute.
            timeout: Optional timeout.
            previous_results: Results from previous steps.

        Returns:
            AgentExecutionResult.
        """
        # Merge previous results into input if specified
        input_data = dict(step.input_data)
        for dep_id in step.depends_on:
            if dep_id in previous_results:
                dep_result = previous_results[dep_id]
                if dep_result.success:
                    input_data[f"_from_{dep_id}"] = dep_result.output

        return await self.execute_agent(step.agent_name, input_data, timeout)

    async def execute_parallel(
        self,
        executions: list[tuple[str, dict[str, Any]]],
        timeout: float | None = None,
    ) -> list[AgentExecutionResult]:
        """Execute multiple agents in parallel.

        Args:
            executions: List of (agent_name, input_data) tuples.
            timeout: Optional timeout per execution.

        Returns:
            List of AgentExecutionResult.
        """
        coroutines = [
            self.execute_agent(name, data, timeout) for name, data in executions
        ]
        results = await asyncio.gather(*coroutines, return_exceptions=True)

        output: list[AgentExecutionResult] = []
        for i, r in enumerate(results):
            if isinstance(r, Exception):
                name, _ = executions[i]
                output.append(
                    AgentExecutionResult(
                        agent_name=name, success=False, error=str(r)
                    )
                )
            else:
                output.append(r)  # type: ignore

        return output


# Global orchestrator instance
_orchestrator: AgentOrchestrator | None = None


def get_orchestrator() -> AgentOrchestrator:
    """Get the global orchestrator instance.

    Returns:
        AgentOrchestrator instance.
    """
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = AgentOrchestrator()
    return _orchestrator


def get_registry() -> AgentRegistry:
    """Get the global agent registry.

    Returns:
        AgentRegistry instance.
    """
    return get_orchestrator().registry
