"""
Base class for LLM providers backed by Pydantic AI models.
"""
from abc import abstractmethod
from typing import List

from pydantic_ai.models import Model

from mcpuniverse.llm.base import BaseLLM


class PydanticAIBaseLLM(BaseLLM):
    """
    BaseLLM adapter that exposes a Pydantic AI model for agent runtimes.

    Subclasses implement ``build_pydantic_ai_model()``; the legacy ``generate()``
  path is not used by Pydantic AI agents.
    """

    @abstractmethod
    def build_pydantic_ai_model(self) -> Model:
        """Build the Pydantic AI model used by Pydantic AI agents."""

    def _generate(self, messages: List[dict[str, str]], **kwargs):
        raise NotImplementedError(
            f"{self.__class__.__name__} is used via Pydantic AI agents; "
            "call build_pydantic_ai_model() instead of generate()."
        )
