"""Cross Linker - 跨书/跨子网连接建立。

核心组网算法：将新书的概念自动整合到已有知识网络中，
通过相似度匹配建立跨书连接。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from conflux.models.concept import Concept, Relation, RelationType
from conflux.models.graph import Edge, EdgeType
from conflux.networker.similarity import SimilarityEngine
from conflux.networker.subnet import SubnetManager
from conflux.networker.merger import NodeMerger


@dataclass
class IntegrationResult:
    """概念集成的结果。"""

    new_concepts: list[Concept] = field(default_factory=list)
    merged_concepts: list[tuple[Concept, Concept]] = field(default_factory=list)  # (new, existing)
    cross_links: list[Relation] = field(default_factory=list)
    new_subnets: list[str] = field(default_factory=list)
    edges_created: list[Edge] = field(default_factory=list)

    @property
    def summary(self) -> dict:
        """集成结果摘要。"""
        return {
            "new_concepts": len(self.new_concepts),
            "merged_concepts": len(self.merged_concepts),
            "cross_links": len(self.cross_links),
            "new_subnets": len(self.new_subnets),
            "edges_created": len(self.edges_created),
        }


class CrossLinker:
    """跨书连接器。

    在引入新书时，自动建立与已有知识网络的连接。
    核心算法：
    1. 对新概念逐一与已有概念做相似度匹配
    2. 若为同一概念 → 合并节点
    3. 若为相关概念 → 建立跨网连接 (CROSS_LINK)
    4. 若完全无关 → 创建新子网
    """

    def __init__(
        self,
        similarity_engine: Optional[SimilarityEngine] = None,
        subnet_manager: Optional[SubnetManager] = None,
        node_merger: Optional[NodeMerger] = None,
        similarity_threshold: float = 0.85,
        same_threshold: float = 0.92,
    ):
        """初始化跨书连接器。

        Args:
            similarity_engine: 相似度引擎。
            subnet_manager: 子网管理器。
            node_merger: 节点合并器。
            similarity_threshold: 相关性阈值。
            same_threshold: 同一概念阈值。
        """
        self.similarity = similarity_engine or SimilarityEngine(
            threshold=similarity_threshold
        )
        self.subnets = subnet_manager or SubnetManager()
        self.merger = node_merger or NodeMerger()
        self.same_threshold = same_threshold

    async def integrate_new_concepts(
        self,
        new_concepts: list[Concept],
        existing_concepts: list[Concept],
        source_book: str,
    ) -> IntegrationResult:
        """将新概念集成到已有知识网络。

        三阶段处理：
        1. 快速名称匹配（无需 LLM）
        2. 语义相似度匹配（需要 embedding）
        3. 分配子网

        Args:
            new_concepts: 新书提取的概念。
            existing_concepts: 已有的概念集合。
            source_book: 新书名称。

        Returns:
            集成结果。
        """
        result = IntegrationResult()

        # Phase 1: 快速名称匹配
        remaining_new: list[Concept] = []
        for new_concept in new_concepts:
            merged_by_name = False
            for existing in existing_concepts:
                if self.merger.should_merge(new_concept, existing):
                    # 名称直接匹配 → 合并
                    self.merger.merge(existing, new_concept)
                    result.merged_concepts.append((new_concept, existing))
                    merged_by_name = True
                    break

            if not merged_by_name:
                remaining_new.append(new_concept)

        # Phase 2: 语义相似度匹配（对剩余概念）
        truly_new: list[Concept] = []
        for new_concept in remaining_new:
            matches = await self.similarity.find_similar(
                new_concept, existing_concepts, top_k=5
            )

            if not matches:
                # 完全无关
                truly_new.append(new_concept)
                continue

            best_match, best_score = matches[0]

            if self.similarity.is_same_concept(new_concept, best_match):
                # 同一概念 → 合并
                self.merger.merge(best_match, new_concept)
                result.merged_concepts.append((new_concept, best_match))
            else:
                # 相关但不同 → 建立跨网连接
                cross_link = Relation(
                    source_id=new_concept.id,
                    target_id=best_match.id,
                    relation_type=RelationType.RELATED_TO,
                    description=f"跨书语义关联 ({source_book})",
                    weight=best_score,
                    confidence=best_score,
                    source_book=source_book,
                    inferred_by="networker",
                )
                result.cross_links.append(cross_link)

                # 创建图的边
                edge = Edge(
                    source_node_id=new_concept.id,
                    target_node_id=best_match.id,
                    edge_type=EdgeType.CROSS_LINK,
                    weight=best_score,
                    confidence=best_score,
                    properties={"source_book": source_book},
                )
                result.edges_created.append(edge)

                truly_new.append(new_concept)

        # Phase 3: 为新概念创建/分配子网
        result.new_concepts = truly_new

        if truly_new:
            subnet = self.subnets.create_subnet(
                name=f"{source_book} 概念组",
                core_concepts=truly_new[:10],
                source=source_book,
            )
            result.new_subnets.append(subnet.id)

            # 剩余概念也加入该子网
            for concept in truly_new[10:]:
                self.subnets.add_to_subnet(concept, subnet.id)

        return result

    def build_cross_links_from_relations(
        self,
        relations: list[Relation],
    ) -> list[Edge]:
        """将概念层的关系转换为图层的边。

        用于从已有的 Relation 列表生成 Graph Edge。

        Args:
            relations: 概念间的关系列表。

        Returns:
            生成的图边列表。
        """
        edges: list[Edge] = []

        for rel in relations:
            # 将 RelationType 映射到 EdgeType
            edge_type = self._map_relation_to_edge_type(rel.relation_type)

            edge = Edge(
                source_node_id=rel.source_id,
                target_node_id=rel.target_id,
                edge_type=edge_type,
                weight=rel.weight,
                confidence=rel.confidence,
                label=rel.description,
                properties={
                    "relation_type": rel.relation_type.value,
                    "source_book": rel.source_book or "",
                },
            )
            edges.append(edge)

        return edges

    @staticmethod
    def _map_relation_to_edge_type(relation_type: RelationType) -> EdgeType:
        """将概念层的关系类型映射到图层的边类型。"""
        mapping = {
            RelationType.SIMILAR_TO: EdgeType.SOFT_LINK,
            RelationType.RELATED_TO: EdgeType.CROSS_LINK,
            RelationType.CONTRASTS: EdgeType.CONFLICTS_WITH,
        }
        return mapping.get(relation_type, EdgeType.SEMANTIC)
