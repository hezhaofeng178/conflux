"""Conflict module - 冲突检测与裁决管理。

完整的冲突检测 Pipeline：
1. ClaimExtractor: 从文档中提取论断
2. StanceDetector: 分析论断立场方向
3. ConflictPairer: 配对产生冲突节点
4. SeverityScorer: 评估冲突严重程度
5. VerdictManager: 管理人类裁决
"""

from conflux.conflict.claim_extractor import ClaimExtractor
from conflux.conflict.conflict_pairer import ConflictPairer
from conflux.conflict.severity_scorer import SeverityScorer
from conflux.conflict.stance_detector import StanceDetector, StanceInfo, ConflictJudgment
from conflux.conflict.verdict import VerdictManager

__all__ = [
    "ClaimExtractor",
    "StanceDetector",
    "StanceInfo",
    "ConflictJudgment",
    "ConflictPairer",
    "SeverityScorer",
    "VerdictManager",
]
