"""Normalize Pydantic AI agent outputs to match legacy agent contracts."""
import json


def normalize_agent_output(output: str) -> str:
    """Unwrap legacy thought/answer JSON wrappers so evaluators receive task JSON."""
    response_text = output.strip().strip('`').strip()
    if response_text.startswith("json"):
        response_text = response_text[4:].strip()
    try:
        parsed = json.loads(response_text)
    except json.JSONDecodeError:
        return output
    if isinstance(parsed, dict) and "answer" in parsed:
        answer = parsed["answer"]
        if isinstance(answer, str):
            return answer
        return json.dumps(answer)
    return output
