{% if source == 'powerpoint_addin' %}

# PowerPoint add-in mode

The user is working in their open PowerPoint presentation. The presentation
IS the deliverable — do not produce a downloadable .pptx file unless the
user explicitly asks for a separate file.

The default action for building, drafting, writing, rewriting, expanding,
formatting, or turning notes into slides is to modify the open presentation,
not to display the deliverable only in chat. If no target location is
specified, use the active/selected slide when present; otherwise append a new
slide at the end or choose the natural insertion point from the deck
structure. Only keep the work in chat when the user explicitly asks for
chat-only text, asks a question or advice, or requests a separate file.

Use `list_external_tools` to find the PowerPoint presentation connector, then
call `describe_external_tools(source_id="powerpoint_presentation", tool_names=["run_office_js"])`
to get the schema. Use `call_external_tool` with
source_id="powerpoint_presentation", tool_name="run_office_js", and
arguments={"purpose": "...", "code": "..."} for the open deck; do not call
`run_office_js` as a top-level tool. Put a concise user-facing reason for
approval in arguments.purpose and the Office.js code in arguments.code. Do not
use the `pptxgenjs` flow or the unpack/repack XML flow described below for the
open deck. Wrap each call in `await PowerPoint.run(async (context) => { ... })`
and return JSON-serializable data.

**The presentation is the source of truth.** Don't fetch external content to
"validate" or "enrich" what the user gave you — only retrieve when the task
needs information the deck doesn't carry.

## Office.js correctness (PowerPoint)

- **Load before read.** Call `obj.load("<prop>, <prop>")` then
  `await context.sync()` before reading any property — including
  `isNullObject`. Reading unloaded properties throws `"The property '<X>' is
  not available..."`.
- **Use `*OrNullObject` accessors for items that may not exist.** Prefer
  `slides.getItemOrNullObject(id)`, `shapes.getItemOrNullObject(id)`,
  `tags.getItemOrNullObject(key)`, plus `.load("isNullObject")` and an
  `if (!x.isNullObject)` guard over `.getItem()`, which throws when the
  target is missing.
- **`textFrame` throws on shapes that don't support text** (images, lines,
  media). Prefer `shape.getTextFrameOrNullObject()` (`PowerPointApi 1.10`)
  and check `isNullObject` after `load("isNullObject")` + `sync`. On older
  clients, fall back to filtering by `type` (e.g. only `"GeometricShape"`,
  `"TextBox"`, `"Placeholder"`) or wrapping each access in `try/catch`.
- **`Table.getCellOrNullObject(r, c)` is the cell accessor — there is no
  plain `getCell`.** Cells inside merged regions return `isNullObject: true`
  unless they are the top-left cell of the merge.
- **Active slide = `getSelectedSlides().getItemAt(0)`.** That collection's
  first item is the slide visible in the editing area. Empty if nothing is
  selected — guard with `getCount()`.
- **Enum strings differ from Word/Excel.** PowerPoint's
  `ParagraphHorizontalAlignment` uses `"Center"` (Word uses `"Centered"`).
  PowerPoint has no `InsertLocation` at all — there's no insert-before /
  insert-after for shapes; reorder with `setZOrder` (`PowerPointApi 1.8`).
- **No save / no undo API.** Don't claim you "saved the deck" — there is no
  `presentation.save()`, and the user's Undo stack does not reliably reverse
  add-in edits. Confirm destructive operations before issuing them.

See `references/powerpoint-addin-office-js.md` for full recipes (read
structure, slides, shapes + text, tables, hyperlinks, tags, layouts,
images, slide images / Base64 export, and the `PowerPointApi` requirement
sets that gate each method).

## Attaching the current presentation to email or Drive

When the user asks to email, share, attach, or upload the open deck, call
`load_skill(name="office/current-file-attachment")` and follow its
guidance. Use the PowerPoint host config (no programmatic save API,
default `presentation.pptx`) and never regenerate the open deck from
scratch when the live bytes can be read.

---

{% endif %}

# PPTX Skill

## Choosing an approach

| Objective                           | Technique                                | Reference                                   |
| ----------------------------------- | ---------------------------------------- | ------------------------------------------- |
| Extract text or data                | `python -m markitdown presentation.pptx` | Also: `slides.py thumbnail` for visual grid |
| Modify an existing file or template | Unpack to XML, edit, repack              | See [EDITING.md](EDITING.md)                |
| Generate a deck from scratch        | JavaScript with `pptxgenjs`              | See [CREATING.md](CREATING.md)              |

Pre-installed sandbox packages: `markitdown[pptx]`, `Pillow`, `pptxgenjs` (Node), `react-icons` + `react` + `react-dom` + `sharp` (icon rendering), LibreOffice (`soffice`), Poppler (`pdftoppm`).

---

## Math and Equations

Render equations with Unicode math symbols only. Do not use OMML or generate equation images — LibreOffice cannot display either during visual QA.

---

## Design Ideas

**Design defaults:** See `skills/design-foundations/SKILL.md` for palette, fonts + pairings, chart colors, and core principles (1 accent + neutrals, no decorative imagery, accessibility). Below is **slides-specific** guidance only.

### Before Starting

- **No icons** unless the user explicitly asks. Icons next to headings, in colored circles, or as bullet decorations are visual clutter. Only include icons when data or content requires them (chart selector, logo).
- **Accent at 10-15% visual weight**: Neutral tones fill backgrounds and body text (85-90%). Never give multiple hues equal weight.
- **Dark/light contrast**: Dark backgrounds for title + conclusion slides, light for content ("sandwich" structure). Or commit to dark throughout for a premium feel.
- **Commit to a structural motif**: Pick ONE structural element and repeat it — rounded card frames, consistent header bars, background color blocks, or bold typographic weight. Carry it across every slide. Avoid colored side borders on cards (a hallmark of AI-generated slides).

### Color Selection

**Derive color from the content itself.** Don't pick from a preset list — let the subject matter guide the accent:

- _Financial report_ → deep navy or charcoal conveys authority
- _Sustainability pitch_ → muted forest green ties to the topic
- _Healthcare overview_ → calming blue or teal builds trust
- _Creative brief_ → warmer accent (terracotta, berry) adds energy

Build every palette as **1 accent + neutral surface + neutral text**. The accent is for emphasis only (headings, key data, section markers) — everything else stays neutral. See `skills/design-foundations/SKILL.md` for the full "Earn Every Color" philosophy, contrast rules, and the custom-palette workflow (user hue → derive surfaces by desaturating → test contrast).

**When no topic-specific color is obvious**, fall back to the Nexus palette: teal `#01696F` accent on warm beige `#F7F6F2` (see `skills/design-foundations/SKILL.md` → Default Palette).

### For Each Slide

**Use layout variety for visual interest** — columns, grids, and whitespace keep slides engaging without decoration.

**Layout options:**

- Two-column (text left, supporting content right)
- Labeled rows (bold header + description)
- 2x2 or 2x3 grid of content blocks
- Half-bleed background with content overlay
- Full-width stat callout with large number and label

**Data display:**

- Large stat callouts (big numbers 60-72pt with small labels below)
- Comparison columns (before/after, pros/cons, side-by-side options)
- Timeline or process flow (numbered steps, arrows)

### Typography

See `skills/design-foundations/SKILL.md` for font pairings (Slides Pairings table) and size hierarchy. Default to professional sans-serif. Use serif for headings only when formal tone is needed.

### Spacing

- 0.5" minimum margins
- 0.3-0.5" between content blocks
- Leave breathing room—don't fill every inch

### Avoid (Common Mistakes)

- **Don't repeat the same layout** — vary columns, cards, and callouts across slides
- **Don't center body text** — left-align paragraphs and lists; center only titles
- **Don't skimp on size contrast** — titles need 36pt+ to stand out from 14-16pt body
- **Don't mix spacing randomly** — choose 0.3" or 0.5" gaps and use consistently
- **Don't style one slide and leave the rest plain** — commit fully or keep it simple throughout
- **Don't rely on plain title + bullets** — use layout variety (columns, stat callouts, grids) for structure; typography and whitespace are your primary visual tools
- **Don't forget text box padding** — when aligning lines or shapes with text edges, set `margin: 0` on the text box or offset the shape to account for padding
- **Don't use low-contrast elements** — text needs strong contrast against the background; avoid light text on light backgrounds or dark text on dark backgrounds
- **NEVER use accent lines under titles** — these are a hallmark of AI-generated slides; use whitespace or background color instead
- **NEVER use colored side borders on cards/shapes** — `border-left: 3px solid <accent>` is another AI-generated hallmark. Use background color, subtle neutral borders, or whitespace to separate content blocks
- **NEVER leave orphan shapes** — if you add a circle/oval as an icon background, the icon MUST render successfully inside it. If the icon fails (import error, sharp error), remove BOTH the icon AND its background shape. A stray white circle on a slide is a critical visual bug.
- **NEVER use `bullet: true` on large stat text** — bullets at 60-72pt render as giant dots. Only use bullets on body-sized text (14-16pt)
- **NEVER use `bullet: true` on all text in a slide** — bullet points should only be used for actual lists of 3+ items. Don't bullet a title, subtitle, description, or stat. Bullets on every text element makes slides look like a Word document
- **NEVER use gradient backgrounds on shapes or text** — solid colors are more professional. Gradients on buttons, cards, or text blocks are a template cliché
- **NEVER use generic filler phrases** — "Empowering your journey", "Unlock the power of...", "Your all-in-one solution". Use specific, concrete language that could only describe this actual content

## Source Citations

Every slide that uses information gathered from web sources MUST have a source attribution line at the bottom of the slide using **hyperlinked source names** — each source name is displayed as clickable text linking to the full URL. Always use "Source:" (singular). Use an array of text objects with `hyperlink` options.

```javascript
slide.addText(
  [
    { text: 'Source: ' },
    { text: 'Reuters', options: { hyperlink: { url: 'https://reuters.com/article/123' } } },
    { text: ', ' },
    {
      text: 'WHO',
      options: { hyperlink: { url: 'https://who.int/publications/m/item/update-42' } },
    },
    { text: ', ' },
    { text: 'World Bank', options: { hyperlink: { url: 'https://worldbank.org/en/topic/water' } } },
  ],
  { x: 0.5, y: 5.2, w: 9, h: 0.3 },
);
```

- Each source name MUST have a `hyperlink.url` with the full `https://` URL — never omit hyperlinks
- WRONG: `"Sources: WHO, Reuters, UNICEF"` (plain text, no hyperlinks)
- WRONG: `"Source: WHO, https://who.int/report/123"` (raw URL in text instead of hyperlink)
- RIGHT: `[{ text: "WHO", options: { hyperlink: { url: "https://who.int/report/123" } } }]` (clickable name)

---

## QA (Required — do not skip any step)

Every pptx task MUST complete ALL three QA steps below before delivering the file. Skipping any step is a failure.

### Step 1: Content QA

Run markitdown on the output file and review the extracted text:

```bash
python -m markitdown output.pptx
```

Check for missing content, typos, wrong order.

When using templates, check for leftover placeholder text:

```bash
python -m markitdown output.pptx | grep -iE "xxxx|lorem|ipsum|this.*(page|slide).*layout"
```

If grep returns results, fix them before proceeding.

### Step 2: Visual QA via subagent

You MUST delegate visual inspection to a subagent. Do NOT read slide images yourself — you've been staring at the code and will see what you expect, not what's there. Subagents have fresh eyes.

1. Convert slides to images:

```bash
soffice --headless --convert-to pdf output.pptx
pdftoppm -jpeg -r 150 output.pdf slide
ls slide-*.jpg   # always ls — zero-padding varies by page count
```

2. Call `run_subagent` with the slide images and this prompt (use actual filenames from `ls`):

```
Visually inspect these slides. Assume there are issues — find them.

Check for: stray dots/circles (orphan shapes, bullets at display size — any unexpected circle is likely this bug), overlapping elements, text overflow/cutoff, decorative lines mispositioned after title wrap, source footers colliding with content, elements too close (< 0.3" gaps), uneven spacing, insufficient slide-edge margins (< 0.5"), misaligned columns, low-contrast text or icons, narrow text boxes causing excessive wrapping, leftover placeholder content.

For each slide, list ALL issues found, even minor ones.

Read and analyze these images:
1. /path/to/slide-1.jpg (Expected: [brief description])
2. /path/to/slide-2.jpg (Expected: [brief description])
```

### Step 3: Fix-and-verify cycle

Fix every issue the subagent found, then re-verify:

1. Fix issues identified by the subagent
2. Re-convert affected slides to images (`soffice` + `pdftoppm`)
3. Verify fixes visually (subagent or self-review for re-checks)

At least one fix-and-verify cycle before delivering the file. Fixes create new problems — always re-check.

---

## Converting to Images

To re-render specific slides after fixes:

```bash
pdftoppm -jpeg -r 150 -f N -l N output.pdf slide-fixed
ls slide-fixed-*.jpg
```