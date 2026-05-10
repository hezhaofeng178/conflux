"""Graph Builder - 将概念和关系生成为 Obsidian Vault 文件。

输出 Markdown 文件，可直接拖入 Obsidian 使用，支持 wikilink 和 frontmatter。
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import structlog
from jinja2 import Template

from conflux.models.concept import Concept, Relation
from conflux.models.conflict import Conflict
from conflux.models.document import Document

logger = structlog.get_logger(__name__)

# ====== Jinja2 模板 ======

CONCEPT_NODE_TEMPLATE = Template("""\
---
aliases: {{ aliases }}
tags: {{ tags }}
conflux_id: {{ concept.id }}
type: {{ concept.concept_type.value }}
domain: {{ concept.domain or "未分类" }}
sources: {{ sources }}
---

# {{ concept.name }}

## 定义
{{ concept.definition or "暂无定义。" }}

{% if concept.description %}
## 详细描述
{{ concept.description }}
{% endif %}

## 来源
- 📖 {{ concept.source_book }}{% if concept.source_chapter %} · {{ concept.source_chapter }}{% endif %}

{% if related_by_type %}
## 关联概念
{% for rel_type, targets in related_by_type.items() %}
### {{ rel_type }}
{% for target_name, description in targets %}
- [[{{ target_name }}]]{% if description %} — {{ description }}{% endif %}

{% endfor %}
{% endfor %}
{% endif %}

{% if conflicts %}
## ⚠️ 冲突标注
{% for conflict in conflicts %}
- [[{{ conflict.id }}]] — {{ conflict.title }}
{% endfor %}
{% endif %}
""")

BOOK_INDEX_TEMPLATE = Template("""\
---
tags: [book, index]
conflux_type: book_index
---

# 📖 {{ document.meta.title }}

## 元信息
- **作者**: {{ document.meta.author or "未知" }}
- **格式**: {{ document.meta.source_format.value }}
- **导入时间**: {{ document.meta.import_time.strftime("%Y-%m-%d") }}
- **章节数**: {{ document.total_chapters }}
- **字数**: ~{{ document.total_words }}

## 章节目录
{% for chapter in document.structure %}
### {{ chapter.title }}
{% for section in chapter.sections %}
{% if section.title %}- {{ section.title }}
{% endif %}
{% endfor %}
{% for child in chapter.children %}
#### {{ child.title }}
{% for section in child.sections %}
{% if section.title %}- {{ section.title }}
{% endif %}
{% endfor %}
{% endfor %}

{% endfor %}

## 提取的概念
{% for concept in concepts %}
- [[{{ concept.name }}]]
{% endfor %}
""")

CONFLICT_NODE_TEMPLATE = Template("""\
---
tags: [conflict, {{ conflict.conflict_type.value }}]
conflux_id: {{ conflict.id }}
severity: {{ conflict.severity.value }}
status: {{ conflict.verdict.status.value }}
---

# ⚠️ {{ conflict.title }}

## 冲突类型
`{{ conflict.conflict_type.value }}` | 严重度: **{{ conflict.severity.value }}**

## 冲突双方
{% for side in conflict.sides %}
### 📕 {{ side.source_book }}
> {{ side.position }}
{% if side.context %}

*上下文: {{ side.context }}*
{% endif %}

{% endfor %}

{% if conflict.analysis.possible_reasons %}
## 分析
### 可能的原因
{% for reason in conflict.analysis.possible_reasons %}
- {{ reason }}
{% endfor %}
{% endif %}

{% if conflict.analysis.suggested_resolution %}
### 建议解决方向
{{ conflict.analysis.suggested_resolution }}
{% endif %}

## 裁决状态
- **状态**: {{ conflict.verdict.status.value }}
{% if conflict.verdict.decision %}
- **裁决**: {{ conflict.verdict.decision }}
- **裁决时间**: {{ conflict.verdict.decided_at }}
{% endif %}
{% if conflict.verdict.notes %}
- **备注**: {{ conflict.verdict.notes }}
{% endif %}
""")


class GraphBuilder:
    """Obsidian Vault 生成器。

    将概念、关系和冲突转化为 Obsidian 可用的 Markdown 文件网络。
    """

    def __init__(self):
        pass

    def build_vault(
        self,
        document: Document,
        concepts: list[Concept],
        relations: list[Relation],
        conflicts: list[Conflict] | None = None,
        output_dir: Path | None = None,
    ) -> Path:
        """生成完整的 Obsidian Vault。

        Args:
            document: 源文档
            concepts: 概念列表
            relations: 关系列表
            conflicts: 冲突列表（可选）
            output_dir: 输出根目录

        Returns:
            Vault 根目录路径
        """
        if output_dir is None:
            output_dir = Path("output/vault")

        vault_dir = output_dir
        vault_dir.mkdir(parents=True, exist_ok=True)

        # 创建目录结构
        books_dir = vault_dir / "Books"
        concepts_dir = vault_dir / "Concepts"
        conflicts_dir = vault_dir / "Conflicts"
        books_dir.mkdir(exist_ok=True)
        concepts_dir.mkdir(exist_ok=True)
        conflicts_dir.mkdir(exist_ok=True)

        # 1. 生成书籍索引
        self._write_book_index(document, concepts, books_dir)

        # 2. 生成概念节点
        written_concepts = self._write_concept_nodes(
            concepts, relations, conflicts or [], concepts_dir
        )

        # 3. 生成冲突节点
        if conflicts:
            self._write_conflict_nodes(conflicts, conflicts_dir)

        logger.info(
            "vault_built",
            dir=str(vault_dir),
            concepts=written_concepts,
            conflicts=len(conflicts) if conflicts else 0,
        )

        return vault_dir

    def _write_book_index(
        self, document: Document, concepts: list[Concept], books_dir: Path
    ) -> None:
        """生成书籍索引 Markdown。"""
        book_dir = books_dir / self._safe_dirname(document.meta.title)
        book_dir.mkdir(parents=True, exist_ok=True)

        content = BOOK_INDEX_TEMPLATE.render(
            document=document,
            concepts=concepts,
        )

        index_path = book_dir / "_INDEX.md"
        index_path.write_text(content, encoding="utf-8")

    def _write_concept_nodes(
        self,
        concepts: list[Concept],
        relations: list[Relation],
        conflicts: list[Conflict],
        concepts_dir: Path,
    ) -> int:
        """生成概念节点 Markdown 文件。"""
        # 构建关系索引
        concept_id_to_name = {c.id: c.name for c in concepts}
        relation_index = self._build_relation_index(relations, concept_id_to_name)

        # 构建冲突索引
        conflict_index: dict[str, list[Conflict]] = {}
        for conflict in conflicts:
            for cid in conflict.related_concepts:
                conflict_index.setdefault(cid, []).append(conflict)

        count = 0
        for concept in concepts:
            # 获取此概念的关系（按类型分组）
            related_by_type = relation_index.get(concept.id, {})

            # 获取此概念的冲突
            concept_conflicts = conflict_index.get(concept.id, [])

            content = CONCEPT_NODE_TEMPLATE.render(
                concept=concept,
                aliases=concept.aliases,
                tags=concept.tags or [concept.domain or "未分类"],
                sources=[concept.source_book],
                related_by_type=related_by_type,
                conflicts=concept_conflicts,
            )

            file_path = concepts_dir / f"{concept.name}.md"
            file_path.write_text(content, encoding="utf-8")
            count += 1

        return count

    def _write_conflict_nodes(
        self, conflicts: list[Conflict], conflicts_dir: Path
    ) -> None:
        """生成冲突节点 Markdown 文件。"""
        # 生成未裁决冲突汇总
        unresolved = [c for c in conflicts if not c.is_resolved]
        if unresolved:
            summary_lines = [
                "---\ntags: [conflict, index]\n---\n",
                "# ⚠️ 未裁决冲突\n",
                f"共 {len(unresolved)} 个冲突待裁决。\n",
            ]
            for conflict in unresolved:
                summary_lines.append(
                    f"- [[{conflict.id}]] | `{conflict.severity.value}` | {conflict.title}"
                )
            summary_path = conflicts_dir / "_UNRESOLVED.md"
            summary_path.write_text("\n".join(summary_lines), encoding="utf-8")

        # 生成每个冲突的详情页
        for conflict in conflicts:
            content = CONFLICT_NODE_TEMPLATE.render(conflict=conflict)
            file_path = conflicts_dir / f"{conflict.id}.md"
            file_path.write_text(content, encoding="utf-8")

    def _build_relation_index(
        self, relations: list[Relation], concept_id_to_name: dict[str, str]
    ) -> dict[str, dict[str, list[tuple[str, Optional[str]]]]]:
        """构建 concept_id → {relation_type: [(target_name, description)]} 索引。"""
        index: dict[str, dict[str, list[tuple[str, Optional[str]]]]] = {}

        # 关系类型的可读标签
        type_labels = {
            "is_a": "上位概念",
            "part_of": "所属",
            "contains": "组成",
            "causes": "导致",
            "caused_by": "由...引起",
            "regulates": "调节",
            "depends_on": "依赖",
            "contrasts": "对比",
            "similar_to": "相似",
            "related_to": "相关",
            "precedes": "先于",
            "follows": "后于",
            "applied_in": "应用于",
            "example_of": "实例",
        }

        for rel in relations:
            source_name = concept_id_to_name.get(rel.source_id)
            target_name = concept_id_to_name.get(rel.target_id)
            if not source_name or not target_name:
                continue

            label = type_labels.get(rel.relation_type.value, rel.relation_type.value)

            # source → target
            index.setdefault(rel.source_id, {}).setdefault(label, []).append(
                (target_name, rel.description)
            )
            # target ← source (反向)
            reverse_label = f"被{label}" if not label.startswith("被") else label[1:]
            index.setdefault(rel.target_id, {}).setdefault(reverse_label, []).append(
                (source_name, rel.description)
            )

        return index

    def _safe_dirname(self, name: str) -> str:
        """安全目录名。"""
        import re
        safe = re.sub(r'[<>:"/\\|?*]', "_", name)
        return safe[:80].strip() or "unnamed"
