"""Tests for the unified context layer (Phase 2 — issue #8)."""
import unittest

from mcpuniverse.context.layer import (
    ContextStrategy,
    model_supports_code_mode,
    select_context_strategy,
)


class TestModelSupportsCodeMode(unittest.TestCase):

    def test_gpt5_models_support_code_mode(self):
        self.assertTrue(model_supports_code_mode("gpt-5.4-mini"))
        self.assertTrue(model_supports_code_mode("gpt-5"))

    def test_unknown_local_model_does_not_support_code_mode(self):
        self.assertFalse(model_supports_code_mode("tiny-local-llm"))


class TestSelectContextStrategy(unittest.TestCase):

    def test_selects_code_mode_when_enabled_and_model_supports(self):
        strategy = select_context_strategy(
            code_mode_enabled=True,
            model_supports_code_mode=True,
            mcp_plus_enabled=True,
        )
        self.assertEqual(strategy, ContextStrategy.CODE_MODE)

    def test_falls_back_to_mcp_plus_when_model_unsupported(self):
        strategy = select_context_strategy(
            code_mode_enabled=True,
            model_supports_code_mode=False,
            mcp_plus_enabled=True,
        )
        self.assertEqual(strategy, ContextStrategy.MCP_PLUS)

    def test_falls_back_to_mcp_plus_for_oversized_payload_when_code_mode_unavailable(self):
        strategy = select_context_strategy(
            code_mode_enabled=False,
            model_supports_code_mode=False,
            mcp_plus_enabled=True,
            tool_payload_tokens=5000,
            token_threshold=2000,
        )
        self.assertEqual(strategy, ContextStrategy.MCP_PLUS)

    def test_uses_direct_when_no_reduction_needed(self):
        strategy = select_context_strategy(
            code_mode_enabled=False,
            model_supports_code_mode=False,
            mcp_plus_enabled=False,
        )
        self.assertEqual(strategy, ContextStrategy.DIRECT)


if __name__ == "__main__":
    unittest.main()
