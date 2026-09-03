# Themes catalog

Every theme is a short CSS file in `assets/themes/` that overrides tokens
defined in `assets/base.css`. Switch themes by changing the `href` of
`<link id="theme-link">` or by pressing **T** if the deck has a
`data-themes="a,b,c"` attribute on `<body>` or `<html>`.

All themes define the same variables: `--bg`, `--bg-soft`, `--surface`,
`--surface-2`, `--border`, `--text-1/2/3`, `--accent`, `--accent-2/3`,
`--good`, `--warn`, `--bad`, `--grad`, `--grad-soft`, `--radius*`, `--shadow*`,
`--font-sans`, `--font-display`.

## Light & calm

| name | description | when to use |
|---|---|---|
| `minimal-white` | 极简白，克制高级。Inter，强文字层级，极低阴影。 | 内部汇报、一对一技术评审、不抢内容的严肃话题 |
| `editorial-serif` | 杂志风 Playfair 衬线 + 奶油底。 | 品牌故事、文字密度大的长文演讲 |
| `soft-pastel` | 柔和马卡龙三色渐变。 | 产品发布、面向消费者、轻松话题 |
| `xiaohongshu-white` | 小红书白底 + 暖红 accent + 衬线标题。 | 小红书图文、生活/美学类内容 |
| `solarized-light` | 经典低眩光配色。 | 长时间观看的工作坊、教学 |
| `catppuccin-latte` | catppuccin 浅色。 | 开发者、极客友好的技术分享 |

## Bold & statement

| name | description | when to use |
|---|---|---|
| `sharp-mono` | 纯黑白 + Archivo Black + 硬阴影。 | 宣言类、极具冲击力的视觉 |
| `neo-brutalism` | 厚描边、硬阴影、明黄 accent。 | 创业路演、敢说敢做的调性 |
| `bauhaus` | 几何 + 红黄蓝原色。 | 设计 talk、艺术史/产品美学主题 |
| `swiss-grid` | 瑞士网格 + Helvetica 感 + 12 栏底纹。 | 严肃排版、设计行业 |
| `memphis-pop` | 孟菲斯波普背景点 + 大字标题。 | 年轻、潮流、品牌合作 |

## Cool & dark

| name | description | when to use |
|---|---|---|
| `catppuccin-mocha` | catppuccin 深。 | 开发者内部分享、长时间观看 |
| `dracula` | 经典 Dracula 紫红主色。 | 代码密集的技术分享 |
| `tokyo-night` | Tokyo Night 蓝夜。 | 偏冷技术分享、基础设施 |
| `nord` | 北欧清冷蓝白。 | 基础设施、云产品 |
| `gruvbox-dark` | 温暖复古深色。 | Terminal / vim / *nix 社群 |
| `rose-pine` | 玫瑰松，柔和暗色。 | 设计+开发交界、审美向技术 |
| `arctic-cool` | 蓝/青/石板灰 浅色版。 | 商业分析、金融、冷静理性 |

## Warm & vibrant

| name | description | when to use |
|---|---|---|
| `sunset-warm` | 橘 / 珊瑚 / 琥珀三色渐变。 | 生活方式、奖项颁发、情绪正向 |

## Effect-heavy

| name | description | when to use |
|---|---|---|
| `glassmorphism` | 毛玻璃 + 多色光斑背景。 | Apple 式发布会、产品特性展示 |
| `aurora` | 极光渐变 + blur + saturate。 | 封面 / CTA / 结语页 |
| `rainbow-gradient` | 白底 + 彩虹流动渐变 accent。 | 欢乐向、节日、庆祝页 |
| `blueprint` | 蓝图工程 + 网格底纹 + 蒙太奇字体。 | 系统架构、工程蓝图 |
| `terminal-green` | 绿屏终端 + 等宽 + 发光文字。 | CLI/black-hat/复古朋克 |

## v2 additions

### Light & professional

| name | description | when to use |
|---|---|---|
| `corporate-clean` | 纯白 + 海军蓝 accent + Inter + 保守边框。 | 董事会汇报、B2B 销售、金融保险 |
| `asc-brand` | Ascentium 午夜绿 `#0F1514` + 活力橙 `#FF6600`；配色/字体/版式见下方 **Ascentium brand** 章节。 | **仅当用户明确要求 Ascentium 品牌** — 咨询交付、董事会、对外方案 |
| `inspire-brand` | Inspire 星空蓝 `#10213E` + 创想蓝 `#5DB2E2` + 章节渐变；见 `references/inspire-brand.md`。 | **仅当用户明确要求 Inspire 公司模板时** — 企业培训、内部分享、技术商务 |
| `pitch-deck-vc` | YC 风白底 + 蓝紫渐变 accent + 大留白。 | 融资路演、种子轮、VC meeting |
| `academic-paper` | 论文白 + 衬线正文 + 黑墨 + 蓝链接。 | 学术报告、研究分享、会议论文 |
| `japanese-minimal` | 象牙白 + 朱红 accent + 极大留白 + Noto Serif。 | 品牌升级、匠人故事、禅意叙事 |
| `engineering-whiteprint` | 白底 + 坐标纸网格 + 海军墨线 + 等宽字。 | 系统设计、API 文档、架构白皮书 |

### Bold & editorial

| name | description | when to use |
|---|---|---|
| `magazine-bold` | 奶油底 + 超大 Playfair 衬线 + 橙色 spot。 | 专栏文章、封面故事、品牌月刊 |
| `news-broadcast` | 白底 + 红色竖条 + Oswald 大写 + 硬阴影。 | 突发新闻、发布通稿、数据播报 |
| `midcentury` | 奶油底 + 芥末/青/焦橙 + 锐利几何。 | 设计史、家居美学、复古品牌 |
| `retro-tv` | 暖奶油 + CRT 扫描线 + 琥珀橙 accent。 | 怀旧叙事、八零九零年代主题 |

### Effect-heavy / dramatic

| name | description | when to use |
|---|---|---|
| `cyberpunk-neon` | 纯黑 + 霓虹粉青黄 + 发光 + JetBrains Mono。 | 黑客、地下文化、赛博 talk |
| `vaporwave` | 深紫 + 粉红青蓝渐变 + 晕染光斑。 | 音乐、潮流艺术、A E S T H E T I C |
| `y2k-chrome` | 银铬渐变 + 彩虹 accent + 大圆角 + Space Grotesk。 | 千禧怀旧、时尚品牌、Gen-Z |

---

## Ascentium brand (`asc-brand`)

当用户**明确**提到 **Ascentium 品牌 / 午夜绿 / 活力橙 / Ascentium template** 时使用。默认商务 deck 仍走 `corporate-clean` 或 `pitch-deck-vc`；**不要**在用户未要求时默认套 Ascentium 色板。

**html-ppt 用法：**

```html
<link rel="stylesheet" href="../../assets/fonts.css">
<link rel="stylesheet" href="../../assets/base.css">
<link rel="stylesheet" id="theme-link" href="../../assets/themes/asc-brand.css">
<link rel="stylesheet" href="../../assets/asc-deck-scoped.css">
<body class="deck-host tpl-asc-brand">
  <section class="slide asc-white">…</section>
  <section class="slide asc-midnight">…</section>
</body>
```

Normalize 会在 `tpl-asc-brand` 时自动补全 `asc-brand.css` 与 `asc-deck-scoped.css` 链接；打包时路径会 rewrite 为 `./assets/...` 并随 artifact 分发。

Agent 须 `read_skill_resource` → **`references/themes.md`**（本节）。从 `templates/single-page/` 或 `full-decks/corporate-clean` 复制 `<section class="slide">`，只改文案与 token；**禁止**把 PPTX 的 inch/`add_rect` 逻辑硬译成 absolute 栅格。

### 设计原则（摘要）

| 原则 | 要求 |
|---|---|
| **色叙事** | 午夜绿 = 稳定/专业；活力橙 = 增长/行动。同一语义在全 deck 复用同一 hue。 |
| **80/20** | 60–80% 留白（白或奶油底）；饱和 hero 色 ≤20% 面积。 |
| **一页一 hero** | 最多一个大面积饱和块（午夜绿或橙）；其余用浅 tint、描边、中性灰。 |
| **Ghost cards** | 分组优先 `#FFFFFF` + `#E0E0E0` 细边框，避免厚重色块。 |
| **结构即视觉** | 双栏/网格分区；用 Power Metric 或 Executive Quote 作锚点，而非装饰背景。 |
| **轻分隔** | 侧线或 `#E0E0E0` 分割线；避免「仪表盘式」满屏卡片。 |

### 色板（硬性 — 必须使用下列 hex）

#### 主色

| 名称 | Hex | 用途 |
|---|---|---|
| Midnight Green 午夜绿 | `#0F1514` | Logo、标题、深色底、强调线、页脚 |
| Vibrant Orange 活力橙 | `#FF6600` | 章节页大底、CTA、图表序列首色、关键标注（**≤20% 面积**） |

#### 辅助色

| 名称 | Hex | 用途 |
|---|---|---|
| White 纯白 | `#FFFFFF` | 内容页主背景、深底上的反白字 |
| Slate Gray 板岩灰 | `#4A4A4A` | 副标题、次要说明 |
| Light Blue 浅蓝 | `#BDD5EF` | **装饰块/分区** — 勿用作整页背景 |

#### 功能色

| 角色 | Hex |
|---|---|
| 标题 / 关键信息 | `#0F1514` |
| 正文 | `#333333` |
| 深正文 / 单元格 | `#272C2C` |
| 次要 / 页码 | `#575B5B` |
| 边框 / 分割线 | `#E0E0E0` |
| 表格线（可选） | `#B7B9B9` |

#### 补充色

| 名称 | Hex | 用途 |
|---|---|---|
| Highlight tint 浅橙 | `#FFF0E7` | 左栏 narrative 区、soft highlight（可用 50% 透明叠加） |
| Cream 奶油 | `#F5F2EF` | 长文阅读底、表格 zebra 交替行 |

#### 图表色盘（顺序）

`#FF6611`, `#077069`, `#1877F2`, `#043834` — 首色与品牌橙一致；勿自造离调色。

#### 映射到 `base.css` token（`asc-brand.css`）

| Token | 建议值 |
|---|---|
| `--bg` / `--surface` | `#FFFFFF` |
| `--bg-soft` / `--surface-2` | `#F5F2EF` |
| `--text-1` | `#0F1514` |
| `--text-2` | `#333333` |
| `--text-3` | `#575B5B` |
| `--border` | `#E0E0E0` |
| `--accent` | `#FF6600` |
| `--accent-2` | `#0F1514` |
| `--font-sans` / `--font-display` | `'Poppins','Noto Sans SC',Inter,sans-serif` |

### 页面背景变体（slide class 语义）

| 变体 | 背景 | 何时用 |
|---|---|---|
| `asc-white`（默认） | `#FFFFFF` | 图表、表格、高密度数据 |
| `asc-cream` | `#F5F2EF` | 长文、 editorial 阅读 |
| `asc-midnight` | `#0F1514` | 封面金句、强 statement、大图页 |
| `asc-orange` | `#FF6600` | 章节分隔、过渡、结语 |
| `asc-split` | 左 40% `#FFF0E7` + 右 60% `#FFFFFF` | 左 narrative / 右 chart（40/60 双 tone） |

深底/橙底页：标题与副标题用 `#FFFFFF`；Logo 用反白版。

### 字体（参考范围 — 用 semantic class，禁止 inline pt）

| 层级 | 参考（16:9） | 字重 | 颜色 |
|---|---|---|---|
| 封面主标题 | clamp(2.5rem, 5vw, 3.375rem) | 700 | `#0F1514` 或白底变体 |
| 封面副标题 | clamp(1.1rem, 2.2vw, 1.5rem) | 400 | `#575B5B` / 白 |
| 章节标题 | clamp(2rem, 4vw, 2.75rem) | 600 | `#FFFFFF` on 橙/深底 |
| 内容页标题 | clamp(1.35rem, 2.5vw, 1.75rem) | 600 | `#0F1514` |
| 正文 | clamp(0.875rem, 1.4vw, 1.05rem) | 400 | `#272C2C`，行高 1.45–1.6 |
| 说明 / 脚注 | clamp(0.7rem, 1.1vw, 0.85rem) | 400 | `#575B5B` |

- **英文：** Poppins（fallback Arial）
- **中文：** Noto Sans SC（fallback Microsoft YaHei / PingFang）
- 对比度须达 WCAG AA（午夜绿 on 白 ≈ 18.5:1）

### 表格

| 属性 | 规范 |
|---|---|
| 表头底 | `#FF6611`，字 `#FFFFFF`，Semi-Bold |
| 表体 | `#272C2C`，Regular |
| 斑马纹（可选） | `#FFFFFF` / `#F5F2EF` |
| 边框 | `#B7B9B9` 1px；优先**仅水平线**，现代简洁 |

### 间距与 16:9 安全区

- 画幅：**16:9**（与 html-ppt 一致，1920×1080 逻辑画布）
- 内容安全区：距四边约 **5%**；右上品牌角标区域勿堆正文
- 主块间距：**0.3–0.5** 相对 slide 高度（约 24–40px @1080p）
- Bullet 段后距：**4–6px** 量级，勿 ≥12px
- 卡片内边距：约 **16–20px**

### Don't（常见错误）

- 不要每页同一版式；不要正文居中（仅标题可居中）
- 不要字号对比不足（封面 vs 正文须明显层级）
- 不要离调色（用户未指定色时默认 Ascentium 色板）
- 不要纯文字页 — 须有 chart、metric、**Lucide 图标**（`<i data-lucide="…">`，见 [icons.md](icons.md)）或结构分区；**禁止 emoji**
- 不要标题下 accent 线 — 用留白或背景区分
- 不要 `#BDD5EF` 作整页背景
- 不要一页 ≥2 种装饰填充色且装饰总面积 >50%
- 不要用页面背景色再填卡片（cream 页上勿再用 `#F5F2EF` 卡片）

---

## How to apply

```html
<link rel="stylesheet" id="theme-link" href="../assets/themes/aurora.css">
```

Or enable `T`-cycling by listing themes on the body:

```html
<body data-themes="minimal-white,aurora,catppuccin-mocha" data-theme-base="../assets/themes/">
```

## How to extend

Copy an existing theme, rename it, and override only the variables you want to
change. Keep each theme under ~200 lines. Prefer adjusting tokens to adding
new selectors.
