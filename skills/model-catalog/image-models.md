# Image Generation Models

Use the `model` parameter in `asi-generate-image` to select an image model.

## nano_banana_2 (Nano Banana 2)

- Fast image generation based on Gemini 3.1 Flash
- 1:1 aspect ratio
- Versatile styles: photorealistic, illustrations, artistic, abstract
- Supports up to 14 reference images for img2img / style transfer

**Strengths:** Faster generation, cost-effective, good quality for most tasks.

**When to use:**

- General image generation tasks
- Photos, illustrations, artistic images, decorative graphics
- Iterating on image concepts quickly
- AI-powered edits (remove background, change colors, add/remove objects)
- Style transfer from reference images

**Not suitable for:**

- Charts, graphs, timelines, infographics (AI hallucinates data — use Python libraries instead)
- Images requiring specific text, numbers, or labels
- Precise measurements or technical diagrams

---

## nano_banana_pro (Nano Banana Pro)

- High-quality image generation
- 1:1 aspect ratio
- Versatile styles: photorealistic, illustrations, artistic, abstract
- Supports up to 14 reference images for img2img / style transfer

**Strengths:** Strong prompt following, diverse style range, effective reference image incorporation.

**When to use:**

- Premium image generation where maximum quality matters
- High-stakes or client-facing images
- Style transfer from reference images

**Not suitable for:**

- Charts, graphs, timelines, infographics (AI hallucinates data — use Python libraries instead)
- Images requiring specific text, numbers, or labels
- Precise measurements or technical diagrams

---

## gpt_image_1_5 (GPT Image 1.5)

- OpenAI image generation model
- Supported aspect ratios: 1:1, 3:2, 2:3
- Supports `background` parameter for transparency control (`transparent`, `opaque`, or `auto`)
- Only available image model that supports transparent backgrounds
- Supports up to 16 reference images for img2img / style transfer

**Strengths:** Transparent background support, strong text rendering in images, high photorealism.

**When to use:**

- Images that need transparent backgrounds (icons, logos, sprites, overlays)

**Not suitable for:**

- General default image generation where `gpt_image_2` is available
- Charts, graphs, timelines, infographics (AI hallucinates data — use Python libraries instead)
- Precise measurements or technical diagrams

---

## gpt_image_2 (GPT Image 2) — default

- OpenAI's newest image generation model, successor to `gpt_image_1_5`
- Supports custom resolutions up to 3840px:
  - Both edges must be multiples of 16px
  - Long to short edge ratio must not exceed 3:1
  - Total pixels must be at least 655,360 and no more than 8,294,400
- Does **not** support transparent backgrounds. Use `gpt_image_1_5` if transparency is required.
- Supports up to 16 reference images for img2img / style transfer

**Strengths:** Very reliable in-image text, strict layouts, and complex multi-step visual instructions.

**When to use:**

- High-quality OpenAI image generation where transparent backgrounds are not needed

**Not suitable for:**

- Images that need transparent backgrounds (use `gpt_image_1_5` instead)
- Charts, graphs, timelines, infographics (AI hallucinates data — use Python libraries instead)
- Precise measurements or technical diagrams

---

## seedream_5 (Seedream 5)

- ByteDance image generation model
- Good quality at very low cost
- Supports text-to-image and reference-image workflows
- Supports up to 14 reference images for img2img / style transfer
- LLM API model ID: `seedream_5`

**Strengths:** Cost-effective generation, fast iteration, broad style coverage for general visual assets.

**When to use:**

- Budget-conscious image generation
- Producing many variations to choose from
- General photos, illustrations, decorative graphics, and concept images

**Not suitable for:**

- Transparent backgrounds (use `gpt_image_1_5` instead)
- Charts, graphs, timelines, infographics (AI hallucinates data — use Python libraries instead)
- Precise measurements or technical diagrams

---

## Default

If `model` is not specified, `generate_image` uses **gpt_image_2**.

## Selection Summary

| Scenario                         | Model            |
| -------------------------------- | ---------------- |
| General-purpose / default        | gpt_image_2      |
| Budget constraints               | seedream_5       |
| Quick drafts / iteration         | nano_banana_2    |
| Premium / highest quality        | nano_banana_pro  |
| Transparent backgrounds          | gpt_image_1_5    |
| Strict layouts or in-image text  | gpt_image_2      |
| User hasn't specified preference | gpt_image_2      |
