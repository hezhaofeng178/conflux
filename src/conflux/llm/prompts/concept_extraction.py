"""概念提取 Prompt - 从文本中提取结构化概念。"""

CONCEPT_EXTRACTION_SYSTEM = """你是一个专业的知识工程师。你的任务是从给定文本中提取结构化概念。

提取规则：
1. 提取重要的实体、理论、方法、过程、属性等概念
2. 为每个概念提供简洁定义
3. 识别概念类型（entity/process/theory/method/property/category）
4. 提供别名/同义词
5. 只提取文本中明确提到或可直接推断的概念
6. 忽略过于泛化的概念（如"事物"、"东西"）

输出要求：返回 JSON 格式"""

CONCEPT_EXTRACTION_PROMPT = """从以下文本中提取核心概念。

## 来源信息
- 书名: {book_title}
- 章节: {chapter_title}
- 小节: {section_title}

## 文本内容
{content}

## 输出格式
请返回 JSON，格式如下：
```json
{{
  "concepts": [
    {{
      "name": "概念名称",
      "aliases": ["别名1", "别名2"],
      "type": "entity|process|theory|method|property|category",
      "definition": "一句话定义",
      "domain": "所属领域",
      "importance": "high|medium|low"
    }}
  ],
  "relations": [
    {{
      "source": "概念A名称",
      "target": "概念B名称",
      "relation": "is_a|part_of|causes|regulates|related_to|contrasts|similar_to",
      "description": "关系描述"
    }}
  ]
}}
```

请提取："""


def build_concept_extraction_prompt(
    content: str,
    book_title: str = "未知",
    chapter_title: str = "未知",
    section_title: str = "未知",
) -> tuple[str, str]:
    """构建概念提取的 prompt 对（system, user）。

    Returns:
        (system_prompt, user_prompt)
    """
    user_prompt = CONCEPT_EXTRACTION_PROMPT.format(
        book_title=book_title,
        chapter_title=chapter_title,
        section_title=section_title or "未知",
        content=content[:6000],  # 限制输入长度
    )
    return CONCEPT_EXTRACTION_SYSTEM, user_prompt
