# PptxGenJS reference (theme-neutral)

> **Scope:** pptxgenjs **API only** — script shell, coordinates, `addText` / lists / shapes / images / icons / tables / charts, and corruption pitfalls.
>
> **Not in this file:** brand colours, logos, typography, or slide-type patterns → read **`ascentium-deck.md`** or **`inspire-deck.md`** for the active theme.
>
> **Colours:** pass **6-char hex without `#`** (e.g. `"272C2C"`).

---

## Script shell

Every create script must use an **async IIFE** and **`await pres.writeFile()`**. Set **`pres.layout` before `addSlide()`**.

```javascript
"use strict";
const pptxgen = require("pptxgenjs");

(async () => {
  const pres = new pptxgen();
  pres.layout = "LAYOUT_16x9"; // or LAYOUT_WIDE — pick one per theme deck; never mix in one file

  const slide = pres.addSlide();
  slide.background = { color: "FFFFFF" };
  slide.addText("Hello", {
    x: 0.5, y: 0.5, w: 8, h: 1,
    fontSize: 24, color: "272C2C", margin: 0,
  });

  await pres.writeFile({ fileName: "/home/user/content-studio/deck.pptx" });
})().catch((err) => {
  process.stderr.write(String(err) + "\n");
  process.exit(1);
});
```

**Do not:** top-level `await` in a plain `.js` file; `writeFile()` without `await`; layout name `LAYOUT_16X9` (wrong casing).

---

## Layout dimensions

Coordinates are in **inches** (`x`, `y`, `w`, `h`).

| `pres.layout` | Slide size |
|---------------|------------|
| `LAYOUT_16x9` | 10" × 5.625" |
| `LAYOUT_WIDE` | 13.33" × 7.5" |

Content past the slide edge is **clipped**, not scaled. The active **theme deck** specifies which layout and padding to use.

---

## Text & Formatting

```javascript
// Basic text
slide.addText("Simple Text", {
  x: 1, y: 1, w: 8, h: 2, fontSize: 24, fontFace: "Arial",
  color: "363636", bold: true, align: "center", valign: "middle"
});

// Character spacing (use charSpacing, not letterSpacing which is silently ignored)
slide.addText("SPACED TEXT", { x: 1, y: 1, w: 8, h: 1, charSpacing: 6 });

// Rich text arrays
slide.addText([
  { text: "Bold ", options: { bold: true } },
  { text: "Italic ", options: { italic: true } }
], { x: 1, y: 3, w: 8, h: 1 });

// Multi-line text (requires breakLine: true)
slide.addText([
  { text: "Line 1", options: { breakLine: true } },
  { text: 'Line 2: 品牌商加速 "China+1" 布局', options: { breakLine: true } },
  { text: "Line 3" }  // Last item doesn't need breakLine
], { x: 0.5, y: 0.5, w: 8, h: 2 });

// Text box margin (internal padding)
slide.addText("Title", {
  x: 0.5, y: 0.3, w: 9, h: 0.6,
  margin: 0  // Use 0 when aligning text with other elements like shapes or icons
});
```

**Quotes in copy:** Any ASCII `"` inside a double-quoted JS string ends the string → syntax error. If the slide copy needs `"` (e.g. `"外国人企业"`, `"China+1"`), wrap that literal in **single quotes** `'…'` or escape as **`\"`**.

```javascript
// ✅ OK — outer single quotes, inner " allowed
{ text: '认定为"外国人企业"' }

// ✅ OK — double-quoted string, inner quotes escaped
{ text: "认定为\"外国人企业\"" }

// ❌ BAD — raw " inside "…" breaks parse / validation
{ text: "认定为"外国人企业"" }
```

**Tip:** Text boxes have internal margin by default. Set `margin: 0` when you need text to align precisely with shapes, lines, or icons at the same x-position.

**Stacked body text / overlap (critical):** Multiple `addText` calls at the **same `(x,y)`** stack on top of each other. Prefer **one** `addText([...])` with `breakLine: true` or bullets; if using separate calls, **increment `y`** after each block.

---

## Lists & Bullets

```javascript
// ✅ CORRECT: Multiple bullets
slide.addText([
  { text: "First item", options: { bullet: true, breakLine: true, paraSpaceAfter: 2  } }, //paraSpaceAfter could be 2-6 pt, optional
  { text: "Second item", options: { bullet: true, breakLine: true, paraSpaceAfter: 2  } }, 
  { text: "Third item", options: { bullet: true, paraSpaceAfter: 0 } }// last item: no extra gap after
], { x: 0.5, y: 0.5, w: 8, h: 3 });

// ❌ WRONG: Never use unicode bullets
slide.addText("• First item", { ... });  // Creates double bullets

// Sub-items and numbered lists
{ text: "Sub-item", options: { bullet: true, indentLevel: 1 } } //用 bullet: true 时，正文里不要再写 1. / 1) / （1）
{ text: "First", options: { bullet: { type: "number" }, breakLine: true } }
```

**Overlap note:** A **single** `addText` with multiple bullet runs (above) shares one `(x,y,w,h)` safely. Do **not** replace that with **N** separate `addText` calls all at the **same** `(x,y)`—see *Stacked body text / overlap* under *Text & Formatting*.

---

## Shapes

```javascript
slide.addShape("roundRect", {
  x: 0.5, y: 0.8, w: 1.5, h: 3.0,
  fill: { color: "FF0000" }, line: { color: "000000", width: 2 }
});

slide.addShape("ellipse", { x: 4, y: 1, w: 2, h: 2, fill: { color: "0000FF" } });

slide.addShape("line", {
  x: 1, y: 3, w: 5, h: 0, line: { color: "FF0000", width: 3, dashType: "dash" }
});

// With transparency
slide.addShape("rect", {
  x: 1, y: 1, w: 3, h: 2,
  fill: { color: "0088CC", transparency: 50 }
});

// ⚠️ Don't pair with rectangular accent overlays — they won't cover rounded corners. Use RECTANGLE instead.
slide.addShape("roundRect", {
  x: 1, y: 1, w: 3, h: 2,
  fill: { color: "FFFFFF" }, rectRadius: 0.1
});

// With shadow
slide.addShape("rect", {
  x: 1, y: 1, w: 3, h: 2,
  fill: { color: "FFFFFF" },
  shadow: { type: "outer", color: "000000", blur: 6, offset: 2, angle: 135, opacity: 0.15 }
});
```

Shadow options:

| Property | Type | Range | Notes |
|----------|------|-------|-------|
| `type` | string | `"outer"`, `"inner"` | |
| `color` | string | 6-char hex (e.g. `"000000"`) | No `#` prefix, no 8-char hex — see Common Pitfalls |
| `blur` | number | 0-100 pt | |
| `offset` | number | 0-200 pt | **Must be non-negative** — negative values corrupt the file |
| `angle` | number | 0-359 degrees | Direction the shadow falls (135 = bottom-right, 270 = upward) |
| `opacity` | number | 0.0-1.0 | Use this for transparency, never encode in color string |

To cast a shadow upward (e.g. on a footer bar), use `angle: 270` with a positive offset — do **not** use a negative offset.

**Note**: Gradient fills are not natively supported. Use a gradient image as a background instead.

---

## Images

### Image Sources

```javascript
// From file path
slide.addImage({ path: "images/chart.png", x: 1, y: 1, w: 5, h: 3 });

// From URL
slide.addImage({ path: "https://example.com/image.jpg", x: 1, y: 1, w: 5, h: 3 });

// From base64 (faster, no file I/O)
slide.addImage({ data: "image/png;base64,iVBORw0KGgo...", x: 1, y: 1, w: 5, h: 3 });
```

### Image Options

```javascript
slide.addImage({
  path: "image.png",
  x: 1, y: 1, w: 5, h: 3,
  rotate: 45,              // 0-359 degrees
  rounding: true,          // Circular crop
  transparency: 50,        // 0-100
  flipH: true,             // Horizontal flip
  flipV: false,            // Vertical flip
  altText: "Description",  // Accessibility
  hyperlink: { url: "https://example.com" }
});
```

### Image Sizing Modes

```javascript
// Contain - fit inside, preserve ratio
{ sizing: { type: 'contain', w: 4, h: 3 } }

// Cover - fill area, preserve ratio (may crop)
{ sizing: { type: 'cover', w: 4, h: 3 } }

// Crop - cut specific portion
{ sizing: { type: 'crop', x: 0.5, y: 0.5, w: 2, h: 2 } }
```

### Calculate Dimensions (preserve aspect ratio)

```javascript
// Brand PNGs — derive h from w using native pixel ratio (never guess h)
const logoW = 1.45;
slide.addImage({ path: 'inspire_logo_white.png', x: 0.5, y: 0.35, w: logoW, h: logoW * (145 / 466) });

// Or use contain sizing inside a bounding box
slide.addImage({
  path: 'asc_logo_black.png',
  x: 0.5, y: 5.15,
  sizing: { type: 'contain', w: 0.73, h: 0.2 },
});
```

```javascript
const origWidth = 1978, origHeight = 923, maxHeight = 3.0;
const calcWidth = maxHeight * (origWidth / origHeight);
const centerX = (10 - calcWidth) / 2;

slide.addImage({ path: "image.png", x: centerX, y: 1.2, w: calcWidth, h: maxHeight });
```

### Supported Formats

- **Standard**: PNG, JPG, GIF (animated GIFs work in Microsoft 365)
- **SVG**: Works in modern PowerPoint/Microsoft 365

---

## Icons

Use react-icons to generate SVG icons, then rasterize to PNG for universal compatibility.

### Setup

```javascript
const React = require("react");
const ReactDOMServer = require("react-dom/server");
const sharp = require("sharp");
const { FaCheckCircle, FaChartLine } = require("react-icons/fa");

function renderIconSvg(IconComponent, color = "#000000", size = 256) {
  return ReactDOMServer.renderToStaticMarkup(
    React.createElement(IconComponent, { color, size: String(size) })
  );
}

async function iconToBase64Png(IconComponent, color, size = 256) {
  const svg = renderIconSvg(IconComponent, color, size);
  const pngBuffer = await sharp(Buffer.from(svg)).png().toBuffer();
  return "image/png;base64," + pngBuffer.toString("base64");
}
```

### Add Icon to Slide

```javascript
const iconData = await iconToBase64Png(FaCheckCircle, "#4472C4", 256);

slide.addImage({
  data: iconData,
  x: 1, y: 1, w: 0.5, h: 0.5  // Size in inches
});
```

**Note**: Use size 256 or higher for crisp icons. The size parameter controls the rasterization resolution, not the display size on the slide (which is set by `w` and `h` in inches).

### Icon Libraries

All icon packages (`react-icons`, `react`, `react-dom`, `sharp`) are **pre-installed** in the E2B sandbox — no install step needed in the generated script. For local development outside E2B: `npm install pptxgenjs react react-dom react-icons sharp`.

Popular icon sets in react-icons:
- `react-icons/fa` - Font Awesome
- `react-icons/md` - Material Design
- `react-icons/hi` - Heroicons
- `react-icons/bi` - Bootstrap Icons

---

## Slide Backgrounds

```javascript
// Solid color
slide.background = { color: "F1F1F1" };

// Color with transparency
slide.background = { color: "FF3399", transparency: 50 };

// Image from URL
slide.background = { path: "https://example.com/bg.jpg" };

// Image from base64
slide.background = { data: "image/png;base64,iVBORw0KGgo..." };
```

---

## Tables

**CJK in tables:** avoid Latin-only or rarely-installed `fontFace` in cells — Chinese may render as □. Examples: **Poppins**, **Arial**, **Georgia**; **MiSans** when the viewer lacks that font. Either omit `fontFace` in cells (let PowerPoint fall back) or use a widely installed CJK face (e.g. `"Microsoft YaHei"`, `"PingFang SC"`, `"Noto Sans SC"`).

**Why only tables break:** pptxgenjs applies `fontFace` to **latin + ea + cs** in the same run. Missing glyphs (Poppins, Georgia, or MiSans not installed) → **□** in `addTable` cells; `addText` on the same slide may still look fine due to viewer substitution.

**Dense slides:** many `addTable` + `addText` siblings on one slide can cause duplicate OOXML ids — split heavy pages or merge side notes into one text frame.

```javascript
// Simple 2×2 — no fontFace in cells (CJK-safe fallback)
const rows = [
  [
    { text: "列 A", options: { bold: true, fontSize: 12, color: "FFFFFF", fill: { color: "333333" } } },
    { text: "列 B", options: { bold: true, fontSize: 12, color: "FFFFFF", fill: { color: "333333" } } },
  ],
  [
    { text: "单元格 1", options: { fontSize: 11, color: "272C2C" } },
    { text: "单元格 2", options: { fontSize: 11, color: "272C2C" } },
  ],
];
slide.addTable(rows, {
  x: 0.5, y: 1.5, w: 9, h: 2.2,
  colW: [4.5, 4.5],
  border: { pt: 1, color: "E0E0E0" },
});

// Colspan — one cell spans two columns; colW length = logical column count
const merged = [
  [
    { text: "Header L", options: { bold: true, fill: { color: "444444" }, color: "FFFFFF" } },
    { text: "Header R", options: { bold: true, fill: { color: "444444" }, color: "FFFFFF" } },
  ],
  [{ text: "Full-width note spanning both columns", options: { colspan: 2, fontSize: 10 } }],
];
slide.addTable(merged, { x: 0.5, y: 4, w: 9, h: 1, colW: [4.5, 4.5] });
```

Apply **brand header colours and positions** from the active `*-deck.md` — this section only documents table **syntax**.

---

## Charts

```javascript
// Bar chart
slide.addChart("bar", [{
  name: "Sales", labels: ["Q1", "Q2", "Q3", "Q4"], values: [4500, 5500, 6200, 7100]
}], {
  x: 0.5, y: 0.6, w: 6, h: 3, barDir: 'col',
  showTitle: true, title: 'Quarterly Sales'
});

// Line chart
slide.addChart("line", [{
  name: "Temp", labels: ["Jan", "Feb", "Mar"], values: [32, 35, 42]
}], { x: 0.5, y: 4, w: 6, h: 3, lineSize: 3, lineSmooth: true });

// Pie chart
slide.addChart("pie", [{
  name: "Share", labels: ["A", "B", "Other"], values: [35, 45, 20]
}], { x: 7, y: 1, w: 5, h: 4, showPercent: true });
```

### Better-Looking Charts

Default charts look dated. Apply these options for a modern, clean appearance:

```javascript
slide.addChart("bar", chartData, {
  x: 0.5, y: 1, w: 9, h: 4, barDir: "col",

  // Custom colors (match your presentation palette)
  chartColors: ["0D9488", "14B8A6", "5EEAD4"],

  // Clean background
  chartArea: { fill: { color: "FFFFFF" }, roundedCorners: true },

  // Muted axis labels
  catAxisLabelColor: "64748B",
  valAxisLabelColor: "64748B",

  // Subtle grid (value axis only)
  valGridLine: { color: "E2E8F0", size: 0.5 },
  catGridLine: { style: "none" },

  // Data labels on bars
  showValue: true,
  dataLabelPosition: "outEnd",
  dataLabelColor: "1E293B",

  // Hide legend for single series
  showLegend: false,
});
```

**Key styling options:**
- `chartColors: [...]` - hex colors for series/segments
- `chartArea: { fill, border, roundedCorners }` - chart background
- `catGridLine/valGridLine: { color, style, size }` - grid lines (`style: "none"` to hide)
- `lineSmooth: true` - curved lines (line charts)
- `legendPos: "r"` - legend position: "b", "t", "l", "r", "tr"

---

## Common Pitfalls

⚠️ These issues cause file corruption, visual bugs, or broken output. Avoid them.

1. **NEVER use "#" with hex colors** - causes file corruption
   ```javascript
   color: "FF0000"      // ✅ CORRECT
   color: "#FF0000"     // ❌ WRONG
   ```

2. **NEVER encode opacity in hex color strings** - 8-char colors (e.g., `"00000020"`) corrupt the file. Use the `opacity` property instead.
   ```javascript
   shadow: { type: "outer", blur: 6, offset: 2, color: "00000020" }          // ❌ CORRUPTS FILE
   shadow: { type: "outer", blur: 6, offset: 2, color: "000000", opacity: 0.12 }  // ✅ CORRECT
   ```
3. **Never reuse one const style = { fill, line, shadow, … } (or any shared sub-object) across two or more calls** — the second call receives already-corrupted props and can emit invalid OOXML. Always pass a fresh options object per call (factory helpers like () => ({ … }) / { …base, fill: { …baseFill } } with new nested objects for fill / line / shadow).
   ```javascript
   const cardFill = { color: "FFFFFF" };
   slide.addShape("rect", { x: 0.5, y: 1, w: 3, h: 2, fill: cardFill });
   slide.addShape("rect", { x: 4, y: 1, w: 3, h: 2, fill: cardFill });   // ❌ CORRUPTS

   // 工厂函数 — 每次返回新对象
   const cardFill = () => ({ color: "FFFFFF" });
   slide.addShape("rect", { x: 0.5, y: 1, w: 3, h: 2, fill: cardFill() });
   slide.addShape("rect", { x: 4, y: 1, w: 3, h: 2, fill: cardFill() });
   ```
4. **`line: { … }` across multiple `addShape` calls** — same mutation trap as `shadow`: do not reuse one `const` object; use a factory or a fresh literal each time.

  ```javascript
  const border = { color: "E0E0E0", width: 1 };
  slide.addShape("rect", { x: 0.5, y: 1, w: 3, h: 2, fill: { color: "FFFFFF" }, line: border });
  slide.addShape("rect", { x: 4, y: 1, w: 3, h: 2, fill: { color: "FFFFFF" }, line: border }); // ❌ second call may get mutated line

  const makeLine = () => ({ color: "E0E0E0", width: 1 });
  slide.addShape("rect", { x: 0.5, y: 1, w: 3, h: 2, fill: { color: "FFFFFF" }, line: makeLine() });
  slide.addShape("rect", { x: 4, y: 1, w: 3, h: 2, fill: { color: "FFFFFF" }, line: makeLine() }); // ✅ fresh object each time
  ```

5. **Use `bullet: true`** - NEVER unicode symbols like "•" (creates double bullets), also avoid dot + handwritten numbering:`"1. `"/ `"1)`" / `"（1）`"

6. **Use `breakLine: true`** between array items or text runs together

7. **Avoid `lineSpacing` with bullets** - causes excessive gaps; use `paraSpaceAfter` instead （said 2-6 pt, avoid>12）

8. **Each presentation needs fresh instance** - don't reuse `pptxgen()` objects

9. **NEVER reuse option objects across calls** - PptxGenJS mutates objects in-place (e.g. converting shadow values to EMU). Sharing one object between multiple calls corrupts the second shape.
   ```javascript
   const shadow = { type: "outer", blur: 6, offset: 2, color: "000000", opacity: 0.15 };
   slide.addShape("rect", { shadow, ... });  // ❌ second call gets already-converted values
   slide.addShape("rect", { shadow, ... });

   const makeShadow = () => ({ type: "outer", blur: 6, offset: 2, color: "000000", opacity: 0.15 });
   slide.addShape("rect", { shadow: makeShadow(), ... });  // ✅ fresh object each time
   slide.addShape("rect", { shadow: makeShadow(), ... });
   ```

10. **Don't pair a sharp `"rect"` accent bar on a `"roundRect"` base** — corners never line up. Use two `"rect"` shapes for that pattern instead.
   ```javascript
   // ❌ WRONG: Accent bar doesn't cover rounded corners
   slide.addShape("roundRect", { x: 1, y: 1, w: 3, h: 1.5, fill: { color: "FFFFFF" } });
   slide.addShape("rect", { x: 1, y: 1, w: 0.08, h: 1.5, fill: { color: "FF6600" } }); // brand accent — not `charts_palette`

   // ✅ CORRECT: Use "rect" for clean alignment
   slide.addShape("rect", { x: 1, y: 1, w: 3, h: 1.5, fill: { color: "FFFFFF" } });
   slide.addShape("rect", { x: 1, y: 1, w: 0.08, h: 1.5, fill: { color: "FF6600" } });
   ```

11. **Strictly positive `w` and `h` (inches) on every `addText` / `addShape` / `addTable` / `addImage`** — OOXML requires **non-negative** extents in EMU. A **negative or zero `h`** on a text box (e.g. `slideH - y` miscalc) becomes **`cy < 0`** in the package → PowerPoint **repair** / **online preview failure**. Use **literal positive** dimensions; if you derive height from “remaining slide”, **clamp** to at least **~0.25″** and ensure **`y + h ≤ 7.5`** (slide height). Exception: a **`"line"`** shape may use **`h: 0`**; do **not** use **`h: 0`** for body **`addText`**.

12. **CJK + `fontFace` on tables** — Latin-only or missing fonts (Poppins, Arial, Georgia, MiSans if not installed) on `addTable` / cell `options` → Chinese **□** in cells. Omit `fontFace` in table cells or use a theme `fontCjk` / widely installed CJK face on every cell.

13. **Brand PNG aspect ratio** — `addImage` with wrong `w:h` **stretches** the asset (common on Inspire logo/corner). Compute `h = w * (imgHeight / imgWidth)` from the PNG’s pixel dimensions, or use `sizing: { type: 'contain', w, h }`. HTML: `width` + `height: auto` + `object-fit: contain` — never fix both width and height unless the ratio matches.

---

## Quick Reference

- **Shapes**: `'rect'`, `'ellipse'`, `'line'`, `'roundRect'` (string literals — **not** `pres.shapes.*`)
- **Charts**: `'bar'`, `'line'`, `'pie'`, `'doughnut'`, `'scatter'`, `'bubble'`, `'radar'` (string literals - **not** `pres.charts.*`)
- **Layouts**: `LAYOUT_16x9`, `LAYOUT_WIDE` (pick one per deck — see theme `*-deck.md`)
- **Alignment**: "left", "center", "right"
- **Stacked bar/column chart labels**: `ctr`, `inEnd`, `inBase` only — not `outEnd`

