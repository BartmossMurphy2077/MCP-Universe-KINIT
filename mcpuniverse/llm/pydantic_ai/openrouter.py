"""
OpenRouter provider backed by Pydantic AI.

Configure via environment variables:
    - OPENROUTER_API_KEY

In YAML configs, set type: openrouter and model_name to an OpenRouter alias
(e.g. GPT5_1_OR) or a raw OpenRouter model id.
"""
from typing import Dict, Optional, Union

from openai import AsyncOpenAI
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.openai import OpenAIProvider

from mcpuniverse.common.context import Context
from mcpuniverse.llm.openrouter import OpenRouterConfig, model_name_map
from .base import PydanticAIBaseLLM

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"


def _resolve_openrouter_model_name(config_name: str) -> str:
    return model_name_map.get(config_name, config_name)


class PydanticAIOpenRouterModel(PydanticAIBaseLLM):
    """OpenRouter language model via Pydantic AI's OpenAI-compatible provider."""

    config_class = OpenRouterConfig
    alias = "openrouter"
    env_vars = ["OPENROUTER_API_KEY"]

    def __init__(self, config: Optional[Union[Dict, str]] = None):
        super().__init__()
        self.config = PydanticAIOpenRouterModel.config_class.load(config)

    def build_pydantic_ai_model(self) -> OpenAIChatModel:
        client = AsyncOpenAI(
            api_key=self.config.api_key,
            base_url=OPENROUTER_BASE_URL,
        )
        return OpenAIChatModel(
            _resolve_openrouter_model_name(self.config.model_name),
            provider=OpenAIProvider(openai_client=client),
        )

    def set_context(self, context: Context):
        super().set_context(context)
        self.config.api_key = context.env.get("OPENROUTER_API_KEY", self.config.api_key)
