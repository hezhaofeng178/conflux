"""FileStore - 基于文件系统的持久化存储。

负责管理所有 JSON/YAML 格式的数据文件：
- IR 文档（解析后的中间表示）
- Skill 输出文件（YAML）
- Conflict 冲突记录
- 元数据索引
"""

from __future__ import annotations

import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import Optional

import yaml

from conflux.models.concept import Concept, Relation
from conflux.models.conflict import Conflict
from conflux.models.document import Document
from conflux.models.skill import Skill


class FileStore:
    """文件系统存储 - 管理所有持久化 JSON/YAML 数据。
    
    目录结构：
        data/
        ├── documents/          # IR 文档 (JSON)
        │   ├── {doc_id}.json
        │   └── index.json      # 文档索引
        ├── concepts/           # 概念数据 (JSON)
        │   ├── {book_id}/
        │   │   └── concepts.json
        │   └── all_concepts.json
        ├── relations/          # 关系数据
        │   └── relations.json
        ├── conflicts/          # 冲突记录
        │   ├── {conflict_id}.json
        │   └── index.json
        └── cache/              # 缓存
            └── hashes.json
        output/
        ├── skills/             # Skill YAML 输出
        │   └── {book}/
        │       └── {skill_name}.yaml
        └── vault/              # Obsidian Vault
            └── {node}.md
    """

    def __init__(self, base_path: Optional[Path] = None) -> None:
        """初始化文件存储。
        
        Args:
            base_path: 项目根目录（含 data/ 和 output/），默认为当前目录。
        """
        self.base_path = Path(base_path) if base_path else Path.cwd()
        self.data_dir = self.base_path / "data"
        self.output_dir = self.base_path / "output"

        # 子目录
        self.documents_dir = self.data_dir / "documents"
        self.concepts_dir = self.data_dir / "concepts"
        self.relations_dir = self.data_dir / "relations"
        self.conflicts_dir = self.data_dir / "conflicts"
        self.cache_dir = self.data_dir / "cache"
        self.skills_dir = self.output_dir / "skills"
        self.vault_dir = self.output_dir / "vault"

    def ensure_dirs(self) -> None:
        """确保所有必要的目录存在。"""
        for d in [
            self.documents_dir,
            self.concepts_dir,
            self.relations_dir,
            self.conflicts_dir,
            self.cache_dir,
            self.skills_dir,
            self.vault_dir,
        ]:
            d.mkdir(parents=True, exist_ok=True)

    # ─── IR Document CRUD ─────────────────────────────────────────

    def save_ir(self, document: Document) -> Path:
        """保存 IR 文档到文件系统。
        
        Args:
            document: 解析后的 Document 对象。
            
        Returns:
            保存的文件路径。
        """
        self.ensure_dirs()
        file_path = self.documents_dir / f"{document.id}.json"
        data = document.model_dump(mode="json")
        file_path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        # 更新索引
        self._update_document_index(document)
        return file_path

    def load_ir(self, document_id: str) -> Optional[Document]:
        """加载单个 IR 文档。
        
        Args:
            document_id: 文档 ID。
            
        Returns:
            Document 对象，不存在则返回 None。
        """
        file_path = self.documents_dir / f"{document_id}.json"
        if not file_path.exists():
            return None
        data = json.loads(file_path.read_text(encoding="utf-8"))
        return Document.model_validate(data)

    def load_all_documents(self) -> list[Document]:
        """加载所有 IR 文档。"""
        documents: list[Document] = []
        if not self.documents_dir.exists():
            return documents

        for file_path in self.documents_dir.glob("*.json"):
            if file_path.name == "index.json":
                continue
            try:
                data = json.loads(file_path.read_text(encoding="utf-8"))
                documents.append(Document.model_validate(data))
            except Exception:
                continue
        return documents

    def delete_ir(self, document_id: str) -> bool:
        """删除 IR 文档。"""
        file_path = self.documents_dir / f"{document_id}.json"
        if file_path.exists():
            file_path.unlink()
            self._rebuild_document_index()
            return True
        return False

    def _update_document_index(self, document: Document) -> None:
        """更新文档索引。"""
        index_path = self.documents_dir / "index.json"
        index: dict = {}
        if index_path.exists():
            index = json.loads(index_path.read_text(encoding="utf-8"))

        index[document.id] = {
            "title": document.meta.title,
            "author": document.meta.author,
            "format": document.meta.source_format.value,
            "import_time": document.meta.import_time.isoformat(),
            "total_chapters": document.total_chapters,
            "total_words": document.total_words,
        }
        index_path.write_text(
            json.dumps(index, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def _rebuild_document_index(self) -> None:
        """重建文档索引。"""
        index_path = self.documents_dir / "index.json"
        index: dict = {}
        for doc in self.load_all_documents():
            index[doc.id] = {
                "title": doc.meta.title,
                "author": doc.meta.author,
                "format": doc.meta.source_format.value,
                "import_time": doc.meta.import_time.isoformat(),
                "total_chapters": doc.total_chapters,
                "total_words": doc.total_words,
            }
        index_path.write_text(
            json.dumps(index, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    # ─── Concept CRUD ─────────────────────────────────────────────

    def save_concepts(
        self,
        concepts: list[Concept],
        document_id: str,
    ) -> Path:
        """保存某本书的概念列表。
        
        Args:
            concepts: 提取的概念列表。
            document_id: 来源文档 ID。
            
        Returns:
            保存的文件路径。
        """
        self.ensure_dirs()
        book_dir = self.concepts_dir / document_id
        book_dir.mkdir(parents=True, exist_ok=True)

        file_path = book_dir / "concepts.json"
        data = [c.model_dump(mode="json") for c in concepts]
        file_path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        # 更新全局概念索引
        self._update_global_concepts()
        return file_path

    def load_concepts(self, document_id: str) -> list[Concept]:
        """加载某本书的概念列表。"""
        file_path = self.concepts_dir / document_id / "concepts.json"
        if not file_path.exists():
            return []
        data = json.loads(file_path.read_text(encoding="utf-8"))
        return [Concept.model_validate(item) for item in data]

    def load_all_concepts(self) -> list[Concept]:
        """加载所有文档的概念。"""
        all_concepts: list[Concept] = []
        if not self.concepts_dir.exists():
            return all_concepts

        for book_dir in self.concepts_dir.iterdir():
            if book_dir.is_dir():
                concepts_file = book_dir / "concepts.json"
                if concepts_file.exists():
                    data = json.loads(concepts_file.read_text(encoding="utf-8"))
                    all_concepts.extend(
                        Concept.model_validate(item) for item in data
                    )
        return all_concepts

    def _update_global_concepts(self) -> None:
        """更新全局概念索引（合并所有书的概念）。"""
        all_concepts = self.load_all_concepts()
        index_path = self.concepts_dir / "all_concepts.json"
        data = [
            {"id": c.id, "name": c.name, "type": c.concept_type.value, "source": c.source_book}
            for c in all_concepts
        ]
        index_path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    # ─── Relations CRUD ───────────────────────────────────────────

    def save_relations(self, relations: list[Relation]) -> Path:
        """保存关系列表（追加模式）。"""
        self.ensure_dirs()
        file_path = self.relations_dir / "relations.json"

        existing: list[dict] = []
        if file_path.exists():
            existing = json.loads(file_path.read_text(encoding="utf-8"))

        # 追加新关系（去重）
        existing_ids = {r["id"] for r in existing}
        for rel in relations:
            if rel.id not in existing_ids:
                existing.append(rel.model_dump(mode="json"))

        file_path.write_text(
            json.dumps(existing, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return file_path

    def load_relations(self) -> list[Relation]:
        """加载所有关系。"""
        file_path = self.relations_dir / "relations.json"
        if not file_path.exists():
            return []
        data = json.loads(file_path.read_text(encoding="utf-8"))
        return [Relation.model_validate(item) for item in data]

    # ─── Conflict CRUD ────────────────────────────────────────────

    def save_conflict(self, conflict: Conflict) -> Path:
        """保存单个冲突记录。"""
        self.ensure_dirs()
        file_path = self.conflicts_dir / f"{conflict.id}.json"
        data = conflict.model_dump(mode="json")
        file_path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        self._update_conflict_index()
        return file_path

    def save_conflicts(self, conflicts: list[Conflict]) -> None:
        """批量保存冲突记录。"""
        for conflict in conflicts:
            self.save_conflict(conflict)

    def load_conflict(self, conflict_id: str) -> Optional[Conflict]:
        """加载单个冲突记录。"""
        file_path = self.conflicts_dir / f"{conflict_id}.json"
        if not file_path.exists():
            return None
        data = json.loads(file_path.read_text(encoding="utf-8"))
        return Conflict.model_validate(data)

    def load_conflicts(self) -> list[Conflict]:
        """加载所有冲突记录。"""
        conflicts: list[Conflict] = []
        if not self.conflicts_dir.exists():
            return conflicts

        for file_path in self.conflicts_dir.glob("*.json"):
            if file_path.name == "index.json":
                continue
            try:
                data = json.loads(file_path.read_text(encoding="utf-8"))
                conflicts.append(Conflict.model_validate(data))
            except Exception:
                continue
        return conflicts

    def _update_conflict_index(self) -> None:
        """更新冲突索引。"""
        index_path = self.conflicts_dir / "index.json"
        conflicts = self.load_conflicts()
        index = {
            c.id: {
                "title": c.title,
                "type": c.conflict_type.value,
                "severity": c.severity.value,
                "status": c.verdict.status.value,
                "sides_count": len(c.sides),
            }
            for c in conflicts
        }
        index_path.write_text(
            json.dumps(index, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    # ─── Skill Output ─────────────────────────────────────────────

    def save_skill(self, skill: Skill, book_name: str) -> Path:
        """保存 Skill 为 YAML 文件。
        
        Args:
            skill: Skill 对象。
            book_name: 所属书籍名称（用作子目录）。
            
        Returns:
            保存的文件路径。
        """
        self.ensure_dirs()
        # 清理文件名
        safe_name = self._safe_filename(skill.name)
        safe_book = self._safe_filename(book_name)

        book_dir = self.skills_dir / safe_book
        book_dir.mkdir(parents=True, exist_ok=True)

        file_path = book_dir / f"{safe_name}.yaml"
        yaml_data = skill.to_yaml_dict()
        file_path.write_text(
            yaml.dump(yaml_data, allow_unicode=True, default_flow_style=False, sort_keys=False),
            encoding="utf-8",
        )
        return file_path

    def save_skills(self, skills: list[Skill], book_name: str) -> list[Path]:
        """批量保存 Skills。"""
        return [self.save_skill(skill, book_name) for skill in skills]

    # ─── Vault Output ─────────────────────────────────────────────

    def save_vault_node(self, filename: str, content: str, subdir: Optional[str] = None) -> Path:
        """保存 Obsidian Vault 节点（Markdown 文件）。
        
        Args:
            filename: 文件名（不含 .md 后缀）。
            content: Markdown 内容。
            subdir: 可选子目录。
            
        Returns:
            保存的文件路径。
        """
        self.ensure_dirs()
        safe_name = self._safe_filename(filename)

        if subdir:
            target_dir = self.vault_dir / self._safe_filename(subdir)
            target_dir.mkdir(parents=True, exist_ok=True)
        else:
            target_dir = self.vault_dir

        file_path = target_dir / f"{safe_name}.md"
        file_path.write_text(content, encoding="utf-8")
        return file_path

    # ─── Cache 管理 ───────────────────────────────────────────────

    def get_hash_cache(self) -> dict[str, str]:
        """获取文件 hash 缓存（用于增量处理判断）。"""
        cache_file = self.cache_dir / "hashes.json"
        if not cache_file.exists():
            return {}
        return json.loads(cache_file.read_text(encoding="utf-8"))

    def update_hash_cache(self, file_path: str, file_hash: str) -> None:
        """更新文件 hash 缓存。"""
        self.ensure_dirs()
        cache_file = self.cache_dir / "hashes.json"
        cache = self.get_hash_cache()
        cache[file_path] = file_hash
        cache_file.write_text(
            json.dumps(cache, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def is_file_changed(self, file_path: str, current_hash: str) -> bool:
        """检查文件是否已变更（用于增量构建）。"""
        cache = self.get_hash_cache()
        cached_hash = cache.get(file_path)
        return cached_hash != current_hash

    # ─── 清理 ────────────────────────────────────────────────────

    def clean_output(self) -> None:
        """清理所有输出文件（保留数据）。"""
        if self.skills_dir.exists():
            shutil.rmtree(self.skills_dir)
        if self.vault_dir.exists():
            shutil.rmtree(self.vault_dir)
        self.ensure_dirs()

    def clean_all(self) -> None:
        """清理所有数据和输出。"""
        if self.data_dir.exists():
            shutil.rmtree(self.data_dir)
        self.clean_output()
        self.ensure_dirs()

    # ─── Stats ────────────────────────────────────────────────────

    def get_stats(self) -> dict:
        """获取存储统计信息。"""
        doc_count = len(list(self.documents_dir.glob("*.json"))) - 1 if self.documents_dir.exists() else 0
        concept_count = len(self.load_all_concepts())
        relation_count = len(self.load_relations())
        conflict_count = len(self.load_conflicts())
        skill_count = len(list(self.skills_dir.glob("**/*.yaml"))) if self.skills_dir.exists() else 0
        vault_count = len(list(self.vault_dir.glob("**/*.md"))) if self.vault_dir.exists() else 0

        return {
            "documents": max(0, doc_count),
            "concepts": concept_count,
            "relations": relation_count,
            "conflicts": conflict_count,
            "skills": skill_count,
            "vault_nodes": vault_count,
        }

    # ─── Helpers ──────────────────────────────────────────────────

    @staticmethod
    def _safe_filename(name: str) -> str:
        """将名称转换为安全的文件名。"""
        # 替换不安全字符
        unsafe_chars = '<>:"/\\|?*'
        result = name
        for ch in unsafe_chars:
            result = result.replace(ch, "_")
        # 截断过长的名称
        if len(result) > 100:
            result = result[:100]
        return result.strip().strip(".")
