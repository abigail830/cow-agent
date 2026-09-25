import { attachmentParsedFigureUrl } from './documentUrls'

const FIGURE_REF_PREFIX = 'figure:'
const FIGURE_MARKDOWN_RE = /!\[([^\]]*)\]\(figure:(f\d+)\)/gi
const FIGURE_HTML_SRC_RE = /(\bsrc\s*=\s*["'])figure:(f\d+)\1/gi

export function resolveParsedFigureSrc(
  src: string | undefined,
  chatId: string,
  attachmentId: string,
): string | undefined {
  if (!src) return src
  if (!src.startsWith(FIGURE_REF_PREFIX)) return src
  const figureId = src.slice(FIGURE_REF_PREFIX.length).trim()
  if (!figureId) return src
  return attachmentParsedFigureUrl(chatId, attachmentId, figureId)
}

/** Rewrite figure:fN refs to browser-fetchable URLs before markdown render. */
export function rewriteParsedFigureRefs(
  content: string,
  chatId: string,
  attachmentId: string,
): string {
  const withMarkdown = content.replace(FIGURE_MARKDOWN_RE, (_match, alt, figureId) => {
    const url = attachmentParsedFigureUrl(chatId, attachmentId, figureId)
    return `![${alt}](${url})`
  })
  return withMarkdown.replace(FIGURE_HTML_SRC_RE, (_match, quote, figureId) => {
    const url = attachmentParsedFigureUrl(chatId, attachmentId, figureId)
    return `src=${quote}${url}${quote}`
  })
}
