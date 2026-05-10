"""Concept models - 概念与关系。

概念是知识图谱的基本节点，关系是节点间的边。
"""

from __future__ import annotations

import uuid
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class RelationType(str, Enum):
    """关系类型枚举。"""

    # 层级关系
    IS_A = "is_a"  # 心室 is_a 心腔
    PART_OF = "part_of"  # 心室 part_of 心脏
    CONTAINS = "contains"  # 心脏 contains 心室

    # 功能关系
    CAUSES = "causes"  # 交感神经兴奋 causes 心率增快
    CAUSED_BY = "caused_by"  # 心率增快 caused_by 交感神经兴奋
    REGULATES = "regulates"  # 迷走神经 regulates 心率
    DEPENDS_ON = "depends_on"  # 心输出量 depends_on 心率

    # 对比关系
    CONTRASTS = "contrasts"  # 动脉 contrasts 静脉
    SIMILAR_TO = "similar_to"  # 心肌 similar_to 骨骼肌

    # 时序关系
    PRECEDES = "precedes"  # 去极化 precedes 复极化
    FOLLOWS = "follows"  # 复极化 follows 去极化

    # 关联关系
    RELATED_TO = "related_to"  # 通用关联
    APPLIED_IN = "applied_in"  # 理论 applied_in 临床场景
    EXAMPLE_OF = "example_of"  # 心房颤动 example_of 心律失常


class ConceptType(str, Enum):
    """概念类型。"""

    ENTITY = "entity"  # 具体实体：器官、人物、地点
    PROCESS = "process"  # 过程/机制：信号传导、新陈代谢
    THEORY = "theory"  # 理论/原理：Frank-Starling 定律
    METHOD = "method"  # 方法/技术：心电图检查
    PROPERTY = "property"  # 属性/指标：心率、血压
    CATEGORY = "category"  # 分类/类别：循环系统、呼吸系统


class Concept(BaseModel):
    """概念节点 - 知识图谱的基本单元。"""

    id: str = Field(default_factory=lambda: f"concept_{uuid.uuid4().hex[:8]}")
    name: str
    aliases: list[str] = Field(default_factory=list)  # 别名/同义词
    concept_type: ConceptType = ConceptType.ENTITY
    definition: str = ""  # 概念定义
    description: Optional[str] = None  # 更详细的描述

    # 来源信息
    source_book: str = ""  # 来自哪本书
    source_chapter: Optional[str] = None  # 来自哪一章
    source_section: Optional[str] = None  # 来自哪一节
    source_document_id: Optional[str] = None  # 对应的 Document ID

    # 分类标签
    domain: Optional[str] = None  # 所属领域：生理学、解剖学
    tags: list[str] = Field(default_factory=list)

    # 向量嵌入（延迟填充）
    embedding: Optional[list[float]] = Field(default=None, exclude=True)

    # 元数据
    confidence: float = 1.0  # 提取置信度
    extracted_at: Optional[str] = None

    def display_name(self) -> str:
        """显示名称（含别名）。"""
        if self.aliases:
            return f"{self.name}（{', '.join(self.aliases[:3])}）"
        return self.name


class Relation(BaseModel):
    """关系边 - 连接两个概念。"""

    id: str = Field(default_factory=lambda: f"rel_{uuid.uuid4().hex[:8]}")
    source_id: str  # 起始概念 ID
    target_id: str  # 目标概念 ID
    relation_type: RelationType
    description: Optional[str] = None  # 关系描述
    weight: float = 1.0  # 关系强度 (0-1)
    confidence: float = 1.0  # 推理置信度

    # 来源追溯
    source_book: Optional[str] = None
    source_section: Optional[str] = None
    inferred_by: str = "llm"  # llm | rule | manual

    def label(self) -> str:
        """关系的可读标签。"""
        return self.relation_type.value.replace("_", " ")


class ConceptCluster(BaseModel):
    """概念簇 - 一组高度相关的概念。"""

    id: str = Field(default_factory=lambda: f"cluster_{uuid.uuid4().hex[:8]}")
    name: str  # 簇名称
    description: Optional[str] = None
    concept_ids: list[str] = Field(default_factory=list)
    core_concept_id: Optional[str] = None  # 核心概念
    domain: Optional[str] = None
