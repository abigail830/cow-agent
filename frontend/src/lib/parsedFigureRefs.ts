import { attachmentParsedFigureUrl, hubParsedFigureUrl } from './documentUrls'

const FIGURE_REF_PREFIX = 'figure:'
const FIGURE_MARKDOWN_RE = /!\[([^\]]*)\]\(([^)]+)\)/g
const FIGURE_HTML_SRC_RE = /(\bsrc\s*=\s*["'])figure:(f\d+)\1/gi
const HTML_IMG_TAG_RE = /<img\b[^>]*\/?>/gi
const HTML_IMG_SRC_ATTR_RE = /\bsrc\s*=\s*(["'])([^"']+)\1/i
const HASH_IMAGE_STEM_RE = /^[a-f0-9]{32,64}$/i
const IMAGE_EXTENSIONS = new Set(['jpeg', 'jpg', 'png', 'gif', 'webp'])

export type ParsedFigureMetaEntry = {
  id: string
  line?: number
  sha256?: string
  filename?: string
  alt?: string
  source_ref?: string
}

export type ParsedFigureMeta = {
  figures?: ParsedFigureMetaEntry[]
}

export function hashImageStem(value: string | undefined): string | null {
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
  return HASH_IMAGE_STEM_RE.test(candidate) ? candidate.toLowerCase() : null
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
    const alt = fig.alt?.toLowerCase() ?? ''
    const sourceRef = fig.source_ref?.toLowerCase() ?? ''
    if (
      sha.startsWith(lower) ||
      filename.includes(lower) ||
      filename.startsWith(lower) ||
      alt.includes(lower) ||
      sourceRef === lower ||
      hashImageStem(fig.alt) === lower ||
      hashImageStem(fig.filename) === lower ||
      hashImageStem(fig.source_ref) === lower
    ) {
      return fig.id
    }
  }
  return undefined
}

/** Map Document Mind hash stems to fN using meta order when line/sha256 matching fails. */
export function buildHashStemToFigureIdMap(
  content: string,
  meta: ParsedFigureMeta | undefined,
): Map<string, string> {
  const map = new Map<string, string>()
  const figures = [...(meta?.figures ?? [])]
    .filter((fig) => fig.id)
    .sort((a, b) => (a.line ?? 0) - (b.line ?? 0))

  const stemsInDoc: string[] = []
  const seen = new Set<string>()
  const recordStem = (stem: string | null) => {
    if (!stem || seen.has(stem)) return
    seen.add(stem)
    stemsInDoc.push(stem)
  }

  for (const line of content.split('\n')) {
    for (const match of line.matchAll(FIGURE_MARKDOWN_RE)) {
      recordStem(hashImageStem(match[2]))
      recordStem(hashImageStem(match[1]))
    }
    for (const match of line.matchAll(/<img\b[^>]*>/gi)) {
      const srcMatch = match[0].match(/\bsrc\s*=\s*["']([^"']+)["']/i)
      if (srcMatch) recordStem(hashImageStem(srcMatch[1]))
      const altMatch = match[0].match(/\balt\s*=\s*["']([^"']+)["']/i)
      if (altMatch) recordStem(hashImageStem(altMatch[1]))
    }
  }

  for (let index = 0; index < stemsInDoc.length; index += 1) {
    const fig = figures[index]
    if (fig?.id) map.set(stemsInDoc[index], fig.id)
  }

  for (const fig of figures) {
    for (const candidate of [fig.source_ref, fig.alt, fig.filename]) {
      const stem = hashImageStem(candidate)
      if (stem && fig.id) map.set(stem, fig.id)
    }
  }

  return map
}

function resolveFigureIdForStem(
  stem: string,
  lineNo: number,
  meta: ParsedFigureMeta | undefined,
  hashMap: Map<string, string>,
): string {
  return (
    figureIdForLine(meta, lineNo) ??
    hashMap.get(stem) ??
    resolveFigureIdFromMeta(stem, meta) ??
    stem
  )
}

function rewriteHtmlImageTags(
  content: string,
  figureUrl: (figureId: string) => string,
  meta: ParsedFigureMeta | undefined,
  hashMap: Map<string, string>,
): string {
  return content.replace(HTML_IMG_TAG_RE, (tag) =>
    tag.replace(HTML_IMG_SRC_ATTR_RE, (_full, quote: string, rawSrc: string) => {
      const src = rawSrc.trim()
      if (!src || src.startsWith('data:')) return _full
      if (src.startsWith(FIGURE_REF_PREFIX)) {
        const figureId = src.slice(FIGURE_REF_PREFIX.length).trim()
        return figureId ? `src=${quote}${figureUrl(figureId)}${quote}` : _full
      }
      const stem = hashImageStem(src)
      if (stem) {
        const figureId = hashMap.get(stem) ?? resolveFigureIdFromMeta(stem, meta) ?? stem
        return `src=${quote}${figureUrl(figureId)}${quote}`
      }
      if (src.startsWith('http://') || src.startsWith('https://') || src.startsWith('/api/')) {
        return _full
      }
      return _full
    }),
  )
}

function rewriteMarkdownFigureRefs(
  content: string,
  figureUrl: (figureId: string) => string,
  meta: ParsedFigureMeta | undefined,
  hashMap: Map<string, string>,
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
          const figureId = resolveFigureIdForStem(stem, lineNo, meta, hashMap)
          return `![${alt}](${figureUrl(figureId)})`
        }

        if (url.startsWith('http://') || url.startsWith('https://')) {
          const pathStem = hashImageStem(url)
          if (pathStem) {
            const figureId = resolveFigureIdForStem(pathStem, lineNo, meta, hashMap)
            return `![${alt}](${figureUrl(figureId)})`
          }
        }

        return match
      }),
    )
  }

  return output.join('\n')
}

function rewriteAllFigureRefs(
  content: string,
  figureUrl: (figureId: string) => string,
  meta?: ParsedFigureMeta,
): string {
  const hashMap = buildHashStemToFigureIdMap(content, meta)
  const withMarkdown = rewriteMarkdownFigureRefs(content, figureUrl, meta, hashMap)
  const withHtml = rewriteHtmlImageTags(withMarkdown, figureUrl, meta, hashMap)
  return withHtml.replace(FIGURE_HTML_SRC_RE, (_match, quote, figureId) => {
    const url = figureUrl(figureId)
    return `src=${quote}${url}${quote}`
  })
}

export function resolveParsedFigureSrc(
  src: string | undefined,
  chatId: string,
  attachmentId: string,
  meta?: ParsedFigureMeta,
  contentForMap?: string,
): string | undefined {
  if (!src) return src
  const hashMap = contentForMap ? buildHashStemToFigureIdMap(contentForMap, meta) : new Map()
  if (src.startsWith(FIGURE_REF_PREFIX)) {
    const figureId = src.slice(FIGURE_REF_PREFIX.length).trim()
    if (!figureId) return src
    return attachmentParsedFigureUrl(chatId, attachmentId, figureId)
  }
  const stem = hashImageStem(src)
  if (stem) {
    const figureId = hashMap.get(stem) ?? resolveFigureIdFromMeta(stem, meta) ?? stem
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
  return rewriteAllFigureRefs(content, figureUrl, meta)
}

export function resolveHubParsedFigureSrc(
  src: string | undefined,
  hubItemId: string,
  meta?: ParsedFigureMeta,
  contentForMap?: string,
): string | undefined {
  if (!src) return src
  const hashMap = contentForMap ? buildHashStemToFigureIdMap(contentForMap, meta) : new Map()
  if (src.startsWith(FIGURE_REF_PREFIX)) {
    const figureId = src.slice(FIGURE_REF_PREFIX.length).trim()
    if (!figureId) return src
    return hubParsedFigureUrl(hubItemId, figureId)
  }
  const stem = hashImageStem(src)
  if (stem) {
    const figureId = hashMap.get(stem) ?? resolveFigureIdFromMeta(stem, meta) ?? stem
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
  return rewriteAllFigureRefs(content, figureUrl, meta)
}
