"""Export command - 导出数据。"""

from pathlib import Path
from typing import Optional

import typer
from rich.console import Console

export_app = typer.Typer()
console = Console()


@export_app.command("graph")
def export_graph(
    output: str = typer.Option("./export/graph.graphml", "--output", "-o", help="输出路径"),
    format: str = typer.Option("graphml", "--format", "-f", help="导出格式 (graphml|json)"),
) -> None:
    """导出知识图谱。"""
    from conflux.storage.graph_store import GraphStore

    graph_store = GraphStore()
    output_path = Path(output).resolve()

    if graph_store.node_count == 0:
        console.print("[yellow]⚠️  图谱为空，请先执行 conflux build[/yellow]")
        return

    output_path.parent.mkdir(parents=True, exist_ok=True)

    if format == "graphml":
        graph_store.export_to_graphml(output_path)
    elif format == "json":
        graph_store.save()
        import shutil
        data_path = graph_store._persist_path
        if data_path.exists():
            shutil.copy(data_path, output_path)
    else:
        console.print(f"[red]❌ 不支持的格式: {format}[/red]")
        raise typer.Exit(1)

    stats = graph_store.get_stats()
    console.print(f"[green]✅ 图谱已导出到: {output_path}[/green]")
    console.print(f"   节点: {stats['nodes']} | 边: {stats['edges']}")


@export_app.command("skills")
def export_skills(
    output: str = typer.Option("./export/skills", "--output", "-o", help="输出目录"),
    format: str = typer.Option("yaml", "--format", "-f", help="格式 (yaml|json)"),
) -> None:
    """导出所有 Skill 文件。"""
    import json
    import shutil

    from conflux.storage.file_store import FileStore

    store = FileStore()
    output_path = Path(output).resolve()
    output_path.mkdir(parents=True, exist_ok=True)

    if store.skills_dir.exists():
        skill_files = list(store.skills_dir.glob("**/*.yaml"))
        if not skill_files:
            console.print("[yellow]⚠️  没有 Skill 文件，请先执行 conflux build[/yellow]")
            return

        # 复制所有 skill 文件
        for src_file in skill_files:
            rel_path = src_file.relative_to(store.skills_dir)
            dst_file = output_path / rel_path
            dst_file.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src_file, dst_file)

        console.print(f"[green]✅ 已导出 {len(skill_files)} 个 Skill 文件到: {output_path}[/green]")
    else:
        console.print("[yellow]⚠️  Skills 目录不存在，请先执行 conflux build[/yellow]")


@export_app.command("vault")
def export_vault(
    output: str = typer.Option("./export/vault", "--output", "-o", help="输出目录"),
) -> None:
    """导出 Obsidian Vault。"""
    import shutil

    from conflux.storage.file_store import FileStore

    store = FileStore()
    output_path = Path(output).resolve()

    if store.vault_dir.exists():
        vault_files = list(store.vault_dir.glob("**/*.md"))
        if not vault_files:
            console.print("[yellow]⚠️  Vault 为空，请先执行 conflux build[/yellow]")
            return

        # 复制整个 vault 目录
        if output_path.exists():
            shutil.rmtree(output_path)
        shutil.copytree(store.vault_dir, output_path)

        console.print(f"[green]✅ 已导出 Vault ({len(vault_files)} 个节点) 到: {output_path}[/green]")
        console.print("   可直接用 Obsidian 打开此目录作为 Vault")
    else:
        console.print("[yellow]⚠️  Vault 目录不存在，请先执行 conflux build[/yellow]")


@export_app.command("stats")
def export_stats(
    output: Optional[str] = typer.Option(None, "--output", "-o", help="输出文件路径（默认输出到终端）"),
) -> None:
    """导出知识库统计报告。"""
    import json

    from rich.panel import Panel
    from rich.table import Table

    from conflux.storage.file_store import FileStore
    from conflux.storage.graph_store import GraphStore

    file_store = FileStore()
    graph_store = GraphStore()

    file_stats = file_store.get_stats()
    graph_stats = graph_store.get_stats()

    report = {
        "storage": file_stats,
        "graph": graph_stats,
    }

    if output:
        output_path = Path(output).resolve()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(
            json.dumps(report, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        console.print(f"[green]✅ 统计报告已导出到: {output_path}[/green]")
    else:
        # 终端输出
        table = Table(title="📊 知识库统计报告")
        table.add_column("分类", style="bold")
        table.add_column("指标")
        table.add_column("数值", justify="right")

        for key, value in file_stats.items():
            table.add_row("存储", key, str(value))
        for key, value in graph_stats.items():
            table.add_row("图谱", key, str(value))

        console.print(table)
