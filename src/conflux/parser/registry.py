"""Parser registry - 解析器注册表。

根据文件后缀自动选择合适的 Parser。
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from conflux import ParseError
from conflux.parser.base import BaseParser


class ParserRegistry:
    """解析器注册表 - 管理可用的 Parser 并按文件类型分发。"""

    def __init__(self):
        self._parsers: list[BaseParser] = []
        self._register_defaults()

    def _register_defaults(self) -> None:
        """注册默认的 Parser 实现。"""
        from conflux.parser.markdown import MarkdownParser
        self._parsers.append(MarkdownParser())

        # EPUB 和 PDF Parser 需要额外依赖，注册但可能无法使用
        from conflux.parser.epub import EpubParser
        self._parsers.append(EpubParser())

        from conflux.parser.pdf import PdfParser
        self._parsers.append(PdfParser())

    def register(self, parser: BaseParser) -> None:
        """注册自定义 Parser。"""
        self._parsers.insert(0, parser)  # 自定义优先

    def get_parser(self, path: Path) -> BaseParser:
        """根据文件路径获取合适的 Parser。

        Args:
            path: 文件路径

        Returns:
            匹配的 Parser 实例

        Raises:
            ParseError: 无法找到匹配的 Parser
        """
        for parser in self._parsers:
            if parser.can_parse(path):
                return parser

        ext = path.suffix.lower()
        supported = []
        for p in self._parsers:
            supported.extend(p.supported_extensions)
        raise ParseError(
            f"不支持的文件格式: {ext}\n"
            f"当前支持的格式: {', '.join(sorted(set(supported)))}"
        )

    def list_supported_formats(self) -> list[str]:
        """列出所有支持的文件扩展名。"""
        formats: list[str] = []
        for parser in self._parsers:
            formats.extend(parser.supported_extensions)
        return sorted(set(formats))


# 全局默认注册表
_default_registry: Optional[ParserRegistry] = None


def get_parser(path: Path) -> BaseParser:
    """便捷函数：从默认注册表获取 Parser。"""
    global _default_registry
    if _default_registry is None:
        _default_registry = ParserRegistry()
    return _default_registry.get_parser(path)
