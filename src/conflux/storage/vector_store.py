"""VectorStore - 基于 ChromaDB 的向量检索存储。

用于概念/论断的语义相似度搜索，是冲突检测和组网的关键依赖。
"""

from __future__ import annotations

import uuid
from pathlib import Path
from typing import Any, Optional

import numpy as np
from pydantic import BaseModel

try:
    import chromadb
    from chromadb.config import Settings

    HAS_CHROMADB = True
except ImportError:
    HAS_CHROMADB = False


class SearchResult(BaseModel):
    """向量搜索结果。"""

    id: str
    content: str
    metadata: dict[str, Any] = {}
    distance: float = 0.0
    similarity: float = 1.0


class VectorStore:
    """向量存储 - 封装 ChromaDB 的语义检索能力。
    
    支持两种模式：
    1. 持久化模式（指定 persist_dir）：数据保存到磁盘
    2. 内存模式（不指定 persist_dir）：仅在内存中
    
    核心能力：
    - 存储带向量嵌入的文本片段
    - 语义相似度搜索
    - 按元数据过滤
    """

    def __init__(
        self,
        persist_dir: Optional[Path] = None,
        collection_name: str = "conflux_default",
    ) -> None:
        """初始化向量存储。
        
        Args:
            persist_dir: 持久化目录，None 则使用内存模式。
            collection_name: ChromaDB collection 名称。
        """
        if not HAS_CHROMADB:
            raise ImportError(
                "chromadb 未安装，请执行: pip install chromadb"
            )

        if persist_dir:
            persist_dir.mkdir(parents=True, exist_ok=True)
            self._client = chromadb.PersistentClient(
                path=str(persist_dir),
                settings=Settings(anonymized_telemetry=False),
            )
        else:
            self._client = chromadb.Client(
                settings=Settings(anonymized_telemetry=False),
            )

        self._collection_name = collection_name
        self._collection = self._client.get_or_create_collection(
            name=collection_name,
            metadata={"hnsw:space": "cosine"},
        )

    @property
    def count(self) -> int:
        """当前 collection 中的文档数量。"""
        return self._collection.count()

    def add(
        self,
        texts: list[str],
        ids: Optional[list[str]] = None,
        embeddings: Optional[list[list[float]]] = None,
        metadatas: Optional[list[dict[str, Any]]] = None,
    ) -> list[str]:
        """添加文本到向量存储。
        
        Args:
            texts: 文本列表。
            ids: 自定义 ID 列表，None 则自动生成。
            embeddings: 预计算的嵌入向量。None 则由 ChromaDB 自动生成。
            metadatas: 元数据列表。
            
        Returns:
            添加的文档 ID 列表。
        """
        if not texts:
            return []

        if ids is None:
            ids = [f"vec_{uuid.uuid4().hex[:12]}" for _ in texts]

        kwargs: dict[str, Any] = {
            "ids": ids,
            "documents": texts,
        }

        if embeddings is not None:
            kwargs["embeddings"] = embeddings
        if metadatas is not None:
            # ChromaDB 要求 metadata 值为基础类型
            kwargs["metadatas"] = [
                self._sanitize_metadata(m) for m in metadatas
            ]

        self._collection.add(**kwargs)
        return ids

    def upsert(
        self,
        texts: list[str],
        ids: list[str],
        embeddings: Optional[list[list[float]]] = None,
        metadatas: Optional[list[dict[str, Any]]] = None,
    ) -> None:
        """更新或插入文档。"""
        if not texts:
            return

        kwargs: dict[str, Any] = {
            "ids": ids,
            "documents": texts,
        }

        if embeddings is not None:
            kwargs["embeddings"] = embeddings
        if metadatas is not None:
            kwargs["metadatas"] = [
                self._sanitize_metadata(m) for m in metadatas
            ]

        self._collection.upsert(**kwargs)

    def search(
        self,
        query: str,
        n_results: int = 10,
        where: Optional[dict[str, Any]] = None,
        query_embedding: Optional[list[float]] = None,
    ) -> list[SearchResult]:
        """语义搜索。
        
        Args:
            query: 搜索文本。
            n_results: 返回结果数量。
            where: 元数据过滤条件。
            query_embedding: 用预计算的嵌入进行搜索。
            
        Returns:
            搜索结果列表，按相似度降序排列。
        """
        kwargs: dict[str, Any] = {
            "n_results": min(n_results, self.count) if self.count > 0 else n_results,
        }

        if query_embedding is not None:
            kwargs["query_embeddings"] = [query_embedding]
        else:
            kwargs["query_texts"] = [query]

        if where:
            kwargs["where"] = where

        if self.count == 0:
            return []

        results = self._collection.query(**kwargs)

        search_results: list[SearchResult] = []
        if results["ids"] and results["ids"][0]:
            for i, doc_id in enumerate(results["ids"][0]):
                distance = results["distances"][0][i] if results["distances"] else 0.0
                # cosine distance -> similarity
                similarity = 1.0 - distance

                search_results.append(
                    SearchResult(
                        id=doc_id,
                        content=results["documents"][0][i] if results["documents"] else "",
                        metadata=results["metadatas"][0][i] if results["metadatas"] else {},
                        distance=distance,
                        similarity=similarity,
                    )
                )

        return search_results

    def search_by_embedding(
        self,
        embedding: list[float],
        n_results: int = 10,
        where: Optional[dict[str, Any]] = None,
    ) -> list[SearchResult]:
        """使用嵌入向量直接搜索。"""
        return self.search(
            query="",
            n_results=n_results,
            where=where,
            query_embedding=embedding,
        )

    def get(self, ids: list[str]) -> list[dict[str, Any]]:
        """按 ID 获取文档。"""
        results = self._collection.get(ids=ids)
        docs: list[dict[str, Any]] = []
        if results["ids"]:
            for i, doc_id in enumerate(results["ids"]):
                docs.append({
                    "id": doc_id,
                    "content": results["documents"][i] if results["documents"] else "",
                    "metadata": results["metadatas"][i] if results["metadatas"] else {},
                })
        return docs

    def delete(self, ids: list[str]) -> None:
        """按 ID 删除文档。"""
        if ids:
            self._collection.delete(ids=ids)

    def clear(self) -> None:
        """清空当前 collection。"""
        self._client.delete_collection(self._collection_name)
        self._collection = self._client.get_or_create_collection(
            name=self._collection_name,
            metadata={"hnsw:space": "cosine"},
        )

    def get_or_create_collection(self, name: str) -> "VectorStore":
        """获取或创建一个新的命名 collection（返回新 VectorStore 实例）。
        
        用于为不同用途创建独立的向量空间：
        - "concepts": 概念嵌入
        - "claims": 论断嵌入
        - "sections": 章节嵌入
        """
        new_store = VectorStore.__new__(VectorStore)
        new_store._client = self._client
        new_store._collection_name = name
        new_store._collection = self._client.get_or_create_collection(
            name=name,
            metadata={"hnsw:space": "cosine"},
        )
        return new_store

    @staticmethod
    def _sanitize_metadata(metadata: dict[str, Any]) -> dict[str, Any]:
        """清理元数据使其兼容 ChromaDB（值只能是 str/int/float/bool）。"""
        sanitized: dict[str, Any] = {}
        for key, value in metadata.items():
            if value is None:
                continue
            if isinstance(value, (str, int, float, bool)):
                sanitized[key] = value
            elif isinstance(value, (list, tuple)):
                # 列表转为逗号分隔字符串
                sanitized[key] = ",".join(str(v) for v in value)
            else:
                sanitized[key] = str(value)
        return sanitized

    @staticmethod
    def cosine_similarity(vec_a: list[float], vec_b: list[float]) -> float:
        """计算两个向量的余弦相似度。"""
        a = np.array(vec_a)
        b = np.array(vec_b)
        norm_a = np.linalg.norm(a)
        norm_b = np.linalg.norm(b)
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return float(np.dot(a, b) / (norm_a * norm_b))
