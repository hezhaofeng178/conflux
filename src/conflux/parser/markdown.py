"""Markdown parser - Markdown 文件解析器。

基于标题层级（# ## ###）拆分章节，生成 Document IR。
这是 MVP Phase 1 的核心 Parser。
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
    Paragraph,
    Section,
    SourceFormat,
)
from conflux.parser.base import BaseParser


# 匹配 Markdown 标题行
HEADING_PATTERN = re.compile(r"^(#{1,6})\s+(.+)$", re.MULTILINE)


class MarkdownParser(BaseParser):
    """Markdown 文件解析器。

    解析策略：
    - # (h1) → Chapter (level 1)
    - ## (h2) → Chapter.children (level 2) 或 Section
    - ### (h3) 及以下 → Section
    - 标题之间的文本 → Section.content / Paragraph
    """

    supported_extensions = ["md", "markdown", "mdx"]
    source_format = SourceFormat.MARKDOWN

    def __init__(self, section_level_threshold: int = 3):
        """
        Args:
            section_level_threshold: >= 此级别的标题视为 Section（默认 h3+）
        """
        self.section_level_threshold = section_level_threshold

    def parse(self, path: Path, **kwargs) -> Document:
        """解析 Markdown 文件为 Document IR。"""
        self.validate_file(path)

        try:
            content = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            try:
                content = path.read_text(encoding="gbk")
            except Exception as e:
                raise ParseError(f"无法读取文件编码: {path}, {e}")

        title = kwargs.get("title") or self._extract_title(content, path)
        author = kwargs.get("author")

        meta = DocumentMeta.from_file(
            path=path,
            title=title,
            source_format=self.source_format,
            author=author,
        )

        structure = self._parse_structure(content)

        return Document(meta=meta, structure=structure)

    def _extract_title(self, content: str, path: Path) -> str:
        """从文件内容或文件名提取标题。"""
        # 尝试从第一个 h1 标题提取
        match = re.search(r"^#\s+(.+)$", content, re.MULTILINE)
        if match:
            return match.group(1).strip()
        # 否则用文件名
        return path.stem

    def _parse_structure(self, content: str) -> list[Chapter]:
        """将 Markdown 内容解析为章节结构。"""
        # 按行分割，识别标题和内容
        lines = content.split("\n")
        segments = self._segment_by_headings(lines)

        if not segments:
            # 没有标题，整体作为单个章节
            return [
                Chapter(
                    title="全文",
                    level=1,
                    sections=[Section(title=None, level=3, content=content.strip())],
                )
            ]

        # 构建层级结构
        return self._build_chapter_tree(segments)

    def _segment_by_headings(self, lines: list[str]) -> list[dict]:
        """将行列表按标题分段。

        返回: [{"level": int, "title": str, "content": str}, ...]
        """
        segments: list[dict] = []
        current_content_lines: list[str] = []
        preamble_lines: list[str] = []  # 第一个标题前的内容

        found_first_heading = False

        for line in lines:
            heading_match = HEADING_PATTERN.match(line)
            if heading_match:
                if not found_first_heading:
                    found_first_heading = True
                    preamble_lines = current_content_lines
                    current_content_lines = []
                else:
                    # 保存上一段
                    if segments:
                        segments[-1]["content"] = "\n".join(current_content_lines).strip()
                    current_content_lines = []

                level = len(heading_match.group(1))
                title = heading_match.group(2).strip()
                segments.append({"level": level, "title": title, "content": ""})
            else:
                current_content_lines.append(line)

        # 处理最后一段
        if segments:
            segments[-1]["content"] = "\n".join(current_content_lines).strip()

        # 如果有前言内容，插入到开头
        preamble = "\n".join(preamble_lines).strip()
        if preamble and segments:
            # 将前言作为第一章的前置 section
            segments.insert(0, {"level": 0, "title": "_preamble", "content": preamble})

        return segments

    def _build_chapter_tree(self, segments: list[dict]) -> list[Chapter]:
        """将扁平的分段列表构建为嵌套的章节树。"""
        chapters: list[Chapter] = []
        chapter_stack: list[Chapter] = []  # 用于追踪层级

        for seg in segments:
            level = seg["level"]
            title = seg["title"]
            content = seg["content"]

            # 前言处理
            if level == 0:
                if chapters:
                    # 添加为第一章的前置 section
                    chapters[0].sections.insert(
                        0, self._make_section(None, content, level=0)
                    )
                else:
                    # 创建"前言"章节
                    ch = Chapter(title="前言", level=1)
                    ch.sections.append(self._make_section(None, content, level=1))
                    chapters.append(ch)
                    chapter_stack = [ch]
                continue

            if level < self.section_level_threshold:
                # 视为 Chapter
                chapter = Chapter(title=title, level=level)
                if content:
                    chapter.sections.append(self._make_section(None, content, level))

                if level == 1:
                    # 顶层章节
                    chapters.append(chapter)
                    chapter_stack = [chapter]
                else:
                    # 子章节：找到合适的父级
                    while chapter_stack and chapter_stack[-1].level >= level:
                        chapter_stack.pop()

                    if chapter_stack:
                        chapter_stack[-1].children.append(chapter)
                    else:
                        # 没有合适的父级，提升为顶层
                        chapters.append(chapter)

                    chapter_stack.append(chapter)
            else:
                # 视为 Section，归入最近的 Chapter
                section = self._make_section(title, content, level)

                if chapter_stack:
                    chapter_stack[-1].sections.append(section)
                elif chapters:
                    chapters[-1].sections.append(section)
                else:
                    # 没有章节，创建默认章节
                    ch = Chapter(title="正文", level=1)
                    ch.sections.append(section)
                    chapters.append(ch)
                    chapter_stack = [ch]

        return chapters

    def _make_section(self, title: Optional[str], content: str, level: int) -> Section:
        """创建 Section 实例。"""
        paragraphs = self._split_paragraphs(content) if content else []
        return Section(
            title=title,
            level=max(level, 3),
            content=content,
            paragraphs=paragraphs,
        )

    def _split_paragraphs(self, content: str) -> list[Paragraph]:
        """将文本按空行分割为段落。"""
        if not content.strip():
            return []

        raw_paragraphs = re.split(r"\n\s*\n", content)
        paragraphs: list[Paragraph] = []

        for raw in raw_paragraphs:
            text = raw.strip()
            if not text:
                continue

            # 识别段落类型
            p_type = self._detect_paragraph_type(text)
            paragraphs.append(Paragraph(content=text, paragraph_type=p_type))

        return paragraphs

    def _detect_paragraph_type(self, text: str) -> str:
        """检测段落类型。"""
        if text.startswith("```"):
            return "code"
        if text.startswith(">"):
            return "quote"
        if re.match(r"^[\-\*\d]+[\.\)]\s", text):
            return "list"
        if "|" in text and "---" in text:
            return "table"
        return "text"
