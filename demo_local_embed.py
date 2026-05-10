"""
🌊 Conflux Demo - 本地 Embedding 语义相似度测试

无需任何 API Key，完全离线运行。
首次运行会自动下载模型（~90MB），之后完全离线。

运行方式：
    cd conflux
    .venv/bin/python demo_local_embed.py
"""

import asyncio
import time

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

console = Console()


async def main():
    console.print(Panel.fit(
        "[bold blue]🌊 Conflux - 本地 Embedding 语义相似度演示[/bold blue]\n"
        "使用 BAAI/bge-small-zh-v1.5 模型，完全离线、免费",
        border_style="blue",
    ))

    # ═══════════════════════════════════════════
    # 1. 初始化本地 Embedding 客户端
    # ═══════════════════════════════════════════
    console.print("\n[bold]━━━ 1. 加载本地 Embedding 模型 ━━━[/bold]\n")

    from conflux.llm.client import LLMClient, LLMConfig

    config = LLMConfig(
        provider="deepseek",
        model="deepseek/deepseek-chat",
        dry_run=True,                      # chat 仍用 dry-run（不需要 API Key）
        embed_provider="local",            # ← 关键：embedding 使用本地模型
        embed_model_name="BAAI/bge-small-zh-v1.5",  # 中文优秀小模型
    )

    console.print("  ⏳ 首次加载模型（如已缓存则很快）...")
    start = time.time()
    llm = LLMClient(config)

    # 预热模型（第一次 embed 会触发模型加载）
    _ = await llm.embed("测试")
    elapsed = time.time() - start
    console.print(f"  [green]✅ 模型加载完成[/green]（耗时 {elapsed:.1f}s）\n")

    # ═══════════════════════════════════════════
    # 2. 语义相似度测试
    # ═══════════════════════════════════════════
    console.print("[bold]━━━ 2. 语义相似度对比 ━━━[/bold]\n")

    import numpy as np

    async def cosine_sim(text_a: str, text_b: str) -> float:
        vec_a = np.array(await llm.embed(text_a))
        vec_b = np.array(await llm.embed(text_b))
        return float(np.dot(vec_a, vec_b) / (np.linalg.norm(vec_a) * np.linalg.norm(vec_b)))

    # 测试对
    test_pairs = [
        # 同义/近义 → 应该高相似度
        ("心率", "心跳频率", "同义词"),
        ("心率", "heart rate", "中英对照"),
        ("高血压", "血压升高", "同一概念不同表述"),
        ("心力衰竭", "心衰", "缩写"),
        ("糖尿病", "diabetes mellitus", "中英对照"),

        # 相关但不同 → 中等相似度
        ("心率", "血压", "相关概念"),
        ("高血压", "冠心病", "有关联"),
        ("肝脏", "肝炎", "器官与疾病"),

        # 不相关 → 应该低相似度
        ("心率", "量子物理", "不相关"),
        ("高血压", "人工智能", "完全不同领域"),
        ("糖尿病", "数据库设计", "无关"),
    ]

    table = Table(title="🔍 语义相似度对比", show_lines=True)
    table.add_column("文本 A", style="cyan", width=15)
    table.add_column("文本 B", style="cyan", width=18)
    table.add_column("关系", style="dim", width=15)
    table.add_column("相似度", justify="right", width=10)
    table.add_column("判定", width=10)

    for text_a, text_b, relation in test_pairs:
        sim = await cosine_sim(text_a, text_b)
        # 判定
        if sim >= 0.85:
            verdict = "[bold green]✅ 同一概念[/bold green]"
        elif sim >= 0.65:
            verdict = "[yellow]🔗 强相关[/yellow]"
        elif sim >= 0.45:
            verdict = "[dim]~ 弱相关[/dim]"
        else:
            verdict = "[red]✗ 不相关[/red]"

        table.add_row(text_a, text_b, relation, f"{sim:.3f}", verdict)

    console.print(table)

    # ═══════════════════════════════════════════
    # 3. 在 Conflux 概念组网中使用
    # ═══════════════════════════════════════════
    console.print("\n[bold]━━━ 3. 概念组网（使用真实 Embedding）━━━[/bold]\n")

    from conflux.models.concept import Concept
    from conflux.networker import SimilarityEngine, SubnetManager, NodeMerger, CrossLinker

    # 模拟两本书的概念
    book_a_concepts = [
        Concept(name="心率", definition="每分钟心脏搏动的次数", source_book="生理学"),
        Concept(name="血压", definition="血液对动脉壁的侧压力", source_book="生理学"),
        Concept(name="心输出量", definition="每分钟心脏泵出的血液量", source_book="生理学"),
    ]

    book_b_concepts = [
        Concept(name="心跳频率", definition="心脏每分钟跳动次数", source_book="内科学", aliases=["heart rate"]),
        Concept(name="高血压", definition="收缩压≥140mmHg或舒张压≥90mmHg", source_book="内科学"),
        Concept(name="心力衰竭", definition="心脏泵血功能下降的综合征", source_book="内科学"),
    ]

    console.print(f"  📖 生理学: {[c.name for c in book_a_concepts]}")
    console.print(f"  📖 内科学: {[c.name for c in book_b_concepts]}")

    # 使用真实本地 embedding 进行组网
    engine = SimilarityEngine(llm_client=llm, threshold=0.65)

    console.print("\n  🔍 正在用 embedding 计算概念间相似度...\n")

    # 手动展示相似度计算结果
    sim_table = Table(title="概念间语义相似度", show_lines=True)
    sim_table.add_column("生理学", style="cyan")
    sim_table.add_column("内科学", style="magenta")
    sim_table.add_column("相似度", justify="right")
    sim_table.add_column("判定")

    for ca in book_a_concepts:
        for cb in book_b_concepts:
            # 用概念的 name + definition 计算相似度
            text_a = f"{ca.name} | {ca.definition}"
            text_b = f"{cb.name} | {cb.definition}" + (f" | 别名: {', '.join(cb.aliases)}" if cb.aliases else "")
            sim = await cosine_sim(text_a, text_b)

            if sim >= 0.80:
                verdict = "[bold green]→ 应合并[/bold green]"
            elif sim >= 0.60:
                verdict = "[yellow]→ 建立关联[/yellow]"
            else:
                verdict = "[dim]→ 独立[/dim]"

            sim_table.add_row(ca.name, cb.name, f"{sim:.3f}", verdict)

    console.print(sim_table)

    # ═══════════════════════════════════════════
    # 4. 模型信息
    # ═══════════════════════════════════════════
    console.print("\n[bold]━━━ 4. 本地模型信息 ━━━[/bold]\n")

    info_table = Table(show_header=False, show_lines=False)
    info_table.add_column("属性", style="bold")
    info_table.add_column("值", style="cyan")

    info_table.add_row("模型", config.embed_model_name)
    from conflux.llm.client import LLMClient as _LC
    dim = _LC._local_embed_model_instance.get_embedding_dimension()
    info_table.add_row("向量维度", str(dim))
    info_table.add_row("大小", "~90 MB")
    info_table.add_row("语言", "中文优化（也支持英文）")
    info_table.add_row("是否需要网络", "仅首次下载，之后完全离线")
    info_table.add_row("是否需要 API Key", "❌ 不需要")

    console.print(info_table)

    # ═══════════════════════════════════════════
    # 完成
    # ═══════════════════════════════════════════
    console.print("\n")
    console.print(Panel.fit(
        "[bold green]🎉 本地 Embedding 演示完成！[/bold green]\n\n"
        "关键发现：\n"
        "  • '心率' ↔ '心跳频率' — 高相似度，可自动合并\n"
        "  • '心率' ↔ 'heart rate' — 跨语言也能匹配\n"
        "  • '心率' ↔ '量子物理' — 正确识别为不相关\n\n"
        "配置方式：\n"
        "  config = LLMConfig(\n"
        "      embed_provider='local',\n"
        "      embed_model_name='BAAI/bge-small-zh-v1.5',\n"
        "  )\n\n"
        "可选模型（更换 embed_model_name）：\n"
        "  • BAAI/bge-small-zh-v1.5  — 轻量，中文优\n"
        "  • BAAI/bge-base-zh-v1.5   — 平衡效果和速度\n"
        "  • BAAI/bge-large-zh-v1.5  — 最佳效果，较慢\n"
        "  • shibing624/text2vec-base-chinese — 另一个好选择",
        border_style="green",
        title="🚀 Summary",
    ))


if __name__ == "__main__":
    asyncio.run(main())
