# parse-pipeline on GitHub Actions

Run parse jobs via GHA **without** the HTTP microservice. Entrypoint: `parse-pipeline run-job`.

## Workflows

| Workflow | File | Trigger |
|----------|------|---------|
| **CI** | [`.github/workflows/parse-pipeline-ci.yml`](../../.github/workflows/parse-pipeline-ci.yml) | push/PR touching `parse-pipeline/` |
| **Run job** | [`.github/workflows/parse-pipeline-run-job.yml`](../../.github/workflows/parse-pipeline-run-job.yml) | Manual `workflow_dispatch` |

## One-time GitHub setup

### 1. Push workflows

Ensure these files exist on your default branch:

- `.github/workflows/parse-pipeline-ci.yml`
- `.github/workflows/parse-pipeline-run-job.yml`

### 2. Repository Secrets

Open **Settings → Secrets and variables → Actions → New repository secret**:

| Secret | Required | Purpose |
|--------|----------|---------|
| `DOCUMENT_MIND_ACCESS_KEY_ID` | For PDF/Office/DM pipelines | Alibaba Cloud AK |
| `DOCUMENT_MIND_ACCESS_KEY_SECRET` | For PDF/Office/DM pipelines | Alibaba Cloud SK |
| `PARSE_WEBHOOK_URL` | Optional | Platform callback URL (when integrated) |
| `PARSE_WEBHOOK_SECRET` | Optional | HMAC secret for webhooks |

Text/sheet jobs using repo fixtures **do not** need Document Mind secrets.

### 3. Run a test job (text, no DM cost)

1. **Actions** tab → **parse-pipeline run job** → **Run workflow**
2. Inputs: leave defaults (`text_standard` + `parse-pipeline/tests/fixtures/sample.md`) or set `source_url` for remote files.
3. Run → download artifact **parse-pipeline-artifacts-*** → `content.md`, `meta.json`

### 4. Run PDF via Document Mind

**Option A — file in repo** (small test PDF committed to repo):

- `pipeline_id`: `pdf_standard`
- `source_repo_path`: `path/to/test.pdf`

**Option B — presigned URL** (recommended for real files):

- `pipeline_id`: `pdf_standard`
- `source_url`: `https://...presigned-get...` (overrides `source_repo_path`)
- `filename`: `report.pdf` (if URL has no extension)

Timeout is 120 minutes (DM VLM can be slow).

### 5. Webhook callback (optional)

When platform is ready, set secrets:

- `PARSE_WEBHOOK_URL` = e.g. `https://your-api/internal/parse/v1/webhook`
- `PARSE_WEBHOOK_SECRET` = shared `whsec_...`

The runner emits `stage.updated` during `parse_wait` and `job.completed` on success.

## Local equivalent

```bash
cd parse-pipeline
python scripts/gha_build_job.py \
  --pipeline-id text_standard \
  --source-path tests/fixtures/sample.md \
  --out-dir /tmp/out \
  --output /tmp/job.json
parse-pipeline run-job --job-file /tmp/job.json --caller-id local
```

## Document Mind OutputFormat default

Jobs use `options.document_mind.output_formats`: **`["markdown", "visualLayoutInfo"]`** unless overridden in job JSON.
