"""Skill models - AI 可调用的技能索引格式。

Skill 是 Conflux 对机器端的输出产物，供 AI Agent 精准调用知识。
"""

from __future__ import annotations

import uuid
from typing import Optional

from pydantic import BaseModel, Field


class SkillSource(BaseModel):
    """Skill 的来源追溯信息。"""

    book: str  # 书名
    chapter: Optional[str] = None
    section: Optional[str] = None
    page: Optional[int] = None
    document_id: Optional[str] = None


class SkillFact(BaseModel):
    """知识事实 - 可直接引用的陈述。"""

    statement: str  # 事实陈述
    confidence: float = 1.0
    source_location: Optional[str] = None  # 精确出处


class SkillProcedure(BaseModel):
    """操作程序 - 分步骤的知识应用指南。"""

    trigger: str  # 触发条件（什么场景下使用）
    steps: list[str] = Field(default_factory=list)  # 执行步骤
    prerequisites: list[str] = Field(default_factory=list)  # 前置条件
    expected_output: Optional[str] = None  # 预期结果


class SkillCaveat(BaseModel):
    """注意事项/警告。"""

    description: str
    severity: str = "info"  # info | warning | critical
    related_conflict_id: Optional[str] = None  # 关联冲突节点


class SkillKnowledge(BaseModel):
    """Skill 包含的知识内容。"""

    facts: list[SkillFact] = Field(default_factory=list)
    procedures: list[SkillProcedure] = Field(default_factory=list)
    caveats: list[SkillCaveat] = Field(default_factory=list)


class Skill(BaseModel):
    """技能索引 - 面向 AI Agent 的结构化知识单元。

    一个 Skill 对应一个可独立调用的知识点，AI Agent 可以
    根据 description 和 tags 精准定位并调用相关知识。
    """

    id: str = Field(default_factory=lambda: f"skill_{uuid.uuid4().hex[:8]}")
    name: str  # 技能名称
    version: str = "1.0.0"
    source: SkillSource

    # 核心内容
    description: str  # 技能描述（AI 用于匹配调用的关键信息）
    knowledge: SkillKnowledge = Field(default_factory=SkillKnowledge)

    # 分类与检索
    domain: Optional[str] = None  # 所属领域
    tags: list[str] = Field(default_factory=list)
    related_skills: list[str] = Field(default_factory=list)  # 关联 Skill ID
    related_concepts: list[str] = Field(default_factory=list)  # 关联概念 ID

    # 元数据
    generated_at: Optional[str] = None
    concept_id: Optional[str] = None  # 对应的概念节点 ID

    def to_yaml_dict(self) -> dict:
        """转换为适合 YAML 输出的字典格式。"""
        return {
            "skill": {
                "id": self.id,
                "name": self.name,
                "version": self.version,
                "source": self.source.model_dump(exclude_none=True),
                "description": self.description,
                "knowledge": {
                    "facts": [f.statement for f in self.knowledge.facts],
                    "procedures": [
                        {"trigger": p.trigger, "steps": p.steps}
                        for p in self.knowledge.procedures
                    ],
                    "caveats": [c.description for c in self.knowledge.caveats],
                },
                "tags": self.tags,
                "related_skills": self.related_skills,
            }
        }
