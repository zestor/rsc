# PowerPoint add-in Office.js recipes

Invoke these recipes by calling
`describe_external_tools(source_id="powerpoint_presentation", tool_names=["run_office_js"])`,
then `call_external_tool` with source_id="powerpoint_presentation",
tool_name="run_office_js", and arguments={"purpose": "...", "code": "..."}.
Every snippet is the arguments.code value and goes inside
`await PowerPoint.run(async (context) => { ... })`. Always `load` the properties
you read, then `await context.sync()` before reading them.

## Presentation structure

### Inventory the presentation (slides, masters, layouts, selection)

```js
return await PowerPoint.run(async (context) => {
  const pres = context.presentation;
  pres.load("title, id");
  const slides = pres.slides;
  slides.load("items/id, items/index");
  const masters = pres.slideMasters;
  masters.load("items/id, items/name, items/layouts/items/id, items/layouts/items/name");
  const selectedSlides = pres.getSelectedSlides();
  selectedSlides.load("items/id, items/index");
  await context.sync();
  return {
    title: pres.title,
    slide_count: slides.items.length,
    slides: slides.items.map(s => ({ id: s.id, index: s.index })),
    selected_slide_ids: selectedSlides.items.map(s => s.id),
    masters: masters.items.map(m => ({
      id: m.id,
      name: m.name,
      layouts: m.layouts.items.map(l => ({ id: l.id, name: l.name })),
    })),
  };
});
```

`Slide.index` is `PowerPointApi 1.8`. `Presentation.id` is `1.5`. Both `slides`
and `slideMasters` are read via the standard collection pattern.

### Get the active slide (and its shapes)

`getSelectedSlides()` returns a `SlideScopedCollection`; the **first item is
the active slide visible in the editing area**. If nothing is selected the
collection is empty — guard with `getCount()` before `getItemAt(0)`.

```js
const slides = context.presentation.getSelectedSlides();
const count = slides.getCount();
await context.sync();
if (count.value === 0) return { error: "No slide selected" };
const slide = slides.getItemAt(0);
slide.load("id, index");
const shapes = slide.shapes;
shapes.load("items/id, items/name, items/type, items/left, items/top, items/width, items/height");
await context.sync();
return {
  slide_id: slide.id,
  slide_index: slide.index,
  shapes: shapes.items.map(s => ({
    id: s.id, name: s.name, type: s.type,
    left: s.left, top: s.top, width: s.width, height: s.height,
  })),
};
```

### Read a slide's text content

`shape.textFrame` throws `InvalidArgument` for shapes that don't support text
(images, lines, media). On `PowerPointApi 1.10` use
`shape.getTextFrameOrNullObject()` and check `isNullObject`; on older clients,
filter by `type` or wrap each access in `try/catch`.

```js
// 1.10+: null-object guard, no try/catch needed.
const slide = context.presentation.slides.getItemAt(slideIdx);
const shapes = slide.shapes;
shapes.load("items/id, items/type, items/name");
await context.sync();
const frames = shapes.items.map(s => ({ s, tf: s.getTextFrameOrNullObject() }));
frames.forEach(({ tf }) => tf.load("isNullObject"));
await context.sync();
const withText = frames.filter(({ tf }) => !tf.isNullObject);
withText.forEach(({ tf }) => tf.textRange.load("text"));
await context.sync();
return withText.map(({ s, tf }) => ({
  id: s.id, name: s.name, type: s.type, text: tf.textRange.text,
}));
```

```js
// 1.4–1.9 fallback: filter by type before touching textFrame.
const slide = context.presentation.slides.getItemAt(slideIdx);
const shapes = slide.shapes;
shapes.load("items/id, items/type, items/name");
await context.sync();
const textShapes = shapes.items.filter(s =>
  s.type === "GeometricShape" || s.type === "TextBox" || s.type === "Placeholder"
);
textShapes.forEach(s => s.textFrame.textRange.load("text"));
await context.sync();
return textShapes.map(s => ({
  id: s.id, name: s.name, type: s.type, text: s.textFrame.textRange.text,
}));
```

## Slides

### Add a slide using a specific layout

`slides.add` is `PowerPointApi 1.3`. **Both `slideMasterId` and `layoutId`
must come from the live `slideMasters` collection** — hardcoded IDs from a
different deck won't resolve.

```js
const masters = context.presentation.slideMasters;
masters.load("items/id, items/layouts/items/id, items/layouts/items/name");
await context.sync();
const master = masters.items[0];
const layout = master.layouts.items.find(l => l.name === "Title and Content")
             ?? master.layouts.items[0];
context.presentation.slides.add({
  slideMasterId: master.id,
  layoutId: layout.id,
});
await context.sync();
```

`slides.add()` returns `void` — to keep working with the new slide, re-load
`slides` after `sync` and pick the last item.

### Insert slides from another .pptx (Base64)

```js
context.presentation.insertSlidesFromBase64(base64, {
  formatting: PowerPoint.InsertSlideFormatting.useDestinationTheme,
  // targetSlideId optional — omit to append at end.
});
await context.sync();
```

### Reorder, delete, select slides

```js
const slide = context.presentation.slides.getItemAt(2);
slide.moveTo(0);                              // 1.8
await context.sync();

context.presentation.slides.getItemAt(0).delete();   // 1.2
await context.sync();

context.presentation.setSelectedSlides([slideId1, slideId2]);   // 1.5
await context.sync();
```

### Apply a layout to an existing slide

```js
const slide = context.presentation.slides.getItemAt(0);
const master = context.presentation.slideMasters.getItemAt(0);
master.layouts.load("items/name, items/id");
await context.sync();
const layout = master.layouts.items.find(l => l.name === "Section Header");
slide.applyLayout(layout);   // 1.8
await context.sync();
```

### Render a slide as a PNG (Base64)

```js
const slide = context.presentation.getSelectedSlides().getItemAt(0);
const png = slide.getImageAsBase64({ height: 720 });   // 1.8
await context.sync();
return png.value;   // Base64 PNG; pair with `data:image/png;base64,...` to display
```

`exportAsBase64()` (1.8) returns the entire slide as a single-slide .pptx file.

## Shapes

`ShapeCollection` lives on `slide.shapes`. The four insert methods are:

| Method                | Returns         | Requirement set |
| --------------------- | --------------- | --------------- |
| `addGeometricShape`   | `Shape`         | 1.4             |
| `addTextBox`          | `Shape`         | 1.4             |
| `addLine`             | `Shape`         | 1.4             |
| `addTable(r, c)`      | `Shape` (table) | 1.8             |

`ShapeCollection.addPicture(base64, options?)` exists but is **preview-only**
as of 1.10 — don't rely on it in production. For stable code, create a
geometric shape and call `shape.fill.setImage(base64)` (`PowerPointApi 1.8`).

### Add a text box

```js
const slide = context.presentation.getSelectedSlides().getItemAt(0);
const tb = slide.shapes.addTextBox("Hello world", {
  left: 50, top: 50, width: 400, height: 60,
});
tb.name = "Title";
tb.textFrame.textRange.font.size = 28;
tb.textFrame.textRange.font.bold = true;
tb.textFrame.textRange.font.color = "#1F3864";
await context.sync();
```

### Add a geometric shape with fill, outline, and text

```js
const slide = context.presentation.getSelectedSlides().getItemAt(0);
const shape = slide.shapes.addGeometricShape(
  PowerPoint.GeometricShapeType.roundRectangle,
  { left: 100, top: 200, width: 220, height: 120 },
);
shape.fill.setSolidColor("#01696F");      // hex or named color
shape.lineFormat.color = "#0F3D40";
shape.lineFormat.weight = 1.5;
shape.textFrame.textRange.text = "Key insight";
shape.textFrame.textRange.font.color = "#FFFFFF";
shape.textFrame.verticalAlignment = PowerPoint.TextVerticalAlignment.middleCentered;
await context.sync();
```

### Insert an image as a shape's fill

```js
const slide = context.presentation.getSelectedSlides().getItemAt(0);
const frame = slide.shapes.addGeometricShape(
  PowerPoint.GeometricShapeType.rectangle,
  { left: 50, top: 50, width: 480, height: 270 },
);
frame.fill.setImage(base64Image);   // 1.8 — sets fill type to PictureAndTexture
await context.sync();
```

### Position, resize, and delete

```js
const shape = slide.shapes.getItemAt(0);
shape.load("left, top, width, height");
await context.sync();
shape.left = 100;           // points; throws InvalidArgument on negative width/height
shape.top = 100;
shape.width = 300;
shape.height = 180;
await context.sync();
shape.delete();
await context.sync();
```

`Shape.rotation`, `altTextDescription`, and `altTextTitle` are
`PowerPointApi 1.10` — gate with
`Office.context.requirements.isSetSupported("PowerPointApi", "1.10")` before
reading or writing them, since 1.8 clients will throw.

### Z-order

```js
shape.setZOrder(PowerPoint.ShapeZOrder.bringToFront);   // 1.8
// Or string: "BringForward" | "BringToFront" | "SendBackward" | "SendToBack"
await context.sync();
```

### Group shapes

```js
const ids = slide.shapes.items.map(s => s.id);
const group = slide.shapes.addGroup(ids);   // 1.8
await context.sync();
// Ungroup later: group.group.ungroup();
```

## Text

`Shape.textFrame.textRange` is the entry point for reading or replacing text.
`textRange.text` is **assignable** — that's how you replace the entire content
of a text frame. There is no `insertText` / `Range.replace` analogue from Word.

### Replace a shape's text wholesale

```js
const shape = slide.shapes.getItem(shapeId);
shape.textFrame.textRange.text = "New title";
await context.sync();
```

### Add multi-paragraph text (use `\n`)

```js
shape.textFrame.textRange.text = "Line one\nLine two\nLine three";
await context.sync();
```

### Append by reading then rewriting

```js
const tr = shape.textFrame.textRange;
tr.load("text");
await context.sync();
tr.text = tr.text + "\nAppended line";
await context.sync();
```

### Format a substring (1.5+)

```js
const tr = shape.textFrame.textRange;
tr.load("text");
await context.sync();
const sub = tr.getSubstring(0, 5);   // first 5 chars
sub.font.bold = true;
sub.font.color = "#C00000";
await context.sync();
```

### Selected text range (1.5)

```js
const sel = context.presentation.getSelectedTextRangeOrNullObject();
sel.load("isNullObject, text, start, length");
await context.sync();
if (sel.isNullObject) return null;
return { text: sel.text, start: sel.start, length: sel.length };
```

> ⚠️ `Presentation.getSelectedTextRange()` (no `OrNullObject`) **throws** if no
> text is selected. Use the null-object form unless you've confirmed selection.

### Paragraph alignment

```js
const tr = shape.textFrame.textRange;
tr.paragraphFormat.horizontalAlignment = PowerPoint.ParagraphHorizontalAlignment.center;
// or string: "Left" | "Center" | "Right" | "Justify"
await context.sync();
```

> ⚠️ Word uses `"Centered"` for paragraph alignment; **PowerPoint uses
> `"Center"`** — different enum strings between hosts.

### Vertical alignment of the text frame

```js
shape.textFrame.verticalAlignment = PowerPoint.TextVerticalAlignment.middleCentered;
// or string: "Top" | "Middle" | "Bottom" | "TopCentered" | "MiddleCentered" | "BottomCentered"
await context.sync();
```

### Auto-size, margins, word wrap

```js
shape.textFrame.autoSizeSetting = PowerPoint.ShapeAutoSize.autoSizeShapeToFitText;
shape.textFrame.leftMargin = 8;     // points
shape.textFrame.rightMargin = 8;
shape.textFrame.topMargin = 4;
shape.textFrame.bottomMargin = 4;
shape.textFrame.wordWrap = true;
await context.sync();
```

### Font properties

`ShapeFont` exposes `name`, `size`, `bold`, `italic`, `underline`, `color`,
`allCaps`, `smallCaps`, `strikethrough`, `doubleStrikethrough`, `subscript`,
`superscript`. Underline is a `ShapeFontUnderlineStyle` enum (`"None"`,
`"Single"`, `"Double"`, `"Heavy"`, `"Dotted"`, `"DashLong"`, `"Wavy"`, …).

```js
const f = shape.textFrame.textRange.font;
f.name = "Calibri";
f.size = 18;
f.bold = true;
f.color = "#01696F";
f.underline = PowerPoint.ShapeFontUnderlineStyle.single;
await context.sync();
```

## Tables

`shapes.addTable(rows, cols)` returns a `Shape`; call `shape.getTable()` for
the `Table` to read or set cell values. Both `addTable` and `Table` are
`PowerPointApi 1.8`.

### Create a table and fill it

```js
const slide = context.presentation.getSelectedSlides().getItemAt(0);
const data = [
  ["Segment", "FY24", "FY25", "FY26"],
  ["Enterprise", "$320M", "$392M", "$470M"],
  ["SMB",        "$140M", "$168M", "$198M"],
  ["Consumer",    "$80M",  "$88M",  "$92M"],
];
const shape = slide.shapes.addTable(data.length, data[0].length, {
  left: 50, top: 100, width: 600, height: 240,
});
const table = shape.getTable();
table.load("rowCount, columnCount");
await context.sync();
for (let r = 0; r < data.length; r++) {
  for (let c = 0; c < data[r].length; c++) {
    const cell = table.getCellOrNullObject(r, c);   // not getCell
    cell.text = data[r][c];
  }
}
await context.sync();
```

> ⚠️ Cells are read with `getCellOrNullObject(rowIndex, columnIndex)` — there
> is no plain `getCell`. If the cell is part of a merged area and isn't the
> top-left cell, the returned object has `isNullObject === true`.

### Read a table's contents

`Table.values` is a 2D string array of **already-loaded** cell text — load
the table to get it.

```js
const shape = slide.shapes.items.find(s => s.type === "Table");
const table = shape.getTable();
table.load("rowCount, columnCount, values");
await context.sync();
return { rows: table.rowCount, cols: table.columnCount, values: table.values };
```

## Hyperlinks

`Slide.hyperlinks` is `PowerPointApi 1.6`, **read-only in 1.6/1.7/1.8/1.9**.
The `add(target, options)` overload that creates a new hyperlink on a shape
or text range is `PowerPointApi 1.10` — gate calls behind a requirement-set
check.

### Read hyperlinks on a slide

```js
const slide = context.presentation.getSelectedSlides().getItemAt(0);
const links = slide.hyperlinks;
links.load("items/address, items/screenTip");
await context.sync();
return links.items.map(h => ({ address: h.address, tip: h.screenTip }));
```

### Add a hyperlink (requires 1.10)

```js
if (Office.context.requirements.isSetSupported("PowerPointApi", "1.10")) {
  const shape = context.presentation.getSelectedShapes().getItemAt(0);
  context.presentation.getSelectedSlides().getItemAt(0).hyperlinks.add(shape, {
    address: "https://www.perplexity.ai",
    screenTip: "Perplexity",
  });
  await context.sync();
}
```

## Tags (custom metadata)

Tags are arbitrary key/value strings attached to the presentation, a slide,
or a shape. Useful for marking generated objects so a later run can find
them. Keys are case-insensitive but stored in **uppercase** — read them
back uppercase.

```js
const slide = context.presentation.getSelectedSlides().getItemAt(0);
slide.tags.add("ASI_GENERATED", new Date().toISOString());   // 1.3
await context.sync();

const tag = slide.tags.getItemOrNullObject("ASI_GENERATED");
tag.load("isNullObject, key, value");
await context.sync();
if (!tag.isNullObject) return { key: tag.key, value: tag.value };
```

## Document properties

`Presentation.properties` (1.7) is a `DocumentProperties` object with `title`,
`subject`, `author`, `keywords`, `comments`, `category`, `manager`, `company`,
plus `customProperties`.

```js
const props = context.presentation.properties;
props.load("title, author, company, customProperties/items/key, customProperties/items/value");
await context.sync();
return {
  title: props.title, author: props.author, company: props.company,
  custom: props.customProperties.items.map(p => ({ key: p.key, value: p.value })),
};
```

## Reading the current presentation as bytes

For email or Drive attachment, use the shared Office add-in recipe in
`../../current-file-attachment/references/current-file-attachment.md` with the
PowerPoint host config (no PowerPoint JS save API to force a flush, default
`presentation.pptx`). The shared recipe covers `getFileAsync`, slice handling,
compressed OOXML string handling, PowerPoint save caveats, and worker-side
reassembly.

## Common pitfalls

- **No file save API.** PowerPoint Office.js has no `presentation.save()` to
  force a flush before `getFileAsync`. If recent edits matter, ask the user to
  save or confirm the deck is up to date. Don't claim you "saved the deck."
- **No undo.** Edits made by the add-in cannot be rolled back from the user's
  Undo stack reliably. Confirm destructive operations before issuing them.
- **Coordinates are points, not EMUs or pixels.** A 16:9 slide is 960×540 pt
  by default. Validate `left`, `top`, `width`, `height` against the slide size
  before placing — there is no per-slide width/height in stable Office.js, so
  hardcode the deck size you know about or read the `slideMaster` shapes.
- **Don't read `placeholderFormat` on non-placeholder shapes.** It throws
  `GeneralException` unless `shape.type === "Placeholder"`. Same for
  `shape.group` (must be `"Group"`) and `shape.parentGroup` (must be inside
  a group).
- **`textFrame` throws on non-text shapes.** On `PowerPointApi 1.10` use
  `shape.getTextFrameOrNullObject()` and check `isNullObject`. On older
  clients, filter by `type` (e.g. exclude `"Image"`, `"Line"`, `"Media"`)
  before touching `textFrame`.
- **`getCell` doesn't exist on `Table`.** It's `getCellOrNullObject(r, c)`,
  always. Check `cell.isNullObject` for merged-area dead cells.
- **Slide selection and shape selection are separate.** `getSelectedShapes()`
  reflects only shapes on the **current view's active slide**, not shapes on
  other selected slides.
- **Insert APIs return objects whose properties aren't available until sync.**
  After `slide.shapes.addTextBox(...)`, the returned `Shape` has no readable
  `id` until you `load("id")` and `await context.sync()`.
- **Enum string values differ from Word.** `ParagraphHorizontalAlignment` uses
  `"Center"` (PowerPoint) vs. `"Centered"` (Word). `InsertLocation` doesn't
  exist in PowerPoint at all — there's no insert-before/after for shapes,
  only `setZOrder`.
- **Requirement sets matter.** Tables (`addTable`, `Table`), `applyLayout`,
  `moveTo`, `getImageAsBase64`, `exportAsBase64`, `setZOrder`, `addGroup`,
  `parentGroup`, `level`, `slide.index`, and `fill.setImage` are all
  `PowerPointApi 1.8`. Hyperlink **add** is 1.10. If you need to support
  older PowerPoint clients, gate with
  `Office.context.requirements.isSetSupported("PowerPointApi", "1.8")`.
