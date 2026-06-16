# PRD: Pydantic AI Migration (adapter-first)

> Umbrella PRD. Design doc: [`docs/design/langchain-pydantic-ai-migration.md`](langchain-pydantic-ai-migration.md)
>
> Near-term reality is **Pydantic AI + Monty Code Mode**. LangChain is a deferred, optional remote-sandbox backend only — it does **not** own code-mode.

## Problem Statement

MCP-Universe maintains a custom agent and LLM framework (BaseLLM, BaseAgent, hand-rolled ReAct and function-call loops, YAML-driven WorkflowBuilder, ComponentABCMeta registry). While functional and benchmark-proven, this stack is difficult for new contributors to learn because patterns are project-specific rather than aligned with widely adopted open-source ecosystems. Three parallel agent stacks already exist (`BaseLLM` agents, `OpenAIAgentSDK`, `ClaudeCodeAgent`) plus `TITOLLMWrapper` for RL, each bypassing the common contract differently.

The framework also faces growing context-window pressure from verbose MCP tool outputs. Multiple overlapping mitigation mechanisms exist today (MCP+, `summarize_tool_response`, in-process `SafeCodeExecutor`, `python-code-sandbox` Docker MCP), and there is no unified strategy for programmatic tool calling (code-mode).

The team needs a maintainable path to adopt **Pydantic AI** for agent runtime and context reduction — while continuing to support OpenAI, Azure, OpenRouter, and (later) local LLMs (vllm_local / sglang_local) — without breaking existing benchmarks, YAML configs, or trace/report outputs.

## Solution

Adopt an **adapter-first migration**: Pydantic AI becomes the primary agent runtime; the existing MCPClient layer, BenchmarkRunner, evaluators, env_pool, and tracing remain the source of truth with thin adapters on top.

New Pydantic AI-backed agent and LLM classes **claim the existing YAML `type:` aliases via the component registry** (registry swap); the legacy implementations are renamed to `*_legacy` aliases and kept for rollback and comparison. Benchmark configs require no edits.

Context reduction is layered: **Pydantic AI Code Mode (Monty)** is the primary programmatic-tool-calling mechanism for capable models, and **MCP+ remains as a model-agnostic fallback** for single oversized tool payloads. The two are complementary, not competing.

Deliverable for the analysis task: **design document + POC** proving one benchmark domain runs end-to-end on the new stack.

## User Stories

1. As a **framework maintainer**, I want agents implemented on Pydantic AI, so that new contributors can use familiar OSS patterns instead of learning custom BaseAgent loops.

2. As a **framework maintainer**, I want a single internal LLM provider factory covering OpenAI-family providers (openai, azure, openrouter, and OpenAI-compatible local endpoints), so that adding or switching providers does not require duplicate agent code.

3. As a **benchmark operator**, I want existing YAML benchmark configs to work unchanged, so that CI and Azure benchmark scripts do not break mid-migration.

4. As a **benchmark operator**, I want BenchmarkRunner, Task evaluators, and BenchmarkReport to work without modification, so that evaluation infrastructure investment is preserved.

5. As a **benchmark operator**, I want trace files and report output to remain compatible with current tooling, so that historical comparison and MCP+ tracer analysis still work.

6. As a **research engineer**, I want function_call agents migrated to Pydantic AI first, so that the most YAML-common agent type proves the adapter pattern quickly.

7. As a **research engineer**, I want react agents migrated for models without reliable native tool calling, so that local-LLM benchmarks remain viable in a later phase.

8. As a **research engineer**, I want wide research agents migrated, so that the flagship parallel tool-calling feature stays on the maintained stack.

9. As a **research engineer**, I want MCP tools exposed to Pydantic AI agents via adapters over the existing MCPClient, so that permissions, gateway routing, and env_pool integration are not reimplemented.

10. As a **research engineer**, I want tool names to remain in the `server__tool` convention, so that existing evaluators and task definitions stay valid.

11. As a **context-cost owner**, I want a unified context reduction layer, so that Code Mode and MCP+ are composed deliberately instead of competing ad hoc mechanisms.

12. As a **context-cost owner**, I want Code Mode / programmatic tool calling via Pydantic AI (Monty sandbox) for supported models, so that agents can call tools in code and only return final results to chat history.

13. As a **context-cost owner**, I want MCP+ as a model-agnostic fallback for single oversized tool payloads, so that large one-shot outputs are still compressed at the MCP transport layer even when Code Mode is unavailable.

14. As a **context-cost owner**, I want MCP+ `PostProcessAgent` refactored onto Pydantic AI, so that the extension is maintainable alongside the new agent stack.

15. As a **security-conscious operator**, I want env_pool to continue provisioning isolated Docker MCP Gateway environments, so that Playwright, Postgres, and Blender tasks remain properly isolated.

16. As a **security-conscious operator**, I want Code Mode to run in the Monty in-process sandbox (no filesystem/network/env access), so that generated Python cannot escape to the host.

17. As a **security-conscious operator**, I want a hybrid execution strategy, so that MCP-heavy benchmarks use env_pool, code-mode uses Monty, and general Python execution uses the existing `python-code-sandbox` MCP.

18. As a **local LLM user**, I want vllm_local and sglang_local supported via OpenAI-compatible Pydantic AI providers in a later phase, so that local inference does not require separate agent implementations.

19. As an **OpenRouter user**, I want openrouter supported via the same provider factory, so that model routing stays configuration-driven.

20. As an **OpenAI / Azure user**, I want openai and azure providers supported, so that cloud benchmark scripts (e.g. Azure benchmarks) continue to work.

21. As an **RL engineer**, I want RL, TITO, and VERL integration to remain on the legacy stack during early phases, so that the OSS migration does not block training workflows.

22. As a **workflow author**, I want custom orchestration workflows (chain, router, orchestrator) to remain on the legacy stack initially, so that migration scope stays bounded.

23. As a **contributor writing tests**, I want the POC validated by an existing benchmark integration test, so that viability is proven by external behavior not unit mocks.

24. As a **contributor writing tests**, I want provider/agent tests following existing test patterns, so that test style stays consistent.

25. As a **contributor writing tests**, I want registry resolution tested so legacy `type:` aliases instantiate the Pydantic AI implementations, so that YAML compatibility is regression-protected.

26. As a **project lead**, I want a phased roadmap split into independently reviewable child issues, so that work can be parallelised and reviewed in small PRs.

27. As a **project lead**, I want an analysis deliverable (design doc + working POC), so that stakeholders can sign off before full implementation.

28. As a **downstream integrator**, I want the Executor contract (`execute` → AgentResponse) preserved, so that FastAPI app and pipeline launcher integrations do not break.

29. As an **MCP+ user**, I want `mcp-build-plus` CLI and wrapper configs to keep working, so that Cursor/Claude Code integrations are not disrupted during the MCP+ refactor.

30. As a **future maintainer**, I want legacy BaseLLM/BaseAgent types kept as `*_legacy` aliases rather than deleted immediately, so that rollback and gradual migration are possible.

## Implementation Decisions

### Strategy

- **Adapter-first, not rewrite.** Approximately 70% of the codebase (MCP layer, benchmarks, evaluators, env_pool, tracing) stays; agent loops, the internal LLM provider factory, and context middleware are the rewrite surface.
- **Pydantic AI owns the agent runtime and code-mode.** LangChain is **not** adopted as a second agent framework and does **not** own code-mode; it is a deferred, optional remote-sandbox backend only.

### YAML compatibility — registry swap (not transparent routing)

- New Pydantic AI-backed classes **claim the existing aliases** through the `ComponentABCMeta` registry: e.g. the new function-call agent registers alias `function_call`; the legacy class is renamed to `function_call_legacy`.
- Same pattern for the LLM layer: the new Pydantic AI-backed model claims `azure` (and later `openai`, `openrouter`); legacy classes become `azure_legacy`, etc.
- No WorkflowBuilder special-case routing table. No external YAML changes. Rollback = point YAML `type:` at the `*_legacy` alias.

### LLM provider factory

- An internal provider factory builds a Pydantic AI model for OpenAI-family providers (openai, azure, openrouter, and OpenAI-compatible local endpoints) behind the claimed aliases.
- POC proves `azure` (the provider `financial_analysis.yaml` currently uses). openai/openrouter follow in Phase 1.
- Local providers (vllm_local/sglang_local) are deferred to their own phase.

### Agent migration

- **POC:** function_call only, `azure` provider.
- **Phase 1:** react and wide research agents; openai + openrouter providers.
- Agents implement the existing Executor contract; internally delegate to a Pydantic AI Agent with MCP toolsets.

### MCP integration

- MCPClient and MCPManager remain source of truth.
- A new adapter layer converts MCPClient tools into Pydantic AI tool definitions (delegating execution to `execute_tool`) **without** replacing transport, permissions, gateway, or env_pool logic.
- The `server__tool` naming convention is preserved at the adapter boundary.

### Context layer

- **Primary:** Pydantic AI Code Mode via `pydantic-ai-harness[code-mode]` (Monty sandbox) — wraps tools into a single `run_code` tool; MCP tools wrapped with `native=False` so they route through the local toolset and into the sandbox.
- **Fallback:** MCP+ wrapper for single oversized tool payloads and models that cannot do code-mode.
- The duplicate `summarize_tool_response` paths on legacy agents are deprecated over time in favour of this layer. MCP+ itself is **kept**.

### Sandboxes / execution (hybrid)

- **env_pool:** unchanged for benchmark and RL MCP Gateway isolation.
- **Monty:** in-process sandbox for Code Mode (no fs/network/env).
- **`python-code-sandbox` MCP:** remains for general Docker-isolated Python execution.
- **LangChain remote sandboxes** (Modal/Daytona/Runloop/LocalShell): **deferred, optional** — only if a concrete benchmark needs remote shell/filesystem execution that Monty deliberately forbids.

### Tracing and callbacks

- Existing Tracer, FileCollector, MemoryCollector, and callback event bus preserved.
- Pydantic AI agents emit **legacy-shaped** trace records (`type: agent | llm | tool`) via adapters at the `execute()` boundary, so `BenchmarkReport` needs no changes.

### Dependencies

- POC: add `pydantic-ai-slim[openai]` (covers openai/azure/openrouter/OpenAI-compatible local through one provider).
- Code Mode phase: add `pydantic-ai-harness[code-mode]` (pulls in Monty).
- LangChain `deepagents` / sandbox partner packages: deferred, only if the optional sandbox phase is activated.
- Do not remove existing OpenAI SDK / openai-agents usage until legacy `*_legacy` aliases are deprecated.

### Registration

- New agents and LLM classes register via the existing ComponentABCMeta / AgentManager / ModelManager patterns so YAML `type:` resolution continues to work.

## Testing Decisions

### Principles

- Test **external behavior** at the highest seam possible, not internal Pydantic AI call structure.
- Prefer integration tests over mocking LLM responses when proving migration viability.
- Existing skipped benchmark tests are the template for POC validation; gate live runs behind credential `skipif` rather than a bare `skip`.

### Modules / seams to test

| Seam | Behavior under test | Prior art |
|------|---------------------|-----------|
| BenchmarkRunner + unchanged YAML | Full benchmark run produces evaluation results | `tests/benchmark/mcpuniverse/test_benchmark_*.py` |
| Registry resolution | Legacy `type:` aliases instantiate Pydantic AI-backed classes; `*_legacy` resolves to old ones | `tests/workflow/test_workflow_builder*.py` |
| Provider factory | Each provider produces valid generation | `tests/llm/test_openai.py`, `test_openrouter.py` |
| Executor.execute | Agent returns AgentResponse; invokes MCP tools | `tests/agent/test_function_call.py` |
| Tracing | FileCollector receives `agent/llm/tool` records; `BenchmarkReport.dump()` succeeds | `tests/tracer/test_tracer.py` |
| MCP+ context layer | Large outputs compressed when threshold exceeded | `tests/extensions/mcpplus/integration/test_integration.py` |

### POC test gate

- `financial_analysis` benchmark passes end-to-end with the Pydantic AI function_call agent and `provider: azure`.
- YAML config file unchanged from current version.
- At least one task (`yfinance_task_0001`, the deterministic MSFT date-range task) reports `passed=True`.
- `BenchmarkReport.dump()` generates without trace-shape errors.
- The integration test uses `@pytest.mark.skipif(not os.getenv("AZURE_API_KEY"))` so CI stays green without secrets.

### Out of scope for POC tests

- react and wide research (Phase 1).
- Code Mode / Monty (Code Mode phase).
- MCP+ refactor (its own phase).
- RL rollouts and env_pool docker_pool mode.
- Local LLM providers (their own phase).

## Out of Scope

- Full migration of all agent types in one effort.
- Replacing MCPClient with Pydantic AI / LangChain MCP clients.
- Retiring env_pool in favour of cloud-only sandboxes.
- Replacing MCP+ entirely with Code Mode.
- Adopting the LangChain QuickJS interpreter (redundant with Monty).
- RL / TITO / VERL / react_train_agent migration.
- Custom workflow orchestration migration to LangGraph.
- Benchmark score parity guarantees with legacy agents.
- Removing legacy BaseLLM and BaseAgent in early phases.
- Committing secrets or API keys in tests or configs.

## Further Notes

- **MCP+ vs CE:** "CE" refers to code execution / code-mode (programmatic tool calling), not a named repo component. Code Mode and MCP+ are complementary.
- **Two code-mode engines exist in the ecosystem** — Pydantic AI Code Mode (Monty / Python) and LangChain Deep Agents interpreter (QuickJS / JavaScript). We deliberately choose **only Monty**, since Pydantic AI is the agent runtime and our tools/evaluators are Python.
- **No existing LangChain or Pydantic AI footprint** in the codebase today; the repo ships `pydantic==2.11.7` and `openai-agents==0.2.11` (unrelated to the Pydantic AI agent framework).
- **Design doc** with architecture diagram, phased roadmap, and decision log: [`docs/design/langchain-pydantic-ai-migration.md`](langchain-pydantic-ai-migration.md).
- **Open questions** for follow-up: whether served vllm/sglang endpoints support native tool calling (else react-parse fallback); which remote sandbox provider, if any, is ever needed.
