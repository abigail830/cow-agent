# OKF platform E2B templates

Custom E2B sandbox images for agents that need real Linux tooling (LibreOffice, Node, Python).

| Template alias | Purpose | Used by |
|----------------|---------|---------|
| `okf-content-studio` | docx / pptx / html-slides skill toolchain | `content-studio` (default); reuse for any document agent |

## Build (once per E2B team / after Dockerfile changes)

```bash
cd agent-backend
# E2B_API_KEY must be set (same as runtime)
npm run e2b:build-content-studio-template
```

This publishes template alias **`okf-content-studio`** (override with `E2B_CONTENT_STUDIO_TEMPLATE`).

## Runtime

Any catalog agent:

```yaml
sandbox:
  provider: e2b
  templateId: okf-content-studio:1.14   # or bare okf-content-studio (tag resolved in code)
  cwd: /home/user/content-studio
```

Platform lifecycle (lazy acquire, pause, timeout kill) lives in `src/sandboxes/` — templates only define the VM image.

## Adding a new template

1. Add `e2b-templates/<name>/template.ts` + `build.ts`
2. Register npm script `e2b:build-<name>-template`
3. Point agent `sandbox.templateId` at the published alias
