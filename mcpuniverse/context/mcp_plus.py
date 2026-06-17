"""MCP+ fallback activation for the unified context layer."""
from __future__ import annotations

from mcpuniverse.extensions.mcpplus.wrapper.wrapper_manager import (
    MCPWrapperManager,
    WrapperConfig,
)
from mcpuniverse.llm.base import BaseLLM
from mcpuniverse.mcp.manager import MCPManager


def activate_mcp_plus_fallback(
    mcp_manager: MCPManager,
    llm: BaseLLM,
    *,
    token_threshold: int = 2000,
) -> MCPManager:
    """
    Return an MCP manager that post-processes oversized tool payloads via MCP+.

    If the manager is already wrapped, it is returned unchanged.
    """
    if isinstance(mcp_manager, MCPWrapperManager):
        return mcp_manager

    wrapper_config = WrapperConfig(
        enabled=True,
        token_threshold=token_threshold,
    )
    wrapped = MCPWrapperManager(
        context=getattr(mcp_manager, "_context", None),
        wrapper_config=wrapper_config,
    )
    if hasattr(mcp_manager, "_raw_configs"):
        wrapped._raw_configs = dict(mcp_manager._raw_configs)
    wrapped.set_llm(llm)
    return wrapped
