---
name: html-slides
description: Create interactive HTML presentations with reveal.js. Use when the user wants web-based slides, HTML deck, browser presentation, or reveal.js instead of PowerPoint.
license: MIT
metadata:
  source: claude-office-skills/skills
  version: "2.0"
---

# HTML Slides Skill

## Directory layout

```
html-slides/
├── SKILL.md                 # workflow (this file)
├── references/              # theme pattern libraries (markdown only)
│   ├── ascentium-deck.md
│   └── inspire-deck.md
├── assets/                  # brand PNGs (sandbox / E2B; embed as base64 in HTML)
│   ├── ascentium/
│   └── inspire/
└── LICENSE.txt
```

`references/` holds copy-paste CSS/HTML patterns. `assets/` holds binary brand files — same split as pptx `themes/*.md` + no bundled images, but html-slides ships PNGs for deck chrome.

## Overview

Build **single-file**, **self-contained** HTML presentations with **reveal.js** on a fixed **1280×720** canvas.
Brand styling comes from **reference pattern libraries** (markdown with copy-paste CSS/HTML) — not external theme files.

## How to Use

1. Clarify topic, audience, and slide count if missing.
2. **Pick theme:** `ascentium` (default) or `inspire`. Never mix brands.
3. `activate_skill` for `html-slides`.
4. **`read`** the theme reference from the **sandbox mirror** (same pattern as pptx/docx themes):
   - Ascentium → `/home/user/content-studio/skills/html-slides/references/ascentium-deck.md`
   - Inspire → `/home/user/content-studio/skills/html-slides/references/inspire-deck.md`
5. Assemble the deliverable:
   - Copy **Part 1** (shell + tokens + base CSS) into one `<style>` block.
   - For each slide, copy **Part 2** pattern CSS (only patterns you use) + adapt the HTML into `<section>`.
   - Embed brand PNGs from `assets/<theme>/` as base64 data URIs (see theme reference §5).
6. `publish_artifact` with the sandbox path — the UI shows a download card; do not add download links in your reply.

**Do not** use external CSS files — copy CSS blocks from the reference into `<style>`.

## Theme references

| Theme | Reference file | Brand |
|-------|----------------|-------|
| **`ascentium`** (default) | `references/ascentium-deck.md` | Ascentium — Poppins + Noto Sans SC; PNGs in `assets/ascentium/` |
| **`inspire`** | `references/inspire-deck.md` | Inspire — MiSans + Georgia; PNGs in `assets/inspire/` |

Each reference contains:

1. **Part 1 — Core build system:** reveal.js shell, `Reveal.initialize`, `:root` tokens, base typography.
2. **Part 2 — Slide pattern library:** ready-made CSS + HTML for cover, bullets, comparison, stats, tables, CTA, etc.

**Workflow principle:** the reference is a **pattern library**, not documentation to summarize. Copy the code blocks into the deliverable; adapt text only.

## Slide canvas (1280×720)

- `Reveal.initialize({ width: 1280, height: 720, … })` — see theme reference Part 1.
- One `<section>` per slide; backgrounds and layout classes on `<section>`, not nested cards.
- **Do not** set `.reveal .slides section { position: relative }` — reveal.js requires `position: absolute` on each slide; `relative` stacks slides vertically so page 2+ render off-screen (gray viewport).
- Fit content inside the padded safe area; split dense slides rather than overflow.

## Skill resources (how to read)

Theme references and brand PNGs live in the sandbox (preinstalled in Content Studio). **Always `read` the sandbox path** — do not guess packaged-skill paths.

| Resource | Sandbox path (`read` / embed) |
|----------|-------------------------------|
| Ascentium patterns | `/home/user/content-studio/skills/html-slides/references/ascentium-deck.md` |
| Ascentium PNGs | `/home/user/content-studio/skills/html-slides/assets/ascentium/` |
| Inspire patterns | `/home/user/content-studio/skills/html-slides/references/inspire-deck.md` |
| Inspire PNGs | `/home/user/content-studio/skills/html-slides/assets/inspire/` |

`read_skill_resource` only accepts the **full** path shown after `read_skill_resource` in `<skill_resources>` (starts with `/.flue/packaged-skills/`). Short paths like `references/ascentium-deck.md` **will fail** — prefer the sandbox paths above. Binary PNGs are **not** packaged into the skill store; use sandbox `assets/` only.

## Markup discipline

- Use **only** class names defined in the reference Part 1–2 blocks you copied.
- Do not invent semantic classes (`eyebrow`, `stat-card`, …) unless you add matching CSS in the same `<style>`.
- All CSS must be **inlined** — published HTML has no sibling assets.
- **Brand `<img>`:** use `object-fit: contain`, native `aspect-ratio` from the reference, and **only one** of `width` / `height` as fixed — never stretch PNGs.

## reveal.js quick reference

### Fragments

```html
<section>
  <p class="fragment">Appears first</p>
  <p class="fragment fade-up">Then this</p>
</section>
```

### Speaker notes

```html
<aside class="notes">Speaker notes — press S in presenter mode.</aside>
```

### Code highlighting (optional)

```html
<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/reveal.js@4/plugin/highlight/monokai.css">
<script src="https://cdn.jsdelivr.net/npm/reveal.js@4/plugin/highlight/highlight.js"></script>
<!-- Reveal.initialize({ plugins: [RevealHighlight] }) -->
```

### Vertical slides

```html
<section>
  <section>Vertical 1</section>
  <section>Vertical 2</section>
</section>
```

## Publishing

1. Write final `.html` in workspace (e.g. `/home/user/content-studio/presentation.html`).
2. `publish_artifact` with sandbox path — UI download card handles delivery; no markdown download link in reply.

## Resources

- [reveal.js documentation](https://revealjs.com/)
- Theme pattern libraries: `references/ascentium-deck.md`, `references/inspire-deck.md`
