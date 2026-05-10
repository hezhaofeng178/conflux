"""Conflicts command - 冲突管理。"""

import typer
from rich.console import Console
from rich.table import Table

conflicts_app = typer.Typer()
console = Console()


@conflicts_app.command("list")
def list_conflicts(
    severity: str = typer.Option(None, "--severity", "-s", help="按严重程度过滤 (low|medium|high|critical)"),
    status: str = typer.Option("unresolved", "--status", help="按状态过滤 (unresolved|resolved|all)"),
    limit: int = typer.Option(20, "--limit", "-l", help="显示数量限制"),
) -> None:
    """列出所有冲突节点。"""
    from conflux.storage.file_store import FileStore

    store = FileStore()
    conflicts = store.load_conflicts()

    # 过滤
    if status != "all":
        conflicts = [c for c in conflicts if c.verdict.status.value == status]
    if severity:
        conflicts = [c for c in conflicts if c.severity.value == severity]

    if not conflicts:
        console.print("[green]✅ 没有找到匹配的冲突节点。[/green]")
        return

    # 表格展示
    table = Table(title=f"⚡ 冲突列表 ({len(conflicts)} 个)", show_lines=True)
    table.add_column("ID", style="dim", width=14)
    table.add_column("标题", style="bold")
    table.add_column("类型", width=12)
    table.add_column("严重程度", width=10)
    table.add_column("来源数", width=8, justify="center")
    table.add_column("状态", width=10)

    severity_colors = {
        "low": "green",
        "medium": "yellow",
        "high": "red",
        "critical": "bold red",
    }

    for conflict in conflicts[:limit]:
        sev_value = conflict.severity.value
        sev_color = severity_colors.get(sev_value, "white")
        table.add_row(
            conflict.id[:14],
            conflict.title,
            conflict.conflict_type.value,
            f"[{sev_color}]{sev_value}[/{sev_color}]",
            str(len(conflict.sides)),
            conflict.verdict.status.value,
        )

    console.print(table)
    console.print(f"\n💡 使用 [bold]conflux conflicts show <id>[/bold] 查看详情")


@conflicts_app.command("show")
def show_conflict(
    conflict_id: str = typer.Argument(..., help="冲突节点 ID（支持前缀匹配）"),
) -> None:
    """查看冲突详情。"""
    from conflux.storage.file_store import FileStore

    store = FileStore()
    
    # 支持前缀匹配
    conflict = store.load_conflict(conflict_id)
    if not conflict:
        # 尝试前缀匹配
        all_conflicts = store.load_conflicts()
        matches = [c for c in all_conflicts if c.id.startswith(conflict_id)]
        if len(matches) == 1:
            conflict = matches[0]
        elif len(matches) > 1:
            console.print(f"[yellow]多个冲突匹配 '{conflict_id}':[/yellow]")
            for c in matches:
                console.print(f"   • {c.id[:14]} - {c.title}")
            return
        else:
            console.print(f"[red]❌ 未找到冲突: {conflict_id}[/red]")
            raise typer.Exit(1)

    console.print(f"\n[bold]⚡ 冲突: {conflict.title}[/bold]")
    console.print(f"   ID: {conflict.id}")
    console.print(f"   类型: {conflict.conflict_type.value}")
    console.print(f"   严重程度: {conflict.severity.value}")
    console.print(f"   状态: {conflict.verdict.status.value}\n")

    console.print("[bold]📚 各方观点:[/bold]")
    for i, side in enumerate(conflict.sides, 1):
        console.print(f"\n   [{i}] 来源: {side.source_book}")
        console.print(f"       观点: {side.position}")
        if side.context:
            console.print(f"       上下文: [dim]{side.context[:100]}[/dim]")

    if conflict.analysis:
        console.print(f"\n[bold]🤔 分析:[/bold]")
        if conflict.analysis.possible_reasons:
            for reason in conflict.analysis.possible_reasons:
                console.print(f"   • {reason}")
        if conflict.analysis.suggested_resolution:
            console.print(f"\n   💡 建议: {conflict.analysis.suggested_resolution}")

    if conflict.verdict.status.value != "unresolved":
        console.print(f"\n[bold]⚖️  裁决:[/bold]")
        console.print(f"   状态: {conflict.verdict.status.value}")
        if conflict.verdict.notes:
            console.print(f"   说明: {conflict.verdict.notes}")
        if conflict.verdict.decided_at:
            console.print(f"   时间: {conflict.verdict.decided_at}")

    console.print(f"\n💡 使用 [bold]conflux conflicts resolve {conflict.id[:14]}[/bold] 进行裁决")


@conflicts_app.command("resolve")
def resolve_conflict(
    conflict_id: str = typer.Argument(..., help="冲突节点 ID"),
) -> None:
    """交互式裁决一个冲突。"""
    from conflux.storage.file_store import FileStore
    from conflux.conflict.verdict import VerdictManager

    store = FileStore()
    
    # 支持前缀匹配
    conflict = store.load_conflict(conflict_id)
    if not conflict:
        all_conflicts = store.load_conflicts()
        matches = [c for c in all_conflicts if c.id.startswith(conflict_id)]
        if len(matches) == 1:
            conflict = matches[0]
        else:
            console.print(f"[red]❌ 未找到冲突: {conflict_id}[/red]")
            raise typer.Exit(1)

    console.print(f"\n[bold]⚡ 裁决冲突: {conflict.title}[/bold]\n")

    # 展示各方
    for i, side in enumerate(conflict.sides, 1):
        console.print(f"   [{i}] {side.source_book}: {side.position}")

    console.print("\n[bold]请选择裁决方式:[/bold]")
    console.print("   1. 选择某一方正确")
    console.print("   2. 双方都正确（适用范围不同）")
    console.print("   3. 双方都不完全正确，补充说明")
    console.print("   4. 标记为误报")
    console.print("   5. 暂时搁置")

    choice = typer.prompt("请输入选项", type=int)

    verdict_manager = VerdictManager()

    if choice == 1:
        side_idx = typer.prompt("选择正确的一方编号", type=int)
        notes = typer.prompt("备注（可选）", default="")
        verdict_manager.resolve(conflict, decision="side", side_index=side_idx - 1, notes=notes)
    elif choice == 2:
        notes = typer.prompt("请说明各自适用范围")
        verdict_manager.resolve(conflict, decision="both_valid", notes=notes)
    elif choice == 3:
        notes = typer.prompt("请输入你的判断")
        verdict_manager.resolve(conflict, decision="custom", notes=notes)
    elif choice == 4:
        notes = typer.prompt("标记为误报的原因", default="")
        verdict_manager.dismiss(conflict, notes=notes)
    elif choice == 5:
        verdict_manager.defer(conflict)
        console.print("[yellow]已搁置，后续可重新裁决。[/yellow]")
        store.save_conflict(conflict)
        return
    else:
        console.print("[red]无效选项[/red]")
        raise typer.Exit(1)

    store.save_conflict(conflict)
    console.print("[green]✅ 裁决已保存！[/green]")


@conflicts_app.command("stats")
def conflict_stats() -> None:
    """查看冲突统计概览。"""
    from rich.panel import Panel

    from conflux.storage.file_store import FileStore

    store = FileStore()
    conflicts = store.load_conflicts()

    if not conflicts:
        console.print("[green]✅ 暂无冲突记录。[/green]")
        return

    # 统计
    total = len(conflicts)
    by_status = {}
    by_severity = {}
    by_type = {}

    for c in conflicts:
        status = c.verdict.status.value
        by_status[status] = by_status.get(status, 0) + 1

        severity = c.severity.value
        by_severity[severity] = by_severity.get(severity, 0) + 1

        ctype = c.conflict_type.value
        by_type[ctype] = by_type.get(ctype, 0) + 1

    lines = [
        f"📊 冲突总数: [bold]{total}[/bold]\n",
        "[bold]按状态:[/bold]",
    ]
    for s, count in sorted(by_status.items()):
        lines.append(f"  {s}: {count}")

    lines.append("\n[bold]按严重程度:[/bold]")
    for s, count in sorted(by_severity.items()):
        lines.append(f"  {s}: {count}")

    lines.append("\n[bold]按类型:[/bold]")
    for t, count in sorted(by_type.items()):
        lines.append(f"  {t}: {count}")

    console.print(Panel("\n".join(lines), title="⚡ 冲突统计", border_style="yellow"))
