"""IR utilities - 中间表示辅助工具。"""

from __future__ import annotations

from conflux.models.document import Chapter, Document, Section


def merge_short_sections(document: Document, min_words: int = 50) -> Document:
    """合并过短的 Section（减少 LLM 调用次数）。

    将连续的短 Section 合并为一个，直到达到 min_words 字数阈值。
    """
    for chapter in document.get_all_chapters_flat():
        if len(chapter.sections) <= 1:
            continue

        merged_sections: list[Section] = []
        buffer_title: str | None = None
        buffer_content_parts: list[str] = []
        buffer_word_count = 0

        for section in chapter.sections:
            if buffer_word_count + section.word_count < min_words:
                # 累积
                if section.title and not buffer_title:
                    buffer_title = section.title
                if section.content:
                    buffer_content_parts.append(section.content)
                    buffer_word_count += section.word_count
            else:
                # 先保存 buffer
                if buffer_content_parts:
                    merged_sections.append(Section(
                        title=buffer_title,
                        level=section.level,
                        content="\n\n".join(buffer_content_parts),
                    ))
                # 开始新 buffer
                buffer_title = section.title
                buffer_content_parts = [section.content] if section.content else []
                buffer_word_count = section.word_count

        # 处理最后的 buffer
        if buffer_content_parts:
            merged_sections.append(Section(
                title=buffer_title,
                level=3,
                content="\n\n".join(buffer_content_parts),
            ))

        chapter.sections = merged_sections

    return document


def count_sections(document: Document) -> int:
    """统计文档总 Section 数。"""
    return len(document.get_all_sections())


def extract_chapter_titles(document: Document) -> list[str]:
    """提取所有章节标题。"""
    return [ch.title for ch in document.get_all_chapters_flat()]
