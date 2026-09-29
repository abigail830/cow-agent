import { attachmentParsedFigureUrl, hubParsedFigureUrl } from './documentUrls'

const FIGURE_REF_PREFIX = 'figure:'
const FIGURE_MARKDOWN_RE = /!\[([^\]]*)\]\(([^)]+)\)/g
const FIGURE_HTML_SRC_RE = /(\bsrc\s*=\s*["'])figure:(f\d+)\1/gi
const HASH_IMAGE_STEM_RE = /^[a-f0-9]{32,64}$/i
const IMAGE_EXTENSIONS = new Set(['jpeg', 'jpg', 'png', 'gif', 'webp'])

export type ParsedFigureMetaEntry = {
  id: string
  line?: number
  sha256?: string
  filename?: string
  alt?: string
}

export type ParsedFigureMeta = {
  figures?: ParsedFigureMetaEntry[]
}

function hashImageStem(value: string | undefined): string | null {
  if (!value) return null
  let candidate = value.trim()
  if (!candidate) return null
  if (candidate.includes('?')) candidate = candidate.split('?')[0] ?? candidate
  if (candidate.includes('/')) candidate = candidate.split('/').pop() ?? candidate
  if (candidate.includes('.')) {
    const ext = candidate.split('.').pop()?.toLowerCase()
    if (!ext || !IMAGE_EXTENSIONS.has(ext)) return null
    candidate = candidate.slice(0, -(ext.length + 1))
  }
  return HASH_IMAGE_STEM_RE.test(candidate) ? candidate : null
}

function figureIdForLine(meta: ParsedFigureMeta | undefined, lineNo: number): string | undefined {
  for (const fig of meta?.figures ?? []) {
    if (fig.line === lineNo && fig.id) return fig.id
  }
  return undefined
}

function resolveFigureIdFromMeta(stem: string, meta: ParsedFigureMeta | undefined): string | undefined {
  const lower = stem.toLowerCase()
  for (const fig of meta?.figures ?? []) {
    if (!fig.id) continue
    const sha = fig.sha256?.toLowerCase() ?? ''
    const filename = fig.filename?.toLowerCase() ?? ''
    if (sha.startsWith(lower) || filename.includes(lower) || filename.startsWith(lower)) {
      return fig.id
    }
  }
  return undefined
}

function rewriteMarkdownFigureRefs(
  content: string,
  figureUrl: (figureId: string) => string,
  meta?: ParsedFigureMeta,
): string {
  const lines = content.split('\n')
  const output: string[] = []

  for (let index = 0; index < lines.length; index += 1) {
    const lineNo = index + 1
    const line = lines[index] ?? ''
    output.push(
      line.replace(FIGURE_MARKDOWN_RE, (match, alt: string, rawUrl: string) => {
        const url = rawUrl.trim()
        if (!url || url.startsWith('data:')) return match

        if (url.startsWith(FIGURE_REF_PREFIX)) {
          const figureId = url.slice(FIGURE_REF_PREFIX.length).trim()
          return figureId ? `![${alt}](${figureUrl(figureId)})` : match
        }

        const urlStem = hashImageStem(url)
        const altStem = hashImageStem(alt)
        const stem = urlStem ?? altStem
        if (stem) {
          const figureId =
            figureIdForLine(meta, lineNo) ?? resolveFigureIdFromMeta(stem, meta) ?? stem
          return `![${alt}](${figureUrl(figureId)})`
        }

        return match
      }),
    )
  }

  return output.join('\n')
}

export function resolveParsedFigureSrc(
  src: string | undefined,
  chatId: string,
  attachmentId: string,
  meta?: ParsedFigureMeta,
): string | undefined {
  if (!src) return src
  if (src.startsWith(FIGURE_REF_PREFIX)) {
    const figureId = src.slice(FIGURE_REF_PREFIX.length).trim()
    if (!figureId) return src
    return attachmentParsedFigureUrl(chatId, attachmentId, figureId)
  }
  const stem = hashImageStem(src)
  if (stem) {
    const figureId = resolveFigureIdFromMeta(stem, meta) ?? stem
    return attachmentParsedFigureUrl(chatId, attachmentId, figureId)
  }
  return src
}

/** Rewrite figure:fN and Document Mind hash image refs to browser-fetchable URLs. */
export function rewriteParsedFigureRefs(
  content: string,
  chatId: string,
  attachmentId: string,
  meta?: ParsedFigureMeta,
): string {
  const figureUrl = (figureId: string) => attachmentParsedFigureUrl(chatId, attachmentId, figureId)
  const withMarkdown = rewriteMarkdownFigureRefs(content, figureUrl, meta)
  return withMarkdown.replace(FIGURE_HTML_SRC_RE, (_match, quote, figureId) => {
    const url = attachmentParsedFigureUrl(chatId, attachmentId, figureId)
    return `src=${quote}${url}${quote}`
  })
}

export function resolveHubParsedFigureSrc(
  src: string | undefined,
  hubItemId: string,
  meta?: ParsedFigureMeta,
): string | undefined {
  if (!src) return src
  if (src.startsWith(FIGURE_REF_PREFIX)) {
    const figureId = src.slice(FIGURE_REF_PREFIX.length).trim()
    if (!figureId) return src
    return hubParsedFigureUrl(hubItemId, figureId)
  }
  const stem = hashImageStem(src)
  if (stem) {
    const figureId = resolveFigureIdFromMeta(stem, meta) ?? stem
    return hubParsedFigureUrl(hubItemId, figureId)
  }
  return src
}

export function rewriteHubParsedFigureRefs(
  content: string,
  hubItemId: string,
  meta?: ParsedFigureMeta,
): string {
  const figureUrl = (figureId: string) => hubParsedFigureUrl(hubItemId, figureId)
  const withMarkdown = rewriteMarkdownFigureRefs(content, figureUrl, meta)
  return withMarkdown.replace(FIGURE_HTML_SRC_RE, (_match, quote, figureId) => {
    const url = hubParsedFigureUrl(hubItemId, figureId)
    return `src=${quote}${url}${quote}`
  })
}
