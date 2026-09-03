# Ascentium theme (Word / docx-js)

Standalone brand spec for **Ascentium** Word documents. Do **not** mix with Inspire colours, fonts, or devices.

**Source:** Brand Guidelines Full Version R1.10 (Nov 2025).

**Default:** use this theme unless the user asks for **inspire**.

## Personality

Professional, confident, clear. Structured hierarchy; readable body copy; orange used for emphasis and CTAs, not overwhelming page fills.

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
| Document title | Poppins | 28–32 | custom paragraph, bold |
| Heading 1 | Poppins | 22–24 | `HeadingLevel.HEADING_1` |
| Heading 2 | Poppins | 18–20 | `HeadingLevel.HEADING_2` |
| Heading 3 | Poppins | 14–16 | `HeadingLevel.HEADING_3` |
| Body | Poppins | 11–12 | default paragraphs |
| Emphasis | Poppins | 11–12 | bold or `bold: true` |
| Chinese body | Noto Sans SC | 11–12 | same runs when needed |
| Caption / footer | Poppins | 9–10 | muted colour `878A8A` |

If Poppins is not available on the target machine, fall back to **Calibri** (body) and **Cambria** (headings) while keeping the Ascentium palette.

**TOC:** use built-in `HeadingLevel.HEADING_1` / `HEADING_2` for sections that should appear in a table of contents.

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
  fontCjk: 'Noto Sans SC',
  fontFallbackTitle: 'Cambria',
  fontFallbackBody: 'Calibri',
};
```

## Minimal docx-js starter

```javascript
const fs = require('fs');
const {
  Document, Packer, Paragraph, TextRun, HeadingLevel,
  AlignmentType, ShadingType, BorderStyle,
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
        children: [new TextRun({ text: 'Section one', bold: true, font: C.fontTitle })],
      }),
      new Paragraph({
        children: [new TextRun('Body paragraph with Ascentium styling.')],
      }),
    ],
  }],
});

Packer.toBuffer(doc).then((buf) => fs.writeFileSync('report.docx', buf));
```

**Table header example:** cell shading `{ type: ShadingType.CLEAR, fill: C.midnightGreen, color: 'auto' }`, run colour `FFFFFF`.

**Hyperlinks / emphasis:** `color: C.vibrantOrange` on `TextRun` for links and CTAs.
