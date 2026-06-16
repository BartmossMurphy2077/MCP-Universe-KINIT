"""
OpenAI provider backed by Pydantic AI.

Configure via environment variables:
    - OPENAI_API_KEY
    - OPENAI_BASE_URL (optional, defaults to https://api.openai.com/v1)

In YAML configs, set type: openai and model_name to your OpenAI model.
"""
from typing import Dict, Optional, Union

from openai import AsyncOpenAI
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.openai import OpenAIProvider

from mcpuniverse.common.context import Context
from mcpuniverse.llm.openai import OpenAIConfig
from .base import PydanticAIBaseLLM


class PydanticAIOpenAIModel(PydanticAIBaseLLM):
    """OpenAI language model via Pydantic AI's OpenAI-compatible provider."""

    config_class = OpenAIConfig
    alias = "openai"
    env_vars = ["OPENAI_API_KEY"]

    def __init__(self, config: Optional[Union[Dict, str]] = None):
        super().__init__()
        self.config = PydanticAIOpenAIModel.config_class.load(config)

    def build_pydantic_ai_model(self) -> OpenAIChatModel:
        client = AsyncOpenAI(
            api_key=self.config.api_key,
            base_url=self.config.base_url,
        )
        return OpenAIChatModel(
            self.config.model_name,
            provider=OpenAIProvider(openai_client=client),
        )

    def set_context(self, context: Context):
        super().set_context(context)
        self.config.api_key = context.env.get("OPENAI_API_KEY", self.config.api_key)
        self.config.base_url = context.env.get("OPENAI_BASE_URL", self.config.base_url)
