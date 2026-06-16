"""Shared helpers for POC integration tests."""
import sys

from mcpuniverse.mcp.manager import MCPManager


def mcp_manager_with_local_python() -> MCPManager:
    """Use the current interpreter for MCP stdio servers (Windows-friendly)."""
    manager = MCPManager()
    for server_name, module in (
        ("yfinance", "mcpuniverse.mcp.servers.yahoo_finance"),
        ("calculator", "mcp_server_calculator"),
    ):
        manager.update_server_config(server_name, {
            "stdio": {"command": sys.executable, "args": ["-m", module]},
        })
    return manager
