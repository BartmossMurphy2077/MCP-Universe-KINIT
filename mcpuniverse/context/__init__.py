"""Unified context reduction layer (Code Mode + MCP+ fallback)."""
from .layer import (
    ContextStrategy,
    UnifiedContextConfig,
    model_supports_code_mode,
    resolve_context_strategy,
    select_context_strategy,
)
from .mcp_plus import activate_mcp_plus_fallback

__all__ = [
    "ContextStrategy",
    "UnifiedContextConfig",
    "activate_mcp_plus_fallback",
    "model_supports_code_mode",
    "resolve_context_strategy",
    "select_context_strategy",
]
