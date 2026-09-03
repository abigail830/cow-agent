---
name: pptx
description: "Use this skill any time a .pptx or .potx file is involved — creating slide decks, editing presentations, or reading deck content. Trigger on \"deck,\" \"slides,\" \"presentation,\" or a .pptx / .potx filename."
license: Proprietary. LICENSE.txt has complete terms
---

# PPTX skill

A `.pptx` is a ZIP of XML parts. Pick the path by task:

| Task | Approach |
|------|----------|
| **Create** a new deck | **Node.js + pptxgenjs** — see [References](#references) |
| **Edit** an existing deck or fill a template | unzip → edit XML (optional Python helpers in `scripts/`) |
| **Read** slide text | `markitdown deck.pptx` |

## References (three files, three roles)

| File | Role |
|------|------|
| `references/pptxgenjs.md` | **API** — text, lists, shapes, images, tables, charts, script shell, pitfalls |
| `references/ascentium-deck.md` | **Ascentium theme** — colours, typography, brand chrome, slide patterns |
| `references/inspire-deck.md` | **Inspire theme** — same for Inspire |

Sandbox mirror: `/home/user/content-studio/skills/pptx/references/`  
Brand PNGs: `/home/user/content-studio/skills/pptx/assets/<theme>/`

## Create workflow

1. Clarify topic, audience, slide count, and theme (`ascentium` default, `inspire` when requested).
2. **`read` `pptxgenjs.md`** — script shell + element APIs you will need.
3. **`read` the theme `*-deck.md`** — copy Part 1 helpers; build slides from Part 2 patterns.
4. Write `build-deck.js` in `/home/user/content-studio/`; run `node build-deck.js` (`2>&1` on failure).
5. **`publish_artifact`** the final `.pptx`.

Do **not** invent colours, fonts, or layout names outside the active theme deck.

## Edit / read (optional)

```bash
python3 -c "import sys,zipfile; zipfile.ZipFile(sys.argv[1]).extractall('unpacked')" deck.pptx
markitdown deck.pptx
```

See `scripts/` for OXML helpers when modifying existing files.

## Dependencies

Node.js + `pptxgenjs` (preinstalled). Optional: Python `markitdown[pptx]`, `defusedxml`, `Pillow`.
