# Ascentium theme (Word / docx-js)

Standalone brand spec for **Ascentium** Word documents. Do **not** mix with Inspire colours, fonts, or devices.

**Source:** Brand Guidelines Full Version R1.10 (Nov 2025).

**Default:** use this theme unless the user asks for **inspire**.

## Personality

Professional, confident, clear. Structured hierarchy; readable body copy; orange used for emphasis and CTAs, not overwhelming page fills.

## Generation safety (docx-js)

Read before writing the generator script. More gotchas in `../SKILL.md`.

| Rule | Do |
|------|-----|
| **`TextRun.text` must be a string** | Always `{ text: String(value) }` — especially table cells, counts, dates, IDs. Never pass a number/boolean directly. |
| **No `\n` in text** | One block per `Paragraph`. Use `PageBreak` inside a paragraph for page breaks. |
| **Font names with spaces** | Safe: `Poppins`, `Calibri`, `Cambria`. Risky as `TextRun.font` or embedded fonts: `Noto Sans SC`, `Microsoft YaHei` (can corrupt the package — [docx-js #2521](https://github.com/dolanmiu/docx/issues/2521)). Prefer single-token names; split Latin/CJK into separate runs (see [CJK / mixed script](#cjk--mixed-script)). |
| **`HeadingLevel` alone is not enough** | Built-in heading styles default to Word blue (`2E74B5`). Override in `styles.paragraphStyles` **or** set `color` + `font` on every heading `TextRun`. |
| **Font fallback** | docx-js has no CSS-style fallback chain. Use `fontFallbackBody` / `fontFallbackTitle` as the primary `font` when Poppins may be missing, or split runs by script (below). |

## Colours (docx-js — hex **without** `#`)

| Role | Name | Hex |
|------|------|-----|
| Primary accent / links | Vibrant Orange | `FF6611` |
| Primary text | Midnight Green | `0F1514` |
| Page background | White | `FFFFFF` |
| Soft highlight / callout box | Orange 1 | `FFF0E7` |
| Secondary text | MG 1 | `B7B9B9` |
| Secondary text (darker) | MG 3 | `575B5B` |
| Table header fill | Midnight Green | `0F1514` |
| Table header text | White | `FFFFFF` |
| Supporting | Teal Green | `077069` |
| Supporting | Sky Blue | `1877F2` |
| Errors only | Error Red | `DC3545` |

**Accessible pairings:** Midnight Green on White; Vibrant Orange on Midnight Green; Midnight Green on Orange 1.

**Owning Orange:** use `FFF0E7` / `FFD1B8` for shaded callout paragraphs or table row highlights; avoid full-page orange backgrounds.

## Typography (Word font names)

| Element | Font | Size (pt) | docx-js |
|---------|------|-----------|---------|
| Document title | Poppins | 28–32 | custom paragraph style, bold |
| Heading 1 | Poppins | 22–24 | `HeadingLevel.HEADING_1` + brand colour |
| Heading 2 | Poppins | 18–20 | `HeadingLevel.HEADING_2` + brand colour |
| Heading 3 | Poppins | 14–16 | `HeadingLevel.HEADING_3` + brand colour |
| Body | Poppins | 11–12 | default paragraphs |
| Emphasis | Poppins | 11–12 | bold or `bold: true` |
| Chinese body | Noto Sans SC | 11–12 | **separate `TextRun`** — see CJK section |
| Caption / footer | Poppins | 9–10 | muted colour `878A8A` |

If Poppins is not installed on the target machine, use **`fontFallbackBody` (Calibri)** for body and **`fontFallbackTitle` (Cambria)** for headings while keeping the Ascentium palette.

**TOC:** use `HeadingLevel.HEADING_1` / `HEADING_2` for sections that should appear in a table of contents.

## CJK / mixed script

**Poppins has no CJK glyphs.** Do not put Chinese and Latin in the same `TextRun` when the run uses `font: C.fontBody`.

```javascript
const HAS_CJK = /[\u4e00-\u9fff\u3400-\u4dbf]/;
function fontFor(text) {
  return HAS_CJK.test(text) ? C.fontCjk : C.fontBody;
}

// Latin run
new TextRun({ text: 'Audit scope: ', font: C.fontBody, size: 22, color: C.midnightGreen })
// Chinese run (separate)
new TextRun({ text: '质量管理体系', font: C.fontCjk, size: 22, color: C.midnightGreen })
```

**Tables with Chinese:** do not set Poppins on every cell. Either omit `font` on mixed cells (Word substitutes) or set `font: C.fontCjk` on cells that contain Chinese. Never use Poppins alone in a cell with CJK text — glyphs show as □.

**`fontCjk` note:** brand face is `Noto Sans SC` (contains a space). For maximum open compatibility, use `fontCjkFallback` (`Microsoft YaHei`, also spaced) only on Chinese-only runs, or omit `font` and let Word pick a system CJK face.

## Document patterns

| Section | Background / shading | Title colour | Body colour |
|---------|-------------------|--------------|-------------|
| Cover block | optional `FFF0E7` shading on title area | `0F1514` | `575B5B` for subtitle |
| Body | White | `0F1514` headings | `0F1514` body |
| Callout / note | cell or paragraph shading `FFF0E7` | `0F1514` | `0F1514` |
| Table header row | fill `0F1514` | `FFFFFF` | — |

**Avoid:** decorative full-width colour bars in headers/footers, pure black (`000000`) when Midnight Green suffices, default beige page backgrounds.

## docx-js constant object

```javascript
const ASCENTIUM = {
  vibrantOrange: 'FF6611',
  midnightGreen: '0F1514',
  white: 'FFFFFF',
  orange1: 'FFF0E7',
  orange2: 'FFD1B8',
  mg1: 'B7B9B9',
  mg2: '878A8A',
  mg3: '575B5B',
  tealGreen: '077069',
  skyBlue: '1877F2',
  errorRed: 'DC3545',
  fontTitle: 'Poppins',
  fontBody: 'Poppins',
  fontCjk: 'Noto Sans SC',           // brand CJK — spaced name; Chinese-only runs
  fontCjkFallback: 'Microsoft YaHei', // widely installed CJK; spaced name
  fontFallbackTitle: 'Cambria',       // use when Poppins unavailable
  fontFallbackBody: 'Calibri',        // use when Poppins unavailable
};
```

## Minimal docx-js starter

```javascript
const fs = require('fs');
const {
  Document, Packer, Paragraph, TextRun, HeadingLevel, ShadingType,
} = require('docx');

const C = ASCENTIUM;

const doc = new Document({
  styles: {
    default: {
      document: {
        run: { font: C.fontBody, size: 22, color: C.midnightGreen }, // half-points: 22 = 11pt
      },
    },
    paragraphStyles: [
      {
        id: 'Title',
        name: 'Title',
        basedOn: 'Normal',
        run: { size: 56, bold: true, font: C.fontTitle, color: C.midnightGreen },
        paragraph: { spacing: { after: 200 } },
      },
      // Override built-in heading colours (default is Word blue 2E74B5)
      {
        id: 'Heading1',
        name: 'Heading 1',
        basedOn: 'Normal',
        next: 'Normal',
        quickFormat: true,
        run: { size: 32, bold: true, font: C.fontTitle, color: C.midnightGreen },
        paragraph: { spacing: { before: 240, after: 120 }, outlineLevel: 0 },
      },
      {
        id: 'Heading2',
        name: 'Heading 2',
        basedOn: 'Normal',
        next: 'Normal',
        quickFormat: true,
        run: { size: 26, bold: true, font: C.fontTitle, color: C.midnightGreen },
        paragraph: { spacing: { before: 200, after: 80 }, outlineLevel: 1 },
      },
    ],
  },
  sections: [{
    properties: {
      page: { size: { width: 12240, height: 15840 } }, // US Letter
    },
    children: [
      new Paragraph({
        style: 'Title',
        children: [new TextRun({ text: 'Report title' })],
      }),
      new Paragraph({
        spacing: { after: 120 },
        children: [new TextRun({ text: 'Subtitle or date', color: C.mg2, size: 22 })],
      }),
      new Paragraph({
        heading: HeadingLevel.HEADING_1,
        children: [new TextRun({
          text: 'Section one',
          bold: true,
          font: C.fontTitle,
          color: C.midnightGreen,
        })],
      }),
      new Paragraph({
        children: [new TextRun({ text: 'Body paragraph with Ascentium styling.' })],
      }),
      // CJK: separate runs — do not mix scripts under Poppins
      new Paragraph({
        children: [
          new TextRun({ text: 'Scope: ', font: C.fontBody, size: 22, color: C.midnightGreen }),
          new TextRun({ text: '示例中文', font: C.fontCjk, size: 22, color: C.midnightGreen }),
        ],
      }),
    ],
  }],
});

Packer.toBuffer(doc).then((buf) => fs.writeFileSync('report.docx', buf));
```

**Table header example:** cell shading `{ type: ShadingType.CLEAR, fill: C.midnightGreen, color: 'auto' }`, run colour `FFFFFF`. Cell text: `{ text: String(cellValue) }` — never a raw number.

**Hyperlinks / emphasis:** `color: C.vibrantOrange` on `TextRun` for links and CTAs.
