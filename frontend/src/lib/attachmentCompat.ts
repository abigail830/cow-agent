import type { AttachmentProcessingMode } from './attachmentMode'
import { isAttachmentReady } from './attachmentUpload'
import type { ChatAttachment } from '../types'

export type AttachmentCompatResult = {
  compatible: boolean
  reason?: string
}

/** Native-mode compatibility for referencing an existing chat attachment. */
export function isNativeAttachmentCompatible(
  att: ChatAttachment,
  currentProvider: string,
): AttachmentCompatResult {
  if (att.processing_mode === 'unify_lite' || att.provider === 'unify_lite') {
    return {
      compatible: false,
      reason: 'Unify-lite attachment; switch to Unify-lite mode to reference',
    }
  }
  if (att.provider !== currentProvider) {
    return {
      compatible: false,
      reason: `Uploaded for ${att.provider}; current model is ${currentProvider}. Re-upload required.`,
    }
  }

  const mime = (att.mime_type || '').split(';', 1)[0]?.trim().toLowerCase() ?? ''
  const filename = att.filename.toLowerCase()

  if (currentProvider === 'azure_openai') {
    if (mime.startsWith('image/') || mime === 'application/pdf' || filename.endsWith('.pdf')) {
      return { compatible: true }
    }
    return { compatible: false, reason: 'Azure OpenAI supports PDF and images only' }
  }

  if (
    currentProvider === 'siliconflow' ||
    currentProvider === 'dashscope' ||
    currentProvider === 'deepseek'
  ) {
    if (!mime.startsWith('image/')) {
      return { compatible: false, reason: 'Current model supports image attachments only' }
    }
  }

  return { compatible: true }
}

export function isAttachmentReferenceCompatible(
  att: ChatAttachment,
  mode: AttachmentProcessingMode,
  currentProvider: string,
): AttachmentCompatResult {
  if (!isAttachmentReady(att)) {
    return { compatible: false, reason: 'Upload in progress' }
  }
  const isLite = att.processing_mode === 'unify_lite' || att.provider === 'unify_lite'
  if (mode === 'unify_lite') {
    if (!isLite) {
      return {
        compatible: false,
        reason: 'Native attachment; switch to Native mode or re-upload in Unify-lite',
      }
    }
    return { compatible: true }
  }
  if (isLite) {
    return {
      compatible: false,
      reason: 'Unify-lite attachment; switch to Unify-lite mode or re-upload in Native',
    }
  }
  return isNativeAttachmentCompatible(att, currentProvider)
}

export function filterNativeCompatibleAttachments(
  attachments: ChatAttachment[],
  currentProvider: string,
): ChatAttachment[] {
  return attachments.filter((att) => isNativeAttachmentCompatible(att, currentProvider).compatible)
}
