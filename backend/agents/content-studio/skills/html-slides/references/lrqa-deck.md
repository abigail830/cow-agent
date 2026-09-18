# LRQA HTML Deck Reference

Pattern library for **LRQA**-branded reveal.js presentations (1280×720).
**Read this file** from the sandbox before building: `/home/user/content-studio/skills/html-slides/references/lrqa-deck.md`
Copy Part 1 into every deliverable; pick slide patterns from Part 2 — do not invent new class names.

**Not Ascentium / Inspire** — do not use Poppins, MiSans, Georgia motifs, orange, or Starry/Creative Blue tokens.

===================================================================
## PART 1 — CORE BUILD SYSTEM
===================================================================

### 1. Self-contained deliverable

- One `.html` file; **all CSS in `<style>`**, reveal.js + Google Fonts from CDN only.
- No `<link href="themes/…">` — published attachments have no sibling files.
- **Brand PNG** (`lrqa_logo.png`) must be embedded as `data:image/png;base64,…` in `<img src>` before `publish_artifact` (see §5).
- Fonts: **Lato** (Latin) + **Noto Sans SC** (CJK) via Google Fonts — match visual weight of PPT/Word decks (those use Arial/YaHei system fonts).

### 2. reveal.js shell (copy verbatim, then fill slides)

```html
<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Presentation Title</title>
  <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/reveal.js@4/dist/reveal.css">
  <link href="https://fonts.googleapis.com/css2?family=Lato:wght@400;700&family=Noto+Sans+SC:wght@400;500;700&display=swap" rel="stylesheet">
  <style>
    /* === Paste PART 1 §3–4 CSS here === */
    /* === Paste PART 2 pattern CSS for slides you use === */
  </style>
</head>
<body>
  <div class="reveal">
    <div class="slides">
      <!-- one <section> per slide — patterns from PART 2 -->
    </div>
  </div>
  <script src="https://cdn.jsdelivr.net/npm/reveal.js@4/dist/reveal.js"></script>
  <script>
    Reveal.initialize({
      width: 1280,
      height: 720,
      margin: 0.04,
      minScale: 0.2,
      maxScale: 2.0,
      hash: true,
      slideNumber: false,
      transition: 'slide',
      center: false,
    });
  </script>
</body>
</html>
```

**Slide rule:** one `<section>` = one slide. Backgrounds and layout classes go on `<section>`.

### 3. Brand tokens (always declare at `:root`)

```css
:root {
  --navy:    #1A1E33;
  --navy-mid:#33374C;
  --teal:    #00DDB3;
  --mist:    #F5F7F8;
  --text:    #1A1E33;
  --muted:   #6B7280;
  --white:   #FFFFFF;
  --slide-px: 64px;
  --slide-py: 48px;
  --footer-h: 56px;
  --font: 'Lato', 'Noto Sans SC', Arial, Helvetica, sans-serif;
}
```

### Typography vs PPT (keep HTML ≥ these px)

| Role | PPT (pt) | HTML (px) | Class / selector |
|------|----------|-----------|------------------|
| Cover / section title | 36–42 | **44** | `.lrqa-title-teal` on dark |
| Section kicker | 14 | **16** | `.lrqa-kicker` |
| Subtitle (dark) | 16–18 | **20** | `.cover-sub` |
| Content slide title | 28–32 | **36** | `.slide-title` |
| Body | 14–16 | **18** (base) | `.reveal` |
| Footer title / page # | 11–12 | **14** | `.deck-title` / `.page-num` |

Use **absolute `px`** for titles (not only `em`) so reveal.css defaults cannot shrink them.

### 4. Base reveal overrides (include in every deck)

```css
.reveal-viewport { background: var(--mist); }
.reveal {
  font-family: var(--font);
  font-size: 18px; font-weight: 400; color: var(--text);
}
.reveal .slides section {
  position: absolute; box-sizing: border-box;
  width: 100%; height: 100%;
  padding: var(--slide-py) var(--slide-px);
  padding-bottom: calc(var(--footer-h) + 24px);
  overflow: hidden; text-align: left;
}
.reveal .slides section img.lrqa-logo {
  margin: 0; border: none; box-shadow: none; background: transparent;
  object-fit: contain; aspect-ratio: 1 / 1;
}
.reveal h1, .reveal h2, .reveal h3, .reveal h4 {
  font-family: var(--font);
  font-weight: 700; color: var(--text); text-transform: none;
  letter-spacing: -0.01em;
}
.reveal p, .reveal li { font-size: 18px; line-height: 1.45; }
.reveal a { color: var(--teal); }
.reveal .progress span { background: var(--teal); }
.reveal .controls button { color: var(--teal); }

.lrqa-title-teal {
  color: var(--teal); font-weight: 700;
  font-size: 44px; line-height: 1.15;
  margin: 0 0 16px;
}
.lrqa-kicker {
  font-size: 16px; font-weight: 700; letter-spacing: .06em;
  color: var(--white); margin: 0 0 14px;
}
.slide-title {
  font-size: 36px; font-weight: 700; color: var(--text);
  line-height: 1.2; margin: 0 0 20px;
}

/* Content footer bar */
.lrqa-footer-bar {
  position: absolute; left: 0; right: 0; bottom: 0;
  height: var(--footer-h);
  background: var(--navy);
  display: flex; align-items: center;
  padding: 0 20px 0 18px;
  z-index: 3;
  box-sizing: border-box;
}
.lrqa-footer-bar .lrqa-logo { width: 28px; height: 28px; flex-shrink: 0; }
.lrqa-footer-bar .deck-title {
  margin-left: 14px; flex: 1;
  font-size: 14px; color: var(--white); white-space: nowrap;
  overflow: hidden; text-overflow: ellipsis;
}
.lrqa-footer-bar .page-num {
  font-size: 14px; color: var(--white); margin-right: 28px;
}
.lrqa-footer-bar .teal-corner {
  position: absolute; right: 0; bottom: 0;
  width: 0; height: 0;
  border-style: solid;
  border-width: 0 0 28px 28px;
  border-color: transparent transparent var(--teal) transparent;
}
```

### 5. Brand image assets (sandbox → embed before publish)

Preinstalled in Content Studio at:

`/home/user/content-studio/skills/html-slides/assets/lrqa/`

| File | Slide | Placement |
|------|-------|-----------|
| `lrqa_logo.png` | Cover / section / content footer | **124×124** square (`aspect-ratio: 1/1`) |

```bash
node -e "const fs=require('fs');const p=process.argv[1];process.stdout.write('data:image/png;base64,'+fs.readFileSync(p).toString('base64'))" \
  /home/user/content-studio/skills/html-slides/assets/lrqa/lrqa_logo.png
```

Replace `__LRQA_LOGO__` placeholders with the data URI before `publish_artifact`.

**Chrome rule:** dark cover/section use CSS diagonal + teal corner (no extra PNGs). Light content slides use `.lrqa-footer-bar` + logo.

===================================================================
## PART 2 — SLIDE PATTERN LIBRARY
===================================================================

---

### Cover / dark title

```css
.reveal .slides section.s-cover-dark {
  background: var(--navy);
  padding: 0;
  color: var(--white);
}
.reveal .slides section.s-cover-dark::before {
  content: '';
  position: absolute; top: 0; right: 0;
  width: 48%; height: 100%;
  background: var(--navy-mid);
  clip-path: polygon(28% 0, 100% 0, 100% 100%, 0 100%);
  z-index: 0;
}
.reveal .slides section.s-cover-dark::after {
  content: '';
  position: absolute; right: 0; bottom: 0;
  width: 34%; height: 26%;
  background: var(--teal);
  clip-path: polygon(35% 100%, 100% 18%, 100% 100%);
  z-index: 0;
}
.reveal .slides section.s-cover-dark .lrqa-logo {
  position: absolute; top: 40px; left: var(--slide-px);
  width: 56px; height: 56px; z-index: 2;
}
.reveal .slides section.s-cover-dark .cover-body {
  position: relative; z-index: 1;
  padding: 168px var(--slide-px) 96px;
  max-width: 780px;
}
.reveal .slides section.s-cover-dark .lrqa-title-teal {
  font-size: 44px; line-height: 1.15; margin-bottom: 18px;
}
.reveal .slides section.s-cover-dark .cover-sub {
  font-size: 20px; color: var(--white); font-weight: 400; margin: 0 0 28px; line-height: 1.4;
}
.reveal .slides section.s-cover-dark .cover-meta {
  font-size: 16px; color: var(--white); line-height: 1.5; margin: 0;
}
```

```html
<section class="s-cover-dark">
  <img class="lrqa-logo" src="__LRQA_LOGO__" alt="LRQA">
  <div class="cover-body">
    <h1 class="lrqa-title-teal">Title here</h1>
    <p class="cover-sub">Subtitle</p>
    <p class="cover-meta"><strong>Presenter</strong><br>Date</p>
  </div>
</section>
```

---

### Section divider

Same dark chrome as cover; kicker + **teal** title (`.lrqa-title-teal`, 44px) + white subtitle. Do **not** use `.slide-title` on dark slides.

```html
<section class="s-cover-dark">
  <img class="lrqa-logo" src="__LRQA_LOGO__" alt="LRQA">
  <div class="cover-body">
    <p class="lrqa-kicker">Section 01</p>
    <h1 class="lrqa-title-teal">Section divider slide</h1>
    <p class="cover-sub">Subtitle</p>
  </div>
</section>
```

---

### Light content

```css
.reveal .slides section.s-light { background: var(--white); }
.reveal .slides section.s-light ul {
  margin-top: 20px; display: flex; flex-direction: column; gap: 12px;
}
.reveal .slides section.s-light li::marker { color: var(--teal); }
```

```html
<section class="s-light">
  <h2 class="slide-title">Header</h2>
  <p>Text goes here</p>
  <div class="lrqa-footer-bar">
    <img class="lrqa-logo" src="__LRQA_LOGO__" alt="LRQA">
    <span class="deck-title">Title of presentation here</span>
    <span class="page-num">2</span>
    <span class="teal-corner" aria-hidden="true"></span>
  </div>
</section>
```

---

### Data table

```css
.reveal .slides section.s-light table {
  width: 100%; border-collapse: collapse; margin-top: 20px; font-size: 16px;
}
.reveal .slides section.s-light th {
  background: var(--navy); color: var(--white); text-align: left;
  padding: 10px 12px;
}
.reveal .slides section.s-light td {
  padding: 10px 12px; border-bottom: 1px solid #E5E7EB; color: var(--text);
}
```

---

### Pattern index

| Class / pattern | Chrome | Notes |
|-----------------|--------|-------|
| `s-cover-dark` | CSS diagonal + teal corner + logo | Title / section — title **44px teal** |
| `s-light` + `lrqa-footer-bar` | Navy footer | Content — `.slide-title` **36px** |
| Table in `s-light` | Footer bar | Navy header cells |
