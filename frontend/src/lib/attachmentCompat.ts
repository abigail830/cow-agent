import { isAttachmentReady } from './attachmentUpload'
import type { ChatAttachment } from '../types'

export type AttachmentCompatResult = {
  compatible: boolean
  reason?: string
}

export function isAttachmentReferenceCompatible(att: ChatAttachment): AttachmentCompatResult {
  if (!isAttachmentReady(att)) {
    return { compatible: false, reason: 'Upload in progress' }
  }
  if (!att.provider_file_id && !att.id) {
    return { compatible: false, reason: 'Attachment is missing storage id' }
  }
  return { compatible: true }
}
