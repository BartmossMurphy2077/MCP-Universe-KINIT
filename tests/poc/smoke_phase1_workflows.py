"""One-off smoke runners for Phase 1 PR checklist (live LLM)."""
from __future__ import annotations

import argparse
import asyncio
import os
import sys
import tempfile
from pathlib import Path

import yaml
from dotenv import load_dotenv

from mcpuniverse.benchmark.runner import BenchmarkRunner
from mcpuniverse.common.context import Context
from mcpuniverse.tracer.collectors import MemoryCollector
from tests.poc.helpers import mcp_manager_with_local_python

REPO_ROOT = Path(__file__).resolve().parents[2]


def _ensure_openai_credentials() -> None:
    if os.getenv("OPENAI_API_KEY"):
        return
    azure_key = os.getenv("AZURE_API_KEY")
    azure_base = os.getenv("AZURE_API_BASE", "").rstrip("/")
    if not azure_key or not azure_base:
        raise RuntimeError(
            "OPENAI_API_KEY is unset and AZURE_API_KEY/AZURE_API_BASE are unavailable"
        )
    os.environ["OPENAI_API_KEY"] = azure_key
    os.environ.setdefault("OPENAI_BASE_URL", f"{azure_base}/openai/v1")


def _write_yaml(path: Path, documents: list[dict]) -> None:
    with path.open("w", encoding="utf-8") as handle:
        yaml.safe_dump_all(documents, handle, sort_keys=False)


def _openai_react_config(model_name: str) -> list[dict]:
    llm_config: dict = {"model_name": model_name, "max_completion_tokens": 1024}
    if os.getenv("OPENAI_API_KEY"):
        llm_config["api_key"] = os.environ["OPENAI_API_KEY"]
    if os.getenv("OPENAI_BASE_URL"):
        llm_config["base_url"] = os.environ["OPENAI_BASE_URL"]
    return [
        {
            "kind": "llm",
            "spec": {
                "name": "llm-1",
                "type": "openai",
                "config": llm_config,
            },
        },
        {
            "kind": "agent",
            "spec": {
                "name": "react-agent",
                "type": "react",
                "config": {
                    "llm": "llm-1",
                    "instruction": (
                        "You are a helpful assistant. Respond using the JSON "
                        "thought/answer contract. Keep answers short."
                    ),
                    "max_iterations": 5,
                    "servers": [{"name": "calculator"}],
                },
            },
        },
        {
            "kind": "benchmark",
            "spec": {
                "description": "Phase 1 smoke: openai + react",
                "agent": "react-agent",
                "tasks": ["tests/poc/smoke_tasks/react_calculator.json"],
            },
        },
    ]


def _openrouter_wide_research_config(model_name: str) -> list[dict]:
    llm_config: dict = {"model_name": model_name, "max_completion_tokens": 1024}
    if os.getenv("OPENROUTER_API_KEY"):
        llm_config["api_key"] = os.environ["OPENROUTER_API_KEY"]
    return [
        {
            "kind": "llm",
            "spec": {
                "name": "llm-1",
                "type": "openrouter",
                "config": llm_config,
            },
        },
        {
            "kind": "agent",
            "spec": {
                "name": "wide-agent",
                "type": "function_call_wide_research",
                "config": {
                    "llm": "llm-1",
                    "instruction": (
                        "You are a helpful assistant. Answer briefly using the "
                        "function-call JSON contract."
                    ),
                    "max_iterations": 5,
                    "servers": [{"name": "calculator"}],
                },
            },
        },
        {
            "kind": "benchmark",
            "spec": {
                "description": "Phase 1 smoke: openrouter + wide research",
                "agent": "wide-agent",
                "tasks": ["tests/poc/smoke_tasks/wide_calculator.json"],
            },
        },
    ]


async def _run_smoke(config_path: Path, label: str) -> None:
    context = Context(env=dict(os.environ))
    runner = BenchmarkRunner(str(config_path), context=context)
    results = await runner.run(
        mcp_manager=mcp_manager_with_local_python(),
        trace_collector=MemoryCollector(),
    )
    if len(results) != 1:
        raise RuntimeError(f"{label}: expected 1 benchmark result, got {len(results)}")

    task_results = next(iter(results[0].task_results.values()))
    eval_results = task_results.get("evaluation_results", task_results)
    if not isinstance(eval_results, list):
        eval_results = task_results.get("evaluation_results", [])
    passed = any(getattr(r, "passed", False) for r in eval_results)
    response = getattr(eval_results[0], "response", "") if eval_results else ""
    print(f"\n=== {label} ===")
    print(f"response: {response!r}")
    print(f"evaluation passed: {passed}")
    if not passed:
        for result in eval_results:
            print(f"  - {result}")
        raise RuntimeError(f"{label} smoke failed evaluation")


async def smoke_openai_react(model_name: str) -> None:
    _ensure_openai_credentials()
    with tempfile.TemporaryDirectory() as tmp:
        config_path = Path(tmp) / "openai_react_smoke.yaml"
        _write_yaml(config_path, _openai_react_config(model_name))
        await _run_smoke(config_path, "openai + react")


async def smoke_openrouter_wide_research(model_name: str) -> None:
    if not os.getenv("OPENROUTER_API_KEY"):
        raise RuntimeError("OPENROUTER_API_KEY is unset")
    with tempfile.TemporaryDirectory() as tmp:
        config_path = Path(tmp) / "openrouter_wide_smoke.yaml"
        _write_yaml(config_path, _openrouter_wide_research_config(model_name))
        await _run_smoke(config_path, "openrouter + function_call_wide_research")


async def main() -> None:
    load_dotenv(REPO_ROOT / ".env")
    parser = argparse.ArgumentParser(description="Phase 1 workflow smoke tests")
    parser.add_argument(
        "which",
        choices=["openai-react", "openrouter-wide", "all"],
        help="Which smoke test to run",
    )
    parser.add_argument("--openai-model", default=os.getenv("SMOKE_OPENAI_MODEL", "gpt-5.4-mini"))
    parser.add_argument(
        "--openrouter-model",
        default=os.getenv("SMOKE_OPENROUTER_MODEL", "GPTOSS20B_OR"),
    )
    args = parser.parse_args()

    os.chdir(REPO_ROOT)
    if args.which in ("openai-react", "all"):
        await smoke_openai_react(args.openai_model)
    if args.which in ("openrouter-wide", "all"):
        await smoke_openrouter_wide_research(args.openrouter_model)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as exc:
        print(f"SMOKE FAILED: {exc}", file=sys.stderr)
        raise
