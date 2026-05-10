"""Web Server Entry - 启动 Web 服务。"""

from __future__ import annotations

from pathlib import Path
from typing import Optional


def serve(
    host: str = "0.0.0.0",
    port: int = 8080,
    data_dir: Optional[Path] = None,
    reload: bool = False,
):
    """启动 Conflux Web 服务。

    Args:
        host: 监听地址。
        port: 监听端口。
        data_dir: 数据目录。
        reload: 是否启用热重载（开发模式）。
    """
    import uvicorn

    from conflux.web.app import create_app

    app = create_app(data_dir=data_dir, debug=reload)

    uvicorn.run(
        app,
        host=host,
        port=port,
        reload=reload,
    )


if __name__ == "__main__":
    serve()
