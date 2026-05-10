"""Similarity Engine - 嵌入向量相似度计算。

提供概念间的语义相似度计算能力，支持：
- 基于 embedding 向量的余弦相似度
- 基于名称/别名的文本相似度
- 综合判断是否为同一概念
"""

from __future__ import annotations

from typing import Optional

import numpy as np

from conflux.models.concept import Concept
from conflux.llm.client import LLMClient


class SimilarityEngine:
    """相似度计算引擎。

    使用 embedding 向量计算概念间的语义相似度。
    支持两种工作模式：
    - 在线模式：调用 LLM embed 接口计算 embedding
    - 离线模式：使用已有的 embedding 进行比较
    """

    def __init__(
        self,
        llm_client: Optional[LLMClient] = None,
        threshold: float = 0.85,
        same_threshold: float = 0.92,
    ):
        """初始化相似度引擎。

        Args:
            llm_client: LLM 客户端（用于计算 embedding）。
            threshold: 相似度阈值（低于此值不认为相关）。
            same_threshold: 同一概念判断阈值。
        """
        self.llm = llm_client or LLMClient()
        self.threshold = threshold
        self.same_threshold = same_threshold

    async def compute_embedding(self, text: str) -> list[float]:
        """计算文本的嵌入向量。

        Args:
            text: 输入文本。

        Returns:
            嵌入向量。
        """
        return await self.llm.embed(text)

    async def ensure_embedding(self, concept: Concept) -> None:
        """确保概念有嵌入向量，如果没有则计算。"""
        if not concept.embedding:
            text = self._concept_to_text(concept)
            concept.embedding = await self.compute_embedding(text)

    async def find_similar(
        self,
        concept: Concept,
        candidates: list[Concept],
        top_k: int = 5,
    ) -> list[tuple[Concept, float]]:
        """在候选概念中查找与目标概念最相似的。

        Args:
            concept: 目标概念。
            candidates: 候选概念列表。
            top_k: 返回前 k 个最相似的。

        Returns:
            (概念, 相似度) 元组列表，按相似度降序排列。
        """
        if not candidates:
            return []

        # 确保目标概念有 embedding
        await self.ensure_embedding(concept)

        # 计算所有候选的 embedding（跳过已有的）
        for c in candidates:
            await self.ensure_embedding(c)

        # 计算余弦相似度
        results: list[tuple[Concept, float]] = []
        query_vec = np.array(concept.embedding)

        for candidate in candidates:
            if candidate.id == concept.id:
                continue
            if not candidate.embedding:
                continue

            cand_vec = np.array(candidate.embedding)
            similarity = self._cosine_similarity(query_vec, cand_vec)
            if similarity >= self.threshold:
                results.append((candidate, float(similarity)))

        # 排序并返回 top_k
        results.sort(key=lambda x: x[1], reverse=True)
        return results[:top_k]

    def find_similar_sync(
        self,
        concept: Concept,
        candidates: list[Concept],
        top_k: int = 5,
    ) -> list[tuple[Concept, float]]:
        """同步版本 - 仅使用已有的 embedding 计算（不调用 LLM）。

        适用于所有概念已有 embedding 的场景。
        """
        if not candidates or not concept.embedding:
            return []

        results: list[tuple[Concept, float]] = []
        query_vec = np.array(concept.embedding)

        for candidate in candidates:
            if candidate.id == concept.id:
                continue
            if not candidate.embedding:
                continue

            cand_vec = np.array(candidate.embedding)
            similarity = self._cosine_similarity(query_vec, cand_vec)
            if similarity >= self.threshold:
                results.append((candidate, float(similarity)))

        results.sort(key=lambda x: x[1], reverse=True)
        return results[:top_k]

    def is_same_concept(
        self,
        a: Concept,
        b: Concept,
        threshold: Optional[float] = None,
    ) -> bool:
        """判断两个概念是否是同一个概念的不同表述。

        综合使用 embedding 相似度和名称匹配。

        Args:
            a: 概念 A。
            b: 概念 B。
            threshold: 自定义阈值（覆盖默认 same_threshold）。

        Returns:
            是否为同一概念。
        """
        _threshold = threshold or self.same_threshold

        # 策略1：名称完全匹配
        name_sim = self._name_similarity(a, b)
        if name_sim >= 0.9:
            return True

        # 策略2：embedding 相似度
        if a.embedding and b.embedding:
            similarity = self._cosine_similarity(
                np.array(a.embedding), np.array(b.embedding)
            )
            return similarity >= _threshold

        # 无法计算 embedding 时退化为名称匹配
        return name_sim > 0.8

    def compute_similarity(self, a: Concept, b: Concept) -> float:
        """计算两个概念之间的综合相似度得分。

        结合 embedding 相似度和名称相似度。

        Returns:
            综合相似度 (0.0 - 1.0)。
        """
        name_sim = self._name_similarity(a, b)

        if a.embedding and b.embedding:
            embed_sim = self._cosine_similarity(
                np.array(a.embedding), np.array(b.embedding)
            )
            # 加权平均：embedding 占 70%，名称占 30%
            return embed_sim * 0.7 + name_sim * 0.3

        # 只有名称相似度
        return name_sim

    def _concept_to_text(self, concept: Concept) -> str:
        """将概念转换为用于 embedding 的文本表示。"""
        parts = [concept.name]
        if concept.definition:
            parts.append(concept.definition)
        if concept.description:
            parts.append(concept.description[:200])
        if concept.aliases:
            parts.append(f"别名: {', '.join(concept.aliases)}")
        if concept.domain:
            parts.append(f"领域: {concept.domain}")
        return " | ".join(parts)

    @staticmethod
    def _cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
        """计算两个向量的余弦相似度。"""
        dot = np.dot(a, b)
        norm_a = np.linalg.norm(a)
        norm_b = np.linalg.norm(b)
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return float(dot / (norm_a * norm_b))

    @staticmethod
    def _name_similarity(a: Concept, b: Concept) -> float:
        """基于名称和别名计算简单相似度。"""
        names_a = {a.name.lower()} | {alias.lower() for alias in a.aliases}
        names_b = {b.name.lower()} | {alias.lower() for alias in b.aliases}

        # 如果有任何名称完全匹配
        if names_a & names_b:
            return 1.0

        # 否则检查是否有包含关系
        for na in names_a:
            for nb in names_b:
                if na in nb or nb in na:
                    return 0.7

        return 0.0
