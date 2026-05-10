"""Pipeline - 知识处理编排流水线。

统一编排从文档加载到最终输出的完整流程：
1. load_documents()     - 加载已导入的 IR 文档
2. compile_document()   - 概念提取 + Skill 生成
3. run_networking()     - 跨书动态组网
4. detect_conflicts()   - 冲突检测
5. generate_output()    - 生成 Skill YAML + Vault MD
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import structlog

from conflux.compiler import ConceptExtractor, GraphBuilder, SkillGenerator
from conflux.llm import LLMClient, get_llm_client
from conflux.models.concept import Concept, Relation
from conflux.models.conflict import Conflict
from conflux.models.document import Document
from conflux.models.graph import Edge, EdgeType, Node, NodeType
from conflux.models.skill import Skill
from conflux.orchestrator.events import EventBus, EventType
from conflux.storage.file_store import FileStore
from conflux.storage.graph_store import GraphStore

logger = structlog.get_logger(__name__)


@dataclass
class PipelineConfig:
    """Pipeline 配置。"""

    # 构建模式
    full_rebuild: bool = False  # 全量重建（忽略增量缓存）
    skip_conflicts: bool = False  # 跳过冲突检测
    skip_networking: bool = False  # 跳过动态组网

    # 路径
    base_path: Optional[Path] = None  # 项目根目录

    # LLM
    llm_config: Optional[dict] = None  # LLM 配置覆盖

    # 阈值
    similarity_threshold: float = 0.85  # 组网相似度阈值
    conflict_sensitivity: str = "medium"  # 冲突检测灵敏度

    # 并发
    max_concurrent: int = 3  # 最大并发 LLM 调用数


@dataclass
class PipelineState:
    """Pipeline 运行状态。"""

    documents: list[Document] = field(default_factory=list)
    concepts: list[Concept] = field(default_factory=list)
    relations: list[Relation] = field(default_factory=list)
    skills: list[Skill] = field(default_factory=list)
    conflicts: list[Conflict] = field(default_factory=list)

    # 统计
    compiled_docs: int = 0
    total_concepts: int = 0
    total_skills: int = 0
    total_conflicts: int = 0
    cross_links: int = 0


class Pipeline:
    """知识处理编排流水线。
    
    整合所有模块（Parser → Compiler → Storage → Output），
    提供完整的知识处理流程编排。
    
    Usage:
        config = PipelineConfig(skip_conflicts=True)
        pipeline = Pipeline(config=config)
        
        # 逐步执行
        docs = pipeline.load_documents()
        for doc in docs:
            pipeline.compile_document(doc)
        pipeline.run_networking()
        stats = pipeline.generate_output()
        
        # 或一键执行
        stats = await pipeline.run_all()
    """

    def __init__(self, config: Optional[PipelineConfig] = None) -> None:
        """初始化 Pipeline。
        
        Args:
            config: Pipeline 配置，None 使用默认配置。
        """
        self.config = config or PipelineConfig()
        self.state = PipelineState()
        self.event_bus = EventBus()

        # 基础路径
        base_path = self.config.base_path or Path.cwd()

        # 初始化依赖模块
        self._file_store = FileStore(base_path=base_path)
        self._graph_store = GraphStore(
            persist_path=base_path / "data" / "graph.json"
        )
        self._llm_client: Optional[LLMClient] = None

        # 编译器组件（延迟初始化）
        self._concept_extractor: Optional[ConceptExtractor] = None
        self._skill_generator: Optional[SkillGenerator] = None
        self._graph_builder: Optional[GraphBuilder] = None

    @property
    def llm_client(self) -> LLMClient:
        """获取 LLM 客户端（延迟初始化）。"""
        if self._llm_client is None:
            self._llm_client = get_llm_client()
        return self._llm_client

    @property
    def concept_extractor(self) -> ConceptExtractor:
        """概念提取器（延迟初始化）。"""
        if self._concept_extractor is None:
            self._concept_extractor = ConceptExtractor(llm_client=self.llm_client)
        return self._concept_extractor

    @property
    def skill_generator(self) -> SkillGenerator:
        """Skill 生成器（延迟初始化）。"""
        if self._skill_generator is None:
            self._skill_generator = SkillGenerator(llm_client=self.llm_client)
        return self._skill_generator

    @property
    def graph_builder(self) -> GraphBuilder:
        """图构建器（延迟初始化）。"""
        if self._graph_builder is None:
            self._graph_builder = GraphBuilder()
        return self._graph_builder

    # ─── Step 1: Load Documents ───────────────────────────────────

    def load_documents(self) -> list[Document]:
        """加载所有已导入的 IR 文档。
        
        Returns:
            Document 列表。
        """
        self.event_bus.emit_sync(
            EventType.PIPELINE_STARTED,
            {"message": "开始加载文档"},
            source="pipeline",
        )

        documents = self._file_store.load_all_documents()
        self.state.documents = documents

        self.event_bus.emit_sync(
            EventType.DOCUMENT_LOADED,
            {"message": f"加载了 {len(documents)} 个文档", "count": len(documents)},
            source="pipeline",
        )

        logger.info("documents_loaded", count=len(documents))
        return documents

    # ─── Step 2: Compile Document ─────────────────────────────────

    def compile_document(self, document: Document) -> None:
        """编译单个文档：概念提取 → Skill 生成 → 图节点构建。
        
        Args:
            document: 要编译的文档。
        """
        self.event_bus.emit_sync(
            EventType.COMPILATION_STARTED,
            {"message": f"开始编译: {document.meta.title}", "doc_id": document.id},
            source="pipeline",
        )

        # 使用 asyncio.run 在同步上下文执行异步编译
        result = asyncio.run(self._compile_document_async(document))

        self.state.compiled_docs += 1
        logger.info(
            "document_compiled",
            title=document.meta.title,
            concepts=len(result["concepts"]),
            skills=len(result["skills"]),
        )

    async def _compile_document_async(self, document: Document) -> dict:
        """异步编译文档。"""
        # Step 2a: 概念提取
        extraction_result = await self.concept_extractor.extract_from_document(document)
        concepts = extraction_result.concepts
        relations = extraction_result.relations

        self.state.concepts.extend(concepts)
        self.state.relations.extend(relations)
        self.state.total_concepts += len(concepts)

        # 持久化概念
        self._file_store.save_concepts(concepts, document.id)
        self._file_store.save_relations(relations)

        await self.event_bus.emit(
            EventType.CONCEPT_EXTRACTED,
            {
                "message": f"提取了 {len(concepts)} 个概念",
                "doc_id": document.id,
                "concept_count": len(concepts),
                "relation_count": len(relations),
            },
            source="concept_extractor",
        )

        # Step 2b: Skill 生成
        skills = await self.skill_generator.generate_skills(
            concepts=concepts,
            document=document,
        )
        self.state.skills.extend(skills)
        self.state.total_skills += len(skills)

        # 持久化 Skills
        self._file_store.save_skills(skills, document.meta.title)

        await self.event_bus.emit(
            EventType.SKILL_GENERATED,
            {
                "message": f"生成了 {len(skills)} 个 Skill",
                "doc_id": document.id,
                "skill_count": len(skills),
            },
            source="skill_generator",
        )

        # Step 2c: 构建图节点
        for concept in concepts:
            node = Node(
                id=concept.id,
                label=concept.name,
                node_type=NodeType.CONCEPT,
                properties={
                    "definition": concept.definition or "",
                    "source_book": concept.source_book or "",
                    "concept_type": concept.concept_type.value,
                },
                source_id=document.id,
            )
            self._graph_store.add_node(node)

        for relation in relations:
            if self._graph_store.has_node(relation.source_id) and self._graph_store.has_node(relation.target_id):
                edge = Edge(
                    source_node_id=relation.source_id,
                    target_node_id=relation.target_id,
                    edge_type=EdgeType.SEMANTIC,
                    weight=relation.weight,
                    confidence=relation.confidence,
                    properties={"relation_type": relation.relation_type.value},
                )
                self._graph_store.add_edge(edge)

        await self.event_bus.emit(
            EventType.COMPILATION_COMPLETED,
            {"message": f"编译完成: {document.meta.title}", "doc_id": document.id},
            source="pipeline",
        )

        return {"concepts": concepts, "relations": relations, "skills": skills}

    # ─── Step 3: Networking ───────────────────────────────────────

    def run_networking(self) -> None:
        """跨书动态组网 - 发现不同书籍间概念的关联。
        
        基于语义相似度匹配跨书概念，建立 cross-link。
        注意：完整的语义组网在 M8（Networker）中实现，
        这里提供基于图拓扑的基础组网能力。
        """
        if self.config.skip_networking:
            return

        self.event_bus.emit_sync(
            EventType.NETWORKING_STARTED,
            {"message": "开始动态组网"},
            source="pipeline",
        )

        # 基于图拓扑的简单组网：检测社区
        communities = self._graph_store.detect_communities(min_size=2)

        cross_link_count = 0
        for community in communities:
            # 在同一社区中寻找跨书连接
            nodes_in_community = []
            for node_id in community:
                node = self._graph_store.get_node(node_id)
                if node:
                    nodes_in_community.append(node)

            # 找出不同来源的节点对
            source_groups: dict[str, list[Node]] = {}
            for node in nodes_in_community:
                source = node.source_id or "unknown"
                if source not in source_groups:
                    source_groups[source] = []
                source_groups[source].append(node)

            # 如果社区跨越多个来源，建立连接
            sources = list(source_groups.keys())
            if len(sources) > 1:
                for i in range(len(sources)):
                    for j in range(i + 1, len(sources)):
                        for node_a in source_groups[sources[i]][:5]:  # 限制数量
                            for node_b in source_groups[sources[j]][:5]:
                                if not self._graph_store.has_edge(node_a.id, node_b.id):
                                    edge = Edge(
                                        source_node_id=node_a.id,
                                        target_node_id=node_b.id,
                                        edge_type=EdgeType.CROSS_LINK,
                                        weight=0.7,
                                        confidence=0.6,
                                        properties={"link_type": "community_based"},
                                    )
                                    self._graph_store.add_edge(edge)
                                    cross_link_count += 1

        self.state.cross_links = cross_link_count

        self.event_bus.emit_sync(
            EventType.NETWORKING_COMPLETED,
            {
                "message": f"组网完成，建立 {cross_link_count} 条跨书连接",
                "cross_links": cross_link_count,
                "communities": len(communities),
            },
            source="pipeline",
        )

        logger.info(
            "networking_completed",
            cross_links=cross_link_count,
            communities=len(communities),
        )

    # ─── Step 4: Conflict Detection ──────────────────────────────

    def detect_conflicts(self) -> list[Conflict]:
        """运行冲突检测。
        
        注意：完整的冲突检测在 M9（Conflict）中实现，
        这里提供 Pipeline 层的调用入口。
        
        Returns:
            检测到的冲突列表。
        """
        if self.config.skip_conflicts:
            return []

        self.event_bus.emit_sync(
            EventType.CONFLICT_DETECTION_STARTED,
            {"message": "开始冲突检测"},
            source="pipeline",
        )

        # 冲突检测的实际逻辑将在 M9 模块中实现
        # 这里先提供一个占位框架
        conflicts = asyncio.run(self._detect_conflicts_async())

        self.state.conflicts = conflicts
        self.state.total_conflicts = len(conflicts)

        # 持久化冲突
        self._file_store.save_conflicts(conflicts)

        self.event_bus.emit_sync(
            EventType.CONFLICT_DETECTION_COMPLETED,
            {
                "message": f"检测完成，发现 {len(conflicts)} 个冲突",
                "conflict_count": len(conflicts),
            },
            source="pipeline",
        )

        logger.info("conflict_detection_completed", conflicts=len(conflicts))
        return conflicts

    async def _detect_conflicts_async(self) -> list[Conflict]:
        """异步冲突检测（M9 实现前的占位）。
        
        目前返回空列表。完整实现将在 M9（Conflict 模块）中。
        """
        # TODO: M9 实现后，调用 ConflictDetector
        return []

    # ─── Step 5: Generate Output ──────────────────────────────────

    def generate_output(self) -> dict:
        """生成最终输出文件（Skill YAML + Vault MD）。
        
        Returns:
            统计信息字典。
        """
        self.event_bus.emit_sync(
            EventType.OUTPUT_STARTED,
            {"message": "开始生成输出"},
            source="pipeline",
        )

        # 生成 Vault 节点
        vault_count = 0
        for concept in self.state.concepts:
            vault_content = self._build_vault_node_content(concept)
            self._file_store.save_vault_node(
                filename=concept.name,
                content=vault_content,
                subdir=concept.source_book,
            )
            vault_count += 1

        # 保存图数据
        self._graph_store.save()

        stats = {
            "skills": self.state.total_skills,
            "vault_nodes": vault_count,
            "cross_links": self.state.cross_links,
            "conflicts": self.state.total_conflicts,
            "concepts": self.state.total_concepts,
            "graph_nodes": self._graph_store.node_count,
            "graph_edges": self._graph_store.edge_count,
        }

        self.event_bus.emit_sync(
            EventType.OUTPUT_COMPLETED,
            {"message": "输出生成完成", **stats},
            source="pipeline",
        )

        self.event_bus.emit_sync(
            EventType.PIPELINE_COMPLETED,
            {"message": "Pipeline 全部完成", **stats},
            source="pipeline",
        )

        logger.info("output_generated", **stats)
        return stats

    # ─── One-shot 执行 ────────────────────────────────────────────

    async def run_all(self) -> dict:
        """一键执行完整 Pipeline。
        
        Returns:
            统计信息字典。
        """
        # Step 1
        documents = self.load_documents()
        if not documents:
            return {"error": "no_documents"}

        # Step 2
        for doc in documents:
            await self._compile_document_async(doc)
            self.state.compiled_docs += 1

        # Step 3
        self.run_networking()

        # Step 4
        if not self.config.skip_conflicts:
            await self._detect_conflicts_async()

        # Step 5
        return self.generate_output()

    # ─── Helpers ──────────────────────────────────────────────────

    def _build_vault_node_content(self, concept: Concept) -> str:
        """构建 Obsidian Vault 节点的 Markdown 内容。"""
        lines: list[str] = []

        # Frontmatter
        lines.append("---")
        lines.append(f"concept_id: {concept.id}")
        lines.append(f"type: {concept.concept_type.value}")
        if concept.source_book:
            lines.append(f"source: {concept.source_book}")
        if concept.aliases:
            lines.append(f"aliases: [{', '.join(concept.aliases)}]")
        lines.append("---")
        lines.append("")

        # Title
        lines.append(f"# {concept.name}")
        lines.append("")

        # Definition
        if concept.definition:
            lines.append("## 定义")
            lines.append("")
            lines.append(concept.definition)
            lines.append("")

        # Source
        if concept.source_book:
            lines.append("## 来源")
            lines.append("")
            lines.append(f"- 📖 {concept.source_book}")
            lines.append("")

        # Related concepts (Obsidian link style)
        related_concepts = self._graph_store.get_neighbors(concept.id)
        if related_concepts:
            lines.append("## 相关概念")
            lines.append("")
            for rel_id in related_concepts[:20]:
                node = self._graph_store.get_node(rel_id)
                if node:
                    lines.append(f"- [[{node.label}]]")
            lines.append("")

        return "\n".join(lines)

    def get_state_summary(self) -> str:
        """获取当前 Pipeline 状态摘要。"""
        return (
            f"📊 Pipeline 状态:\n"
            f"   文档: {len(self.state.documents)} 个已加载, {self.state.compiled_docs} 个已编译\n"
            f"   概念: {self.state.total_concepts} 个\n"
            f"   Skill: {self.state.total_skills} 个\n"
            f"   跨书连接: {self.state.cross_links} 条\n"
            f"   冲突: {self.state.total_conflicts} 个"
        )
