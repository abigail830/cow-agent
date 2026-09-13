# Inspire theme (Word / docx-js)

Standalone brand spec for **Inspire** Word documents. **Not Ascentium** — do not use Poppins, Noto Sans SC, orange palette, or Ascentium motifs.

**Source:** Inspire brand guidelines (Colour / Typography).

Use when the user asks for **inspire** (or Inspire AI branding).

## Personality

Tech-forward, calm. Creative Blue for emphasis only. Body text in deep gray (`333333`), not pure black.

## Generation safety (docx-js)

Read before writing the generator script. More gotchas in `../SKILL.md`.

| Rule | Do |
|------|-----|
| **`TextRun.text` must be a string** | Always `{ text: String(value) }` — especially table cells, counts, dates. Never pass a number/boolean directly. |
| **No `\n` in text** | One block per `Paragraph`. Use `PageBreak` inside a paragraph for page breaks. |
| **Font names with spaces** | Safe: `MiSans`, `Georgia`, `Arial`, `Calibri`. Risky as `TextRun.font` or embedded fonts: `PingFang SC`, `Microsoft YaHei` (can corrupt the package — [docx-js #2521](https://github.com/dolanmiu/docx/issues/2521)). Prefer single-token names; split Latin/CJK runs (see [CJK / mixed script](#cjk--mixed-script)). |
| **`HeadingLevel` alone is not enough** | Built-in heading styles default to Word blue. Override in `styles.paragraphStyles` **or** set `color` + `font` on every heading `TextRun`. |
| **Font fallback** | docx-js has no CSS-style fallback chain. The prose chain `PingFang SC → Microsoft YaHei → Arial` is for **Word viewer substitution**, not something you declare in one `font` field. Use `fontFallbackBody` when MiSans may be missing, or split runs by script. |

## Colours (docx-js — hex **without** `#`)

| Role | Name | Hex |
|------|------|-----|
| Primary dark | Starry Blues | `0A2342` |
| Accent / links | Creative Blue | `34B3E4` |
| Light section bg | Tech Gray | `F0F2F5` |
| Page background | White | `FFFFFF` |
| Body text | Deep gray | `333333` |
| Muted / footer | Light gray | `999999` |
| Table header fill | Starry Blues | `0A2342` |
| Table header text | White | `FFFFFF` |
| Chart / callout aux | Amethys | `6964AD` |
| Chart / callout aux | Myrtle Deep Green | `005043` |

**Creative Blue:** headings accents, hyperlinks, footer line — not large background fills.

## Typography (Word font names)

| Element | Font | Size (pt) | docx-js |
|---------|------|-----------|---------|
| Document / chapter title | Georgia | 26–32 | custom style, serif |
| Heading 1 | MiSans | 20–22 | `HeadingLevel.HEADING_1` + brand colour |
| Heading 2 | MiSans | 16–18 | `HeadingLevel.HEADING_2` + brand colour |
| Body | MiSans | 11–12 | default paragraphs |
| Subtitle on cover | MiSans | 14–16 | colour `34B3E4` |
| Footer | MiSans | 9–10 | `999999` or `34B3E4` |

**Viewer fallback** (Word substitutes when MiSans is missing): PingFang SC → Microsoft YaHei → Arial. Do not paste spaced names into a single `font:` unless required — see [Generation safety](#generation-safety-docx-js).

Chapter openers (e.g. `CONTENTS`): **Georgia** serif, colour `0A2342`.

## CJK / mixed script

**MiSans** supports Chinese when installed; many target machines **do not** have it — Chinese may render as □ if forced on every run.

**Georgia (`fontChapter`) is Latin-only** — use only for English chapter labels, never for Chinese table cells or body copy.

```javascript
const HAS_CJK = /[\u4e00-\u9fff\u3400-\u4dbf]/;
function fontFor(text) {
  return HAS_CJK.test(text) ? C.fontCjkFallback : C.fontBody;
}

// Latin body
new TextRun({ text: 'Section overview', font: C.fontBody, size: 22, color: C.text })
// Chinese body (separate run)
new TextRun({ text: '章节概述', font: C.fontCjkFallback, size: 22, color: C.text })
```

**Tables with Chinese:** do not set `font: C.fontHeadline` or `C.fontChapter` on cells. Safest: **omit `font`** on mixed cells and let Word substitute. For all-Chinese cells, use `font: C.fontCjkFallback` or omit `font`. Never use Georgia in a cell with CJK text.

## Document patterns

| Section | Background | Title | Body |
|---------|------------|-------|------|
| Cover | White or `F0F2F5` shading | `0A2342` Georgia title | `34B3E4` MiSans subtitle |
| Body | White | `0A2342` MiSans headings | `333333` MiSans |
| Section divider | optional `F0F2F5` paragraph shading | Georgia chapter label | — |
| Footer | — | — | `© {year} Inspire \| Confidential` in `34B3E4`, 9–10pt |

**Avoid:** Ascentium orange, Poppins, pure black body text, heavy colour bars in headers.

## docx-js constant object

```javascript
const INSPIRE = {
  starryBlues: '0A2342',
  creativeBlue: '34B3E4',
  techGray: 'F0F2F5',
  white: 'FFFFFF',
  text: '333333',
  textMuted: '999999',
  amethys: '6964AD',
  myrtleGreen: '005043',
  fontHeadline: 'MiSans',
  fontBody: 'MiSans',
  fontChapter: 'Georgia',              // Latin chapter labels only
  fontCjkFallback: 'Microsoft YaHei',    // widely installed CJK; spaced name
  fontFallbackBody: 'Arial',             // use when MiSans unavailable
  fontFallbackChapter: 'Georgia',
};
```

## Minimal docx-js starter

```javascript
const fs = require('fs');
const {
  Document, Packer, Paragraph, TextRun, HeadingLevel, ShadingType,
} = require('docx');

const C = INSPIRE;
const year = String(new Date().getFullYear());

const doc = new Document({
  styles: {
    default: {
      document: {
        run: { font: C.fontBody, size: 22, color: C.text },
      },
    },
    paragraphStyles: [
      {
        id: 'InspireTitle',
        name: 'Inspire Title',
        basedOn: 'Normal',
        run: { size: 52, font: C.fontChapter, color: C.starryBlues },
        paragraph: { spacing: { after: 160 } },
      },
      {
        id: 'Heading1',
        name: 'Heading 1',
        basedOn: 'Normal',
        next: 'Normal',
        quickFormat: true,
        run: { size: 40, bold: true, font: C.fontHeadline, color: C.starryBlues },
        paragraph: { spacing: { before: 240, after: 120 }, outlineLevel: 0 },
      },
      {
        id: 'Heading2',
        name: 'Heading 2',
        basedOn: 'Normal',
        next: 'Normal',
        quickFormat: true,
        run: { size: 32, bold: true, font: C.fontHeadline, color: C.starryBlues },
        paragraph: { spacing: { before: 200, after: 80 }, outlineLevel: 1 },
      },
    ],
  },
  sections: [{
    properties: { page: { size: { width: 12240, height: 15840 } } },
    children: [
      new Paragraph({
        style: 'InspireTitle',
        children: [new TextRun({ text: 'Document title' })],
      }),
      new Paragraph({
        children: [new TextRun({ text: 'Creative Blue subtitle', color: C.creativeBlue, size: 28 })],
      }),
      new Paragraph({
        spacing: { before: 400 },
        children: [new TextRun({
          text: `© ${year} Inspire | Confidential`,
          color: C.creativeBlue,
          size: 18,
        })],
      }),
      new Paragraph({
        heading: HeadingLevel.HEADING_1,
        children: [new TextRun({
          text: 'Section',
          bold: true,
          font: C.fontHeadline,
          color: C.starryBlues,
        })],
      }),
      new Paragraph({
        children: [new TextRun({ text: 'Body text in deep gray, not pure black.' })],
      }),
    ],
  }],
});

Packer.toBuffer(doc).then((buf) => fs.writeFileSync('report.docx', buf));
```

**Callout paragraph:** shading `{ type: ShadingType.CLEAR, fill: C.techGray, color: 'auto' }`.

**Table header example:** cell shading `{ type: ShadingType.CLEAR, fill: C.starryBlues, color: 'auto' }`, run colour `FFFFFF`. Cell text: `{ text: String(cellValue) }`. Do not set `fontChapter` or `fontHeadline` on cells that contain Chinese — omit `font` or use `fontCjkFallback`.
