# Word add-in Office.js recipes

Invoke these recipes by calling
`describe_external_tools(source_id="word_document", tool_names=["run_office_js"])`,
then `call_external_tool` with source_id="word_document",
tool_name="run_office_js", and arguments={"purpose": "...", "code": "..."}.
Every snippet is the arguments.code value and goes inside
`await Word.run(async (context) => { ... })`.
Always `load` the properties you read, then `await context.sync()` before
reading them.

## Reading

### Document outline (paragraph count, styles, tables, content controls)

```js
return await Word.run(async (context) => {
  const body = context.document.body;
  const paragraphs = body.paragraphs;
  // List level lives on `paragraph.listItemOrNullObject.level` — there is no
  // `paragraph.listLevel`. Non-list paragraphs have `isNullObject === true`.
  paragraphs.load(
    "items/text, items/style, items/styleBuiltIn, " +
    "items/listItemOrNullObject/level, items/listItemOrNullObject/isNullObject"
  );
  const tables = body.tables;
  tables.load("items/rowCount, items/values");
  const ccs = context.document.contentControls;
  ccs.load("items/title, items/tag, items/id");
  await context.sync();
  return {
    paragraph_count: paragraphs.items.length,
    paragraphs: paragraphs.items.slice(0, 50).map((p, i) => ({
      index: i,
      text: p.text,
      style: p.style || p.styleBuiltIn,
      list_level: p.listItemOrNullObject.isNullObject ? null : p.listItemOrNullObject.level,
    })),
    table_count: tables.items.length,
    content_controls: ccs.items.map(c => ({ id: c.id, tag: c.tag, title: c.title })),
  };
});
```

### Read a paragraph range by index

```js
const paras = context.document.body.paragraphs;
paras.load("items/text, items/style");
await context.sync();
const slice = paras.items.slice(start, end + 1);
return slice.map(p => ({ text: p.text, style: p.style }));
```

### Current selection

`document.getSelection()` returns a `Word.Range`, which has no `isEmpty`
property — test emptiness with `range.text === ""` after sync.

```js
const sel = context.document.getSelection();
sel.load("text, style");
await context.sync();
return { text: sel.text, style: sel.style, is_empty: sel.text === "" };
```

## Searching

`body.search` returns a `RangeCollection` of plain `Word.Range` objects — load
properties (`text`, `style`, etc.) before reading them. Search options:
`matchCase`, `matchWholeWord`, `matchPrefix`, `matchSuffix`, `ignoreSpace`,
`ignorePunct`, and `matchWildcards`. **`matchWildcards` is Word's
Find-and-Replace wildcard syntax (`?`, `*`, `[A-Z]`, `\<`, `\>`) — not regex.**
Patterns like `(\d{4})` will not work. Iterate hits with `.items`.

```js
const hits = context.document.body.search("Quarterly revenue", { matchCase: false });
hits.load("items/text");
await context.sync();
return hits.items.map(r => r.text);
```

To replace, use `Range.insertText(replacement, "Replace")` after sync — see below.

## Inserting

`InsertLocation` string literals are PascalCase:
`"Before" | "After" | "Start" | "End" | "Replace"` (or use the typed enum
`Word.InsertLocation.before`, etc.). Lowercase string literals throw.
Some methods accept only a subset — e.g. `Table.addRows` is `"Start" | "End"`
only; `Body.insertParagraph` doesn't accept `"Replace"`.

### Append a paragraph at the end of the document

```js
context.document.body.insertParagraph("New section", "End");
await context.sync();
```

### Insert before/after the Nth paragraph

```js
const paras = context.document.body.paragraphs;
paras.load("items");
await context.sync();
paras.items[n].insertParagraph("Inserted text", "After"); // or "Before"
await context.sync();
```

### Replace a search match

```js
const hits = context.document.body.search("OLD VALUE", { matchCase: true });
hits.load("items");
await context.sync();
hits.items.forEach(r => r.insertText("NEW VALUE", "Replace"));
await context.sync();
```

### Insert at the user's selection

```js
context.document.getSelection().insertText("inline text", "Replace");
await context.sync();
```

## Deleting

```js
const paras = context.document.body.paragraphs;
paras.load("items");
await context.sync();
paras.items.slice(start, end + 1).forEach(p => p.delete());
await context.sync();
```

## Paragraph styling

Built-in styles use `Word.BuiltInStyleName` values: `"Heading1"`–`"Heading9"`,
`"Normal"`, `"Title"`, `"Subtitle"`, `"Quote"`, `"IntenseQuote"`,
`"ListParagraph"`, `"Caption"`, `"Header"`, `"Footer"`, `"FootnoteText"`,
`"Toc1"`–`"Toc9"`, etc. There is **no `"ListBullet"` or `"ListNumber"`** —
for bullets and numbering use `paragraph.startNewList()` (see below). For
custom styles defined in the document, use `paragraph.style = "MyStyleName"`.

```js
const p = context.document.body.paragraphs.getFirst();
p.styleBuiltIn = "Heading1";
p.alignment = "Centered";       // "Left"|"Centered"|"Right"|"Justified"
p.leftIndent = 36;              // points
p.spaceAfter = 6;
await context.sync();
```

> ⚠️ Trap: `paragraph.alignment` uses **`"Centered"`** but
> `tableCell.verticalAlignment` uses **`"Center"`** (no "ed"). Different enums.

### Bullet / numbered lists

```js
const para = paras.items[n];
para.startNewList();             // begin a list at this paragraph
// or attach to the existing list above:
// para.attachToList(paras.items[n-1].listOrNullObject.id, 0);
await context.sync();
```

## Inline formatting

Apply to a `Range` (paragraph, search hit, or selection) via `range.font`.

```js
const r = hits.items[0];
r.font.bold = true;
r.font.italic = false;
r.font.color = "#b91c1c";
r.font.highlightColor = "#fef3c7";
r.font.name = "Calibri";
r.font.size = 11;
await context.sync();
```

To format a sub-range, locate it with `search` (preferred — there is no
clean character-offset slice in stable Office.js):

```js
const hits = paras.items[n].search("specific phrase");
hits.load("items");
await context.sync();
hits.items.forEach(r => { r.font.bold = true; });
await context.sync();
```

## Tables

### Insert a table from a 2D array

```js
const data = [["Name", "Q1", "Q2"], ["Alice", "100", "120"], ["Bob", "90", "150"]];
const table = context.document.body.insertTable(data.length, data[0].length, "End", data);
table.styleBuiltIn = "GridTable4_Accent1";
table.headerRowCount = 1;
await context.sync();
```

### Append a row

`Table.addRows` only accepts `"Start"` or `"End"` — not `"Before"` / `"After"`.
For mid-table inserts, use `tableRow.insertRows("Before"|"After", n, values)`
on a specific row.

```js
const tables = context.document.body.tables;
tables.load("items");
await context.sync();
tables.items[0].addRows("End", 1, [["Carol", "110", "140"]]);
await context.sync();
```

### Set a single cell

```js
const t = tables.items[0];
t.getCell(rowIdx, colIdx).value = "updated";
await context.sync();
```

## Comments

```js
const hits = context.document.body.search("flagged phrase");
hits.load("items");
await context.sync();
hits.items.forEach(r => r.insertComment("Reviewer note here"));
await context.sync();
```

Read existing comments:

```js
const comments = context.document.body.getComments();
comments.load("items/content, items/authorName, items/resolved");
await context.sync();
return comments.items.map(c => ({
  author: c.authorName, text: c.content, resolved: c.resolved,
}));
```

`comment.contentRange` is a `CommentContentRange` (limited methods, mainly
`insertText`) — not a regular `Word.Range`. To get a regular range over the
commented text in the document, use `comment.getRange()`.

### Reply, resolve, delete

In review workflows, lawyers reply to comments rather than overwriting them.

```js
const comments = context.document.body.getComments();
comments.load("items/id, items/content");
await context.sync();
const c = comments.items[0];
c.reply("Agreed — will fix in next draft.");   // adds a CommentReply
c.resolved = true;                              // mark thread resolved
// c.delete();                                  // remove the whole thread
await context.sync();
```

Read replies:

```js
const c = comments.items[0];
c.replies.load("items/content, items/authorName");
await context.sync();
return c.replies.items.map(r => ({ author: r.authorName, text: r.content }));
```

## Hyperlinks

```js
const sel = context.document.getSelection();
sel.hyperlink = "https://www.perplexity.ai";
await context.sync();
```

For a search match: `hits.items[0].hyperlink = "..."`.

## Track changes

```js
context.document.changeTrackingMode = "TrackAll";  // "Off" | "TrackAll" | "TrackMineOnly"
await context.sync();
```

Accept all tracked changes — use the document-level shortcut:

```js
context.document.acceptAllRevisions();
await context.sync();
```

Or iterate manually if you need to inspect each one:

```js
const changes = context.document.body.getRange().getTrackedChanges();
changes.load("items/author, items/date, items/text, items/type");
await context.sync();
changes.items.forEach(c => c.accept());
await context.sync();
```

> ⚠️ Lawyers expect tracked changes to be accepted by the **originating
> reviewer**, not silently by an assistant. Don't run accept/reject without
> explicit instruction — see the SKILL.md guidance on track-changes etiquette.

## Sections, headers, footers

Headers and footers are per-section. Confidentiality and privilege markings
("PRIVILEGED & CONFIDENTIAL", "ATTORNEY WORK PRODUCT", "DRAFT — SUBJECT TO
REVIEW") belong in the **header** so they're visible without print preview.

```js
const sections = context.document.sections;
sections.load("items");
await context.sync();
const header = sections.items[0].getHeader("Primary"); // "Primary"|"FirstPage"|"EvenPages"
header.insertParagraph("PRIVILEGED & CONFIDENTIAL — ATTORNEY-CLIENT COMMUNICATION", "End")
      .alignment = "Centered";
await context.sync();
```

Footers work the same way — `section.getFooter("Primary")` returns a `Body`.

## Page numbers, breaks, fields

Page numbers, "Page X of Y", cross-references, and TOCs are **fields** —
the agent should never flatten them to literal text, since cross-refs
auto-update on `Fields.update()`.

### Insert a page break

```js
context.document.body.insertBreak("Page", "End");
// "Page" | "Next" | "SectionContinuous" | "SectionEven" | "SectionOdd"
// | "SectionNext" | "Line" | "LineClearLeft" | "LineClearRight" | "TextWrapping"
await context.sync();
```

### Page X of Y in the footer

`Range.insertField(insertLocation, fieldType, fieldText, removeFormatting)` is
how you insert any field type. `Word.FieldType` values include `"Page"`,
`"NumPages"`, `"Date"`, `"DocProperty"`, `"Toc"`, `"Ref"`, `"PageRef"`,
`"Hyperlink"`.

```js
const footer = context.document.sections.getFirst().getFooter("Primary");
const para = footer.insertParagraph("Page ", "End");
para.alignment = "Centered";
para.getRange("End").insertField("End", "Page");
para.getRange("End").insertText(" of ", "End");
para.getRange("End").insertField("End", "NumPages");
await context.sync();
```

### Cross-references (REF / PAGEREF)

For "see Section 2.1" and similar, use `"Ref"` against a bookmark name. Do
not retype the section number as flat text — renumbering will silently
desync the citation.

```js
const r = context.document.getSelection();
r.insertText("See Section ", "Replace");
r.getRange("End").insertField("End", "Ref", "BookmarkName", false);
await context.sync();
```

### Insert / refresh a TOC

There is no first-class `insertTOC` — use the field:

```js
context.document.body.insertParagraph("Table of Contents", "Start").styleBuiltIn = "Heading1";
context.document.body.paragraphs.getFirst().getRange("After").insertField("After", "Toc");
await context.sync();
```

Refresh fields after structural edits:

```js
context.document.fields.load("items");
await context.sync();
context.document.fields.items.forEach(f => f.updateResult());
await context.sync();
```

## Footnotes and endnotes

Critical for legal citations (Bluebook) and source notes in finance memos.

```js
const sel = context.document.getSelection();
sel.insertFootnote("See 17 C.F.R. § 240.10b-5.");   // inserts at the selection
// sel.insertEndnote("...");
await context.sync();
```

Read footnotes:

```js
const notes = context.document.body.footnotes;
notes.load("items/body/text, items/reference");
await context.sync();
return notes.items.map(n => ({ text: n.body.text }));
```

## Document properties (built-in and custom)

Compliance and records-management metadata: matter numbers, deal codenames,
retention codes. Built-in: `title`, `author`, `subject`, `company`,
`manager`, `keywords`, `comments`, `category`, `lastAuthor`, `revisionNumber`.

```js
const props = context.document.properties;
props.load("title, author, company, lastAuthor, revisionNumber");
await context.sync();
return {
  title: props.title, author: props.author, company: props.company,
  last_author: props.lastAuthor, revision: props.revisionNumber,
};
```

Custom properties:

```js
const custom = context.document.properties.customProperties;
custom.add("MatterNumber", "2026-0457");
custom.load("items/key, items/value");
await context.sync();
return custom.items.map(p => ({ key: p.key, value: p.value }));
```

## Custom XML parts

Backbone of corporate templates with databound content controls (legal doc
assembly, finance pitch templates). Don't modify or delete unless explicitly
asked — these are typically firm-managed.

```js
const parts = context.document.customXmlParts;
parts.load("items/id");
await context.sync();
// To inspect a specific part:
const xml = await parts.items[0].getXml();
await context.sync();
return xml.value;
```

## Saving

`document.save()` saves in place. For an Untitled document you can pass a
filename. **There is no `saveAs`** — to save a copy, the user must use
File → Save a Copy in the UI.

```js
context.document.save();                 // save in place
// context.document.save("Prompt", "Q3 Earnings Memo");  // Untitled docs only
await context.sync();
```

## Reading the current document as bytes

For email or Drive attachment, use the shared Office add-in recipe in
`../../current-file-attachment/references/current-file-attachment.md` with the
Word host config (`context.document.save()`, default `document.docx`). The
shared recipe covers `getFileAsync`, slice handling, compressed OOXML string
handling, and worker-side reassembly.

## Lists with custom numbering format

Legal numbering schemes (1.1, 1.1.1, (a), (i), (A)) use multi-level lists.

```js
const para = paras.items[n];
const list = para.startNewList();
list.setLevelNumbering(0, "Arabic", ["%1."]);
list.setLevelNumbering(1, "Arabic", ["%1.%2"]);
list.setLevelNumbering(2, "LowerLetter", ["(%3)"]);
list.setLevelNumbering(3, "LowerRoman", ["(%4)"]);
// Word.ListNumbering: "None" | "Arabic" | "UpperRoman" | "LowerRoman"
//                     | "UpperLetter" | "LowerLetter"
await context.sync();
```

## Images

`insertInlinePictureFromBase64` takes a Base64-encoded image (no data URI
prefix). For a remote URL, fetch the bytes in your worker first and pass the
encoded string in `code` — Office.js itself can't fetch.

```js
const img = context.document.body.insertInlinePictureFromBase64(
  base64String, "End"
);
img.width = 300;
await context.sync();
```

## Common pitfalls

1. **Reading unloaded properties** throws `"The property '<X>' is not available..."`.
   Always `obj.load("a, b, c")` then `await context.sync()` before reading.
2. **`*OrNullObject` for missing items.** Use `body.paragraphs.getFirstOrNullObject()`,
   `contentControls.getByIdOrNullObject(id)`, then check `.isNullObject` after sync.
   `.getFirst()` / `.getById()` throw when the target doesn't exist.
3. **Paragraph identity isn't stable across edits.** After inserting or deleting,
   re-`load("items")` and re-resolve indexes — don't reuse the old `items[i]` references.
4. **`InsertLocation` string literals are PascalCase** — `"Before"`, `"After"`,
   `"Start"`, `"End"`, `"Replace"`. Lowercase string literals throw. The typed
   enum (`Word.InsertLocation.before`) also works.
5. **`matchWildcards` is Word's wildcard syntax, not regex.** `?`, `*`,
   `[A-Z]`, `\<`, `\>` work; `\d`, `\w`, `(group)` do not.
6. **`Range` has no `isEmpty`.** `document.getSelection()` returns a `Range`;
   test emptiness with `range.text === ""` after sync.
7. **`paragraph.listLevel` does not exist.** Use
   `paragraph.listItemOrNullObject.level` and check `isNullObject` first.
8. **`paragraph.alignment` is `"Centered"`, but `tableCell.verticalAlignment`
   is `"Center"`.** Easy typo to make.
9. **Track changes must round-trip a sync** — set `changeTrackingMode`, sync,
   then make edits.
10. **Don't mix `Search.replace` with manual range edits in the same sync block** —
    later replacements may reference an out-of-date range. Sync between phases.
11. **No password / restrict-editing API.** There is no programmatic way to set
    or remove document protection; tell the user to do it from the UI.
12. **No `saveAs`.** `document.save(saveBehavior, fileName)` only sets the
    filename for an Untitled document. To save a copy, the user must use
    File → Save a Copy.
