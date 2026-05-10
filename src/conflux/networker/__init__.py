"""Networker module - 动态组网层。

负责知识概念间的连接建立：
- SimilarityEngine: 语义相似度计算
- SubnetManager: 知识子网管理
- NodeMerger: 概念节点合并
- CrossLinker: 跨书/跨网连接建立
"""

from conflux.networker.cross_linker import CrossLinker, IntegrationResult
from conflux.networker.merger import NodeMerger, MergeResult
from conflux.networker.similarity import SimilarityEngine
from conflux.networker.subnet import SubnetManager

__all__ = [
    "SimilarityEngine",
    "SubnetManager",
    "NodeMerger",
    "MergeResult",
    "CrossLinker",
    "IntegrationResult",
]
