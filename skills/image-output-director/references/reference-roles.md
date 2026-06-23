# Reference Image Roles

Read this when the user provides or mentions reference images.

## Role Taxonomy

Assign each reference one or more roles. Do not use a reference for roles the user did not imply.

| Role | Preserve | Do not infer |
|---|---|---|
| Subject | identity, shape, product details, pose, visible attributes | unseen features, brand claims, hidden text |
| Composition | framing, camera angle, scale, negative space, layout | subject identity or style |
| Style | palette, material, lighting, rendering language, texture | exact artwork, protected characters, exact composition |
| Mood | emotional tone, energy, atmosphere | specific objects or factual claims |
| Brand | supplied logo, colors, typography, product rules | missing logos, partner marks, campaign claims |

## Conflicts

If references conflict, preserve the priority explicitly requested by the user. If no priority is given:

1. Subject or product fidelity.
2. Composition.
3. Style.
4. Mood.

State the reference use briefly only when it helps the user understand the output.

## Provenance and Safety

For user-provided products or owned assets, preserve only the requested visible features.

For third-party brand references, use broad art direction unless the user provides exact brand assets and asks for brand-consistent work.

For real logos or marks, do not invent, approximate, or hallucinate. Preserve an explicitly provided mark or use fictional placeholder branding.

For real-person likeness, avoid deceptive, compromising, sexual, political, medical, criminal, or evidentiary contexts. If uncertain, ask briefly or keep the depiction clearly fictional.

If a reference depicts an identifiable real person, the Trust Boundaries in `SKILL.md` apply, including for edits, face transfer, de-aging, and likeness-style transfer. Do not assume consent because the user supplied the image.
