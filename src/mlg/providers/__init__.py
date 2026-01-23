"""Model providers for different LLM backends."""

from mlg.providers.base import (
    FinishReason,
    Message,
    ModelProvider,
    StreamChunk,
    ToolCall,
    ToolDeclaration,
)
from mlg.providers.deepseek import DeepSeekProvider
from mlg.providers.openai_compat import OpenAICompatibleProvider
from mlg.providers.registry import ProviderRegistry, get_default_registry

__all__ = [
    "DeepSeekProvider",
    "FinishReason",
    "Message",
    "ModelProvider",
    "OpenAICompatibleProvider",
    "ProviderRegistry",
    "StreamChunk",
    "ToolCall",
    "ToolDeclaration",
    "get_default_registry",
]
