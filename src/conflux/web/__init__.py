"""Web module - Conflux Web UI。

提供：
- FastAPI REST API 后端
- 静态文件服务（SPA 前端）
- 图谱可视化数据接口
- 冲突管理接口
"""

from conflux.web.app import create_app

__all__ = ["create_app"]
