import type { ParsedArtifactsAvailability } from '../types'
import { resolveApiPath } from './apiBase'
import {
  attachmentOriginalUrl,
  attachmentParsedFigureUrl,
  attachmentParsedUrl,
  hubParsedFigureUrl,
  type ParsedArtifactKey,
} from './documentUrls'
import {
  type ParsedFigureMeta,
  resolveHubParsedFigureSrc,
  resolveParsedFigureSrc,
  rewriteHubParsedFigureRefs,
  rewriteParsedFigureRefs,
} from './parsedFigureRefs'

export type ParsedDocumentRef =
  | { scope: 'chat'; chatId: string; documentId: string }
  | { scope: 'hub'; itemId: string }

const credentialedFetch: RequestInit = { credentials: 'include' }

export function originalDocumentUrl(
  ref: ParsedDocumentRef,
  options?: { inline?: boolean },
): string {
  if (ref.scope === 'chat') {
    return attachmentOriginalUrl(ref.chatId, ref.documentId, options)
  }
  return resolveApiPath(`/document-hub/items/${ref.itemId}/original`)
}

export function parsedArtifactUrl(ref: ParsedDocumentRef, artifactKey: ParsedArtifactKey): string {
  if (ref.scope === 'chat') {
    return attachmentParsedUrl(ref.chatId, ref.documentId, artifactKey)
  }
  return resolveApiPath(`/document-hub/items/${ref.itemId}/parsed/${artifactKey}`)
}

export function parsedFigureUrl(ref: ParsedDocumentRef, figureId: string): string {
  if (ref.scope === 'chat') {
    return attachmentParsedFigureUrl(ref.chatId, ref.documentId, figureId)
  }
  return hubParsedFigureUrl(ref.itemId, figureId)
}

export async function fetchParsedArtifactText(
  ref: ParsedDocumentRef,
  artifactKey: ParsedArtifactKey,
): Promise<string> {
  const res = await fetch(parsedArtifactUrl(ref, artifactKey), credentialedFetch)
  if (!res.ok) {
    const text = await res.text()
    throw new Error(text || res.statusText)
  }
  return res.text()
}

export function rewriteParsedMarkdown(
  content: string,
  ref: ParsedDocumentRef,
  meta?: ParsedFigureMeta,
): string {
  if (ref.scope === 'chat') {
    return rewriteParsedFigureRefs(content, ref.chatId, ref.documentId, meta)
  }
  return rewriteHubParsedFigureRefs(content, ref.itemId, meta)
}

export function resolveParsedMarkdownFigureSrc(
  src: string | undefined,
  ref: ParsedDocumentRef,
  meta?: ParsedFigureMeta,
  parsedContent?: string | null,
): string | undefined {
  const contentForMap = parsedContent ?? undefined
  if (ref.scope === 'chat') {
    return resolveParsedFigureSrc(src, ref.chatId, ref.documentId, meta, contentForMap)
  }
  return resolveHubParsedFigureSrc(src, ref.itemId, meta, contentForMap)
}

export function emptyParsedArtifacts(): ParsedArtifactsAvailability {
  return { content_md: false, meta_json: false, pageindex_json: false }
}

export function parsedArtifactsFromManifest(manifest: unknown): ParsedArtifactsAvailability {
  if (!manifest || typeof manifest !== 'object') return emptyParsedArtifacts()
  const artifacts = (manifest as { artifacts?: Record<string, unknown> }).artifacts
  if (!artifacts || typeof artifacts !== 'object') return emptyParsedArtifacts()
  return {
    content_md: 'content_md' in artifacts,
    meta_json: 'meta_json' in artifacts,
    pageindex_json: 'pageindex_json' in artifacts,
  }
}

export function hubItemParsedArtifacts(item: {
  parse_status?: string | null
  parsed_artifacts?: ParsedArtifactsAvailability | null
}): ParsedArtifactsAvailability {
  if (item.parsed_artifacts) return item.parsed_artifacts
  const ready = item.parse_status === 'ready' || item.parse_status === 'skipped'
  return {
    content_md: ready,
    meta_json: false,
    pageindex_json: false,
  }
}

export function canPreviewOriginalMime(mimeType: string): boolean {
  const mime = mimeType.toLowerCase()
  return mime.startsWith('image/') || mime === 'application/pdf' || mime.startsWith('text/')
}
