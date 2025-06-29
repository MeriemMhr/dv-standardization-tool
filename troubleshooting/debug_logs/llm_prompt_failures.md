# LLM Prompt Failures and Inference Limitations

This document collects instances where LLM-based inference produced incorrect or ambiguous results when attempting to map dataset columns to standardized dependent variables. These examples inform future improvements to prompt engineering and schema conditioning.

---

## Failure Case 1: Ambiguous Mapping

**Input Column**: `response_time`
**LLM Suggestion**: `user_engagement_score`
**Expected Mapping**: `task_completion_time`

**Issue**: The model interpreted "response" as a qualitative reaction instead of a temporal metric. This may be due to insufficient schema context or overfitting on engagement-related terminology.

---

## Failure Case 2: Hallucinated Variable

**Input Column**: `app_usability_delta`
**LLM Suggestion**: `delta_heuristic_match_score`

**Issue**: The suggested DV does not exist in the schema and is semantically vague. LLM hallucinated a term likely inspired by heuristic evaluation literature.

---

## Failure Case 3: Misleading Generalization

**Input Column**: `trust_level_admin_mode`
**LLM Suggestion**: `system_usability_scale`

**Issue**: Model incorrectly generalized a trust-related column to usability. This likely stems from generic prompts lacking role- or system-level qualifiers.

---

## Recommendations

- Include structured schema descriptions using `schema_meta.yaml` during inference.
- Ground prompts using dataset context (e.g., study objective, participant type).
- Explore few-shot prompting or retrieval-augmented generation (RAG) for schema-aware suggestions.

---

Please add future prompt failure examples below or submit them via GitHub Issues.
