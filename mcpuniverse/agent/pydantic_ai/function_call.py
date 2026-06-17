"""
Pydantic AI function_call agent.

Implements the legacy Executor contract while delegating the agent loop to Pydantic AI.
"""
import json
from typing import Dict, List, Optional, Union

from pydantic_ai import Agent

from mcpuniverse.agent.base import BaseAgent
from mcpuniverse.agent.function_call import FunctionCallConfig
from mcpuniverse.agent.types import AgentResponse
from mcpuniverse.agent.utils import build_system_prompt
from mcpuniverse.llm.base import BaseLLM
from mcpuniverse.llm.pydantic_ai.base import PydanticAIBaseLLM
from mcpuniverse.mcp.manager import MCPManager
from mcpuniverse.tracer import Tracer

from mcpuniverse.context.layer import (
    ContextStrategy,
    UnifiedContextConfig,
    resolve_context_strategy,
)
from mcpuniverse.context.mcp_plus import activate_mcp_plus_fallback

from .code_mode import build_code_mode_capabilities
from .mcp_tools import build_mcp_pydantic_tools
from .response import normalize_agent_output
from .tracing import build_messages_for_trace, emit_llm_trace, summarize_run_for_trace


class PydanticAIFunctionCall(BaseAgent):
    """
    Function-calling agent backed by Pydantic AI.

    MCP tools are exposed via adapters over MCPClient; tool names keep the
    ``server__tool`` convention.
    """
    config_class = FunctionCallConfig
    alias = ["function_call", "fc", "function-call"]

    def __init__(
            self,
            mcp_manager: MCPManager,
            llm: BaseLLM,
            config: Optional[Union[Dict, str]] = None,
    ):
        super().__init__(mcp_manager=mcp_manager, llm=llm, config=config)
        if not isinstance(llm, PydanticAIBaseLLM):
            raise TypeError(
                f"{self.__class__.__name__} requires a PydanticAIBaseLLM, got {type(llm).__name__}"
            )
        self._pydantic_llm: PydanticAIBaseLLM = llm
        self._run_tracer: Optional[Tracer] = None
        self._run_callbacks = None
        raw_config = config if isinstance(config, dict) else {}
        self._context_layer_config = UnifiedContextConfig.from_agent_config(raw_config)

    async def initialize(self, mcp_servers: Optional[List[dict]] = None):
        strategy = self.resolve_context_strategy()
        self._context_strategy = strategy
        if strategy == ContextStrategy.MCP_PLUS:
            self._mcp_manager = self._prepare_mcp_manager_for_context(strategy)
        await super().initialize(mcp_servers=mcp_servers)

    def resolve_context_strategy(self) -> ContextStrategy:
        """Resolve the unified context strategy for this agent run."""
        model_name = getattr(self._pydantic_llm.config, "model_name", "")
        return resolve_context_strategy(
            context_config=self._context_layer_config,
            model_name=model_name,
        )

    def _prepare_mcp_manager_for_context(self, strategy: ContextStrategy) -> MCPManager:
        if strategy == ContextStrategy.MCP_PLUS:
            return activate_mcp_plus_fallback(
                self._mcp_manager,
                self._llm,
                token_threshold=self._context_layer_config.token_threshold,
            )
        return self._mcp_manager

    def _build_user_prompt(self, message: str) -> str:
        params = {
            "INSTRUCTION": self._config.instruction,
            "QUESTION": message,
            "MAX_STEPS": self._config.max_iterations,
        }
        if self._config.context_examples:
            params["CONTEXT_EXAMPLES"] = self._config.context_examples
        params.update(self._config.template_vars)
        return build_system_prompt(
            system_prompt_template=self._config.system_prompt,
            tool_prompt_template="",
            tools=None,
            **params,
        )

    async def _execute(
            self,
            message: Union[str, List[str]],
            output_format: Optional[Union[str, Dict]] = None,
            **kwargs,
    ) -> AgentResponse:
        if isinstance(message, (list, tuple)):
            message = "\n".join(message)
        if output_format is not None:
            message += f"\n{self._get_output_format_prompt(output_format)}"

        tracer = kwargs.get("tracer", Tracer())
        callbacks = kwargs.get("callbacks", [])
        self._run_tracer = tracer
        self._run_callbacks = callbacks

        strategy = self.resolve_context_strategy()
        self._context_strategy = strategy

        user_prompt = self._build_user_prompt(message)
        pydantic_tools = build_mcp_pydantic_tools(self)
        model = self._pydantic_llm.build_pydantic_ai_model()
        capabilities = build_code_mode_capabilities(strategy)
        agent = Agent(
            model,
            instructions=self._config.instruction,
            tools=pydantic_tools,
            capabilities=capabilities or None,
        )

        result = await agent.run(user_prompt)
        emit_llm_trace(
            tracer,
            class_name=self.__class__.__name__,
            config=self._pydantic_llm.config.to_dict(),
            messages=build_messages_for_trace(user_prompt),
            response=summarize_run_for_trace(result),
        )

        return AgentResponse(
            name=self._name,
            class_name=self.__class__.__name__,
            response=normalize_agent_output(result.output),
            trace_id=tracer.trace_id,
        )
