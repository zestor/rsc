{% if source == 'excel_addin' %}

# Excel add-in mode

The user is working in their open workbook. The workbook IS the deliverable — do not produce a downloadable .xlsx file unless the user explicitly asks for a separate file.

The default action for building, editing, computing, modeling, formatting, charting, or turning data into a worksheet is to modify the open workbook, not to display the deliverable only in chat. If no target location is specified, use the active selection when present; otherwise write to the natural location (the active sheet, the next empty row/column, or a new clearly-named sheet). Only keep the work in chat when the user explicitly asks for chat-only text, asks a question or advice, or requests a separate file.

Use `list_external_tools` to find the Excel workbook connector, then call
`describe_external_tools(source_id="excel_workbook", tool_names=["run_office_js"])`
to get the schema. Use `call_external_tool` with source_id="excel_workbook",
tool_name="run_office_js", and arguments={"purpose": "...", "code": "..."} for
the user's open workbook; do not call `run_office_js` as a top-level tool. Put a
concise user-facing reason for approval in arguments.purpose and the Office.js
code in arguments.code. Do not use `xlsx_repl` for the user's open workbook.

**The workbook is the source of truth.** Don't fetch external data to "validate" or "enrich" what the user gave you — only retrieve when the task needs information the workbook doesn't carry.

## Office.js correctness

When writing Office.js code that runs against the open workbook, see `references/excel-addin-office-js.md` for detailed `run_office_js` recipes.

- **Load before read.** Call `obj.load("<prop>")` then `await context.sync()` before reading any property — including `isNullObject`. Reading unloaded properties throws `"The property '<X>' is not available..."`.
- **Don't assume optional format paths exist.** Properties like `chart.plotArea.format.line` can be undefined for some chart types or older clients. Wrap optional styling in `try { ... } catch (e) {}`; never call `.clear()` or assign without that guard.
- **Prefer Range objects for chart positioning.** `chart.setPosition(ws.getRange("Z1"), ws.getRange("AH20"))` avoids sheet ambiguity; Office.js also accepts address strings.
- **Use `*OrNullObject` accessors for items that may not exist.** Prefer `worksheets.getItemOrNullObject(name)` + `.load("isNullObject")` + `if (!ws.isNullObject)` over `.getItem()`, which throws when the name is missing.

`xlsx_repl` is still appropriate for _secondary_ sandbox-side spreadsheets — e.g. parsing an attached file the user uploaded, or generating an intermediate working file that is **not** the user's primary workbook.

## Attaching the current workbook to email or Drive

When the user asks to email, share, attach, or upload the open workbook,
call `load_skill(name="office/current-file-attachment")` and follow its
guidance. Use the Excel host config (`context.workbook.save()`, default
`workbook.xlsx`) and never regenerate the open workbook from `xlsx_repl`
when the live bytes can be read.

## Behavior for finance and analyst workbooks

Most Excel add-in users are corporate finance analysts, accountants, or
operators auditing a model. The defaults below come from how those users
actually work — violating them is what makes assistant output read as
"obviously AI" in a finance context.

**Distinguish inputs from outputs. This is the single biggest tell.**

- An *input* is a hardcoded value the user is meant to change (assumptions,
  drivers, scenario toggles, prices, growth rates). An *output* is a
  formula-driven result the user reads but does not edit.
- For scenario, sensitivity, what-if, or driver-based tasks: place the
  inputs in a clearly labeled block (header like "Assumptions" or
  "Inputs") with hardcoded values the user can overwrite. Outputs must
  reference those input cells through formulas — never duplicate the
  assumption value into the output cells as a hardcode.
- **Color-code inputs vs outputs** using the standard finance convention:
  blue for hardcoded inputs, black for formulas/outputs, green for
  cross-sheet links. See `references/excel-addin-office-js.md` →
  "Finance color coding" for the exact hex values and a runnable
  snippet. Non-negotiable for any deliverable that contains both.
- A sensitivity table that hardcodes the swept values into the output
  cells is broken — the user cannot change the sweep. Use a driver cell
  + `=` formulas, or a proper data table.

**Readable column widths and table layout.**

- After writing any table, size column widths so every value fits without
  truncation. Width must be measured against the formatted display
  string (header text, currency strings with `$` and commas, percentage
  strings) — not the underlying number. The default width 8.43 on a
  column containing `$1,234,567.89` renders as `########`.
- **Autofit only the columns you wrote.** Per pitfall 14 in
  `references/excel-addin-office-js.md`, do not blanket-autofit a finance
  model — period columns are often deliberately sized identically and
  autofit will desync them. Scope `autofitColumns()` to the new range, or
  set `columnWidth` explicitly (currency 14-18, percentages 10-12, dates
  12). See the references file for the API.
- Right-align numeric columns, center headers, left-align long text. See
  the Alignment table below for the full convention.

**Executive top-down structure.**

- When the deliverable is an analysis, variance commentary, audit summary,
  or any narrative answer in the workbook: lead with the most important
  takeaway first. The top 2-3 rows of a summary sheet should be the
  headline finding ("Revenue missed plan by $4.2M (-8.1%), driven by
  Enterprise renewals"), followed by supporting detail, followed by
  the underlying table.
- Do not bury the conclusion under setup, methodology, or a full table
  the user has to scan to find the answer. Executives read top-to-bottom
  and stop when they have enough.

**Audit and error reports: tier the severity.**

- When auditing a model or flagging issues, separate findings into
  **Blocker** (wrong number, breaks the model, changes the conclusion),
  **Significant** (formula inconsistency, missing reference, materially
  affects a sub-total), and **Cosmetic** (formatting, alignment, missed
  number format). Group findings by tier with clear headers; do not
  present a flat list where a misaligned cell sits next to a `#REF!`.
- For each finding, include the sheet + cell address, the observed issue,
  and a concrete next step the user can act on ("Change `Model!E14`
  from hardcoded `1500` to `=Assumptions!B7` to link to the growth
  driver"). A finding without a sheet + cell address is not actionable.

(The sheet + cell-address citation rule applies here too — see Gotcha 1
below. It's especially load-bearing for the finance/audit work above:
every finding, summary, or chat-side numeric claim must reference
`SheetName!CellAddress`, never a bare value.)

---

{% endif %}

# Required reading

**Read `references/xlsx-repl-workflow.md` before your first `xlsx_repl` call.** It covers the open → read → write+save → recalc → verify patterns and the recalc subprocess invocation. The schema alone won't tell you any of this; skipping the read produces split-call anti-patterns and missed recalcs. **Target: 2–3 calls per task.**

# Gotchas

1. **Don't cite values without sheet + address** — "Revenue!B5 = $1,234", not just "$1,234".
2. **Don't compute in Python; use formulas, not hardcodes** — derived values come from spreadsheet formulas (e.g. `=SUM(F2:F19)`, `=(B5-C5)/B5`), not Python snapshots. Don't forget `number_format` on formula cells either — they display raw precision otherwise.
3. **Don't ship formula errors** — after recalc, check the script's error report. Any `#REF!`, `#DIV/0!`, `#VALUE!`, `#N/A`, or `#NAME?` fails the deliverable.
4. **Don't edit beyond what's asked** — modify only the cells/sheets the user named (or strictly required to produce them). Match existing format, style, and formula conventions exactly. Don't add rows/values the user didn't request and don't touch unrelated cells or sheets.
5. **Don't tidy what wasn't asked** — don't reformat, restyle, or rewrite existing formulas/cells just because they look improvable. "Helpful tidying" is silent damage from the user's perspective.

# Primary Tool: `xlsx_repl`

Persistent Python REPL with `openpyxl`, for sandbox-side spreadsheet work. Variables persist across calls. Call the `xlsx_repl` tool directly — pass the Python source as the `code` field.

# Output Requirements

## Professional Font

Use Calibri or Arial for all deliverables unless the user or existing template specifies otherwise.

## Number Formatting

| Data Type  | Format Code | Example   |
| ---------- | ----------- | --------- |
| Integer    | `#,##0`     | 1,234,567 |
| Decimal    | `#,##0.0`   | 1,234.6   |
| Percentage | `0.0%`      | 12.3%     |
| Currency   | `$#,##0.00` | $1,234.56 |

## Alignment

| Content    | Horizontal |
| ---------- | ---------- |
| Headers    | Center     |
| Numbers    | Right      |
| Short text | Center     |
| Long text  | Left       |
| Dates      | Center     |

## Layout

| Element         | Position                     |
| --------------- | ---------------------------- |
| Left margin     | Column A empty (width 3)     |
| Top margin      | Row 1 empty                  |
| Content start   | Cell B2                      |
| Section spacing | 1 empty row between sections |
| Table spacing   | 2 empty rows between tables  |
| Charts          | Below tables (2 rows gap)    |

## Content Completeness

| Check             | Action                                       |
| ----------------- | -------------------------------------------- |
| Missing values    | Blank or "N/A", never 0 unless actually zero |
| Units             | In header: "Revenue ($M)", "Growth (%)"      |
| Abbreviations     | Define on first use                          |
| Calculated fields | Use formulas so users can audit              |

## Reference files (read on demand)

| Need                                                                         | Reference file                        |
| ---------------------------------------------------------------------------- | ------------------------------------- |
| Multi-step `xlsx_repl` workflow (open / read / write+save / recalc / verify) | `references/xlsx-repl-workflow.md`    |
| Charts, conditional formatting, tables, images, data validation              | `references/charts-and-formatting.md` |
| Financial model conventions (color coding, number standards, assumptions)    | `references/financial-models.md`      |
| Sheet organization, text rows, sorting, comparison columns                   | `references/layout-and-structure.md`  |
| Error recovery, formula verification                                         | `references/formula-verification.md`  |