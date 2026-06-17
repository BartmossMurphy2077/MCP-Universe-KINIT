"""Tests for Code Mode integration on PydanticAIFunctionCall."""
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pydantic_ai.models.test import TestModel

pytest.importorskip("pydantic_ai_harness")

from mcpuniverse.agent.pydantic_ai import PydanticAIFunctionCall
from mcpuniverse.context.layer import ContextStrategy
from mcpuniverse.llm.pydantic_ai.azure import PydanticAIAzureModel
from mcpuniverse.mcp.manager import MCPManager


class TestPydanticAIFunctionCallCodeMode(unittest.IsolatedAsyncioTestCase):

    async def test_agent_receives_code_mode_capability_when_strategy_is_code_mode(self):
        llm = PydanticAIAzureModel(config={
            "model_name": "gpt-5.4-mini",
            "api_key": "test-key",
            "azure_endpoint": "https://example.openai.azure.com",
        })
        agent = PydanticAIFunctionCall(
            mcp_manager=MCPManager(),
            llm=llm,
            config={
                "instruction": "You are a helpful assistant.",
                "servers": [],
                "context_layer": {"mode": "code_mode"},
            },
        )
        await agent.initialize()

        captured: dict = {}

        class _FakeResult:
            output = "done"
            usage = None

        def _fake_agent_factory(*args, **kwargs):
            captured["capabilities"] = kwargs.get("capabilities")
            mock_agent = MagicMock()
            mock_agent.run = AsyncMock(return_value=_FakeResult())
            return mock_agent

        with patch.object(llm, "build_pydantic_ai_model", return_value=TestModel()):
            with patch("mcpuniverse.agent.pydantic_ai.function_call.Agent", side_effect=_fake_agent_factory):
                with patch("mcpuniverse.agent.pydantic_ai.function_call.emit_llm_trace"):
                    await agent.execute("What is 2+2?")

        self.assertIsNotNone(captured.get("capabilities"))
        self.assertEqual(len(captured["capabilities"]), 1)
        self.assertEqual(captured["capabilities"][0].__class__.__name__, "CodeMode")
        await agent.cleanup()

    async def test_agent_has_no_code_mode_capability_when_strategy_is_direct(self):
        llm = PydanticAIAzureModel(config={
            "model_name": "gpt-5.4-mini",
            "api_key": "test-key",
            "azure_endpoint": "https://example.openai.azure.com",
        })
        agent = PydanticAIFunctionCall(
            mcp_manager=MCPManager(),
            llm=llm,
            config={
                "instruction": "You are a helpful assistant.",
                "servers": [],
                "context_layer": {"mode": "direct"},
            },
        )
        await agent.initialize()

        captured: dict = {}

        class _FakeResult:
            output = "done"
            usage = None

        def _fake_agent_factory(*args, **kwargs):
            captured["capabilities"] = kwargs.get("capabilities")
            mock_agent = MagicMock()
            mock_agent.run = AsyncMock(return_value=_FakeResult())
            return mock_agent

        with patch.object(llm, "build_pydantic_ai_model", return_value=TestModel()):
            with patch("mcpuniverse.agent.pydantic_ai.function_call.Agent", side_effect=_fake_agent_factory):
                with patch("mcpuniverse.agent.pydantic_ai.function_call.emit_llm_trace"):
                    await agent.execute("What is 2+2?")

        self.assertIn(captured.get("capabilities"), ([], None))
        await agent.cleanup()

    async def test_resolve_context_strategy_returns_code_mode_for_gpt5_auto(self):
        llm = PydanticAIAzureModel(config={
            "model_name": "gpt-5.4-mini",
            "api_key": "test-key",
            "azure_endpoint": "https://example.openai.azure.com",
        })
        agent = PydanticAIFunctionCall(
            mcp_manager=MCPManager(),
            llm=llm,
            config={
                "instruction": "test",
                "servers": [],
                "context_layer": {"mode": "auto"},
            },
        )
        self.assertEqual(agent.resolve_context_strategy(), ContextStrategy.CODE_MODE)


if __name__ == "__main__":
    unittest.main()
