"""
Pydantic AI ReAct agent.

Preserves the legacy text/JSON thought-action-answer contract while using
Pydantic AI for LLM turns (no native tool calling on the model).
"""
import json
from typing import Dict, List, Optional, Union

from mcp.types import TextContent
from pydantic_ai import Agent

from mcpuniverse.agent.base import BaseAgent
from mcpuniverse.agent.react import ReAct, ReActConfig
from mcpuniverse.agent.types import AgentResponse
from mcpuniverse.agent.utils import build_system_prompt
from mcpuniverse.llm.base import BaseLLM
from mcpuniverse.llm.pydantic_ai.base import PydanticAIBaseLLM
from mcpuniverse.mcp.manager import MCPManager
from mcpuniverse.tracer import Tracer

from .response import normalize_agent_output
from .tracing import build_messages_for_trace, emit_llm_trace, summarize_run_for_trace


class PydanticAIReAct(BaseAgent):
    """ReAct agent backed by Pydantic AI text turns and legacy JSON actions."""

    config_class = ReActConfig
    alias = ["react"]

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
        self._history: List[str] = []

    def _build_prompt(self, question: str) -> str:
        params = {
            "INSTRUCTION": self._config.instruction,
            "QUESTION": question,
            "MAX_STEPS": self._config.max_iterations,
        }
        if self._config.context_examples:
            params["CONTEXT_EXAMPLES"] = self._config.context_examples
        params.update(self._config.template_vars)
        if self._history:
            params["HISTORY"] = "\n\n".join(self._history)
        return build_system_prompt(
            system_prompt_template=self._config.system_prompt,
            tool_prompt_template=self._config.tools_prompt,
            tools=self._tools,
            **params,
        )

    def _add_history(self, history_type: str, message: str):
        self._history.append(f"{history_type.title()}: {message}")

    def _parse_react_response(self, content: str) -> dict:
        response_text = content.strip().strip('`').strip()
        if response_text.startswith("json"):
            response_text = response_text[4:].strip()
        parsed = json.loads(response_text)
        if "thought" not in parsed:
            raise ValueError("Invalid response format")
        return parsed

    async def _execute(
            self,
            message: Union[str, List[str]],
            output_format: Optional[Union[str, Dict]] = None,
            **kwargs,
    ) -> AgentResponse:
        if isinstance(message, (list, tuple)):
            message = "\n".join(message)
        if output_format is not None:
            message = message + "\n\n" + self._get_output_format_prompt(output_format)

        tracer = kwargs.get("tracer", Tracer())
        callbacks = kwargs.get("callbacks", [])
        model = self._pydantic_llm.build_pydantic_ai_model()
        agent = Agent(model, instructions=self._config.instruction)

        for iter_num in range(self._config.max_iterations):
            prompt = self._build_prompt(message)
            try:
                result = await agent.run(prompt)
                emit_llm_trace(
                    tracer,
                    class_name=self.__class__.__name__,
                    config=self._pydantic_llm.config.to_dict(),
                    messages=build_messages_for_trace(prompt),
                    response=summarize_run_for_trace(result),
                )
                parsed = self._parse_react_response(result.output)
            except (json.JSONDecodeError, ValueError):
                self._add_history(
                    history_type="error",
                    message="I encountered an error in parsing LLM response. Let me try again.",
                )
                continue

            self._add_history(history_type=f"Step {iter_num + 1}", message="")

            if "answer" in parsed:
                self._add_history(history_type="answer", message=parsed["answer"])
                await ReAct._send_callback_message(
                    callbacks=callbacks,
                    iter_num=iter_num,
                    thought=parsed["thought"],
                    answer=parsed["answer"],
                )
                return AgentResponse(
                    name=self._name,
                    class_name=self.__class__.__name__,
                    response=normalize_agent_output(result.output),
                    trace_id=tracer.trace_id,
                )

            if "action" in parsed:
                self._add_history(history_type="thought", message=parsed["thought"])
                action = parsed["action"]
                if not isinstance(action, dict) or "server" not in action or "tool" not in action:
                    self._add_history(history_type="action", message=str(action))
                    self._add_history(history_type="result", message="Invalid action")
                    await ReAct._send_callback_message(
                        callbacks=callbacks,
                        iter_num=iter_num,
                        thought=parsed["thought"],
                        action=parsed["action"],
                        result="Invalid action",
                    )
                    continue

                self._add_history(
                    history_type="action",
                    message=f"Using tool `{action['tool']}` in server `{action['server']}`",
                )
                self._add_history(
                    history_type="action input",
                    message=str(action.get("arguments", "none")),
                )
                try:
                    tool_result = await self.call_tool(action, tracer=tracer, callbacks=callbacks)
                    tool_content = tool_result.content[0]
                    if not isinstance(tool_content, TextContent):
                        raise ValueError("Tool output is not a text")
                    if self._config.summarize_tool_response:
                        context = json.dumps(action, indent=2)
                        tool_summary = await self.summarize_tool_response(
                            tool_content.text,
                            context=context,
                            tracer=tracer,
                        )
                        self._add_history(history_type="result", message=tool_summary)
                        result_text = tool_summary
                    else:
                        self._add_history(history_type="result", message=tool_content.text)
                        result_text = tool_content.text
                    await ReAct._send_callback_message(
                        callbacks=callbacks,
                        iter_num=iter_num,
                        thought=parsed["thought"],
                        action=parsed["action"],
                        result=result_text,
                    )
                except Exception as exc:
                    self._add_history(history_type="result", message=str(exc)[:300])
                    await ReAct._send_callback_message(
                        callbacks=callbacks,
                        iter_num=iter_num,
                        thought=parsed["thought"],
                        action=parsed["action"],
                        result=str(exc),
                    )
                continue

            if "result" in parsed:
                self._add_history(history_type="thought", message=parsed["thought"])
                self._add_history(history_type="result", message=parsed["result"])
                await ReAct._send_callback_message(
                    callbacks=callbacks,
                    iter_num=iter_num,
                    thought=parsed["thought"],
                    result=parsed["result"],
                )
                continue

            self._add_history(history_type="error", message="Invalid response format")

        return AgentResponse(
            name=self._name,
            class_name=self.__class__.__name__,
            response=(
                "I'm sorry, but I couldn't find a satisfactory answer "
                "within the allowed number of iterations."
            ),
            trace_id=tracer.trace_id,
        )
