import type { AttachmentParseStatus } from '../types'
import type { ChatAttachmentListItem } from './attachmentUpload'
import type { HubItem } from '../types/hub'

export function hubItemPreviewReady(item: HubItem): boolean {
  const status = item.parse_status ?? 'pending'
  return status === 'ready' || status === 'skipped'
}

export function hubItemShowsParseDrawer(item: HubItem): boolean {
  return !hubItemPreviewReady(item)
}

/** Map hub list row to attachment shape for AttachmentParseDrawer. */
export function hubItemToAttachmentListItem(item: HubItem): ChatAttachmentListItem {
  const snap = item.parse_stage_snapshot
  const parse_progress =
    snap && typeof snap === 'object'
      ? {
          current_stage:
            typeof snap.current_stage === 'string' ? snap.current_stage : null,
          message: typeof snap.message === 'string' ? snap.message : null,
          stages: Array.isArray(snap.stages) ? snap.stages : null,
        }
      : null

  return {
    id: item.id,
    chat_id: '',
    filename: item.filename,
    mime_type: item.mime_type,
    size_bytes: item.size_bytes,
    provider: 'hub',
    provider_file_id: item.id,
    created_at: null,
    parse_status: (item.parse_status ?? 'pending') as AttachmentParseStatus,
    parse_pipeline_id: item.parse_pipeline_id ?? null,
    parse_job_id: item.parse_job_id ?? null,
    parse_error_message: item.parse_error_message ?? null,
    parse_progress,
  }
}
