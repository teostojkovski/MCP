"""
Tool registry for MCP server.
"""
from dataclasses import dataclass
from typing import Callable, Awaitable
from mcp.types import Tool, TextContent


@dataclass
class ToolDef:
    """Tool definition with schema and handler."""
    tool: Tool
    handler: Callable[[dict], Awaitable[list[TextContent]]]


Handler = Callable[[dict], Awaitable[list[TextContent]]]

