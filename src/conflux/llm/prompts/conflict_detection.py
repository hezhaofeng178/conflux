"""冲突检测 Prompt - 判断两个论断是否冲突。"""

CONFLICT_DETECTION_SYSTEM = """你是一个专业的知识冲突分析师。你的任务是判断两个论断之间是否存在冲突。

判断标准：
1. factual (事实性矛盾): 对同一事物给出不同数值/结论
2. methodological (方法论分歧): 推荐了互斥的方法
3. interpretive (解读差异): 对同一现象给出不同解释
4. temporal (时效性冲突): 新旧标准/指南的差异
5. scope (适用范围冲突): 一方说"所有"另一方说"部分"

注意：
- 互补不是冲突（A说X，B说Y，X和Y不矛盾则不是冲突）
- 不同视角不是冲突（解剖学和生理学从不同角度描述同一器官）
- 严格区分"真冲突"和"表述差异"

输出要求：返回 JSON 格式"""

CONFLICT_DETECTION_PROMPT = """判断以下两个论断之间是否存在冲突。

## 论断 A
- 来源: {source_a}
- 主题: {subject_a}
- 内容: "{statement_a}"
- 上下文: {context_a}

## 论断 B
- 来源: {source_b}
- 主题: {subject_b}
- 内容: "{statement_b}"
- 上下文: {context_b}

## 输出格式
请返回 JSON：
```json
{{
  "is_conflict": true/false,
  "confidence": 0.85,
  "conflict_type": "factual|methodological|interpretive|temporal|scope|none",
  "severity": "low|medium|high|critical",
  "analysis": {{
    "reasoning": "判断理由（100字以内）",
    "possible_reasons": ["可能的原因1", "可能的原因2"],
    "suggested_resolution": "建议的解决方向"
  }}
}}
```

请分析："""


def build_conflict_detection_prompt(
    statement_a: str,
    source_a: str,
    subject_a: str,
    context_a: str,
    statement_b: str,
    source_b: str,
    subject_b: str,
    context_b: str,
) -> tuple[str, str]:
    """构建冲突检测的 prompt 对。

    Returns:
        (system_prompt, user_prompt)
    """
    user_prompt = CONFLICT_DETECTION_PROMPT.format(
        statement_a=statement_a,
        source_a=source_a,
        subject_a=subject_a,
        context_a=context_a or "无",
        statement_b=statement_b,
        source_b=source_b,
        subject_b=subject_b,
        context_b=context_b or "无",
    )
    return CONFLICT_DETECTION_SYSTEM, user_prompt
