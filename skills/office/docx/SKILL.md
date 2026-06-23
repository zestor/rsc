{% if source == 'word_addin' %}

# Word add-in mode

The user is working in their open Word document. The document IS the deliverable
— do not produce a downloadable .docx file unless the user explicitly asks for
a separate file.

The default action for drafting, writing, rewriting, composing, expanding,
formatting, or turning notes into prose is to modify the open document, not to
display the deliverable only in chat. If no target location is specified, use
the active selection when present; otherwise append at the end or choose the
natural insertion point from the document structure. Only keep the work in chat
when the user explicitly asks for chat-only text, asks a question or advice, or
requests a separate file.

Use `list_external_tools` to find the Word document connector, then call
`describe_external_tools(source_id="word_document", tool_names=["run_office_js"])`
to get the schema. Use `call_external_tool` with source_id="word_document",
tool_name="run_office_js", and arguments={"purpose": "...", "code": "..."} for
the open document; do not call `run_office_js` as a top-level tool. Put a
concise user-facing reason for approval in arguments.purpose and the Office.js
code in arguments.code. Do not use the `docx` npm module or the unpack/repack
XML flow described below for the open document.
Wrap each call in `await Word.run(async (context) => { ... })` and return
JSON-serializable data.

**The document is the source of truth.** Don't fetch external content to
"validate" or "enrich" what the user gave you — only retrieve when the task
needs information the document doesn't carry.

## Office.js correctness (Word)

- **Load before read.** Call `obj.load("<prop>, <prop>")` then
  `await context.sync()` before reading any property — including `isNullObject`.
  Reading unloaded properties throws `"The property '<X>' is not available..."`.
- **Use `*OrNullObject` accessors for items that may not exist.** Prefer
  `paragraphs.getFirstOrNullObject()` and
  `contentControls.getByIdOrNullObject(id)` plus `.load("isNullObject")` and an
  `if (!x.isNullObject)` guard over `.getFirst()` / `.getById()`, which throw
  when the target is missing.
- **Paragraph identity isn't stable across edits.** After inserting or deleting,
  re-fetch `body.paragraphs` and re-resolve indexes — cached
  `Word.Paragraph` references shift.
- **`InsertLocation` strings are PascalCase** —
  `"Before" | "After" | "Start" | "End" | "Replace"`. Use the PascalCase
  string literal or the typed enum member (`Word.InsertLocation.before`);
  a lowercase string literal (`"before"`) throws. Note `Table.addRows` is
  even stricter — only `"Start"` and `"End"` are accepted there.
- **Don't mix `Search.replace` with manual range edits in the same sync block.**
  Later replacements may reference out-of-date ranges. Sync between phases.

See `references/word-addin-office-js.md` for full recipes (read structure,
search & replace, paragraph + inline formatting, tables, comments, track
changes, sections/headers/footers, fields, footnotes, document properties,
custom XML parts, save, list numbering, images).

## Attaching the current document to email or Drive

When the user asks to email, share, attach, or upload the open document,
call `load_skill(name="office/current-file-attachment")` and follow its
guidance. Use the Word host config (`context.document.save()`, default
`document.docx`) and never regenerate the open document from scratch when
the live bytes can be read.

## Behavior in finance and legal documents

Most enterprise users opening this assistant in Word are corporate finance
analysts or lawyers. The defaults below come from how those users actually
work — violating them is what makes assistant output read as "obviously AI."

**Track changes is sacred.**

- On every edit, read `document.changeTrackingMode`. If it is `"TrackAll"`
  or `"TrackMineOnly"`, all insertions/deletions go through tracked. Never
  silently toggle it off.
- **Never accept or reject pre-existing tracked changes.** Each redline is
  attributed to a specific reviewer; silently changing the change record is
  functionally equivalent to forging another lawyer's edit. Only do this when
  the user explicitly instructs you to, and even then surface a confirmation
  before acting (which redlines, by which reviewer, accept or reject).
- For contract edits, default to producing a tracked-changes redline. Offer
  a clean (accepted) version separately if the user asks.

**Preserve fields and links — never flatten to text.**

- Word `REF`, `PAGEREF`, `TOC`, `DATE`, `DOCPROPERTY`, `NUMPAGES` fields and
  embedded `LINK Excel.Sheet` / OLE objects must stay as fields. Re-typing
  "Section 2.1" or a linked Excel cell as flat text breaks every downstream
  cross-reference and severs the model audit trail.
- After structural edits, refresh fields (`document.fields.items.forEach(f => f.updateResult())`)
  rather than letting them stale.
- Don't renumber legal clauses (1.1, 1.1.1, (a), (i)) without explicit
  instruction — `REF` fields anchor to the numbering and will desync.

**Match the document's number-format dialect.**

- Sample existing currency strings before inserting new ones. `$1.2bn`
  (banking lowercase), `$1.2B` (US accounting), `$1.2MM` (where M = thousand,
  MM = million) are document-specific — pick the convention already in use.
- **Negatives in parentheses, not minus signs**, in finance tables and body
  text: `($1,234)` not `-$1,234`. Dollar sign outside the parens.
- Always use comma thousand separators and consistent decimal precision per
  column (typically 1 decimal for $M, 2 for ratios/multiples).
- Right-align numeric columns. Bold subtotals with a single top border;
  bold grand totals with a double bottom border (accounting underlines).
- **Legal agreements spell out amounts, then repeat in numerals in
  parentheses**, with the words conventionally capitalized:
  `One Million Five Hundred Thousand United States Dollars ($1,500,000)`,
  `Thirty (30) days`. Use the body's existing convention — once a section
  establishes the spelled-out-then-numeral form, keep it consistent.

**Cite data sources with date stamps.**

- When inserting any sourced data point, append a footnote or below-table
  caption: `Source: Capital IQ, as of 2026-05-06`. Italic, 8–9pt,
  left-aligned. An undated source is a credibility tell to a finance reader.

**Defined terms are load-bearing.**

- In contracts, `"the Agreement"` and `"the agreement"` are different —
  capitalization triggers the contractual definition. On document open, scan
  the Definitions section and any inline `"Foo" means …` patterns to build
  a glossary, and preserve exact capitalization (and pluralization rules)
  in all generated text.
- Defined terms are typically introduced in one of two ways:
  - **Inline parenthetical** after a definition:
    `[definition] ("Defined Term")` — e.g.,
    `Perplexity AI, Inc., a Delaware corporation ("Perplexity")`.
  - **Definition form**: `"Defined Term" means [definition]`.
- The parenthetical can be more elaborate. Recognize variants like
  `(each, a "Defined Term")` and `(collectively, the "Defined Term")`
  as introducing a defined term, not as decoration.
- The defined term inside the parenthetical may be **bold**, underlined,
  plain, or — rarely — italic, or a combination. Preserve the document's
  formatting convention exactly when generating new defined-term
  introductions; don't normalize bold to plain or vice versa.
- Match the document's quote style. If existing defined terms use curly
  quotes (`"…"`), use curly quotes; if they use straight quotes (`"..."`),
  use straight quotes. Don't mix the two within a document.
- Treating a defined-term form (ALL CAPS phrase, capitalized proper noun
  followed by `("…")`, etc.) as a glossary entry rather than free text
  reduces false positives when deciding whether to alter capitalization
  or pluralization.

**Preserve confidentiality / privilege markings verbatim.**

- If the document already carries confidentiality or privilege markings —
  full forms like `PRIVILEGED & CONFIDENTIAL — ATTORNEY-CLIENT COMMUNICATION`,
  `ATTORNEY WORK PRODUCT`, `DRAFT — SUBJECT TO REVIEW`, or shorter variants
  like `ACP` or `Confidential` — they belong in the **header** on every page
  (footer alone is insufficient — must be visible without print preview).
  Never delete, move, lowercase, or alter these. Propagate them to any new
  sections or pages you create.
- **Don't add new privilege or confidentiality markings unless the user
  explicitly asks.** Adding `PRIVILEGED & CONFIDENTIAL` to a document that
  didn't have it can change how the document is treated in discovery; it
  is not a safe default.

**Use Word formatting, never literal markdown.**

- Map markdown to Word: `# heading` → `Heading 1` style, `**bold**` → bold
  font run, `*italic*` → italic font run, `> quote` → block-quote style.
- Never write literal `**`, `#`, `>`, or `- ` characters into the document
  text. Literal markdown is the canonical "obviously AI" tell.
- Apply paragraph styles (`paragraph.styleBuiltIn = "Heading1"`) rather than
  direct font formatting — preserves theme fonts and brand standards in
  corporate templates.

**Don't touch template scaffolding.**

- Detect content controls (`document.contentControls`) and custom XML parts
  (`document.customXmlParts`). These are how corporate templates databind
  data and are typically firm-managed. Insert text into a content control's
  range only — never delete the control, never modify its `tag` / `title`,
  never strip XML parts.
- Don't reformat firm-styled tables or override theme fonts/colors. "Helpful
  tidying" of a branded template is silent damage.

**Preserve placeholders verbatim.**

- `[•]`, `[_]`, `[ ]` (legal blanks), `[TBD]`, `[NTD: …]` (note to draft),
  `[XX]` (amount placeholder), `[CP comment: …]` (firm-initial pattern).
  Never auto-resolve, never reformat. They're deliberate.
- On `"clean up"` / `"finalize"` requests, **highlight the remaining
  placeholders and explain what input is still needed** — don't silently
  fill, delete, or guess at them. A finalized document with a fabricated
  amount in place of `[XX]` is worse than one that still shows `[XX]`.

**Pre-share metadata warning.**

- Before any "share" / "save as" / "export" action, scan for: tracked changes
  present, comments present, hidden text, populated `Author` /
  `LastModifiedBy`, custom document properties. Surface a checklist and
  recommend Word's Document Inspector (File → Info → Check for Issues).
  **Never claim metadata was "removed" without actually running it.**

**Never overwrite without confirmation.**

- Files like `Memo_v3_FINAL_v2.docx` follow deliberate version conventions.
  Default to versioned save with a suffix matching the existing pattern;
  ask before overwriting any path. There is no `saveAs` API — to save a
  copy, instruct the user to use File → Save a Copy.

**Comments: reply, don't replace.**

- Use `comment.reply(text)` to engage with a reviewer's comment, not edits
  that overwrite the underlying text. Use `comment.resolved = true` only
  with explicit instruction; never delete a comment thread silently.

---

{% endif %}

# Word Document Skill

Under the hood, .docx is a ZIP container holding XML parts. Creation, reading, and modification all operate on this XML structure.

**Visual and typographic standards:** Consult `skills/design-foundations/SKILL.md` for color palette, typeface selection, and layout principles (single accent color with neutral tones, no decorative graphics, WCAG-compliant contrast). Use widely available sans-serif typefaces like Arial or Calibri as your baseline.

## Choosing an approach

| Objective                      | Technique                                           | Reference                                        |
| ------------------------------ | --------------------------------------------------- | ------------------------------------------------ |
| Create a document from scratch | `docx` npm module (JavaScript)                      | See CREATION.md                                  |
| Edit an existing file          | Unpack to XML, modify, repack                       | See EDITING.md                                   |
| Pull out text                  | `pandoc document.docx -o output.md`                 | Append `--track-changes=all` for redline content |
| Handle legacy .doc format      | `soffice --headless --convert-to docx file.doc`     | Convert before any XML work                      |
| Rebuild from a PDF             | Run `pdf2docx`, then patch issues                   | See below                                        |
| Export pages as images         | `soffice` to PDF, then `pdftoppm`                   | See below                                        |
| Flatten tracked changes        | `python scripts/accept_changes.py in.docx out.docx` | Requires LibreOffice                             |

All tools referenced above (`pandoc`, `soffice`, `pdftoppm`, `docx` npm module, `pdf2docx`) are pre-installed in the sandbox.

## PDF to Word

Start by running `pdf2docx` to get a baseline .docx, then correct any artifacts. Never skip the automated conversion and attempt to rebuild manually.

```python
from pdf2docx import Converter

parser = Converter("source.pdf")
parser.convert("converted.docx")
parser.close()
```

Once you have the converted file, address any problems (misaligned tables, broken hyperlinks, shifted images) by unpacking and editing the XML directly (see EDITING.md).

## Image rendering

```bash
soffice --headless --convert-to pdf document.docx
pdftoppm -jpeg -r 150 document.pdf page
ls page-*.jpg   # always ls to discover actual filenames — zero-padding varies by page count
```

Validation runs automatically when the document is shared. If issues are found, fix the XML and re-share.