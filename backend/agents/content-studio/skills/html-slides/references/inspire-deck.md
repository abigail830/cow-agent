# Inspire HTML Deck Reference

Pattern library for **Inspire**-branded reveal.js presentations (1280×720).
**Read this file** from the sandbox before building: `/home/user/content-studio/skills/html-slides/references/inspire-deck.md`
Copy Part 1 into every deliverable; pick slide patterns from Part 2 — do not invent new class names.

**Not Ascentium** — do not use Poppins, Noto Sans SC, orange palette, or Ascentium corner/logo assets.

===================================================================
## PART 1 — CORE BUILD SYSTEM
===================================================================

### 1. Self-contained deliverable

- One `.html` file; **all CSS in `<style>`**, reveal.js from CDN only.
- No `<link href="themes/…">` — published attachments have no sibling files.
- **Brand PNGs** must be embedded as `data:image/png;base64,…` in `<img src>` before `publish_artifact` (see §5).
- Fonts: **MiSans** (CDN) + **Georgia** serif for cover/chapter titles (system stack).

### 2. reveal.js shell (copy verbatim, then fill slides)

```html
<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Presentation Title</title>
  <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/reveal.js@4/dist/reveal.css">
  <link href="https://cdn.jsdelivr.net/npm/misans@4.1.0/lib/Normal/MiSans-Regular.min.css" rel="stylesheet">
  <link href="https://cdn.jsdelivr.net/npm/misans@4.1.0/lib/Normal/MiSans-Medium.min.css" rel="stylesheet">
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
      slideNumber: true,
      transition: 'slide',
      center: false,
    });
  </script>
</body>
</html>
```

**Slide rule:** one `<section>` = one slide. Backgrounds and layout classes go on `<section>`, not nested wrapper cards.

### 3. Brand tokens (always declare at `:root`)

```css
:root {
  --starry:  #0A2342;   /* Starry Blues — cover / dark slides */
  --creative:#34B3E4;   /* Creative Blue — accent only (~5–10% area) */
  --tech:    #F0F2F5;   /* Tech Gray — light alt background */
  --dark-bg: #0A1E3C;   /* Dark slide layer (closing, optional) */
  --text:    #333333;   /* Body — not pure black */
  --muted:   #999999;   /* Slide numbers, labels */
  --white:   #FFFFFF;
  --amethys: #6964AD;
  --myrtle:  #005043;
  --cerulean:#73AFC2;
  --sakura:  #F5B0BD;
  --slide-px: 64px;
  --slide-py: 48px;
}
```

### 4. Base reveal overrides (include in every deck)

```css
.reveal-viewport { background: var(--tech); }
.reveal {
  font-family: 'MiSans', 'PingFang SC', 'Microsoft YaHei', Arial, sans-serif;
  font-size: 20px; font-weight: 400; color: var(--text);
}
/* reveal.js stacks slides with position:absolute — never override to relative */
.reveal .slides section {
  position: absolute; box-sizing: border-box;
  width: 100%; height: 100%;
  padding: var(--slide-py) var(--slide-px);
  padding-bottom: calc(var(--slide-py) + 1.5em);
  overflow: hidden; text-align: left;
}
.reveal .slides section img.inspire-logo,
.reveal .slides section img.inspire-corner-cover {
  margin: 0; border: none; box-shadow: none; background: transparent;
  object-fit: contain; /* never stretch — set width OR height, not both fixed */
}
.reveal h1, .reveal h2 { font-weight: 600; color: var(--starry); text-transform: none; }
.reveal h3, .reveal h4 { font-weight: 500; color: var(--starry); }
.reveal a { color: var(--creative); }
.reveal .progress span { background: var(--creative); }
.reveal .controls button { color: var(--creative); }

.inspire-serif-title {
  font-family: Georgia, 'Times New Roman', serif;
  font-weight: 400; letter-spacing: 0.02em;
}
.inspire-subtitle {
  font-family: 'MiSans', 'PingFang SC', 'Microsoft YaHei', Arial, sans-serif;
  color: var(--creative); font-weight: 500; font-size: 1.1em;
}
.inspire-footer {
  position: absolute; bottom: 36px; left: var(--slide-px);
  font-size: 11px; color: var(--creative);
  border-top: 1px solid rgba(52, 179, 228, 0.35);
  padding-top: 8px; min-width: 200px; z-index: 2;
}
.kicker {
  font-size: 12px; font-weight: 500; letter-spacing: .14em;
  text-transform: uppercase; color: var(--creative); margin-bottom: 12px;
}
.slide-title { font-size: 38px; font-weight: 600; color: var(--starry); line-height: 1.15; }
```

Creative Blue is **emphasis only** — subtitles, footer, progress, CTAs; never flood large areas.

### 5. Brand image assets (sandbox → embed before publish)

Preinstalled in Content Studio at:

`/home/user/content-studio/skills/html-slides/assets/inspire/`

| File | Slide | Placement |
|------|-------|-----------|
| `inspire_logo_white.png` | **Cover / dark separator** | Top-left — **466×145** native ratio (`aspect-ratio: 466/145`), ~180px wide |
| `inspire_right_bottom_cover.png` | **Cover / dark separator** | Bottom-right bleed — **629×662** native ratio (`aspect-ratio: 629/662`) |

**Embed workflow** — use a small Node build script (same pattern as Ascentium §5) with placeholders `__INSPIRE_LOGO__` / `__INSPIRE_CORNER__`. Inspire PNGs are small enough for one-liners if preferred:

```bash
node -e "const fs=require('fs');const p=process.argv[1];process.stdout.write('data:image/png;base64,'+fs.readFileSync(p).toString('base64'))" \
  /home/user/content-studio/skills/html-slides/assets/inspire/inspire_logo_white.png
```

**Chrome rule:** cover and chapter separators use `s-cover-dark` + both PNGs. Light content slides use `inspire-footer` only (no corner PNG yet).

===================================================================
## PART 2 — SLIDE PATTERN LIBRARY
===================================================================

---

### Cover / dark separator (title slide)

Starry Blues (`--starry`) full-bleed dark slide matching brand deck cover: **white serif title**, **Creative Blue MiSans subtitle**, **logo top-left**, **corner graphic bottom-right**, **footer bottom-left**.

```css
.reveal .slides section.s-cover-dark {
  background: var(--starry);
  padding: 0;
  color: var(--white);
}
.reveal .slides section.s-cover-dark .inspire-logo {
  position: absolute;
  top: 44px;
  left: var(--slide-px);
  width: 180px;
  height: auto;
  aspect-ratio: 466 / 145;
  object-fit: contain;
  object-position: left top;
  pointer-events: none;
  z-index: 2;
}
.reveal .slides section.s-cover-dark .inspire-corner-cover {
  position: absolute;
  right: -8px;
  bottom: -12px;
  width: min(36vw, 320px);
  height: auto;
  aspect-ratio: 629 / 662;
  object-fit: contain;
  object-position: right bottom;
  pointer-events: none;
  z-index: 0;
}
.reveal .slides section.s-cover-dark .cover-body {
  position: relative;
  z-index: 1;
  padding: 148px var(--slide-px) 96px;
  max-width: 760px;
}
.reveal .slides section.s-cover-dark .inspire-serif-title {
  font-size: 2.85em;
  color: var(--white);
  line-height: 1.12;
  margin-bottom: 14px;
}
.reveal .slides section.s-cover-dark .inspire-subtitle {
  font-size: 1.15em;
  color: var(--creative);
  font-weight: 500;
}
.reveal .slides section.s-cover-dark .inspire-footer {
  bottom: 32px;
  color: var(--creative);
}
```

```html
<section class="s-cover-dark">
  <img class="inspire-logo" src="data:image/png;base64,…" alt="Inspire AI">
  <img class="inspire-corner-cover" src="data:image/png;base64,…" alt="">
  <div class="cover-body">
    <h1 class="inspire-serif-title">Slide Separater</h1>
    <p class="inspire-subtitle">Click to add subtitle</p>
  </div>
  <div class="inspire-footer">© 2026 Inspire | Confidential</div>
</section>
```

Use the same pattern for **chapter dividers** (swap title/subtitle text). Optional alt background `var(--dark-bg)` only when user explicitly requests — default cover is `--starry`.

---

### Light content

White or tech-gray background; optional **Georgia** serif on first `h1` (chapter opener). Footer on every light slide.

```css
.reveal .slides section.s-light { background: var(--white); }
.reveal .slides section.s-light > h1:first-child.inspire-serif-title {
  font-size: 2em; margin-bottom: 24px; color: var(--starry);
}
.reveal .slides section.s-tech { background: var(--tech); }
.reveal .slides section.s-light ul,
.reveal .slides section.s-tech ul {
  margin-top: 20px; display: flex; flex-direction: column; gap: 12px;
}
.reveal .slides section.s-light li::marker,
.reveal .slides section.s-tech li::marker { color: var(--creative); }
```

```html
<section class="s-light">
  <h1 class="inspire-serif-title">Contents</h1>
  <ul>
    <li>关于 Inspire</li>
    <li>产品能力</li>
    <li>客户案例</li>
  </ul>
  <div class="inspire-footer">© 2026 Inspire | Confidential</div>
</section>
```

---

### Section + bullets

Standard content slide with kicker and MiSans title.

```html
<section class="s-light">
  <div class="kicker">章节</div>
  <h2 class="slide-title">核心能力</h2>
  <ul>
    <li>多模态理解与生成</li>
    <li>企业级知识库接入</li>
    <li>可审计的 Agent 工作流</li>
  </ul>
  <div class="inspire-footer">© 2026 Inspire | Confidential</div>
</section>
```

---

### Metric highlight

Large Creative Blue number on light background.

```css
.reveal .slides section.s-metric { background: var(--tech); text-align: center;
  display: flex; flex-direction: column; justify-content: center; align-items: center;
}
.reveal .slides section.s-metric .metric {
  font-size: 3.2em; font-weight: 600; color: var(--creative); line-height: 1;
}
.reveal .slides section.s-metric .metric-label {
  font-size: 1.1em; color: var(--muted); margin-top: 12px; max-width: 560px;
}
```

```html
<section class="s-metric">
  <p class="metric">90%</p>
  <p class="metric-label">客户报告人工任务时间减少</p>
  <div class="inspire-footer">© 2026 Inspire | Confidential</div>
</section>
```

---

### Contact / closing (dark)

Name, role, email on dark slide — reuse cover assets when a branded closing is needed.

```css
.reveal .slides section.s-contact { background: var(--starry); color: var(--white);
  display: flex; flex-direction: column; justify-content: center; padding: 80px var(--slide-px);
}
.reveal .slides section.s-contact .contact-name {
  font-size: 1.4em; font-weight: 600; margin-top: 24px;
}
.reveal .slides section.s-contact .contact-email { color: var(--creative); font-size: 1em; }
```

```html
<section class="s-contact s-cover-dark">
  <img class="inspire-logo" src="data:image/png;base64,…" alt="Inspire AI">
  <img class="inspire-corner-cover" src="data:image/png;base64,…" alt="">
  <div class="cover-body">
    <h1 class="inspire-serif-title">期待与您合作</h1>
    <p class="inspire-subtitle">We look forward to working with you</p>
    <p class="contact-name">张三</p>
    <p>业务发展经理</p>
    <p class="contact-email">zhangsan@inspiregroup.com</p>
  </div>
  <div class="inspire-footer">© 2026 Inspire | Confidential</div>
</section>
```

---

### Auxiliary-color cards (charts / differentiation)

Four-column cards using Inspire auxiliary palette — charts, feature differentiation.

```css
.reveal .slides section.s-cards { background: var(--white); }
.reveal .slides section.s-cards .cards {
  display: grid; grid-template-columns: repeat(4, 1fr); gap: 16px; margin-top: 28px;
}
.reveal .slides section.s-cards .card {
  border-radius: 14px; padding: 22px 16px; text-align: center;
}
.reveal .slides section.s-cards .card h3 { font-size: 1em; margin-bottom: 8px; }
.reveal .slides section.s-cards .card p { font-size: 12px; color: var(--muted); line-height: 1.45; }
.reveal .slides section.s-cards .c-amethys { background: rgba(105,100,173,.12); }
.reveal .slides section.s-cards .c-amethys h3 { color: var(--amethys); }
.reveal .slides section.s-cards .c-myrtle  { background: rgba(0,80,67,.1); }
.reveal .slides section.s-cards .c-myrtle h3  { color: var(--myrtle); }
.reveal .slides section.s-cards .c-cerulean { background: rgba(115,175,194,.15); }
.reveal .slides section.s-cards .c-cerulean h3 { color: var(--cerulean); }
.reveal .slides section.s-cards .c-sakura   { background: rgba(245,176,189,.2); }
.reveal .slides section.s-cards .c-sakura h3   { color: #c45d6e; }
```

```html
<section class="s-cards">
  <div class="kicker">差异化</div>
  <h2 class="slide-title">四大能力维度</h2>
  <div class="cards">
    <div class="card c-amethys"><h3>智能</h3><p>语义理解与推理</p></div>
    <div class="card c-myrtle"><h3>合规</h3><p>审计与权限</p></div>
    <div class="card c-cerulean"><h3>集成</h3><p>API 与 MCP</p></div>
    <div class="card c-sakura"><h3>体验</h3><p>对话式交互</p></div>
  </div>
  <div class="inspire-footer">© 2026 Inspire | Confidential</div>
</section>
```
