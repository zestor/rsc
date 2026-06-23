# Multi-Model Comparison Format

When spawning multiple subagents on different models for the same query, use this synthesis format to present their findings. The core value is analyzing **agreement and disagreement** — not merging answers, but surfacing what models converge on (high confidence) and where they diverge (nuance or uncertainty).

## Execution

Spawn one `run_subagent` per model **in a single tool-call batch** (concurrent execution). Each subagent gets the same query with this addition to the objective:

> You are one of several models independently researching this query. Bring your own analytical angle — depth on a specific facet is more valuable than surface coverage of everything.

After all subagents complete, save each model's report to a file and share via `share_file`, then synthesize below.

## Synthesis Structure

### 1. Where Models Agree

| Finding      | [Model 1] | [Model 2] | [Model 3] | Evidence                     |
| ------------ | --------- | --------- | --------- | ---------------------------- |
| [Conclusion] | ✓         | ✓         | ✓         | [Key supporting point][1][4] |

- 3-6 rows covering main agreed-upon findings
- Model columns contain ONLY ✓ or blank — no other text
- Every row must have at least two ✓ marks (single-model findings go in Unique Discoveries)
- Citations in Evidence column only

### 2. Where Models Disagree

| Topic      | [Model 1]  | [Model 2]  | [Model 3]  | Why They Differ        |
| ---------- | ---------- | ---------- | ---------- | ---------------------- |
| [Question] | [Position] | [Position] | [Position] | [Reasoning difference] |

Identify: different evidence cited, different weighting of factors, different assumptions, different data interpretations.

### 3. Unique Discoveries

Only include if at least one model surfaced a finding not mentioned by others. Omit entirely if none exist.

| Model        | Unique Finding | Why It Matters |
| ------------ | -------------- | -------------- |
| [Model Name] | [Finding][N]   | [Relevance]    |

### 4. Comprehensive Analysis

Flowing prose (NOT bullets or tables), 400-1500 words depending on query complexity:

1. **High-Confidence Findings** (2-3 paragraphs) — expand on agreements, explain why convergence means reliability
2. **Areas of Divergence** (2-4 paragraphs) — explore disagreements, why models reached different conclusions
3. **Unique Insights Worth Noting** (1-2 paragraphs) — notable unique discoveries
4. **Recommendations** (1 paragraph) — actionable guidance

## Attribution

- Always attribute to specific models using friendly display names from model-catalog: "Claude Opus 4.6 and GPT 5.4 both found that...[2][5], while Gemini 3.1 Pro noted...[9]"
- Never write generic "research shows" or "experts suggest" when you have model-specific findings

## Low-Divergence Results

When models produce similar findings:

- The "Where Models Agree" table is the primary table — populate it fully
- For "Where Models Disagree," look for emphasis, detail, framing, and completeness differences
- If genuinely zero differences, note "All models produced highly consistent findings" but still include table headers

## Query Complexity Calibration

- **Simple factual**: Quick lookups, brief synthesis
- **Opinion/evaluative**: Research perspectives and stances, highlight where stances align vs differ
- **Comprehensive research**: Deep investigation, detailed synthesis (1000-1500 words)
- **Creative**: Each model produces creative output, compare approaches and styles
