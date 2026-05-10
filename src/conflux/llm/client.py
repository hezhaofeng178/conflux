"""LLM Client - 统一的大模型调用客户端。

基于 LiteLLM 封装，支持 OpenAI / Anthropic / 本地模型的统一调用。
内置重试、限流、JSON 校验、dry-run 模式。
"""

from __future__ import annotations

import json
import os
from typing import Any, Optional

import structlog
from pydantic import BaseModel
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from conflux import LLMError

logger = structlog.get_logger(__name__)


class LLMConfig(BaseModel):
    """LLM 配置。"""

    provider: str = "openai"  # openai | anthropic | local | deepseek
    model: str = "gpt-4o-mini"
    api_key: Optional[str] = None
    api_base: Optional[str] = None
    temperature: float = 0.1  # 低温度确保稳定输出
    max_tokens: int = 4096
    timeout: int = 300  # 超时秒数（DeepSeek V4 Pro 等大模型建议 ≥180）
    max_retries: int = 3
    dry_run: bool = False  # dry-run 模式不实际调用 LLM
    embed_provider: str = "api"  # "api" | "local" - embedding 使用的方式
    embed_model_name: str = "BAAI/bge-small-zh-v1.5"  # 本地 embedding 模型名


class LLMResponse(BaseModel):
    """LLM 调用响应。"""

    content: str  # 原始文本响应
    parsed: Optional[dict | list] = None  # 解析后的 JSON（如果响应是 JSON）
    model: str = ""
    usage: dict = {}  # token 用量统计
    is_mock: bool = False  # 是否为 mock 响应


class LLMClient:
    """统一的 LLM 调用客户端。

    Features:
    - 多 provider 支持（通过 LiteLLM）
    - 自动重试（指数退避）
    - JSON 输出强制校验
    - dry-run 模式（用于测试）
    - 结构化日志
    """

    def __init__(self, config: Optional[LLMConfig] = None):
        self.config = config or LLMConfig()
        self._resolve_api_key()

    def _resolve_api_key(self) -> None:
        """从环境变量解析 API Key。"""
        if self.config.api_key:
            return

        # 按优先级查找环境变量
        env_keys = [
            "CONFLUX_LLM_KEY",
            "OPENAI_API_KEY",
            "ANTHROPIC_API_KEY",
            "DEEPSEEK_API_KEY",
        ]
        for key in env_keys:
            val = os.environ.get(key)
            if val:
                self.config.api_key = val
                logger.debug("resolved_api_key", source=key)
                return

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=2, min=5, max=60),
        retry=retry_if_exception_type((Exception,)),
        reraise=True,
    )
    async def complete(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        response_format: Optional[str] = None,  # "json" | None
    ) -> LLMResponse:
        """调用 LLM 获取补全结果。

        Args:
            prompt: 用户 prompt
            system_prompt: 系统 prompt（可选）
            temperature: 覆盖默认温度
            max_tokens: 覆盖默认 max_tokens
            response_format: 期望的响应格式

        Returns:
            LLMResponse

        Raises:
            LLMError: 调用失败
        """
        if self.config.dry_run:
            return self._mock_response(prompt, response_format)

        try:
            import litellm

            messages: list[dict[str, str]] = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            messages.append({"role": "user", "content": prompt})

            kwargs: dict[str, Any] = {
                "model": self.config.model,
                "messages": messages,
                "temperature": temperature or self.config.temperature,
                "max_tokens": max_tokens or self.config.max_tokens,
                "timeout": self.config.timeout,
            }

            if self.config.api_key:
                kwargs["api_key"] = self.config.api_key
            if self.config.api_base:
                kwargs["api_base"] = self.config.api_base

            # JSON 模式
            if response_format == "json":
                kwargs["response_format"] = {"type": "json_object"}

            response = await litellm.acompletion(**kwargs)

            content = response.choices[0].message.content or ""
            usage = dict(response.usage) if response.usage else {}

            # 尝试解析 JSON
            parsed = None
            if response_format == "json" or self._looks_like_json(content):
                parsed = self._try_parse_json(content)

            logger.info(
                "llm_call_success",
                model=self.config.model,
                prompt_len=len(prompt),
                response_len=len(content),
                usage=usage,
            )

            return LLMResponse(
                content=content,
                parsed=parsed,
                model=self.config.model,
                usage=usage,
            )

        except ImportError:
            raise LLMError("需要安装 litellm: pip install litellm")
        except Exception as e:
            logger.error("llm_call_failed", error=str(e), model=self.config.model)
            raise LLMError(f"LLM 调用失败: {e}")

    async def complete_json(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: Optional[float] = None,
    ) -> dict | list:
        """调用 LLM 并确保返回有效 JSON。

        Returns:
            解析后的 JSON 对象

        Raises:
            LLMError: 调用失败或 JSON 解析失败
        """
        response = await self.complete(
            prompt=prompt,
            system_prompt=system_prompt,
            temperature=temperature,
            response_format="json",
        )

        if response.parsed is not None:
            return response.parsed

        # 尝试从 markdown 代码块中提取 JSON
        extracted = self._extract_json_from_text(response.content)
        if extracted is not None:
            return extracted

        raise LLMError(
            f"LLM 返回的内容不是有效 JSON:\n{response.content[:500]}"
        )

    def _mock_response(self, prompt: str, response_format: Optional[str]) -> LLMResponse:
        """Dry-run 模式的 mock 响应。"""
        if response_format == "json":
            mock_content = json.dumps({"mock": True, "note": "dry-run mode"})
            return LLMResponse(
                content=mock_content,
                parsed={"mock": True, "note": "dry-run mode"},
                model=f"{self.config.model} (dry-run)",
                is_mock=True,
            )
        return LLMResponse(
            content="[DRY-RUN] This is a mock response.",
            model=f"{self.config.model} (dry-run)",
            is_mock=True,
        )

    def _looks_like_json(self, text: str) -> bool:
        """快速判断文本是否看起来像 JSON。"""
        stripped = text.strip()
        return (stripped.startswith("{") and stripped.endswith("}")) or (
            stripped.startswith("[") and stripped.endswith("]")
        )

    def _try_parse_json(self, text: str) -> Optional[dict | list]:
        """尝试解析 JSON，失败返回 None。"""
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            # 尝试从 markdown 代码块提取
            return self._extract_json_from_text(text)

    def _extract_json_from_text(self, text: str) -> Optional[dict | list]:
        """从可能包含 markdown 代码块的文本中提取 JSON。"""
        import re

        # 匹配 ```json ... ``` 代码块
        pattern = r"```(?:json)?\s*\n?(.*?)\n?```"
        matches = re.findall(pattern, text, re.DOTALL)
        for match in matches:
            try:
                return json.loads(match.strip())
            except json.JSONDecodeError:
                continue

        # 尝试直接解析整体
        try:
            return json.loads(text.strip())
        except json.JSONDecodeError:
            return None


    async def chat(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: Optional[float] = None,
        response_format: Optional[str] = None,
    ) -> str:
        """便捷的聊天接口 - 返回纯文本响应。

        Args:
            system_prompt: 系统 prompt
            user_prompt: 用户 prompt
            temperature: 覆盖默认温度
            response_format: 期望的响应格式 ("json" | None)

        Returns:
            LLM 响应的纯文本内容
        """
        response = await self.complete(
            prompt=user_prompt,
            system_prompt=system_prompt,
            temperature=temperature,
            response_format=response_format,
        )
        return response.content

    async def embed(self, text: str) -> list[float]:
        """计算文本的嵌入向量。

        支持两种模式：
        - local: 使用本地 sentence-transformers 模型（离线、免费）
        - api: 调用远程 embedding API（需要 key 和网络）

        注意：即使 dry_run=True，如果 embed_provider="local" 也会使用真实本地模型。

        Args:
            text: 输入文本

        Returns:
            嵌入向量 (list[float])

        Raises:
            LLMError: 调用失败
        """
        # 本地 embedding 模式（优先级最高，无论 dry_run）
        if self.config.embed_provider == "local":
            return self._embed_local(text)

        if self.config.dry_run:
            # dry-run 模式返回固定维度的随机向量
            import random
            return [random.uniform(-1, 1) for _ in range(384)]

        # API 模式
        try:
            import litellm

            embed_model = "text-embedding-3-small"
            kwargs: dict[str, Any] = {
                "model": embed_model,
                "input": [text],
            }
            if self.config.api_key:
                kwargs["api_key"] = self.config.api_key
            if self.config.api_base:
                kwargs["api_base"] = self.config.api_base

            response = await litellm.aembedding(**kwargs)
            embedding = response.data[0]["embedding"]

            logger.debug(
                "embed_success",
                model=embed_model,
                text_len=len(text),
                dim=len(embedding),
            )
            return embedding

        except ImportError:
            raise LLMError("需要安装 litellm: pip install litellm")
        except Exception as e:
            logger.error("embed_failed", error=str(e))
            raise LLMError(f"Embedding 调用失败: {e}")

    _local_embed_model_instance = None  # 类级别的模型缓存
    _local_embed_model_name = None

    def _embed_local(self, text: str) -> list[float]:
        """使用本地 sentence-transformers 模型计算 embedding。

        首次调用会下载模型（~90MB），之后完全离线运行。
        推荐中文模型: BAAI/bge-small-zh-v1.5（维度 512，效果好且轻量）
        """
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError:
            raise LLMError(
                "本地 embedding 需要安装 sentence-transformers:\n"
                "  pip install sentence-transformers"
            )

        model_name = self.config.embed_model_name

        # 懒加载模型（类级别单例，多实例共享；模型名变则重新加载）
        if (LLMClient._local_embed_model_instance is None
                or LLMClient._local_embed_model_name != model_name):
            logger.info("loading_local_embed_model", model=model_name)
            LLMClient._local_embed_model_instance = SentenceTransformer(model_name)
            LLMClient._local_embed_model_name = model_name
            logger.info(
                "local_embed_model_loaded",
                model=model_name,
                dim=LLMClient._local_embed_model_instance.get_embedding_dimension(),
            )

        model = LLMClient._local_embed_model_instance
        embedding = model.encode(text, normalize_embeddings=True)
        return embedding.tolist()


# 全局客户端单例
_default_client: Optional[LLMClient] = None


def get_llm_client(config: Optional[LLMConfig] = None) -> LLMClient:
    """获取全局 LLM 客户端（单例）。"""
    global _default_client
    if _default_client is None or config is not None:
        _default_client = LLMClient(config)
    return _default_client
