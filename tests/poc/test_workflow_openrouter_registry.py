import unittest

from mcpuniverse.llm.openrouter import OpenRouterModel
from mcpuniverse.llm.pydantic_ai.openrouter import PydanticAIOpenRouterModel
from mcpuniverse.mcp.manager import MCPManager
from mcpuniverse.workflows.builder import WorkflowBuilder


class TestWorkflowBuilderOpenRouter(unittest.TestCase):

    def test_builds_openrouter_llm_from_config(self):
        configs = [{
            "kind": "llm",
            "spec": {
                "name": "llm-1",
                "type": "openrouter",
                "config": {"model_name": "GPT5_1_OR"},
            },
        }]
        workflow = WorkflowBuilder(mcp_manager=MCPManager(), config=configs)
        workflow.build(project_id="test")

        llm = workflow.get_component("llm-1")
        self.assertIsInstance(llm, PydanticAIOpenRouterModel)
        self.assertEqual(llm.config.model_name, "GPT5_1_OR")

    def test_builds_openrouter_legacy_llm_from_config(self):
        configs = [{
            "kind": "llm",
            "spec": {
                "name": "llm-1",
                "type": "openrouter_legacy",
                "config": {"model_name": "GPT5_1_OR"},
            },
        }]
        workflow = WorkflowBuilder(mcp_manager=MCPManager(), config=configs)
        workflow.build(project_id="test")

        llm = workflow.get_component("llm-1")
        self.assertIsInstance(llm, OpenRouterModel)
        self.assertEqual(llm.config.model_name, "GPT5_1_OR")


if __name__ == "__main__":
    unittest.main()
