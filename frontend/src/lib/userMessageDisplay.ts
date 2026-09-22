import type { MessageAttachmentMeta } from '../types'

const ATTACHMENT_BLOCK_MARKER = '\n\n### '

/** User-visible prompt only; strip legacy merged attachment materialization tails. */
export function splitUserPromptText(content: string | null | undefined): string {
  const stripped = (content ?? '').trim()
  if (!stripped) return ''
  const marker = stripped.indexOf(ATTACHMENT_BLOCK_MARKER)
  if (marker >= 0) return stripped.slice(0, marker).trim()
  if (stripped.startsWith('### ') && stripped.includes('```')) return ''
  return stripped
}

export function isAttachmentMaterializationText(content: string | null | undefined): boolean {
  const stripped = (content ?? '').trim()
  return stripped.startsWith('### ') && stripped.includes('```')
}

export function platformAttachments(raw: unknown): MessageAttachmentMeta[] {
  if (!raw || typeof raw !== 'object') return []
  const platform = (raw as { platform?: unknown }).platform
  if (!platform || typeof platform !== 'object') return []
  const attachments = (platform as { attachments?: unknown }).attachments
  if (!Array.isArray(attachments)) return []
  return attachments.filter(
    (item): item is MessageAttachmentMeta =>
      !!item &&
      typeof item === 'object' &&
      typeof (item as MessageAttachmentMeta).filename === 'string',
  )
}
