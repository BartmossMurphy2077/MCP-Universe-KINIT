# Intermediary README — Pydantic AI Migration Tracker

Living document for the **adapter-first** migration of MCP-Universe’s agent/LLM layer to **Pydantic AI**.

Goals throughout:

- Keep existing **YAML configs** working (registry alias swaps, not config rewrites).
- Keep **MCP tools** on the existing `MCPManager` / MCP client plumbing.
- Keep **benchmark tracing + evaluator contracts** compatible (legacy-shaped trace shim, answer unwrapping).
- Land in small phases on the long-lived integration branch `complete-refactor`, then merge to `main` when the full migration is done.

---

## Migration status at a glance

| Area | Default YAML `type` | Pydantic AI implementation | Legacy escape hatch | Phase | Status |
|------|---------------------|----------------------------|---------------------|-------|--------|
| Azure LLM | `azure` | `PydanticAIAzureModel` | `azure_legacy` | 0 | Done (merged) |
| OpenAI LLM | `openai` | `PydanticAIOpenAIModel` | `openai_legacy` | 1 | Done (merged) |
| OpenRouter LLM | `openrouter` | `PydanticAIOpenRouterModel` | `openrouter_legacy` | 1 | Done (merged) |
| Function-call agent | `function_call` | `PydanticAIFunctionCall` | `function_call_legacy` | 0 | Done (merged) |
| ReAct agent | `react` | `PydanticAIReAct` | `react_legacy` | 1 | Done (merged) |
| Wide research agent | `function_call_wide_research` | `PydanticAIFunctionCallWideResearch` | `function_call_wide_research_legacy` | 1 | Minimal adapter |
| Wide research (Claude) | `function_call_wide_claude` | — | legacy only | — | Not started |
| Other LLMs (Mistral, etc.) | various | — | legacy only | 3+ | Not started |
| LangChain integration | — | — | deferred | 5 (#11) | Not started |
| Unified context layer | `context_layer` YAML | `mcpuniverse/context/` | — | 2 | In progress (PR #8) |
| Code Mode (Monty) | via `context_layer` | `CodeMode()` harness | direct path | 2 | In progress (PR #8) |
| MCP+ fallback | via `context_layer` | `MCPWrapperManager` | legacy summarize | 2 | In progress (PR #8) |

**Test suite (`tests/poc/` + MCP+ integration):** 29 tests passing (20 POC + 9 MCP+ integration).

---

## Branch & PR history

| Phase | Branch | PR | Closes | Base | Status |
|-------|--------|-----|--------|------|--------|
| 0 | `feat/3-pydantic-ai-langchain-migration` | [#12](https://github.com/BartmossMurphy2077/MCP-Universe-KINIT/pull/12) | #6 | `complete-refactor` | Merged |
| 1 | `feat/7-phase-1-pydantic-ai-providers-agents` | [#13](https://github.com/BartmossMurphy2077/MCP-Universe-KINIT/pull/13) | #7 | `complete-refactor` | Merged |
| 2 | `feat/8-phase-2-code-mode-context-layer` | (this PR) | #8 | `complete-refactor` | Open |

Umbrella tracking issue: **#3** (PRD). Later phases: **#8** (Code Mode), **#9** (MCP+), **#10** (local LLMs), **#11** (LangChain deferred).

---

## Architecture (adapter-first)

```
YAML config (unchanged)
    │
    ▼
WorkflowBuilder ──► ModelManager / AgentManager (registry aliases)
    │
    ├── PydanticAIBaseLLM ──► pydantic_ai.Agent (LLM turns)
    │       └── build_pydantic_ai_model() per provider
    │
    └── PydanticAI*Agent ──► legacy JSON contracts (thought/action/answer)
            ├── MCP tools via mcp_tools.py adapter + call_tool()
            ├── tracing via tracing.py shim (legacy trace shape)
            └── output via response.normalize_agent_output()
```

**Key directories:**

| Path | Purpose |
|------|---------|
| `mcpuniverse/context/` | Unified context layer (Code Mode + MCP+ fallback) |
| `mcpuniverse/llm/pydantic_ai/` | Pydantic AI-backed LLM providers |
| `mcpuniverse/agent/pydantic_ai/` | Pydantic AI-backed agents + MCP adapter |
| `tests/poc/` | All migration POC / phase tests (centralized) |

---

## Phase 0 — Azure + function_call (merged via PR #12)

### What shipped

1. **Pydantic AI LLM base + Azure provider**
   - `PydanticAIBaseLLM` (`mcpuniverse/llm/pydantic_ai/base.py`)
   - `PydanticAIAzureModel` (`mcpuniverse/llm/pydantic_ai/azure.py`, alias: `azure`)

2. **Pydantic AI function-call agent**
   - `PydanticAIFunctionCall` (`mcpuniverse/agent/pydantic_ai/function_call.py`, alias: `function_call`)
   - MCP tool adapter: `mcpuniverse/agent/pydantic_ai/mcp_tools.py`
   - Tracing shim: `mcpuniverse/agent/pydantic_ai/tracing.py`

3. **Registry swaps** (YAML unchanged)
   - `azure` → Pydantic AI; `azure_legacy` → original `AzureOpenAIModel`
   - `function_call` → Pydantic AI; `function_call_legacy` → original `FunctionCall`

4. **End-to-end proof**
   - `financial_analysis` benchmark task `yfinance_task_0001` passes with live Azure LLM + yfinance MCP.

### Bug fixes uncovered during Phase 0

#### a) Answer unwrapping for evaluators

Legacy `FunctionCall` returns the inner JSON `answer`. Pydantic AI agents initially returned the outer wrapper (`{"thought": ..., "answer": ...}`), breaking evaluators.

**Fix:** `normalize_agent_output()` in `mcpuniverse/agent/pydantic_ai/response.py`, used by function-call and ReAct agents.

#### b) Yahoo Finance MCP date handling

`yfinance.Ticker(...).history(end=...)` treats `end` as **exclusive**.

**Fixes in** `mcpuniverse/mcp/servers/yahoo_finance/server.py`:

- Treat requested `end_date` as **inclusive** (add one day before `history()`)
- Normalize `Date` field to `YYYY-MM-DD` strings

#### c) MCPManager runtime config sync

`mcpuniverse/mcp/manager.py` now keeps `_raw_configs` in sync so runtime server config updates (e.g. Windows-friendly Python interpreter for stdio MCP servers) are reflected when building MCP clients.

---

## Phase 1 — OpenAI, OpenRouter, ReAct, wide research (PR #13, issue #7)

### 1) OpenAI provider

**File:** `mcpuniverse/llm/pydantic_ai/openai.py`

| YAML `type` | Class | Env vars |
|-------------|-------|----------|
| `openai` | `PydanticAIOpenAIModel` | `OPENAI_API_KEY`, optional `OPENAI_BASE_URL` |
| `openai_legacy` | `OpenAIModel` | same |

Uses Pydantic AI’s `OpenAIChatModel` + `OpenAIProvider` with `AsyncOpenAI`.

**Tests:** `tests/poc/test_workflow_openai_registry.py`

### 2) OpenRouter provider

**File:** `mcpuniverse/llm/pydantic_ai/openrouter.py`

| YAML `type` | Class | Env vars |
|-------------|-------|----------|
| `openrouter` | `PydanticAIOpenRouterModel` | `OPENROUTER_API_KEY` |
| `openrouter_legacy` | `OpenRouterModel` | same |

OpenRouter is OpenAI-compatible; uses `model_name_map` from `mcpuniverse/llm/openrouter.py` for alias resolution (e.g. `GPT5_Medium_OR` → `openai/gpt-5`).

**Tests:** `tests/poc/test_workflow_openrouter_registry.py`

### 3) ReAct agent

**File:** `mcpuniverse/agent/pydantic_ai/react.py`

| YAML `type` | Class |
|-------------|-------|
| `react` | `PydanticAIReAct` |
| `react_legacy` | `ReAct` |

Preserves the legacy JSON contract:

```json
{"thought": "...", "action": {"tool": "...", "arguments": {...}}, "answer": "..."}
```

- LLM turns via Pydantic AI (text/JSON, no native tool calling on the model).
- Tool execution via existing `MCPManager` + `call_tool()`.
- Final answer unwrapped via `normalize_agent_output()`.

**Tests:**

- `tests/poc/test_workflow_react_registry.py` — registry / WorkflowBuilder
- `tests/poc/test_agent_react.py` — execute path (mocked LLM)

### 4) Wide research agent (minimal adapter)

**File:** `mcpuniverse/agent/pydantic_ai/function_call_wide_research.py`

| YAML `type` | Class |
|-------------|-------|
| `function_call_wide_research` | `PydanticAIFunctionCallWideResearch` |
| `function_call_wide_research_legacy` | `FunctionCallWideResearch` |

Subclass of `PydanticAIFunctionCall` with wide-research config (`WideFunctionCallConfig`).

**Phase 1 scope note:** adapter-first only. The legacy scheduler / parallel tool-calling behaviour from `FunctionCallWideResearch` is **not** fully ported yet. YAML configs still resolve; behaviour may differ from legacy until a later phase.

**Tests:** `tests/poc/test_workflow_wide_research_registry.py`

### 5) Shared output normalization refactor

`normalize_agent_output()` extracted to `mcpuniverse/agent/pydantic_ai/response.py` and reused by:

- `PydanticAIFunctionCall` (refactored to import from `response.py`)
- `PydanticAIReAct`

### 6) Registry robustness

`mcpuniverse/agent/manager.py` now eagerly imports Pydantic AI agents so `ComponentABCMeta` registers them **before** `WorkflowBuilder` snapshots the registry. This avoids relying on `mcpuniverse/agent/__init__.py` side-effects (that `__init__.py` was removed on this branch).

### 7) Live LLM benchmark retry

`tests/poc/test_benchmark_financial_analysis.py` retries once on failure — live LLM smoke tests can be flaky.

---

## Live workflow smoke tests (manual PR checklist)

Optional live smoke runner (local, not required for CI):

```powershell
.\venv\Scripts\python.exe -m tests.poc.smoke_phase1_workflows openai-react
.\venv\Scripts\python.exe -m tests.poc.smoke_phase1_workflows openrouter-wide
.\venv\Scripts\python.exe -m tests.poc.smoke_phase1_workflows all
```

Files: `tests/poc/smoke_phase1_workflows.py`, `tests/poc/smoke_tasks/*.json`

| Smoke | YAML stack | Result | Notes |
|-------|------------|--------|-------|
| `openai` + `react` | temp workflow YAML → calculator MCP | **Passed** | `OPENAI_API_KEY` was empty; used `AZURE_API_KEY` via OpenAI-compatible `/openai/v1` endpoint + deployment `gpt-5.4-mini`. Response: `391` for `17 × 23`. |
| `openrouter` + `function_call_wide_research` | temp workflow YAML → calculator MCP | **Blocked** | `OPENROUTER_API_KEY` unset in `.env`. Set key and re-run. |

**Credential gotcha:** `BenchmarkRunner` does not call `workflow.set_context()`, so live smoke configs pass `api_key` / `base_url` explicitly in the LLM YAML block (the smoke runner handles this). For production YAML, env vars are picked up at LLM construction time via `OpenAIConfig` / `OpenRouterConfig` defaults.

---

## Phase 2 — Code Mode + unified context layer (issue #8)

**Branch:** `feat/8-phase-2-code-mode-context-layer`

### Unified context layer

**Package:** `mcpuniverse/context/`

| YAML block | Purpose |
|------------|---------|
| `context_layer.mode` | `auto` \| `code_mode` \| `mcp_plus` \| `direct` |
| `context_layer.code_mode_enabled` | Enable Code Mode when model supports it |
| `context_layer.mcp_plus_enabled` | Enable MCP+ fallback when Code Mode unavailable |
| `context_layer.token_threshold` | Token threshold for MCP+ summarization (default 2000) |

**Auto strategy:** picks Code Mode for capable models (gpt-4/5, claude prefixes); falls back to MCP+ otherwise.

### Code Mode integration

**File:** `mcpuniverse/agent/pydantic_ai/code_mode.py`

- Uses `pydantic-ai-harness[code-mode]` optional extra (`pip install -e ".[code-mode]"`)
- Adds `CodeMode()` capability to Pydantic AI `Agent` when strategy resolves to `code_mode`

### MCP+ fallback

**File:** `mcpuniverse/context/mcp_plus.py`

- `activate_mcp_plus_fallback()` wires `MCPWrapperManager` during agent `initialize()`
- Reuses existing MCP+ integration tests

### Function-call agent wiring

`PydanticAIFunctionCall` reads `context_layer` from `FunctionCallConfig` and applies the selected strategy at agent construction / init.

**Tests:**

| File | What it proves |
|------|----------------|
| `test_context_layer.py` | Strategy resolution, YAML config parsing |
| `test_agent_function_call_code_mode.py` | Code Mode capability on function-call agent |
| `test_context_mcp_plus_fallback.py` | MCP+ fallback activation path |

**Optional dependency note:** `pydantic-ai-harness` requires newer `pydantic-ai-slim` / `openai` than the main pin set; kept as optional `[code-mode]` extra. Code Mode tests use `pytest.importorskip("pydantic_ai_harness")`.

---

## How to run locally

### Prerequisites

- Python 3.12+ (matches project venv)
- Virtualenv: `venv/` in repo root
- `.env` with keys for the providers you test

### Install

```powershell
pip install -e .
```

If imports fail (e.g. `mistralai` version mismatch): recreate venv or `pip install mistralai==1.6.0`.

### Configure `.env`

```powershell
cp .env.example .env
```

Minimum for current test suite:

| Variable | Needed for |
|----------|------------|
| `AZURE_API_KEY` + `AZURE_API_BASE` | Live financial benchmark (`test_benchmark_financial_analysis`) |
| `OPENAI_API_KEY` | OpenAI provider smoke / workflows using `type: openai` |
| `OPENROUTER_API_KEY` | OpenRouter provider smoke / workflows using `type: openrouter` |

### Run all POC tests

```powershell
.\venv\Scripts\python.exe -m pytest tests/poc -v
```

Skip live benchmark:

```powershell
.\venv\Scripts\python.exe -m pytest tests/poc -v -k "not benchmark_financial"
```

### Run financial benchmark manually

```python
import asyncio
from mcpuniverse.benchmark.runner import BenchmarkRunner
from mcpuniverse.tracer.collectors import FileCollector
from mcpuniverse.callbacks.handlers.vprint import get_vprint_callbacks
from tests.poc.helpers import mcp_manager_with_local_python

TASK_0001 = "mcpuniverse/financial_analysis/yfinance_task_0001.json"

async def main():
    benchmark = BenchmarkRunner("mcpuniverse/financial_analysis.yaml")
    benchmark._benchmark_configs[0].tasks = [TASK_0001]
    trace_collector = FileCollector(log_file="log/mcpuniverse/financial_analysis.log")
    return await benchmark.run(
        mcp_manager=mcp_manager_with_local_python(),
        trace_collector=trace_collector,
        callbacks=get_vprint_callbacks(),
    )

asyncio.run(main())
```

---

## Test inventory (`tests/poc/`)

| Test file | What it proves |
|-----------|----------------|
| `test_agent_function_call.py` | Pydantic AI function-call execute, trace, answer unwrap |
| `test_agent_react.py` | Pydantic AI ReAct execute + JSON answer contract |
| `test_workflow_azure_registry.py` | `azure` / `azure_legacy` WorkflowBuilder resolution |
| `test_workflow_function_call_registry.py` | `function_call` / `function_call_legacy` resolution |
| `test_workflow_openai_registry.py` | `openai` / `openai_legacy` resolution |
| `test_workflow_openrouter_registry.py` | `openrouter` / `openrouter_legacy` resolution |
| `test_workflow_react_registry.py` | `react` / `react_legacy` resolution |
| `test_workflow_wide_research_registry.py` | `function_call_wide_research` / legacy resolution |
| `test_benchmark_financial_analysis.py` | End-to-end: Azure + function_call + yfinance task (live LLM) |
| `test_context_layer.py` | Context strategy resolution + YAML config |
| `test_agent_function_call_code_mode.py` | Code Mode capability on function-call agent |
| `test_context_mcp_plus_fallback.py` | MCP+ fallback activation |
| `helpers.py` | `mcp_manager_with_local_python()` — Windows-friendly stdio MCP |
| `smoke_phase1_workflows.py` | Optional live workflow smoke (see above) |

---

## File change map (Phase 0 + Phase 1 + Phase 2 on this branch)

### New files

```
mcpuniverse/llm/pydantic_ai/
  base.py, azure.py, openai.py, openrouter.py
mcpuniverse/agent/pydantic_ai/
  function_call.py, react.py, function_call_wide_research.py
  mcp_tools.py, tracing.py, response.py
tests/poc/
  test_workflow_openai_registry.py
  test_workflow_openrouter_registry.py
  test_workflow_react_registry.py
  test_workflow_wide_research_registry.py
  test_agent_react.py
  smoke_phase1_workflows.py          # optional local smoke
  smoke_tasks/react_calculator.json
mcpuniverse/context/
  __init__.py, layer.py, mcp_plus.py
mcpuniverse/agent/pydantic_ai/
  code_mode.py
tests/poc/
  test_context_layer.py
  test_agent_function_call_code_mode.py
  test_context_mcp_plus_fallback.py
```

### Modified files

```
mcpuniverse/llm/openai.py              # openai_legacy alias
mcpuniverse/llm/openrouter.py          # openrouter_legacy alias
mcpuniverse/llm/__init__.py            # exports
mcpuniverse/llm/pydantic_ai/__init__.py
mcpuniverse/agent/react.py             # react_legacy alias
mcpuniverse/agent/function_call_wide.py # wide_research legacy aliases
mcpuniverse/agent/manager.py           # eager Pydantic AI imports
mcpuniverse/agent/pydantic_ai/__init__.py
mcpuniverse/agent/pydantic_ai/function_call.py  # uses response.py
mcpuniverse/mcp/manager.py             # _raw_configs sync (Phase 0)
mcpuniverse/mcp/servers/yahoo_finance/server.py # date fixes (Phase 0)
mcpuniverse/agent/function_call.py       # context_layer field on FunctionCallConfig
mcpuniverse/agent/pydantic_ai/function_call.py  # context strategy wiring
mcpuniverse/agent/pydantic_ai/mcp_tools.py
mcpuniverse/agent/pydantic_ai/tracing.py # null-safe usage in summarize_run_for_trace
pyproject.toml                           # optional [code-mode] extra
```

### Removed

```
mcpuniverse/agent/__init__.py          # replaced by manager.py eager imports
```

---

## Known limitations & follow-ups

1. **Wide research is minimal** — scheduler / parallel tool-calling from legacy not ported; only registry swap + Pydantic AI LLM turns.
2. **`function_call_wide_claude` not migrated** — still legacy only.
3. **`BenchmarkRunner` + `Context`** — smoke tests revealed credentials are not propagated via `workflow.set_context()`; env vars must be present at LLM init or inlined in YAML config.
4. **Live LLM flakiness** — benchmark retry helps; structural fixes (answer unwrap, yfinance dates) already in place.
5. **OneDrive sync** — `mcpuniverse/agent/__init__.py` deletion may reappear as a sync glitch; restore from `origin/complete-refactor` if needed.
6. **Remaining providers** — Mistral, Anthropic, DeepSeek, Ollama, Gemini, xAI, etc. still on legacy paths.

---

## What's next (not in Phase 2)

| Issue | Scope |
|-------|-------|
| #9 | MCP+ deeper integration |
| #10 | Local LLMs (Ollama, vLLM) |
| #11 | LangChain (deferred) |

Within the Pydantic AI migration itself, likely next slices:

- Full wide-research scheduler port
- `function_call_wide_claude`
- Wire context layer into ReAct / wide research agents
- Live Code Mode benchmark + token reduction metrics
- Remaining LLM providers (one vertical slice per provider, same registry pattern)
- Remove legacy paths once all benchmarks pass on Pydantic AI defaults

---

## Troubleshooting

### Tests fail during collection (`ImportError`, `mistralai`)

```powershell
pip install -e .
# or pin: pip install mistralai==1.6.0
```

### `test_benchmark_financial_analysis` skipped

Set `AZURE_API_KEY` and `AZURE_API_BASE` in `.env`.

### MCP stdio servers fail on Windows

Use `tests.poc.helpers.mcp_manager_with_local_python()` — it points stdio servers at `sys.executable`.

### `gh pr create` targets wrong repo

This fork is `BartmossMurphy2077/MCP-Universe-KINIT`. Pass `-R BartmossMurphy2077/MCP-Universe-KINIT` if `gh` defaults to upstream `SalesforceAIResearch/MCP-Universe`.
