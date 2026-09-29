import type { AttachmentParseStatus } from '../types'
import {
  effectiveParseStatus,
  parseNotRequired,
  parseNotRequiredDetail,
  parseProgressMessage,
  parseStatusDisplayLabel,
} from './attachmentParseProgress'

export type DocumentParseListFields = {
  filename: string
  mime_type?: string | null
  parse_status?: string | null
  parse_error_message?: string | null
  parse_stage_snapshot?: Record<string, unknown> | null
  parse_pipeline_id?: string | null
  parse_job_id?: string | null
}

function snapshotMessage(snapshot: Record<string, unknown> | null | undefined): string | null {
  if (!snapshot || typeof snapshot !== 'object') return null
  const message = snapshot.message
  return typeof message === 'string' && message.trim() ? message : null
}

/** Hub-style list badge (Ready / Processing / Queued). */
export function documentParseListBadge(item: DocumentParseListFields): {
  label: string
  detail: string | null
  badgeClass: string
} {
  const status = item.parse_status ?? 'pending'
  if (status === 'uploading') {
    return { label: 'Uploading', detail: null, badgeClass: 'documents-status-badge-running' }
  }
  if (status === 'ready' || status === 'skipped') {
    return { label: 'Ready', detail: null, badgeClass: 'documents-status-badge-ready' }
  }
  if (status === 'failed') {
    return {
      label: 'Failed',
      detail: item.parse_error_message ?? null,
      badgeClass: 'documents-status-badge-failed',
    }
  }
  const message = snapshotMessage(item.parse_stage_snapshot)
  if (status === 'running') {
    return {
      label: 'Processing',
      detail: message,
      badgeClass: 'documents-status-badge-running',
    }
  }
  if (status === 'pending') {
    return { label: 'Queued', detail: message, badgeClass: 'documents-status-badge-pending' }
  }
  return {
    label: status,
    detail: message,
    badgeClass: parseStatusBadgeClass(status),
  }
}

export function parseStatusBadgeClass(status: string | undefined): string {
  const key = status ?? 'pending'
  if (key === 'ready' || key === 'skipped') return 'documents-status-badge-ready'
  if (key === 'failed') return 'documents-status-badge-failed'
  if (key === 'running' || key === 'uploading') return 'documents-status-badge-running'
  return 'documents-status-badge-pending'
}

/** Attachment row in Documents view (uses shared parse progress helpers). */
export function attachmentParseListLabel(attachment: DocumentParseListFields & { parse_status?: AttachmentParseStatus | null }): string {
  return parseStatusDisplayLabel(attachment as Parameters<typeof parseStatusDisplayLabel>[0])
}

export {
  effectiveParseStatus,
  parseNotRequired,
  parseNotRequiredDetail,
  parseProgressMessage,
  parseStatusDisplayLabel,
}
