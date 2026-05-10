"""Conflux - A living encyclopedia engine.

Compile books into AI-ready Skills and human-friendly Knowledge Graphs,
with automatic cross-source conflict detection.
"""

__version__ = "0.1.0"


class ConfluxError(Exception):
    """Base exception for all Conflux errors."""


class ParseError(ConfluxError):
    """Raised when document parsing fails."""


class CompileError(ConfluxError):
    """Raised when compilation (concept extraction, skill generation) fails."""


class NetworkError(ConfluxError):
    """Raised when knowledge networking fails."""


class ConflictDetectionError(ConfluxError):
    """Raised when conflict detection fails."""


class StorageError(ConfluxError):
    """Raised when storage operations fail."""


class LLMError(ConfluxError):
    """Raised when LLM calls fail."""
