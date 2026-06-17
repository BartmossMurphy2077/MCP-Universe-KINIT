import unittest

from mcpuniverse.agent.react import ReAct
from mcpuniverse.agent.pydantic_ai import PydanticAIReAct
from mcpuniverse.mcp.manager import MCPManager
from mcpuniverse.workflows.builder import WorkflowBuilder


class TestWorkflowBuilderReAct(unittest.TestCase):

    def test_builds_react_agent_from_config(self):
        configs = [
            {
                "kind": "llm",
                "spec": {
                    "name": "llm-1",
                    "type": "openai",
                    "config": {"model_name": "gpt-4.1"},
                },
            },
            {
                "kind": "agent",
                "spec": {
                    "name": "agent-1",
                    "type": "react",
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
        self.assertIsInstance(agent, PydanticAIReAct)

    def test_builds_react_legacy_agent_from_config(self):
        configs = [
            {
                "kind": "llm",
                "spec": {
                    "name": "llm-1",
                    "type": "openai_legacy",
                    "config": {"model_name": "gpt-4.1"},
                },
            },
            {
                "kind": "agent",
                "spec": {
                    "name": "agent-1",
                    "type": "react_legacy",
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
        self.assertIsInstance(agent, ReAct)


if __name__ == "__main__":
    unittest.main()
