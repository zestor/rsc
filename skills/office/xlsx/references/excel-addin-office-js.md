# Excel add-in Office.js recipes

Invoke these recipes by calling
`describe_external_tools(source_id="excel_workbook", tool_names=["run_office_js"])`,
then `call_external_tool` with source_id="excel_workbook",
tool_name="run_office_js", and arguments={"purpose": "...", "code": "..."}.
Every snippet is the arguments.code value and goes inside
`await Excel.run(async (context) => { ... })`.
Always `load` the properties you read, then `await context.sync()` before
reading them. Range writes (`values`, `formulas`, `numberFormat`) are 2D arrays
even for a single cell.

## Workbook structure

### Inventory the workbook (sheets, tables, names, active selection)

```js
return await Excel.run(async (context) => {
  const wb = context.workbook;
  const sheets = wb.worksheets;
  sheets.load("items/name, items/position, items/visibility");
  const tables = wb.tables;
  tables.load("items/name, items/worksheet/name, items/showHeaders");
  const names = wb.names;
  names.load("items/name, items/formula, items/type, items/scope");
  const active = wb.getActiveCell();
  active.load("address, worksheet/name");
  const activeSheet = wb.getActiveWorksheet();
  activeSheet.load("name");
  await context.sync();
  tables.items.forEach(t => t.rows.load("count"));
  await context.sync();
  return {
    active_sheet: activeSheet.name,
    active_cell: active.address,
    sheets: sheets.items.map(s => ({
      name: s.name, position: s.position, visibility: s.visibility,
    })),
    tables: tables.items.map(t => ({
      name: t.name, sheet: t.worksheet.name, rows: t.rows.count,
    })),
    named_ranges: names.items.map(n => ({
      name: n.name, refers_to: n.formula, scope: n.scope, type: n.type,
    })),
  };
});
```

### Used range of a sheet

`sheet.getUsedRange(valuesOnly?)` throws if the sheet is empty — prefer the
null-object form. Pass `true` to ignore cells that only have formatting.

```js
const sheet = context.workbook.worksheets.getItem("Model");
const used = sheet.getUsedRangeOrNullObject(true);
used.load("isNullObject, address, rowCount, columnCount");
await context.sync();
if (used.isNullObject) return { empty: true };
return { address: used.address, rows: used.rowCount, cols: used.columnCount };
```

## Reading

### Load values, formulas, and number formats together

```js
const r = context.workbook.worksheets.getItem("Inputs").getRange("B5:D20");
r.load("address, values, formulas, numberFormat, rowCount, columnCount");
await context.sync();
return {
  address: r.address,
  rows: r.rowCount,
  cols: r.columnCount,
  values: r.values,
  formulas: r.formulas,
  number_formats: r.numberFormat,
};
```

`values` returns evaluated numbers/strings/booleans; `formulas` returns the
formula text (or the literal value if no formula); `numberFormat` returns the
display format string per cell. Read all three when you need to reason about
what's actually in a model — `values` alone hides whether a number is
hardcoded or calculated.

### Find sheet by name without throwing

```js
const sheet = context.workbook.worksheets.getItemOrNullObject("Assumptions");
sheet.load("isNullObject, name");
await context.sync();
if (sheet.isNullObject) {
  return { error: "Sheet 'Assumptions' not found" };
}
```

### Active cell / current selection

`workbook.getSelectedRange()` returns whatever the user has highlighted —
single cell or block. Use this for "operate on the current selection" tasks.

```js
const sel = context.workbook.getSelectedRange();
sel.load("address, values, rowCount, columnCount, worksheet/name");
await context.sync();
return {
  sheet: sel.worksheet.name,
  address: sel.address,
  rows: sel.rowCount, cols: sel.columnCount,
};
```

### Resolve a named range

```js
const named = context.workbook.names.getItemOrNullObject("WACC");
named.load("isNullObject, name, formula, value");
await context.sync();
if (named.isNullObject) return null;
const r = named.getRange();
r.load("address, values");
await context.sync();
return { name: named.name, address: r.address, value: r.values[0][0] };
```

### Iterate a table

```js
const t = context.workbook.tables.getItem("RevenueBuild");
const header = t.getHeaderRowRange();
const body = t.getDataBodyRange();
header.load("values");
body.load("values, formulas, rowCount, columnCount");
await context.sync();
return {
  columns: header.values[0],
  rows: body.values,
};
```

## Writing values, formulas, number formats

`values` and `formulas` writes are shape-sensitive 2D arrays. Even a single
cell is `[[ ... ]]`, and mismatched dimensions throw `"The argument is invalid
or missing or has an incorrect format."`.

### Write a 2D block of values

```js
const sheet = context.workbook.worksheets.getItem("Model");
const r = sheet.getRange("B5:D7");
r.values = [
  ["Revenue", 1200, 1380],
  ["COGS",     720,  810],
  ["Gross",    480,  570],
];
await context.sync();
```

### Write formulas (and apply a number format)

Formulas use `=` prefixes and standard Excel syntax. Unit and currency
formats are applied through `numberFormat`. Use `[[fmt]]` for one uniform
format across the target range, or a full 2D array when each cell may differ.

```js
const sheet = context.workbook.worksheets.getItem("Model");
const r = sheet.getRange("E5:E7");
r.formulas = [
  ["=D5/C5-1"],
  ["=D6/C6-1"],
  ["=D7/C7-1"],
];
r.numberFormat = [["0.0%;(0.0%);-"]];
await context.sync();
```

### Write the same formula across a range with relative refs

`getRange("E5:E20").formulas = [["=D5/C5-1"], ...]` requires N rows of
formulas. For repeating patterns, prefer building the array in JS:

```js
const cell = (i) => [`=D${5+i}/C${5+i}-1`];
const formulas = Array.from({length: 16}, (_, i) => cell(i));
sheet.getRange("E5:E20").formulas = formulas;
sheet.getRange("E5:E20").numberFormat =
  Array.from({length: 16}, () => ["0.0%;(0.0%);-"]);
await context.sync();
```

### Common finance number formats

```js
// Currency with parens for negatives, dash for zero.
sheet.getRange("C5:Z5").numberFormat = [["$#,##0;($#,##0);-"]];

// Percent
sheet.getRange("E5:E20").numberFormat = [["0.0%;(0.0%);-"]];

// Multiple ("x") for ratios
sheet.getRange("F5:F20").numberFormat = [['0.0"x";(0.0"x");-']];

// Basis points
sheet.getRange("G5:G20").numberFormat = [['0" bps"']];

// Date — ISO-style for audit-friendly output
sheet.getRange("A5:A20").numberFormat = [["yyyy-mm-dd"]];
await context.sync();
```

> ⚠️ `numberFormat` is still a 2D array, but `[[fmt]]` is valid when applying
> one uniform format across the whole range. Use a range-shaped 2D array only
> when formats differ by cell or when using `null` placeholders to leave
> specific cells unchanged.

### Recalc after bulk formula writes

If `application.calculationMode` is `"Manual"`, formulas you just wrote
won't update until you trigger calculation. Read `values` only after.

```js
context.application.calculate("Full");  // "Full" | "FullRebuild" | "Recalculate"
await context.sync();
const r = sheet.getRange("E5:E20");
r.load("values");
await context.sync();
return r.values;
```

`sheet.calculate(true)` recalculates a single sheet (the boolean controls
"recalculate even if marked up-to-date").

## Formatting

Apply font, fill, alignment, and borders through `range.format`. Colors are
hex strings; named CSS colors (`"white"`, `"red"`) also work.

### Header row (blue fill, white bold text, centered)

```js
const header = sheet.getRange("B4:G4");
header.format.fill.color = "#1F3864";
header.format.font.color = "white";
header.format.font.bold = true;
header.format.horizontalAlignment = "Center";    // "General"|"Left"|"Center"|"Right"|"Fill"|"Justify"|"CenterAcrossSelection"|"Distributed"
header.format.verticalAlignment = "Center";       // "Top"|"Center"|"Bottom"|"Justify"|"Distributed"
await context.sync();
```

### Finance color coding (inputs blue, formulas black, links green)

```js
// Hardcoded inputs (assumptions)
sheet.getRange("C5:C10").format.font.color = "#0000FF";

// Cross-sheet links
sheet.getRange("C12:C15").format.font.color = "#008000";

// External / live links (avoid in audit copy — flag in red)
sheet.getRange("C20:C20").format.font.color = "#C00000";

// Highlight assumption cells the user is meant to edit
sheet.getRange("C5:C10").format.fill.color = "#FFF2CC";  // pale yellow
await context.sync();
```

### Borders

```js
const r = sheet.getRange("B4:G15");
const edges = ["EdgeTop", "EdgeBottom", "EdgeLeft", "EdgeRight",
               "InsideHorizontal", "InsideVertical"];
edges.forEach(side => {
  const b = r.format.borders.getItem(side);
  b.style = "Continuous";       // "None"|"Continuous"|"Dash"|"DashDot"|"DashDotDot"|"Dot"|"Double"|"SlantDashDot"
  b.weight = "Thin";            // "Hairline"|"Thin"|"Medium"|"Thick"
  b.color = "#999999";
});
await context.sync();
```

### Column width / row height / autofit

```js
sheet.getRange("A:A").format.columnWidth = 32;
sheet.getRange("B:G").format.autofitColumns();    // size to current contents
sheet.getRange("4:4").format.rowHeight = 22;
sheet.getUsedRange().format.autofitRows();
await context.sync();
```

### Number, font, and indent in one pass

```js
const r = sheet.getRange("C5:C20");
r.numberFormat = Array.from({length: 16}, () => ["$#,##0;($#,##0);-"]);
r.format.font.name = "Calibri";
r.format.font.size = 11;
r.format.indentLevel = 1;          // 0..15
await context.sync();
```

## Conditional formatting

`range.conditionalFormats.add(Excel.ConditionalFormatType.<type>)` returns a
typed conditional format. Read the right sub-property (`colorScale`,
`cellValue`, `containsText`, `custom`, `presetCriteria`, `dataBar`,
`iconSet`, `topBottom`) to configure it.

### Color scale (3-color, low → mid → high)

```js
const r = sheet.getRange("C5:N20");
const cf = r.conditionalFormats.add(Excel.ConditionalFormatType.colorScale);
cf.colorScale.criteria = {
  minimum: { type: Excel.ConditionalFormatColorCriterionType.lowestValue, color: "#F8696B" },
  midpoint: { type: Excel.ConditionalFormatColorCriterionType.percentile, formula: "50", color: "#FFEB84" },
  maximum: { type: Excel.ConditionalFormatColorCriterionType.highestValue, color: "#63BE7B" },
};
await context.sync();
```

### Highlight negatives in red

```js
const r = sheet.getRange("C5:N20");
const cf = r.conditionalFormats.add(Excel.ConditionalFormatType.cellValue);
cf.cellValue.rule = { formula1: "=0", operator: "LessThan" };
cf.cellValue.format.font.color = "#C00000";
cf.cellValue.format.font.bold = true;
await context.sync();
```

### Flag formulas that resolve to errors (#REF!, #DIV/0!, #VALUE!, #N/A)

```js
const r = sheet.getRange("B5:Z200");
const cf = r.conditionalFormats.add(Excel.ConditionalFormatType.custom);
cf.custom.rule.formula = "=ISERROR(B5)";   // relative to top-left of range
cf.custom.format.fill.color = "#FFC7CE";
cf.custom.format.font.color = "#9C0006";
await context.sync();
```

### Match-text rule (e.g. flag "TBD" assumptions)

```js
const r = sheet.getRange("C5:C50");
const cf = r.conditionalFormats.add(Excel.ConditionalFormatType.containsText);
cf.textComparison.rule = { operator: "Contains", text: "TBD" };
cf.textComparison.format.fill.color = "#FFE699";
await context.sync();
```

### Clear conditional formats

```js
sheet.getRange("C5:N20").conditionalFormats.clearAll();
await context.sync();
```

## Tables

Excel tables (ListObjects) are how you keep header styling, total rows, and
structured references in sync.

### Create a table from a range

```js
const sheet = context.workbook.worksheets.getItem("RevenueBuild");
sheet.getRange("A1:E1").values = [["Segment", "FY24", "FY25", "FY26", "Growth"]];
sheet.getRange("A2:E4").values = [
  ["Enterprise", 320, 392, 470, 0.20],
  ["SMB",        140, 168, 198, 0.18],
  ["Consumer",    80,  88,  92, 0.05],
];
const t = sheet.tables.add("A1:E4", true);   // true = has headers
t.name = "tbl_RevenueBuild";
t.style = "TableStyleMedium2";
await context.sync();
```

### Add a row

```js
const t = context.workbook.tables.getItem("tbl_RevenueBuild");
t.rows.add(null, [["International", 60, 75, 90, 0.20]]);  // null = append at end
await context.sync();
```

### Read column by name

```js
const t = context.workbook.tables.getItem("tbl_RevenueBuild");
const col = t.columns.getItem("Segment").getDataBodyRange();
col.load("values");
await context.sync();
return col.values.flat();
```

### Add a totals row with structured references

```js
const t = context.workbook.tables.getItem("tbl_RevenueBuild");
t.showTotals = true;
await context.sync();
const total = t.getTotalRowRange();
total.formulas = [["Total", "=SUBTOTAL(109,tbl_RevenueBuild[FY24])",
                          "=SUBTOTAL(109,tbl_RevenueBuild[FY25])",
                          "=SUBTOTAL(109,tbl_RevenueBuild[FY26])",
                          "=AVERAGE(tbl_RevenueBuild[Growth])"]];
await context.sync();
```

## Charts

`sheet.charts.add(chartType, sourceData, seriesBy)` returns a `Chart`. Type
strings come from `Excel.ChartType` (`"Line"`, `"ColumnClustered"`,
`"BarStacked"`, `"Pie"`, `"XyScatter"`, `"Area"`, `"Combo"`, etc.). Pass the
typed enum form when possible.

### Trend line of revenue by year

```js
const sheet = context.workbook.worksheets.getItem("RevenueBuild");
const data = sheet.getRange("A1:D4");                  // headers + 3 segments
const chart = sheet.charts.add(Excel.ChartType.line, data, Excel.ChartSeriesBy.rows);
chart.title.text = "Revenue by Segment ($mm)";
chart.title.format.font.size = 12;
chart.legend.position = Excel.ChartLegendPosition.bottom;  // "Top"|"Bottom"|"Left"|"Right"|"Corner"|"Custom"|"Invalid"
chart.axes.valueAxis.format.font.size = 10;
chart.axes.valueAxis.numberFormat = "$#,##0";
// setPosition accepts Range objects or address strings. Range objects keep the
// snippet scoped to this sheet and avoid cross-sheet ambiguity.
chart.setPosition(sheet.getRange("G1"), sheet.getRange("N18"));
await context.sync();
```

### Optional styling — guard `plotArea.format.line`

Some chart types (or older clients) don't expose `plotArea.format.line`.
Wrap optional styling so the whole call doesn't fail.

```js
try {
  chart.plotArea.format.line.color = "#D9D9D9";
} catch (e) { /* not all chart types support this */ }
await context.sync();
```

### Update an existing chart's data

```js
const sheet = context.workbook.worksheets.getItem("RevenueBuild");
const chart = sheet.charts.getItem("Chart 1");
chart.setData(sheet.getRange("A1:E4"), Excel.ChartSeriesBy.rows);
chart.setPosition(sheet.getRange("G1"), sheet.getRange("N18"));
await context.sync();
```

### Delete a chart

```js
const c = sheet.charts.getItemOrNullObject("Stale Chart");
c.load("isNullObject");
await context.sync();
if (!c.isNullObject) {
  c.delete();
  await context.sync();
}
```

## Freeze panes, gridlines, view

```js
const sheet = context.workbook.worksheets.getItem("Model");
sheet.freezePanes.unfreeze();
sheet.freezePanes.freezeRows(4);            // freeze first 4 rows
sheet.freezePanes.freezeColumns(2);         // and first 2 cols
// Or both at once anchored at a cell:
// sheet.freezePanes.freezeAt(sheet.getRange("C5"));
await context.sync();
```

Inspect the current freeze location:

```js
const loc = sheet.freezePanes.getLocationOrNullObject();
loc.load("isNullObject, address");
await context.sync();
return loc.isNullObject ? null : loc.address;
```

## Worksheet management

### Add, rename, reorder, delete

```js
const wb = context.workbook;
const existing = wb.worksheets.getItemOrNullObject("Scratch");
existing.load("isNullObject");
await context.sync();
if (!existing.isNullObject) {
  existing.delete();
  await context.sync();
}
const s = wb.worksheets.add("Scratch");
// worksheets.add() appends to the end by default.
s.tabColor = "#FFC000";
s.activate();
await context.sync();
```

### Hide / unhide

```js
sheet.visibility = Excel.SheetVisibility.hidden;       // "Visible"|"Hidden"|"VeryHidden"
await context.sync();
```

`VeryHidden` sheets can't be unhidden from the UI — only via Office.js or
VBA. Useful for compiled assumption sheets you don't want users editing,
but document the choice in a visible README sheet.

### Copy a sheet (templated tab pattern)

```js
const tmpl = context.workbook.worksheets.getItem("Template");
const copy = tmpl.copy(Excel.WorksheetPositionType.end);  // or .after, .before, .beginning
copy.load("name");
await context.sync();
copy.name = "FY26_Forecast";
await context.sync();
```

## Insert / delete / clear

`Range.insert` shifts existing cells; `Range.delete` removes cells and shifts
neighbors. `Range.clear` keeps the cells in place and removes content,
formats, or hyperlinks.

```js
// Insert a blank row above row 5
sheet.getRange("5:5").insert(Excel.InsertShiftDirection.down);

// Delete column C, shifting columns left
sheet.getRange("C:C").delete(Excel.DeleteShiftDirection.left);

// Clear contents only (keep formatting)
sheet.getRange("C5:N20").clear(Excel.ClearApplyTo.contents);  // "All"|"Formats"|"Contents"|"Hyperlinks"|"RemoveHyperlinks"
await context.sync();
```

## Sorting and filtering

### Sort a range by column

```js
const r = sheet.getRange("A2:E20");          // body only — headers excluded
r.sort.apply(
  [{ key: 1, ascending: false }],   // sort by 2nd column (FY24) descending
  false,                            // matchCase
  false,                            // hasHeaders — false because we excluded the header row
  Excel.SortOrientation.rows
);
await context.sync();
```

`key` is the **0-based column offset within the sorted range**, not a column
letter. For a table, use `tbl.sort.apply([{ key: 1, ascending: false }])`
where `key` is the table column index.

### Apply an autofilter

```js
const r = sheet.getRange("A1:E20");
sheet.autoFilter.apply(r, 4 /* growth column */, {
  filterOn: Excel.FilterOn.values,
  values: [0.18, 0.20],
});
await context.sync();
```

To clear: `sheet.autoFilter.clearCriteria();` or `sheet.autoFilter.remove();`.

## Named ranges

Named ranges are how serious models stay readable — `WACC` reads better than
`Assumptions!$C$5`, and refactor-safe.

```js
context.workbook.names.add("WACC", "=Assumptions!$C$5");
context.workbook.names.add("TaxRate", "=Assumptions!$C$6");
// Sheet-scoped (only visible inside one sheet):
context.workbook.worksheets.getItem("Model").names
  .add("LocalRate", "=Model!$D$10");
await context.sync();
```

Reading the value of a named scalar:

```js
const n = context.workbook.names.getItemOrNullObject("WACC");
n.load("isNullObject, value");
await context.sync();
return n.isNullObject ? null : n.value;
```

## Data validation

Lock down assumption cells to a list of acceptable values.

```js
const r = sheet.getRange("C12:C12");
r.dataValidation.rule = {
  list: { inCellDropDown: true, source: "Bull,Base,Bear" },
};
r.dataValidation.errorAlert = {
  message: "Choose Bull, Base, or Bear.",
  showAlert: true,
  style: "Stop",                  // "Stop"|"Warning"|"Information"
  title: "Invalid scenario",
};
await context.sync();
```

For numeric ranges:

```js
r.dataValidation.rule = {
  wholeNumber: { formula1: "0", formula2: "100", operator: "Between" },
};
```

## Calculation control and recalc

```js
const app = context.application;
app.load("calculationMode");
await context.sync();
// app.calculationMode is "Automatic" | "AutomaticExceptTables" | "Manual"

// Force a full recalc of every formula in every open workbook
app.calculate("Full");

// Switch to manual while doing bulk writes, then restore
const prior = app.calculationMode;
app.calculationMode = "Manual";
// ... heavy writes ...
app.calculate("Full");
app.calculationMode = prior;
await context.sync();
```

`sheet.calculate(true)` recalculates a single sheet; the boolean forces
recalc even when Excel thinks the sheet is up-to-date.

## Document properties

Useful for stamping deal codename, version, source date, and "as-of" notes
into workbook metadata so they survive Save As.

```js
const props = context.workbook.properties;
props.load("title, author, company, lastAuthor, revisionNumber");
await context.sync();
return {
  title: props.title, author: props.author, company: props.company,
  last_author: props.lastAuthor, revision: props.revisionNumber,
};
```

Custom properties (e.g. `DealCode`, `AsOfDate`):

```js
const custom = context.workbook.properties.custom;
custom.add("DealCode", "PROJECT_HARBOR");
custom.add("AsOfDate", "2026-05-06");
custom.load(["key", "value"]);
await context.sync();
return custom.items.map(p => ({ key: p.key, value: p.value }));
```

## Saving

`workbook.save()` saves in place. There is **no `saveAs`** — to save a
copy, the user must use File → Save a Copy in Excel.

```js
context.workbook.save();
await context.sync();
```

## Reading the current workbook as bytes

For email or Drive attachment, use the shared Office add-in recipe in
`../../current-file-attachment/references/current-file-attachment.md` with the
Excel host config (`context.workbook.save()`, default `workbook.xlsx`). The
shared recipe covers `getFileAsync`, slice handling, compressed OOXML string
handling, and worker-side reassembly.

## Common pitfalls

1. **Reading unloaded properties** throws `"The property '<X>' is not
   available..."`. Always `obj.load("a, b, c")` then `await context.sync()`
   before reading. Plural properties live behind `load("items/<prop>")`.
2. **`*OrNullObject` for missing items.** `worksheets.getItemOrNullObject(name)`,
   `tables.getItemOrNullObject(name)`, `range.getUsedRangeOrNullObject(true)`,
   `freezePanes.getLocationOrNullObject()`. The non-null versions throw when
   the target doesn't exist; check `.isNullObject` after sync.
3. **Range values/formulas are shape-sensitive 2D arrays.** Even one cell is
   `[[ ... ]]`, and mismatched dimensions throw `"The argument is invalid or
   missing or has an incorrect format."`. `numberFormat` is also a 2D array,
   but `[[fmt]]` applies one uniform format across a range; build a full
   range-shaped array only when formats differ by cell or when using `null`
   placeholders.
4. **`chart.setPosition` accepts Range objects or address strings.** Prefer
   `chart.setPosition(sheet.getRange("Z1"), sheet.getRange("AH20"))` when you
   already have the sheet object; strings are valid Office.js but easier to
   aim at the wrong sheet.
5. **Optional format paths can be undefined.** `chart.plotArea.format.line`,
   `format.fill.pattern`, and similar can be missing on certain chart types
   or older clients. Wrap optional styling in `try { ... } catch (e) {}`.
6. **`application.calculationMode` may be `"Manual"`.** Formulas you write
   won't recalc until you call `application.calculate("Full")`. Read
   computed values **after** the calc + sync, not before.
7. **`sort.key` is a 0-based offset within the sorted range**, not a column
   letter. For tables, it's the column index in the table.
8. **Use shaped `numberFormat` arrays only for mixed formats.** `[[fmt]]` is
   valid for one uniform format; if some cells need different formats or must
   stay unchanged, build a full 2D array and use `null` for unchanged cells.
9. **Tables can't span discontinuous ranges.** `tables.add` requires a
   single contiguous block. Sheet must be visible; tables can't be added on
   a `Hidden` or `VeryHidden` sheet.
10. **`null` and empty strings are different in 2D arrays.** Use `null` to
    leave a cell unchanged while updating other cells in the same range.
    Empty strings (`""`) clear values, formulas, or number formats depending
    on the property being set.
11. **Sheet names have constraints.** Max 31 chars; can't contain `:\/?*[]`;
    can't be blank or duplicate (case-insensitive). Trim and dedupe before
    `worksheets.add(name)` or it throws.
12. **`worksheet.position` is 0-based.** `worksheets.getCount()` returns an
    `OfficeExtension.ClientResult<number>`; call it, `await context.sync()`,
    then read `.value` before doing arithmetic. `worksheets.add(name)` already
    appends new sheets to the end.
13. **No `saveAs`.** `workbook.save()` saves in place only — to save a copy,
    the user uses File → Save a Copy in the UI.
14. **Don't blanket-`autofitColumns` a finance model.** Column widths are
    often deliberate (period columns sized identically). Autofit only the
    columns you wrote, not `getUsedRange().format.autofitColumns()`.
15. **Recalc before reading values that depend on freshly-written formulas**
    even in Automatic mode if you wrote both the formula and the inputs in
    the same `Excel.run` — values may be stale until after `calculate("Full")`.
