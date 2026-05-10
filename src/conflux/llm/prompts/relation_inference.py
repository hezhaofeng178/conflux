"""关系推理 Prompt - 判断两个概念之间的关系类型。"""

RELATION_INFERENCE_SYSTEM = """你是一个知识图谱构建专家。你的任务是判断两个概念之间的语义关系。

可选的关系类型：
- is_a: A 是 B 的一种（下位词关系）
- part_of: A 是 B 的组成部分
- contains: A 包含 B
- causes: A 导致 B
- caused_by: A 由 B 引起
- regulates: A 调节/控制 B
- depends_on: A 依赖于 B
- contrasts: A 与 B 形成对比
- similar_to: A 与 B 相似
- precedes: A 在时间/逻辑上先于 B
- follows: A 在时间/逻辑上后于 B
- related_to: A 与 B 相关（无法归入以上类型时使用）
- applied_in: A 应用于 B 场景
- example_of: A 是 B 的实例

规则：
1. 选择最精确的关系类型
2. 如果不确定，用 related_to
3. 给出置信度分数

输出要求：返回 JSON 格式"""

RELATION_INFERENCE_PROMPT = """判断以下两个概念之间的关系。

## 概念 A
- 名称: {concept_a_name}
- 定义: {concept_a_definition}
- 领域: {concept_a_domain}

## 概念 B
- 名称: {concept_b_name}
- 定义: {concept_b_definition}
- 领域: {concept_b_domain}

## 上下文（如有）
{context}

## 输出格式
请返回 JSON：
```json
{{
  "has_relation": true/false,
  "relation_type": "is_a|part_of|contains|causes|regulates|...",
  "direction": "a_to_b|b_to_a|bidirectional",
  "confidence": 0.85,
  "description": "关系描述（一句话）"
}}
```

请分析："""


def build_relation_inference_prompt(
    concept_a_name: str,
    concept_a_definition: str,
    concept_a_domain: str,
    concept_b_name: str,
    concept_b_definition: str,
    concept_b_domain: str,
    context: str = "",
) -> tuple[str, str]:
    """构建关系推理的 prompt 对。

    Returns:
        (system_prompt, user_prompt)
    """
    user_prompt = RELATION_INFERENCE_PROMPT.format(
        concept_a_name=concept_a_name,
        concept_a_definition=concept_a_definition or "无定义",
        concept_a_domain=concept_a_domain or "未知",
        concept_b_name=concept_b_name,
        concept_b_definition=concept_b_definition or "无定义",
        concept_b_domain=concept_b_domain or "未知",
        context=context or "无额外上下文",
    )
    return RELATION_INFERENCE_SYSTEM, user_prompt
