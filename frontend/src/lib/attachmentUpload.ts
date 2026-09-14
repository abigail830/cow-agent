import type { ChatAttachment } from '../types'

export type AttachmentUploadStatus = 'uploading' | 'failed'

export type ChatAttachmentListItem = ChatAttachment & {
  upload_status?: AttachmentUploadStatus
}

export function isPendingAttachmentId(id: string): boolean {
  return id.startsWith('pending-')
}

export function isAttachmentReady(att: ChatAttachmentListItem): boolean {
  return !isPendingAttachmentId(att.id) && att.upload_status !== 'uploading'
}

export function createPendingAttachment(file: File): ChatAttachmentListItem {
  return {
    id: `pending-${crypto.randomUUID()}`,
    chat_id: '',
    filename: file.name,
    mime_type: file.type || 'application/octet-stream',
    size_bytes: file.size,
    provider: 'pending',
    provider_file_id: '',
    created_at: null,
    upload_status: 'uploading',
  }
}

export function readyAttachments(items: ChatAttachmentListItem[]): ChatAttachment[] {
  return items.filter(isAttachmentReady)
}

/** Merge server list with local upload state without dropping in-flight or just-finished rows. */
export function mergeChatAttachmentList(
  local: ChatAttachmentListItem[],
  server: ChatAttachment[],
): ChatAttachmentListItem[] {
  const serverById = new Map(server.map((row) => [row.id, row]))
  const uploading = local.filter((row) => row.upload_status === 'uploading')
  const localOnlyReady = local.filter(
    (row) => isAttachmentReady(row) && !serverById.has(row.id),
  )

  const seen = new Set<string>()
  const merged: ChatAttachmentListItem[] = []

  const push = (row: ChatAttachmentListItem) => {
    if (isPendingAttachmentId(row.id)) {
      merged.push(row)
      return
    }
    if (seen.has(row.id)) return
    seen.add(row.id)
    merged.push(row)
  }

  for (const row of uploading) push(row)
  for (const row of server) push(row)
  for (const row of localOnlyReady) push(row)
  return merged
}

export function replacePendingAttachment(
  prev: ChatAttachmentListItem[],
  pendingId: string,
  uploaded: ChatAttachment,
): ChatAttachmentListItem[] {
  const withoutPending = prev.filter((row) => row.id !== pendingId)
  if (withoutPending.some((row) => row.id === uploaded.id)) {
    return withoutPending
  }
  return prev.map((row) => (row.id === pendingId ? uploaded : row))
}
