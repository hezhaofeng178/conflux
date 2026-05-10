"""GraphStore - 基于 NetworkX 的图存储。

管理知识图谱的持久化，支持查询和遍历。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Optional

import networkx as nx

from conflux.models.graph import (
    CrossLink,
    Edge,
    EdgeType,
    KnowledgeGraph,
    Node,
    NodeType,
    Subnet,
)


class GraphStore:
    """图存储 - 管理知识图谱的持久化与查询。
    
    基于 NetworkX 实现，支持：
    - 图的序列化/反序列化（JSON）
    - 节点/边的 CRUD
    - 子图查询
    - 路径搜索
    - 子网管理
    """

    def __init__(self, persist_path: Optional[Path] = None) -> None:
        """初始化图存储。
        
        Args:
            persist_path: 图数据文件路径。None 则使用默认路径。
        """
        self._persist_path = persist_path or Path("data/graph.json")
        self._graph = nx.DiGraph()
        self._knowledge_graph: Optional[KnowledgeGraph] = None

        # 尝试加载已有数据
        if self._persist_path.exists():
            self._load()

    @property
    def graph(self) -> nx.DiGraph:
        """底层 NetworkX 图。"""
        return self._graph

    @property
    def knowledge_graph(self) -> KnowledgeGraph:
        """获取 KnowledgeGraph 模型对象。"""
        if self._knowledge_graph is None:
            self._knowledge_graph = KnowledgeGraph()
        return self._knowledge_graph

    @property
    def node_count(self) -> int:
        """节点数量。"""
        return self._graph.number_of_nodes()

    @property
    def edge_count(self) -> int:
        """边数量。"""
        return self._graph.number_of_edges()

    # ─── Node CRUD ────────────────────────────────────────────────

    def add_node(self, node: Node) -> None:
        """添加节点到图。"""
        self._graph.add_node(
            node.id,
            label=node.label,
            node_type=node.node_type.value,
            properties=node.properties,
            source_id=node.source_id,
        )
        self.knowledge_graph.add_node(node)

    def get_node(self, node_id: str) -> Optional[Node]:
        """获取节点。"""
        if node_id not in self._graph:
            return None

        data = self._graph.nodes[node_id]
        return Node(
            id=node_id,
            label=data.get("label", ""),
            node_type=NodeType(data.get("node_type", "concept")),
            properties=data.get("properties", {}),
            source_id=data.get("source_id"),
        )

    def remove_node(self, node_id: str) -> bool:
        """删除节点及其关联的边。"""
        if node_id in self._graph:
            self._graph.remove_node(node_id)
            return True
        return False

    def has_node(self, node_id: str) -> bool:
        """检查节点是否存在。"""
        return node_id in self._graph

    # ─── Edge CRUD ────────────────────────────────────────────────

    def add_edge(self, edge: Edge) -> None:
        """添加边到图。"""
        self._graph.add_edge(
            edge.source_node_id,
            edge.target_node_id,
            edge_type=edge.edge_type.value,
            weight=edge.weight,
            confidence=edge.confidence,
            properties=edge.properties,
        )
        self.knowledge_graph.add_edge(edge)

    def get_edge(self, source_id: str, target_id: str) -> Optional[Edge]:
        """获取边。"""
        if not self._graph.has_edge(source_id, target_id):
            return None

        data = self._graph.edges[source_id, target_id]
        return Edge(
            source_node_id=source_id,
            target_node_id=target_id,
            edge_type=EdgeType(data.get("edge_type", "semantic")),
            weight=data.get("weight", 1.0),
            confidence=data.get("confidence", 1.0),
            properties=data.get("properties", {}),
        )

    def remove_edge(self, source_id: str, target_id: str) -> bool:
        """删除边。"""
        if self._graph.has_edge(source_id, target_id):
            self._graph.remove_edge(source_id, target_id)
            return True
        return False

    def has_edge(self, source_id: str, target_id: str) -> bool:
        """检查边是否存在。"""
        return self._graph.has_edge(source_id, target_id)

    # ─── Query ────────────────────────────────────────────────────

    def get_neighbors(
        self,
        node_id: str,
        direction: str = "both",
        edge_type: Optional[EdgeType] = None,
    ) -> list[str]:
        """获取节点的邻居。
        
        Args:
            node_id: 节点 ID。
            direction: 方向 - "out"(出边), "in"(入边), "both"(双向)。
            edge_type: 可选的边类型过滤。
            
        Returns:
            邻居节点 ID 列表。
        """
        if node_id not in self._graph:
            return []

        neighbors: set[str] = set()

        if direction in ("out", "both"):
            for _, target, data in self._graph.out_edges(node_id, data=True):
                if edge_type is None or data.get("edge_type") == edge_type.value:
                    neighbors.add(target)

        if direction in ("in", "both"):
            for source, _, data in self._graph.in_edges(node_id, data=True):
                if edge_type is None or data.get("edge_type") == edge_type.value:
                    neighbors.add(source)

        return list(neighbors)

    def get_subgraph(self, node_ids: list[str]) -> nx.DiGraph:
        """获取指定节点集的子图。"""
        return self._graph.subgraph(node_ids).copy()

    def find_shortest_path(
        self,
        source_id: str,
        target_id: str,
    ) -> Optional[list[str]]:
        """查找两个节点间的最短路径。"""
        try:
            path = nx.shortest_path(
                self._graph, source=source_id, target=target_id
            )
            return path
        except (nx.NodeNotFound, nx.NetworkXNoPath):
            return None

    def get_connected_components(self) -> list[set[str]]:
        """获取所有连通分量（忽略边方向）。"""
        undirected = self._graph.to_undirected()
        return [
            component
            for component in nx.connected_components(undirected)
        ]

    def get_nodes_by_type(self, node_type: NodeType) -> list[Node]:
        """按类型获取所有节点。"""
        nodes: list[Node] = []
        for node_id, data in self._graph.nodes(data=True):
            if data.get("node_type") == node_type.value:
                nodes.append(
                    Node(
                        id=node_id,
                        label=data.get("label", ""),
                        node_type=node_type,
                        properties=data.get("properties", {}),
                        source_id=data.get("source_id"),
                    )
                )
        return nodes

    def get_node_degree(self, node_id: str) -> dict[str, int]:
        """获取节点的度数信息。"""
        if node_id not in self._graph:
            return {"in_degree": 0, "out_degree": 0, "total": 0}
        in_deg = self._graph.in_degree(node_id)
        out_deg = self._graph.out_degree(node_id)
        return {
            "in_degree": in_deg,
            "out_degree": out_deg,
            "total": in_deg + out_deg,
        }

    # ─── Subnet 管理 ──────────────────────────────────────────────

    def add_subnet(self, subnet: Subnet) -> None:
        """添加子网记录。"""
        self.knowledge_graph.subnets[subnet.id] = subnet

    def get_subnet(self, subnet_id: str) -> Optional[Subnet]:
        """获取子网。"""
        return self.knowledge_graph.subnets.get(subnet_id)

    def detect_communities(self, min_size: int = 3) -> list[set[str]]:
        """使用社区检测算法发现子网。
        
        基于 Louvain 算法（如果可用），否则使用连通分量。
        
        Args:
            min_size: 社区最小节点数。
            
        Returns:
            社区（节点 ID 集合）列表。
        """
        undirected = self._graph.to_undirected()

        if undirected.number_of_nodes() == 0:
            return []

        try:
            # 尝试使用 Louvain 社区检测
            communities = nx.community.louvain_communities(undirected)
            return [c for c in communities if len(c) >= min_size]
        except (AttributeError, Exception):
            # 回退到连通分量
            components = list(nx.connected_components(undirected))
            return [c for c in components if len(c) >= min_size]

    # ─── Persistence ──────────────────────────────────────────────

    def save(self) -> Path:
        """持久化图数据到 JSON 文件。"""
        self._persist_path.parent.mkdir(parents=True, exist_ok=True)

        data = {
            "nodes": [],
            "edges": [],
            "subnets": {},
        }

        # 序列化节点
        for node_id, node_data in self._graph.nodes(data=True):
            data["nodes"].append({
                "id": node_id,
                "label": node_data.get("label", ""),
                "node_type": node_data.get("node_type", "concept"),
                "properties": node_data.get("properties", {}),
                "source_id": node_data.get("source_id"),
            })

        # 序列化边
        for source, target, edge_data in self._graph.edges(data=True):
            data["edges"].append({
                "source_node_id": source,
                "target_node_id": target,
                "edge_type": edge_data.get("edge_type", "related_to"),
                "weight": edge_data.get("weight", 1.0),
                "confidence": edge_data.get("confidence", 1.0),
                "properties": edge_data.get("properties", {}),
            })

        # 序列化子网
        for subnet_id, subnet in self.knowledge_graph.subnets.items():
            data["subnets"][subnet_id] = subnet.model_dump(mode="json")

        self._persist_path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return self._persist_path

    def _load(self) -> None:
        """从 JSON 文件加载图数据。"""
        if not self._persist_path.exists():
            return

        try:
            data = json.loads(self._persist_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, Exception):
            return

        self._graph = nx.DiGraph()
        self._knowledge_graph = KnowledgeGraph()

        # 加载节点
        for node_data in data.get("nodes", []):
            node = Node(
                id=node_data["id"],
                label=node_data.get("label", ""),
                node_type=NodeType(node_data.get("node_type", "concept")),
                properties=node_data.get("properties", {}),
                source_id=node_data.get("source_id"),
            )
            self.add_node(node)

        # 加载边
        for edge_data in data.get("edges", []):
            edge = Edge(
                source_node_id=edge_data["source_node_id"],
                target_node_id=edge_data["target_node_id"],
                edge_type=EdgeType(edge_data.get("edge_type", "semantic")),
                weight=edge_data.get("weight", 1.0),
                confidence=edge_data.get("confidence", 1.0),
                properties=edge_data.get("properties", {}),
            )
            self.add_edge(edge)

        # 加载子网
        for subnet_id, subnet_data in data.get("subnets", {}).items():
            subnet = Subnet.model_validate(subnet_data)
            self.knowledge_graph.subnets[subnet_id] = subnet

    def clear(self) -> None:
        """清空图数据。"""
        self._graph.clear()
        self._knowledge_graph = KnowledgeGraph()
        if self._persist_path.exists():
            self._persist_path.unlink()

    def get_stats(self) -> dict:
        """获取图统计信息。"""
        components = self.get_connected_components()
        return {
            "nodes": self.node_count,
            "edges": self.edge_count,
            "connected_components": len(components),
            "subnets": len(self.knowledge_graph.subnets),
            "density": nx.density(self._graph) if self.node_count > 0 else 0,
        }

    def export_to_graphml(self, output_path: Path) -> Path:
        """导出为 GraphML 格式（可被 Gephi 等工具打开）。"""
        output_path.parent.mkdir(parents=True, exist_ok=True)
        nx.write_graphml(self._graph, str(output_path))
        return output_path
