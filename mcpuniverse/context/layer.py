"""
Unified context layer — Code Mode primary, MCP+ fallback.

See issue #8 and docs/design/langchain-pydantic-ai-migration.md.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class ContextStrategy(str, Enum):
    """How an agent should reduce tool-output context."""

    CODE_MODE = "code_mode"
    MCP_PLUS = "mcp_plus"
    DIRECT = "direct"


# Models known to work with Pydantic AI Code Mode (Monty) in our cloud benchmarks.
_CODE_MODE_CAPABLE_PREFIXES = (
    "gpt-4",
    "gpt-5",
    "gpt-4o",
    "gpt-4.1",
    "o1",
    "o3",
    "claude-3",
    "claude-sonnet",
    "claude-opus",
    "claude-haiku",
)


def model_supports_code_mode(model_name: str) -> bool:
    """Return whether the configured model is treated as Code Mode capable."""
    normalized = (model_name or "").strip().lower()
    if not normalized:
        return False
    return any(normalized.startswith(prefix) for prefix in _CODE_MODE_CAPABLE_PREFIXES)


@dataclass
class UnifiedContextConfig:
    """YAML-facing unified context settings for Pydantic AI agents."""

    mode: str = "auto"  # auto | code_mode | mcp_plus | direct
    code_mode_enabled: bool = True
    mcp_plus_enabled: bool = True
    token_threshold: int = 2000

    @classmethod
    def from_agent_config(cls, config: dict | None) -> "UnifiedContextConfig":
        if not config:
            return cls()
        layer = config.get("context_layer") or {}
        if isinstance(layer, str):
            return cls(mode=layer)
        return cls(
            mode=layer.get("mode", config.get("context_layer_mode", "auto")),
            code_mode_enabled=layer.get("code_mode_enabled", True),
            mcp_plus_enabled=layer.get("mcp_plus_enabled", True),
            token_threshold=layer.get("token_threshold", 2000),
        )


def select_context_strategy(
    *,
    code_mode_enabled: bool,
    model_supports_code_mode: bool,
    mcp_plus_enabled: bool,
    tool_payload_tokens: int | None = None,
    token_threshold: int = 2000,
) -> ContextStrategy:
    """
    Choose the context reduction strategy.

    Code Mode is primary when enabled and the model supports it.
    MCP+ is the fallback for non-code-mode models and for single oversized payloads
    when Code Mode is unavailable.
    """
    if code_mode_enabled and model_supports_code_mode:
        return ContextStrategy.CODE_MODE

    if mcp_plus_enabled:
        oversized = (
            tool_payload_tokens is not None
            and tool_payload_tokens >= token_threshold
        )
        if not model_supports_code_mode or oversized:
            return ContextStrategy.MCP_PLUS

    return ContextStrategy.DIRECT


def resolve_context_strategy(
    *,
    context_config: UnifiedContextConfig,
    model_name: str,
    tool_payload_tokens: int | None = None,
) -> ContextStrategy:
    """Resolve strategy from agent config, model name, and optional payload size."""
    if context_config.mode == ContextStrategy.CODE_MODE.value:
        return ContextStrategy.CODE_MODE
    if context_config.mode == ContextStrategy.MCP_PLUS.value:
        return ContextStrategy.MCP_PLUS
    if context_config.mode == ContextStrategy.DIRECT.value:
        return ContextStrategy.DIRECT

    return select_context_strategy(
        code_mode_enabled=context_config.code_mode_enabled,
        model_supports_code_mode=model_supports_code_mode(model_name),
        mcp_plus_enabled=context_config.mcp_plus_enabled,
        tool_payload_tokens=tool_payload_tokens,
        token_threshold=context_config.token_threshold,
    )
