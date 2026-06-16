# Design: Pydantic AI Migration (adapter-first)

> Status: **Proposed** (grill sessions + PRD, June 2026)  
> Deliverable type: ADR + POC, then phased implementation

## Summary

Migrate MCP-Universe's agent and LLM layers onto **Pydantic AI** (agent runtime + code-mode) while preserving the benchmark infrastructure, custom MCP client layer, tracing, and existing YAML configurations.

Code-mode is owned by **Pydantic AI Code Mode** (the Monty in-process Python sandbox), not LangChain. **LangChain Deep Agents** is a *deferred, optional* remote-sandbox backend only (Modal/Daytona/Runloop/LocalShell), used solely if a benchmark ever needs remote shell/filesystem execution that Monty deliberately forbids. The LangChain QuickJS interpreter is **not** adopted (redundant with Monty).

**Strategy: adapter-first, not rewrite. YAML compatibility via registry swap.**

---

## Problem

MCP-Universe ships a custom agent framework (BaseLLM, BaseAgent, hand-rolled ReAct/function-call loops, ComponentABCMeta registry, YAML WorkflowBuilder). This works but:

- Onboarding cost is high — patterns are project-specific, not industry-standard.
- Context-window pressure from verbose MCP tool outputs requires bespoke solutions (MCP+, summarize_tool_response, in-process SafeCodeExecutor).
- Multiple parallel LLM integration paths already exist (OpenAI SDK, Anthropic, openai-agents, claude-code-sdk, TITO/vLLM direct).
- Adding LangChain + Pydantic AI as *additional* stacks without a plan increases surface area.

The assigned task is to **analyze and prove viability** of migrating to LangChain and Pydantic AI for OpenAI, OpenRouter, and local LLMs (vllm_local / sglang_local), including CodeMode and MCP+ vs code-execution (CE) tradeoffs.

---

## Goals

| Goal | Priority |
|------|----------|
| Maintainability via OSS agent frameworks | **Primary** |
| CodeMode + unified context reduction | **High** |
| Existing benchmark YAML unchanged | **High** |
| Benchmark trace/report format unchanged | **High** |
| Score parity with legacy agents | **Low** (not a gate) |

---

## Non-Goals (Phase 1)

- RL / TITO / VERL rollout engine migration
- Custom workflow orchestration (chain, router, orchestrator) → LangGraph
- Replacing MCPClient / MCPManager
- Replacing env_pool with cloud-only sandboxes
- Big-bang migration of all agent types

---

## Architecture

### Layer responsibilities

```
┌─────────────────────────────────────────────────────────────┐
│  YAML configs (unchanged externally)                      │
│  kind: llm (openai, openrouter, vllm_local, …)            │
│  kind: agent (function_call, react, …)                      │
└──────────────────────────┬──────────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────────┐
│  WorkflowBuilder — transparent routing                      │
│  Legacy type aliases → Pydantic AI implementations            │
└──────────────────────────┬──────────────────────────────────┘
                           │
        ┌──────────────────┼──────────────────┐
        │                  │                  │
┌───────▼───────┐  ┌───────▼───────┐  ┌───────▼───────┐
│ Pydantic AI   │  │ Unified       │  │ Tracing       │
│ agents        │  │ context layer │  │ (adapters)    │
│               │  │               │  │               │
│ function_call │  │ CodeMode/PTC  │  │ FileCollector │
│ react         │  │ (LangChain)   │  │ BenchmarkRpt  │
│ wide research │  │ MCP+ fallback │  │               │
└───────┬───────┘  └───────┬───────┘  └───────────────┘
        │                  │
┌───────▼──────────────────▼──────────────────────────────────┐
│  MCPClient / MCPManager (unchanged — source of truth)       │
│  Thin adapters expose MCP tools to Pydantic AI / LangChain  │
└───────┬────────────────────────────────────────────────────┘
        │
┌───────▼────────────────────────────────────────────────────┐
│  Execution environments (hybrid)                           │
│  • env_pool — Docker MCP Gateway stacks (benchmarks, RL)   │
│  • LangChain Sandboxes — CodeMode, general code execution  │
│  • python_code_sandbox MCP — legacy narrow Python exec     │
└────────────────────────────────────────────────────────────┘
```

### Framework split

| Concern | Owner | Rationale |
|---------|-------|-----------|
| Agent loop, tool calling, structured outputs | **Pydantic AI** | Fits existing Pydantic v2 usage |
| LLM providers (OpenAI, Azure, OpenRouter, + later local) | **Pydantic AI** via internal provider factory | One `OpenAIProvider(base_url=…)` covers azure/openrouter/OpenAI-compatible local |
| Code-mode / PTC (context reduction) | **Pydantic AI Code Mode (Monty)** | Python sandbox, same framework as the runtime; matches Python tools/evaluators |
| MCP tool transport, permissions, gateway | **Custom MCPClient** (adapter on top) | Domain logic not in generic OSS clients |
| Benchmarks, evaluators, tasks | **Unchanged** | Only need `Executor.execute()` contract |
| Remote shell/filesystem sandboxes | **LangChain Deep Agents** (deferred, optional) | Only if a benchmark needs fs/network Monty forbids |

### Execution environments (hybrid)

| | env_pool | Monty (Code Mode) | `python-code-sandbox` MCP | LangChain remote sandbox |
|---|----------|-------------------|---------------------------|--------------------------|
| **Isolates** | Full MCP stack (Gateway + servers) | In-process Python subset, no fs/net | Docker Python exec | Remote shell + filesystem |
| **Use for** | Playwright, Postgres, Blender; RL docker_pool | Programmatic tool calling / context reduction | General Python execution as a tool | *(deferred)* fs/net-heavy code |
| **Status** | Keep | Adopt (Code Mode phase) | Keep | Deferred / optional |

### MCP+ vs Code Mode (CE)

| | MCP+ | Code Mode / PTC (Monty) |
|---|------|-------------------------|
| **Layer** | MCP transport (wrapper on tool output) | Agent runtime (Pydantic AI capability) |
| **Trigger** | Single tool response exceeds token threshold | Model can write competent Python |
| **Strength** | Model-agnostic; one huge payload | Multi-call workflows; intermediate results stay out of context |
| **Verdict** | **Keep** as fallback — refactor PostProcessAgent onto Pydantic AI | **Add** — complementary, not a replacement |

**Unified context layer:** try Code Mode when the model supports it; fall back to MCP+ for single oversized payloads and non-code-mode models; deprecate duplicate `summarize_tool_response` paths over time. MCP+ itself is kept.

### LLM provider factory

An **internal** factory builds a Pydantic AI model for OpenAI-family providers. The new model classes **claim the legacy aliases via the registry** (registry swap) — there is no external `pydantic_ai` type and no WorkflowBuilder routing table.

| alias (unchanged in YAML) | Backend | Phase |
|----------|---------|-------|
| `azure` | Azure OpenAI via Pydantic AI OpenAI provider | POC |
| `openai` | OpenAI API | Phase 1 |
| `openrouter` | OpenAI-compatible base URL | Phase 1 |
| `vllm_local` / `sglang_local` | OpenAI-compatible local server | Deferred phase |

Legacy classes are renamed to `azure_legacy`, `openai_legacy`, etc., and kept for rollback/comparison.

---

## Phased delivery

### Phase 0 — POC (deliverable for analysis task)

- [ ] Internal provider factory; new Pydantic AI model claims `azure` alias (legacy → `azure_legacy`)
- [ ] Pydantic AI `function_call` agent claims `function_call` alias (legacy → `function_call_legacy`)
- [ ] MCPClient adapter exposing tools as Pydantic AI tools (`server__tool` preserved)
- [ ] Tracing adapters emitting legacy-shaped `agent/llm/tool` records at `execute()` boundary
- [ ] `financial_analysis` end-to-end, YAML unchanged, `provider: azure`
- [ ] Code Mode and MCP+ refactor deferred (MCP+ untouched)

**POC pass:** `financial_analysis` integration test (gated by `skipif AZURE_API_KEY`) runs; `yfinance_task_0001` reports `passed=True`; `BenchmarkReport.dump()` succeeds; YAML unchanged.

### Phase 1 — Benchmark agents + cloud providers

- [ ] Migrate `react` agent
- [ ] Migrate wide research agent
- [ ] `openai` + `openrouter` providers via factory (registry swap)
- [ ] Provider + agent tests following existing patterns

### Phase 2 — Code Mode + unified context layer

- [ ] Add `pydantic-ai-harness[code-mode]` (Monty)
- [ ] Code Mode for capable models, MCP tools wrapped `native=False`
- [ ] Unified context middleware (Code Mode → MCP+ fallback chain)
- [ ] Deprecation path for duplicate `summarize_tool_response`

### Phase 3 — MCP+ refactor

- [ ] Refactor MCP+ `PostProcessAgent` onto Pydantic AI
- [ ] Keep `mcp-build-plus` CLI + wrapper configs working

### Phase 4 — Local LLMs

- [ ] `vllm_local`/`sglang_local` via OpenAI-compatible Pydantic AI provider
- [ ] Verify served endpoint native tool calling; react-parse fallback if unreliable

### Phase 5 — Sandboxes (deferred, optional)

- [ ] Only if a benchmark needs remote shell/fs: evaluate LangChain remote sandbox (Modal/Daytona/Runloop/LocalShell)
- [ ] Optional: wrap env_pool as a custom `BaseSandbox` backend

### Phase 6 — Cleanup

- [ ] Deprecate legacy `*_legacy` internals (keep aliases)
- [ ] Optional: migrate tracing to Pydantic AI / Logfire
- [ ] Documentation update

---

## Key interfaces (stable contracts)

These seams must not break during migration:

1. **Executor** — `async execute(message) -> AgentResponse`
2. **BenchmarkRunner.run()** — accepts trace_collector, returns benchmark results
3. **WorkflowBuilder** — loads multi-doc YAML, resolves `kind: llm | agent | workflow`; new classes claim aliases via `ComponentABCMeta`
4. **MCPClient.execute_tool()** — tool naming `server__tool`
5. **BenchmarkReport** — consumes trace collector output (`agent/llm/tool` records)

---

## Testing strategy

Tests at the **highest seam possible** — external behavior, not implementation:

| Seam | What to assert | Prior art |
|------|----------------|-----------|
| BenchmarkRunner + YAML | Full run completes; evaluation results present | `tests/benchmark/mcpuniverse/test_benchmark_*.py` |
| Registry resolution | Legacy `type:` instantiates Pydantic AI-backed class; `*_legacy` resolves to old | `tests/workflow/test_workflow_builder_azure.py` |
| Provider factory | Each provider generates valid responses | `tests/llm/test_openai.py`, `test_openrouter.py` |
| Agent execute | Returns AgentResponse; calls tools via MCP | `tests/agent/test_function_call.py` |
| Tracing | FileCollector records trace IDs used by report; `dump()` succeeds | `tests/tracer/test_tracer.py` |
| MCP+ context layer | Large tool output compressed | `tests/extensions/mcpplus/integration/test_integration.py` |

POC minimum: `financial_analysis` integration test green with `provider: azure`, `yfinance_task_0001` passing, gated by `skipif AZURE_API_KEY`.

---

## Open questions

1. **Local LLM tool calling** — do served vllm/sglang endpoints support native tool calling, or do we need react-parse fallback? (Phase 4)
2. **Remote sandbox providers** — is any benchmark ever going to need Modal/Daytona/Runloop, or is env_pool + `python-code-sandbox` MCP sufficient? (Phase 5, deferred)

---

## Decision log (grill sessions)

| # | Decision |
|---|----------|
| 1 | Maintainability > benchmark parity |
| 2 | **Adapter-first**, not full rewrite |
| 3 | Pydantic AI owns runtime **and code-mode**; LangChain deferred optional remote sandbox only |
| 4 | Code-mode engine = **Pydantic AI Code Mode (Monty)**; no LangChain QuickJS interpreter |
| 5 | Unified context layer: Code Mode primary + MCP+ fallback (both kept, complementary) |
| 6 | Keep MCPClient; adapters only; `server__tool` preserved |
| 7 | YAML compat via **registry swap** (`function_call`→`function_call_legacy`, `azure`→`azure_legacy`); no routing table |
| 8 | Internal provider factory; POC proves `azure`; openai/openrouter Phase 1; local deferred |
| 9 | Tracing: legacy-shaped `agent/llm/tool` records via adapters at execute(); no BenchmarkReport changes |
| 10 | POC: `financial_analysis`, YAML unchanged, `yfinance_task_0001` passes, `skipif AZURE_API_KEY` |
| 11 | Deps: `pydantic-ai-slim[openai]` for POC; `pydantic-ai-harness[code-mode]` at Code Mode phase |
| 12 | MCP+ `PostProcessAgent` refactor is its own phase (out of POC) |
| 13 | Deliverable: ADR + POC; umbrella issue #3 + per-phase child issues |

---

## References

- [MCP-Universe system architecture](../system-architecture.md)
- [MCP+ README](../../mcpuniverse/extensions/mcpplus/README.md)
- [env_pool README](../../mcpuniverse/mcp/env_pool/README.md)
- [LangChain Deep Agents — Sandboxes](https://docs.langchain.com/oss/python/deepagents/sandboxes)
- [Pydantic AI — MCP Client](https://ai.pydantic.dev/mcp/client/)
