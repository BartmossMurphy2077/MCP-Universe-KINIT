"""
Azure OpenAI provider backed by Pydantic AI.

Configure via environment variables:
    - AZURE_API_KEY
    - AZURE_API_BASE (Azure resource endpoint URL)
    - AZURE_API_VERSION (optional, defaults to 2024-12-01-preview)

In YAML configs, set type: azure and model_name to your Azure deployment name.
"""
from typing import Dict, Optional, Union

from openai import AsyncAzureOpenAI
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.openai import OpenAIProvider

from mcpuniverse.common.context import Context
from mcpuniverse.llm.azure import (
    AzureOpenAIConfig,
    DEFAULT_AZURE_API_VERSION,
    _normalize_azure_endpoint,
)
from .base import PydanticAIBaseLLM


class PydanticAIAzureModel(PydanticAIBaseLLM):
    """
    Azure OpenAI language model via Pydantic AI's OpenAI-compatible provider.
    """
    config_class = AzureOpenAIConfig
    alias = "azure"
    env_vars = ["AZURE_API_KEY", "AZURE_API_BASE"]

    def __init__(self, config: Optional[Union[Dict, str]] = None):
        super().__init__()
        self.config = PydanticAIAzureModel.config_class.load(config)
        self.config.azure_endpoint = _normalize_azure_endpoint(self.config.azure_endpoint)

    def build_pydantic_ai_model(self) -> OpenAIChatModel:
        client = AsyncAzureOpenAI(
            api_version=self.config.api_version,
            azure_endpoint=self.config.azure_endpoint,
            api_key=self.config.api_key,
        )
        return OpenAIChatModel(
            self.config.model_name,
            provider=OpenAIProvider(openai_client=client),
        )

    def set_context(self, context: Context):
        """Refresh Azure credentials and endpoint from runtime environment."""
        super().set_context(context)
        self.config.api_key = context.env.get("AZURE_API_KEY", self.config.api_key)
        endpoint = context.env.get("AZURE_API_BASE", self.config.azure_endpoint)
        self.config.azure_endpoint = _normalize_azure_endpoint(endpoint)
        self.config.api_version = context.env.get(
            "AZURE_API_VERSION",
            self.config.api_version or DEFAULT_AZURE_API_VERSION,
        )
