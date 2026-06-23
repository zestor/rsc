# Model Catalog

Reference for available AI models across video generation, image generation, and text/agent tasks. Use this to select the right model based on quality needs, cost constraints, and task complexity.

## Rating Scale

Each model is rated on three dimensions using a 1–5 relative scale:

- **Quality** (output fidelity/reasoning): ★ = basic → ★★★★★ = best-in-class
- **Speed** (generation latency): ★ = slow → ★★★★★ = fastest
- **Cost**: $ = cheapest → $$$$$ = most expensive

## Quick Decision Guide

**Video generation (`asi-generate-video`):**

- Default / cost-effective → `sora_2`
- Premium: cinematic realism, physics → `sora_2_pro`
- Premium: creative control, dialogue/audio → `veo_3_1`
- Veo quality at lower cost → `veo_3_1_fast`
- Cost-effective ByteDance generation → `seedance_2_0`

**Image generation (`asi-generate-image`):**

- Default / high-quality OpenAI image generation → `gpt_image_2`
- Transparent background → `gpt_image_1_5` with `background: "transparent"`
- Faster concept iteration → `nano_banana_2`
- Premium / highest quality → `nano_banana_pro`
- Cost-effective ByteDance generation → `seedream_5`

**Subagents (`run_subagent` tool):**

- Complex tasks (website building, asset creation, multi-step reasoning) → `claude_opus_4_8`
- General-purpose (research, data processing, writing) → `claude_sonnet_4_6`
- Budget-friendly research → `gemini_3_1_pro`
- Math, logic, structured reasoning → `gpt_5_4`

## Detailed Model Documentation

Read these files for full specifications, ratings, and selection guidance:

- **video-models.md** — Video generation models (sora_2, sora_2_pro, veo_3_1, veo_3_1_fast, seedance_2_0)
- **image-models.md** — Image generation models (nano_banana_pro, nano_banana_2, gpt_image_1_5, gpt_image_2, seedream_5)
- **text-models.md** — Text/agent models for subagents (claude_sonnet_4_6, claude_opus_4_8, gemini_3_1_pro, gpt_5_4, gpt_5_5)
- **multi-model-comparison.md** — Synthesis format for multi-model comparison (agreement/disagreement tables)

## Multi-Model Comparison

When the user asks to compare what different AI models think, wants multi-perspective analysis, or requests a "model council":

- Pick one frontier model from each of the three major providers (OpenAI, Anthropic, Google) unless the user specifies models
- Validate all requested models exist in text-models.md before proceeding
- Read **multi-model-comparison.md** for the synthesis format

## Key Guidelines

- **Use friendly names with users** — Say "Sora 2 Pro", "Claude Opus 4.8", "Veo 3.1", etc. in messages. Internal identifiers like `sora_2_pro` are only for tool `model` parameters, never shown to users.
- Website building subagents should use `claude_opus_4_8` — the complexity of multi-page sites with interactions demands top-tier reasoning
- Asset generation (PDF, DOCX, PPTX, XLSX) should use `claude_opus_4_8` — quality of output depends heavily on model capability
- For simple research or data gathering, `claude_sonnet_4_6` is sufficient and more cost-effective
- When users mention budget constraints, cost concerns, or "doesn't need to be perfect", prefer cheaper model options
- When users ask for "best quality" or the task is high-stakes, use premium models