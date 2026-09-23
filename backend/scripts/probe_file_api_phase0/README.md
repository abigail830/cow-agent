# Phase 0 File API 探针

纯测试脚本，用于探测国产模型（百炼 / DeepSeek）的文档与文件 API 能力，**不修改** chat attachments 生产代码。

## 运行

```bash
cd backend
.venv/bin/python scripts/probe_file_api_phase0.py --output data/probe_file_api_phase0_report.json
```

可选：`--skip-dashscope` / `--skip-deepseek`

单元测试（无 live API）：

```bash
.venv/bin/pytest tests/test_file_api_probe_phase0.py -v
```

## 探针项

| ID | 说明 |
|----|------|
| `dashscope.upload_*` | 百炼 `POST /v1/files` `purpose=file-extract` |
| `dashscope.chat_*_fileid_*` | system `fileid://{id}` + chat |
| `dashscope.chat_*_pdf_file_data` | OpenAI 兼容 `type:file` + `file.file_data` |
| `deepseek.upload_*` | DeepSeek Files API（仅图片） |
| `deepseek.chat_*` | file_id / file_data 引用 |

## 2026-09-23 实测结论（供方案讨论）

环境：`.env` 中已配置 `DASHSCOPE_API_KEY`、`DEEPSEEK_API_KEY`。

### 百炼 Files API（upload）

- MD / PDF `purpose=file-extract`：**上传成功**，`status=processed` 可 poll 到。
- 长 MD 探针文件 **>32k 字符**（用于对比当前 inline 截断）。

### qwen-long（官方 file-extract consumer）

- `fileid://` + **长 MD**：**PASS**（准确返回 sentinel）
- `fileid://` + **短 MD**：**PASS**

### qwen3.7-plus

- `fileid://` + MD（长/短）：**FAIL**（模型回复无法访问文件 / 截断 token）
- `fileid://` + PDF（file-extract 上传）：**PASS**
- `PDF file_data`（OpenAI file part）：**FAIL** — `The current model does not support PDF file input`

### qwen3.8-max

- `fileid://` + MD（长/短）：**FAIL**（无法访问文件或 hallucinate file_id 后缀）
- `fileid://` + PDF：**PASS**
- `PDF file_data`（`data:application/pdf;base64,...` + `filename`）：**PASS**

### deepseek-flash

- PNG upload + `file_id` chat：**PASS**
- PDF upload：**拒绝**（仅 webp/png/jpeg/gif）
- PDF `file_data`（nested 或 flat）：**FAIL**（不支持 PDF 输入）

### 方案含义（草案）

1. **md/txt 去截断**：qwen3.7/3.8 **不能**依赖 `fileid://`；需另选路径（如转 PDF → qwen3.8 `file_data` / fileid PDF，或专用 qwen-long 路由，或 extract+inline 仅小文件）。
2. **PDF**：qwen3.8 优先 **`file_data` inject**（无需 provider upload）；qwen3.7 可用 **`fileid://` + file-extract upload**。
3. **DeepSeek**：文档 v1 仍 **不支持**；图片可 Files API `file_id` 或继续 inline vision。
4. 当前 `materialize.py` 的 `Content.from_data(pdf)` **不符合** qwen3.8 官方 wire format，需改为 `type:file` + `file.file_data` + `filename`。

完整 JSON 见 `backend/data/probe_file_api_phase0_report.json`（运行后生成）。
