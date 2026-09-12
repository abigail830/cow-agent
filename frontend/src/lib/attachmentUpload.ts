import type { AttachmentProcessingMode } from './attachmentMode'
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

export function createPendingAttachment(
  file: File,
  processingMode: AttachmentProcessingMode,
): ChatAttachmentListItem {
  return {
    id: `pending-${crypto.randomUUID()}`,
    chat_id: '',
    filename: file.name,
    mime_type: file.type || 'application/octet-stream',
    size_bytes: file.size,
    provider: processingMode === 'unify_lite' ? 'unify_lite' : 'pending',
    provider_file_id: '',
    processing_mode: processingMode,
    created_at: null,
    upload_status: 'uploading',
  }
}

export function readyAttachments(items: ChatAttachmentListItem[]): ChatAttachment[] {
  return items.filter(isAttachmentReady)
}
