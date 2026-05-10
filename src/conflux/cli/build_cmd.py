"""Build command - 构建输出（编译+组网+冲突检测）。"""

from pathlib import Path

import typer
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn

build_app = typer.Typer()
console = Console()


@build_app.callback(invoke_without_command=True)
def build(
    full: bool = typer.Option(False, "--full", help="全量构建（忽略增量缓存）"),
    skip_conflicts: bool = typer.Option(False, "--skip-conflicts", help="跳过冲突检测"),
    skip_networking: bool = typer.Option(False, "--skip-networking", help="跳过动态组网"),
) -> None:
    """构建输出：编译 Skill + 生成 Vault + 组网 + 冲突检测。"""
    from conflux.config_loader import load_config, build_llm_config
    from conflux.llm.client import get_llm_client
    from conflux.orchestrator.pipeline import Pipeline
    from conflux.orchestrator.pipeline import PipelineConfig

    # 读取 conflux.config.yaml 并构建 LLM 配置
    raw_config = load_config()
    if raw_config:
        llm_config = build_llm_config(raw_config)
        # 注册为全局 LLM 客户端
        get_llm_client(llm_config)

    config = PipelineConfig(
        full_rebuild=full,
        skip_conflicts=skip_conflicts,
        skip_networking=skip_networking,
    )

    console.print("[bold blue]🔨 开始构建...[/bold blue]\n")

    pipeline = Pipeline(config=config)

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        console=console,
    ) as progress:
        # Step 1: 加载 IR 文档
        task = progress.add_task("加载已导入的文档...", total=None)
        documents = pipeline.load_documents()
        progress.update(task, description=f"✅ 加载了 {len(documents)} 个文档")
        progress.remove_task(task)

        if not documents:
            console.print("[yellow]⚠️  没有已导入的文档，请先执行 conflux import[/yellow]")
            raise typer.Exit(0)

        # Step 2: 概念提取 & 编译
        task = progress.add_task("提取概念并编译...", total=len(documents))
        for doc in documents:
            pipeline.compile_document(doc)
            progress.advance(task)
        progress.update(task, description="✅ 编译完成")
        progress.remove_task(task)

        # Step 3: 动态组网
        if not skip_networking:
            task = progress.add_task("动态组网...", total=None)
            pipeline.run_networking()
            progress.update(task, description="✅ 组网完成")
            progress.remove_task(task)

        # Step 4: 冲突检测
        if not skip_conflicts:
            task = progress.add_task("冲突检测...", total=None)
            conflicts = pipeline.detect_conflicts()
            progress.update(
                task, description=f"✅ 检测完成 - 发现 {len(conflicts)} 个冲突"
            )
            progress.remove_task(task)

        # Step 5: 输出生成
        task = progress.add_task("生成输出文件...", total=None)
        stats = pipeline.generate_output()
        progress.update(task, description="✅ 输出生成完成")
        progress.remove_task(task)

    console.print("\n[green bold]✅ 构建完成！[/green bold]")
    console.print(f"   🤖 生成 Skill 文件: {stats.get('skills', 0)} 个")
    console.print(f"   🧠 生成 Vault 节点: {stats.get('vault_nodes', 0)} 个")
    console.print(f"   🔗 建立跨书连接: {stats.get('cross_links', 0)} 条")
    console.print(f"   ⚡ 发现冲突: {stats.get('conflicts', 0)} 个")
    console.print(f"\n   📁 Skills: ./output/skills/")
    console.print(f"   📁 Vault:  ./output/vault/")
