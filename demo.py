"""
🌊 Conflux Demo - 无需 API Key 即可体验完整流程

运行方式：
    cd conflux
    .venv/bin/python demo.py
"""

import asyncio
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

console = Console()


async def main():
    console.print(Panel.fit(
        "[bold blue]🌊 Conflux Demo[/bold blue]\n"
        "无需 API Key，使用 dry-run 模式演示完整功能",
        border_style="blue",
    ))

    # ═══════════════════════════════════════════
    # 1. LLM Client — dry-run 模式
    # ═══════════════════════════════════════════
    console.print("\n[bold]━━━ 1. LLM Client（dry-run 模式）━━━[/bold]\n")

    from conflux.llm.client import LLMClient, LLMConfig

    config = LLMConfig(
        provider="deepseek",
        model="deepseek/deepseek-chat",
        dry_run=True,  # ← 关键：不发真实 API 请求
    )
    llm = LLMClient(config)

    # 对话
    resp = await llm.chat(system_prompt="你是医学专家", user_prompt="什么是心律失常？")
    console.print(f"  💬 chat 响应: [dim]{resp[:60]}[/dim]")

    # JSON
    data = await llm.complete_json(prompt="返回心律失常分类")
    console.print(f"  📋 JSON 响应: [dim]{data}[/dim]")

    # Embedding
    vec = await llm.embed("心律失常")
    console.print(f"  📐 embedding 维度: {len(vec)}")

    console.print("  [green]✅ LLM Client 工作正常[/green]")

    # ═══════════════════════════════════════════
    # 2. 概念模型 & 组网
    # ═══════════════════════════════════════════
    console.print("\n[bold]━━━ 2. 概念组网（Networker）━━━[/bold]\n")

    from conflux.models.concept import Concept
    from conflux.networker import SimilarityEngine, SubnetManager, NodeMerger, CrossLinker

    # 模拟两本书的概念
    book_a_concepts = [
        Concept(name="心率", definition="每分钟心脏搏动的次数", source_book="生理学"),
        Concept(name="血压", definition="血液对动脉壁的侧压力", source_book="生理学"),
        Concept(name="心输出量", definition="每分钟心脏泵出的血液量", source_book="生理学"),
    ]

    book_b_concepts = [
        Concept(name="心率", definition="心脏每分钟跳动次数", source_book="内科学", aliases=["heart rate"]),
        Concept(name="高血压", definition="收缩压≥140mmHg或舒张压≥90mmHg", source_book="内科学"),
        Concept(name="心力衰竭", definition="心脏泵血功能下降的综合征", source_book="内科学"),
    ]

    console.print(f"  📖 生理学概念: {[c.name for c in book_a_concepts]}")
    console.print(f"  📖 内科学概念: {[c.name for c in book_b_concepts]}")

    # 组网（传入 dry-run LLM client）
    engine = SimilarityEngine(llm_client=llm, threshold=0.7)
    subnet_mgr = SubnetManager()
    merger = NodeMerger()
    linker = CrossLinker(similarity_engine=engine, subnet_manager=subnet_mgr, node_merger=merger)

    result = await linker.integrate_new_concepts(book_b_concepts, book_a_concepts, "内科学")

    console.print(f"\n  🔗 组网结果:")
    console.print(f"     合并概念: {result.summary['merged_concepts']} 个（同名概念自动合并）")
    console.print(f"     新增概念: {result.summary['new_concepts']} 个")
    console.print(f"     跨书连接: {result.summary['cross_links']} 条")
    console.print("  [green]✅ 组网完成[/green]")

    # ═══════════════════════════════════════════
    # 3. 冲突检测
    # ═══════════════════════════════════════════
    console.print("\n[bold]━━━ 3. 冲突检测（Conflict）━━━[/bold]\n")

    from conflux.models.conflict import (
        Claim, Conflict, ConflictType, ConflictSeverity, ConflictSide,
    )
    from conflux.conflict import StanceDetector, SeverityScorer, VerdictManager

    # 模拟两条矛盾论断
    claim_a = Claim(
        statement="正常成人静息心率为 60-100 次/分",
        subject="正常心率范围",
        source_book="内科学（第9版）",
        confidence=0.95,
    )
    claim_b = Claim(
        statement="运动员正常心率可低至 40-60 次/分，普通人为 50-90 次/分",
        subject="正常心率范围",
        source_book="运动医学",
        confidence=0.90,
    )

    console.print(f"  📝 论断A: {claim_a.statement}")
    console.print(f"     来源: {claim_a.source_book}")
    console.print(f"  📝 论断B: {claim_b.statement}")
    console.print(f"     来源: {claim_b.source_book}")

    # 检测是否同一主题
    detector = StanceDetector()
    same_topic = detector._same_topic(claim_a, claim_b)
    console.print(f"\n  🔍 同主题检测: {same_topic}")

    # 构造冲突并评分
    conflict = Conflict(
        title="正常心率范围数值不一致",
        conflict_type=ConflictType.FACTUAL,
        sides=[
            ConflictSide(claim_id=claim_a.id, source_book="内科学（第9版）", position="60-100次/分"),
            ConflictSide(claim_id=claim_b.id, source_book="运动医学", position="50-90次/分"),
        ],
    )

    scorer = SeverityScorer()
    severity = scorer.score(conflict, concept_importance=0.8)
    score_val = scorer.compute_score(conflict, 0.8)

    console.print(f"  ⚡ 冲突: {conflict.title}")
    console.print(f"     类型: {conflict.conflict_type.value}")
    console.print(f"     严重度: {severity.value} (分数: {score_val:.2f})")

    # 裁决
    vm = VerdictManager()
    resolved = vm.resolve(
        conflict,
        decision="side",
        side_index=0,
        notes="临床标准以内科学教材为准，60-100次/分更为通用",
    )
    console.print(f"  ⚖️  裁决: {resolved.verdict.status.value}")
    console.print(f"     理由: {resolved.verdict.notes}")
    console.print("  [green]✅ 冲突检测 & 裁决完成[/green]")

    # ═══════════════════════════════════════════
    # 4. Web UI
    # ═══════════════════════════════════════════
    console.print("\n[bold]━━━ 4. Web UI━━━[/bold]\n")

    from conflux.web import create_app

    app = create_app()
    routes = [r.path for r in app.routes if hasattr(r, 'path')]
    
    table = Table(title="API 端点", show_lines=False)
    table.add_column("路径", style="cyan")
    table.add_column("用途")
    
    api_desc = {
        "/api/stats": "知识库统计",
        "/api/documents": "文档列表",
        "/api/graph": "图谱数据（D3 可视化）",
        "/api/conflicts": "冲突列表",
        "/api/conflicts/{id}/verdict": "提交裁决",
        "/api/subnets": "子网列表",
        "/api/health": "健康检查",
    }
    for path, desc in api_desc.items():
        table.add_row(path, desc)
    
    console.print(table)
    console.print("\n  启动方式: [bold cyan]conflux serve --port 8080[/bold cyan]")
    console.print("  然后浏览器打开 http://localhost:8080")
    console.print("  [green]✅ Web UI 就绪[/green]")

    # ═══════════════════════════════════════════
    # 汇总
    # ═══════════════════════════════════════════
    console.print("\n")
    console.print(Panel.fit(
        "[bold green]🎉 Demo 完成！所有模块正常工作[/bold green]\n\n"
        "下一步：\n"
        "  1. 获取 DeepSeek API Key → https://platform.deepseek.com\n"
        "  2. export DEEPSEEK_API_KEY='sk-xxx'\n"
        "  3. 将 demo.py 中 dry_run=True 改为 dry_run=False\n"
        "  4. 或直接运行: conflux init && conflux import && conflux build\n\n"
        "Web UI:\n"
        "  .venv/bin/python -m conflux.cli.main serve --port 8080",
        border_style="green",
        title="🚀 Next Steps",
    ))


if __name__ == "__main__":
    asyncio.run(main())
