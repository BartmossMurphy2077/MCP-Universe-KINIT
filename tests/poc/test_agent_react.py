import unittest
from unittest.mock import patch

from pydantic_ai.models.test import TestModel

from mcpuniverse.agent.pydantic_ai import PydanticAIReAct
from mcpuniverse.agent.types import AgentResponse
from mcpuniverse.llm.pydantic_ai.openai import PydanticAIOpenAIModel
from mcpuniverse.mcp.manager import MCPManager


class TestPydanticAIReActAgent(unittest.IsolatedAsyncioTestCase):

    async def test_execute_returns_final_answer_from_json_contract(self):
        llm = PydanticAIOpenAIModel(config={
            "model_name": "gpt-4.1",
            "api_key": "test-key",
        })
        agent = PydanticAIReAct(
            mcp_manager=MCPManager(),
            llm=llm,
            config={"instruction": "You are a helpful assistant.", "servers": []},
        )
        await agent.initialize()

        payload = '{"thought": "done", "answer": "it is sunny"}'
        with patch.object(llm, "build_pydantic_ai_model", return_value=TestModel(custom_output_text=payload)):
            response = await agent.execute("Will it rain?")

        self.assertIsInstance(response, AgentResponse)
        self.assertEqual(response.response, "it is sunny")
        await agent.cleanup()


if __name__ == "__main__":
    unittest.main()
