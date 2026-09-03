# Inspire PPTX Deck Reference

**Theme scope only** — Inspire colours, typography, brand chrome, and slide patterns for pptxgenjs.

Sandbox path: `/home/user/content-studio/skills/pptx/references/inspire-deck.md`

**Not in this file:** pptxgenjs API syntax → read **`pptxgenjs.md`** first.

**Not Ascentium** — no Poppins, Noto Sans SC, orange palette, or Ascentium PNGs.

===================================================================
## PART 1 — BRAND SYSTEM
===================================================================

### 1. Deliverable rules

- Script shell per **`pptxgenjs.md` § Script shell**.
- **Layout:** `LAYOUT_16x9`.
- Assets: `pptx/assets/inspire/`.

### 2. Palette (`INSPIRE`)

```javascript
const INSPIRE = {
  starryBlues: '0A2342',
  creativeBlue: '34B3E4',
  techGray: 'F0F2F5',
  white: 'FFFFFF',
  text: '333333',
  textMuted: '999999',
  darkBg: '0A1E3C',
  amethys: '6964AD',
  myrtleGreen: '005043',
  ceruleanFrost: '73AFC2',
  sakuraPink: 'F5B0BD',
  chartColors: ['34B3E4', '6964AD', '005043', '73AFC2', 'F5B0BD'],
  fontHeadline: 'MiSans',
  fontBody: 'MiSans',
  fontChapter: 'Georgia',
  fontCjk: 'Microsoft YaHei', // tables / Chinese when fontFace required; omit in cells if possible
};

const PAD = { x: 0.5, y: 0.375 };
const ASSETS = '/home/user/content-studio/skills/pptx/assets/inspire';
const FOOTER_TEXT = '© 2026 Inspire | Confidential';
```

Creative Blue ≈ **5–10%** of slide area — subtitles, footer, CTAs only.

### 3. Typography

| Role | Font | pt | Colour |
|------|------|-----|--------|
| Cover / chapter title | Georgia | 40–44 | white on dark |
| Subtitle (dark slides) | MiSans | 18–22 | `34B3E4` |
| Slide title | MiSans | 38 | `0A2342` |
| Kicker | MiSans | 12 uppercase | `34B3E4` |
| Body | MiSans | 14–16 | `333333` |
| Footer | MiSans | 10–11 | `34B3E4` |

Viewer fallback (not automatic in pptxgenjs): MiSans → PingFang SC → Microsoft YaHei → Arial.

**CJK / tables (critical):**

- **MiSans** supports Chinese when installed, but many viewers **do not** have it — same **□ in table cells** as Poppins when `fontFace: INSPIRE.fontBody` is set on `addTable`.
- **Georgia** (`fontChapter`) is **Latin-only** — never use in table cells with Chinese.
- **Tables:** omit `fontFace` in every cell (safest) or use `fontCjk` below on all cells. Do **not** copy `fontHeadline` / `fontBody` / `fontChapter` into table options.

```javascript
const INSPIRE_TABLE_FONT = 'Microsoft YaHei'; // widely available CJK; or omit fontFace entirely
const TABLE_OPTS = { fontSize: 14, color: INSPIRE.text, margin: 0 }; // no fontFace — preferred
```

### 4. Brand assets & chrome rules

| File | Use | Placement (inches; native PNG ratio) |
|------|-----|--------------------------------------|
| `inspire_logo_white.png` | Cover / dark separator | Top-left `x:PAD.x, y:0.35, w:1.45, h:0.451` (466×145) |
| `inspire_right_bottom_cover.png` | Cover / dark separator | Bottom-right bleed `x:7.05, y:2.52, w:2.95, h:3.11` (629×662) |

**Aspect ratio rule:** Inspire logo is **not** the same ratio as Ascentium — never copy `w/h` from another theme. Corner is ~square (629×662), not wide landscape.

**Chrome rule:** dark cover/chapter → both PNGs + footer. Light content slides → **footer text only** (no corner PNG).

### 5. Brand helpers

```javascript
const path = require('path');

function asset(file) {
  return path.join(ASSETS, file);
}

function addDarkCoverChrome(slide) {
  const logoW = 1.45;
  const cornerW = 2.95;
  slide.addImage({ path: asset('inspire_logo_white.png'), x: PAD.x, y: 0.35, w: logoW, h: logoW * (145 / 466) });
  slide.addImage({
    path: asset('inspire_right_bottom_cover.png'),
    x: 10 - cornerW + 0.05,
    y: 5.625 - cornerW * (662 / 629) + 0.12,
    w: cornerW,
    h: cornerW * (662 / 629),
  });
}

function addInspireFooter(slide) {
  slide.addShape('line', {
    x: PAD.x, y: 5.05, w: 2.0, h: 0,
    line: { color: INSPIRE.creativeBlue, width: 0.75, transparency: 65 },
  });
  slide.addText(FOOTER_TEXT, {
    x: PAD.x, y: 5.15, w: 4, h: 0.25,
    fontFace: INSPIRE.fontBody, fontSize: 10, color: INSPIRE.creativeBlue, margin: 0,
  });
}

function addKicker(slide, text, y = PAD.y) {
  slide.addText(text.toUpperCase(), {
    x: PAD.x, y, w: 8.8, h: 0.22,
    fontFace: INSPIRE.fontHeadline, fontSize: 12, bold: true,
    color: INSPIRE.creativeBlue, charSpacing: 2, margin: 0,
  });
}

function addSlideTitle(slide, text, y) {
  slide.addText(text, {
    x: PAD.x, y, w: 8.8, h: 0.65,
    fontFace: INSPIRE.fontHeadline, fontSize: 38, bold: true,
    color: INSPIRE.starryBlues, margin: 0,
  });
}
```

### 6. Design constraints

- **Avoid:** Ascentium orange, Poppins, full-width colour bars, pure black (`000000`) body text.

===================================================================
## PART 2 — SLIDE PATTERNS
===================================================================

---

### `cover-dark`

Background `starryBlues`. Georgia white title + MiSans `creativeBlue` subtitle. `addDarkCoverChrome` + `addInspireFooter`.

Reuse for chapter dividers. Alt dark `0A1E3C` only when user requests.

---

### `light-content`

White or `techGray` background. Optional Georgia chapter heading. Bullets per **`pptxgenjs.md` § Lists**. **Footer on every light slide.**

---

### `section-bullets`

Kicker + MiSans slide title + bullets + footer.

---

### `metric-highlight`

`techGray` background. Centred 52pt `creativeBlue` number + muted caption. Footer.

---

### `aux-cards`

Four `'roundRect'` cards using auxiliary palette tints (`amethys`, `myrtleGreen`, `ceruleanFrost`, sakura). Shapes per **`pptxgenjs.md` § Shapes**.

---

### `data-table`

Dark header (`starryBlues` fill, white text). Syntax → **`pptxgenjs.md` § Tables**.

**CJK:** use `TABLE_OPTS` (no `fontFace`) or `fontFace: INSPIRE.fontCjk` on every cell — never MiSans or Georgia in table cells.

```javascript
slide.addTable([
  [
    { text: '维度', options: { bold: true, color: INSPIRE.white, fill: { color: INSPIRE.starryBlues } } },
    { text: '说明', options: { bold: true, color: INSPIRE.white, fill: { color: INSPIRE.starryBlues } } },
  ],
  [
    { text: '示例行', options: TABLE_OPTS },
    { text: '单元格内容', options: TABLE_OPTS },
  ],
], { x: PAD.x, y: 1.35, w: 8.8, colW: [3, 5.8], ...TABLE_OPTS });
addInspireFooter(slide);
```

---

### `contact-close`

`starryBlues` + cover chrome. Georgia title, blue subtitle, contact name/email. Footer.

---

### Pattern index

| ID | Chrome | Notes |
|----|--------|-------|
| `cover-dark` | Logo + corner + footer | Chapter separator |
| `light-content` | Footer only | White or tech gray |
| `section-bullets` | Footer | Standard content |
| `metric-highlight` | Footer | Big number |
| `aux-cards` | Footer | 4-column cards |
| `data-table` | Footer | Dark header table |
| `contact-close` | Full dark chrome | Closing slide |

Charts: `INSPIRE.chartColors` — **`pptxgenjs.md` § Charts**.
