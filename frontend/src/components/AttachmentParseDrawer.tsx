import { X } from 'lucide-react'
import type { ChatAttachmentListItem } from '../lib/attachmentUpload'
import { isAttachmentParsing } from '../lib/attachmentUpload'

const STAGE_ORDER = [
  'fetch',
  'analyze',
  'parse_submit',
  'parse_wait',
  'parse_collect',
  'normalize',
  'write',
  'finalize',
] as const

function formatFileSize(sizeBytes: number): string {
  if (sizeBytes < 1024) return `${sizeBytes} B`
  if (sizeBytes < 1024 * 1024) return `${(sizeBytes / 1024).toFixed(1)} KB`
  return `${(sizeBytes / (1024 * 1024)).toFixed(1)} MB`
}

type Props = {
  attachment: ChatAttachmentListItem | null
  onClose: () => void
}

export function AttachmentParseDrawer({ attachment, onClose }: Props) {
  if (!attachment) return null

  const status = attachment.parse_status ?? 'ready'
  const progress = attachment.parse_progress
  const stageMap = new Map(
    (progress?.stages ?? []).map((s) => [s.stage_id ?? '', s.status ?? 'pending']),
  )

  return (
    <div className="attachment-parse-drawer-backdrop" role="presentation" onClick={onClose}>
      <aside
        className="attachment-parse-drawer"
        role="dialog"
        aria-label={`Parse status for ${attachment.filename}`}
        onClick={(e) => e.stopPropagation()}
      >
        <header className="attachment-parse-drawer-header">
          <div>
            <h3 className="attachment-parse-drawer-title">{attachment.filename}</h3>
            <p className="attachment-parse-drawer-meta">
              {formatFileSize(attachment.size_bytes)} · {status}
              {attachment.parse_pipeline_id ? ` · ${attachment.parse_pipeline_id}` : ''}
            </p>
          </div>
          <button type="button" className="attachment-parse-drawer-close" onClick={onClose} aria-label="Close">
            <X size={18} />
          </button>
        </header>

        {progress?.message ? (
          <p className="attachment-parse-drawer-message">{progress.message}</p>
        ) : null}

        {attachment.parse_error_message ? (
          <p className="attachment-parse-drawer-error">{attachment.parse_error_message}</p>
        ) : null}

        {isAttachmentParsing(attachment) || (progress?.stages?.length ?? 0) > 0 ? (
          <ol className="attachment-parse-drawer-stages">
            {STAGE_ORDER.map((stageId) => {
              const stageStatus = stageMap.get(stageId) ?? 'pending'
              const active = progress?.current_stage === stageId
              return (
                <li
                  key={stageId}
                  className={[
                    'attachment-parse-drawer-stage',
                    `attachment-parse-drawer-stage-${stageStatus}`,
                    active ? 'attachment-parse-drawer-stage-active' : '',
                  ]
                    .filter(Boolean)
                    .join(' ')}
                >
                  <span className="attachment-parse-drawer-stage-id">{stageId}</span>
                  <span className="attachment-parse-drawer-stage-status">{stageStatus}</span>
                </li>
              )
            })}
          </ol>
        ) : null}
      </aside>
    </div>
  )
}
