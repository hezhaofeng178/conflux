"""Conflict Pairer - 将冲突论断配对生成冲突节点。

扫描所有论断，按主题分组，跨书两两比较，
使用 StanceDetector 判断是否矛盾，最终生成 Conflict 对象。
"""

from __future__ import annotations

from typing import Optional

from conflux.models.conflict import (
    Claim,
    Conflict,
    ConflictAnalysis,
    ConflictSeverity,
    ConflictSide,
    ConflictType,
)
from conflux.conflict.stance_detector import StanceDetector
from conflux.llm.client import LLMClient


class ConflictPairer:
    """冲突配对器。

    将检测到的冲突论断配对，生成结构化的冲突节点。

    算法：
    1. 按主题对论断分组
    2. 同主题内，只比较不同书籍的论断
    3. 使用 StanceDetector 判断是否真正冲突
    4. 为每对冲突创建 Conflict 对象
    """

    def __init__(
        self,
        stance_detector: Optional[StanceDetector] = None,
        llm_client: Optional[LLMClient] = None,
        min_confidence: float = 0.6,
    ):
        """初始化冲突配对器。

        Args:
            stance_detector: 立场检测器。
            llm_client: LLM 客户端。
            min_confidence: 冲突最低置信度（低于此值不生成冲突节点）。
        """
        self.stance_detector = stance_detector or StanceDetector(llm_client)
        self.llm = llm_client or LLMClient()
        self.min_confidence = min_confidence

    async def find_conflicts(self, claims: list[Claim]) -> list[Conflict]:
        """在所有论断中查找冲突对。

        Args:
            claims: 所有论断列表（来自多本书）。

        Returns:
            检测到的冲突列表。
        """
        conflicts: list[Conflict] = []

        # 按主题分组
        topic_groups = self._group_by_topic(claims)

        for topic, group_claims in topic_groups.items():
            # 只比较来自不同书的论断
            books = set(c.source_book for c in group_claims)
            if len(books) < 2:
                continue

            # 两两比较不同书的论断
            for i, claim_a in enumerate(group_claims):
                for claim_b in group_claims[i + 1:]:
                    if claim_a.source_book == claim_b.source_book:
                        continue

                    is_conflict, confidence = await self.stance_detector.are_conflicting(
                        claim_a, claim_b
                    )

                    if is_conflict and confidence >= self.min_confidence:
                        conflict = self._create_conflict(
                            claim_a, claim_b, topic, confidence
                        )
                        conflicts.append(conflict)

        return conflicts

    async def find_conflicts_for_new_claims(
        self,
        new_claims: list[Claim],
        existing_claims: list[Claim],
    ) -> list[Conflict]:
        """在新论断与已有论断之间查找冲突（增量模式）。

        比完整扫描更高效，只比较新旧之间。

        Args:
            new_claims: 新提取的论断（来自新书）。
            existing_claims: 已有的论断。

        Returns:
            新发现的冲突列表。
        """
        conflicts: list[Conflict] = []

        for new_claim in new_claims:
            for existing_claim in existing_claims:
                # 跳过同一书的论断
                if new_claim.source_book == existing_claim.source_book:
                    continue

                is_conflict, confidence = await self.stance_detector.are_conflicting(
                    new_claim, existing_claim
                )

                if is_conflict and confidence >= self.min_confidence:
                    topic = new_claim.subject or "未知主题"
                    conflict = self._create_conflict(
                        new_claim, existing_claim, topic, confidence
                    )
                    conflicts.append(conflict)

        return conflicts

    def _group_by_topic(self, claims: list[Claim]) -> dict[str, list[Claim]]:
        """按主题对论断分组。"""
        groups: dict[str, list[Claim]] = {}

        for claim in claims:
            topic = (claim.subject or "unknown").lower().strip()
            groups.setdefault(topic, []).append(claim)

        return groups

    def _create_conflict(
        self,
        claim_a: Claim,
        claim_b: Claim,
        topic: str,
        confidence: float,
    ) -> Conflict:
        """创建冲突节点。"""
        # 确定冲突类型
        conflict_type = self._infer_conflict_type(claim_a, claim_b)

        # 构建冲突双方
        sides = [
            ConflictSide(
                claim_id=claim_a.id,
                source_book=claim_a.source_book,
                position=claim_a.statement,
                context=claim_a.context,
            ),
            ConflictSide(
                claim_id=claim_b.id,
                source_book=claim_b.source_book,
                position=claim_b.statement,
                context=claim_b.context,
            ),
        ]

        # 标题
        title = f"关于「{topic}」的观点分歧"

        # 基础分析
        analysis = ConflictAnalysis(
            possible_reasons=[
                f"{claim_a.source_book} 与 {claim_b.source_book} 对「{topic}」有不同看法"
            ],
        )

        conflict = Conflict(
            title=title,
            conflict_type=conflict_type,
            sides=sides,
            analysis=analysis,
            subject=topic,
            detection_confidence=confidence,
            related_concepts=[topic],
        )

        return conflict

    def _infer_conflict_type(self, a: Claim, b: Claim) -> ConflictType:
        """推断冲突类型。"""
        type_a = a.claim_type if isinstance(a.claim_type, str) else a.claim_type
        type_b = b.claim_type if isinstance(b.claim_type, str) else b.claim_type

        if "methodological" in (type_a, type_b):
            return ConflictType.METHODOLOGICAL
        if "interpretive" in (type_a, type_b):
            return ConflictType.INTERPRETIVE
        return ConflictType.FACTUAL
