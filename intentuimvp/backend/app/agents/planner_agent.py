"""Planner Agent for generating structured plans with task dependencies.

This agent analyzes user goals and context to generate:
- Structured plans with clear objectives
- Decomposed tasks with dependencies
- Task DAG (Directed Acyclic Graph) for execution order
- Links to relevant sources and existing nodes
"""

import logging
import uuid
from typing import Any

from pydantic import BaseModel, Field

from app.agents.base import BaseAgent

logger = logging.getLogger(__name__)


# Request/Response models for Planner


class TaskDependency(BaseModel):
    """A dependency relationship between tasks."""

    task_id: str = Field(description="ID of the task that depends on another")
    depends_on_task_id: str = Field(description="ID of the task this depends on")
    dependency_type: str = Field(
        default="hard",
        description="Type of dependency: 'hard' (must complete first) or 'soft' (recommended order)",
    )


class PlanTask(BaseModel):
    """A single task within a plan."""

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    title: str = Field(description="Brief title for the task")
    description: str = Field(description="Detailed description of what the task involves")
    status: str = Field(
        default="pending",
        description="Task status: pending, in_progress, completed, blocked",
    )
    priority: str = Field(
        default="medium",
        description="Task priority: high, medium, low",
    )
    estimated_effort: str | None = Field(
        default=None,
        description="Estimated effort (e.g., '30 minutes', '2 hours', '1 day')",
    )
    dependencies: list[str] = Field(
        default_factory=list,
        description="IDs of tasks this task depends on",
    )
    linked_node_ids: list[str] = Field(
        default_factory=list,
        description="IDs of existing canvas nodes this task references",
    )
    calendar_suggestion: dict[str, Any] | None = Field(
        default=None,
        description="Optional calendar event suggestion for this task",
    )


class TaskDAG(BaseModel):
    """Directed Acyclic Graph representing task dependencies."""

    tasks: list[PlanTask] = Field(description="All tasks in the plan")
    dependencies: list[TaskDependency] = Field(
        default_factory=list,
        description="Dependency relationships between tasks",
    )

    def get_execution_order(self) -> list[list[str]]:
        """Calculate topological order for task execution.

        Returns:
            List of task ID layers where each layer can execute in parallel.
        """
        # Build adjacency list and in-degree count
        in_degree: dict[str, int] = {task.id: 0 for task in self.tasks}
        adj_list: dict[str, list[str]] = {task.id: [] for task in self.tasks}

        for dep in self.dependencies:
            if (
                dep.depends_on_task_id in adj_list
                and dep.task_id in adj_list
                and dep.depends_on_task_id != dep.task_id
            ):
                adj_list[dep.depends_on_task_id].append(dep.task_id)
                in_degree[dep.task_id] += 1

        # Kahn's algorithm for topological sort with layer detection
        layers: list[list[str]] = []
        remaining = set(in_degree.keys())

        while remaining:
            # Find all tasks with no dependencies in remaining set
            ready = [tid for tid in remaining if in_degree[tid] == 0]

            if not ready:
                # Cycle detected - break to avoid infinite loop
                logger.warning("Cycle detected in task dependencies")
                break

            layers.append(ready)

            # Remove ready tasks and update in-degrees
            for tid in ready:
                remaining.remove(tid)
                for neighbor in adj_list[tid]:
                    if neighbor in remaining:
                        in_degree[neighbor] -= 1

        return layers

    def validate_acyclic(self) -> bool:
        """Validate that the DAG is actually acyclic.

        Returns:
            True if acyclic, False if cycle detected.
        """
        task_ids = {task.id for task in self.tasks}
        visited: set[str] = set()
        rec_stack: set[str] = set()

        adj_list: dict[str, list[str]] = {task.id: [] for task in self.tasks}
        for dep in self.dependencies:
            if dep.depends_on_task_id in adj_list and dep.task_id in adj_list:
                adj_list[dep.depends_on_task_id].append(dep.task_id)

        def has_cycle(task_id: str) -> bool:
            visited.add(task_id)
            rec_stack.add(task_id)

            for neighbor in adj_list[task_id]:
                if neighbor not in visited:
                    if has_cycle(neighbor):
                        return True
                elif neighbor in rec_stack:
                    return True

            rec_stack.remove(task_id)
            return False

        for task_id in task_ids:
            if task_id not in visited:
                if has_cycle(task_id):
                    return False

        return True


class PlanMetadata(BaseModel):
    """Metadata about the generated plan."""

    goal: str = Field(description="The original goal the plan addresses")
    approach: str = Field(description="High-level approach or strategy")
    estimated_total_effort: str | None = Field(
        default=None,
        description="Estimated total effort for all tasks",
    )
    assumptions: list[str] = Field(
        default_factory=list,
        description="Assumptions made in generating the plan",
    )
    risks: list[str] = Field(
        default_factory=list,
        description="Potential risks or blockers identified",
    )


class PlannerResult(BaseModel):
    """Result from the planner agent."""

    plan_metadata: PlanMetadata = Field(description="Metadata about the plan")
    task_dag: TaskDAG = Field(description="The task dependency graph")
    source_references: list[dict[str, Any]] = Field(
        default_factory=list,
        description="References to source materials or context used",
    )
    reasoning: str = Field(description="Explanation of the planning process")
    success: bool = Field(default=True, description="Whether planning succeeded")


class PlannerAgent(BaseAgent):
    """Agent for generating structured plans with task dependencies.

    This agent uses the Gateway to analyze user goals and generate:
    - Structured plans with clear objectives and approach
    - Decomposed tasks with priorities and effort estimates
    - Task DAG showing dependency relationships
    - Execution order (topological sort) for parallelizable work

    Usage:
        agent = PlannerAgent()
        result = await agent.plan("Launch a new product feature")
    """

    def __init__(
        self,
        gateway: Any | None = None,
        model: str = "openai/gpt-4o",
        temperature: float = 0.5,  # Balanced temperature for creative but structured planning
    ) -> None:
        """Initialize the Planner Agent.

        Args:
            gateway: Gateway client instance. If None, uses singleton.
            model: Model identifier for Gateway.
            temperature: Sampling temperature (mid-range for structured creativity).
        """
        super().__init__(gateway=gateway, model=model, temperature=temperature)

    async def run(self, input_data: dict[str, Any]) -> dict[str, Any]:
        """Run the agent with the given input.

        Args:
            input_data: Must contain 'goal' key with user goal. Optionally 'context'.

        Returns:
            PlannerResult as dictionary.
        """
        goal = input_data.get("goal", "")
        if not goal:
            raise ValueError("Input data must contain 'goal' field")

        context = input_data.get("context", "")
        result = await self.plan(goal, context)
        return result.model_dump()

    async def plan(self, goal: str, context: str = "") -> PlannerResult:
        """Generate a structured plan for the given goal.

        Args:
            goal: The user's goal or objective.
            context: Optional additional context (selected nodes, workspace state, etc.).

        Returns:
            PlannerResult with plan metadata and task DAG.
        """
        system_prompt = self._build_system_prompt()
        user_prompt = self._build_user_prompt(goal, context)

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        try:
            result = await self.generate_structured(
                messages=messages,
                response_model=PlannerResult,
            )

            # Validate DAG is acyclic
            if not result.task_dag.validate_acyclic():
                logger.warning("Generated plan has cycles in task dependencies")
                result.success = False
                result.reasoning += " [WARNING: Cycle detected in dependencies]"

            return result

        except Exception as e:
            logger.error(f"Planning failed: {e}", exc_info=True)
            return self._fallback_result(goal, str(e))

    def _build_system_prompt(self) -> str:
        """Build the system prompt for planning."""
        return """You are a Planning Agent for a canvas-based agentic workspace.

Your task is to analyze user goals and generate structured plans with:
1. **Plan Metadata**: Goal, approach, estimated effort, assumptions, risks
2. **Task DAG**: Decomposed tasks with dependencies forming a Directed Acyclic Graph
3. **Execution Order**: Tasks should be ordered so dependent tasks run after their dependencies

Task Requirements:
- Each task should have a clear title and description
- Tasks should be atomic and achievable
- Dependencies should form a DAG (no cycles!)
- Estimate effort when possible (e.g., "30 minutes", "2 hours", "1 day")
- Set appropriate priority levels (high, medium, low)

Dependency Types:
- "hard": Task MUST complete before dependent task can start
- "soft": Recommended order but not strictly required

Output a complete, valid plan that can be executed to achieve the user's goal."""

    def _build_user_prompt(self, goal: str, context: str) -> str:
        """Build the user prompt from the input."""
        prompt = f"""Create a structured plan for this goal:

"{goal}"
"""

        if context:
            prompt += f"\nAdditional context:\n{context}\n"

        prompt += """
Generate:
1. A clear approach description
2. 3-10 atomic tasks needed to achieve this goal
3. Dependencies between tasks (what must complete before what)
4. Effort estimates for each task
5. Any assumptions or risks

Ensure tasks form a valid DAG (no circular dependencies)."""

        return prompt

    def _fallback_result(self, goal: str, error_message: str) -> PlannerResult:
        """Return a safe fallback result when planning fails.

        Args:
            goal: The original goal.
            error_message: Error message to include in reasoning.

        Returns:
            Minimal PlannerResult.
        """
        return PlannerResult(
            plan_metadata=PlanMetadata(
                goal=goal,
                approach="Fallback plan due to processing error",
                assumptions=[],
                risks=[f"Planning error: {error_message}"],
            ),
            task_dag=TaskDAG(
                tasks=[
                    PlanTask(
                        id=str(uuid.uuid4()),
                        title="Complete goal manually",
                        description=f"Work toward goal: {goal}",
                        status="pending",
                        priority="medium",
                    )
                ],
                dependencies=[],
            ),
            reasoning=f"Planning encountered an error: {error_message}",
            success=False,
        )


# Singleton instance
_agent: PlannerAgent | None = None


def get_planner() -> PlannerAgent:
    """Get the singleton Planner Agent instance.

    Returns:
        Planner Agent instance.
    """
    global _agent
    if _agent is None:
        _agent = PlannerAgent()
    return _agent
