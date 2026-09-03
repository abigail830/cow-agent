# Icons — Lucide (CDN)

Slides use **[Lucide](https://lucide.dev/)** stroke icons via CDN — same pattern as Google Fonts in `fonts.css`. No local SVG download or bundling.

## Setup (automatic)

Normalize injects into every deck `<head>`:

```html
<script src="https://unpkg.com/lucide@0.469.0/dist/umd/lucide.min.js"></script>
<script src="../../assets/runtime.js"></script>
```

`runtime.js` calls `lucide.createIcons()` on load. Icons inherit theme accent through `.slide-icon-box { color: var(--accent) }`.

## Usage

```html
<!-- Four pillars — four separate icon boxes -->
<div class="grid g4">
  <div class="card">
    <span class="slide-icon-box sm" aria-hidden="true"><i data-lucide="database"></i></span>
    <h4>Module 01</h4>
    <p class="dim">…</p>
  </div>
  <div class="card">
    <span class="slide-icon-box sm" aria-hidden="true"><i data-lucide="messages-square"></i></span>
    <h4>Module 02</h4>
  </div>
  <!-- … -->
</div>

<!-- Single KPI / pillar -->
<span class="slide-icon-box" aria-hidden="true"><i data-lucide="rocket"></i></span>
<h4>Phase 1 delivery</h4>

<!-- List row -->
<li class="slide-icon-inline">
  <span class="slide-icon-box sm" aria-hidden="true"><i data-lucide="check-circle"></i></span>
  <span>完成三大交付闭环</span>
</li>
```

Browse all names at [lucide.dev/icons](https://lucide.dev/icons/) — use kebab-case (`bar-chart`, `check-circle`, `pen-line`).

## Hard rules

| Do | Don't |
|---|---|
| `<i data-lucide="shield">` inside `.slide-icon-box` | Emoji on visible slides |
| **One icon box per column/card** (four pillars → four boxes) | One shared icon box for the whole slide |
| Copy from `three-column.html` / `kpi-grid.html` | Deprecated `data-icon="..."` on empty `<span>` |
| Semantic icon per block (calendar → milestone) | Random decorative spam |
| Copy icon markup from `templates/single-page/` layouts | Download SVG files into the repo |

## Common picks (executive decks)

| Lucide name | Use for |
|---|---|
| `rocket` | Launch, phase 1, go-live |
| `target` | Goals, KPI, focus |
| `bar-chart` / `trending-up` | Metrics, growth |
| `users` | Team, customers |
| `check-circle` | Done, acceptance |
| `calendar` | Timeline, quarters |
| `shield` | Risk, security |
| `lightbulb` | Insight, recommendation |
| `layers` | Architecture, platform |
| `layout-grid` | Modules, structure |
| `palette` | Brand, design |
| `zap` | Automation, speed |

## Layouts with icons

`three-column`, `roadmap`, `kpi-grid`, `flow-diagram`, `arch-diagram`, `chart-pie` — copy their icon markup when copying those layouts.

Ascentium (`asc-brand`): avoid pure text pages — pair Lucide icon + metric/chart (see `themes.md`).

## Offline / export note

Icons need network access on first load (unpkg). For fully offline PDF/PNG export in air-gapped env, pin Lucide locally — not required for normal preview/export with network.
