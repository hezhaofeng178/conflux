"""Data models for Conflux.

All modules share these data contracts defined via Pydantic v2.
"""

from conflux.models.concept import (
    Concept,
    ConceptCluster,
    ConceptType,
    Relation,
    RelationType,
)
from conflux.models.conflict import (
    Claim,
    Conflict,
    ConflictAnalysis,
    ConflictSeverity,
    ConflictSide,
    ConflictType,
    Verdict,
    VerdictStatus,
)
from conflux.models.document import (
    Chapter,
    Document,
    DocumentMeta,
    Paragraph,
    Section,
    SourceFormat,
)
from conflux.models.graph import (
    CrossLink,
    Edge,
    EdgeType,
    KnowledgeGraph,
    Node,
    NodeType,
    Subnet,
    SubnetStats,
)
from conflux.models.skill import (
    Skill,
    SkillCaveat,
    SkillFact,
    SkillKnowledge,
    SkillProcedure,
    SkillSource,
)

__all__ = [
    # Document
    "Document",
    "DocumentMeta",
    "Chapter",
    "Section",
    "Paragraph",
    "SourceFormat",
    # Concept
    "Concept",
    "ConceptType",
    "ConceptCluster",
    "Relation",
    "RelationType",
    # Skill
    "Skill",
    "SkillSource",
    "SkillFact",
    "SkillProcedure",
    "SkillCaveat",
    "SkillKnowledge",
    # Conflict
    "Claim",
    "Conflict",
    "ConflictType",
    "ConflictSeverity",
    "ConflictSide",
    "ConflictAnalysis",
    "Verdict",
    "VerdictStatus",
    # Graph
    "Node",
    "NodeType",
    "Edge",
    "EdgeType",
    "Subnet",
    "SubnetStats",
    "CrossLink",
    "KnowledgeGraph",
]
