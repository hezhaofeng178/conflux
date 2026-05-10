"""VerdictManager - 冲突裁决管理。

管理人类对冲突的裁决操作：
- 选择某一方
- 双方都正确
- 自定义裁决
- 暂缓处理
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from conflux.models.conflict import Conflict, Verdict, VerdictStatus


class VerdictManager:
    """冲突裁决管理器。
    
    负责处理人类对冲突的裁决逻辑，包括：
    - 记录裁决结果
    - 更新冲突状态
    - 生成裁决说明
    """

    def __init__(self, decided_by: str = "user") -> None:
        """初始化裁决管理器。
        
        Args:
            decided_by: 裁决人标识。
        """
        self.decided_by = decided_by

    def resolve(
        self,
        conflict: Conflict,
        decision: str,
        side_index: Optional[int] = None,
        notes: str = "",
    ) -> Conflict:
        """裁决一个冲突。
        
        Args:
            conflict: 冲突对象。
            decision: 裁决类型 - "side" | "both_valid" | "custom"
            side_index: 选择的一方索引（decision="side" 时使用）。
            notes: 裁决说明。
            
        Returns:
            更新后的 Conflict 对象。
        """
        chosen_side = None

        if decision == "side" and side_index is not None:
            if 0 <= side_index < len(conflict.sides):
                chosen_side = conflict.sides[side_index].claim_id
                if not notes:
                    notes = f"选择了第 {side_index + 1} 方的观点"

        elif decision == "both_valid":
            if not notes:
                notes = "双方观点在各自适用范围内均有效"

        elif decision == "custom":
            pass  # 使用用户提供的 notes

        conflict.verdict = Verdict(
            status=VerdictStatus.RESOLVED,
            decision=decision,
            decided_by=self.decided_by,
            decided_at=datetime.now(),
            notes=notes,
            chosen_side=chosen_side,
        )

        return conflict

    def defer(self, conflict: Conflict, notes: str = "") -> Conflict:
        """暂缓裁决。
        
        Args:
            conflict: 冲突对象。
            notes: 暂缓原因。
            
        Returns:
            更新后的 Conflict 对象。
        """
        conflict.verdict = Verdict(
            status=VerdictStatus.DEFERRED,
            decision="deferred",
            decided_by=self.decided_by,
            decided_at=datetime.now(),
            notes=notes or "需要更多信息才能裁决",
        )
        return conflict

    def dismiss(self, conflict: Conflict, notes: str = "") -> Conflict:
        """驳回冲突（标记为误报）。
        
        Args:
            conflict: 冲突对象。
            notes: 驳回原因。
            
        Returns:
            更新后的 Conflict 对象。
        """
        conflict.verdict = Verdict(
            status=VerdictStatus.DISMISSED,
            decision="dismissed",
            decided_by=self.decided_by,
            decided_at=datetime.now(),
            notes=notes or "非真正冲突，标记为误报",
        )
        return conflict

    def reopen(self, conflict: Conflict) -> Conflict:
        """重新打开已裁决的冲突。
        
        Args:
            conflict: 冲突对象。
            
        Returns:
            更新后的 Conflict 对象。
        """
        conflict.verdict = Verdict(
            status=VerdictStatus.UNRESOLVED,
        )
        return conflict
