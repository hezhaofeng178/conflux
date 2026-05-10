"""Search command - 语义搜索。"""

from typing import Optional

import typer
from rich.console import Console
from rich.table import Table

search_app = typer.Typer()
console = Console()


@search_app.callback(invoke_without_command=True)
def search(
    query: str = typer.Argument(..., help="搜索关键词或自然语言描述"),
    scope: str = typer.Option("all", "--scope", "-s", help="搜索范围 (all|concepts|skills|documents)"),
    limit: int = typer.Option(10, "--limit", "-l", help="返回结果数量"),
) -> None:
    """在知识库中进行语义搜索。"""
    from conflux.storage.file_store import FileStore

    store = FileStore()

    console.print(f"[blue]🔍 搜索: [bold]{query}[/bold][/blue]")
    console.print(f"   范围: {scope}  |  上限: {limit}\n")

    results_found = False

    if scope in ("all", "concepts"):
        # 搜索概念
        all_concepts = store.load_all_concepts()
        matched_concepts = _fuzzy_match_concepts(query, all_concepts, limit)

        if matched_concepts:
            results_found = True
            table = Table(title="💡 匹配的概念")
            table.add_column("名称", style="bold")
            table.add_column("类型", width=10)
            table.add_column("来源")
            table.add_column("定义")

            for concept in matched_concepts:
                table.add_row(
                    concept.name,
                    concept.concept_type.value,
                    concept.source_book or "-",
                    (concept.definition or "")[:60] + "..." if concept.definition and len(concept.definition) > 60 else (concept.definition or "-"),
                )
            console.print(table)
            console.print()

    if scope in ("all", "documents"):
        # 搜索文档
        documents = store.load_all_documents()
        matched_docs = _fuzzy_match_documents(query, documents, limit)

        if matched_docs:
            results_found = True
            table = Table(title="📚 匹配的文档")
            table.add_column("标题", style="bold")
            table.add_column("作者")
            table.add_column("章节数", justify="center")

            for doc in matched_docs:
                table.add_row(
                    doc.meta.title,
                    doc.meta.author or "-",
                    str(doc.total_chapters),
                )
            console.print(table)
            console.print()

    if not results_found:
        console.print("[yellow]未找到匹配的结果。[/yellow]")
        console.print("[dim]提示: 确保已导入文档并执行了 conflux build[/dim]")


def _fuzzy_match_concepts(query: str, concepts: list, limit: int) -> list:
    """简单模糊匹配概念（不依赖向量搜索）。"""
    query_lower = query.lower()
    scored = []

    for concept in concepts:
        score = 0
        # 名称匹配（最高优先级）
        if query_lower in concept.name.lower():
            score += 10
        if concept.name.lower() == query_lower:
            score += 20

        # 别名匹配
        for alias in concept.aliases:
            if query_lower in alias.lower():
                score += 8

        # 定义匹配
        if concept.definition and query_lower in concept.definition.lower():
            score += 3

        if score > 0:
            scored.append((score, concept))

    scored.sort(key=lambda x: x[0], reverse=True)
    return [c for _, c in scored[:limit]]


def _fuzzy_match_documents(query: str, documents: list, limit: int) -> list:
    """简单模糊匹配文档。"""
    query_lower = query.lower()
    scored = []

    for doc in documents:
        score = 0
        if query_lower in doc.meta.title.lower():
            score += 10
        if doc.meta.author and query_lower in doc.meta.author.lower():
            score += 5
        for tag in doc.meta.tags:
            if query_lower in tag.lower():
                score += 3

        if score > 0:
            scored.append((score, doc))

    scored.sort(key=lambda x: x[0], reverse=True)
    return [d for _, d in scored[:limit]]
