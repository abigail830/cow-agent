import { resolveApiPath } from './apiBase'

export type ParsedArtifactKey = 'content_md' | 'meta_json' | 'pageindex_json'

export function attachmentOriginalUrl(chatId: string, attachmentId: string): string {
  return resolveApiPath(`/chats/${chatId}/attachments/${attachmentId}/original`)
}

export function attachmentParsedUrl(
  chatId: string,
  attachmentId: string,
  artifactKey: ParsedArtifactKey,
): string {
  return resolveApiPath(`/chats/${chatId}/attachments/${attachmentId}/parsed/${artifactKey}`)
}
