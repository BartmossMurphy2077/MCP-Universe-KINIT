"""Code Mode helpers for Pydantic AI agents."""
from __future__ import annotations

from typing import Any, List

from mcpuniverse.context.layer import ContextStrategy


def build_code_mode_capabilities(strategy: ContextStrategy) -> List[Any]:
    """
    Return Pydantic AI Harness capabilities for the resolved context strategy.

    Code Mode wraps tools into a single Monty-sandboxed ``run_code`` tool.
    MCP tools must route through the local toolset (our ``mcp_tools`` adapter),
    not provider-native MCP execution.
    """
    if strategy != ContextStrategy.CODE_MODE:
        return []

    try:
        from pydantic_ai_harness import CodeMode
    except ImportError as exc:  # pragma: no cover - exercised when extra missing
        raise RuntimeError(
            "Code Mode requires pydantic-ai-harness[code-mode]. "
            "Install with: pip install 'mcpuniverse[code-mode]'"
        ) from exc

    return [CodeMode()]
