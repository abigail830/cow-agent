import type { ChatAttachment } from '../types'
import type { ChatDocumentImport } from '../types/hub'
import { isAttachmentReady } from './attachmentUpload'

/** Resolve an attachment id for send — chat uploads and hub imports use different stores. */
export function resolveAttachmentForSend(
  attachmentId: string,
  chatAttachments: ChatAttachment[],
  mentionAttachments: ChatAttachment[],
): ChatAttachment | undefined {
  const fromChat = chatAttachments.find((row) => row.id === attachmentId)
  if (fromChat) return fromChat
  return mentionAttachments.find((row) => row.id === attachmentId)
}

/** Single hub import row → mention chip shape (any parse status). */
export function hubImportRowToMentionAttachment(row: ChatDocumentImport): ChatAttachment | null {
  if (row.source !== 'hub_item') return null
  return {
    id: row.ref_id,
    chat_id: '',
    filename: row.filename ?? 'Hub document',
    mime_type: 'application/octet-stream',
    size_bytes: 0,
    provider: 'hub',
    provider_file_id: row.ref_id,
    created_at: null,
    parse_status: (row.parse_status ?? 'pending') as ChatAttachment['parse_status'],
  }
}

/** Map session import rows to mention-compatible attachment rows. */
export function importsToMentionAttachments(
  imports: ChatDocumentImport[],
  chatAttachments: ChatAttachment[],
): ChatAttachment[] {
  const out: ChatAttachment[] = []
  for (const imp of imports) {
    if (imp.source === 'chat_attachment') {
      const row = chatAttachments.find((a) => a.id === imp.ref_id)
      if (row && isAttachmentReady(row)) out.push(row)
      continue
    }
    if (imp.source === 'hub_item' && imp.parse_status === 'ready') {
      out.push({
        id: imp.ref_id,
        chat_id: '',
        filename: imp.filename ?? 'Hub document',
        mime_type: 'application/octet-stream',
        size_bytes: 0,
        provider: 'hub',
        provider_file_id: imp.ref_id,
        created_at: null,
        parse_status: 'ready',
      })
    }
  }
  return out
}
