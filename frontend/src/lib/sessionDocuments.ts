import type { ChatAttachment } from '../types'
import type { ChatDocumentImport } from '../types/hub'
import { isAttachmentReady } from './attachmentUpload'

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
        parse_status: imp.parse_status ?? 'ready',
        upload_status: 'ready',
      } as ChatAttachment)
    }
  }
  return out
}
