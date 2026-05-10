"""EPUB parser - EPUB 电子书解析器。

解压 EPUB → 提取 HTML 章节 → 转化为 Document IR。
需要安装 ebooklib: pip install conflux[epub]
"""

from __future__ import annotations

import re
from html.parser import HTMLParser
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


class _HTMLTextExtractor(HTMLParser):
    """简易 HTML 文本提取器。"""

    def __init__(self):
        super().__init__()
        self.result: list[str] = []
        self._current_tag: Optional[str] = None
        self._heading_level: int = 0
        self._skip_tags = {"script", "style", "nav", "footer", "header"}
        self._skip = False

    def handle_starttag(self, tag: str, attrs: list) -> None:
        self._current_tag = tag
        if tag in self._skip_tags:
            self._skip = True
        # 检测标题
        if re.match(r"h[1-6]", tag):
            self._heading_level = int(tag[1])
            self.result.append(f"\n{'#' * self._heading_level} ")

    def handle_endtag(self, tag: str) -> None:
        if tag in self._skip_tags:
            self._skip = False
        if tag in ("p", "div", "br", "li"):
            self.result.append("\n")
        if re.match(r"h[1-6]", tag):
            self.result.append("\n")
            self._heading_level = 0
        self._current_tag = None

    def handle_data(self, data: str) -> None:
        if not self._skip:
            self.result.append(data)

    def get_text(self) -> str:
        return "".join(self.result).strip()


def _html_to_markdown(html_content: str) -> str:
    """将 HTML 转换为简化的 Markdown 文本。"""
    extractor = _HTMLTextExtractor()
    extractor.feed(html_content)
    return extractor.get_text()


class EpubParser(BaseParser):
    """EPUB 文件解析器。

    解析策略：
    1. 使用 ebooklib 读取 EPUB
    2. 按 spine 顺序遍历文档项
    3. 将每个 HTML 文档转为 Markdown 文本
    4. 复用 MarkdownParser 的结构化逻辑
    """

    supported_extensions = ["epub"]
    source_format = SourceFormat.EPUB

    def parse(self, path: Path, **kwargs) -> Document:
        """解析 EPUB 文件为 Document IR。"""
        self.validate_file(path)

        try:
            import ebooklib
            from ebooklib import epub
        except ImportError:
            raise ParseError(
                "EPUB 解析需要 ebooklib 库。请安装: pip install conflux[epub]"
            )

        try:
            book = epub.read_epub(str(path))
        except Exception as e:
            raise ParseError(f"EPUB 文件解析失败: {path}, {e}")

        # 提取元数据
        title = kwargs.get("title") or self._get_metadata(book, "title") or path.stem
        author = kwargs.get("author") or self._get_metadata(book, "creator")

        meta = DocumentMeta.from_file(
            path=path,
            title=title,
            source_format=self.source_format,
            author=author,
        )

        # 提取章节内容
        chapters = self._extract_chapters(book, ebooklib)

        return Document(meta=meta, structure=chapters)

    def _get_metadata(self, book, field: str) -> Optional[str]:
        """从 EPUB 元数据中提取字段。"""
        try:
            values = book.get_metadata("DC", field)
            if values:
                return values[0][0]
        except Exception:
            pass
        return None

    def _extract_chapters(self, book, ebooklib) -> list[Chapter]:
        """从 EPUB 中提取章节结构。"""
        chapters: list[Chapter] = []
        chapter_index = 0

        for item in book.get_items_of_type(ebooklib.ITEM_DOCUMENT):
            try:
                html_content = item.get_content().decode("utf-8", errors="ignore")
            except Exception:
                continue

            # HTML → 简化 Markdown 文本
            text = _html_to_markdown(html_content)
            if not text.strip():
                continue

            chapter_index += 1

            # 尝试从文本中提取第一个标题作为章节名
            title_match = re.search(r"^#\s+(.+)$", text, re.MULTILINE)
            ch_title = title_match.group(1).strip() if title_match else f"章节 {chapter_index}"

            # 构建 Chapter
            chapter = Chapter(title=ch_title, level=1)

            # 将文本按段落分割为 sections
            sections = self._text_to_sections(text)
            chapter.sections = sections

            if sections:  # 只添加有内容的章节
                chapters.append(chapter)

        return chapters

    def _text_to_sections(self, text: str) -> list[Section]:
        """将提取的文本转为 Section 列表。"""
        sections: list[Section] = []
        # 按小标题分割
        parts = re.split(r"\n(#{2,6}\s+.+)\n", text)

        current_title: Optional[str] = None
        current_content_parts: list[str] = []

        for part in parts:
            heading_match = re.match(r"^(#{2,6})\s+(.+)$", part.strip())
            if heading_match:
                # 保存前一段
                if current_content_parts:
                    content = "\n".join(current_content_parts).strip()
                    if content:
                        sections.append(Section(
                            title=current_title,
                            level=3,
                            content=content,
                        ))
                current_title = heading_match.group(2).strip()
                current_content_parts = []
            else:
                current_content_parts.append(part)

        # 处理最后一段
        if current_content_parts:
            content = "\n".join(current_content_parts).strip()
            if content:
                sections.append(Section(
                    title=current_title,
                    level=3,
                    content=content,
                ))

        return sections
