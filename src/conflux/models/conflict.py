"""Conflict models - 知识冲突与裁决。

当不同来源的知识产生矛盾时，系统会创建冲突节点进行标注。
"""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class ConflictType(str, Enum):
    """冲突类型分类。"""

    FACTUAL = "factual"  # 事实性矛盾：A说X=1，B说X=2
    METHODOLOGICAL = "methodological"  # 方法论分歧：A推荐方法X，B推荐方法Y
    INTERPRETIVE = "interpretive"  # 解读差异：同一现象的不同解释
    TEMPORAL = "temporal"  # 时效性冲突：旧版 vs 新版
    SCOPE = "scope"  # 适用范围冲突：A说"所有人"，B说"仅限成人"


class ConflictSeverity(str, Enum):
    """冲突严重程度。"""

    LOW = "low"  # 差异微小，不影响实际应用
    MEDIUM = "medium"  # 有实质差异，但非关键
    HIGH = "high"  # 重大分歧，可能影响决策
    CRITICAL = "critical"  # 严重矛盾，必须裁决


class VerdictStatus(str, Enum):
    """裁决状态。"""

    UNRESOLVED = "unresolved"  # 未裁决
    RESOLVED = "resolved"  # 已裁决
    DEFERRED = "deferred"  # 暂缓（需更多信息）
    DISMISSED = "dismissed"  # 误报，非真正冲突


class Claim(BaseModel):
    """论断 - 可被验证或反驳的陈述。

    从文本中提取的具体观点/事实声明，是冲突检测的基本单元。
    """

    id: str = Field(default_factory=lambda: f"claim_{uuid.uuid4().hex[:8]}")
    statement: str  # 论断内容
    subject: str  # 论断主题（如 "正常心率范围"）

    # 来源追溯
    source_book: str
    source_chapter: Optional[str] = None
    source_section: Optional[str] = None
    source_location: Optional[str] = None  # 更精确的位置（如 "P128"）
    source_document_id: Optional[str] = None

    # 分类
    claim_type: str = "factual"  # factual | methodological | interpretive
    domain: Optional[str] = None

    # 置信度
    confidence: float = 0.9  # LLM 提取时的置信度
    context: Optional[str] = None  # 原文上下文片段

    # 向量嵌入（延迟填充）
    embedding: Optional[list[float]] = Field(default=None, exclude=True)


class ConflictSide(BaseModel):
    """冲突的一方 - 某个论断在冲突中的立场。"""

    claim_id: str
    source_book: str
    position: str  # 该方的具体立场/数值
    context: Optional[str] = None  # 上下文


class ConflictAnalysis(BaseModel):
    """冲突分析 - 系统对冲突的自动分析。"""

    possible_reasons: list[str] = Field(default_factory=list)  # 可能的原因
    suggested_resolution: Optional[str] = None  # 建议的解决方案
    auto_analysis: Optional[str] = None  # LLM 生成的分析


class Verdict(BaseModel):
    """人类裁决结果。"""

    status: VerdictStatus = VerdictStatus.UNRESOLVED
    decision: Optional[str] = None  # 裁决内容
    decided_by: Optional[str] = None  # 裁决人
    decided_at: Optional[datetime] = None
    notes: str = ""  # 裁决说明
    chosen_side: Optional[str] = None  # 选择了哪一方（claim_id）


class Conflict(BaseModel):
    """冲突节点 - 跨源知识矛盾的完整记录。

    当系统发现不同来源的论断存在矛盾时，创建此节点。
    不替用户做主，而是清晰呈现矛盾双方，交由人类裁决。
    """

    id: str = Field(default_factory=lambda: f"conflict_{uuid.uuid4().hex[:8]}")
    title: str  # 冲突标题
    conflict_type: ConflictType
    severity: ConflictSeverity = ConflictSeverity.MEDIUM

    # 冲突双方
    sides: list[ConflictSide] = Field(default_factory=list)

    # 系统分析
    analysis: ConflictAnalysis = Field(default_factory=ConflictAnalysis)

    # 人类裁决
    verdict: Verdict = Field(default_factory=Verdict)

    # 关联
    related_concepts: list[str] = Field(default_factory=list)  # 涉及的概念
    subject: Optional[str] = None  # 冲突主题

    # 元数据
    detected_at: Optional[datetime] = Field(default_factory=datetime.now)
    detection_confidence: float = 0.8

    @property
    def is_resolved(self) -> bool:
        """是否已裁决。"""
        return self.verdict.status == VerdictStatus.RESOLVED

    @property
    def source_books(self) -> list[str]:
        """涉及的书籍列表。"""
        return list(set(side.source_book for side in self.sides))
