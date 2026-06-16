"""Emit legacy-shaped trace records from Pydantic AI agent runs."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic_ai import AgentRunResult

from mcpuniverse.tracer import Tracer


def emit_llm_trace(
        tracer: Tracer,
        *,
        class_name: str,
        config: Dict[str, Any],
        messages: List[dict],
        response: Any,
) -> None:
    """Record a single legacy ``type: llm`` span for BenchmarkReport compatibility."""
    with tracer.sprout() as t:
        t.add({
            "type": "llm",
            "class": class_name,
            "config": config,
            "messages": messages,
            "response": response,
            "error": "",
        })


def summarize_run_for_trace(result: AgentRunResult) -> Any:
    """Extract a JSON-serializable response payload from a Pydantic AI run."""
    usage = result.usage() if callable(result.usage) else result.usage
    return {
        "output": result.output,
        "usage": {
            "input_tokens": usage.input_tokens,
            "output_tokens": usage.output_tokens,
            "requests": usage.requests,
        },
    }


def build_messages_for_trace(user_prompt: str) -> List[dict]:
    return [{"role": "user", "content": user_prompt}]
