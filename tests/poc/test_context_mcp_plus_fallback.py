"""Tests for MCP+ fallback in the unified context layer."""
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from mcpuniverse.agent.pydantic_ai import PydanticAIFunctionCall
from mcpuniverse.context.layer import ContextStrategy
from mcpuniverse.context.mcp_plus import activate_mcp_plus_fallback
from mcpuniverse.extensions.mcpplus.wrapper.wrapper_manager import MCPWrapperManager
from mcpuniverse.llm.pydantic_ai.azure import PydanticAIAzureModel
from mcpuniverse.mcp.manager import MCPManager


class TestActivateMcpPlusFallback(unittest.TestCase):

    def test_wraps_plain_manager(self):
        llm = MagicMock()
        wrapped = activate_mcp_plus_fallback(MCPManager(), llm, token_threshold=1500)
        self.assertIsInstance(wrapped, MCPWrapperManager)

    def test_leaves_existing_wrapper_unchanged(self):
        llm = MagicMock()
        existing = MCPWrapperManager(wrapper_config={"enabled": True})
        self.assertIs(activate_mcp_plus_fallback(existing, llm), existing)


class TestMcpPlusFallbackInitialize(unittest.IsolatedAsyncioTestCase):

    async def test_initialize_activates_wrapper_for_mcp_plus_mode(self):
        llm = PydanticAIAzureModel(config={
            "model_name": "tiny-local-llm",
            "api_key": "test-key",
            "azure_endpoint": "https://example.openai.azure.com",
        })
        agent = PydanticAIFunctionCall(
            mcp_manager=MCPManager(),
            llm=llm,
            config={
                "instruction": "test",
                "servers": [],
                "context_layer": {"mode": "mcp_plus"},
            },
        )
        wrapped = MagicMock(spec=MCPWrapperManager)

        with patch(
            "mcpuniverse.agent.pydantic_ai.function_call.activate_mcp_plus_fallback",
            return_value=wrapped,
        ) as mock_activate:
            with patch.object(
                PydanticAIFunctionCall.__bases__[0],
                "initialize",
                new=AsyncMock(),
            ):
                await agent.initialize()

        mock_activate.assert_called_once()
        self.assertIs(agent._mcp_manager, wrapped)
        self.assertEqual(agent._context_strategy, ContextStrategy.MCP_PLUS)


if __name__ == "__main__":
    unittest.main()
