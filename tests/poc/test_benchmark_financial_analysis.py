import os
import unittest

import pytest

from mcpuniverse.benchmark.runner import BenchmarkRunner
from mcpuniverse.benchmark.report import BenchmarkReport
from mcpuniverse.callbacks.handlers.vprint import get_vprint_callbacks
from mcpuniverse.tracer.collectors import FileCollector

from tests.poc.helpers import mcp_manager_with_local_python

TASK_0001 = "mcpuniverse/financial_analysis/yfinance_task_0001.json"


@pytest.mark.skipif(
    not os.getenv("AZURE_API_KEY"),
    reason="needs Azure credentials (AZURE_API_KEY)",
)
class TestBenchmarkFinancialAnalysis(unittest.IsolatedAsyncioTestCase):

    async def test_yfinance_task_0001_passes_with_pydantic_ai_agent(self):
        trace_collector = FileCollector(
            log_file="log/mcpuniverse/financial_analysis.log"
        )
        benchmark = BenchmarkRunner("mcpuniverse/financial_analysis.yaml")
        # YAML file stays unchanged; limit runtime to the deterministic POC task.
        benchmark._benchmark_configs[0].tasks = [TASK_0001]

        passed_any = False
        results = None
        last_eval_results = None

        # This is a smoke-test over a live LLM. To keep Phase 0 POC signal
        # usable, we allow a single retry if the first evaluation fails.
        for _attempt in range(2):
            results = await benchmark.run(
                mcp_manager=mcp_manager_with_local_python(),
                trace_collector=trace_collector,
                callbacks=get_vprint_callbacks(),
            )

            self.assertEqual(len(results), 1)
            task_results = results[0].task_results[TASK_0001]
            eval_results = task_results["evaluation_results"]
            last_eval_results = eval_results
            if any(r.passed for r in eval_results):
                passed_any = True
                break

        self.assertTrue(
            passed_any,
            "yfinance_task_0001 should pass at least one evaluator",
        )

        report = BenchmarkReport(benchmark, trace_collector=trace_collector)
        report.dump()


if __name__ == "__main__":
    unittest.main()
