"""Pydantic AI-backed wide research agent.

Adapter-first implementation: uses the legacy `function_call_wide_research`
prompt contract while running LLM turns via Pydantic AI.
"""

from mcpuniverse.agent.function_call_wide import FunctionCallConfig as WideFunctionCallConfig
from mcpuniverse.agent.pydantic_ai.function_call import PydanticAIFunctionCall


class PydanticAIFunctionCallWideResearch(PydanticAIFunctionCall):
    """Wide research agent backed by Pydantic AI."""

    config_class = WideFunctionCallConfig
    alias = ["function_call_wide_research", "fc_wide_research", "function-call-wide-research"]

