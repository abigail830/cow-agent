/** Attachment limits — defaults match backend; override via GET /config/attachments */

import type { ChatAttachment } from '../types'

export const DEFAULT_ATTACHMENT_LIMITS = {
  max_files_per_message: 5,
  max_bytes_per_file: 50 * 1024 * 1024,
  max_total_bytes_per_message: 50 * 1024 * 1024,
} as const

export type AttachmentLimits = {
  max_files_per_message: number
  max_bytes_per_file: number
  max_total_bytes_per_message: number
}

export const SUPPORTED_ATTACHMENT_ACCEPT =
  '.pdf,.txt,.md,.csv,.json,.png,.jpg,.jpeg,.gif,.webp,.doc,.docx,.xls,.xlsx,.ppt,.pptx'

export const SUPPORTED_ATTACHMENT_LABEL =
  'PDF, text, CSV, JSON, images (PNG/JPEG/GIF/WebP), Word/Excel/PowerPoint'

const SUPPORTED_ATTACHMENT_EXTENSIONS = new Set(
  SUPPORTED_ATTACHMENT_ACCEPT.split(',').map((ext) => ext.trim().toLowerCase()).filter(Boolean),
)

const SUPPORTED_ATTACHMENT_MIMES = new Set([
  'application/pdf',
  'text/plain',
  'text/markdown',
  'text/csv',
  'application/json',
  'image/png',
  'image/jpeg',
  'image/gif',
  'image/webp',
  'application/msword',
  'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
  'application/vnd.ms-excel',
  'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
  'application/vnd.ms-powerpoint',
  'application/vnd.openxmlformats-officedocument.presentationml.presentation',
])

const MIME_TO_EXTENSION: Record<string, string> = {
  'image/png': 'png',
  'image/jpeg': 'jpg',
  'image/gif': 'gif',
  'image/webp': 'webp',
  'application/pdf': 'pdf',
  'text/plain': 'txt',
  'text/markdown': 'md',
  'text/csv': 'csv',
  'application/json': 'json',
}

function fileExtension(filename: string): string {
  const idx = filename.lastIndexOf('.')
  if (idx < 0) return ''
  return filename.slice(idx).toLowerCase()
}

export function isSupportedAttachmentFile(file: File): boolean {
  const ext = fileExtension(file.name)
  if (ext && SUPPORTED_ATTACHMENT_EXTENSIONS.has(ext)) return true
  const mime = (file.type || '').split(';', 1)[0]?.trim().toLowerCase()
  return Boolean(mime && SUPPORTED_ATTACHMENT_MIMES.has(mime))
}

/** Clipboard screenshots often arrive as unnamed blobs — give them a stable filename. */
export function normalizePastedAttachmentFile(file: File): File {
  const ext = fileExtension(file.name)
  if (ext && file.name.trim() && !/^image\.\w+$/i.test(file.name.trim())) {
    return file
  }
  const mime = (file.type || '').split(';', 1)[0]?.trim().toLowerCase()
  const resolvedExt = (mime && MIME_TO_EXTENSION[mime]) || ext.replace('.', '') || 'png'
  const stamp = new Date().toISOString().replace(/[:.]/g, '-').slice(0, 19)
  const type = file.type || (resolvedExt === 'jpg' ? 'image/jpeg' : `image/${resolvedExt}`)
  return new File([file], `pasted-${stamp}.${resolvedExt}`, { type })
}

/** Read supported files from a paste event (e.g. screenshot from clipboard). */
export function readPastedAttachmentFiles(data: DataTransfer | null): File[] {
  if (!data) return []
  const files: File[] = []
  for (const item of Array.from(data.items)) {
    if (item.kind !== 'file') continue
    const raw = item.getAsFile()
    if (!raw) continue
    const file = normalizePastedAttachmentFile(raw)
    if (isSupportedAttachmentFile(file)) files.push(file)
  }
  return files
}

export function formatAttachmentLimitMb(bytes: number): number {
  return bytes / (1024 * 1024)
}

export function validatePendingAttachments(
  current: { size_bytes: number }[],
  incomingBytes: number,
  limits: AttachmentLimits = DEFAULT_ATTACHMENT_LIMITS,
): string | null {
  if (current.length >= limits.max_files_per_message) {
    return `At most ${limits.max_files_per_message} attachments per message`
  }
  if (incomingBytes > limits.max_bytes_per_file) {
    return `Each file must be under ${formatAttachmentLimitMb(limits.max_bytes_per_file)} MB`
  }
  const total = current.reduce((sum, item) => sum + item.size_bytes, 0) + incomingBytes
  if (total > limits.max_total_bytes_per_message) {
    return `Combined attachments must stay under ${formatAttachmentLimitMb(limits.max_total_bytes_per_message)} MB per message`
  }
  return null
}

/** Pending attachment before send — local file (no chat yet) or uploaded to provider. */
export type PendingAttachment =
  | { kind: 'local'; localId: string; file: File }
  | { kind: 'uploaded'; attachment: ChatAttachment }

export function pendingAttachmentId(item: PendingAttachment): string {
  return item.kind === 'local' ? item.localId : item.attachment.id
}

export function pendingAttachmentFilename(item: PendingAttachment): string {
  return item.kind === 'local' ? item.file.name : item.attachment.filename
}

export function pendingAttachmentSize(item: PendingAttachment): number {
  return item.kind === 'local' ? item.file.size : item.attachment.size_bytes
}

export function pendingAttachmentsForValidation(items: PendingAttachment[]): { size_bytes: number }[] {
  return items.map((item) => ({ size_bytes: pendingAttachmentSize(item) }))
}
