# Ascentium PPTX Deck Reference

**Theme scope only** — Ascentium colours, typography, brand chrome, and slide patterns for pptxgenjs.

Sandbox path: `/home/user/content-studio/skills/pptx/references/ascentium-deck.md`

**Not in this file:** `addText` / `addTable` / `addChart` syntax, corruption pitfalls → read **`pptxgenjs.md`** first.

Source: *Brand Guidelines Full Version R1.10 (Nov 2025)*.

===================================================================
## PART 1 — BRAND SYSTEM
===================================================================

### 1. Deliverable rules

- One `.pptx` via Node script — shell and `await pres.writeFile()` per **`pptxgenjs.md` § Script shell**.
- **Layout:** `LAYOUT_16x9` (10" × 5.625") for this theme.
- Brand PNGs: `addImage({ path })` from `pptx/assets/ascentium/` — never embed base64 in the script.
- Run: `cd /home/user/content-studio && node build-deck.js`.

### 2. Safe area (inches)

| Token | Value |
|-------|-------|
| `PAD.x` | 0.5 |
| `PAD.y` | 0.375 |
| Body max Y (above logo) | ~4.85 |
| Content corner | flush top-right `x:8.9, y:0, w:1.1, h:1.1` (square; bottom ≈ title row) |
| Content logo | `x:0.5, y:5.15, w:0.73, h:0.111` (⅔ prior; 512×78 ratio) |
| Cover logo | `y:5.05, w:0.87, h:0.133` (⅔ prior cover size) |

### 3. Palette (`ASCENTIUM`)

```javascript
const ASCENTIUM = {
  vibrantOrange: 'FF6611',
  midnightGreen: '0F1514',
  white: 'FFFFFF',
  orange1: 'FFF0E7',   // opal — soft slides, stat cards
  orange2: 'FFD1B8',
  orange3: 'FFA370',
  orange4: 'FF8541',
  mg1: 'B7B9B9',
  mg2: '878A8A',
  mg3: '575B5B',
  mg4: '272C2C',
  tealGreen: '077069',
  skyBlue: '1877F2',
  errorRed: 'DC3545',
  chartColors: ['FF6611', '077069', '1877F2', 'FFA370', '575B5B'],
  fontTitle: 'Poppins',
  fontBody: 'Poppins',
  fontCjk: 'Noto Sans SC',
};

const PAD = { x: 0.5, y: 0.375 };
const ASSETS = '/home/user/content-studio/skills/pptx/assets/ascentium';
```

### 4. Typography

| Role | pt | Weight | Colour |
|------|-----|--------|--------|
| Kicker | 12 | 600 | `FF6611`, uppercase |
| Slide title | 38 | 600 | `0F1514` |
| Cover title | 44–52 | 600 | `0F1514` or white on dark/orange cover |
| Body / bullets | 16–17 | 400 | `272C2C` |
| Subtitle | 15 | 400 | `575B5B` |
| Footnote | 11–12 | 400 | `878A8A` |

≤4 bullets per slide.

**CJK / mixed Chinese (critical):**

- `fontTitle` / `fontBody` = **Poppins** — Latin brand face; **no CJK glyphs**.
- `fontCjk` = **Noto Sans SC** — use for slide copy that includes Chinese (titles, bullets, labels).
- **Tables:** **never** set `fontFace: ASCENTIUM.fontBody` or `fontTitle` on `addTable` or in cell `options` — pptxgenjs writes that face to **East Asian (`ea`) runs too**, so Chinese becomes **□**. Either **omit `fontFace` in every cell** (safest) or set `fontFace: ASCENTIUM.fontCjk` on all cells.
- Viewers may still substitute missing glyphs in plain `addText` boxes but **not** in table cells — that is why only the comparison table breaks while titles/bullets look fine.

```javascript
const HAS_CJK = /[\u4e00-\u9fff\u3400-\u4dbf]/;
function fontFor(text) {
  return HAS_CJK.test(text) ? ASCENTIUM.fontCjk : ASCENTIUM.fontBody;
}
// Chinese deck: addSlideTitle(slide, t, y) → fontFace: fontFor(t)
// Tables: use TABLE_OPTS below — no Poppins anywhere
const TABLE_OPTS = { fontSize: 14, color: ASCENTIUM.mg4, margin: 0 }; // no fontFace
```

### 5. Brand assets & chrome rules

| File | Use | Placement (inches, LAYOUT_16x9) |
|------|-----|--------------------------------|
| `asc_cover_right_top_corner.png` | Cover only | Inset top-right `x:6.55, y:0.375, w:2.97, h:2.96` (760×757) |
| `asc_content_right-top-corner.png` | Every **content** slide | Flush top-right `x:8.9, y:0, w:1.1, h:1.1` (458×458; bottom ≈ title) |
| `asc_logo_black.png` | White / light slides | Bottom-left `x:PAD.x, y:5.15, w:0.73, h:0.111` (512×78) |
| `asc_logo_white.png` | Orange / midnight **cover** | Bottom-left `x:PAD.x, y:5.05, w:0.87, h:0.133` |

**Aspect ratio rule:** always set `w` and `h` from the PNG pixel ratio — never reuse another logo’s ratio. Or use `sizing: { type: 'contain', w, h }` per **`pptxgenjs.md` § Images**.

**Chrome rule:** content slides → small corner + black logo. Cover → large corner + logo (black on white cover, white on orange/midnight).

### 6. Brand helpers (copy into build script)

```javascript
const path = require('path');

function asset(file) {
  return path.join(ASSETS, file);
}

function addCoverChrome(slide, { whiteLogo = false } = {}) {
  slide.addImage({ path: asset('asc_cover_right_top_corner.png'), x: 6.55, y: 0.375, w: 2.97, h: 2.96 });
  slide.addImage({
    path: asset(whiteLogo ? 'asc_logo_white.png' : 'asc_logo_black.png'),
    x: PAD.x, y: 5.05, w: 0.87, h: 0.133,
  });
}

function addContentChrome(slide) {
  slide.addImage({ path: asset('asc_content_right-top-corner.png'), x: 8.9, y: 0, w: 1.1, h: 1.1 });
  slide.addImage({ path: asset('asc_logo_black.png'), x: PAD.x, y: 5.15, w: 0.73, h: 0.111 });
}

function addKicker(slide, text, y = PAD.y) {
  slide.addText(text.toUpperCase(), {
    x: PAD.x, y, w: 8.8, h: 0.22,
    fontFace: ASCENTIUM.fontTitle, fontSize: 12, bold: true,
    color: ASCENTIUM.vibrantOrange, charSpacing: 2, margin: 0,
  });
}

function addSlideTitle(slide, text, y) {
  slide.addText(text, {
    x: PAD.x, y, w: 8.8, h: 0.65,
    fontFace: ASCENTIUM.fontTitle, fontSize: 38, bold: true,
    color: ASCENTIUM.midnightGreen, margin: 0,
  });
}

function addBullets(slide, items, y) {
  slide.addText(
    items.map((t, i) => ({ text: t, options: { bullet: true, breakLine: i < items.length - 1 } })),
    {
      x: PAD.x, y, w: 8.8, h: 3.6,
      fontFace: ASCENTIUM.fontBody, fontSize: 17, color: ASCENTIUM.mg4,
      paraSpaceAfter: 10, margin: 0,
    },
  );
}
```

### 7. Design constraints

- Prefer `orange1` / `orange2` soft fills over full-slide orange.
- **Avoid:** full-width colour bars, vertical sidebar stripes, accent lines under titles, cream/beige defaults.

===================================================================
## PART 2 — SLIDE PATTERNS
===================================================================

One `pres.addSlide()` per pattern. Use helpers above + **`pptxgenjs.md`** for shapes/tables/charts syntax.

---

### `cover`

White (default), vibrant orange (`bg-org`), or midnight green (`bg-gd`).

```javascript
const cover = pres.addSlide();
cover.background = { color: ASCENTIUM.white };
addCoverChrome(cover, { whiteLogo: false });
cover.addText('Deck title', {
  x: PAD.x, y: 1.0, w: 7.5, h: 1.2,
  fontFace: ASCENTIUM.fontTitle, fontSize: 48, bold: true,
  color: ASCENTIUM.midnightGreen, margin: 0,
});
cover.addText('Subtitle line', {
  x: PAD.x, y: 2.35, w: 6.8, h: 0.8,
  fontFace: ASCENTIUM.fontBody, fontSize: 15, color: ASCENTIUM.mg3, margin: 0,
});
// bg-org: background FF6611, whiteLogo: true, white title/sub
// bg-gd: background 0F1514, whiteLogo: true, white title/sub
```

---

### `content-branded`

Default inner slide: chrome + kicker + title + bullets.

```javascript
const slide = pres.addSlide();
slide.background = { color: ASCENTIUM.white };
addContentChrome(slide);
addKicker(slide, '章节');
addSlideTitle(slide, 'Slide title', PAD.y + 0.35);
addBullets(slide, ['Point one', 'Point two', 'Point three'], PAD.y + 1.15);
```

Apply `addContentChrome` on every white content pattern below.

---

### `agenda`

Numbered list — bullet API per **`pptxgenjs.md` § Lists**.

```javascript
const agenda = pres.addSlide();
agenda.background = { color: ASCENTIUM.white };
addContentChrome(agenda);
addKicker(agenda, '议程');
addSlideTitle(agenda, 'Today', PAD.y + 0.35);
agenda.addText(
  ['Topic A', 'Topic B', 'Topic C'].map((t, i, a) => ({
    text: t, options: { bullet: { type: 'number' }, breakLine: i < a.length - 1 },
  })),
  { x: PAD.x, y: PAD.y + 1.1, w: 8.8, h: 3.5, fontSize: 18, color: ASCENTIUM.mg4, paraSpaceAfter: 12, margin: 0 },
);
```

---

### `stats-row`

Three KPI cards on `orange1`; centre card may use `midnightGreen`.

- Card shape: `'roundRect'`, `rectRadius: 0.12`
- Number: 40pt bold, `vibrantOrange` or `orange3` on dark card
- Label: 13pt `mg3`

Place at `y: 2.0`, card width `2.7`, gap `0.35`, starting `x: PAD.x`.

---

### `comparison-split`

Two `'roundRect'` cards — bad (`FFF5F5` / `FECACA` / `errorRed`) vs good (`F0FDF4` / `BBF7D0` / `tealGreen`), centre “vs” label.

---

### `data-table`

Dark header row (`midnightGreen` fill, white text). Table cell syntax → **`pptxgenjs.md` § Tables**.

**CJK:** header/body cells must **not** use Poppins — use `TABLE_OPTS` (no `fontFace`) or `fontFace: ASCENTIUM.fontCjk` on every cell.

```javascript
slide.addTable([
  [
    { text: '材料', options: { bold: true, color: ASCENTIUM.white, fill: { color: ASCENTIUM.midnightGreen } } },
    { text: '负责方', options: { bold: true, color: ASCENTIUM.white, fill: { color: ASCENTIUM.midnightGreen } } },
  ],
  [
    { text: '审计报告', options: TABLE_OPTS },
    { text: '财务部', options: TABLE_OPTS },
  ],
], { x: PAD.x, y: 1.35, w: 8.8, colW: [4, 4.8], ...TABLE_OPTS });
// ❌ never: fontFace: ASCENTIUM.fontBody on table or cells
```

---

### `process-steps`

Orange `'ellipse'` badge (0.45") + step title + grey subline. Stack vertically with `y` step ~1.15.

---

### `soft-bg`

Full slide `orange1`; centred title + subline. Chrome optional.

---

### `cta-close`

Background `midnightGreen`. Headline with `orange3` accent span. Two `'roundRect'` columns — muted dark left, `vibrantOrange` right.

---

### Pattern index

| ID | Chrome | Notes |
|----|--------|-------|
| `cover` | Large corner + logo | White / org / midnight variants |
| `content-branded` | Small corner + logo | Kicker + title + bullets |
| `agenda` | Yes | Numbered list |
| `stats-row` | Yes | 3 KPI cards |
| `comparison-split` | Yes | Good vs bad |
| `data-table` | Yes | Dark header table |
| `process-steps` | Yes | Numbered badges |
| `soft-bg` | Optional | Opal centred |
| `cta-close` | No | Dark two-column close |

Charts on any content slide: use `ASCENTIUM.chartColors` — see **`pptxgenjs.md` § Charts**.
