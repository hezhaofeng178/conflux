"""Document models - 文档中间表示 (IR)。

IR 是 Parser 层的统一输出格式，后续所有模块都基于 IR 工作。
"""

from __future__ import annotations

import hashlib
import uuid
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, Field, computed_field


class SourceFormat(str, Enum):
    """支持的输入格式。"""

    MARKDOWN = "markdown"
    EPUB = "epub"
    PDF = "pdf"
    HTML = "html"
    TXT = "txt"


class DocumentMeta(BaseModel):
    """文档元数据。"""

    title: str
    author: Optional[str] = None
    source_format: SourceFormat
    language: str = "zh-CN"
    import_time: datetime = Field(default_factory=datetime.now)
    file_hash: Optional[str] = None
    file_path: Optional[str] = None
    isbn: Optional[str] = None
    publisher: Optional[str] = None
    publish_year: Optional[int] = None
    tags: list[str] = Field(default_factory=list)
    description: Optional[str] = None

    @classmethod
    def from_file(cls, path: Path, title: str, source_format: SourceFormat, **kwargs) -> "DocumentMeta":
        """从文件路径创建元数据，自动计算 hash。"""
        file_hash = hashlib.sha256(path.read_bytes()).hexdigest()[:16]
        return cls(
            title=title,
            source_format=source_format,
            file_hash=file_hash,
            file_path=str(path),
            **kwargs,
        )


class Paragraph(BaseModel):
    """段落 - 最小内容单元。"""

    id: str = Field(default_factory=lambda: f"p_{uuid.uuid4().hex[:8]}")
    content: str
    paragraph_type: str = "text"  # text | quote | list | code | table
    metadata: dict = Field(default_factory=dict)


class Section(BaseModel):
    """文档章节中的一个小节。"""

    id: str = Field(default_factory=lambda: f"sec_{uuid.uuid4().hex[:8]}")
    title: Optional[str] = None
    level: int = 3
    content: str = ""
    paragraphs: list[Paragraph] = Field(default_factory=list)
    concepts: list[str] = Field(default_factory=list)  # 编译后填充的概念 ID 列表
    claims: list[str] = Field(default_factory=list)  # 编译后填充的论断 ID 列表

    @computed_field
    @property
    def word_count(self) -> int:
        """自动计算字数。"""
        return len(self.content)

    @computed_field
    @property
    def is_empty(self) -> bool:
        """判断是否为空节。"""
        return len(self.content.strip()) == 0


class Chapter(BaseModel):
    """文档中的一个章节。"""

    id: str = Field(default_factory=lambda: f"ch_{uuid.uuid4().hex[:8]}")
    title: str
    level: int = 1
    sections: list[Section] = Field(default_factory=list)
    children: list["Chapter"] = Field(default_factory=list)

    @computed_field
    @property
    def full_content(self) -> str:
        """获取本章节所有内容的拼接文本。"""
        parts: list[str] = []
        for s in self.sections:
            if s.content:
                parts.append(s.content)
        for child in self.children:
            if child.full_content:
                parts.append(child.full_content)
        return "\n\n".join(parts)

    @computed_field
    @property
    def total_sections(self) -> int:
        """递归计算所有小节数量。"""
        count = len(self.sections)
        for child in self.children:
            count += child.total_sections
        return count

    def get_all_sections_flat(self) -> list[Section]:
        """扁平化获取所有 Section（含子章节的）。"""
        sections: list[Section] = list(self.sections)
        for child in self.children:
            sections.extend(child.get_all_sections_flat())
        return sections


class Document(BaseModel):
    """文档中间表示 (IR) - Parser 层的统一输出。

    所有格式的书籍经过 Parser 后都转化为此结构。
    """

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    meta: DocumentMeta
    structure: list[Chapter] = Field(default_factory=list)

    @computed_field
    @property
    def total_chapters(self) -> int:
        """顶层章节数量。"""
        return len(self.structure)

    @computed_field
    @property
    def total_words(self) -> int:
        """估算总字数。"""
        return sum(s.word_count for s in self.get_all_sections())

    def get_all_sections(self) -> list[Section]:
        """扁平化获取所有 Section。"""
        sections: list[Section] = []
        for chapter in self.structure:
            sections.extend(chapter.get_all_sections_flat())
        return sections

    def get_all_chapters_flat(self) -> list[Chapter]:
        """扁平化获取所有 Chapter（含嵌套子章节）。"""
        chapters: list[Chapter] = []

        def _collect(ch_list: list[Chapter]) -> None:
            for ch in ch_list:
                chapters.append(ch)
                _collect(ch.children)

        _collect(self.structure)
        return chapters

    def summary(self) -> str:
        """生成文档摘要信息。"""
        return (
            f"📖 {self.meta.title}\n"
            f"   作者: {self.meta.author or '未知'}\n"
            f"   格式: {self.meta.source_format.value}\n"
            f"   章节: {self.total_chapters} 章\n"
            f"   字数: ~{self.total_words} 字"
        )
