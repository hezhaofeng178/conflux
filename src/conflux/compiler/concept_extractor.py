"""Concept Extractor - 从 IR 文档中提取结构化概念。

调用 LLM 对每个 Section 进行概念提取，输出 Concept + Relation 列表。
"""

from __future__ import annotations

from typing import Optional

import structlog

from conflux import CompileError
from conflux.llm.client import LLMClient, get_llm_client
from conflux.llm.prompts.concept_extraction import build_concept_extraction_prompt
from conflux.models.concept import Concept, ConceptType, Relation, RelationType
from conflux.models.document import Document, Section

logger = structlog.get_logger(__name__)


class ExtractionResult:
    """单次提取的结果。"""

    def __init__(self):
        self.concepts: list[Concept] = []
        self.relations: list[Relation] = []


class ConceptExtractor:
    """概念提取器。

    遍历 Document 的所有 Section，通过 LLM 提取概念和关系。

    策略：
    - 章节级粒度：每个 Section 调用一次 LLM
    - 去重：同名概念合并（保留更详细的定义）
    - 关系推断：从同一段文本中提取的关系更可信
    """

    def __init__(self, llm_client: Optional[LLMClient] = None):
        self.llm = llm_client or get_llm_client()
        self._concept_name_map: dict[str, Concept] = {}  # name → Concept（用于去重）

    async def extract_from_document(
        self, document: Document, *, batch_mode: bool = True, max_concurrent: int = 3
    ) -> ExtractionResult:
        """从整个文档提取概念和关系。

        Args:
            document: 解析后的 Document IR
            batch_mode: 是否合并 section 批量提取（减少 LLM 调用次数）
            max_concurrent: 最大并发 LLM 调用数

        Returns:
            ExtractionResult 包含去重后的概念和关系列表
        """
        import asyncio

        result = ExtractionResult()
        sections = document.get_all_sections()

        logger.info(
            "concept_extraction_start",
            book=document.meta.title,
            section_count=len(sections),
        )

        # 找到每个 section 所属的 chapter 标题
        chapter_map = self._build_section_chapter_map(document)

        # 过滤空 section
        valid_sections = [
            (s, chapter_map.get(s.id, "未知章节"))
            for s in sections
            if not s.is_empty
        ]

        if batch_mode:
            # ── 批量模式：合并相邻 section，减少 LLM 调用次数 ──
            batches = self._batch_sections(valid_sections, max_chars=4000)
            logger.info(
                "batch_extraction",
                sections=len(valid_sections),
                batches=len(batches),
                book=document.meta.title,
            )

            # 并发执行批次
            semaphore = asyncio.Semaphore(max_concurrent)

            async def _extract_batch(batch):
                async with semaphore:
                    return await self._extract_from_section_batch(
                        sections_with_chapters=batch,
                        book_title=document.meta.title,
                    )

            tasks = [_extract_batch(batch) for batch in batches]
            batch_results = await asyncio.gather(*tasks, return_exceptions=True)

            for i, br in enumerate(batch_results):
                if isinstance(br, Exception):
                    logger.warning("batch_extraction_failed", batch=i, error=str(br))
                    continue
                for concept in br.concepts:
                    self._merge_concept(concept, result)
                result.relations.extend(br.relations)
        else:
            # ── 逐 section 模式（兼容旧行为，带并发） ──
            semaphore = asyncio.Semaphore(max_concurrent)

            async def _extract_one(section, chapter_title, idx):
                async with semaphore:
                    return idx, await self._extract_from_section(
                        section=section,
                        book_title=document.meta.title,
                        chapter_title=chapter_title,
                    )

            tasks = [
                _extract_one(s, ch, i) for i, (s, ch) in enumerate(valid_sections)
            ]
            task_results = await asyncio.gather(*tasks, return_exceptions=True)

            for tr in task_results:
                if isinstance(tr, Exception):
                    logger.warning("section_extraction_failed", error=str(tr))
                    continue
                idx, section_result = tr
                for concept in section_result.concepts:
                    self._merge_concept(concept, result)
                result.relations.extend(section_result.relations)

        # 修复关系中的概念引用（将名称映射为 ID）
        result.relations = self._resolve_relation_ids(result.relations, result)

        logger.info(
            "concept_extraction_done",
            book=document.meta.title,
            total_concepts=len(result.concepts),
            total_relations=len(result.relations),
        )

        return result

    def _batch_sections(
        self,
        sections_with_chapters: list[tuple[Section, str]],
        max_chars: int = 4000,
    ) -> list[list[tuple[Section, str]]]:
        """将多个 section 按字数合并为批次，减少 LLM 调用。

        Args:
            sections_with_chapters: (section, chapter_title) 列表
            max_chars: 每批最大字符数

        Returns:
            分批后的 section 列表
        """
        batches: list[list[tuple[Section, str]]] = []
        current_batch: list[tuple[Section, str]] = []
        current_len = 0

        for item in sections_with_chapters:
            section = item[0]
            section_len = len(section.content)
            if current_batch and current_len + section_len > max_chars:
                batches.append(current_batch)
                current_batch = []
                current_len = 0
            current_batch.append(item)
            current_len += section_len

        if current_batch:
            batches.append(current_batch)

        return batches

    async def _extract_from_section_batch(
        self,
        sections_with_chapters: list[tuple[Section, str]],
        book_title: str,
    ) -> ExtractionResult:
        """从合并的多个 section 中一次性提取概念（单次 LLM 调用）。"""
        # 合并内容
        combined_content = ""
        for section, chapter_title in sections_with_chapters:
            header = f"### {chapter_title} / {section.title or '未知'}\n"
            combined_content += header + section.content + "\n\n"

        # 用第一个 section 的 chapter 作为代表
        first_chapter = sections_with_chapters[0][1]
        section_titles = [s.title or "未知" for s, _ in sections_with_chapters]

        system_prompt, user_prompt = build_concept_extraction_prompt(
            content=combined_content.strip(),
            book_title=book_title,
            chapter_title=first_chapter,
            section_title="、".join(section_titles),
        )

        response = await self.llm.complete_json(
            prompt=user_prompt,
            system_prompt=system_prompt,
        )

        # 用第一个 section 作为解析上下文
        return self._parse_extraction_response(
            response, book_title, first_chapter, sections_with_chapters[0][0]
        )

    async def _extract_from_section(
        self,
        section: Section,
        book_title: str,
        chapter_title: str,
    ) -> ExtractionResult:
        """从单个 Section 提取概念。"""
        system_prompt, user_prompt = build_concept_extraction_prompt(
            content=section.content,
            book_title=book_title,
            chapter_title=chapter_title,
            section_title=section.title or "未知",
        )

        response = await self.llm.complete_json(
            prompt=user_prompt,
            system_prompt=system_prompt,
        )

        return self._parse_extraction_response(
            response, book_title, chapter_title, section
        )

    def _parse_extraction_response(
        self,
        data: dict | list,
        book_title: str,
        chapter_title: str,
        section: Section,
    ) -> ExtractionResult:
        """解析 LLM 返回的 JSON 为 Concept 和 Relation。"""
        result = ExtractionResult()

        if isinstance(data, list):
            data = {"concepts": data, "relations": []}

        # 解析概念
        raw_concepts = data.get("concepts", [])
        for raw in raw_concepts:
            if not isinstance(raw, dict) or "name" not in raw:
                continue

            concept_type = self._map_concept_type(raw.get("type", "entity"))
            concept = Concept(
                name=raw["name"],
                aliases=raw.get("aliases", []),
                concept_type=concept_type,
                definition=raw.get("definition", ""),
                source_book=book_title,
                source_chapter=chapter_title,
                source_section=section.title,
                domain=raw.get("domain"),
                tags=raw.get("tags", []),
                confidence=raw.get("importance_score", 0.8),
            )
            result.concepts.append(concept)

        # 解析关系
        raw_relations = data.get("relations", [])
        for raw in raw_relations:
            if not isinstance(raw, dict):
                continue
            source_name = raw.get("source", "")
            target_name = raw.get("target", "")
            if not source_name or not target_name:
                continue

            rel_type = self._map_relation_type(raw.get("relation", "related_to"))
            relation = Relation(
                source_id=source_name,  # 暂用名称，后续 resolve
                target_id=target_name,
                relation_type=rel_type,
                description=raw.get("description"),
                source_book=book_title,
                source_section=section.title,
                inferred_by="llm",
            )
            result.relations.append(relation)

        return result

    def _merge_concept(self, new_concept: Concept, result: ExtractionResult) -> None:
        """合并同名概念（保留更详细的信息）。"""
        key = new_concept.name.lower().strip()

        if key in self._concept_name_map:
            existing = self._concept_name_map[key]
            # 合并别名
            for alias in new_concept.aliases:
                if alias not in existing.aliases:
                    existing.aliases.append(alias)
            # 保留更长的定义
            if len(new_concept.definition) > len(existing.definition):
                existing.definition = new_concept.definition
            # 合并标签
            for tag in new_concept.tags:
                if tag not in existing.tags:
                    existing.tags.append(tag)
        else:
            self._concept_name_map[key] = new_concept
            result.concepts.append(new_concept)

    def _resolve_relation_ids(
        self, relations: list[Relation], result: ExtractionResult
    ) -> list[Relation]:
        """将关系中的概念名称替换为实际 ID。"""
        resolved: list[Relation] = []
        name_to_id = {c.name.lower().strip(): c.id for c in result.concepts}
        # 加上别名映射
        for c in result.concepts:
            for alias in c.aliases:
                name_to_id[alias.lower().strip()] = c.id

        for rel in relations:
            source_id = name_to_id.get(rel.source_id.lower().strip())
            target_id = name_to_id.get(rel.target_id.lower().strip())
            if source_id and target_id and source_id != target_id:
                rel.source_id = source_id
                rel.target_id = target_id
                resolved.append(rel)

        return resolved

    def _build_section_chapter_map(self, document: Document) -> dict[str, str]:
        """构建 section_id → chapter_title 的映射。"""
        mapping: dict[str, str] = {}
        for chapter in document.get_all_chapters_flat():
            for section in chapter.sections:
                mapping[section.id] = chapter.title
        return mapping

    def _map_concept_type(self, raw_type: str) -> ConceptType:
        """映射概念类型字符串为枚举。"""
        type_map = {
            "entity": ConceptType.ENTITY,
            "process": ConceptType.PROCESS,
            "theory": ConceptType.THEORY,
            "method": ConceptType.METHOD,
            "property": ConceptType.PROPERTY,
            "category": ConceptType.CATEGORY,
        }
        return type_map.get(raw_type.lower(), ConceptType.ENTITY)

    def _map_relation_type(self, raw_type: str) -> RelationType:
        """映射关系类型字符串为枚举。"""
        try:
            return RelationType(raw_type.lower())
        except ValueError:
            return RelationType.RELATED_TO
