"""Web App Factory - 创建 FastAPI 应用。"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from conflux.web.routes import api_router

STATIC_DIR = Path(__file__).parent / "static"


def create_app(
    data_dir: Optional[Path] = None,
    title: str = "Conflux Knowledge Engine",
    debug: bool = False,
) -> FastAPI:
    """创建 FastAPI 应用实例。

    Args:
        data_dir: 数据目录路径（用于初始化存储）。
        title: 应用标题。
        debug: 是否启用调试模式。

    Returns:
        配置好的 FastAPI 应用。
    """
    app = FastAPI(
        title=title,
        description="Conflux - 多源知识融合引擎 Web API",
        version="0.1.0",
        debug=debug,
    )

    # CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # 注册 API 路由
    app.include_router(api_router, prefix="/api")

    # 静态文件服务（SPA 前端）
    if STATIC_DIR.exists():
        app.mount("/", StaticFiles(directory=str(STATIC_DIR), html=True), name="static")

    # 将 data_dir 存储在 app state 中
    app.state.data_dir = data_dir or Path("data")

    return app
