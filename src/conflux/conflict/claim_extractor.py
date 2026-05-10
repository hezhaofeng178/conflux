"""Claim Extractor - 从文本中提取可验证/可反驳的论断。

论断（Claim）是冲突检测的基本单元，代表文本中可被验证或反驳的陈述。
通过 LLM 从文档的各个章节中自动提取。
"""

from __future__ import annotations

import json
from typing import Optional

from conflux.models.conflict import Claim
from conflux.models.document import Document
from conflux.llm.client import LLMClient
from conflux.llm.prompts.claim_extraction import (
    CLAIM_EXTRACTION_SYSTEM,
    CLAIM_EXTRACTION_PROMPT,
)


class ClaimExtractor:
    """论断提取器。

    从文档中提取"可被验证或反驳"的陈述性论断。
    这些论断将作为冲突检测的基本单元。

    Features:
    - 按章节逐段提取
    - LLM 驱动的结构化提取
    - 置信度过滤
    - 来源追溯
    """

    def __init__(
        self,
        llm_client: Optional[LLMClient] = None,
        min_confidence: float = 0.7,
    ):
        """初始化论断提取器。

        Args:
            llm_client: LLM 客户端。
            min_confidence: 最低置信度阈值。
        """
        self.llm = llm_client or LLMClient()
        self.min_confidence = min_confidence

    async def extract_claims(self, document: Document) -> list[Claim]:
        """从文档中提取所有论断。

        遍历文档的所有章节和 section，逐段调用 LLM 提取论断。

        Args:
            document: 解析后的文档 IR。

        Returns:
            提取到的论断列表。
        """
        all_claims: list[Claim] = []

        for chapter in document.structure:
            for section in chapter.sections:
                if not section.content or not section.content.strip():
                    continue

                claims = await self._extract_from_section(
                    content=section.content,
                    book_title=document.meta.title,
                    chapter_title=chapter.title,
                    section_title=section.title or "",
                    document_id=document.id,
                )
                all_claims.extend(claims)

        return all_claims

    async def extract_from_text(
        self,
        text: str,
        source_book: str = "未知",
        chapter: str = "未知",
        section: str = "",
    ) -> list[Claim]:
        """从纯文本中提取论断（便捷接口）。

        Args:
            text: 文本内容。
            source_book: 来源书名。
            chapter: 来源章节。
            section: 来源 section。

        Returns:
            提取到的论断列表。
        """
        return await self._extract_from_section(
            content=text,
            book_title=source_book,
            chapter_title=chapter,
            section_title=section,
        )

    async def _extract_from_section(
        self,
        content: str,
        book_title: str,
        chapter_title: str,
        section_title: str = "",
        document_id: Optional[str] = None,
    ) -> list[Claim]:
        """从单个 section 中提取论断。"""
        # 截断过长内容
        text = content[:3000]

        location = chapter_title
        if section_title:
            location += f" > {section_title}"

        # 构建 prompt
        user_prompt = CLAIM_EXTRACTION_PROMPT.format(
            content=text,
            book_title=book_title,
            chapter_title=chapter_title,
            location=location,
        )

        # 调用 LLM
        response = await self.llm.chat(
            system_prompt=CLAIM_EXTRACTION_SYSTEM,
            user_prompt=user_prompt,
            response_format="json",
        )

        return self._parse_claims(
            response=response,
            book_title=book_title,
            chapter_title=chapter_title,
            section_title=section_title,
            document_id=document_id,
        )

    def _parse_claims(
        self,
        response: str,
        book_title: str,
        chapter_title: str,
        section_title: Optional[str],
        document_id: Optional[str] = None,
    ) -> list[Claim]:
        """解析 LLM 返回的论断列表。"""
        try:
            data = json.loads(response)
            claims_data = data.get("claims", [])
        except (json.JSONDecodeError, KeyError, TypeError):
            return []

        claims: list[Claim] = []
        for item in claims_data:
            if not isinstance(item, dict):
                continue

            confidence = item.get("confidence", 0.8)
            if confidence < self.min_confidence:
                continue

            statement = item.get("statement", "").strip()
            if not statement:
                continue

            # 构建位置信息
            location = chapter_title
            if section_title:
                location += f" > {section_title}"

            claim = Claim(
                statement=statement,
                subject=item.get("subject", statement[:20]),
                source_book=book_title,
                source_chapter=chapter_title,
                source_section=section_title,
                source_location=location,
                source_document_id=document_id,
                claim_type=item.get("type", "factual"),
                confidence=confidence,
                context=item.get("context"),
            )

            claims.append(claim)

        return claims
