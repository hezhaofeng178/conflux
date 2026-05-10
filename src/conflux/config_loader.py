"""Config Loader - 加载并解析 conflux.config.yaml。

将 YAML 配置映射为运行时配置对象（LLMConfig、PipelineConfig 等）。
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

import structlog
import yaml

from conflux.llm.client import LLMConfig

logger = structlog.get_logger(__name__)

# 默认配置文件名
CONFIG_FILENAME = "conflux.config.yaml"


def find_config(start_path: Optional[Path] = None) -> Optional[Path]:
    """向上查找 conflux.config.yaml 文件。

    Args:
        start_path: 起始搜索路径，默认当前目录。

    Returns:
        配置文件路径，未找到返回 None。
    """
    current = (start_path or Path.cwd()).resolve()
    for parent in [current, *current.parents]:
        config_path = parent / CONFIG_FILENAME
        if config_path.exists():
            return config_path
    return None


def load_config(config_path: Optional[Path] = None) -> dict[str, Any]:
    """加载并解析 YAML 配置文件。

    Args:
        config_path: 配置文件路径。None 则自动查找。

    Returns:
        解析后的配置字典。

    Raises:
        FileNotFoundError: 配置文件不存在。
    """
    if config_path is None:
        config_path = find_config()

    if config_path is None or not config_path.exists():
        logger.warning("config_not_found", hint="运行 conflux init 创建配置文件")
        return {}

    with open(config_path, encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}

    logger.debug("config_loaded", path=str(config_path))
    return data


def build_llm_config(raw_config: Optional[dict[str, Any]] = None) -> LLMConfig:
    """从原始配置字典构建 LLMConfig。

    会读取 engine.llm 和 engine.embedding 两个部分。

    Args:
        raw_config: load_config() 返回的字典。None 则自动加载。

    Returns:
        LLMConfig 实例。
    """
    if raw_config is None:
        raw_config = load_config()

    engine = raw_config.get("engine", {})
    llm_section = engine.get("llm", {})
    embed_section = engine.get("embedding", {})

    # --- LLM 部分 ---
    provider = llm_section.get("provider", "openai")
    model = llm_section.get("model", "gpt-4o-mini")

    # 自动修正模型名（为 LiteLLM 路由添加前缀）
    if provider == "deepseek" and not model.startswith("deepseek/"):
        model = f"deepseek/{model}"

    api_key_env = llm_section.get("api_key_env")
    api_base = llm_section.get("api_base")

    # 从环境变量读取 key
    import os
    api_key = None
    if api_key_env:
        api_key = os.environ.get(api_key_env)

    # --- Embedding 部分 ---
    embed_provider = embed_section.get("provider", "api")
    embed_model_name = embed_section.get("model", "BAAI/bge-small-zh-v1.5")

    # --- 可选参数 ---
    timeout = llm_section.get("timeout", 300)
    temperature = llm_section.get("temperature", 0.1)
    max_tokens = llm_section.get("max_tokens", 4096)
    max_retries = llm_section.get("max_retries", 3)

    config = LLMConfig(
        provider=provider,
        model=model,
        api_key=api_key,
        api_base=api_base,
        timeout=timeout,
        temperature=temperature,
        max_tokens=max_tokens,
        max_retries=max_retries,
        embed_provider=embed_provider,
        embed_model_name=embed_model_name,
    )

    logger.info(
        "llm_config_built",
        provider=provider,
        model=model,
        embed_provider=embed_provider,
        embed_model=embed_model_name,
    )

    return config
