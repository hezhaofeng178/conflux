"""Subnet Manager - 知识子网管理。

管理知识子网的创建、合并和跨网连接。
子网代表高度关联的知识集群（如一个主题领域），
通过桥接概念与其他子网建立跨网连接。
"""

from __future__ import annotations

from typing import Optional

from conflux.models.concept import Concept
from conflux.models.graph import CrossLink, Subnet, SubnetStats


class SubnetManager:
    """知识子网管理器。

    管理知识子网的创建、合并和跨网连接。
    维护 concept → subnet 的映射关系。
    """

    def __init__(self):
        self.subnets: dict[str, Subnet] = {}
        self._node_to_subnet: dict[str, str] = {}  # concept_id → subnet_id

    def create_subnet(
        self,
        name: str,
        core_concepts: list[Concept],
        source: str,
        domain: Optional[str] = None,
    ) -> Subnet:
        """创建新的知识子网。

        Args:
            name: 子网名称（如 "心血管系统"）。
            core_concepts: 核心概念列表。
            source: 来源书籍名称。
            domain: 所属领域。

        Returns:
            创建的 Subnet 对象。
        """
        all_ids = [c.id for c in core_concepts]
        core_ids = [c.id for c in core_concepts[:5]]

        subnet = Subnet(
            name=name,
            domain=domain,
            node_ids=all_ids,
            core_node_ids=core_ids,
            source_books=[source],
            stats=SubnetStats(
                node_count=len(core_concepts),
            ),
        )

        self.subnets[subnet.id] = subnet
        for concept in core_concepts:
            self._node_to_subnet[concept.id] = subnet.id

        return subnet

    def find_subnet_for_concept(self, concept_id: str) -> Optional[Subnet]:
        """查找概念所属的子网。

        Args:
            concept_id: 概念 ID。

        Returns:
            所属的 Subnet，不存在则返回 None。
        """
        subnet_id = self._node_to_subnet.get(concept_id)
        if subnet_id:
            return self.subnets.get(subnet_id)
        return None

    def add_to_subnet(self, concept: Concept, subnet_id: str) -> None:
        """将概念添加到已有子网。

        Args:
            concept: 要添加的概念。
            subnet_id: 目标子网 ID。
        """
        subnet = self.subnets.get(subnet_id)
        if subnet and concept.id not in subnet.node_ids:
            subnet.node_ids.append(concept.id)
            subnet.stats.node_count = len(subnet.node_ids)
            self._node_to_subnet[concept.id] = subnet_id

            # 更新来源书籍列表
            if concept.source_book and concept.source_book not in subnet.source_books:
                subnet.source_books.append(concept.source_book)

    def remove_from_subnet(self, concept_id: str) -> None:
        """从子网中移除概念。

        Args:
            concept_id: 要移除的概念 ID。
        """
        subnet_id = self._node_to_subnet.get(concept_id)
        if subnet_id:
            subnet = self.subnets.get(subnet_id)
            if subnet and concept_id in subnet.node_ids:
                subnet.node_ids.remove(concept_id)
                subnet.stats.node_count = len(subnet.node_ids)
            del self._node_to_subnet[concept_id]

    def create_cross_link(
        self,
        subnet_a_id: str,
        subnet_b_id: str,
        bridge_concepts: list[str],
    ) -> None:
        """创建两个子网之间的跨网连接。

        在双方的 cross_links 中互相记录。

        Args:
            subnet_a_id: 子网 A 的 ID。
            subnet_b_id: 子网 B 的 ID。
            bridge_concepts: 桥接概念 ID 列表。
        """
        subnet_a = self.subnets.get(subnet_a_id)
        subnet_b = self.subnets.get(subnet_b_id)

        if not subnet_a or not subnet_b:
            return

        strength = min(len(bridge_concepts) / 5.0, 1.0)

        # 在 A 中记录到 B 的连接
        cross_link_a = CrossLink(
            target_subnet_id=subnet_b_id,
            target_subnet_name=subnet_b.name,
            bridge_concepts=bridge_concepts,
            link_strength=strength,
        )
        subnet_a.cross_links.append(cross_link_a)

        # 在 B 中记录到 A 的连接
        cross_link_b = CrossLink(
            target_subnet_id=subnet_a_id,
            target_subnet_name=subnet_a.name,
            bridge_concepts=bridge_concepts,
            link_strength=strength,
        )
        subnet_b.cross_links.append(cross_link_b)

    def merge_subnets(self, subnet_a_id: str, subnet_b_id: str) -> Optional[Subnet]:
        """合并两个子网为一个。

        将 subnet_b 的所有节点合并到 subnet_a 中，删除 subnet_b。

        Args:
            subnet_a_id: 保留的子网 ID。
            subnet_b_id: 被合并的子网 ID。

        Returns:
            合并后的子网，失败返回 None。
        """
        subnet_a = self.subnets.get(subnet_a_id)
        subnet_b = self.subnets.get(subnet_b_id)

        if not subnet_a or not subnet_b:
            return None

        # 迁移节点
        for node_id in subnet_b.node_ids:
            if node_id not in subnet_a.node_ids:
                subnet_a.node_ids.append(node_id)
            self._node_to_subnet[node_id] = subnet_a_id

        # 合并核心节点
        for core_id in subnet_b.core_node_ids:
            if core_id not in subnet_a.core_node_ids:
                subnet_a.core_node_ids.append(core_id)

        # 合并来源书籍
        for book in subnet_b.source_books:
            if book not in subnet_a.source_books:
                subnet_a.source_books.append(book)

        # 更新统计
        subnet_a.stats.node_count = len(subnet_a.node_ids)

        # 删除被合并的子网
        del self.subnets[subnet_b_id]

        return subnet_a

    def get_all_subnets(self) -> list[Subnet]:
        """获取所有子网。"""
        return list(self.subnets.values())

    def get_subnet(self, subnet_id: str) -> Optional[Subnet]:
        """获取指定子网。"""
        return self.subnets.get(subnet_id)

    def get_isolated_concepts(self, all_concept_ids: list[str]) -> list[str]:
        """找出尚未归入任何子网的孤立概念。

        Args:
            all_concept_ids: 所有概念 ID 列表。

        Returns:
            未归入子网的概念 ID 列表。
        """
        return [cid for cid in all_concept_ids if cid not in self._node_to_subnet]

    def get_cross_linked_subnets(self, subnet_id: str) -> list[tuple[str, float]]:
        """获取与指定子网有跨网连接的所有子网。

        Args:
            subnet_id: 目标子网 ID。

        Returns:
            (子网 ID, 连接强度) 列表。
        """
        subnet = self.subnets.get(subnet_id)
        if not subnet:
            return []

        return [
            (link.target_subnet_id, link.link_strength)
            for link in subnet.cross_links
        ]

    def get_stats(self) -> dict:
        """获取子网管理器的统计信息。"""
        total_nodes = sum(len(s.node_ids) for s in self.subnets.values())
        total_cross_links = sum(len(s.cross_links) for s in self.subnets.values()) // 2

        return {
            "subnet_count": len(self.subnets),
            "total_nodes": total_nodes,
            "isolated_count": 0,  # 需要传入 all_concept_ids 才能计算
            "cross_links": total_cross_links,
        }
