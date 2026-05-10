"""Base parser - 解析器抽象基类。"""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

from conflux.models.document import Document, SourceFormat


class BaseParser(ABC):
    """所有 Parser 的抽象基类。

    子类需实现 parse() 方法，将特定格式文件解析为 Document IR。
    """

    # 子类应覆盖这些属性
    supported_extensions: list[str] = []
    source_format: SourceFormat = SourceFormat.TXT

    def can_parse(self, path: Path) -> bool:
        """判断此 Parser 是否能处理给定文件。"""
        return path.suffix.lower().lstrip(".") in self.supported_extensions

    @abstractmethod
    def parse(self, path: Path, **kwargs) -> Document:
        """将文件解析为 Document IR。

        Args:
            path: 输入文件路径
            **kwargs: 额外参数（如指定标题、作者等）

        Returns:
            统一的 Document 中间表示

        Raises:
            ParseError: 解析失败时抛出
        """
        ...

    def validate_file(self, path: Path) -> None:
        """校验文件是否可读取。"""
        if not path.exists():
            from conflux import ParseError
            raise ParseError(f"文件不存在: {path}")
        if not path.is_file():
            from conflux import ParseError
            raise ParseError(f"路径不是文件: {path}")
        if path.stat().st_size == 0:
            from conflux import ParseError
            raise ParseError(f"文件为空: {path}")
