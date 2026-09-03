# Inspire theme (Word / docx-js)

Standalone brand spec for **Inspire** Word documents. **Not Ascentium** — do not use Poppins, Noto Sans SC, orange palette, or Ascentium motifs.

**Source:** Inspire brand guidelines (Colour / Typography).

Use when the user asks for **inspire** (or Inspire AI branding).

## Personality

Tech-forward, calm. Creative Blue for emphasis only. Body text in deep gray (`333333`), not pure black.

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
| Heading 1 | MiSans | 20–22 | `HeadingLevel.HEADING_1` |
| Heading 2 | MiSans | 16–18 | `HeadingLevel.HEADING_2` |
| Body | MiSans | 11–12 | default paragraphs |
| Subtitle on cover | MiSans | 14–16 | colour `34B3E4` |
| Footer | MiSans | 9–10 | `999999` or `34B3E4` |

MiSans fallback: **PingFang SC → Microsoft YaHei → Arial**.

Chapter openers (e.g. `CONTENTS`): **Georgia** serif, colour `0A2342`.

## Document patterns

| Section | Background | Title | Body |
|---------|------------|-------|------|
| Cover | White or `F0F2F5` shading | `0A2342` Georgia title | `34B3E4` MiSans subtitle |
| Body | White | `0A2342` MiSans headings | `333333` MiSans |
| Section divider | optional `F0F2F5` paragraph shading | Georgia chapter label | — |
| Footer | — | — | `© 2026 Inspire | Confidential` in `34B3E4`, 9–10pt |

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
  fontChapter: 'Georgia',
};
```

## Minimal docx-js starter

```javascript
const fs = require('fs');
const {
  Document, Packer, Paragraph, TextRun, HeadingLevel, ShadingType,
} = require('docx');

const C = INSPIRE;

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
        children: [new TextRun({ text: '© 2026 Inspire | Confidential', color: C.creativeBlue, size: 18 })],
      }),
      new Paragraph({
        heading: HeadingLevel.HEADING_1,
        children: [new TextRun({ text: 'Section', bold: true, font: C.fontHeadline, color: C.starryBlues })],
      }),
      new Paragraph({
        children: [new TextRun('Body text in deep gray, not pure black.')],
      }),
    ],
  }],
});

Packer.toBuffer(doc).then((buf) => fs.writeFileSync('report.docx', buf));
```

**Callout paragraph:** shading `{ type: ShadingType.CLEAR, fill: C.techGray, color: 'auto' }`.
