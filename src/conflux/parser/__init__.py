"""Parser layer - 解析层。

将各种格式的输入源转化为统一的 Document IR。
"""

from pathlib import Path
from typing import Optional

from conflux.parser.base import BaseParser
from conflux.parser.markdown import MarkdownParser
from conflux.parser.registry import ParserRegistry, get_parser

__all__ = [
    "BaseParser",
    "MarkdownParser",
    "ParserRegistry",
    "get_parser",
    "parse_document",
]


def parse_document(file_path: Path, format: Optional[str] = None):
    """便捷函数 - 解析文档并返回 Document IR。
    
    Args:
        file_path: 文件路径。
        format: 强制指定格式（auto 则自动检测）。
        
    Returns:
        Document 对象。
    """
    path = Path(file_path) if not isinstance(file_path, Path) else file_path
    parser = get_parser(path)
    return parser.parse(path)
