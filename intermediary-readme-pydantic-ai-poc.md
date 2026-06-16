# Intermediary README — Phase 0 POC: Pydantic AI Migration (adapter-first)

This fork currently contains the completed **Phase 0 proof-of-concept** for migrating MCP-Universe’s agent/LLM layer to **Pydantic AI**, while keeping the existing benchmark + custom MCP client layer and keeping YAML configs unchanged.

The overall outcome of this phase is:

- You can build a **Pydantic AI-backed** agent via the existing `WorkflowBuilder` YAML path.
- MCP tools still run through the existing `MCPManager` / MCP client plumbing.
- Benchmark tracing/report formatting stays compatible (legacy-shaped trace shim).
- The “financial_analysis” benchmark task `yfinance_task_0001` passes end-to-end when Azure credentials are present.

---

## What changed in this fork (high level)

### 1) New Pydantic AI LLM + agent components (adapter-first)

The new components live under `mcpuniverse/llm/pydantic_ai/` and `mcpuniverse/agent/pydantic_ai/`.

Key additions:

- **`PydanticAIBaseLLM`** (`mcpuniverse/llm/pydantic_ai/base.py`)
- **`PydanticAIAzureModel`** (`mcpuniverse/llm/pydantic_ai/azure.py`, alias: `azure`)
- **`PydanticAIFunctionCall`** (`mcpuniverse/agent/pydantic_ai/function_call.py`, alias: `function_call`)
  - includes output normalization so evaluators see the legacy-shaped JSON
- **MCP tool adapter + tracing shim**
  - `mcpuniverse/agent/pydantic_ai/mcp_tools.py`
  - `mcpuniverse/agent/pydantic_ai/tracing.py`

### 2) Registry swaps (YAML compatibility without rewriting configs)

To keep YAML unchanged while swapping in the Pydantic AI implementation:

- `azure` now resolves to the Pydantic AI-backed Azure model
- `azure_legacy` resolves to the original legacy Azure provider
- `function_call` resolves to `PydanticAIFunctionCall`
- `function_call_legacy` resolves to the original legacy `FunctionCall` agent

This behavior is validated by the WorkflowBuilder tests in `tests/poc/`.

### 3) Important bug fixes uncovered during the POC

#### a) `PydanticAIFunctionCall` output normalization

Legacy `FunctionCall` returns the inner JSON `answer`, but the Pydantic AI-backed agent initially returned the outer wrapper (`{"thought": ..., "answer": ...}`).

Fix: `PydanticAIFunctionCall` now normalizes output so evaluators receive the legacy task JSON.

Validated by:

- `tests/poc/test_agent_function_call.py`
- passing benchmark evaluation (`yfinance_task_0001`)

#### b) MCP `yahoo_finance` end-date inclusion + date formatting

`yfinance.Ticker(...).history(end=...)` treats `end` as **exclusive**.

Fixes:

- Treat the requested `end_date` as **inclusive** by adding one day before calling `history()`
- Normalize the returned `Date` field to `YYYY-MM-DD` strings (LLMs match these reliably)

Validated by:

- `tests/poc/test_benchmark_financial_analysis.py` (end-to-end)

#### c) MCPManager runtime config sync

`mcpuniverse/mcp/manager.py` now keeps `_raw_configs` in sync so runtime server config updates are reflected when building MCP clients.

This was required for earlier integration stability.

---

## How to run the framework locally

### Prerequisites

- Python installed (this project uses Python 3.12 in your setup)
- A configured virtual environment (recommended: the existing `venv/` in the repo)
- The environment variables required by the benchmarks you run

### Step 1: Install dependencies

From the repo root:

```powershell
pip install -e .
```

If you already have dependencies installed, this is usually enough. If you need a full reinstall:

```powershell
pip install -r requirements.txt
pip install -r dev-requirements.txt
```

### Step 2: Configure `.env`

```powershell
cp .env.example .env
```

Then edit `.env` and fill required keys (for this POC specifically, `AZURE_API_KEY` is required for the integration benchmark test to run).

---

## Run the Phase 0 POC tests (centralized)

All Phase 0 POC tests are centralized under:

**`tests/poc/`**

### Run everything in that folder

```powershell
python -m pytest tests/poc -v
```

### Run only the agent/unit tests

```powershell
python -m pytest tests/poc/test_agent_function_call.py -v
```

### Run only the registry/WorkflowBuilder tests

```powershell
python -m pytest tests/poc/test_workflow_*.py -v
```

### Run the end-to-end benchmark test

```powershell
python -m pytest tests/poc/test_benchmark_financial_analysis.py -v
```

Notes:

- This test is marked with `@skipif(not os.getenv("AZURE_API_KEY"))`
- If you do not set `AZURE_API_KEY`, it will be skipped (not failed)

---

## Run the “financial_analysis” benchmark manually (optional)

The integration test uses the existing benchmark runner and an MCP manager that starts MCP servers via local Python.

Equivalent flow:

```python
from mcpuniverse.benchmark.runner import BenchmarkRunner
from mcpuniverse.tracer.collectors import FileCollector
from mcpuniverse.callbacks.handlers.vprint import get_vprint_callbacks

from tests.poc.helpers import mcp_manager_with_local_python

import asyncio

TASK_0001 = "mcpuniverse/financial_analysis/yfinance_task_0001.json"


async def main():
    benchmark = BenchmarkRunner("mcpuniverse/financial_analysis.yaml")
    benchmark._benchmark_configs[0].tasks = [TASK_0001]

    trace_collector = FileCollector(log_file="log/mcpuniverse/financial_analysis.log")

    results = await benchmark.run(
        mcp_manager=mcp_manager_with_local_python(),
        trace_collector=trace_collector,
        callbacks=get_vprint_callbacks(),
    )
    return results


results = asyncio.run(main())
```

When Azure creds are present, the evaluator for `yfinance_task_0001` should pass at least once.

---

## Where the key proof lives (test list)

The Phase 0 POC “made in this fork” tests are:

- `tests/poc/test_agent_function_call.py`
- `tests/poc/test_workflow_azure_registry.py`
- `tests/poc/test_workflow_function_call_registry.py`
- `tests/poc/test_llm_azure_registry.py`
- `tests/poc/test_benchmark_financial_analysis.py`

---

## Troubleshooting

### “Tests fail during collection with ImportError”

If you see import errors from optional providers (for example `mistralai` mismatches), your venv dependencies are out of sync with the repo.

Fix by reinstalling pinned deps:

```powershell
pip install -e .
```

and/or recreate the venv.

---

## Next steps (not done in Phase 0)

Phase 0 here is intentionally narrow:

- Pydantic AI adapter-first migration for Azure + function-call agent.
- No MCP+ refactor scope expansion beyond what was needed for stability.

---

## Phase 1 progress (Issue #7 — react + wide research + openai/openrouter)

This branch is now extending Phase 0 into Phase 1 (per GitHub issue **#7**), still using an
adapter-first approach and preserving YAML config compatibility.

### 1) OpenAI + OpenRouter providers (Pydantic AI backed)

Added Pydantic AI-backed providers and registry aliases:

- `mcpuniverse/llm/pydantic_ai/openai.py` (`type: openai`)
  - legacy alias: `openai_legacy`
- `mcpuniverse/llm/pydantic_ai/openrouter.py` (`type: openrouter`)
  - legacy alias: `openrouter_legacy`

And updated exports so `WorkflowBuilder` can resolve the new registry entries.

Validated by tests:

- `tests/poc/test_workflow_openai_registry.py`
- `tests/poc/test_workflow_openrouter_registry.py`

### 2) ReAct agent (Pydantic AI backed)

Introduced a Pydantic AI-backed ReAct implementation that preserves the legacy
`{"thought", "action", "answer"}` JSON contract and tool execution via the existing
`MCPManager` + `call_tool()` plumbing.

Registry aliases:

- `type: react` → `PydanticAIReAct`
- `type: react_legacy` → legacy `ReAct`

Validated by:

- `tests/poc/test_workflow_react_registry.py`
- `tests/poc/test_agent_react.py`

### 3) Wide research agent registry swap (minimal adapter-first)

Swapped the registry alias for wide research so that:

- `type: function_call_wide_research` → `PydanticAIFunctionCallWideResearch`
- `type: function_call_wide_research_legacy` → legacy `FunctionCallWideResearch`

Implementation note: for Phase 1 we started with an adapter-first implementation
that reuses the existing wide-research prompt contract and runs the LLM via Pydantic AI.

Validated by:

- `tests/poc/test_workflow_wide_research_registry.py`

### 4) Registry robustness: ensure Pydantic AI agents are registered

To avoid relying on package `__init__.py` side-effects, `mcpuniverse/agent/manager.py`
now imports the Pydantic AI-backed agents so `ComponentABCMeta` registers them
before `WorkflowBuilder` snapshots the registry.

### 5) Live LLM smoke-test retry

The Phase 0 integration benchmark (`tests/poc/test_benchmark_financial_analysis.py`)
is a live-LLM smoke test and can be flaky. The test now retries the run once if the
first attempt fails to get `passed=True`.

