"""Skill Generator - 将概念转化为 AI 可调用的 Skill YAML 文件。

基于提取的概念和原文上下文，生成结构化的 Skill 描述。
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import structlog
import yaml

from conflux.models.concept import Concept
from conflux.models.document import Document
from conflux.models.skill import (
    Skill,
    SkillCaveat,
    SkillFact,
    SkillKnowledge,
    SkillProcedure,
    SkillSource,
)
from conflux.llm.client import LLMClient, get_llm_client

logger = structlog.get_logger(__name__)

SKILL_GENERATION_SYSTEM = """你是一个 AI 技能设计师。你的任务是将一个知识概念转化为 AI Agent 可调用的结构化技能描述。

设计原则：
1. description 要精准、信息密度高（AI 靠此匹配调用）
2. facts 列出关键事实（可直接引用的知识点）
3. procedures 描述"什么时候用、怎么用"（操作指南）
4. caveats 标注注意事项和局限性

输出要求：返回 JSON"""

SKILL_GENERATION_PROMPT = """将以下概念转化为一个 AI 可调用的 Skill 描述。

## 概念信息
- 名称: {concept_name}
- 定义: {concept_definition}
- 领域: {concept_domain}
- 来源: {source_book} · {source_chapter}

## 相关原文
{context}

## 输出格式
```json
{{
  "description": "技能描述（100字以内，精准概括该知识点的应用场景）",
  "facts": ["事实1", "事实2", "事实3"],
  "procedures": [
    {{
      "trigger": "触发条件（什么时候使用此知识）",
      "steps": ["步骤1", "步骤2"],
      "expected_output": "预期输出"
    }}
  ],
  "caveats": ["注意事项1"],
  "tags": ["标签1", "标签2"]
}}
```

请生成："""


class SkillGenerator:
    """Skill 生成器。

    将 Concept 列表 + 原文上下文转化为 Skill YAML 文件。
    """

    def __init__(self, llm_client: Optional[LLMClient] = None):
        self.llm = llm_client or get_llm_client()

    async def generate_skills(
        self,
        concepts: list[Concept],
        document: Document,
        *,
        max_concurrent: int = 3,
        batch_size: int = 3,
    ) -> list[Skill]:
        """为概念列表生成 Skill。

        优化策略：
        - 多个概念合并为一次 LLM 调用（batch_size 控制每批数量）
        - 多个批次并发执行（max_concurrent 控制并发数）

        Args:
            concepts: 提取出的概念列表
            document: 原始文档（用于获取上下文）
            max_concurrent: 最大并发 LLM 调用数
            batch_size: 每批合并的概念数量

        Returns:
            生成的 Skill 列表
        """
        import asyncio

        skills: list[Skill] = []

        logger.info(
            "skill_generation_start",
            book=document.meta.title,
            concept_count=len(concepts),
        )

        # 将概念分批
        batches = [
            concepts[i : i + batch_size]
            for i in range(0, len(concepts), batch_size)
        ]

        logger.info(
            "skill_batch_info",
            concept_count=len(concepts),
            batch_count=len(batches),
            batch_size=batch_size,
        )

        semaphore = asyncio.Semaphore(max_concurrent)

        async def _generate_batch(batch: list[Concept]) -> list[Skill]:
            async with semaphore:
                return await self._generate_batch_skills(batch, document)

        tasks = [_generate_batch(batch) for batch in batches]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.warning("skill_batch_failed", batch=i, error=str(result))
                # 退化为模板生成
                for concept in batches[i]:
                    skills.append(self._generate_fallback_skill(concept, document))
            else:
                skills.extend(result)

        logger.info("skill_generation_done", total_skills=len(skills))
        return skills

    async def _generate_batch_skills(
        self, concepts: list[Concept], document: Document
    ) -> list[Skill]:
        """为一批概念生成 Skill（一次 LLM 调用）。"""
        if len(concepts) == 1:
            # 单个概念走原逻辑
            skill = await self._generate_single_skill(concepts[0], document)
            return [skill] if skill else [self._generate_fallback_skill(concepts[0], document)]

        # 多个概念合并 prompt
        concept_blocks = []
        for idx, concept in enumerate(concepts, 1):
            context = self._find_context_for_concept(concept, document)
            block = (
                f"### 概念 {idx}: {concept.name}\n"
                f"- 定义: {concept.definition or '无定义'}\n"
                f"- 领域: {concept.domain or '未知'}\n"
                f"- 来源: {concept.source_book} · {concept.source_chapter or '未知'}\n"
                f"- 上下文: {context[:1000]}\n"
            )
            concept_blocks.append(block)

        batch_prompt = (
            "将以下多个概念分别转化为 AI 可调用的 Skill 描述。\n\n"
            + "\n".join(concept_blocks)
            + "\n## 输出格式\n"
            "返回一个 JSON 数组，每个元素对应一个概念的 Skill：\n"
            "```json\n"
            "[\n"
            '  {"name": "概念名", "description": "...", "facts": [...], '
            '"procedures": [...], "caveats": [...], "tags": [...]},\n'
            "  ...\n"
            "]\n"
            "```\n\n请生成："
        )

        try:
            data = await self.llm.complete_json(
                prompt=batch_prompt,
                system_prompt=SKILL_GENERATION_SYSTEM,
            )

            # 解析返回结果
            if isinstance(data, dict) and "skills" in data:
                items = data["skills"]
            elif isinstance(data, list):
                items = data
            else:
                items = [data]

            skills = []
            for idx, item in enumerate(items):
                concept = concepts[idx] if idx < len(concepts) else concepts[-1]
                if isinstance(item, dict):
                    skill = self._build_skill_from_response(item, concept, document)
                    skills.append(skill)

            # 如果返回数量不够，用 fallback 补齐
            for idx in range(len(skills), len(concepts)):
                skills.append(self._generate_fallback_skill(concepts[idx], document))

            return skills

        except Exception as e:
            logger.warning("batch_skill_generation_failed", error=str(e))
            return [self._generate_fallback_skill(c, document) for c in concepts]

    async def _generate_single_skill(
        self, concept: Concept, document: Document
    ) -> Optional[Skill]:
        """为单个概念生成 Skill（通过 LLM）。"""
        # 获取相关上下文
        context = self._find_context_for_concept(concept, document)

        prompt = SKILL_GENERATION_PROMPT.format(
            concept_name=concept.name,
            concept_definition=concept.definition or "无定义",
            concept_domain=concept.domain or "未知",
            source_book=concept.source_book,
            source_chapter=concept.source_chapter or "未知",
            context=context[:3000],
        )

        data = await self.llm.complete_json(
            prompt=prompt,
            system_prompt=SKILL_GENERATION_SYSTEM,
        )

        return self._build_skill_from_response(data, concept, document)

    def _generate_fallback_skill(self, concept: Concept, document: Document) -> Skill:
        """不调用 LLM 的退化生成。"""
        return Skill(
            name=f"{concept.name}知识",
            source=SkillSource(
                book=document.meta.title,
                chapter=concept.source_chapter,
                document_id=document.id,
            ),
            description=concept.definition or f"关于{concept.name}的知识",
            knowledge=SkillKnowledge(
                facts=[SkillFact(statement=concept.definition)] if concept.definition else [],
            ),
            domain=concept.domain,
            tags=concept.tags or [concept.name],
            concept_id=concept.id,
        )

    def _build_skill_from_response(
        self, data: dict | list, concept: Concept, document: Document
    ) -> Skill:
        """从 LLM 响应构建 Skill 对象。"""
        if isinstance(data, list):
            data = data[0] if data else {}

        # 解析 facts
        facts = [
            SkillFact(statement=f) for f in data.get("facts", []) if isinstance(f, str)
        ]

        # 解析 procedures
        procedures: list[SkillProcedure] = []
        for proc in data.get("procedures", []):
            if isinstance(proc, dict):
                procedures.append(SkillProcedure(
                    trigger=proc.get("trigger", ""),
                    steps=proc.get("steps", []),
                    expected_output=proc.get("expected_output"),
                ))

        # 解析 caveats
        caveats = [
            SkillCaveat(description=c) for c in data.get("caveats", []) if isinstance(c, str)
        ]

        return Skill(
            name=f"{concept.name}知识",
            source=SkillSource(
                book=document.meta.title,
                chapter=concept.source_chapter,
                document_id=document.id,
            ),
            description=data.get("description", concept.definition or ""),
            knowledge=SkillKnowledge(
                facts=facts,
                procedures=procedures,
                caveats=caveats,
            ),
            domain=concept.domain,
            tags=data.get("tags", concept.tags or [concept.name]),
            concept_id=concept.id,
            related_concepts=[concept.id],
        )

    def _find_context_for_concept(self, concept: Concept, document: Document) -> str:
        """从文档中找到与概念相关的上下文文本。"""
        relevant_parts: list[str] = []
        search_terms = [concept.name] + concept.aliases[:3]

        for section in document.get_all_sections():
            content_lower = section.content.lower()
            for term in search_terms:
                if term.lower() in content_lower:
                    relevant_parts.append(section.content[:500])
                    break

            if len(relevant_parts) >= 3:  # 最多取 3 段
                break

        return "\n---\n".join(relevant_parts) if relevant_parts else "无相关上下文"

    def write_skills_to_dir(self, skills: list[Skill], output_dir: Path) -> list[Path]:
        """将 Skill 列表写入目录为 YAML 文件。

        Args:
            skills: Skill 列表
            output_dir: 输出目录

        Returns:
            写入的文件路径列表
        """
        output_dir.mkdir(parents=True, exist_ok=True)
        written: list[Path] = []

        for skill in skills:
            # 生成安全的文件名
            safe_name = self._safe_filename(skill.name)
            file_path = output_dir / f"{safe_name}.skill.yaml"

            yaml_data = skill.to_yaml_dict()
            file_path.write_text(
                yaml.dump(yaml_data, allow_unicode=True, default_flow_style=False, sort_keys=False),
                encoding="utf-8",
            )
            written.append(file_path)

        logger.info("skills_written", count=len(written), dir=str(output_dir))
        return written

    def _safe_filename(self, name: str) -> str:
        """将名称转为安全文件名。"""
        import re
        safe = re.sub(r"[^\w\u4e00-\u9fff\-]", "_", name)
        return safe[:50].strip("_") or "unnamed"
