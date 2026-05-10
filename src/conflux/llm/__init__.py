"""LLM abstraction layer - 大模型统一调用接口。"""

from conflux.llm.client import LLMClient, get_llm_client

__all__ = ["LLMClient", "get_llm_client"]
