"""Node Merger - 概念节点合并逻辑。

当不同书籍中出现相同概念时，将多个来源版本合并为一个统一节点。
保留所有来源信息，综合别名、标签、定义。
"""

from __future__ import annotations

from typing import Optional

from conflux.models.concept import Concept


class MergeResult:
    """合并结果。"""

    def __init__(self, merged: Concept, sources: list[str]):
        self.merged = merged  # 合并后的概念
        self.sources = sources  # 参与合并的来源书籍列表
        self.merged_count = len(sources)  # 合并的来源数量


class NodeMerger:
    """节点合并器。

    当不同书籍中出现相同概念时，将它们合并为一个节点。
    合并策略：
    - 保留更完整的定义
    - 合并别名（去重）
    - 合并标签
    - 在 properties 中记录多来源信息
    """

    def merge(self, existing: Concept, new_concept: Concept) -> Concept:
        """将新概念合并到已有概念中。

        Args:
            existing: 已存在的概念节点。
            new_concept: 新提取的概念。

        Returns:
            合并后的概念。
        """
        # 合并别名（去重）
        for alias in new_concept.aliases:
            if alias not in existing.aliases and alias != existing.name:
                existing.aliases.append(alias)

        # 如果新概念的名称不在已有别名中，添加为别名
        if (
            new_concept.name != existing.name
            and new_concept.name not in existing.aliases
        ):
            existing.aliases.append(new_concept.name)

        # 合并标签
        for tag in new_concept.tags:
            if tag not in existing.tags:
                existing.tags.append(tag)

        # 如果新概念有更好的定义，更新
        if new_concept.definition and not existing.definition:
            existing.definition = new_concept.definition
        elif new_concept.definition and existing.definition:
            # 保留两者，在描述中注明多视角
            alt_view = f"\n\n[来自 {new_concept.source_book}] {new_concept.definition}"
            if existing.description:
                existing.description += alt_view
            else:
                existing.description = alt_view

        # 取较高的置信度
        existing.confidence = max(existing.confidence, new_concept.confidence)

        # 在 properties 中记录合并来源（使用 Node 的 properties 模式）
        # 这里通过 tags 来记录多来源
        source_tag = f"source:{new_concept.source_book}"
        if source_tag not in existing.tags:
            existing.tags.append(source_tag)

        return existing

    def should_merge(self, a: Concept, b: Concept) -> bool:
        """判断两个概念是否应该合并。

        简单规则判断（embedding 判断在 SimilarityEngine 中完成）。

        Args:
            a: 概念 A。
            b: 概念 B。

        Returns:
            是否应该合并。
        """
        # 名称完全相同
        if a.name.lower().strip() == b.name.lower().strip():
            return True

        # 名称出现在对方的别名中
        a_aliases_lower = [alias.lower() for alias in a.aliases]
        b_aliases_lower = [alias.lower() for alias in b.aliases]

        if a.name.lower() in b_aliases_lower:
            return True
        if b.name.lower() in a_aliases_lower:
            return True

        # 互相有共同别名
        if set(a_aliases_lower) & set(b_aliases_lower):
            return True

        return False

    def batch_merge(
        self,
        concepts: list[Concept],
    ) -> list[MergeResult]:
        """批量合并同一概念的多个实例。

        扫描所有概念，找出应该合并的组，执行合并。

        Args:
            concepts: 所有概念列表。

        Returns:
            合并结果列表。
        """
        # 按名称分组
        name_groups: dict[str, list[Concept]] = {}
        for concept in concepts:
            key = concept.name.lower().strip()
            name_groups.setdefault(key, []).append(concept)

        results: list[MergeResult] = []

        for _name, group in name_groups.items():
            if len(group) <= 1:
                continue

            # 以第一个为基础进行合并
            base = group[0]
            sources = [base.source_book] if base.source_book else []

            for other in group[1:]:
                base = self.merge(base, other)
                if other.source_book and other.source_book not in sources:
                    sources.append(other.source_book)

            results.append(MergeResult(merged=base, sources=sources))

        return results

    def get_merge_candidates(
        self,
        new_concepts: list[Concept],
        existing_concepts: list[Concept],
    ) -> list[tuple[Concept, Concept]]:
        """找出新概念中可以与已有概念合并的候选对。

        Args:
            new_concepts: 新提取的概念。
            existing_concepts: 已有的概念。

        Returns:
            (new_concept, existing_concept) 候选对列表。
        """
        candidates: list[tuple[Concept, Concept]] = []

        for new_c in new_concepts:
            for existing_c in existing_concepts:
                if self.should_merge(new_c, existing_c):
                    candidates.append((new_c, existing_c))
                    break  # 一个新概念只匹配一个已有概念

        return candidates
