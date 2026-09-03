---
name: docx
description: "Use this skill whenever the user wants to create, read, edit, or manipulate Word documents (.docx / .dotx): reports, memos, letters, templates, tracked changes, comments, or image insertion. Do NOT use for PDFs, spreadsheets, or non-Word deliverables."
license: Proprietary. LICENSE.txt has complete terms
---

# DOCX skill

A `.docx` is a ZIP of XML parts. Pick the path by task:

| Task | Approach |
|------|----------|
| **Create** a new document | **Node.js + docx** (npm) — see [Brand themes](#brand-themes) and [docx-js gotchas](#docx-js-gotchas) |
| **Edit** an existing document | unzip → edit `word/document.xml` → zip (docx-js cannot open existing files) |
| **Read** content | `pandoc -t markdown file.docx` |

Paths below are relative to this skill directory unless noted.

## Create new documents (docx-js)

**Workflow**

1. Clarify purpose, audience, length, and brand theme if missing.
2. **Default theme: `ascentium`** — use `themes/inspire.md` only when the user asks for Inspire.
3. Read the matching theme file for colours, fonts, document patterns, and the `ASCENTIUM` / `INSPIRE` constant object.
4. Write a **Node.js script** using the `docx` package; export with `Packer.toBuffer()` / `writeFileSync`.
5. Optionally spot-check structure with `pandoc -t markdown output.docx` (headings, order, obvious gaps).
6. **`publish_artifact`** on the final `.docx` — not PDF previews or validate scratch files.

`docx` is preinstalled. Do not run `npm install` unless `require('docx')` fails.

**Do not** require PDF render + image inspection for normal create-and-deliver requests. Fix formatting in the generator; use pandoc for a quick text/structure check if unsure.

## Brand themes

Two **independent** themes. **Never mix** colours, fonts, or styling cues.

| Theme | Brand | Spec file | When |
|-------|-------|-----------|------|
| **`ascentium`** (default) | Ascentium | `themes/ascentium.md` | Corporate reports, memos, client Word deliverables |
| **`inspire`** | Inspire | `themes/inspire.md` | Inspire / Inspire AI materials |

Each theme file includes:

- Hex values for docx-js (`FF6611`, not `#FF6611`)
- Word font names and point sizes
- Cover, heading, body, table, and footer patterns
- A minimal `docx` script starter

Do not invent a third palette unless the user explicitly opts out of brand themes.

## docx-js gotchas

- **Page size defaults to A4.** US Letter: `page: { size: { width: 12240, height: 15840 } }` (DXA; 1440 = 1″).
- **Landscape:** portrait dimensions + `orientation: PageOrientation.LANDSCAPE`.
- **Font sizes are half-points:** `size: 22` → 11pt body text.
- **Tables:** set `columnWidths` on the table AND `width` on every cell (`WidthType.DXA`). Column widths must sum to table width.
- **Table shading:** `ShadingType.CLEAR`, never `SOLID` (renders black).
- **Lists:** use `numbering` with `LevelFormat.BULLET` — never literal `•`.
- **`ImageRun` requires `type:`** (`png`, `jpg`, …).
- **`PageBreak` inside a `Paragraph`.**
- **Never use `\n`** — separate `Paragraph` elements.
- **TOC:** headings need `HeadingLevel.HEADING_1` / `HEADING_2` (or styles with `outlineLevel`).
- **Horizontal rules:** paragraph bottom border, not a one-row table.
- **Dot leaders:** `PositionalTab` with `PositionalTabLeader.DOT`, not padded dots.

## Design (all themes)

- Clear hierarchy: title → H1 sections → H2 subsections → body.
- One primary idea per section; use lists and tables for dense data.
- Left-align body text; consistent spacing between blocks.
- **Avoid:** walls of unbroken text, mixed arbitrary fonts, decorative header colour bars.

## Edit existing documents (optional)

Use when the user supplies a `.docx` to modify, redline, or comment — not for typical “write a new report” requests.

```bash
unzip -q doc.docx -d unpacked/
find unpacked -type l -delete
python scripts/merge_runs.py unpacked/
# edit unpacked/word/document.xml in place — do NOT pretty-print
(cd unpacked && rm -f ../out.docx && zip -Xr ../out.docx .)
python scripts/office/validate.py out.docx --original doc.docx
```

| Script | Purpose |
|--------|---------|
| `scripts/merge_runs.py` | Merge fragmented runs so text is findable in XML |
| `scripts/accept_changes.py` | Produce clean copy with tracked changes accepted |
| `scripts/comment.py` | Add Word comments (directory or `.docx` mode) |
| `scripts/office/validate.py` | XSD / relationship checks when editing OOXML |

**Tracked changes:** validate with `--author "<name>"` and `--original` when redlining — untracked edits are invisible in the accepted view.

Legacy `.doc`: `python scripts/office/soffice.py --headless --convert-to docx file.doc`

## Read content

```bash
pandoc -t markdown file.docx
```

For tracked-change aware extract: `pandoc --track-changes=accept file.docx -t markdown`

## Dependencies

- **Create:** Node.js, `docx` (preinstalled)
- **Edit / read:** Python 3, `pandoc`, `defusedxml` (via scripts)
- **Optional:** LibreOffice via `scripts/office/soffice.py` (legacy `.doc` only)

## Scripts not in the default create workflow

`scripts/office/validate.py`, LibreOffice PDF conversion, and `pdftoppm` image inspection remain for **edit/redline** workflows — not required after every docx-js `writeFile`.
