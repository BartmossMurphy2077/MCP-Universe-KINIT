import unittest
from unittest.mock import patch

from pydantic_ai.models.test import TestModel

from mcpuniverse.agent.pydantic_ai import PydanticAIFunctionCall
from mcpuniverse.agent.types import AgentResponse
from mcpuniverse.llm.pydantic_ai.azure import PydanticAIAzureModel
from mcpuniverse.mcp.manager import MCPManager
from mcpuniverse.tracer.collectors import MemoryCollector


class TestPydanticAIFunctionCallAgent(unittest.IsolatedAsyncioTestCase):

    async def test_execute_returns_agent_response(self):
        llm = PydanticAIAzureModel(config={
            "model_name": "test-deployment",
            "api_key": "test-key",
            "azure_endpoint": "https://example.openai.azure.com",
        })
        agent = PydanticAIFunctionCall(
            mcp_manager=MCPManager(),
            llm=llm,
            config={"instruction": "You are a helpful assistant.", "servers": []},
        )
        await agent.initialize()

        with patch.object(llm, "build_pydantic_ai_model", return_value=TestModel(custom_output_text="done")):
            response = await agent.execute("hello")

        self.assertIsInstance(response, AgentResponse)
        self.assertEqual(response.response, "done")
        self.assertTrue(response.trace_id)
        await agent.cleanup()

    async def test_execute_extracts_answer_from_thought_answer_wrapper(self):
        llm = PydanticAIAzureModel(config={
            "model_name": "test-deployment",
            "api_key": "test-key",
            "azure_endpoint": "https://example.openai.azure.com",
        })
        agent = PydanticAIFunctionCall(
            mcp_manager=MCPManager(),
            llm=llm,
            config={"instruction": "You are a helpful assistant.", "servers": []},
        )
        await agent.initialize()

        wrapped = (
            '{"thought": "reasoning", "answer": '
            '"{\\"total value\\": 100.0, \\"total percentage return\\": 5.0}"}'
        )
        with patch.object(llm, "build_pydantic_ai_model", return_value=TestModel(custom_output_text=wrapped)):
            response = await agent.execute("hello")

        self.assertEqual(
            response.response,
            '{"total value": 100.0, "total percentage return": 5.0}',
        )
        await agent.cleanup()

    async def test_execute_emits_llm_trace_record(self):
        llm = PydanticAIAzureModel(config={
            "model_name": "test-deployment",
            "api_key": "test-key",
            "azure_endpoint": "https://example.openai.azure.com",
        })
        agent = PydanticAIFunctionCall(
            mcp_manager=MCPManager(),
            llm=llm,
            config={"instruction": "You are a helpful assistant.", "servers": []},
        )
        await agent.initialize()

        from mcpuniverse.tracer import Tracer

        tracer = Tracer(collector=MemoryCollector())
        with patch.object(llm, "build_pydantic_ai_model", return_value=TestModel(custom_output_text="done")):
            await agent.execute("hello", tracer=tracer)

        trace_records = tracer.get_trace()
        record_types = [
            r.records[0].data.get("type")
            for r in trace_records
            if r.records
        ]
        self.assertIn("llm", record_types)
        self.assertIn("agent", record_types)
        await agent.cleanup()


if __name__ == "__main__":
    unittest.main()
