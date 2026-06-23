# Video Generation Models

Use the `model` parameter in `asi-generate-video` to select a video model.

## sora_2 (OpenAI Sora 2) — default

- Quality: ★★★ | Speed: ★★★★ | Cost: $
- Resolution up to 720p
- Duration: 4, 8, or 12 seconds
- Aspect ratios: 16:9 (landscape), 9:16 (portrait)
- Supports audio and 1 reference image for image-to-video

**Strengths:** Fast iteration, good for simple to moderate scenes, strong physics simulation for the price.

**When to use:**

- General-purpose video generation
- Social media clips
- Rapid prototyping and iteration
- Generating multiple variations to choose from
- Budget-conscious projects

---

## sora_2_pro (OpenAI Sora 2 Pro)

- Quality: ★★★★★ | Speed: ★★★ | Cost: $$$
- Resolution up to 1080p
- Duration: 4, 8, or 12 seconds
- Aspect ratios: 16:9 (landscape), 9:16 (portrait)
- Supports audio and up to 5 reference images for image-to-video

**Strengths:** Best-in-class physics simulation, cinematic motion, tight audio synchronization. Objects respond to gravity, momentum, and collisions realistically.

**When to use:**

- Cinematic or photorealistic content
- Scenes requiring realistic physics and motion
- Professional marketing videos where realism matters
- When tight audio-visual synchronization is critical

---

## veo_3_1 (Google Veo 3.1)

- Quality: ★★★★★ | Speed: ★★ | Cost: $$$
- Resolution up to 1080p
- Duration: 4, 6, or 8 seconds
- Aspect ratios: 16:9 (landscape), 9:16 (portrait)
- Native audio generation (dialogue via speaker labels, sound effects via [brackets])
- Supports up to 3 reference images for image-to-video

**Strengths:** Creative control, composability (image-to-video workflows), strong prompt following, natural camera movements. Best native audio generation with dialogue support.

**When to use:**

- Content requiring dialogue or complex audio design
- Image-to-video animation workflows
- Multi-element scenes needing precise creative control
- Brand content where specific visual direction matters

---

## veo_3_1_fast (Google Veo 3.1 Fast)

- Quality: ★★★★ | Speed: ★★★★ | Cost: $$
- Resolution up to 1080p
- Duration: 4, 6, or 8 seconds
- Aspect ratios: 16:9 (landscape), 9:16 (portrait)
- Native audio generation (dialogue, sound effects)
- Supports up to 3 reference images for image-to-video

**Strengths:** Same creative control and audio capabilities as veo_3_1, but generates ~2x faster. Nearly indistinguishable quality in most cases.

**When to use:**

- When you want Veo quality but at lower cost
- Faster turnaround on Veo-style content
- Good default when user asks for "Veo" without specifying quality tier
- Iterating on Veo content before committing to standard quality

---

## seedance_2_0 (Seedance 2.0)

- Quality: ★★★★ | Speed: ★★★★ | Cost: $
- Resolution: 720p
- Duration: 4, 6, 8, or 12 seconds
- Aspect ratios: 16:9 (landscape), 9:16 (portrait)
- Supports up to 9 reference images for image-to-video
- Generates native synchronized audio, including sound effects, ambient sound, music, and lip-synced dialogue

**Strengths:** Cost-effective ByteDance video generation, good motion quality, useful for quick drafts and generating multiple variations.

**When to use:**

- Budget-conscious video generation
- Quick drafts and iteration
- Generating multiple variations to compare
- Short social clips and general motion concepts

---

## Default

If `model` is not specified, `generate_video` uses **sora_2**.

## Selection Summary

| Scenario                         | Model                   |
| -------------------------------- | ----------------------- |
| General-purpose / default        | sora_2                  |
| Budget constraints               | sora_2                  |
| Quick drafts / iteration         | sora_2                  |
| Low-cost video variations        | seedance_2_0            |
| Cinematic realism, physics       | sora_2_pro              |
| Veo quality at lower cost        | veo_3_1_fast            |
| Dialogue / complex audio         | veo_3_1 or veo_3_1_fast |
| Image-to-video animation         | veo_3_1 or veo_3_1_fast |
| Creative control / composability | veo_3_1 or veo_3_1_fast |
| User wants "best quality"        | sora_2_pro or veo_3_1   |
| User hasn't specified preference | sora_2 (default)        |
