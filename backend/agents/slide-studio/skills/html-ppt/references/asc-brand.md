# BRAND & DESIGN

## PPTX Skill Design Ideas

**Don't create boring slides.** Plain bullets on a white background won't impress anyone. Consider ideas from this list for each slide.

## Ascentium Design Principles: The Architect’s Vision

Before executing code, establish a cohesive strategic narrative by following these core pillars.

### I. Color Narrative & Economy
* **Topic-Driven Palettes**: Colors are "content-informed". Use `Midnight_Green`（#0F1514） to anchor stability and `C_ORANGE`（#FF6600） to signal growth.
* **The 80/20 Rule**: Avoid visual noise by ensuring hierarchy through dominance. Maintain 60-80% "breathing room" with `C_WHITE`（#FFFFFF） or `C_BG_CREAM`（#F5F2EF）, reserving saturated hero colors for ≤20% of the slide area.
* **White as the default surface**: Treat whitespace as **intentional** design—not empty space waiting to be filled.
* **One hero per slide**: At most **one** large saturated focal block (midnight_green or vibrant_orange); keep other emphasis to light tints, outlines, or neutrals so hierarchy stays obvious.
* **Semantic consistency**: Reuse the same hue for the **same meaning** across the deck (e.g. orange = timeline / momentum everywhere); avoid repurposing accent colors for unrelated roles.
* **Ghost cards**: Prefer **`FFFFFF`** fill + thin **`E0E0E0`** border over heavy tinted fills when you only need grouping—lighter and more modern than solid blocks.
* **Signature Motif**: Pick *one* distinctive design cue (e.g., rounded frames or specific border accents) and repeat it consistently throughout the deck.

### II. Canvas & Background Strategy
* **Functional Backgrounds**: Select a variant based on the slide's "mode".
    * **Announcements**: Use `variant="dark"` or `"orange"` for high-impact Covers, Transitions, and Conclusions.
    * **Evidence**: Use `variant="white"` for complex data/charts and `"cream"` for long-form editorial reading.
* **The 40/60 Split (Dual-Tone)**: Use split backgrounds to separate Narrative Context from Data.
    * **Practice**: Fill the left 40% with a highlight **`FFE0CF`（C_BG_HIGHLIGHT）** as appropriate—while keeping the right 60% **`C_WHITE`（FFFFFF）** for chart/table legibility (see `color_system` supplementary + brand_primary).
    * **Execution**: Always sync text colors with the active variant's `title_color` for maximum contrast.

### III. Visual Architecture: Structure as Hero
* **Strategic Partitioning**: Use Dual-Column or Grid layouts to manage density. Prioritize whitespace and proximity over physical containers to group related ideas.
* **Visual Anchors**: Use a "Power Metric" or punchy quote as a center of gravity to anchor the slide. This provides a focal point without needing decorative backgrounds.
* **Minimalist Dividers**: Avoid "The Dashboard Trap". Prefer a single side-accent line or a thin C_BORDER divider over solid-filled cards to keep the layout "light" and airy.
* **Containment Discipline**: Use physical cards only as a last resort for content that must be isolated from the main narrative flow.

### Color Palettes

When using the Ascentium template, strickly follow below color_system

```json
"color_system": {
  "brand_primary": {
    "midnight_green": {
      "name_cn": "午夜绿",
      "name_en": "Midnight Green",
      "hex": "#0F1514",
      "usage": "Primary brand color; used for logos, titles, dark backgrounds, emphasis text, and footer lines.",
      "description": "Represents professionalism, trust, and global leadership."
    },
    "vibrant_orange": {
      "name_cn": "活力橙",
      "name_en": "Vibrant Orange",
      "hex": "#FF6600",
      "usage": "Brand accent color; used for large background areas on section slides, first-sequence chart data, key annotations, call for action and decorative blocks.",
      "description": "Symbolizes growth, momentum, and the spirit of ascending."
    }
  },
  "brand_secondary": {
    "white": {
      "name_cn": "纯白",
      "name_en": "White",
      "hex": "#FFFFFF",
      "usage": "Main background for content slides, reverse-white logos, and body text on dark backgrounds.",
      "description": "Pure white to maintain page breathability."
    },
    "slate_gray": {
      "name_cn": "板岩灰",
      "name_en": "Slate Gray",
      "hex": "#4A4A4A",
      "usage": "Auxiliary text, subtitles, and non-essential content descriptions.",
      "description": "Neutral gray used to balance visual intensity."
    },
    "light_blue": {
      "name_cn": "浅蓝",
      "name_en": "Light Blue",
      "hex": "#BDD5EF",
      "usage": "Neutral decorative blocks, auxiliary chart colors, or background fill for content partitioning.",
      "description": "Soft light blue for neutral card filling and light-weight layer differentiation."
    }
  },
  "functional": {
    "text_primary": {
      "hex": "#0F1514",
      "usage": "Body titles and critical information; ensures alignment with brand identity."
    },
    "text_body": {
      "hex": "#333333",
      "usage": "Standard body text color; ensures comfort for long-duration reading."
    },
    "border": {
      "hex": "#E0E0E0",
      "usage": "Table borders and divider lines."
    }
  },
  "charts_palette": [
    "#FF6611",
    "#077069",
    "#1877F2",
    "#043834"
  ],
  "supplementary": {
    "highlight_tint": {
      "name_cn": "浅橙",
      "hex": "#FFF0E7",
      "usage": "High-lighting key content and local emphasis areas; can be layered at 50% transparency for soft highlights."
    },
    "cream": {
      "name_cn": "奶油",
      "hex": "#F5F2EF",
      "usage": "Background fill for alternating table rows."
    }
  }
}
```

### ## Page Backgrounds & Canvas Strategy

Your background choice sets the "atmospheric mode" of the slide. Rather than picking colors randomly, select a canvas based on content density and strategic intent.

* **Monochromatic Canvas: The Power of Single Tones**
    * **Principle**: Use background variants to define the slide’s function—light for data-heavy "Evidence" and bold/dark for high-impact "Announcements."
    * **Practice**:
        * **Standard (`"white"`)**: The default for complex charts and dense tables.
        * **Premium (`"midnight_green"`)**: High-impact for powerful statements or image-centric slides.
        * **Transition (`"vibrant_orange"`)**: Reserved for chapter starts and section breaks.

* **Dual-Tone Canvas: The 40/60 Split**
    * **Principle**: Use a split-tone background to separate "Context" (Narrative) from "Data" (Visuals). This creates a natural eye-path from left to right.
    * **Practice**: 
        * **Narrative Anchor**: Fill the left 40% (≈5.33") with `C_BG_HIGHLIGHT` to house summaries or key takeaways.
        * **Data Stage**: Keep the right 60% (≈8.0") as `C_WHITE` to ensure charts and tables remain clean and legible.
    * **Implementation**: Apply the split using `add_rect` first, then layer the `"white"` chrome over the entire slide for a unified brand frame.

* **Visual Logic: Auto-Adaptive Assets**
    * **Principle**: Brand assets (logos/corners) must remain visible. Trust the `chrome` helper to handle the technical switching of logo versions.
    * **Practice**: When using dark or split backgrounds, always sync your text colors with the returned `title_color` from the chrome helper to ensure maximum contrast.

### ## For Each Slide: Visual Architecture

Effective slides balance information density with visual clarity. Your goal is to transform raw knowledge into a structured narrative where the layout itself guides the user's understanding.

* **Information Architecture: Structure as a Visual**
    * **Principle**: When content is text-heavy, the *structure* becomes the visual hero. Avoid monolithic blocks; use spatial distribution to signal importance.
    * **Practice**:
        * **Strategic Partitioning**: Use Dual-Column or Grid layouts to break complex arguments into digestible "knowledge clusters".
        * **The Editorial Anchor**: If a high-quality image or chart is unavailable, use a "Power Metric" or a punchy "Executive Quote" as the slide's visual gravity center.
        * **The Half-Bleed Logic**: Reserve full-height imagery for high-impact storytelling where emotional resonance is as important as the data.

* **Data Presence: The "Power" Metric**
    * **Principle**: Data should be felt, not just read. Strategic insights gain authority when key supporting metrics are visually hierarchy through scale and placement.
    * **Practice**: 
        * **Stat Callouts**: Use oversized figures for "Hero" metrics to provide an immediate takeaway.
        * **Mapping Relationships**: Use Matrices, Timelines, or Funnels to visualize the *logic* between data points rather than just listing facts.

* **Decorative Geometry: Purposeful Partitioning**
    * **Principle**: Shapes are structural tools used to organize high-density information. Avoid decorative layering that doesn't serve a functional grouping purpose.
    * **Practice**:
        * **Contextual grouping**: Use semi-transparent cards or thin `C_BORDER` outlines to wrap related ideas, creating a clean typographic grouping.
        * **Visual Breathing Room**: Regardless of text density, maintain the 80/20 rule—ensure the cumulative area of decorative blocks remains ≤20% to avoid visual clutter.


### Typography

The default template defines **two contexts**: 
- the global `typography` hierarchy (cover / section / in-slide headings);
- and **content slides** (`page_types.content_page`).

#### Font stacks

**Type scale & hierarchy**

| Element | Size | Font | Notes |
| :--- | :--- | :--- | :--- |
| **Cover Title** | **48-54pt Bold** | Poppins / Noto Sans | Color `C_TEXT_PRIMARY` (#0F1514),Primary focus for deck identification. |
| **Cover Subtitle** | **20-24pt Regular** | Poppins / Noto Sans | Color `MIDNIGHT_GREEN_3` (#575B5B). Used for Context/Date/Author. |
| **Section Title** | **36-44pt Semi-Bold** | Poppins / Noto Sans | Text `C_WHITE` (#FFFFFF). Typically used on Vibrant Orange or dark variants. |
| **Slide Title (Chrome)** | **24-28pt Semi-Bold** | Poppins / Noto Sans | Color `C_TEXT_PRIMARY` (#0F1514). Top-level heading for digital clarity. |
| **In-slide H1** | **14-18pt Semi-Bold** | Poppins / Noto Sans | Color `MIDNIGHT_GREEN` (#0F1514). Used for major content grouping. |
| **In-slide H2** | **11-13pt Medium** | Poppins / Noto Sans | Color `C_TEXT_PRIMARY` (#0F1514). For sub-headers or card/table titles. |
| **Body Text** | **10-12pt Regular** | Poppins / Noto Sans | Color `MIDNIGHT_GREEN_4` (#272C2C). Standard density with 1.2 line spacing. |
| **Captions** | **8–10 pt** | Regular | 补充说明；用于脚注、来源引用或法律声明。 |
| **Page Number** | **8pt Regular** | Poppins / Noto Sans | Color `MIDNIGHT_GREEN_3` (#575B5B). Right-aligned at the bottom edge. |

### Key Design Principles for Typography

* **Primary Typeface**: Poppins is the global standard for English content to ensure a modern and confident brand presence.
* **Chinese Typeface**: Noto Sans is mandatory for Simplified and Traditional Chinese to maintain a clean aesthetic.
* **Weight Usage**: 
    * Use **Semi-Bold** for titles and headings to provide prominence.
    * Use **Medium** for emphasis within body text to maintain design hierarchy without disrupting flow.
    * Use **Regular** for smaller copy and body text to ensure optimal readability.
* **System Fallbacks**: 
    * **English**: Use Arial only if Poppins is unavailable.
    * **Chinese (Windows)**: Use Microsoft YaHei if Noto Sans is unavailable.
    * **Chinese (Mac/iOS)**: Use PingFang as the fallback typeface.
* **Tracking & Spacing**: 
    * Maintain standard tracking for body text to ensure cohesion.
    * Headings may use slightly increased tracking for better readability in larger formats.
* **Color Contrast**: All text pairings must pass WCAG 2.0 level AA requirements (e.g., Midnight Green on White provides a ratio of 18.58).

### Tables

| Property | Specification |
| :--- | :--- |
| **Header Fill Color** | `#FF6611` (Vibrant Orange)  |
| **Header Text Color** | `#FFFFFF` (White)  |
| **Header Typography** | 11-13pt Semi-Bold; Line Spacing 1.0; Poppins / Noto Sans|
| **Alternating Row Fill (Optional)** | Default all-white rows (`#FFFFFF`). If zebra striping is needed, use `#FFFFFF` + `#F5F2EF` (Cream) only.  |
| **Cell Text Color** | `#272C2C` (Midnight Green 4)  |
| **Cell Typography** | 10-12pt Regular; Poppins / Noto Sans |
| **Border Specification** | `#B7B9B9` (Midnight Green 1); `border_pt = 1`  |
| **Visual Style** | Prefer horizontal-only dividers for a clean, modern aesthetic.  |


### Spacing & Dynamic Layout Logic

**Slide Grid (Content Page):** * **Canvas Size**: 13.33″ × 7.5″ (`LAYOUT_WIDE`).
* **Safe Area**: Body content must stay within **x: 0.403″ to 12.93″** and **y: 1.1″ to 6.35″**. 
* **Z-Order**: The orange L-corner asset (graphic device) is placed first. All content shapes render on top; do not shrink the right boundary to avoid the corner.

**Rhythm & Alignment:**
* **Block Spacing**: Maintain **~0.3–0.5″** between major content blocks to ensure "breathing room."
* **Bullet Spacing**: Use `para_space_after` of **4–6 pt**. Avoid `para_space_after` ≥ 12 pt to prevent broken visual rhythm.
* **Padding (Cards/Shapes)**: When text is inside a colored background shape, set all margins to **0.15″** to prevent text from feeling cramped.
* **Flush Alignment**: Set `margin=0` only when a text run must sit flush against an icon or divider.


### content page
严格遵循下面的板式要求输出内容页

```json
      "content_page": {
          "description": "Standard content slide using official brand typefaces. High-impact layout with integrated brand graphic devices. Use LAYOUT_WIDE (13.33\" × 7.5\").",
          "layout": "LAYOUT_WIDE",
          "slide_dimensions_in": { "w": 13.33, "h": 7.5 },
          "font": "Poppins, Noto Sans",
          "content_safe_area_in": {
              "x": 0.403, "y": 1.1, "w": 12.527, "h": 5.25,
              "right_edge": 12.93,
              "bottom_edge": 6.35,
              "note": "Symmetric ~0.40\" padding on both sides. The Vibrant Orange L-corner (#FF6611) at top-right (x=11.948–13.33, y=0–1.382) is placed first in z-order — content can overlap it safely."
          }
      }
```

### cover page
封面统一使用下面的板式（`add_cover_chrome` + `add_cover_title` 已按此实现）。
两种 variant 可选：白色（默认）或活力橙。

```json
      "cover_page": {
          "description": "Brand cover — solid colour background + cover corner image top-right + logo. Use LAYOUT_WIDE (13.33\" × 7.5\"). Cover text uses Poppins (Latin) + Noto Sans (CJK).",
          "layout": "LAYOUT_WIDE",
          "slide_dimensions_in": { "w": 13.33, "h": 7.5 },
          "font": "Poppins, Noto Sans",
          "corner_image_in": { "x": 9.19, "y": 0.19, "w": 3.94, "h": 3.94,
              "note": "reference/cover_right_top_corner.png; 284×284 design-px @72pt/in" },
          "title_in":    { "x": 0.40, "y": 2.00, "w": 8.00, "h": 1.50, "size_pt": 50 },//size_pt range 48-54 
          "subtitle_in": { "x": 0.40, "y": 4.20, "w": 8.00, "h": 0.80, "size_pt": 24 },//size_pt range 20-24
          "variants": {
              "white": {
                  "background": "#FFFFFF",
                  "logo_asset": "reference/logo.png",
                  "logo_position_in": { "x": 0.126, "y": 6.610, "w": 2.230, "h": 0.890 },
                  "title_color": "#0F1514",
                  "subtitle_color": "#575B5B"
              },
              "orange": {
                  "background": "#FF6600",
                  "logo_asset": "reference/logo_white.png",
                  "logo_position_in": { "x": 0.126, "y": 6.610, "w": 2.230, "h": 0.890 },
                  "title_color": "#FFFFFF",
                  "subtitle_color": "#FFFFFF"
              }
          }
      }
```

> Cover slides are optional. If used, they should be the first slide. `add_cover_chrome()` returns a variant dict — pass `v["title_color"]` and `v["subtitle_color"]` to `add_cover_title()` so text colour matches the background.


### Avoid (Common Mistakes)

- **Don't repeat the same layout** — vary columns, cards, and callouts across slides
- **Don't center body text** — left-align paragraphs and lists; center only titles
- **Don't skimp on size contrast** — follow the template scale (e.g. 24pt content titles vs 10pt body, 48pt cover) so hierarchy stays obvious，ensure maximum legibility and visibility for long-distance projection.
- **Don't default to off-brand colors** — user-specified colors win; absent that, treat the deck as Ascentium-branded and stay within color_system defined above
- **Don't mix spacing randomly** — choose 0.3" or 0.5" gaps and use consistently
- **Don't style one slide and leave the rest plain** — commit fully or keep it simple throughout
- **Don't create text-only slides** — add images, icons, charts, or visual elements; avoid plain title + bullets
- **Don't forget text box padding** — when aligning lines or shapes with text edges, set `margin: 0` on the text box or offset the shape to account for padding
- **Don't use low-contrast elements** — icons AND text need strong contrast against the background; avoid light text on light backgrounds or dark text on dark backgrounds
- **NEVER use accent lines under titles** — use whitespace or background color instead
- **Don't overlay rectangular accent bars on `add_rounded_rect`** — the rounded corners can't be covered, leaving a visual notch. If you need a flush accent edge, use `add_rect` for the base shape instead.
- **Don't pad bullets with large `para_space_after`** — keep it at 4–6 pt; bigger values produce ragged lists and break Spacing rhythm.
- **Don't forget `margin=0`** when a text box must align flush with a shape at the same `x` (default text-box padding ≈ 0.05″ will look mis-aligned).
- **Decorative blocks — max 2 fill colors per slide** (e.g. one hero + one neutral deco). Using 3+ colors collapses visual hierarchy.
- **Decorative blocks — max 50% combined area** (including overlaps). Beyond that the slide reads as visual noise.
- **Keep page-bg palette and deco palette separate** — never reuse the page background color as a block fill (e.g. if `variant="cream"`, don't fill cards with `#F5F2EF`), and never use a deco color as a full-page chrome variant.
- **`#BDD5EF` (light_blue / C_LIGHT_BLUE) is a deco color, not a page background** — use `add_content_page_chrome` for full-page variants.



