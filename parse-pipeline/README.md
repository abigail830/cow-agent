# parse-pipeline

Independent file parse service for agent-platform. Async jobs, abstract 8-stage lifecycle, local text/sheet parsers, Document Mind for PDF/Office.

**Scope of this package:** standalone module only. Platform backend integration (`platform/parse_pipeline` client) is a separate step.

## Quick start

```bash
cd parse-pipeline
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env
pytest
parse-pipeline serve
```

## API

- `POST /v1/jobs` — submit async job (202)
- `GET /v1/jobs/{job_id}` — job status + stages (in-memory store by default)
- `POST /v1/jobs/{job_id}/cancel` — best-effort cancel
- `GET /health`

Auth:

```http
Authorization: Bearer <psk_parse_...>
X-Parse-Caller-Id: agent-platform
```

## CLI (GHA entrypoint)

```bash
parse-pipeline run-job --job-file /path/to/job.json
```

## GitHub Actions

See **[docs/github-actions.md](docs/github-actions.md)** for secrets, manual `workflow_dispatch`, and PDF via presigned URL.

Workflows live at repo root:

- `.github/workflows/parse-pipeline-ci.yml` — pytest on PR
- `.github/workflows/parse-pipeline-run-job.yml` — manual parse job

## Pipelines

| pipeline_id | Parser |
|-------------|--------|
| `text_standard` | local text |
| `sheet_standard` | local sheet (CSV/XLSX); fallback Document Mind on failure |
| `pdf_standard` | Document Mind (VLM default) |
| `office_standard` | Document Mind |
| `document_mind_generic` | Document Mind |

## Job store

- `JOB_STORE=memory` (default): in-process state for `GET /v1/jobs` during service lifetime
- `JOB_STORE=postgres`: optional durable store (migration scaffold planned)

## Document Mind

Async API flow (阿里云文档解析大模型版):

1. `SubmitDocParserJobAdvance` — submit local file (`output_format` → API `OutputFormat`)
2. `QueryDocParserStatus` — poll until `Status=success|failed` (`parse_wait` emits stage updates each poll)
3. `GetDocParserResult` — paginated layout/markdown collect

**OutputFormat** (job `options.document_mind.output_formats`, default `["markdown", "visualLayoutInfo"]`):

| Value | Effect |
|-------|--------|
| `markdown` | Markdown content in result |
| `visualLayoutInfo` | Page/layout info for `pageindex.json` |

Set in `.env`:

```env
DOCUMENT_MIND_ACCESS_KEY_ID=...
DOCUMENT_MIND_ACCESS_KEY_SECRET=...
DOCUMENT_MIND_LLM_ENHANCEMENT=true
DOCUMENT_MIND_ENHANCEMENT_MODE=VLM
```

## Local test without HTTP

```bash
parse-pipeline run-job --job-file tests/fixtures/job_text_example.json
```

See `tests/` for file:// StorageSpec examples.
