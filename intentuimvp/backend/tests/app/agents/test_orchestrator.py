"""Tests for Agent Orchestrator and Registry."""


import pytest

from app.agents.base import BaseAgent
from app.agents.orchestrator import (
    AgentMetadata,
    AgentOrchestrator,
    AgentRegistry,
    WorkflowStep,
    get_orchestrator,
    get_registry,
)


class DummyAgent2(BaseAgent):
    """Test agent for orchestrator."""

    async def run(self, input_data: dict):
        return {"result": f"processed: {input_data.get('value', '')}"}


class FailingAgent(BaseAgent):
    """Test agent that always fails."""

    async def run(self, input_data: dict):
        raise ValueError("Intentional failure")


class TestAgentRegistry:
    """Tests for AgentRegistry."""

    def test_register_agent(self):
        """Test registering an agent."""
        registry = AgentRegistry()
        metadata = AgentMetadata(
            name="test_agent",
            agent_class=DummyAgent2,
            description="Test agent",
            capabilities=["test"],
        )

        registry.register(metadata)

        assert registry.get("test_agent") is metadata
        assert len(registry.list_agents()) == 1

    def test_register_duplicate_overwrites(self):
        """Test that registering duplicate overwrites."""
        registry = AgentRegistry()
        metadata1 = AgentMetadata(
            name="test_agent",
            agent_class=DummyAgent2,
            description="First",
        )
        metadata2 = AgentMetadata(
            name="test_agent",
            agent_class=DummyAgent2,
            description="Second",
        )

        registry.register(metadata1)
        registry.register(metadata2)

        assert registry.get("test_agent").description == "Second"

    def test_unregister_agent(self):
        """Test unregistering an agent."""
        registry = AgentRegistry()
        metadata = AgentMetadata(
            name="test_agent",
            agent_class=DummyAgent2,
            description="Test",
        )

        registry.register(metadata)
        assert registry.get("test_agent") is not None

        registry.unregister("test_agent")
        assert registry.get("test_agent") is None

    def test_list_agents_filter_by_capability(self):
        """Test listing agents with capability filter."""
        registry = AgentRegistry()

        registry.register(
            AgentMetadata(
                name="agent1",
                agent_class=DummyAgent2,
                description="Agent 1",
                capabilities=["read", "write"],
            )
        )
        registry.register(
            AgentMetadata(
                name="agent2",
                agent_class=DummyAgent2,
                description="Agent 2",
                capabilities=["read"],
            )
        )

        read_agents = registry.list_agents(capability="read")
        assert len(read_agents) == 2

        write_agents = registry.list_agents(capability="write")
        assert len(write_agents) == 1

    @pytest.mark.asyncio
    async def test_get_singleton_instance(self):
        """Test getting singleton agent instance."""
        registry = AgentRegistry()
        metadata = AgentMetadata(
            name="test_agent",
            agent_class=DummyAgent2,
            description="Test",
            singleton=True,
        )

        registry.register(metadata)

        instance1 = await registry.get_instance("test_agent")
        instance2 = await registry.get_instance("test_agent")

        assert instance1 is instance2

    @pytest.mark.asyncio
    async def test_get_non_singleton_instance(self):
        """Test getting non-singleton agent instance."""
        registry = AgentRegistry()
        metadata = AgentMetadata(
            name="test_agent",
            agent_class=DummyAgent2,
            description="Test",
            singleton=False,
        )

        registry.register(metadata)

        instance1 = await registry.get_instance("test_agent")
        instance2 = await registry.get_instance("test_agent")

        assert instance1 is not instance2


class TestAgentOrchestrator:
    """Tests for AgentOrchestrator."""

    def test_init_with_custom_registry(self):
        """Test initialization with custom registry."""
        custom_registry = AgentRegistry()
        orchestrator = AgentOrchestrator(registry=custom_registry)

        assert orchestrator.registry is custom_registry

    def test_register_agent(self):
        """Test registering agent through orchestrator."""
        orchestrator = AgentOrchestrator()
        metadata = AgentMetadata(
            name="test_agent",
            agent_class=DummyAgent2,
            description="Test",
        )

        orchestrator.register_agent(metadata)

        assert orchestrator.registry.get("test_agent") is metadata

    def test_add_hooks(self):
        """Test adding pre and post hooks."""
        orchestrator = AgentOrchestrator()

        async def pre_hook(name, data):
            pass

        async def post_hook(name, data):
            pass

        orchestrator.add_pre_hook(pre_hook)
        orchestrator.add_post_hook(post_hook)

        assert len(orchestrator._pre_hooks) == 1
        assert len(orchestrator._post_hooks) == 1

    @pytest.mark.asyncio
    async def test_execute_agent_success(self):
        """Test successful agent execution."""
        orchestrator = AgentOrchestrator()
        metadata = AgentMetadata(
            name="test_agent",
            agent_class=DummyAgent2,
            description="Test",
            singleton=True,
        )

        orchestrator.register_agent(metadata)

        result = await orchestrator.execute_agent(
            "test_agent", {"value": "hello"}
        )

        assert result.success
        assert result.output == {"result": "processed: hello"}
        assert result.agent_name == "test_agent"
        assert result.duration_ms > 0

    @pytest.mark.asyncio
    async def test_execute_agent_not_registered(self):
        """Test executing non-existent agent."""
        orchestrator = AgentOrchestrator()

        result = await orchestrator.execute_agent("nonexistent", {})

        assert not result.success
        assert "not registered" in result.error

    @pytest.mark.asyncio
    async def test_execute_agent_failure(self):
        """Test agent execution with failure."""
        orchestrator = AgentOrchestrator()
        metadata = AgentMetadata(
            name="failing_agent",
            agent_class=FailingAgent,
            description="Failing",
            singleton=True,
        )

        orchestrator.register_agent(metadata)

        result = await orchestrator.execute_agent("failing_agent", {})

        assert not result.success
        assert "Intentional failure" in result.error

    @pytest.mark.asyncio
    async def test_execute_agent_with_timeout(self):
        """Test agent execution with timeout."""
        orchestrator = AgentOrchestrator()

        # Create a slow agent
        class SlowAgent(BaseAgent):
            async def run(self, input_data: dict):
                import asyncio

                await asyncio.sleep(2)
                return {"done": True}

        metadata = AgentMetadata(
            name="slow_agent",
            agent_class=SlowAgent,
            description="Slow",
            singleton=True,
        )

        orchestrator.register_agent(metadata)

        result = await orchestrator.execute_agent("slow_agent", {}, timeout=0.1)

        assert not result.success
        assert "timed out" in result.error

    @pytest.mark.asyncio
    async def test_execute_parallel(self):
        """Test parallel execution of multiple agents."""
        orchestrator = AgentOrchestrator()
        metadata = AgentMetadata(
            name="test_agent",
            agent_class=DummyAgent2,
            description="Test",
            singleton=True,
        )

        orchestrator.register_agent(metadata)

        results = await orchestrator.execute_parallel(
            [
                ("test_agent", {"value": "a"}),
                ("test_agent", {"value": "b"}),
                ("test_agent", {"value": "c"}),
            ]
        )

        assert len(results) == 3
        assert all(r.success for r in results)
        assert results[0].output == {"result": "processed: a"}
        assert results[1].output == {"result": "processed: b"}
        assert results[2].output == {"result": "processed: c"}

    @pytest.mark.asyncio
    async def test_execute_workflow_sequential(self):
        """Test sequential workflow execution."""
        orchestrator = AgentOrchestrator()
        metadata = AgentMetadata(
            name="test_agent",
            agent_class=DummyAgent2,
            description="Test",
            singleton=True,
        )

        orchestrator.register_agent(metadata)

        steps = [
            WorkflowStep(agent_name="test_agent", step_id="step1", input_data={"value": "a"}),
            WorkflowStep(agent_name="test_agent", step_id="step2", input_data={"value": "b"}),
            WorkflowStep(agent_name="test_agent", step_id="step3", input_data={"value": "c"}),
        ]

        result = await orchestrator.execute_workflow(steps, parallel=False)

        assert result.success
        assert len(result.steps) == 3
        assert all(s.success for s in result.steps)

    @pytest.mark.asyncio
    async def test_execute_workflow_with_dependencies(self):
        """Test workflow with step dependencies."""
        orchestrator = AgentOrchestrator()
        metadata = AgentMetadata(
            name="test_agent",
            agent_class=DummyAgent2,
            description="Test",
            singleton=True,
        )

        orchestrator.register_agent(metadata)

        steps = [
            WorkflowStep(agent_name="test_agent", step_id="step1", input_data={"value": "a"}),
            WorkflowStep(
                agent_name="test_agent",
                step_id="step2",
                input_data={},
                depends_on=["step1"],
            ),
            WorkflowStep(
                agent_name="test_agent",
                step_id="step3",
                input_data={},
                depends_on=["step2"],
            ),
        ]

        result = await orchestrator.execute_workflow(steps, parallel=False)

        assert result.success
        assert len(result.steps) == 3

    @pytest.mark.asyncio
    async def test_execute_workflow_continue_on_error(self):
        """Test workflow with continue_on_error flag."""
        orchestrator = AgentOrchestrator()

        success_metadata = AgentMetadata(
            name="success_agent",
            agent_class=DummyAgent2,
            description="Success",
            singleton=True,
        )
        fail_metadata = AgentMetadata(
            name="failing_agent",
            agent_class=FailingAgent,
            description="Failing",
            singleton=True,
        )

        orchestrator.register_agent(success_metadata)
        orchestrator.register_agent(fail_metadata)

        steps = [
            WorkflowStep(agent_name="success_agent", step_id="step1", input_data={"value": "a"}),
            WorkflowStep(
                agent_name="failing_agent",
                step_id="step2",
                input_data={},
                continue_on_error=True,
            ),
            WorkflowStep(agent_name="success_agent", step_id="step3", input_data={"value": "c"}),
        ]

        result = await orchestrator.execute_workflow(steps, parallel=False)

        # Should succeed overall because we continue on error
        assert len(result.steps) == 3
        assert result.steps[0].success
        assert not result.steps[1].success
        assert result.steps[2].success


class TestGlobalOrchestrator:
    """Tests for global orchestrator functions."""

    def test_get_orchestrator_singleton(self):
        """Test that get_orchestrator returns singleton."""
        orch1 = get_orchestrator()
        orch2 = get_orchestrator()

        assert orch1 is orch2

    def test_get_registry(self):
        """Test that get_registry returns orchestrator's registry."""
        registry = get_registry()

        assert registry is get_orchestrator().registry
