"""Conflux CLI main entry point."""

import typer
from rich.console import Console

from conflux import __version__
from conflux.cli.import_cmd import import_app
from conflux.cli.build_cmd import build_app
from conflux.cli.conflicts_cmd import conflicts_app
from conflux.cli.search_cmd import search_app
from conflux.cli.export_cmd import export_app

app = typer.Typer(
    name="conflux",
    help="🌊 Conflux - 活体百科全书引擎",
    add_completion=True,
    rich_markup_mode="rich",
)
console = Console()

# 注册子命令
app.add_typer(import_app, name="import", help="导入书籍/文档")
app.add_typer(build_app, name="build", help="构建输出（编译+组网+冲突检测）")
app.add_typer(conflicts_app, name="conflicts", help="冲突管理")
app.add_typer(search_app, name="search", help="语义搜索")
app.add_typer(export_app, name="export", help="导出数据")


@app.command()
def init(
    name: str = typer.Option("我的知识库", "--name", "-n", help="项目名称"),
    path: str = typer.Option(".", "--path", "-p", help="项目路径"),
) -> None:
    """初始化一个新的 Conflux 知识库项目。"""
    import shutil
    from pathlib import Path

    project_path = Path(path).resolve()
    config_path = project_path / "conflux.config.yaml"

    if config_path.exists():
        console.print("[yellow]⚠️  配置文件已存在，跳过初始化。[/yellow]")
        return

    # 创建目录结构
    dirs = [
        "sources",
        "output/skills",
        "output/vault",
        "data",
        "logs",
    ]
    for d in dirs:
        (project_path / d).mkdir(parents=True, exist_ok=True)

    # 生成配置
    config_content = f"""project:
  name: "{name}"
  language: "zh-CN"

input:
  sources_dir: "./sources"
  supported_formats: ["md", "epub", "pdf"]

output:
  skills_dir: "./output/skills"
  vault_dir: "./output/vault"

engine:
  llm:
    provider: "deepseek"
    model: "deepseek/deepseek-chat"
    api_key_env: "DEEPSEEK_API_KEY"
  embedding:
    provider: "local"
    model: "BAAI/bge-small-zh-v1.5"
  conflict_detection:
    sensitivity: "medium"
  networking:
    similarity_threshold: 0.85

storage:
  vector_db: "chromadb"
  graph_db: "networkx"
  persistence_dir: "./data/"
"""
    config_path.write_text(config_content, encoding="utf-8")

    console.print(f"[green]✅ 知识库 [bold]{name}[/bold] 初始化成功！[/green]")
    console.print(f"   📁 项目路径: {project_path}")
    console.print("   📝 下一步: 将书籍放入 ./sources/ 目录，然后执行 conflux import")


@app.command()
def status() -> None:
    """查看当前知识库状态。"""
    from pathlib import Path

    from rich.panel import Panel
    from rich.table import Table

    from conflux.storage.file_store import FileStore

    console.print("[bold]📊 Conflux 知识库状态[/bold]\n")

    config_path = Path("conflux.config.yaml")
    if not config_path.exists():
        console.print("[red]❌ 未找到 conflux.config.yaml，请先执行 conflux init[/red]")
        raise typer.Exit(1)

    store = FileStore()
    stats = store.get_stats()

    # 构建统计表格
    table = Table(show_header=False, box=None, padding=(0, 2))
    table.add_column("指标", style="bold")
    table.add_column("数值", justify="right")

    table.add_row("📚 已导入文档", str(stats["documents"]))
    table.add_row("💡 概念总数", str(stats["concepts"]))
    table.add_row("🔗 关系总数", str(stats["relations"]))
    table.add_row("🤖 Skill 文件", str(stats["skills"]))
    table.add_row("🧠 Vault 节点", str(stats["vault_nodes"]))
    table.add_row("⚡ 冲突节点", str(stats["conflicts"]))

    console.print(Panel(table, title="存储统计", border_style="blue"))


@app.command()
def version() -> None:
    """显示版本信息。"""
    console.print(f"[bold blue]🌊 Conflux[/bold blue] v{__version__}")
    console.print("   活体百科全书引擎")
    console.print("   https://github.com/conflux-engine/conflux")


@app.command()
def clean(
    output_only: bool = typer.Option(True, "--output-only/--all", help="仅清理输出 vs 全部清理"),
    confirm: bool = typer.Option(False, "--yes", "-y", help="跳过确认"),
) -> None:
    """清理输出文件或全部数据。"""
    from conflux.storage.file_store import FileStore

    if not confirm:
        if output_only:
            msg = "确认清理所有输出文件（output/skills 和 output/vault）？"
        else:
            msg = "⚠️  确认清理所有数据和输出？此操作不可恢复！"

        confirmed = typer.confirm(msg)
        if not confirmed:
            console.print("[yellow]已取消。[/yellow]")
            raise typer.Exit(0)

    store = FileStore()
    if output_only:
        store.clean_output()
        console.print("[green]✅ 输出文件已清理。[/green]")
    else:
        store.clean_all()
        console.print("[green]✅ 所有数据和输出已清理。[/green]")


@app.command()
def doctor() -> None:
    """诊断环境配置是否正确。"""
    from pathlib import Path

    console.print("[bold]🔍 环境诊断\n[/bold]")

    checks: list[tuple[str, bool, str]] = []

    # 检查配置文件
    config_exists = Path("conflux.config.yaml").exists()
    checks.append(("配置文件", config_exists, "conflux.config.yaml"))

    # 检查目录
    for dirname in ["sources", "data", "output"]:
        exists = Path(dirname).exists()
        checks.append((f"目录 {dirname}/", exists, ""))

    # 检查 Python 依赖
    deps = [
        ("pydantic", "数据模型"),
        ("typer", "CLI"),
        ("rich", "终端美化"),
        ("litellm", "LLM 调用"),
        ("networkx", "图算法"),
        ("yaml", "YAML 处理"),
        ("structlog", "日志"),
    ]

    for pkg, desc in deps:
        try:
            __import__(pkg)
            checks.append((f"依赖 {pkg} ({desc})", True, ""))
        except ImportError:
            checks.append((f"依赖 {pkg} ({desc})", False, "pip install " + pkg))

    # 检查 LLM API Key
    import os
    has_key = bool(os.environ.get("CONFLUX_LLM_KEY") or os.environ.get("OPENAI_API_KEY"))
    checks.append(("LLM API Key", has_key, "设置 CONFLUX_LLM_KEY 或 OPENAI_API_KEY"))

    # 输出结果
    for name, passed, hint in checks:
        status = "[green]✅[/green]" if passed else "[red]❌[/red]"
        line = f"  {status} {name}"
        if not passed and hint:
            line += f"  [dim]→ {hint}[/dim]"
        console.print(line)

    passed_count = sum(1 for _, p, _ in checks if p)
    total = len(checks)
    console.print(f"\n  结果: {passed_count}/{total} 通过")


@app.command()
def serve(
    host: str = typer.Option("0.0.0.0", "--host", "-h", help="监听地址"),
    port: int = typer.Option(8080, "--port", "-p", help="监听端口"),
    reload: bool = typer.Option(False, "--reload", help="热重载模式（开发用）"),
) -> None:
    """启动 Web UI 服务。"""
    from pathlib import Path

    console.print(f"[bold blue]🌐 Conflux Web UI[/bold blue]")
    console.print(f"   地址: http://{host}:{port}")
    console.print(f"   API:  http://{host}:{port}/api")
    console.print("   按 Ctrl+C 停止\n")

    from conflux.web.server import serve as run_server

    data_dir = Path("data")
    run_server(host=host, port=port, data_dir=data_dir, reload=reload)


if __name__ == "__main__":
    app()
