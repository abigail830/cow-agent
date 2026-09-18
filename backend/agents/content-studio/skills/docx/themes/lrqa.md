# LRQA theme (Word / docx-js)

Standalone brand spec for **LRQA** Word documents. **Not Ascentium / Inspire** — do not use orange/Poppins, Starry Blues/Creative Blue, MiSans, or Georgia chapter motifs.

**Source:** LRQA deck layouts (dark navy + teal accent) and `assets` logo mark.

Use when the user asks for **lrqa** / **LRQA**, or when the agent default is LRQA Assist.

## Personality

Corporate assurance brand: dark navy authority, bright teal accent sparingly, clean sans-serif hierarchy. Body text near-black on white — not pure black flood fills.

## Generation safety (docx-js)

Read before writing the generator script. More gotchas in `../SKILL.md`.

| Rule | Do |
|------|-----|
| **`TextRun.text` must be a string** | Always `{ text: String(value) }` — especially table cells, counts, dates. |
| **No `\n` in text** | One block per `Paragraph`. Use `PageBreak` inside a paragraph for page breaks. |
| **Font names** | Prefer `Arial` / `Calibri` (single-token). For CJK cells prefer omit `font` or `Microsoft YaHei`. |
| **`HeadingLevel` alone is not enough** | Override heading colour/font in `styles.paragraphStyles` **or** on every heading `TextRun`. |
| **No logo in Word** | LRQA PNG chrome is for pptx/html-slides only. Word uses colour/typography patterns. |

## Colours (docx-js — hex **without** `#`)

| Role | Name | Hex |
|------|------|-----|
| Primary dark / table header | Navy | `1A1E33` |
| Mid navy (rare shading) | Navy Mid | `33374C` |
| Accent / links / H1 emphasis | Teal | `00DDB3` |
| Page background | White | `FFFFFF` |
| Light section bg | Mist | `F5F7F8` |
| Body text | Near black | `1A1E33` |
| Muted / footer | Gray | `6B7280` |
| Table header text | White | `FFFFFF` |

**Teal:** headings accents, hyperlinks, footer accent line — not large background fills.

## Typography (Word font names)

| Element | Font | Size (pt) | docx-js |
|---------|------|-----------|---------|
| Document / cover title | Arial | 26–32 | custom style, bold |
| Heading 1 | Arial | 20–22 | `HeadingLevel.HEADING_1` + `teal` or `navy` |
| Heading 2 | Arial | 16–18 | `HeadingLevel.HEADING_2` + `navy` |
| Body | Arial | 11–12 | default paragraphs |
| Subtitle on cover | Arial | 14–16 | colour `00DDB3` |
| Footer | Arial | 9–10 | `6B7280` |

**CJK / mixed script:** split runs; use omit-`font` or `fontCjkFallback` for Chinese table cells.

```javascript
const HAS_CJK = /[\u4e00-\u9fff\u3400-\u4dbf]/;
function fontFor(text) {
  return HAS_CJK.test(text) ? C.fontCjkFallback : C.fontBody;
}
```

## Document patterns

| Section | Background | Title | Body |
|---------|------------|-------|------|
| Cover | White or `F5F7F8` | `1A1E33` bold title | `00DDB3` subtitle |
| Body | White | `00DDB3` H1 / `1A1E33` H2 | `1A1E33` body |
| Section divider | optional `F5F7F8` shading | Navy label | — |
| Footer | — | — | `© {year} LRQA \| Confidential` in `6B7280`, optional teal rule |

**Avoid:** Ascentium orange, Inspire Creative Blue flood, Poppins, MiSans, Georgia as body font.

## docx-js constant object

```javascript
const LRQA = {
  navy: '1A1E33',
  navyMid: '33374C',
  teal: '00DDB3',
  mist: 'F5F7F8',
  white: 'FFFFFF',
  text: '1A1E33',
  textMuted: '6B7280',
  fontHeadline: 'Arial',
  fontBody: 'Arial',
  fontCjkFallback: 'Microsoft YaHei',
  fontFallbackBody: 'Arial',
};
```

## Minimal docx-js starter

```javascript
const fs = require('fs');
const {
  Document, Packer, Paragraph, TextRun, HeadingLevel, ShadingType,
} = require('docx');

const C = LRQA;
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
        id: 'LrqaTitle',
        name: 'LRQA Title',
        basedOn: 'Normal',
        run: { size: 52, bold: true, font: C.fontHeadline, color: C.navy },
        paragraph: { spacing: { after: 160 } },
      },
      {
        id: 'Heading1',
        name: 'Heading 1',
        basedOn: 'Normal',
        next: 'Normal',
        quickFormat: true,
        run: { size: 40, bold: true, font: C.fontHeadline, color: C.teal },
        paragraph: { spacing: { before: 240, after: 120 }, outlineLevel: 0 },
      },
      {
        id: 'Heading2',
        name: 'Heading 2',
        basedOn: 'Normal',
        next: 'Normal',
        quickFormat: true,
        run: { size: 32, bold: true, font: C.fontHeadline, color: C.navy },
        paragraph: { spacing: { before: 200, after: 80 }, outlineLevel: 1 },
      },
    ],
  },
  sections: [{
    properties: { page: { size: { width: 12240, height: 15840 } } },
    children: [
      new Paragraph({
        style: 'LrqaTitle',
        children: [new TextRun({ text: 'Document title' })],
      }),
      new Paragraph({
        children: [new TextRun({ text: 'Teal subtitle', color: C.teal, size: 28 })],
      }),
      new Paragraph({
        spacing: { before: 400 },
        children: [new TextRun({
          text: `© ${year} LRQA | Confidential`,
          color: C.textMuted,
          size: 18,
        })],
      }),
      new Paragraph({
        heading: HeadingLevel.HEADING_1,
        children: [new TextRun({
          text: 'Section',
          bold: true,
          font: C.fontHeadline,
          color: C.teal,
        })],
      }),
      new Paragraph({
        children: [new TextRun({ text: 'Body text in navy, teal for accents only.' })],
      }),
    ],
  }],
});

Packer.toBuffer(doc).then((buf) => fs.writeFileSync('report.docx', buf));
```

**Callout paragraph:** shading `{ type: ShadingType.CLEAR, fill: C.mist, color: 'auto' }`.

**Table header example:** cell shading `{ type: ShadingType.CLEAR, fill: C.navy, color: 'auto' }`, run colour `FFFFFF`. Cell text: `{ text: String(cellValue) }`. Omit `font` on mixed/CJK cells or use `fontCjkFallback`.
