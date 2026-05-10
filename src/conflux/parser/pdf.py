"""PDF parser - PDF 文件解析器。

使用 PyMuPDF 进行文本提取和布局分析。
需要安装 pymupdf: pip install conflux[pdf]
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Optional

from conflux import ParseError
from conflux.models.document import (
    Chapter,
    Document,
    DocumentMeta,
    Section,
    SourceFormat,
)
from conflux.parser.base import BaseParser


class PdfParser(BaseParser):
    """PDF 文件解析器。

    解析策略：
    1. 使用 PyMuPDF 提取文本
    2. 通过字体大小/加粗检测标题层级
    3. 按标题分割为章节结构
    """

    supported_extensions = ["pdf"]
    source_format = SourceFormat.PDF

    def __init__(self, heading_font_size_threshold: float = 14.0):
        """
        Args:
            heading_font_size_threshold: 大于此字号视为标题
        """
        self.heading_font_size_threshold = heading_font_size_threshold

    def parse(self, path: Path, **kwargs) -> Document:
        """解析 PDF 文件为 Document IR。"""
        self.validate_file(path)

        try:
            import fitz  # PyMuPDF
        except ImportError:
            raise ParseError(
                "PDF 解析需要 PyMuPDF 库。请安装: pip install conflux[pdf]"
            )

        try:
            doc = fitz.open(str(path))
        except Exception as e:
            raise ParseError(f"PDF 文件打开失败: {path}, {e}")

        title = kwargs.get("title") or self._extract_title(doc) or path.stem
        author = kwargs.get("author") or self._extract_author(doc)

        meta = DocumentMeta.from_file(
            path=path,
            title=title,
            source_format=self.source_format,
            author=author,
        )

        chapters = self._extract_structure(doc)
        doc.close()

        return Document(meta=meta, structure=chapters)

    def _extract_title(self, doc) -> Optional[str]:
        """从 PDF 元数据中提取标题。"""
        metadata = doc.metadata
        if metadata and metadata.get("title"):
            return metadata["title"]
        return None

    def _extract_author(self, doc) -> Optional[str]:
        """从 PDF 元数据中提取作者。"""
        metadata = doc.metadata
        if metadata and metadata.get("author"):
            return metadata["author"]
        return None

    def _extract_structure(self, doc) -> list[Chapter]:
        """从 PDF 中提取章节结构。

        优先使用 PDF 书签（TOC）来确定结构，
        如果没有书签则按页面分组。
        """
        # 尝试从 TOC（书签）获取结构
        toc = doc.get_toc()
        if toc:
            return self._build_from_toc(doc, toc)

        # 无书签，按页面粗粒度分章
        return self._build_from_pages(doc)

    def _build_from_toc(self, doc, toc: list) -> list[Chapter]:
        """基于 PDF 书签构建章节结构。"""
        chapters: list[Chapter] = []

        for i, entry in enumerate(toc):
            level, title, page_num = entry[0], entry[1], entry[2]

            # 确定章节文本范围（到下一个同级或上级标题为止）
            start_page = page_num - 1  # 0-indexed
            end_page = self._find_chapter_end(toc, i, doc.page_count)

            # 提取文本
            text = self._extract_pages_text(doc, start_page, end_page)

            if level == 1:
                chapter = Chapter(title=title, level=1)
                if text:
                    chapter.sections.append(Section(
                        title=None, level=3, content=text
                    ))
                chapters.append(chapter)
            elif level == 2 and chapters:
                child = Chapter(title=title, level=2)
                if text:
                    child.sections.append(Section(
                        title=None, level=3, content=text
                    ))
                chapters[-1].children.append(child)
            elif chapters:
                # level 3+ 视为 section
                if chapters[-1].children:
                    chapters[-1].children[-1].sections.append(
                        Section(title=title, level=level + 1, content=text)
                    )
                else:
                    chapters[-1].sections.append(
                        Section(title=title, level=level + 1, content=text)
                    )

        return chapters

    def _find_chapter_end(self, toc: list, current_idx: int, total_pages: int) -> int:
        """找到当前 TOC 条目的结束页（下一个同级或上级条目的起始页）。"""
        current_level = toc[current_idx][0]
        for j in range(current_idx + 1, len(toc)):
            if toc[j][0] <= current_level:
                return toc[j][2] - 1  # 0-indexed
        return total_pages

    def _build_from_pages(self, doc) -> list[Chapter]:
        """无书签时，按固定页数分组为章节。"""
        chapters: list[Chapter] = []
        pages_per_chapter = 10  # 每 10 页一章

        total_pages = doc.page_count
        chapter_idx = 0

        for start in range(0, total_pages, pages_per_chapter):
            end = min(start + pages_per_chapter, total_pages)
            text = self._extract_pages_text(doc, start, end)

            if text.strip():
                chapter_idx += 1
                # 尝试从开头提取标题
                title = self._guess_chapter_title(text) or f"第 {chapter_idx} 部分 (P{start+1}-P{end})"
                chapter = Chapter(title=title, level=1)
                chapter.sections.append(Section(title=None, level=3, content=text))
                chapters.append(chapter)

        return chapters

    def _extract_pages_text(self, doc, start_page: int, end_page: int) -> str:
        """提取指定页范围的文本。"""
        texts: list[str] = []
        for page_num in range(start_page, min(end_page, doc.page_count)):
            try:
                page = doc[page_num]
                text = page.get_text("text")
                if text.strip():
                    texts.append(text.strip())
            except Exception:
                continue
        return "\n\n".join(texts)

    def _guess_chapter_title(self, text: str) -> Optional[str]:
        """从文本开头猜测章节标题。"""
        lines = text.strip().split("\n")
        for line in lines[:5]:  # 看前5行
            line = line.strip()
            # 匹配常见章节标题模式
            if re.match(r"^第[一二三四五六七八九十百千\d]+[章节篇]", line):
                return line
            if re.match(r"^Chapter\s+\d+", line, re.IGNORECASE):
                return line
        return None
