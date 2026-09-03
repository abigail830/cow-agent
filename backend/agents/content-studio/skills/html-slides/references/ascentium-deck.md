# Ascentium HTML Deck Reference

Pattern library for **Ascentium**-branded reveal.js presentations (1280×720).
**Read this file** from the sandbox before building: `/home/user/content-studio/skills/html-slides/references/ascentium-deck.md`
Copy Part 1 into every deliverable; pick slide patterns from Part 2 — do not invent new class names.

Source: *Brand Guidelines Full Version R1.10 (Nov 2025)*.

===================================================================
## PART 1 — CORE BUILD SYSTEM
===================================================================

### 1. Self-contained deliverable

- One `.html` file; **all CSS in `<style>`**, reveal.js from CDN only.
- No `<link href="themes/…">` — published attachments have no sibling files.
- **Brand PNGs** must be embedded as `data:image/png;base64,…` in `<img src>` before `publish_artifact` (see §5).
- Fonts: Poppins + Noto Sans SC (Google Fonts CDN).

### 2. reveal.js shell (copy verbatim, then fill slides)

```html
<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Presentation Title</title>
  <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/reveal.js@4/dist/reveal.css">
  <link href="https://fonts.googleapis.com/css2?family=Noto+Sans+SC:wght@400;500;600&family=Poppins:wght@400;500;600&display=swap" rel="stylesheet">
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

Use variables — **never hardcode hex in pattern CSS** except inside `:root`.

```css
:root {
  --org:   #FF6611;   /* Vibrant Orange — primary accent, CTA */
  --org2:  #FF8541;   /* Orange 4 — gradients, emphasis */
  --org3:  #FFA370;   /* Orange 3 */
  --opal:  #FFF0E7;   /* Orange 1 — soft slide backgrounds */
  --ol:    #FFD1B8;   /* Orange 2 — borders, secondary */
  --gd:    #0F1514;   /* Midnight Green — dark slides, headings */
  --gm:    #272C2C;   /* MG 4 */
  --g3:    #575B5B;   /* MG 3 — body secondary */
  --g4:    #878A8A;   /* MG 2 — captions */
  --g5:    #B7B9B9;   /* MG 1 — dim text */
  --teal:  #077069;
  --blue:  #1877F2;
  --err:   #DC3545;
  --white: #FFFFFF;
  --slide-px: 64px;
  --slide-py: 48px;
}
```

### 4. Base reveal overrides (include in every deck)

```css
.reveal-viewport { background: var(--g5); }
.reveal {
  font-family: 'Poppins', 'Noto Sans SC', Arial, Helvetica, sans-serif;
  font-size: 20px;
  font-weight: 400;
  color: var(--gd);
}
/* reveal.js stacks slides with position:absolute — never override to relative */
.reveal .slides section {
  position: absolute;
  box-sizing: border-box;
  width: 100%;
  height: 100%;
  padding: var(--slide-py) var(--slide-px);
  overflow: hidden;
  text-align: left;
  background: var(--white);
}
.reveal .slides section img.brand-corner-cover,
.reveal .slides section img.brand-corner-content,
.reveal .slides section img.brand-logo {
  margin: 0; border: none; box-shadow: none; background: transparent;
  object-fit: contain; /* never stretch brand PNGs */
}
.reveal h1, .reveal h2, .reveal h3 {
  font-weight: 600;
  color: var(--gd);
  text-transform: none;
  letter-spacing: -0.01em;
}
.reveal h1 { font-size: 2.4em; line-height: 1.15; }
.reveal h2 { font-size: 1.55em; line-height: 1.23; }
.reveal p, .reveal li { font-size: 1em; line-height: 1.45; }
.reveal a { color: var(--org); text-decoration: none; }
.reveal .progress span { background: var(--org); }
.reveal .controls button { color: var(--org); }

/* Shared typography components */
.kicker {
  font-size: 12px; font-weight: 600; letter-spacing: .16em;
  text-transform: uppercase; color: var(--org); margin-bottom: 12px;
}
.slide-title { font-size: 38px; font-weight: 600; color: var(--gd); line-height: 1.15; margin-bottom: 8px; }
.slide-sub { font-size: 15px; color: var(--g3); line-height: 1.55; }
.accent { color: var(--org); }
.emphasis { font-weight: 500; }

/* === Brand chrome (cover + content slides) — include when using §5 assets === */
/* Content corner bottom ≈ slide-title baseline (kicker + title block). Logo ~⅔ prior width. */
.reveal .slides section.s-branded { padding-bottom: calc(var(--slide-py) + 56px); }
.reveal .slides section.s-branded .brand-corner-content {
  position: absolute; top: 0; right: 0;
  width: 120px; height: auto;
  aspect-ratio: 1 / 1; /* asc_content_right-top-corner.png is 458×458 */
  object-fit: contain; object-position: top right;
  pointer-events: none; z-index: 0;
}
.reveal .slides section.s-branded .brand-logo {
  position: absolute; left: var(--slide-px); bottom: 28px;
  width: 93px; height: auto;
  aspect-ratio: 512 / 78; /* asc_logo_black.png */
  object-fit: contain;
  pointer-events: none; z-index: 2;
}
.reveal .slides section.s-branded > :not(.brand-corner-content):not(.brand-logo) {
  position: relative; z-index: 1;
}
```

Typography scale: **kicker** 12px uppercase orange · **slide-title** 38px · **cover h1** 56–64px · **key stat** 48–56px · body ≤4 bullets per slide · footnotes 11–12px `var(--g4)`.

### 5. Brand image assets (sandbox → embed before publish)

Preinstalled in Content Studio at:

`/home/user/content-studio/skills/html-slides/assets/ascentium/`

| File | Slide | Placement |
|------|-------|-----------|
| `asc_cover_right_top_corner.png` | **Cover** | Top-right, **inset** (~48px top, 64px right) — large corner mark (~250 KB, pre-optimized) |
| `asc_content_right-top-corner.png` | **Content** | Top-right **flush** — **120×120px** max (square); bottom aligns with slide-title row |
| `asc_logo_black.png` | White / light slides | Bottom-left logo — **~93px** wide (⅔ prior), `aspect-ratio: 512/78` |
| `asc_logo_white.png` | Orange or midnight-green cover | Bottom-left logo |

**Do not** pipe large PNGs through `node -e` into the terminal — stdout truncates and base64 will be incomplete. Use a **build script** instead:

```javascript
// build-deck.js — run: cd /home/user/content-studio && node build-deck.js
const fs = require('fs');
const path = require('path');

const ASSETS = '/home/user/content-studio/skills/html-slides/assets/ascentium';
const toDataUri = (file) =>
  'data:image/png;base64,' + fs.readFileSync(path.join(ASSETS, file)).toString('base64');

let html = fs.readFileSync('deck.template.html', 'utf8');
html = html
  .replaceAll('__COVER_CORNER__', toDataUri('asc_cover_right_top_corner.png'))
  .replaceAll('__CONTENT_CORNER__', toDataUri('asc_content_right-top-corner.png'))
  .replaceAll('__LOGO_BLACK__', toDataUri('asc_logo_black.png'))
  .replaceAll('__LOGO_WHITE__', toDataUri('asc_logo_white.png'));

fs.writeFileSync('presentation.html', html);
console.log('Wrote presentation.html', fs.statSync('presentation.html').size, 'bytes');
```

In `deck.template.html`, use placeholders in `<img src="__COVER_CORNER__">` etc. Logos/small corners can use the one-liner below; cover corner **must** use the script.

**One-liner** (logos / small corners only):

```bash
node -e "const fs=require('fs');const p=process.argv[1];process.stdout.write('data:image/png;base64,'+fs.readFileSync(p).toString('base64'))" \
  /home/user/content-studio/skills/html-slides/assets/ascentium/asc_logo_black.png
```

Paste each data URI into the matching `<img src="…">`. Use **black** logo on white/light backgrounds; **white** logo on `bg-org` / `bg-gd` covers.

**Chrome rule:** every **content** slide uses `s-branded` + content corner + black logo. **Cover** uses `s-cover` + cover corner + logo (black or white per background).

===================================================================
## PART 2 — SLIDE PATTERN LIBRARY
===================================================================

Include CSS only for patterns you use. Markup goes inside `<section>`.

---

### Cover (title slide)

White (default), theme orange (`bg-org`), or midnight green (`bg-gd`). Large inset corner mark top-right; logo bottom-left; title block left-aligned.

```css
.reveal .slides section.s-cover {
  background: var(--white);
  padding: 0;
  display: flex;
  align-items: center;
}
.reveal .slides section.s-cover.bg-org { background: var(--org); }
.reveal .slides section.s-cover.bg-gd { background: var(--gd); }
.reveal .slides section.s-cover .brand-corner-cover {
  position: absolute;
  top: 48px;
  right: 64px;
  height: min(52vh, 380px);
  width: auto;
  pointer-events: none;
  z-index: 0;
}
.reveal .slides section.s-cover .brand-logo {
  position: absolute;
  left: var(--slide-px);
  bottom: 40px;
  width: 168px;
  height: auto;
  pointer-events: none;
  z-index: 2;
}
.reveal .slides section.s-cover .cover-body {
  position: relative;
  z-index: 1;
  padding: 72px var(--slide-px) 120px;
  max-width: 760px;
}
.reveal .slides section.s-cover h1 {
  font-size: 2.75em;
  font-weight: 600;
  color: var(--gd);
  line-height: 1.1;
  margin-bottom: 20px;
}
.reveal .slides section.s-cover.bg-org h1,
.reveal .slides section.s-cover.bg-gd h1 { color: var(--white); }
.reveal .slides section.s-cover .sub {
  font-size: 1.05em;
  color: var(--g3);
  line-height: 1.55;
  max-width: 640px;
}
.reveal .slides section.s-cover.bg-org .sub,
.reveal .slides section.s-cover.bg-gd .sub { color: rgba(255, 255, 255, 0.82); }
```

**White cover** (default — black logo):

```html
<section class="s-cover">
  <img class="brand-corner-cover" src="data:image/png;base64,…" alt="">
  <img class="brand-logo" src="data:image/png;base64,…" alt="Ascentium">
  <div class="cover-body">
    <h1>Singapore Full Compliance Suite</h1>
    <p class="sub">Proposal for Walkghost Limited | Sara, CEO | sara@abc.com</p>
  </div>
</section>
```

**Orange cover** (`bg-org` — white logo):

```html
<section class="s-cover bg-org">
  <img class="brand-corner-cover" src="data:image/png;base64,…" alt="">
  <img class="brand-logo" src="data:image/png;base64,…" alt="Ascentium">
  <div class="cover-body">
    <h1>Deck title</h1>
    <p class="sub">Subtitle or client line.</p>
  </div>
</section>
```

**Midnight green cover** (`bg-gd` — white logo): same as orange cover but `class="s-cover bg-gd"`.

---

### Section + bullets (light content)

Default content slide with **brand chrome**: flush small corner top-right, black logo bottom-left. Add `s-branded` to any white content pattern (`s-section`, `s-split`, `s-stats`, `s-table`, …).

```css
.reveal .slides section.s-section { background: var(--white); }
.reveal .slides section.s-section ul {
  margin-top: 20px; display: flex; flex-direction: column; gap: 14px;
}
.reveal .slides section.s-section li {
  font-size: 1.05em; color: var(--gm); padding-left: 1.2em; position: relative;
}
.reveal .slides section.s-section li::before {
  content: ''; position: absolute; left: 0; top: 0.55em;
  width: 6px; height: 6px; border-radius: 50%; background: var(--org);
}
```

```html
<section class="s-section s-branded">
  <img class="brand-corner-content" src="data:image/png;base64,…" alt="">
  <img class="brand-logo" src="data:image/png;base64,…" alt="Ascentium">
  <div class="kicker">章节</div>
  <h2 class="slide-title">为什么需要提前规划</h2>
  <ul>
    <li>越南对税后利润汇回有明确合规要求，不能随时划转。</li>
    <li>须先完成纳税义务并取得税务机关许可，方可启动购汇。</li>
    <li>投资路径（香港/新加坡/直接投资）直接影响每次汇回的税务成本。</li>
  </ul>
</section>
```

---

### Soft background content

Orange-tint light background for emphasis or closing.

```css
.reveal .slides section.s-soft {
  background: var(--opal);
  display: flex; flex-direction: column; justify-content: center; align-items: center;
  text-align: center;
}
.reveal .slides section.s-soft h2 { color: var(--gd); }
.reveal .slides section.s-soft .cta {
  display: inline-block; margin-top: 24px;
  background: var(--org); color: var(--white);
  font-weight: 500; padding: 0.5em 1.4em; border-radius: 4px;
}
```

```html
<section class="s-soft">
  <h2>有问题？</h2>
  <p class="slide-sub">欢迎联系合规团队进一步讨论。</p>
  <a class="cta" href="mailto:team@ascentium.com">联系我们</a>
</section>
```

---

### Two-column comparison

Side-by-side good/bad or before/after cards.

```css
.reveal .slides section.s-split { background: var(--white); }
.reveal .slides section.s-split .split {
  display: grid; grid-template-columns: 1fr auto 1fr; gap: 24px;
  margin-top: 28px; align-items: stretch;
}
.reveal .slides section.s-split .card {
  border-radius: 16px; padding: 28px 24px; text-align: center;
}
.reveal .slides section.s-split .card.bad  { background: #FFF5F5; border: 2px solid #FECACA; }
.reveal .slides section.s-split .card.good { background: #F0FDF4; border: 2px solid #BBF7D0; }
.reveal .slides section.s-split .card .big { font-size: 2.8em; font-weight: 600; line-height: 1; }
.reveal .slides section.s-split .card.bad  .big { color: var(--err); }
.reveal .slides section.s-split .card.good .big { color: var(--teal); }
.reveal .slides section.s-split .card .lbl {
  font-size: 11px; font-weight: 600; letter-spacing: .1em;
  text-transform: uppercase; margin-bottom: 8px;
}
.reveal .slides section.s-split .vs { font-size: 1.2em; font-weight: 600; color: var(--g5); align-self: center; }
```

```html
<section class="s-split">
  <div class="kicker">对比</div>
  <h2 class="slide-title">合规规划的价值</h2>
  <div class="split">
    <div class="card bad"><div class="lbl">未规划</div><div class="big">4–6 周</div><p class="slide-sub">补材料、反复沟通</p></div>
    <div class="vs">vs</div>
    <div class="card good"><div class="lbl">提前规划</div><div class="big">1–2 周</div><p class="slide-sub">材料齐备、一次通过</p></div>
  </div>
</section>
```

---

### Stat row (3 KPIs)

Three metrics in a row — totals, percentages, counts.

```css
.reveal .slides section.s-stats { background: var(--white); }
.reveal .slides section.s-stats .stats {
  display: grid; grid-template-columns: repeat(3, 1fr); gap: 20px; margin-top: 32px;
}
.reveal .slides section.s-stats .stat {
  background: var(--opal); border-radius: 14px; padding: 24px 20px; text-align: center;
}
.reveal .slides section.s-stats .stat.dark {
  background: var(--gd); color: var(--white);
}
.reveal .slides section.s-stats .stat .num {
  font-size: 2.6em; font-weight: 600; color: var(--org); line-height: 1;
}
.reveal .slides section.s-stats .stat.dark .num { color: var(--org3); }
.reveal .slides section.s-stats .stat .lbl { font-size: 13px; color: var(--g3); margin-top: 8px; }
.reveal .slides section.s-stats .stat.dark .lbl { color: var(--g4); }
```

```html
<section class="s-stats">
  <div class="kicker">关键数据</div>
  <h2 class="slide-title">利润汇回概览</h2>
  <div class="stats">
    <div class="stat dark"><div class="num">$2.4M</div><div class="lbl">可汇回利润</div></div>
    <div class="stat"><div class="num">15%</div><div class="lbl">预提所得税</div></div>
    <div class="stat"><div class="num">3</div><div class="lbl">合规里程碑</div></div>
  </div>
</section>
```

---

### Agenda

Numbered or bulleted agenda with fragments optional.

```html
<section class="s-section">
  <div class="kicker">议程</div>
  <h2 class="slide-title">今日内容</h2>
  <ol style="margin-top:24px;font-size:1.1em;line-height:2;color:var(--gm)">
    <li class="fragment">背景与监管框架</li>
    <li class="fragment">四步汇回流程</li>
    <li class="fragment">材料清单与常见误区</li>
    <li class="fragment">时间线与下一步</li>
  </ol>
</section>
```

---

### Data table

Dark header row; compact cells.

```css
.reveal .slides section.s-table { background: var(--white); }
.reveal .slides section.s-table table {
  width: 100%; border-collapse: collapse; margin-top: 24px;
  font-size: 14px; border-radius: 12px; overflow: hidden;
}
.reveal .slides section.s-table th {
  background: var(--gd); color: var(--white);
  padding: 12px 16px; text-align: left; font-weight: 600;
}
.reveal .slides section.s-table td {
  padding: 12px 16px; border-bottom: 1px solid var(--g5); color: var(--gm);
}
.reveal .slides section.s-table tr:last-child td { border-bottom: none; }
```

```html
<section class="s-table">
  <div class="kicker">清单</div>
  <h2 class="slide-title">必备材料</h2>
  <table>
    <thead><tr><th>材料</th><th>负责方</th><th>周期</th></tr></thead>
    <tbody>
      <tr><td>审计报告</td><td>财务部</td><td>T+30</td></tr>
      <tr><td>纳税证明</td><td>税务</td><td>T+45</td></tr>
      <tr><td>董事会决议</td><td>法务</td><td>T+15</td></tr>
    </tbody>
  </table>
</section>
```

---

### CTA / dark closing

Two-column org vs audience actions; end with one concrete next step.

```css
.reveal .slides section.s-cta {
  background: var(--gd); padding: 52px 80px;
  display: flex; flex-direction: column; justify-content: center;
}
.reveal .slides section.s-cta h2 {
  font-size: 2.2em; color: var(--white); line-height: 1.2; max-width: 800px; margin-bottom: 32px;
}
.reveal .slides section.s-cta h2 span { color: var(--org3); }
.reveal .slides section.s-cta .cols { display: grid; grid-template-columns: 1fr 1fr; gap: 20px; }
.reveal .slides section.s-cta .col-org {
  background: rgba(255,255,255,.06); border: 1px solid rgba(255,255,255,.1);
  border-radius: 14px; padding: 24px;
}
.reveal .slides section.s-cta .col-you { background: var(--org); border-radius: 14px; padding: 24px; }
.reveal .slides section.s-cta .col-title {
  font-size: 11px; font-weight: 600; letter-spacing: .12em;
  text-transform: uppercase; margin-bottom: 16px; color: var(--g4);
}
.reveal .slides section.s-cta .col-you .col-title { color: rgba(255,255,255,.85); }
.reveal .slides section.s-cta .col-you p { color: var(--white); font-size: 15px; line-height: 1.5; }
```

```html
<section class="s-cta">
  <h2>下一步：<span>启动合规评估</span></h2>
  <div class="cols">
    <div class="col-org">
      <div class="col-title">组织侧</div>
      <p style="color:var(--white);font-size:15px">统筹审计、税务、法务材料时间表</p>
    </div>
    <div class="col-you">
      <div class="col-title">您的行动</div>
      <p>本周内确认投资路径与董事会决议模板</p>
    </div>
  </div>
</section>
```
