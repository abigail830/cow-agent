/** How chat attachments are processed before reaching the LLM. */

export type AttachmentProcessingMode = 'native' | 'unify_lite'

export const ATTACHMENT_MODE_OPTIONS: {
  value: AttachmentProcessingMode
  label: string
  description: string
}[] = [
  {
    value: 'native',
    label: 'Native',
    description: 'Use the current model Files / Vision APIs',
  },
  {
    value: 'unify_lite',
    label: 'Unify-lite',
    description: 'Extract txt/md/docx; images stay in library until @referenced (native vision)',
  },
]

export const UNIFY_LITE_ATTACHMENT_ACCEPT = '.txt,.md,.docx,.png,.jpg,.jpeg,.gif,.webp'

export const UNIFY_LITE_ATTACHMENT_LABEL =
  'Text (.txt, .md, .docx) and images (PNG/JPEG/GIF/WebP); @ to reference on send'

export const DEFAULT_ATTACHMENT_MODE: AttachmentProcessingMode = 'unify_lite'

const STORAGE_PREFIX = 'agent-platform:attachment-mode:'

export function getStoredAttachmentMode(agentId: string): AttachmentProcessingMode | null {
  try {
    const raw = localStorage.getItem(`${STORAGE_PREFIX}${agentId}`)
    if (raw === 'native' || raw === 'unify_lite') return raw
  } catch {
    /* ignore */
  }
  return null
}

export function setStoredAttachmentMode(agentId: string, mode: AttachmentProcessingMode): void {
  try {
    localStorage.setItem(`${STORAGE_PREFIX}${agentId}`, mode)
  } catch {
    /* ignore */
  }
}

export function attachmentModeLabel(mode: AttachmentProcessingMode): string {
  return ATTACHMENT_MODE_OPTIONS.find((item) => item.value === mode)?.label ?? mode
}
