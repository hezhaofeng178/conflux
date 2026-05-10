"""Graph models - 知识图谱结构。

定义图的节点、边、子网等结构，用于 Networker 层和 Storage 层。
"""

from __future__ import annotations

import uuid
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


class NodeType(str, Enum):
    """图节点类型。"""

    CONCEPT = "concept"  # 概念节点
    DOCUMENT = "document"  # 文档节点
    CHAPTER = "chapter"  # 章节节点
    CLAIM = "claim"  # 论断节点
    CONFLICT = "conflict"  # 冲突节点


class EdgeType(str, Enum):
    """图边类型。"""

    # 结构关系
    BELONGS_TO = "belongs_to"  # 概念 belongs_to 文档
    MENTIONED_IN = "mentioned_in"  # 概念 mentioned_in 章节

    # 语义关系（来自 RelationType）
    SEMANTIC = "semantic"  # 通用语义关系

    # 组网关系
    CROSS_LINK = "cross_link"  # 跨书连接
    SOFT_LINK = "soft_link"  # 主题相近的软连接
    SAME_AS = "same_as"  # 确认为同一概念

    # 冲突关系
    CONFLICTS_WITH = "conflicts_with"  # 冲突关系


class Node(BaseModel):
    """图节点。"""

    id: str = Field(default_factory=lambda: f"node_{uuid.uuid4().hex[:8]}")
    node_type: NodeType
    label: str  # 显示标签
    properties: dict[str, Any] = Field(default_factory=dict)

    # 来源追溯
    source_id: Optional[str] = None  # 对应的 Concept/Claim/Document ID
    source_book: Optional[str] = None
    subnet_id: Optional[str] = None  # 所属子网

    # 向量
    embedding: Optional[list[float]] = Field(default=None, exclude=True)


class Edge(BaseModel):
    """图边。"""

    id: str = Field(default_factory=lambda: f"edge_{uuid.uuid4().hex[:8]}")
    source_node_id: str
    target_node_id: str
    edge_type: EdgeType
    label: Optional[str] = None  # 边标签
    weight: float = 1.0  # 边权重
    confidence: float = 1.0  # 置信度
    properties: dict[str, Any] = Field(default_factory=dict)


class SubnetStats(BaseModel):
    """子网统计信息。"""

    node_count: int = 0
    edge_count: int = 0
    density: float = 0.0  # 内部连接密度
    avg_degree: float = 0.0


class CrossLink(BaseModel):
    """跨子网连接信息。"""

    target_subnet_id: str
    target_subnet_name: str
    bridge_concepts: list[str] = Field(default_factory=list)  # 桥接概念
    link_strength: float = 0.0


class Subnet(BaseModel):
    """子网 - 一组高度关联的知识节点。

    类似知识领域或主题模块，内部节点紧密连接，
    通过桥接概念与其他子网相连。
    """

    id: str = Field(default_factory=lambda: f"subnet_{uuid.uuid4().hex[:8]}")
    name: str  # 子网名称（如 "心血管系统"）
    description: Optional[str] = None
    domain: Optional[str] = None  # 所属领域

    # 内容
    core_node_ids: list[str] = Field(default_factory=list)  # 核心概念节点
    node_ids: list[str] = Field(default_factory=list)  # 所有节点
    source_books: list[str] = Field(default_factory=list)  # 贡献了节点的书籍

    # 跨网连接
    cross_links: list[CrossLink] = Field(default_factory=list)

    # 统计
    stats: SubnetStats = Field(default_factory=SubnetStats)


class KnowledgeGraph(BaseModel):
    """知识图谱 - 顶层容器。

    包含所有节点、边和子网的全局视图。
    """

    id: str = Field(default_factory=lambda: f"graph_{uuid.uuid4().hex[:8]}")
    name: str = "Conflux Knowledge Graph"
    nodes: dict[str, Node] = Field(default_factory=dict)  # node_id → Node
    edges: list[Edge] = Field(default_factory=list)
    subnets: dict[str, Subnet] = Field(default_factory=dict)  # subnet_id → Subnet

    @property
    def node_count(self) -> int:
        return len(self.nodes)

    @property
    def edge_count(self) -> int:
        return len(self.edges)

    @property
    def subnet_count(self) -> int:
        return len(self.subnets)

    def add_node(self, node: Node) -> None:
        """添加节点。"""
        self.nodes[node.id] = node

    def add_edge(self, edge: Edge) -> None:
        """添加边。"""
        self.edges.append(edge)

    def get_node(self, node_id: str) -> Optional[Node]:
        """获取节点。"""
        return self.nodes.get(node_id)

    def get_neighbors(self, node_id: str) -> list[str]:
        """获取邻居节点 ID 列表。"""
        neighbors: list[str] = []
        for edge in self.edges:
            if edge.source_node_id == node_id:
                neighbors.append(edge.target_node_id)
            elif edge.target_node_id == node_id:
                neighbors.append(edge.source_node_id)
        return neighbors

    def summary(self) -> str:
        """图谱摘要。"""
        return (
            f"🌐 {self.name}\n"
            f"   节点: {self.node_count}\n"
            f"   边: {self.edge_count}\n"
            f"   子网: {self.subnet_count}"
        )
