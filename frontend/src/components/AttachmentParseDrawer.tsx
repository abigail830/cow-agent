import { useState } from 'react'
import { Check, Circle, ImageIcon, Loader2, Minus, RotateCcw, X } from 'lucide-react'
import type { ChatAttachmentListItem } from '../lib/attachmentUpload'
import {
  PARSE_STAGE_ORDER,
  buildStageStatuses,
  effectiveParseStatus,
  isImageAttachment,
  parseNotRequired,
  parseNotRequiredDetail,
  parseProgressMessage,
  parseProgressMessageTone,
  parseStatusDisplayLabel,
  type ParseStageDisplayStatus,
  type ParseStageId,
} from '../lib/attachmentParseProgress'

const STAGE_LABELS: Record<ParseStageId, string> = {
  fetch: 'Fetch source',
  analyze: 'Analyze file',
  parse_submit: 'Submit parse',
  parse_wait: 'Wait for parser',
  parse_collect: 'Collect output',
  normalize: 'Normalize',
  write: 'Write artifacts',
  finalize: 'Finalize',
}

const STAGE_STATUS_LABELS: Record<ParseStageDisplayStatus, string> = {
  pending: 'waiting',
  running: 'running',
  succeeded: 'done',
  failed: 'failed',
  skipped: 'skipped',
}

function formatFileSize(sizeBytes: number): string {
  if (sizeBytes < 1024) return `${sizeBytes} B`
  if (sizeBytes < 1024 * 1024) return `${(sizeBytes / 1024).toFixed(1)} KB`
  return `${(sizeBytes / (1024 * 1024)).toFixed(1)} MB`
}

function stageNodeClass(status: ParseStageDisplayStatus, active: boolean): string {
  const classes = ['parse-pipeline-node', `parse-pipeline-node-${status}`]
  if (active) classes.push('parse-pipeline-node-active')
  return classes.join(' ')
}

function StageIcon({ status }: { status: ParseStageDisplayStatus }) {
  if (status === 'running') {
    return <Loader2 size={12} className="parse-pipeline-node-spinner" aria-hidden />
  }
  if (status === 'succeeded') {
    return <Check size={12} aria-hidden />
  }
  if (status === 'failed') {
    return <X size={12} aria-hidden />
  }
  if (status === 'skipped') {
    return <Minus size={12} aria-hidden />
  }
  return <Circle size={8} aria-hidden />
}

type Props = {
  attachment: ChatAttachmentListItem | null
  onClose: () => void
  onRetry?: (attachment: ChatAttachmentListItem) => Promise<void>
}

export function AttachmentParseDrawer({ attachment, onClose, onRetry }: Props) {
  const [retrying, setRetrying] = useState(false)

  if (!attachment) return null

  const currentAttachment = attachment
  const notRequired = parseNotRequired(currentAttachment)
  const status = effectiveParseStatus(currentAttachment)
  const statusLabel = parseStatusDisplayLabel(currentAttachment)
  const stageStatuses = buildStageStatuses(currentAttachment)
  const progressMessage = parseProgressMessage(currentAttachment)
  const progressTone = parseProgressMessageTone(currentAttachment)
  const notRequiredDetail = parseNotRequiredDetail(currentAttachment)
  const canRetry = Boolean(onRetry) && !notRequired && status === 'failed'

  async function handleRetry() {
    if (!onRetry || retrying) return
    setRetrying(true)
    try {
      await onRetry(currentAttachment)
    } finally {
      setRetrying(false)
    }
  }

  return (
    <>
      <div className="attachment-parse-drawer-backdrop" role="presentation" onClick={onClose} />
      <aside
        className="attachment-parse-drawer"
        role="dialog"
        aria-modal="true"
        aria-label={`Parse status for ${attachment.filename}`}
      >
        <header className="attachment-parse-drawer-header">
          <div>
            <h3 className="attachment-parse-drawer-title">{attachment.filename}</h3>
            <p className="attachment-parse-drawer-meta">
              {formatFileSize(attachment.size_bytes)} · {statusLabel}
              {attachment.parse_pipeline_id ? ` · ${attachment.parse_pipeline_id}` : ''}
            </p>
          </div>
          <button type="button" className="attachment-parse-drawer-close" onClick={onClose} aria-label="Close">
            <X size={18} />
          </button>
        </header>

        {notRequired ? (
          <div className="attachment-parse-drawer-not-required" role="status">
            <span className="attachment-parse-drawer-not-required-icon" aria-hidden>
              {isImageAttachment(attachment) ? <ImageIcon size={20} /> : <Check size={20} />}
            </span>
            <p className="attachment-parse-drawer-not-required-text">{notRequiredDetail}</p>
          </div>
        ) : (
          <>
            {progressMessage ? (
              <p
                className={[
                  'attachment-parse-drawer-message',
                  progressTone === 'warning' ? 'attachment-parse-drawer-message-warning' : '',
                  progressTone === 'error' ? 'attachment-parse-drawer-message-error' : '',
                ]
                  .filter(Boolean)
                  .join(' ')}
              >
                {progressMessage}
              </p>
            ) : null}

            {attachment.parse_error_message && progressTone !== 'error' ? (
              <p className="attachment-parse-drawer-error">{attachment.parse_error_message}</p>
            ) : null}

            {canRetry ? (
              <div className="attachment-parse-drawer-actions">
                <button
                  type="button"
                  className="attachment-parse-drawer-retry"
                  disabled={retrying}
                  onClick={() => void handleRetry()}
                >
                  {retrying ? (
                    <Loader2 size={14} className="parse-pipeline-node-spinner" aria-hidden />
                  ) : (
                    <RotateCcw size={14} aria-hidden />
                  )}
                  {retrying ? 'Retrying…' : 'Retry parse'}
                </button>
                <p className="attachment-parse-drawer-retry-hint">
                  Re-runs the full pipeline from fetch (v1). Partial step resume is not supported yet.
                </p>
              </div>
            ) : null}

            <ol className="parse-pipeline-track" aria-label="Parse pipeline stages">
              {PARSE_STAGE_ORDER.map((stageId) => {
                const stageStatus = stageStatuses.get(stageId) ?? 'pending'
                const active = stageStatus === 'running'
                const label = STAGE_LABELS[stageId]
                return (
                  <li key={stageId} className={stageNodeClass(stageStatus, active)}>
                    <span className="parse-pipeline-node-rail" aria-hidden>
                      <span className="parse-pipeline-node-dot">
                        <StageIcon status={stageStatus} />
                      </span>
                    </span>
                    <div className="parse-pipeline-node-body">
                      <span className="parse-pipeline-node-label">{label}</span>
                      <span className="parse-pipeline-node-id">{stageId}</span>
                      <span className="parse-pipeline-node-status">{STAGE_STATUS_LABELS[stageStatus]}</span>
                    </div>
                  </li>
                )
              })}
            </ol>
          </>
        )}
      </aside>
    </>
  )
}
