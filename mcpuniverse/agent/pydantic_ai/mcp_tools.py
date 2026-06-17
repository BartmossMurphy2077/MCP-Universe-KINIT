"""
Build Pydantic AI tools that delegate to MCPClient via BaseAgent.call_tool.

These are local (non-provider-native) tool handlers — the equivalent of
``native=False`` for MCP in Pydantic AI Harness Code Mode, so tools route
through the local toolset into the Monty sandbox instead of server-side execution.
"""
from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any, List

from mcp.types import TextContent
from pydantic_ai import Tool

if TYPE_CHECKING:
    from mcpuniverse.agent.base import BaseAgent


def _tool_result_to_str(tool_result: Any) -> str:
    if hasattr(tool_result, "content") and tool_result.content:
        content = tool_result.content[0]
        if isinstance(content, TextContent):
            return content.text
    return json.dumps(tool_result.model_dump(mode="json") if hasattr(tool_result, "model_dump") else tool_result)


def build_mcp_pydantic_tools(agent: "BaseAgent") -> List[Tool]:
    """
    Convert initialized MCP tools on an agent into Pydantic AI Tool definitions.

    Tool names use the ``server__tool`` convention expected by evaluators.
    """
    tools: List[Tool] = []

    for server_name, tool_list in agent._tools.items():
        for mcp_tool in tool_list:
            tool_name = f"{server_name}__{mcp_tool.name}"

            def _make_handler(server: str, name: str, description: str):
                async def handler(**kwargs) -> str:
                    tool_result = await agent.call_tool(
                        {"server": server, "tool": name, "arguments": kwargs},
                        tracer=getattr(agent, "_run_tracer", None),
                        callbacks=getattr(agent, "_run_callbacks", None),
                    )
                    return _tool_result_to_str(tool_result)

                handler.__name__ = tool_name
                handler.__doc__ = description or f"MCP tool {name} on server {server}"
                return handler

            tools.append(Tool(
                _make_handler(server_name, mcp_tool.name, mcp_tool.description or ""),
                takes_ctx=False,
            ))

    return tools
