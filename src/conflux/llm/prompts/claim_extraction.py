"""论断提取 Prompt - 从文本中提取可验证/可反驳的陈述。"""

CLAIM_EXTRACTION_SYSTEM = """你是一个专业的知识分析师。你的任务是从文本中提取"论断"（Claims）。

论断的定义：可以被验证或反驳的明确陈述性观点。

提取规则：
1. 只提取明确的、具体的陈述（非模糊表述）
2. 优先提取包含数据/数值/标准的论断
3. 优先提取方法论建议（"应该用X方法"）
4. 忽略纯描述性/定义性内容（除非定义本身有争议）
5. 标注论断的主题和类型

论断类型：
- factual: 事实性论断（"正常心率是60-100次/分"）
- methodological: 方法论论断（"应该用X方法而非Y方法"）
- interpretive: 解释性论断（"该现象的原因是X"）

输出要求：返回 JSON 格式"""

CLAIM_EXTRACTION_PROMPT = """从以下文本中提取可被验证或反驳的论断（Claims）。

## 来源信息
- 书名: {book_title}
- 章节: {chapter_title}
- 位置: {location}

## 文本内容
{content}

## 输出格式
请返回 JSON：
```json
{{
  "claims": [
    {{
      "statement": "论断的完整陈述",
      "subject": "论断涉及的主题（2-5个字）",
      "type": "factual|methodological|interpretive",
      "confidence": 0.9,
      "context": "相关上下文片段（50字以内）"
    }}
  ]
}}
```

请提取："""


def build_claim_extraction_prompt(
    content: str,
    book_title: str = "未知",
    chapter_title: str = "未知",
    location: str = "未知",
) -> tuple[str, str]:
    """构建论断提取的 prompt 对。

    Returns:
        (system_prompt, user_prompt)
    """
    user_prompt = CLAIM_EXTRACTION_PROMPT.format(
        book_title=book_title,
        chapter_title=chapter_title,
        location=location,
        content=content[:6000],
    )
    return CLAIM_EXTRACTION_SYSTEM, user_prompt
