"""Stance Detector - 检测论断的立场/方向。

分析论断的立场方向，为冲突配对提供依据。
两个论断要构成冲突，它们必须：
1. 针对同一主题
2. 持有不同/矛盾的立场
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Optional

from conflux.models.conflict import Claim
from conflux.llm.client import LLMClient


@dataclass
class StanceInfo:
    """论断的立场信息。"""

    claim_id: str
    subject: str
    direction: str  # positive / negative / neutral
    strength: float = 0.8
    keywords: list[str] = None  # type: ignore

    def __post_init__(self):
        if self.keywords is None:
            self.keywords = []


@dataclass
class ConflictJudgment:
    """冲突判断结果。"""

    is_conflicting: bool
    confidence: float
    reason: str = ""


class StanceDetector:
    """立场检测器。

    分析论断的立场方向，为冲突配对提供依据。
    支持：
    - 单论断立场检测
    - 两论断矛盾判断
    - 快速主题匹配
    """

    def __init__(self, llm_client: Optional[LLMClient] = None):
        """初始化立场检测器。

        Args:
            llm_client: LLM 客户端。
        """
        self.llm = llm_client or LLMClient()

    async def detect_stance(self, claim: Claim) -> StanceInfo:
        """检测单个论断的立场信息。

        Args:
            claim: 论断对象。

        Returns:
            立场信息。
        """
        subject = claim.subject or self._extract_subject(claim.statement)

        return StanceInfo(
            claim_id=claim.id,
            subject=subject,
            direction="positive",  # 默认为正面陈述
            strength=claim.confidence,
            keywords=self._extract_keywords(claim.statement),
        )

    async def are_conflicting(
        self,
        claim_a: Claim,
        claim_b: Claim,
    ) -> tuple[bool, float]:
        """判断两个论断是否冲突。

        先进行快速主题匹配过滤，再使用 LLM 精确判断。

        Args:
            claim_a: 论断 A。
            claim_b: 论断 B。

        Returns:
            (是否冲突, 冲突置信度)
        """
        # 快速过滤：不同主题的论断不太可能冲突
        if not self._same_topic(claim_a, claim_b):
            return False, 0.0

        # 使用 LLM 精确判断
        judgment = await self._llm_judge_conflict(claim_a, claim_b)
        return judgment.is_conflicting, judgment.confidence

    async def _llm_judge_conflict(
        self,
        claim_a: Claim,
        claim_b: Claim,
    ) -> ConflictJudgment:
        """使用 LLM 判断两个论断是否存在矛盾。"""
        system_prompt = (
            "你是一个知识冲突检测专家。请客观分析两个论断是否存在实质性矛盾。\n"
            "注意区分：1) 真正的矛盾（互相排斥）2) 补充关系（互相补充）3) 范围差异（适用条件不同）"
        )

        user_prompt = f"""判断以下两个论断是否存在矛盾或冲突：

论断A（来自《{claim_a.source_book}》）：{claim_a.statement}
论断B（来自《{claim_b.source_book}》）：{claim_b.statement}

请以 JSON 格式回答：
{{"is_conflicting": true/false, "confidence": 0.0-1.0, "reason": "一句话解释"}}
"""

        response = await self.llm.chat(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            response_format="json",
        )

        try:
            data = json.loads(response)
            return ConflictJudgment(
                is_conflicting=data.get("is_conflicting", False),
                confidence=data.get("confidence", 0.0),
                reason=data.get("reason", ""),
            )
        except (json.JSONDecodeError, KeyError, TypeError):
            return ConflictJudgment(is_conflicting=False, confidence=0.0)

    def _same_topic(self, a: Claim, b: Claim) -> bool:
        """快速判断两个论断是否讨论同一主题。

        使用主题关键词匹配作为快速过滤。
        """
        if not a.subject or not b.subject:
            return False

        subj_a = a.subject.lower().strip()
        subj_b = b.subject.lower().strip()

        # 主题完全相同
        if subj_a == subj_b:
            return True

        # 主题互相包含
        if subj_a in subj_b or subj_b in subj_a:
            return True

        # 关键词交集（中文按字符拆分，至少2字重叠）
        chars_a = set(subj_a)
        chars_b = set(subj_b)
        overlap = chars_a & chars_b - {" ", "的", "了", "是", "在"}
        if len(overlap) >= 2 and len(overlap) / max(len(chars_a), len(chars_b)) > 0.4:
            return True

        return False

    @staticmethod
    def _extract_subject(statement: str) -> str:
        """从论断中提取主题关键词。"""
        # 简单启发式：取第一个分句的前半部分
        first_part = statement.split("，")[0].split(",")[0]
        # 去除常见动词
        for sep in ["是", "为", "有", "可以", "应该"]:
            if sep in first_part:
                return first_part.split(sep)[0].strip()
        return first_part[:20].strip()

    @staticmethod
    def _extract_keywords(statement: str) -> list[str]:
        """从论断中提取关键词。"""
        # 简单实现：按标点分割取关键部分
        keywords: list[str] = []
        parts = statement.replace("，", " ").replace(",", " ").split()
        for part in parts[:5]:
            cleaned = part.strip("。.!！?？")
            if len(cleaned) >= 2:
                keywords.append(cleaned)
        return keywords
