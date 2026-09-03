# Inspire 品牌主题 — 使用指南

当用户**明确**提到 **Inspire 主题 / Inspire 模板 / 公司模板 / 星空蓝 / 创想蓝 / 企业培训 PPT** 时，使用本指南与 `assets/inspire/` 下的品牌资源。

**必须先读：** `read_skill_resource` → **`references/inspire-brand.md`**（本文件 — 色板、字体、页型、Do/Don't 的唯一规范来源）。

**必须标记 opt-in：** 在 `<body class="tpl-inspire-brand">` 或 `<html data-inspire-brand="true">` 上声明；未标记时渲染器会剥离 Inspire CSS/Logo，避免误套品牌。

---

## 资源清单

| 路径 | 用途 |
|---|---|
| `references/inspire-brand.md` | 品牌设计规范（Agent 必读） |
| `assets/inspire-deck-scoped.css` | **Chrome + 页型布局**（Logo/Copyright 固定锚点、`.slide-main`）— Inspire opt-in 时必须链入 |
| `templates/full-decks/inspire-brand/` | 完整 deck 起点（`index.html` + `style.css` → 引用 scoped CSS） |
| `assets/themes/inspire-brand.css` | 主题 token 覆盖（**仅色板/字体**，不含 chrome 定位） |
| `assets/inspire/logo-white.png` | 反白 Logo — 封面 / 章节页 / 结束页（深色或渐变背景） |
| `assets/inspire/logo.png` | 彩色 Logo — 内容页页脚、白底场景 |
| `assets/inspire/background.jpg` | 可选背景图（1024×580），封面或章节页叠加 dark overlay |
| `assets/inspire/*.pptx` | 版式参考（HTML 中复刻，不嵌入 artifact） |

渲染时 `../../assets/inspire/...` 会自动改写为 `./assets/inspire/...` 并随 artifact 打包。

---

## 推荐起点

| 场景 | 起点 |
|---|---|
| 完整企业培训 / 内部分享 deck | **`templates/full-decks/inspire-brand/`** — 复制整包 |
| 已有 HTML、只补 Inspire 品牌 | `<head>` 链 **`inspire-brand.css` + `inspire-deck-scoped.css`**，`<body class="tpl-inspire-brand">` |
| 单页封面 / 章节 / 结束 | `templates/single-page/cover.html` 等 + Inspire 双 CSS |

**不要**从零手写 `position:absolute` 栅格；从 full-deck 或 single-page 模板复制 `<section class="slide">` 再替换文案。

---

## 色板（硬性约束 — 必须使用这些 hex）

### 主色

| 名称 | Hex | 用途 |
|---|---|---|
| 星空蓝 Starry Blues | `#10213E` | 主品牌色、正文主色、关键标题、主按钮 |
| 创想蓝 Creative Blue | `#5DB2E2` | 强调色 — bullet、编号、标签、高亮数据（**全 deck 面积约 5–10%**） |
| 科技灰 Tech Gray | `#F5F5F6` | 内容区浅底、卡片背景 |

### 辅助色（同一页最多 2 种）

| 名称 | Hex | 用途 |
|---|---|---|
| 白 | `#FFFFFF` | 内容页主背景 |
| 紫水晶 Amethyst | `#625D9C` | 图表辅助、创新类标识 |
| 冬青绿 Myrtle Deep Green | `#00524C` | 成功状态、正向数据 |
| 蔚蓝霜 Cerulean Frost | `#6FB1C8` | 次要信息、轻量背景 |
| 樱花粉 Sakura Pink | `#F5ACB8` | 温馨提示、人文关怀 |

### 功能色

| 角色 | Hex |
|---|---|
| 正文主色 | `#10213E`（不用纯黑 `#000`） |
| 次要文字 | `#64748B` |
| 占位 / 脚注 | `#94A3B8` |
| 边框 / 分割线 | `#E2E8F0` |
| 成功 | `#10B981` |
| 警告 | `#F59E0B` |
| 危险 | `#EF4444` |

### 渐变（仅 Cover / Section 页）

| 名称 | 值 | 用途 |
|---|---|---|
| 章节渐变 | `linear-gradient(135deg, #1B2B47 0%, #4A9FD8 100%)` | 封面、章节分隔、结束页 |
| 图片叠加 | `linear-gradient(to bottom, rgba(27,43,71,0.8), rgba(27,43,71,0.4))` | 背景图上的文字可读层 |

图表主色盘：`#1B2B47`, `#4A9FD8`, `#7B6B9E`, `#2F5B56`, `#8FBCD4`。

---

## 字体（硬性约束 + 参考范围）

### 字体族

| 场景 | 首选 | Fallback（skill 默认） |
|---|---|---|
| 中文标题 / 正文 | MiSans SemiBold / Regular | **Noto Sans SC** |
| 英文标题 / 正文 | MiSans SemiBold / Regular | **Inter** |
| 系统 fallback | — | Microsoft YaHei, Arial |

`inspire-brand.css` 与 full-deck `style.css` 已配置 Noto Sans SC + Inter。**不要**在 slide 上写 `font-size: 48pt` 等固定 pt — 用 semantic class + CSS 变量。

### 字号层级（参考范围，非硬编码）

用 `base.css` 的 `.h1` `.h2` `.h3` `.lede` `.dim2` 和 full-deck 的 `.inspire-*` class，让 scoped CSS 控制大小。若需微调，保持在下列**相对关系**内：

| 层级 | 语义 class | 参考范围（16:9 slide） | 字重 | 颜色 |
|---|---|---|---|---|
| 封面主标题 | `.h1` on `.inspire-cover` | **clamp(2rem, 4.5vw, 3rem)** | 600–700 | `#FFFFFF` |
| 封面副标题 | `.lede` on cover | **clamp(1rem, 2vw, 1.35rem)** | 400–500 | `rgba(255,255,255,0.85)` |
| 章节大标题 | `.h1` on `.inspire-section` | **clamp(1.75rem, 3.5vw, 2.5rem)** | 600–700 | `#FFFFFF` |
| 章节装饰序号 | `.inspire-section-num` | **clamp(4rem, 12vw, 6rem)** | 700 | `#4A9FD8` @ 15% opacity |
| 内容页标题 | `.inspire-content-title` / `.h2` | **clamp(1.35rem, 2.5vw, 1.75rem)** | 600 | `#10213E` |
| 三级标题 | `.h3` | **clamp(1.1rem, 2vw, 1.35rem)** | 500–600 | `#1B2B47` |
| 正文 / bullet | body text | **clamp(15px, 1rem, 18px)** | 400 | `#10213E`，行高 1.45–1.6 |
| 说明 / caption | `.dim2` | **clamp(0.75rem, 1.2vw, 0.9rem)** | 400 | `#64748B` |
| 标签 / kicker | `.kicker` / `.inspire-part` | **clamp(0.7rem, 1vw, 0.85rem)** | 600 | `#4A9FD8`，大写 + letter-spacing |
| 页脚 / copyright | `.inspire-footer` | **10–13px** | 400 | `#64748B` 或 white @ 55–65% |

**原则：** 一页内最多 3 级字号对比；长 bullet 列表用较小正文档；**禁止** inline `style="font-size:XXpt"` 或 **< 14px**；四列布局每栏最多 2 条 bullet，否则拆页。

---

## Chrome 契约（固定层 + Stage 层 — Agent 必须遵守）

每页 slide 由 **两层** 组成，不要把 Logo / Copyright 写进正文流。

### 固定 Chrome（由 `inspire-deck-scoped.css` 定位，勿 inline 改位置）

| 元素 | 位置 | DOM / class |
|---|---|---|
| Logo | **右上** `top:40px; right:60px` | `<img class="inspire-logo">` — 深底用 `logo-white.png`，白底内容页也可用右上彩色 logo |
| Copyright | **左下**（footer 行内最左） | `<span class="inspire-copyright">© Inspire Group</span>` 放在 `.deck-footer.inspire-footer` 内 |
| 页码 / 副标 | footer 行右侧 | `.slide-number` 或 `.dim2` |

Footer 容器：

```html
<div class="deck-footer inspire-footer">
  <span class="inspire-copyright">© Inspire Group</span>
  <span class="dim2">可选副标</span>
  <span class="slide-number" data-current="3" data-total="8"></span>
</div>
```

深底页（Cover / Section / End）用 `.inspire-footer-light`。

### Stage 层（正文 — 垂直居中于 chrome 之间）

内容页 / 议程 / 案例 / 互动页：**标题 + 主视觉** 必须包在 `.slide-main` 内：

```html
<section class="slide inspire-content" data-title="要点">
  <img class="inspire-logo" src="../../assets/inspire/logo.png" alt="Inspire">
  <div class="slide-main">
    <div class="slide-header">
      <p class="kicker">SMART PROPOSAL</p>
      <h2 class="inspire-content-title h2">页面标题</h2>
      <p class="lede">一句 scope / 副标题</p>
    </div>
    <!-- 主视觉：bullets / grid / 流程 — 从 templates/single-page/ 复制 -->
    <ul class="inspire-bullets mt-m">…</ul>
  </div>
  <div class="deck-footer inspire-footer">
    <span class="inspire-copyright">© Inspire Group</span>
    <span class="slide-number" data-current="3" data-total="8"></span>
  </div>
</section>
```

| 层 | class | 职责 |
|---|---|---|
| Chrome | `.inspire-logo`, `.deck-footer.inspire-footer` | 固定四角，**不参与** flex 流 |
| Stage | `.slide-main` | `flex:1` + 垂直居中，避开 logo/footer 安全区 |
| Header band | `.slide-header`（可选） | 标题区，放在 `.slide-main` 顶部 |
| Takeaway | `.slide-takeaway`（可选） | 页内一句结论，放在 `.slide-main` 底部 |

Cover / Section / End 整页居中，**不需要** `.slide-main`。

### `<head>` 最低配置（Inspire opt-in）

```html
<link rel="stylesheet" href="../../assets/fonts.css">
<link rel="stylesheet" href="../../assets/base.css">
<link rel="stylesheet" href="../../assets/themes/inspire-brand.css">
<link rel="stylesheet" href="../../assets/inspire-deck-scoped.css">
```

**禁止：** 只链 `inspire-brand.css` 而不链 `inspire-deck-scoped.css`；把 Copyright 当作普通 `<p>` 放在卡片下方。

---

## 布局（硬性约束）

| 规则 | 值 |
|---|---|
| 画幅 | 16:9 |
| slide 内边距 | 约 **48px 上下 · 60px 左右**（full-deck CSS 已定义，勿覆盖） |
| 安全区 | 距边缘 ≥ **40px** 不放关键内容 |
| 正文最大宽度 | ≤ **80%** slide 宽度 |
| 对齐 | 正文左对齐；Cover / Section 标题可居中 |

---

## 页型与 HTML class

| 页型 | class | 结构要点 |
|---|---|---|
| 封面 | `.inspire-cover` | 渐变或 background.jpg + overlay；居中标题；反白 Logo 右上 |
| 议程 | `.inspire-agenda` | 左标题 + 右 01–05 编号列表（编号 `#5DB2E2`） |
| 章节分隔 | `.inspire-section` | PART 标签 + 大标题 + 装饰序号（低 opacity） |
| 标准内容 | `.inspire-content` | 标题下 2px `#1B2B47` 边框；≤5 bullet，marker `#5DB2E2` |
| 案例 | `.inspire-case` | PAIN / SOLUTION / RESULT 三区；结果区左绿边 `#00524C` |
| 互动 | `.inspire-interaction` | 暖黄 badge + 左 `#F59E0B` 4px 边框 |
| 结束 | `.inspire-end` | 同 cover 渐变；感谢语 + Logo |

---

## 组件规范

### 卡片

- 背景 `#FFFFFF`，边框 `1px solid #E2E8F0`，圆角 `8px`
- 阴影 `0 2px 8px rgba(27,43,71,0.08)`，内边距约 `20px`

### Callout

| 类型 | 左边框 | 背景 |
|---|---|---|
| info | `4px #4A9FD8` | `#F0F9FF` |
| success | `4px #00524C` | `#F0FDF4` |
| warning | `4px #F59E0B` | `#FFFBEB` |

### Badge 分类色

| 类型 | 背景 | 文字 |
|---|---|---|
| tech | `#E8F4FD` | `#4A9FD8` |
| business | `#F0F9F6` | `#00524C` |
| warning | `#FFF9E6` | `#F59E0B` |

---

## Do / Don't

### Do

- Cover 和 Section **才**用星空蓝→创想蓝渐变
- 内容页背景保持 **White** 或 **Tech Gray `#F5F5F6`**
- 创想蓝**谨慎**点缀 — bullet、编号、小标签，不大面积铺色
- 文本用 `#10213E` 替代纯黑，营造温暖专业感
- 图片上叠字时**必须**加 dark overlay
- 从 **`templates/full-decks/inspire-brand/`** 复制结构，只改文案
- 演讲者提示、沟通重点 → **仅** `<div class="notes">`

### Don't

- **不要**硬编码 pt 字号（如 `48pt`、`28pt`）— 用 semantic class
- **不要**从零手写 absolute 布局或侧边栏
- **不要**在 slide 可见区域写 Agent 说明（`Inspire Theme`、`本页沟通重点` 等）
- **不要**在图片上直接叠字而无 overlay
- **不要**同一页超过 **3 种主色**（星空蓝、创想蓝、科技灰除外）
- **不要**同一页超过 **2 种辅助色**
- **不要**用中灰 / 浅灰当正文主色（可读性不足）
- **不要**正文宽度超过 80%

---

## HTML 引用示例

### 封面（渐变 + 反白 Logo）

```html
<section class="slide inspire-cover" data-title="Cover">
  <img class="inspire-logo" src="../../assets/inspire/logo-white.png" alt="Inspire">
  <div class="inspire-cover-inner tc center">
    <h1 class="h1">培训主题标题</h1>
    <p class="lede">副标题 · 日期</p>
  </div>
  <div class="deck-footer inspire-footer-light">
    <span class="inspire-copyright">© Inspire Group</span>
    <span class="slide-number" data-current="1" data-total="8"></span>
  </div>
</section>
```

### 章节分隔页

```html
<section class="slide inspire-section" data-title="Section 01">
  <p class="inspire-part">PART 01</p>
  <h1 class="h1">章节标题</h1>
  <p class="lede">预计 15 分钟 · 主题 A / 主题 B</p>
  <span class="inspire-section-num">01</span>
</section>
```

### 内容页（标题栏 + bullet + slide-main）

```html
<section class="slide inspire-content" data-title="要点">
  <img class="inspire-logo" src="../../assets/inspire/logo.png" alt="Inspire">
  <div class="slide-main">
    <h2 class="inspire-content-title h2">页面标题</h2>
    <ul class="inspire-bullets mt-l">
      <li>第一条要点</li>
      <li>第二条要点</li>
    </ul>
  </div>
  <div class="deck-footer inspire-footer">
    <span class="inspire-copyright">© Inspire Group</span>
    <img src="../../assets/inspire/logo.png" alt="" class="inspire-logo-sm">
  </div>
</section>
```

---

## 工作流

1. `load_skill` → `html-ppt`
2. `read_skill_resource` → **`references/inspire-brand.md`**
3. 复制 **`templates/full-decks/inspire-brand/`** 整包（含 scoped CSS）
4. 设置 `<body class="tpl-inspire-brand">`
5. 替换 demo 文案，**保持** `.inspire-*` structural class，**不改** layout CSS
6. `render_html_ppt`（`source` = 完整 HTML，`title` = 制品标题）

## 硬性规范（Agent 必须遵守）

| 必须 | 实现 |
|---|---|
| Opt-in | `<body class="tpl-inspire-brand">` 或 `data-inspire-brand="true"` |
| Scoped CSS | `<head>` 必须链 **`inspire-deck-scoped.css`**（或复制 full-deck） |
| Logo | 每页 `.inspire-logo` — `logo-white.png`（深底）或 `logo.png`（白底） |
| Copyright | 每页 `.deck-footer.inspire-footer` 内 `.inspire-copyright` — **左下固定** |
| Stage | 内容页正文包在 **`.slide-main`** 内 |
| 字号 | 用 semantic class + full-deck CSS，**禁止** inline pt |
| 演讲者内容 | 仅 `<div class="notes">`，不可出现在可见 DOM |

平台在 `render_html_ppt` 时会自动剥离常见 Agent 说明文字，并补全缺失的 Logo / Copyright（仅 opt-in deck）。
