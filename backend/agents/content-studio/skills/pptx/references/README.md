# PPTX skill references — file roles

Read **both** the API reference and one theme deck when creating a deck.

| File | Scope | Read for |
|------|--------|----------|
| **`pptxgenjs.md`** | **Theme-neutral** pptxgenjs API | Script shell, layout sizes, `addText` / bullets / shapes / images / icons / tables / charts, corruption pitfalls |
| **`inspire-deck.md`** | **Inspire brand** (default for Content Studio) | Same as above for Inspire |
| **`ascentium-deck.md`** | **Ascentium brand** | Palette, fonts, logo/corner placement, slide patterns, branded coordinates |
| **`lrqa-deck.md`** | **LRQA brand** (default for LRQA Assist) | Navy/teal palette, square logo, shape chrome, slide patterns |

**Division of labour**

- `pptxgenjs.md` — *how* to call the library (syntax, options, pitfalls). No brand colours, logos, or slide-type catalogue.
- `*-deck.md` — *what* the deck should look like (tokens, chrome rules, pattern library). Uses pptxgenjs APIs but does not re-teach them.

Sandbox paths:

- `/home/user/content-studio/skills/pptx/references/`
- `/home/user/content-studio/skills/pptx/assets/{ascentium,inspire,lrqa}/`
