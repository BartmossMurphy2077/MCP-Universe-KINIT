import unittest

from mcpuniverse.llm.openai import OpenAIModel
from mcpuniverse.llm.pydantic_ai.openai import PydanticAIOpenAIModel
from mcpuniverse.mcp.manager import MCPManager
from mcpuniverse.workflows.builder import WorkflowBuilder


class TestWorkflowBuilderOpenAI(unittest.TestCase):

    def test_builds_openai_llm_from_config(self):
        configs = [{
            "kind": "llm",
            "spec": {
                "name": "llm-1",
                "type": "openai",
                "config": {"model_name": "gpt-4.1"},
            },
        }]
        workflow = WorkflowBuilder(mcp_manager=MCPManager(), config=configs)
        workflow.build(project_id="test")

        llm = workflow.get_component("llm-1")
        self.assertIsInstance(llm, PydanticAIOpenAIModel)
        self.assertEqual(llm.config.model_name, "gpt-4.1")

    def test_builds_openai_legacy_llm_from_config(self):
        configs = [{
            "kind": "llm",
            "spec": {
                "name": "llm-1",
                "type": "openai_legacy",
                "config": {"model_name": "gpt-4.1"},
            },
        }]
        workflow = WorkflowBuilder(mcp_manager=MCPManager(), config=configs)
        workflow.build(project_id="test")

        llm = workflow.get_component("llm-1")
        self.assertIsInstance(llm, OpenAIModel)
        self.assertEqual(llm.config.model_name, "gpt-4.1")


if __name__ == "__main__":
    unittest.main()
