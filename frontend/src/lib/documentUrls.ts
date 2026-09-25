import { resolveApiPath } from './apiBase'

export type ParsedArtifactKey = 'content_md' | 'meta_json' | 'pageindex_json'

export function attachmentOriginalUrl(
  chatId: string,
  attachmentId: string,
  options?: { inline?: boolean },
): string {
  const base = resolveApiPath(`/chats/${chatId}/attachments/${attachmentId}/original`)
  return options?.inline ? `${base}?disposition=inline` : base
}

export function attachmentParsedUrl(
  chatId: string,
  attachmentId: string,
  artifactKey: ParsedArtifactKey,
): string {
  return resolveApiPath(`/chats/${chatId}/attachments/${attachmentId}/parsed/${artifactKey}`)
}

export function attachmentParsedFigureUrl(
  chatId: string,
  attachmentId: string,
  figureId: string,
): string {
  return resolveApiPath(
    `/chats/${chatId}/attachments/${attachmentId}/parsed/figures/${figureId}`,
  )
}
