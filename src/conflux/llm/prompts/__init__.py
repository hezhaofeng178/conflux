"""LLM Prompts package - 各模块的 Prompt 模板。"""

from conflux.llm.prompts.concept_extraction import CONCEPT_EXTRACTION_PROMPT, build_concept_extraction_prompt
from conflux.llm.prompts.claim_extraction import CLAIM_EXTRACTION_PROMPT, build_claim_extraction_prompt
from conflux.llm.prompts.conflict_detection import CONFLICT_DETECTION_PROMPT, build_conflict_detection_prompt
from conflux.llm.prompts.relation_inference import RELATION_INFERENCE_PROMPT, build_relation_inference_prompt

__all__ = [
    "CONCEPT_EXTRACTION_PROMPT",
    "build_concept_extraction_prompt",
    "CLAIM_EXTRACTION_PROMPT",
    "build_claim_extraction_prompt",
    "CONFLICT_DETECTION_PROMPT",
    "build_conflict_detection_prompt",
    "RELATION_INFERENCE_PROMPT",
    "build_relation_inference_prompt",
]
