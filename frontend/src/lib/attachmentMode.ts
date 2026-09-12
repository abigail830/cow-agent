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
    description: 'Platform extracts text/descriptions into the message (coming soon)',
  },
]

export const DEFAULT_ATTACHMENT_MODE: AttachmentProcessingMode = 'native'

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
