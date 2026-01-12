"""Tests for PlannerAgent."""

import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.agents.base import BaseAgent
from app.agents.planner_agent import (
    PlannerAgent,
    PlanTask,
    TaskDAG,
    TaskDependency,
)
from app.gateway.client import GatewayClient, GatewayClientError


def build_gateway_response(payload: dict) -> dict:
    """Build a Gateway response payload for structured output."""
    return {"choices": [{"message": {"content": json.dumps(payload)}}]}


class TestPlannerAgent:
    """Tests for PlannerAgent behavior."""

    @pytest.mark.asyncio
    async def test_plan_success_uses_gateway(self):
        """Test planning success via Gateway."""
        mock_gateway = MagicMock(spec=GatewayClient)
        mock_gateway.generate = AsyncMock(
            return_value=build_gateway_response(
                {
                    "plan_metadata": {
                        "goal": "Build a dashboard",
                        "approach": "Create React component with data fetching",
                        "estimated_total_effort": "4 hours",
                        "assumptions": ["Data API is available"],
                        "risks": ["API rate limits"],
                    },
                    "task_dag": {
                        "tasks": [
                            {
                                "id": "task-1",
                                "title": "Design layout",
                                "description": "Create wireframe for dashboard",
                                "status": "pending",
                                "priority": "high",
                                "estimated_effort": "1 hour",
                                "dependencies": [],
                                "linked_node_ids": [],
                            },
                            {
                                "id": "task-2",
                                "title": "Fetch data",
                                "description": "Implement API calls",
                                "status": "pending",
                                "priority": "high",
                                "estimated_effort": "1 hour",
                                "dependencies": ["task-1"],
                                "linked_node_ids": [],
                            },
                        ],
                        "dependencies": [
                            {
                                "task_id": "task-2",
                                "depends_on_task_id": "task-1",
                                "dependency_type": "hard",
                            }
                        ],
                    },
                    "source_references": [],
                    "reasoning": "Clear sequential approach with data dependency",
                    "success": True,
                }
            )
        )

        agent = PlannerAgent(
            gateway=mock_gateway,
            model="test/model",
            temperature=0.4,
        )
        result = await agent.plan("Build a sales dashboard")

        assert result.plan_metadata.goal == "Build a dashboard"
        assert result.plan_metadata.approach == "Create React component with data fetching"
        assert len(result.task_dag.tasks) == 2
        assert result.task_dag.tasks[0].id == "task-1"
        assert result.task_dag.tasks[1].id == "task-2"
        assert result.success is True

        mock_gateway.generate.assert_called_once()
        call_kwargs = mock_gateway.generate.call_args.kwargs
        assert call_kwargs["model"] == "test/model"
        assert call_kwargs["temperature"] == 0.4
        messages = call_kwargs["messages"]
        assert any(m["role"] == "system" for m in messages)
        assert any(m["role"] == "user" for m in messages)

    @pytest.mark.asyncio
    async def test_plan_with_context(self):
        """Test planning with additional context."""
        mock_gateway = MagicMock(spec=GatewayClient)
        mock_gateway.generate = AsyncMock(
            return_value=build_gateway_response(
                {
                    "plan_metadata": {
                        "goal": "Launch feature",
                        "approach": "Incremental rollout",
                        "assumptions": [],
                        "risks": [],
                    },
                    "task_dag": {"tasks": [], "dependencies": []},
                    "source_references": [],
                    "reasoning": "Used context for better planning",
                    "success": True,
                }
            )
        )

        agent = PlannerAgent(gateway=mock_gateway)
        result = await agent.plan(
            "Launch new feature", context="Existing users: 1000, Beta testers available"
        )

        assert result.plan_metadata.goal == "Launch feature"
        call_kwargs = mock_gateway.generate.call_args.kwargs
        user_message = call_kwargs["messages"][1]["content"]
        assert "Beta testers available" in user_message

    @pytest.mark.asyncio
    async def test_plan_gateway_failure_returns_fallback(self):
        """Test Gateway failure yields fallback result."""
        mock_gateway = MagicMock(spec=GatewayClient)
        mock_gateway.generate = AsyncMock(side_effect=GatewayClientError("Gateway failed"))

        agent = PlannerAgent(gateway=mock_gateway)
        result = await agent.plan("Organize conference")

        assert result.success is False
        assert "Fallback plan" in result.plan_metadata.approach
        assert len(result.task_dag.tasks) == 1
        assert result.task_dag.tasks[0].title == "Complete goal manually"
        assert "Gateway failed" in result.reasoning

    @pytest.mark.asyncio
    async def test_plan_invalid_gateway_format_returns_fallback(self):
        """Test invalid Gateway response format triggers fallback."""
        mock_gateway = MagicMock(spec=GatewayClient)
        mock_gateway.generate = AsyncMock(return_value={"invalid": "format"})

        agent = PlannerAgent(gateway=mock_gateway)
        result = await agent.plan("Write book")

        assert result.success is False
        assert "Fallback plan" in result.plan_metadata.approach

    @pytest.mark.asyncio
    async def test_run_requires_goal(self):
        """Test run validates required goal input."""
        agent = PlannerAgent(gateway=MagicMock(spec=GatewayClient))

        with pytest.raises(ValueError, match="goal"):
            await agent.run({})

    @pytest.mark.asyncio
    async def test_run_returns_dict(self):
        """Test run returns serialized result dict."""
        mock_gateway = MagicMock(spec=GatewayClient)
        mock_gateway.generate = AsyncMock(
            return_value=build_gateway_response(
                {
                    "plan_metadata": {
                        "goal": "Deploy app",
                        "approach": "CI/CD pipeline",
                        "assumptions": [],
                        "risks": [],
                    },
                    "task_dag": {"tasks": [], "dependencies": []},
                    "source_references": [],
                    "reasoning": "Standard deployment",
                    "success": True,
                }
            )
        )

        agent = PlannerAgent(gateway=mock_gateway)
        result = await agent.run({"goal": "Deploy app"})

        assert isinstance(result, dict)
        assert result["plan_metadata"]["goal"] == "Deploy app"
        assert result["success"] is True


class TestTaskDAG:
    """Tests for TaskDAG functionality."""

    def test_get_execution_order_simple_chain(self):
        """Test execution order for simple chain of tasks."""
        dag = TaskDAG(
            tasks=[
                PlanTask(id="a", title="Task A", description="First", dependencies=[]),
                PlanTask(id="b", title="Task B", description="Second", dependencies=["a"]),
                PlanTask(id="c", title="Task C", description="Third", dependencies=["b"]),
            ],
            dependencies=[
                TaskDependency(task_id="b", depends_on_task_id="a"),
                TaskDependency(task_id="c", depends_on_task_id="b"),
            ],
        )

        order = dag.get_execution_order()
        assert order == [["a"], ["b"], ["c"]]

    def test_get_execution_order_parallel_tasks(self):
        """Test execution order with parallelizable tasks."""
        dag = TaskDAG(
            tasks=[
                PlanTask(id="a", title="Task A", description="First", dependencies=[]),
                PlanTask(id="b", title="Task B", description="Second", dependencies=["a"]),
                PlanTask(id="c", title="Task C", description="Also second", dependencies=["a"]),
            ],
            dependencies=[
                TaskDependency(task_id="b", depends_on_task_id="a"),
                TaskDependency(task_id="c", depends_on_task_id="a"),
            ],
        )

        order = dag.get_execution_order()
        assert order == [["a"], ["b", "c"]] or order == [["a"], ["c", "b"]]

    def test_get_execution_order_independent_tasks(self):
        """Test execution order with independent tasks."""
        dag = TaskDAG(
            tasks=[
                PlanTask(id="a", title="Task A", description="Independent", dependencies=[]),
                PlanTask(id="b", title="Task B", description="Also independent", dependencies=[]),
            ],
            dependencies=[],
        )

        order = dag.get_execution_order()
        # Both can run in parallel
        assert len(order) == 1
        assert set(order[0]) == {"a", "b"}

    def test_validate_acyclic_valid_dag(self):
        """Test validation of valid acyclic graph."""
        dag = TaskDAG(
            tasks=[
                PlanTask(id="a", title="A", description="A", dependencies=[]),
                PlanTask(id="b", title="B", description="B", dependencies=["a"]),
            ],
            dependencies=[TaskDependency(task_id="b", depends_on_task_id="a")],
        )

        assert dag.validate_acyclic() is True

    def test_validate_acyclic_cycle_detected(self):
        """Test validation detects cycles."""
        dag = TaskDAG(
            tasks=[
                PlanTask(id="a", title="A", description="A", dependencies=["c"]),
                PlanTask(id="b", title="B", description="B", dependencies=["a"]),
                PlanTask(id="c", title="C", description="C", dependencies=["b"]),
            ],
            dependencies=[
                TaskDependency(task_id="b", depends_on_task_id="a"),
                TaskDependency(task_id="c", depends_on_task_id="b"),
                TaskDependency(task_id="a", depends_on_task_id="c"),
            ],
        )

        assert dag.validate_acyclic() is False

    def test_validate_acyclic_self_loop(self):
        """Test validation detects self-loops."""
        dag = TaskDAG(
            tasks=[
                PlanTask(id="a", title="A", description="A", dependencies=["a"]),
            ],
            dependencies=[TaskDependency(task_id="a", depends_on_task_id="a")],
        )

        assert dag.validate_acyclic() is False


class TestGatewayOnlyEnforcement:
    """Tests to verify Gateway-only enforcement for the planner."""

    def test_planner_extends_base_agent(self):
        """Verify PlannerAgent extends BaseAgent."""
        assert issubclass(PlannerAgent, BaseAgent)

    def test_no_direct_provider_imports_in_planner(self):
        """Verify PlannerAgent does not import provider SDKs directly."""
        import inspect

        import app.agents.planner_agent as planner_module

        source = inspect.getsource(planner_module)

        assert "import openai" not in source.lower()
        assert "import anthropic" not in source.lower()
        assert "from openai" not in source.lower()
        assert "from anthropic" not in source.lower()
