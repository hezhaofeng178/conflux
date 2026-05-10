"""API Routes - REST API 路由定义。"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel

from conflux.models.conflict import Conflict, ConflictSeverity, VerdictStatus
from conflux.models.graph import NodeType
from conflux.storage.file_store import FileStore
from conflux.storage.graph_store import GraphStore

api_router = APIRouter()


# ─── 响应模型 ─────────────────────────────────────────────────────

class StatsResponse(BaseModel):
    """系统统计信息。"""
    documents: int = 0
    concepts: int = 0
    relations: int = 0
    conflicts: int = 0
    graph_nodes: int = 0
    graph_edges: int = 0
    subnets: int = 0


class GraphNodeResponse(BaseModel):
    """图节点响应。"""
    id: str
    label: str
    node_type: str
    group: Optional[str] = None
    properties: dict = {}


class GraphEdgeResponse(BaseModel):
    """图边响应。"""
    id: str
    source: str
    target: str
    edge_type: str
    weight: float = 1.0
    label: Optional[str] = None


class GraphDataResponse(BaseModel):
    """图可视化数据。"""
    nodes: list[GraphNodeResponse] = []
    edges: list[GraphEdgeResponse] = []


class ConflictListItem(BaseModel):
    """冲突列表项。"""
    id: str
    title: str
    conflict_type: str
    severity: str
    status: str
    source_books: list[str] = []
    subject: Optional[str] = None


class ConflictDetailResponse(BaseModel):
    """冲突详情。"""
    id: str
    title: str
    conflict_type: str
    severity: str
    status: str
    sides: list[dict] = []
    analysis: dict = {}
    verdict: dict = {}
    source_books: list[str] = []
    subject: Optional[str] = None
    detection_confidence: float = 0.0


class VerdictRequest(BaseModel):
    """裁决请求。"""
    decision: str  # "side" | "both_valid" | "custom" | "defer" | "dismiss"
    side_index: Optional[int] = None
    notes: str = ""


class DocumentListItem(BaseModel):
    """文档列表项。"""
    id: str
    title: str
    source: str = ""
    chapters: int = 0
    words: int = 0


class SearchRequest(BaseModel):
    """搜索请求。"""
    query: str
    top_k: int = 10


class SearchResultItem(BaseModel):
    """搜索结果项。"""
    id: str
    name: str
    type: str
    score: float = 0.0
    source: str = ""
    snippet: str = ""


# ─── Helper 函数 ─────────────────────────────────────────────────

def _get_file_store(request: Request) -> FileStore:
    """从 request 中获取 FileStore。"""
    data_dir = getattr(request.app.state, "data_dir", Path("data"))
    return FileStore(base_path=data_dir)


def _get_graph_store(request: Request) -> GraphStore:
    """从 request 中获取 GraphStore。"""
    data_dir = getattr(request.app.state, "data_dir", Path("data"))
    return GraphStore(persist_path=data_dir / "graph.json")


# ─── API 端点 ─────────────────────────────────────────────────────

@api_router.get("/stats", response_model=StatsResponse)
async def get_stats(request: Request):
    """获取系统总览统计。"""
    file_store = _get_file_store(request)
    graph_store = _get_graph_store(request)

    file_stats = file_store.get_stats()
    graph_stats = graph_store.get_stats()

    return StatsResponse(
        documents=file_stats.get("documents", 0),
        concepts=file_stats.get("concepts", 0),
        relations=file_stats.get("relations", 0),
        conflicts=file_stats.get("conflicts", 0),
        graph_nodes=graph_stats.get("nodes", 0),
        graph_edges=graph_stats.get("edges", 0),
        subnets=graph_stats.get("subnets", 0),
    )


@api_router.get("/documents", response_model=list[DocumentListItem])
async def list_documents(request: Request):
    """获取已导入的文档列表。"""
    file_store = _get_file_store(request)
    documents: list[DocumentListItem] = []

    ir_dir = file_store.base_path / "ir"
    if ir_dir.exists():
        for f in ir_dir.glob("*.json"):
            try:
                doc = file_store.load_ir(f.stem)
                if doc:
                    documents.append(DocumentListItem(
                        id=doc.id,
                        title=doc.meta.title,
                        source=doc.meta.source_path or "",
                        chapters=doc.total_chapters,
                        words=doc.total_words,
                    ))
            except Exception:
                continue

    return documents


@api_router.get("/graph", response_model=GraphDataResponse)
async def get_graph_data(
    request: Request,
    node_type: Optional[str] = Query(None, description="过滤节点类型"),
    limit: int = Query(200, description="最大节点数"),
):
    """获取图可视化数据（用于前端 D3/Cytoscape 渲染）。"""
    graph_store = _get_graph_store(request)
    graph = graph_store.graph

    nodes: list[GraphNodeResponse] = []
    edges: list[GraphEdgeResponse] = []

    # 获取节点
    node_count = 0
    for node_id, data in graph.nodes(data=True):
        if node_count >= limit:
            break

        n_type = data.get("node_type", "concept")
        if node_type and n_type != node_type:
            continue

        nodes.append(GraphNodeResponse(
            id=node_id,
            label=data.get("label", node_id),
            node_type=n_type,
            group=data.get("properties", {}).get("domain"),
            properties=data.get("properties", {}),
        ))
        node_count += 1

    # 获取边（只包含已选节点相关的边）
    node_ids = {n.id for n in nodes}
    edge_idx = 0
    for source, target, data in graph.edges(data=True):
        if source in node_ids and target in node_ids:
            edges.append(GraphEdgeResponse(
                id=f"e_{edge_idx}",
                source=source,
                target=target,
                edge_type=data.get("edge_type", "semantic"),
                weight=data.get("weight", 1.0),
                label=data.get("edge_type", ""),
            ))
            edge_idx += 1

    return GraphDataResponse(nodes=nodes, edges=edges)


@api_router.get("/graph/node/{node_id}")
async def get_node_detail(request: Request, node_id: str):
    """获取节点详情及其邻居。"""
    graph_store = _get_graph_store(request)

    node = graph_store.get_node(node_id)
    if not node:
        raise HTTPException(status_code=404, detail=f"节点 {node_id} 不存在")

    neighbors = graph_store.get_neighbors(node_id)
    degree = graph_store.get_node_degree(node_id)

    neighbor_nodes = []
    for nid in neighbors[:20]:
        n = graph_store.get_node(nid)
        if n:
            neighbor_nodes.append({
                "id": n.id,
                "label": n.label,
                "node_type": n.node_type.value,
            })

    return {
        "node": {
            "id": node.id,
            "label": node.label,
            "node_type": node.node_type.value,
            "properties": node.properties,
            "source_id": node.source_id,
        },
        "neighbors": neighbor_nodes,
        "degree": degree,
    }


@api_router.get("/conflicts", response_model=list[ConflictListItem])
async def list_conflicts(
    request: Request,
    status: Optional[str] = Query(None, description="过滤状态"),
    severity: Optional[str] = Query(None, description="过滤严重程度"),
):
    """获取冲突列表。"""
    file_store = _get_file_store(request)
    conflicts: list[ConflictListItem] = []

    conflicts_dir = file_store.base_path / "conflicts"
    if not conflicts_dir.exists():
        return []

    import json

    for f in conflicts_dir.glob("*.json"):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            conflict = Conflict.model_validate(data)

            # 过滤
            if status and conflict.verdict.status.value != status:
                continue
            if severity and conflict.severity.value != severity:
                continue

            conflicts.append(ConflictListItem(
                id=conflict.id,
                title=conflict.title,
                conflict_type=conflict.conflict_type.value,
                severity=conflict.severity.value,
                status=conflict.verdict.status.value,
                source_books=conflict.source_books,
                subject=conflict.subject,
            ))
        except Exception:
            continue

    return conflicts


@api_router.get("/conflicts/{conflict_id}", response_model=ConflictDetailResponse)
async def get_conflict_detail(request: Request, conflict_id: str):
    """获取冲突详情。"""
    file_store = _get_file_store(request)

    import json

    conflict_path = file_store.base_path / "conflicts" / f"{conflict_id}.json"
    if not conflict_path.exists():
        raise HTTPException(status_code=404, detail=f"冲突 {conflict_id} 不存在")

    data = json.loads(conflict_path.read_text(encoding="utf-8"))
    conflict = Conflict.model_validate(data)

    return ConflictDetailResponse(
        id=conflict.id,
        title=conflict.title,
        conflict_type=conflict.conflict_type.value,
        severity=conflict.severity.value,
        status=conflict.verdict.status.value,
        sides=[side.model_dump() for side in conflict.sides],
        analysis=conflict.analysis.model_dump(),
        verdict=conflict.verdict.model_dump(mode="json"),
        source_books=conflict.source_books,
        subject=conflict.subject,
        detection_confidence=conflict.detection_confidence,
    )


@api_router.post("/conflicts/{conflict_id}/verdict")
async def resolve_conflict(request: Request, conflict_id: str, body: VerdictRequest):
    """对冲突进行裁决。"""
    from conflux.conflict.verdict import VerdictManager

    file_store = _get_file_store(request)
    import json

    conflict_path = file_store.base_path / "conflicts" / f"{conflict_id}.json"
    if not conflict_path.exists():
        raise HTTPException(status_code=404, detail=f"冲突 {conflict_id} 不存在")

    data = json.loads(conflict_path.read_text(encoding="utf-8"))
    conflict = Conflict.model_validate(data)

    manager = VerdictManager()

    if body.decision in ("side", "both_valid", "custom"):
        conflict = manager.resolve(
            conflict,
            decision=body.decision,
            side_index=body.side_index,
            notes=body.notes,
        )
    elif body.decision == "defer":
        conflict = manager.defer(conflict, notes=body.notes)
    elif body.decision == "dismiss":
        conflict = manager.dismiss(conflict, notes=body.notes)
    else:
        raise HTTPException(status_code=400, detail=f"无效的裁决类型: {body.decision}")

    # 持久化
    conflict_path.write_text(
        json.dumps(conflict.model_dump(mode="json"), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    return {"status": "ok", "verdict_status": conflict.verdict.status.value}


@api_router.get("/subnets")
async def list_subnets(request: Request):
    """获取所有子网列表。"""
    graph_store = _get_graph_store(request)
    kg = graph_store.knowledge_graph

    subnets = []
    for subnet_id, subnet in kg.subnets.items():
        subnets.append({
            "id": subnet.id,
            "name": subnet.name,
            "domain": subnet.domain,
            "node_count": len(subnet.node_ids),
            "source_books": subnet.source_books,
            "cross_links_count": len(subnet.cross_links),
        })

    return subnets


@api_router.get("/vault/content")
async def get_vault_content(
    request: Request,
    label: str = Query(..., description="节点标签（概念名称）"),
    source: Optional[str] = Query(None, description="来源书籍名（可选，用于精确定位）"),
):
    """根据节点标签查找对应的 vault 知识讲解 Markdown 内容。
    
    在所有 vault 目录中搜索匹配的 .md 文件，返回内容用于前端渲染。
    """
    from conflux.web.app import STATIC_DIR

    # vault 目录相对于 data_dir 或默认 output/vault
    data_dir = getattr(request.app.state, "data_dir", Path("data"))
    vault_dirs = []

    # 尝试多个可能的 vault 路径
    candidates = [
        Path("output/vault"),
        data_dir.parent / "output" / "vault",
        data_dir / ".." / "output" / "vault",
    ]
    for c in candidates:
        resolved = c.resolve()
        if resolved.exists():
            vault_dirs.append(resolved)

    # 也递归搜索 data 目录下是否有 vault
    for p in data_dir.rglob("vault"):
        if p.is_dir():
            vault_dirs.append(p.resolve())

    # 去重
    vault_dirs = list(dict.fromkeys(vault_dirs))

    for vault_dir in vault_dirs:
        # 优先精确匹配文件名
        md_name = f"{label}.md"
        # 在所有子目录中搜索
        for md_file in vault_dir.rglob("*.md"):
            if md_file.name == md_name:
                # 如果指定了 source，验证目录名匹配
                if source and source not in md_file.parent.name:
                    continue
                content = md_file.read_text(encoding="utf-8")
                rel_path = md_file.relative_to(vault_dir.parent if vault_dir.parent.name == "output" else vault_dir)
                return {
                    "found": True,
                    "content": content,
                    "path": str(rel_path.as_posix()),
                    "label": label,
                }

    return {"found": False, "content": None, "path": None, "label": label}


@api_router.get("/health")
async def health_check():
    """健康检查。"""
    return {"status": "ok", "service": "conflux-web"}
