"""Import command - 导入书籍/文档到 Conflux。"""

from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn

import_app = typer.Typer()
console = Console()


@import_app.callback(invoke_without_command=True)
def import_callback(ctx: typer.Context) -> None:
    """导入书籍/文档到知识库。"""
    if ctx.invoked_subcommand is None:
        console.print("[yellow]请指定子命令。用法示例：[/yellow]")
        console.print("  conflux import file ./sources/book.md   # 导入单个文件")
        console.print("  conflux import batch ./sources           # 批量导入")
        console.print("  conflux import list                      # 列出已导入文档")
        raise typer.Exit(0)


@import_app.command("file")
def import_file(
    file_path: str = typer.Argument(..., help="要导入的文件路径"),
    format: str = typer.Option("auto", "--format", "-f", help="文件格式 (auto|md|epub|pdf)"),
    force: bool = typer.Option(False, "--force", help="强制重新导入（忽略缓存）"),
    title: Optional[str] = typer.Option(None, "--title", "-t", help="手动指定书名"),
) -> None:
    """导入一本书籍或文档到知识库。"""
    source = Path(file_path).resolve()

    if not source.exists():
        console.print(f"[red]❌ 文件不存在: {source}[/red]")
        raise typer.Exit(1)

    # 自动检测格式
    if format == "auto":
        suffix = source.suffix.lower()
        format_map = {".md": "md", ".markdown": "md", ".epub": "epub", ".pdf": "pdf"}
        format = format_map.get(suffix, "")
        if not format:
            console.print(f"[red]❌ 无法识别文件格式: {suffix}，请用 --format 指定[/red]")
            raise typer.Exit(1)

    console.print(f"[blue]📖 导入文件: [bold]{source.name}[/bold][/blue]")
    console.print(f"   格式: {format}")

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        # Step 1: 检查缓存
        from conflux.storage.file_store import FileStore

        store = FileStore()

        if not force:
            import hashlib
            current_hash = hashlib.sha256(source.read_bytes()).hexdigest()[:16]
            if not store.is_file_changed(str(source), current_hash):
                console.print("[yellow]⚠️  文件未变更，跳过导入。使用 --force 强制重新导入。[/yellow]")
                return
        else:
            current_hash = None

        # Step 2: 解析
        task = progress.add_task("解析文档结构...", total=None)
        from conflux.parser import parse_document

        ir_document = parse_document(source, format=format)

        # 覆盖标题（如果用户指定了）
        if title:
            ir_document.meta.title = title

        progress.update(task, description=f"✅ 解析完成 - {len(ir_document.structure)} 个章节")
        progress.remove_task(task)

        # Step 3: 存储 IR
        task = progress.add_task("保存中间表示...", total=None)
        store.save_ir(ir_document)
        progress.update(task, description="✅ 已保存到 data/")
        progress.remove_task(task)

        # Step 4: 更新 hash 缓存
        if current_hash:
            store.update_hash_cache(str(source), current_hash)

    console.print(f"\n[green]✅ 导入成功！[/green]")
    console.print(f"   文档ID: {ir_document.id}")
    console.print(f"   标题: {ir_document.meta.title}")
    console.print(f"   章节数: {len(ir_document.structure)}")
    console.print(f"   字数: ~{ir_document.total_words}")
    console.print(f"   下一步: 执行 [bold]conflux build[/bold] 生成 Skill 和 Vault")


@import_app.command("batch")
def import_batch(
    directory: str = typer.Argument("./sources", help="包含书籍的目录路径"),
    force: bool = typer.Option(False, "--force", help="强制重新导入"),
) -> None:
    """批量导入目录下的所有文档。"""
    from conflux.parser import parse_document
    from conflux.storage.file_store import FileStore

    source_dir = Path(directory).resolve()

    if not source_dir.exists():
        console.print(f"[red]❌ 目录不存在: {source_dir}[/red]")
        raise typer.Exit(1)

    # 查找支持的文件
    supported_exts = {".md", ".markdown", ".epub", ".pdf"}
    files = [
        f for f in source_dir.rglob("*")
        if f.suffix.lower() in supported_exts and f.is_file()
    ]

    if not files:
        console.print(f"[yellow]⚠️  未在 {source_dir} 中找到支持的文件。[/yellow]")
        console.print(f"   支持格式: {', '.join(supported_exts)}")
        return

    console.print(f"[blue]📚 发现 {len(files)} 个文件:[/blue]")
    for f in files:
        console.print(f"   • {f.name}")

    console.print()

    store = FileStore()
    success_count = 0
    fail_count = 0

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        for file in files:
            task = progress.add_task(f"导入: {file.name}...", total=None)
            try:
                doc = parse_document(file)
                store.save_ir(doc)
                progress.update(task, description=f"✅ {file.name}")
                success_count += 1
            except Exception as e:
                progress.update(task, description=f"❌ {file.name}: {e}")
                fail_count += 1
            progress.remove_task(task)

    console.print(f"\n[green]✅ 批量导入完成: {success_count} 成功, {fail_count} 失败[/green]")


@import_app.command("list")
def import_list() -> None:
    """列出所有已导入的文档。"""
    from rich.table import Table

    from conflux.storage.file_store import FileStore

    store = FileStore()
    documents = store.load_all_documents()

    if not documents:
        console.print("[yellow]⚠️  暂无已导入的文档。使用 conflux import <文件> 导入。[/yellow]")
        return

    table = Table(title=f"📚 已导入文档 ({len(documents)} 个)")
    table.add_column("ID", style="dim", width=12)
    table.add_column("标题", style="bold")
    table.add_column("作者")
    table.add_column("格式", width=8)
    table.add_column("章节", justify="center", width=6)
    table.add_column("字数", justify="right")
    table.add_column("导入时间", width=16)

    for doc in documents:
        table.add_row(
            doc.id[:12],
            doc.meta.title,
            doc.meta.author or "-",
            doc.meta.source_format.value,
            str(doc.total_chapters),
            f"~{doc.total_words:,}",
            doc.meta.import_time.strftime("%Y-%m-%d %H:%M"),
        )

    console.print(table)


@import_app.command("remove")
def import_remove(
    document_id: str = typer.Argument(..., help="要删除的文档 ID（支持前缀匹配）"),
) -> None:
    """删除一个已导入的文档。"""
    from conflux.storage.file_store import FileStore

    store = FileStore()

    # 支持前缀匹配
    documents = store.load_all_documents()
    matches = [d for d in documents if d.id.startswith(document_id)]

    if not matches:
        console.print(f"[red]❌ 未找到匹配的文档: {document_id}[/red]")
        raise typer.Exit(1)

    if len(matches) > 1:
        console.print(f"[yellow]⚠️  多个文档匹配 '{document_id}'，请提供更完整的 ID：[/yellow]")
        for m in matches:
            console.print(f"   • {m.id[:12]} - {m.meta.title}")
        raise typer.Exit(1)

    doc = matches[0]
    confirmed = typer.confirm(f"确认删除文档: {doc.meta.title} ({doc.id[:12]})?")
    if not confirmed:
        console.print("[yellow]已取消。[/yellow]")
        return

    store.delete_ir(doc.id)
    console.print(f"[green]✅ 已删除文档: {doc.meta.title}[/green]")
