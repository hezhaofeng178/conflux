"""Event system - 编排层事件总线。

提供事件驱动的松耦合通信机制，让各模块可以：
- 发布事件（如 "概念提取完成"）
- 订阅事件（如 UI 层订阅进度事件）
"""

from __future__ import annotations

import asyncio
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Awaitable, Optional
from uuid import uuid4

from pydantic import BaseModel, Field


class EventType(str, Enum):
    """事件类型枚举。"""

    # Pipeline 生命周期
    PIPELINE_STARTED = "pipeline.started"
    PIPELINE_COMPLETED = "pipeline.completed"
    PIPELINE_FAILED = "pipeline.failed"

    # 文档处理
    DOCUMENT_LOADED = "document.loaded"
    DOCUMENT_PARSED = "document.parsed"

    # 编译
    COMPILATION_STARTED = "compilation.started"
    COMPILATION_COMPLETED = "compilation.completed"
    CONCEPT_EXTRACTED = "concept.extracted"
    SKILL_GENERATED = "skill.generated"

    # 组网
    NETWORKING_STARTED = "networking.started"
    NETWORKING_COMPLETED = "networking.completed"
    CROSS_LINK_FOUND = "crosslink.found"

    # 冲突
    CONFLICT_DETECTION_STARTED = "conflict_detection.started"
    CONFLICT_DETECTION_COMPLETED = "conflict_detection.completed"
    CONFLICT_FOUND = "conflict.found"

    # 输出
    OUTPUT_STARTED = "output.started"
    OUTPUT_COMPLETED = "output.completed"

    # 进度
    PROGRESS = "progress"


class Event(BaseModel):
    """事件对象。"""

    id: str = Field(default_factory=lambda: uuid4().hex[:12])
    type: EventType
    timestamp: datetime = Field(default_factory=datetime.now)
    data: dict[str, Any] = Field(default_factory=dict)
    source: Optional[str] = None  # 事件来源模块

    @property
    def summary(self) -> str:
        """事件摘要。"""
        msg = self.data.get("message", "")
        return f"[{self.type.value}] {msg}" if msg else f"[{self.type.value}]"


# 事件处理器类型
EventHandler = Callable[[Event], Awaitable[None] | None]


class EventBus:
    """事件总线 - 发布/订阅模式的事件分发器。
    
    支持同步和异步事件处理器。
    
    Usage:
        bus = EventBus()
        
        # 订阅
        @bus.on(EventType.CONCEPT_EXTRACTED)
        async def on_concept(event: Event):
            print(f"提取了概念: {event.data['concept_name']}")
        
        # 发布
        await bus.emit(EventType.CONCEPT_EXTRACTED, {"concept_name": "机器学习"})
    """

    def __init__(self) -> None:
        self._handlers: dict[EventType, list[EventHandler]] = {}
        self._global_handlers: list[EventHandler] = []
        self._history: list[Event] = []
        self._max_history: int = 1000

    def on(self, event_type: EventType) -> Callable:
        """装饰器 - 注册事件处理器。
        
        Args:
            event_type: 要订阅的事件类型。
        """

        def decorator(handler: EventHandler) -> EventHandler:
            self.subscribe(event_type, handler)
            return handler

        return decorator

    def subscribe(self, event_type: EventType, handler: EventHandler) -> None:
        """订阅事件。"""
        if event_type not in self._handlers:
            self._handlers[event_type] = []
        self._handlers[event_type].append(handler)

    def subscribe_all(self, handler: EventHandler) -> None:
        """订阅所有事件（全局监听器）。"""
        self._global_handlers.append(handler)

    def unsubscribe(self, event_type: EventType, handler: EventHandler) -> None:
        """取消订阅。"""
        if event_type in self._handlers:
            self._handlers[event_type] = [
                h for h in self._handlers[event_type] if h != handler
            ]

    async def emit(
        self,
        event_type: EventType,
        data: Optional[dict[str, Any]] = None,
        source: Optional[str] = None,
    ) -> Event:
        """发布事件。
        
        Args:
            event_type: 事件类型。
            data: 事件数据。
            source: 事件来源。
            
        Returns:
            创建的 Event 对象。
        """
        event = Event(
            type=event_type,
            data=data or {},
            source=source,
        )

        # 记录历史
        self._history.append(event)
        if len(self._history) > self._max_history:
            self._history = self._history[-self._max_history:]

        # 分发给类型订阅者
        handlers = self._handlers.get(event_type, [])
        for handler in handlers:
            await self._invoke_handler(handler, event)

        # 分发给全局订阅者
        for handler in self._global_handlers:
            await self._invoke_handler(handler, event)

        return event

    def emit_sync(
        self,
        event_type: EventType,
        data: Optional[dict[str, Any]] = None,
        source: Optional[str] = None,
    ) -> Event:
        """同步发布事件（适用于非异步上下文）。"""
        event = Event(
            type=event_type,
            data=data or {},
            source=source,
        )

        self._history.append(event)
        if len(self._history) > self._max_history:
            self._history = self._history[-self._max_history:]

        # 同步分发
        handlers = self._handlers.get(event_type, [])
        for handler in handlers:
            self._invoke_handler_sync(handler, event)

        for handler in self._global_handlers:
            self._invoke_handler_sync(handler, event)

        return event

    @staticmethod
    async def _invoke_handler(handler: EventHandler, event: Event) -> None:
        """安全调用处理器。"""
        try:
            result = handler(event)
            if asyncio.iscoroutine(result):
                await result
        except Exception:
            # 事件处理器异常不应阻断流程
            pass

    @staticmethod
    def _invoke_handler_sync(handler: EventHandler, event: Event) -> None:
        """同步安全调用处理器。"""
        try:
            result = handler(event)
            if asyncio.iscoroutine(result):
                # 如果是异步处理器在同步上下文中，忽略
                pass
        except Exception:
            pass

    @property
    def history(self) -> list[Event]:
        """事件历史。"""
        return list(self._history)

    def clear_history(self) -> None:
        """清空事件历史。"""
        self._history.clear()

    def get_history_by_type(self, event_type: EventType) -> list[Event]:
        """按类型获取事件历史。"""
        return [e for e in self._history if e.type == event_type]
