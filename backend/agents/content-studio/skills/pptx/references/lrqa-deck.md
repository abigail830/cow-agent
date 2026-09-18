# LRQA PPTX Deck Reference

**Theme scope only** — LRQA colours, typography, brand chrome, and slide patterns for pptxgenjs.

Sandbox path: `/home/user/content-studio/skills/pptx/references/lrqa-deck.md`

**Not in this file:** pptxgenjs API syntax → read **`pptxgenjs.md`** first.

**Not Ascentium / Inspire** — no orange/Poppins, Starry Blues/Creative Blue, MiSans, Georgia, or other-brand PNGs.

===================================================================
## PART 1 — BRAND SYSTEM
===================================================================

### 1. Deliverable rules

- Script shell per **`pptxgenjs.md` § Script shell**.
- **Layout:** `LAYOUT_16x9` (10″ × 5.625″).
- Assets: `pptx/assets/lrqa/`.

### 2. Palette (`LRQA`)

```javascript
const LRQA = {
  navy: '1A1E33',
  navyMid: '33374C',
  teal: '00DDB3',
  mist: 'F5F7F8',
  white: 'FFFFFF',
  text: '1A1E33',
  textMuted: '6B7280',
  chartColors: ['00DDB3', '1A1E33', '33374C', '6B7280', '88E8D0'],
  fontHeadline: 'Arial',
  fontBody: 'Arial',
  fontCjk: 'Microsoft YaHei', // tables / Chinese when fontFace required; omit in cells if possible
};

const PAD = { x: 0.5, y: 0.4 };
const ASSETS = '/home/user/content-studio/skills/pptx/assets/lrqa';
const FOOTER_BAR_H = 0.55;
const SLIDE_W = 10;
const SLIDE_H = 5.625;
```

Teal ≈ **5–12%** of slide area — titles on dark slides, accents, corner triangle — not full-bleed fills on content slides.

### 3. Typography

| Role | Font | pt | Colour |
|------|------|-----|--------|
| Cover / section title | Arial | 36–42 bold | `00DDB3` on dark |
| Section kicker | Arial | 14 bold | white on dark |
| Subtitle / meta (dark) | Arial | 16–18 | white |
| Content slide title | Arial | 28–32 bold | `1A1E33` |
| Body | Arial | 14–16 | `1A1E33` |
| Footer title / page # | Arial | 11–12 | white on navy bar |

Viewer fallback: Arial → Helvetica → sans-serif.

**CJK / tables:** omit `fontFace` in cells (preferred) or use `fontCjk` on every cell — never invent brand fonts for tables.

```javascript
const TABLE_OPTS = { fontSize: 13, color: LRQA.text, margin: 0 }; // no fontFace — preferred
```

### 4. Brand assets & chrome rules

| File | Use | Placement (inches; native PNG **124×124** square) |
|------|-----|-----------------------------------------------------|
| `lrqa_logo.png` | Cover / section / content footer | Square mark — keep **1:1** aspect |

**Aspect ratio rule:** logo is **square** — never copy `w/h` from Ascentium or Inspire wordmarks.

**Chrome rule:**

- **Dark cover / section:** full navy bg + diagonal `navyMid` shape + teal ribbon/triangle shapes + logo top-left. **Do not** require extra corner PNGs — use `addShape`.
- **Light content:** white bg + navy footer bar (logo left, deck title center, page # right) + teal right-angle triangle at bottom-right corner of the bar.

### 5. Brand helpers

```javascript
const path = require('path');

function asset(file) {
  return path.join(ASSETS, file);
}

/** Top-left square logo (124×124 source). */
function addLogo(slide, { x = PAD.x, y = 0.28, w = 0.55 } = {}) {
  slide.addImage({ path: asset('lrqa_logo.png'), x, y, w, h: w });
}

/**
 * Dark cover / section background:
 * - full navy
 * - diagonal mid-navy panel (right side)
 * - teal geometric ribbon bottom-right
 * - logo top-left
 */
function addDarkCoverChrome(slide) {
  slide.addShape('rect', {
    x: 0, y: 0, w: SLIDE_W, h: SLIDE_H,
    fill: { color: LRQA.navy }, line: { color: LRQA.navy },
  });
  // Mid-navy diagonal panel (approx right wedge via large rotated-feel rectangle stack)
  slide.addShape('rightTriangle', {
    x: 4.2, y: 0, w: 5.8, h: SLIDE_H,
    fill: { color: LRQA.navyMid }, line: { color: LRQA.navyMid },
    rotate: 180,
  });
  // Teal corner ribbon (two overlapping rects / triangle)
  slide.addShape('rightTriangle', {
    x: 7.35, y: 4.15, w: 2.65, h: 1.48,
    fill: { color: LRQA.teal }, line: { color: LRQA.teal },
  });
  addLogo(slide, { x: PAD.x, y: 0.32, w: 0.62 });
}

function addSectionChrome(slide) {
  addDarkCoverChrome(slide);
}

/**
 * Content footer: navy bar + logo + title + page number + teal corner triangle.
 * Call on every light content slide. `pageLabel` e.g. "3" or "03".
 */
function addContentChrome(slide, { deckTitle = '', pageLabel = '' } = {}) {
  const barY = SLIDE_H - FOOTER_BAR_H;
  slide.addShape('rect', {
    x: 0, y: barY, w: SLIDE_W, h: FOOTER_BAR_H,
    fill: { color: LRQA.navy }, line: { color: LRQA.navy },
  });
  // Teal right-angle triangle at bottom-right
  slide.addShape('rightTriangle', {
    x: SLIDE_W - 0.42, y: SLIDE_H - 0.42, w: 0.42, h: 0.42,
    fill: { color: LRQA.teal }, line: { color: LRQA.teal },
  });
  const logoW = 0.36;
  slide.addImage({
    path: asset('lrqa_logo.png'),
    x: 0.28, y: barY + (FOOTER_BAR_H - logoW) / 2, w: logoW, h: logoW,
  });
  if (deckTitle) {
    slide.addText(String(deckTitle), {
      x: 0.85, y: barY + 0.12, w: 7.2, h: 0.32,
      fontFace: LRQA.fontBody, fontSize: 11, color: LRQA.white, margin: 0,
    });
  }
  if (pageLabel) {
    slide.addText(String(pageLabel), {
      x: 8.55, y: barY + 0.12, w: 0.9, h: 0.32,
      fontFace: LRQA.fontBody, fontSize: 12, color: LRQA.white, align: 'right', margin: 0,
    });
  }
}

function addCoverTitleBlock(slide, { title, subtitle, presenter, date }) {
  let y = 1.85;
  slide.addText(String(title), {
    x: PAD.x, y, w: 6.8, h: 1.1,
    fontFace: LRQA.fontHeadline, fontSize: 36, bold: true,
    color: LRQA.teal, margin: 0, valign: 'top',
  });
  y += 1.15;
  if (subtitle) {
    slide.addText(String(subtitle), {
      x: PAD.x, y, w: 6.5, h: 0.4,
      fontFace: LRQA.fontBody, fontSize: 18, color: LRQA.white, margin: 0,
    });
    y += 0.55;
  }
  if (presenter || date) {
    const meta = [presenter, date].filter(Boolean).map(String).join('\n');
    slide.addText(meta, {
      x: PAD.x, y, w: 5, h: 0.6,
      fontFace: LRQA.fontBody, fontSize: 14, color: LRQA.white, margin: 0,
    });
  }
}

function addSlideTitle(slide, text, y = PAD.y) {
  slide.addText(String(text), {
    x: PAD.x, y, w: 9.0, h: 0.55,
    fontFace: LRQA.fontHeadline, fontSize: 28, bold: true,
    color: LRQA.text, margin: 0,
  });
}
```

**Shape note:** If `rightTriangle` is unavailable in the installed pptxgenjs, approximate the diagonal with a large `rect` on the right (`x: 5.5, w: 4.5, h: SLIDE_H`, fill `navyMid`) and a teal `rect` strip at the bottom-right (`x: 7.5, y: 4.6, w: 2.5, h: 1.0`). Prefer shapes over inventing PNGs.

### 6. Design constraints

- **Avoid:** Ascentium orange, Inspire blues, Poppins, MiSans, Georgia, pure black (`000000`) body on white when `1A1E33` is available.
- Keep teal for emphasis; content slides stay mostly white + navy footer.

===================================================================
## PART 2 — SLIDE PATTERNS
===================================================================

---

### `cover-dark`

1. `addDarkCoverChrome(slide)`
2. `addCoverTitleBlock(slide, { title, subtitle, presenter, date })`

---

### `section-divider`

1. `addSectionChrome(slide)`
2. Small white kicker e.g. `Section 01` at `y: 1.7`
3. Teal title (32–40pt) + white subtitle

```javascript
slide.addText(String(sectionLabel), {
  x: PAD.x, y: 1.7, w: 6, h: 0.35,
  fontFace: LRQA.fontBody, fontSize: 14, bold: true, color: LRQA.white, margin: 0,
});
slide.addText(String(sectionTitle), {
  x: PAD.x, y: 2.15, w: 6.8, h: 0.9,
  fontFace: LRQA.fontHeadline, fontSize: 34, bold: true, color: LRQA.teal, margin: 0,
});
slide.addText(String(sectionSubtitle || ''), {
  x: PAD.x, y: 3.15, w: 6.5, h: 0.4,
  fontFace: LRQA.fontBody, fontSize: 16, color: LRQA.white, margin: 0,
});
```

---

### `light-content`

White background. `addSlideTitle` + body/bullets per **`pptxgenjs.md` § Lists**. Always `addContentChrome(slide, { deckTitle, pageLabel })`. Leave bottom ~0.7″ clear of body text for the footer bar.

---

### `section-bullets`

Same as `light-content` with a bullet list.

---

### `data-table`

Navy header (`navy` fill, white text). Syntax → **`pptxgenjs.md` § Tables**. Then `addContentChrome`.

```javascript
slide.addTable([
  [
    { text: '维度', options: { bold: true, color: LRQA.white, fill: { color: LRQA.navy } } },
    { text: '说明', options: { bold: true, color: LRQA.white, fill: { color: LRQA.navy } } },
  ],
  [
    { text: '示例行', options: TABLE_OPTS },
    { text: '单元格内容', options: TABLE_OPTS },
  ],
], { x: PAD.x, y: 1.2, w: 9.0, colW: [3.2, 5.8], ...TABLE_OPTS });
addContentChrome(slide, { deckTitle: 'Deck title', pageLabel: '4' });
```

---

### `contact-close`

Reuse `cover-dark` chrome with closing title + contact lines in white/teal.

---

### Pattern index

| ID | Chrome | Notes |
|----|--------|-------|
| `cover-dark` | Shape chrome + logo | Title slide |
| `section-divider` | Same dark chrome | Section opener |
| `light-content` | Navy footer bar | Standard content |
| `section-bullets` | Footer bar | Bullets |
| `data-table` | Footer bar | Navy header table |
| `contact-close` | Dark chrome | Closing |

Charts: `LRQA.chartColors` — **`pptxgenjs.md` § Charts**.
