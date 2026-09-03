# Required Documents — Compose

## 本质

`required_documents`（或类似章节）的内容不是 static 块，也不是 platform 自动推导的——它由 **category catalog 选型 + body 文件拼接** 决定，agent 负责读 catalog、判断选型、读必要的 body 文件、patch 到 draft。

Template 通过 `sections[].knowledge` 声明：用哪套 catalog（`category`）、body 文件在哪（`body_root`）、选型依据哪个 fee_section（`source_section`）。

---

## 不变量（边界）

这些是约束，执行路径 AI 自行判断：

**enable ≠ 内容已就绪**
`enable_proposal_draft_section` 只切可见性；内容是否完整取决于是否已 compose。

**catalog 规则不进 proposal**
catalog 的 `agent_notes`、`include_when`、body 文件里残留的 HTML 注释——这些是 AI 用的，不是客户看的，**一个字不能出现在 `content` 里**。

**edit_state 优先**
若 `composition.edit_state.content === "user"`，用户已手改文案，不能 silent 覆盖。需要 refresh 时先确认。

**选型来源是 fee tables，不是对话记忆**
从 draft `solution_and_fees`（或 template 指定的 `source_section`）的 fee rows 读 package/service 信息，不凭记忆猜。

**空 fee tables → placeholder，不是全量正文**
选型未定时贴全部 KYC 文件是错的；应 patch 一句占位文案，等服务确定后再 compose。

**只读 catalog 的 `content_file`，不要拆条猜路径**
body 以 catalog 块为单位（如 `Individual KYC Requirements.md` 一整块含多条清单），路径为 `{body_root}/{content_file}`。禁止把块内条目拆成 `passport.md`、`proof-of-address.md` 等臆造文件。

---

## 选型逻辑（category catalog 定义）

每个 body block 在 catalog 里有触发规则：

- **include_when** / **exclude_when**：按 fee rows 的 service_name、description、package 名匹配；exclude 优先于 include
- **append_when_any**：依赖其他 block 是否被选中（常用于结尾固定条款）
- **requires_structure**：需要 client 结构信息（如公司层级、股东类型）才能 compose 该 block；缺时最小问一个问题，不要把整个 compose 挂起

选中的 blocks 按 catalog `order` 排序后拼接，正文之间空一行。

---

## Draft 携带的状态（可选但有用）

`composition` 字段作为 agent 的工作记忆，记录上次 compose 的状态，方便 refresh 判断：

- `status`：`ready` / `pending_packages` / `pending_structure` / `stale`
- `block_ids`：上次选中的 block list
- `source_snapshot`：compose 时的 fee tables 快照（package_ids, skus）
- `edit_state.content`：`agent`（compose 写入）或 `user`（手改过）

这些字段不是 platform 强制读取的，而是 agent 留给自己下次用的。

---

## Refresh 时机

fee tables 变化（add/remove package 或 service）后，若 `required_documents` 已 enabled，`source_snapshot` 会 stale。此时：

- 若 `edit_state.content !== "user"`：可直接 recompose
- 若用户手改过：告知有新服务加入，确认是否要更新 required docs

判断是否需要 refresh 的依据是 **snapshot 与当前 fee tables 的差异**，不是"每次 add 就强制触发"。

---

## 新 category 扩展

增加对应的 `references/required-docs-{category}-catalog.md` + `peripheral/required-docs/{category}/` body 文件。catalog 表结构与 Harneys 保持一致，本文件无需改动。
