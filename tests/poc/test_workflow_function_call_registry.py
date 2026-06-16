import unittest

from mcpuniverse.agent.function_call import FunctionCall
from mcpuniverse.agent.pydantic_ai import PydanticAIFunctionCall
from mcpuniverse.mcp.manager import MCPManager
from mcpuniverse.workflows.builder import WorkflowBuilder


class TestWorkflowBuilderFunctionCall(unittest.TestCase):

    def test_builds_function_call_agent_from_config(self):
        configs = [
            {
                "kind": "llm",
                "spec": {
                    "name": "llm-1",
                    "type": "azure",
                    "config": {"model_name": "gpt-5.4-mini"},
                },
            },
            {
                "kind": "agent",
                "spec": {
                    "name": "agent-1",
                    "type": "function_call",
                    "config": {
                        "llm": "llm-1",
                        "instruction": "You are a test agent.",
                        "servers": [],
                    },
                },
            },
        ]
        workflow = WorkflowBuilder(mcp_manager=MCPManager(), config=configs)
        workflow.build(project_id="test")

        agent = workflow.get_component("agent-1")
        self.assertIsInstance(agent, PydanticAIFunctionCall)

    def test_builds_function_call_legacy_agent_from_config(self):
        configs = [
            {
                "kind": "llm",
                "spec": {
                    "name": "llm-1",
                    "type": "azure_legacy",
                    "config": {"model_name": "gpt-5.4-mini"},
                },
            },
            {
                "kind": "agent",
                "spec": {
                    "name": "agent-1",
                    "type": "function_call_legacy",
                    "config": {
                        "llm": "llm-1",
                        "instruction": "You are a test agent.",
                        "servers": [],
                    },
                },
            },
        ]
        workflow = WorkflowBuilder(mcp_manager=MCPManager(), config=configs)
        workflow.build(project_id="test")

        agent = workflow.get_component("agent-1")
        self.assertIsInstance(agent, FunctionCall)


if __name__ == "__main__":
    unittest.main()
