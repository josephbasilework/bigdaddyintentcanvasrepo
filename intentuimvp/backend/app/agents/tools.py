"""Tool calling with structured validation for agent operations.

Provides:
- Tool discovery and registration
- Structured argument validation with Pydantic
- Tool execution with error handling
- Integration with MCP tools
- Automatic tool recommendation for agents
"""

import json
import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC
from typing import Any, Literal

from pydantic import BaseModel, Field, ValidationError
from sqlalchemy import or_, select

from app.database import AsyncSessionLocal
from app.models.canvas import Canvas
from app.models.edge import RelationType
from app.models.node import Node, NodeType
from app.repositories.canvas_repo import CanvasRepository
from app.repositories.edge_repo import EdgeRepository
from app.repositories.node_repo import NodeRepository

logger = logging.getLogger(__name__)

DEFAULT_USER_ID = "default_user"

# MCP integration is optional - requires database session
# Tools will work without MCP, just MCP-specific tools won't be available
try:
    from app.mcp.registry import MCPServerRegistry
    MCP_AVAILABLE = True
except ImportError:
    MCP_AVAILABLE = False
    MCPServerRegistry = None  # type: ignore


# Type aliases
ToolFunc = Callable[..., Any]
AsyncToolFunc = Callable[..., Awaitable[Any]]


@dataclass
class ToolMetadata:
    """Metadata for a registered tool."""

    name: str
    description: str
    parameters: type[BaseModel] | None = None
    function: ToolFunc | AsyncToolFunc | None = None
    is_async: bool = False
    mcp_server: str | None = None
    mcp_tool_name: str | None = None
    dangerous: bool = False
    requires_confirmation: bool = False


class ToolExecutionResult(BaseModel):
    """Result from executing a tool."""

    tool_name: str
    success: bool
    output: Any = None
    error: str | None = None
    execution_time_ms: float = 0.0


class ToolRecommendation(BaseModel):
    """Recommended tool for an agent request."""

    tool_name: str
    confidence: float
    reason: str
    suggested_arguments: dict[str, Any] = Field(default_factory=dict)


class CanvasNodePosition(BaseModel):
    """Position coordinates for a canvas node."""

    x: float = Field(..., description="X coordinate")
    y: float = Field(..., description="Y coordinate")
    z: float = Field(..., description="Z coordinate")


class CanvasCreateNodeParams(BaseModel):
    """Parameters for creating a canvas node."""

    type: NodeType = Field(..., description="Node type")
    content: str = Field(..., min_length=1, description="Node content/label")
    position: CanvasNodePosition = Field(..., description="Node position")
    metadata: dict[str, Any] | None = Field(
        default=None, description="Optional node metadata"
    )


class CanvasUpdateNodePosition(BaseModel):
    """Partial updates to node position."""

    x: float | None = Field(default=None, description="X coordinate")
    y: float | None = Field(default=None, description="Y coordinate")
    z: float | None = Field(default=None, description="Z coordinate")


class CanvasUpdateNodePatch(BaseModel):
    """Patch fields for updating a canvas node."""

    label: str | None = Field(default=None, description="Updated node label")
    content: str | None = Field(
        default=None, description="Updated node content (alias for label)"
    )
    type: NodeType | None = Field(default=None, description="Updated node type")
    position: CanvasUpdateNodePosition | None = Field(
        default=None, description="Updated node position"
    )
    metadata: dict[str, Any] | None = Field(
        default=None, description="Updated node metadata"
    )


class CanvasUpdateNodeParams(BaseModel):
    """Parameters for updating a canvas node."""

    node_id: int = Field(..., ge=1, description="Node identifier")
    patch: CanvasUpdateNodePatch = Field(
        ..., description="Fields to update on the node"
    )

class CanvasLinkNodesParams(BaseModel):
    """Parameters for linking two nodes."""

    from_id: int = Field(..., ge=1, description="Source node identifier")
    to_id: int = Field(..., ge=1, description="Target node identifier")
    relation_type: RelationType = Field(
        default=RelationType.DEPENDS_ON,
        description="Edge relation type",
    )
    metadata: dict[str, Any] | None = Field(
        default=None,
        description="Optional edge metadata",
    )


class WorkspaceSearchParams(BaseModel):
    """Parameters for searching nodes/documents in the workspace."""

    query: str = Field(..., min_length=1, description="Search query")
    scope: Literal["selection", "canvas", "all"] = Field(
        ..., description="Search scope"
    )
    selection_ids: list[int] | None = Field(
        default=None, description="Optional selected node IDs for selection scope"
    )
    canvas_id: int | None = Field(
        default=None, description="Optional canvas ID for canvas scope"
    )


class ToolValidationError(Exception):
    """Exception raised when tool validation fails."""

    def __init__(
        self, tool_name: str, errors: list[str], validation_errors: Any = None
    ) -> None:
        """Initialize the validation error.

        Args:
            tool_name: Name of the tool that failed validation.
            errors: List of error messages.
            validation_errors: Pydantic ValidationError if available.
        """
        self.tool_name = tool_name
        self.errors = errors
        self.validation_errors = validation_errors
        super().__init__(f"Tool {tool_name} validation failed: {', '.join(errors)}")


class ToolManager:
    """Manager for tool registration, validation, and execution."""

    def __init__(self) -> None:
        """Initialize the tool manager."""
        self._tools: dict[str, ToolMetadata] = {}
        self._register_builtin_tools()

    def _register_builtin_tools(self) -> None:
        """Register built-in tools."""

        async def web_search(query: str, num_results: int = 5) -> dict[str, Any]:
            """Search the web for information."""
            # Placeholder - would integrate with actual search
            return {
                "query": query,
                "results": [
                    {"title": f"Result {i}", "url": f"https://example.com/{i}"}
                    for i in range(num_results)
                ],
            }

        async def read_file(path: str, encoding: str = "utf-8") -> str:
            """Read a file from the filesystem."""
            try:
                with open(path, encoding=encoding) as f:
                    return f.read()
            except Exception as e:
                raise FileNotFoundError(f"Could not read file: {e}")

        async def write_file(path: str, content: str, encoding: str = "utf-8") -> dict:
            """Write content to a file."""
            try:
                with open(path, "w", encoding=encoding) as f:
                    f.write(content)
                return {"path": path, "bytes_written": len(content.encode(encoding))}
            except Exception as e:
                raise OSError(f"Could not write file: {e}")

        async def get_current_time(tz_name: str = "UTC") -> dict:
            """Get the current time."""
            from datetime import datetime

            tz = UTC if tz_name == "UTC" else None
            return {
                "timezone": tz_name,
                "datetime": datetime.now(tz).isoformat(),
                "timestamp": datetime.now(tz).timestamp(),
            }

        async def calculate(expression: str) -> dict:
            """Safely calculate a mathematical expression."""
            import ast

            try:
                # Only allow basic arithmetic operations
                node = ast.parse(expression, mode="eval")
                for child in ast.walk(node):
                    if isinstance(child, (ast.BinOp, ast.UnaryOp, ast.Num, ast.Constant)):  # noqa: UP038
                        continue
                    if isinstance(  # noqa: UP038
                        child,
                        (
                            ast.Add,
                            ast.Sub,
                            ast.Mult,
                            ast.Div,
                            ast.Pow,
                            ast.Mod,
                            ast.USub,
                        ),
                    ):
                        continue
                    raise ValueError(f"Disallowed operation: {type(child).__name__}")

                result = eval(compile(node, "<string>", "eval"))
                return {"expression": expression, "result": result}
            except Exception as e:
                raise ValueError(f"Invalid expression: {e}")

        async def canvas_create_node(
            type: NodeType,
            content: str,
            position: CanvasNodePosition | dict[str, Any],
            metadata: dict[str, Any] | None = None,
        ) -> dict[str, Any]:
            """Create a new canvas node in the workspace."""
            parsed_position = (
                position
                if isinstance(position, CanvasNodePosition)
                else CanvasNodePosition.model_validate(position)
            )
            params = CanvasCreateNodeParams(
                type=type,
                content=content,
                position=parsed_position,
                metadata=metadata,
            )

            async with AsyncSessionLocal() as session:
                canvas_repo = CanvasRepository(session)
                canvases = await canvas_repo.get_by_user(
                    DEFAULT_USER_ID, limit=1
                )
                canvas = (
                    canvases[0]
                    if canvases
                    else await canvas_repo.create_canvas(
                        user_id=DEFAULT_USER_ID, name="default"
                    )
                )

                node_repo = NodeRepository(session)
                node = await node_repo.create_node(
                    canvas_id=canvas.id,
                    label=params.content,
                    type=params.type,
                    position=params.position.model_dump(),
                    node_metadata=params.metadata,
                )

            return {"id": node.id}

        async def canvas_update_node(
            node_id: int,
            patch: CanvasUpdateNodePatch | dict[str, Any],
        ) -> dict[str, Any]:
            """Update an existing canvas node."""
            parsed_patch = (
                patch
                if isinstance(patch, CanvasUpdateNodePatch)
                else CanvasUpdateNodePatch.model_validate(patch)
            )
            fields_set = parsed_patch.model_fields_set
            if not fields_set:
                raise ValueError("No fields to update")

            async with AsyncSessionLocal() as session:
                node_repo = NodeRepository(session)
                node = await node_repo.get_by_id(node_id)
                if node is None:
                    raise ValueError(f"Node not found: {node_id}")

                updates: dict[str, Any] = {}

                label_value: str | None = None
                if "label" in fields_set:
                    if parsed_patch.label is None:
                        raise ValueError("Label cannot be null")
                    label_value = parsed_patch.label
                elif "content" in fields_set:
                    if parsed_patch.content is None:
                        raise ValueError("Content cannot be null")
                    label_value = parsed_patch.content

                if label_value is not None:
                    updates["label"] = label_value

                if "type" in fields_set:
                    if parsed_patch.type is None:
                        raise ValueError("Type cannot be null")
                    updates["type"] = parsed_patch.type

                if "metadata" in fields_set:
                    if parsed_patch.metadata is None:
                        updates["node_metadata"] = None
                    else:
                        updates["node_metadata"] = json.dumps(
                            parsed_patch.metadata
                        )

                if "position" in fields_set:
                    if parsed_patch.position is None:
                        updated_position = {"x": 0, "y": 0, "z": 0}
                    else:
                        position_updates = parsed_patch.position.model_dump(
                            exclude_unset=True
                        )
                        position_updates = {
                            key: value
                            for key, value in position_updates.items()
                            if value is not None
                        }
                        current_position = node.get_position()
                        updated_position = (
                            {**current_position, **position_updates}
                            if position_updates
                            else current_position
                        )
                    updates["position"] = json.dumps(updated_position)

                if not updates:
                    raise ValueError("No fields to update")

                updated_node = await node_repo.update(node_id, **updates)
                if updated_node is None:
                    raise ValueError(f"Node not found: {node_id}")

            return updated_node.to_dict()

        async def canvas_link_nodes(
            from_id: int,
            to_id: int,
            relation_type: RelationType,
            metadata: dict[str, Any] | None = None,
        ) -> dict[str, Any]:
            """Create a new edge between two nodes."""
            params = CanvasLinkNodesParams(
                from_id=from_id,
                to_id=to_id,
                relation_type=relation_type,
                metadata=metadata,
            )

            async with AsyncSessionLocal() as session:
                node_repo = NodeRepository(session)
                from_node = await node_repo.get_by_id(params.from_id)
                if from_node is None:
                    raise ValueError(
                        f"Source node not found: {params.from_id}"
                    )

                to_node = await node_repo.get_by_id(params.to_id)
                if to_node is None:
                    raise ValueError(
                        f"Target node not found: {params.to_id}"
                    )

                if from_node.canvas_id != to_node.canvas_id:
                    raise ValueError(
                        "Nodes must belong to the same canvas"
                    )

                edge_repo = EdgeRepository(session)
                edge = await edge_repo.create_edge(
                    canvas_id=from_node.canvas_id,
                    from_node_id=from_node.id,
                    to_node_id=to_node.id,
                    relation_type=params.relation_type,
                )

            return {"id": edge.id}

        async def workspace_search(
            query: str,
            scope: str,
            selection_ids: list[int] | None = None,
            canvas_id: int | None = None,
        ) -> list[dict[str, Any]]:
            """Search nodes/documents in the workspace."""
            normalized_query = query.strip()
            if not normalized_query:
                return []

            pattern = f"%{normalized_query}%"

            async with AsyncSessionLocal() as session:
                stmt = (
                    select(Node)
                    .join(Canvas)
                    .where(Canvas.user_id == DEFAULT_USER_ID)
                )

                if scope == "selection":
                    if not selection_ids:
                        return []
                    stmt = stmt.where(Node.id.in_(selection_ids))
                elif scope == "canvas":
                    resolved_canvas_id = canvas_id
                    if resolved_canvas_id is None:
                        canvas_repo = CanvasRepository(session)
                        canvases = await canvas_repo.get_by_user(
                            DEFAULT_USER_ID, limit=1
                        )
                        if not canvases:
                            return []
                        resolved_canvas_id = canvases[0].id

                    stmt = stmt.where(Node.canvas_id == resolved_canvas_id)

                stmt = stmt.where(
                    or_(
                        Node.label.ilike(pattern),
                        Node.node_metadata.ilike(pattern),
                    )
                ).order_by(Node.id)

                result = await session.execute(stmt)
                nodes = result.scalars().all()
                return [node.to_dict() for node in nodes]

        # Register the tools
        self.register_function(
            name="web_search",
            description="Search the web for information",
            func=web_search,
            is_async=True,
        )

        self.register_function(
            name="read_file",
            description="Read a file from the filesystem",
            func=read_file,
            is_async=True,
            dangerous=True,
            requires_confirmation=True,
        )

        self.register_function(
            name="write_file",
            description="Write content to a file",
            func=write_file,
            is_async=True,
            dangerous=True,
            requires_confirmation=True,
        )

        self.register_function(
            name="get_current_time",
            description="Get the current time",
            func=get_current_time,
            is_async=True,
        )

        self.register_function(
            name="calculate",
            description="Calculate a mathematical expression",
            func=calculate,
            is_async=True,
        )

        self.register_function(
            name="canvas.create_node",
            description="Create a new node on the canvas",
            func=canvas_create_node,
            parameters=CanvasCreateNodeParams,
            is_async=True,
        )

        self.register_function(
            name="canvas.update_node",
            description="Update an existing node on the canvas",
            func=canvas_update_node,
            parameters=CanvasUpdateNodeParams,
            is_async=True,
        )

        self.register_function(
            name="canvas.link_nodes",
            description="Create a typed edge between two nodes",
            func=canvas_link_nodes,
            parameters=CanvasLinkNodesParams,
            is_async=True,
        )

        self.register_function(
            name="workspace.search",
            description="Search nodes/documents in the workspace",
            func=workspace_search,
            parameters=WorkspaceSearchParams,
            is_async=True,
        )

    def register_function(
        self,
        name: str,
        description: str,
        func: ToolFunc | AsyncToolFunc,
        parameters: type[BaseModel] | None = None,
        is_async: bool = False,
        dangerous: bool = False,
        requires_confirmation: bool = False,
    ) -> None:
        """Register a function as a tool.

        Args:
            name: Unique name for the tool.
            description: Human-readable description.
            func: The function to call.
            parameters: Optional Pydantic model for parameter validation.
            is_async: Whether the function is async.
            dangerous: Whether the tool performs dangerous operations.
            requires_confirmation: Whether the tool requires user confirmation.
        """
        metadata = ToolMetadata(
            name=name,
            description=description,
            parameters=parameters,
            function=func,
            is_async=is_async,
            dangerous=dangerous,
            requires_confirmation=requires_confirmation,
        )

        self._tools[name] = metadata
        logger.info(f"Registered tool: {name}")

    def register_mcp_tool(
        self, name: str, server_name: str, tool_name: str, description: str
    ) -> None:
        """Register an MCP tool.

        Args:
            name: Local name for the tool.
            server_name: MCP server name.
            tool_name: Tool name on the server.
            description: Tool description.
        """
        metadata = ToolMetadata(
            name=name,
            description=description,
            parameters=None,
            function=None,
            is_async=True,
            mcp_server=server_name,
            mcp_tool_name=tool_name,
            requires_confirmation=True,
        )

        self._tools[name] = metadata
        logger.info(f"Registered MCP tool: {name} from {server_name}")

    def get_tool(self, name: str) -> ToolMetadata | None:
        """Get tool metadata by name.

        Args:
            name: Tool name.

        Returns:
            ToolMetadata if found, None otherwise.
        """
        return self._tools.get(name)

    def list_tools(
        self, include_mcp: bool = True, include_dangerous: bool = True
    ) -> list[ToolMetadata]:
        """List all available tools.

        Args:
            include_mcp: Whether to include MCP tools.
            include_dangerous: Whether to include dangerous tools.

        Returns:
            List of ToolMetadata.
        """
        tools = list(self._tools.values())

        if not include_mcp:
            tools = [t for t in tools if t.mcp_server is None]

        if not include_dangerous:
            tools = [t for t in tools if not t.dangerous]

        return tools

    def validate_arguments(
        self, tool_name: str, arguments: dict[str, Any]
    ) -> tuple[bool, list[str]]:
        """Validate tool arguments.

        Args:
            tool_name: Name of the tool.
            arguments: Arguments to validate.

        Returns:
            Tuple of (is_valid, error_messages).
        """
        tool = self.get_tool(tool_name)
        if not tool:
            return False, [f"Tool not found: {tool_name}"]

        if tool.parameters is None:
            # No validation schema, accept any arguments
            return True, []

        try:
            tool.parameters.model_validate(arguments)
            return True, []
        except ValidationError as e:
            errors = [
                f"{'.'.join(str(loc) for loc in err['loc'])}: {err['msg']}"
                for err in e.errors()
            ]
            return False, errors

    async def execute_tool(
        self, name: str, arguments: dict[str, Any]
    ) -> ToolExecutionResult:
        """Execute a tool with validated arguments.

        Args:
            name: Tool name.
            arguments: Tool arguments.

        Returns:
            ToolExecutionResult with output or error.

        Raises:
            ToolValidationError: If validation fails.
        """
        import time

        tool = self.get_tool(name)
        if not tool:
            return ToolExecutionResult(
                tool_name=name,
                success=False,
                error=f"Tool not found: {name}",
            )

        # Validate arguments
        is_valid, errors = self.validate_arguments(name, arguments)
        if not is_valid:
            raise ToolValidationError(name, errors)

        start_time = time.time()

        try:
            if tool.mcp_server:
                # Execute via MCP
                result = await self._execute_mcp_tool(tool, arguments)
            elif tool.function:
                # Execute local function
                if tool.is_async:
                    result = await tool.function(**arguments)
                else:
                    result = tool.function(**arguments)
            else:
                raise ValueError(f"Tool {name} has no executable function")

            execution_time_ms = (time.time() - start_time) * 1000

            return ToolExecutionResult(
                tool_name=name,
                success=True,
                output=result,
                execution_time_ms=execution_time_ms,
            )

        except Exception as e:
            execution_time_ms = (time.time() - start_time) * 1000
            logger.error(f"Tool {name} execution failed", exc_info=True)

            return ToolExecutionResult(
                tool_name=name,
                success=False,
                error=str(e),
                execution_time_ms=execution_time_ms,
            )

    async def _execute_mcp_tool(
        self, tool: ToolMetadata, arguments: dict[str, Any]
    ) -> Any:
        """Execute an MCP tool.

        Args:
            tool: Tool metadata with MCP configuration.
            arguments: Tool arguments.

        Returns:
            Tool execution result.

        Raises:
            ValueError: If MCP is not available or server not found.
        """
        if not tool.mcp_server or not tool.mcp_tool_name:
            raise ValueError(f"Tool {tool.name} is not configured as an MCP tool")

        if not MCP_AVAILABLE:
            raise ValueError(
                f"MCP integration not available. "
                f"Tool {tool.name} requires MCP server {tool.mcp_server}. "
                f"Ensure database is configured and MCP registry is accessible."
            )

        # Note: MCP registry requires a database session which isn't available
        # in this simple tool manager context. For production use, the tool
        # should be called through the orchestrator which can provide the session.
        raise ValueError(
            "MCP tool execution requires database session. "
            "Use the orchestrator's execute_agent method for MCP tools."
        )

    async def recommend_tools(
        self, agent_request: str, context: dict[str, Any] | None = None
    ) -> list[ToolRecommendation]:
        """Recommend tools for an agent request.

        Args:
            agent_request: The agent's text request.
            context: Optional context for tool selection.

        Returns:
            List of ToolRecommendation sorted by confidence.
        """
        # This is a simple keyword-based recommendation
        # In production, would use embeddings or LLM-based matching
        recommendations: list[ToolRecommendation] = []

        request_lower = agent_request.lower()

        # Keyword matching (maps tool names to keywords)
        keywords_map = {
            "web_search": ["search", "find", "look up", "google"],
            "read_file": ["read", "open", "view file", "load file"],
            "write_file": ["write", "save", "create file", "store"],
            "get_current_time": ["time", "date", "clock", "now"],
            "calculate": ["calculate", "compute", "math", "solve"],
        }

        for tool_name, keywords in keywords_map.items():
            for keyword in keywords:
                if keyword in request_lower:
                    recommendations.append(
                        ToolRecommendation(
                            tool_name=tool_name,
                            confidence=0.8,
                            reason=f"Keyword '{keyword}' matched",
                        )
                    )
                    break

        # Sort by confidence
        recommendations.sort(key=lambda r: r.confidence, reverse=True)

        return recommendations


# Global tool manager instance
_tool_manager: ToolManager | None = None


def get_tool_manager() -> ToolManager:
    """Get the global tool manager instance.

    Returns:
        ToolManager instance.
    """
    global _tool_manager
    if _tool_manager is None:
        _tool_manager = ToolManager()
    return _tool_manager


async def call_tool(name: str, **arguments: Any) -> Any:
    """Convenience function to call a tool.

    Args:
        name: Tool name.
        **arguments: Tool arguments.

    Returns:
        Tool execution result.

    Raises:
        RuntimeError: If tool execution or validation fails.
    """
    manager = get_tool_manager()

    try:
        result = await manager.execute_tool(name, arguments)
    except ToolValidationError as e:
        raise RuntimeError(f"Tool validation failed: {e}") from e

    if not result.success:
        raise RuntimeError(f"Tool execution failed: {result.error}")

    return result.output
