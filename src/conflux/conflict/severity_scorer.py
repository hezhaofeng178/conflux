"""Severity Scorer - 冲突严重程度评分。

多维度评估冲突的严重程度，帮助用户优先处理重要冲突。

评分维度：
- 来源数量：越多方参与，越严重 (30%)
- 概念重要性：涉及核心概念则更严重 (40%)
- 冲突类型：事实矛盾 > 方法论分歧 > 解释性差异 (30%)
"""

from __future__ import annotations

from conflux.models.conflict import Conflict, ConflictSeverity, ConflictType


class SeverityScorer:
    """冲突严重程度评分器。

    评估冲突的严重程度，帮助用户优先处理重要冲突。
    使用多维度加权评分模型。
    """

    # 冲突类型的权重映射
    TYPE_WEIGHTS: dict[str, float] = {
        ConflictType.FACTUAL.value: 0.9,  # 事实矛盾最严重
        ConflictType.METHODOLOGICAL.value: 0.7,  # 方法论分歧
        ConflictType.TEMPORAL.value: 0.6,  # 时效性冲突
        ConflictType.INTERPRETIVE.value: 0.5,  # 解释性差异
        ConflictType.SCOPE.value: 0.4,  # 适用范围冲突
    }

    def __init__(
        self,
        source_weight: float = 0.3,
        importance_weight: float = 0.4,
        type_weight: float = 0.3,
    ):
        """初始化评分器。

        Args:
            source_weight: 来源数量维度的权重。
            importance_weight: 概念重要性维度的权重。
            type_weight: 冲突类型维度的权重。
        """
        self.source_weight = source_weight
        self.importance_weight = importance_weight
        self.type_weight = type_weight

    def score(
        self,
        conflict: Conflict,
        concept_importance: float = 0.5,
    ) -> ConflictSeverity:
        """评估冲突的严重程度。

        Args:
            conflict: 冲突节点。
            concept_importance: 相关概念的重要性 (0-1)。

        Returns:
            严重程度等级。
        """
        total_score = self.compute_score(conflict, concept_importance)
        return self._score_to_severity(total_score)

    def compute_score(
        self,
        conflict: Conflict,
        concept_importance: float = 0.5,
    ) -> float:
        """计算冲突的数值分数 (0-1)。

        Args:
            conflict: 冲突节点。
            concept_importance: 相关概念的重要性。

        Returns:
            数值分数。
        """
        score = 0.0

        # 维度1：来源数量（越多方参与，越严重）
        sides_score = min(len(conflict.sides) / 3.0, 1.0)
        score += sides_score * self.source_weight

        # 维度2：概念重要性
        score += concept_importance * self.importance_weight

        # 维度3：冲突类型权重
        type_score = self.TYPE_WEIGHTS.get(conflict.conflict_type.value, 0.5)
        score += type_score * self.type_weight

        return min(score, 1.0)

    def batch_score(
        self,
        conflicts: list[Conflict],
        concept_importance_map: Optional[dict[str, float]] = None,
    ) -> list[tuple[Conflict, ConflictSeverity, float]]:
        """批量评分并按严重程度排序。

        Args:
            conflicts: 冲突列表。
            concept_importance_map: 概念重要性映射（concept_name → importance）。

        Returns:
            (冲突, 严重程度, 分数) 列表，按分数降序。
        """
        concept_importance_map = concept_importance_map or {}

        results: list[tuple[Conflict, ConflictSeverity, float]] = []
        for conflict in conflicts:
            # 查找相关概念的最高重要性
            importance = 0.5
            if conflict.subject and concept_importance_map:
                importance = concept_importance_map.get(
                    conflict.subject, 0.5
                )

            numerical_score = self.compute_score(conflict, importance)
            severity = self._score_to_severity(numerical_score)

            # 更新冲突对象的 severity 字段
            conflict.severity = severity

            results.append((conflict, severity, numerical_score))

        # 按分数降序排列
        results.sort(key=lambda x: x[2], reverse=True)
        return results

    @staticmethod
    def _score_to_severity(score: float) -> ConflictSeverity:
        """将数值分数映射到严重程度等级。"""
        if score >= 0.8:
            return ConflictSeverity.CRITICAL
        elif score >= 0.6:
            return ConflictSeverity.HIGH
        elif score >= 0.4:
            return ConflictSeverity.MEDIUM
        else:
            return ConflictSeverity.LOW


# 兼容性: 允许 Severity 作为别名
from typing import Optional  # noqa: E402
