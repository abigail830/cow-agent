import { X } from 'lucide-react'
import { LoadingSpinner } from './LoadingSpinner'
import type { ChatAttachmentListItem } from '../lib/attachmentUpload'
import { isAttachmentParsing, isAttachmentReady, isPendingAttachmentId } from '../lib/attachmentUpload'

type Props = {
  attachments: ChatAttachmentListItem[]
  onRemove: (id: string) => void
  onChipClick?: (attachment: ChatAttachmentListItem) => void
  disabled?: boolean
}

export function ComposerStagedChips({ attachments, onRemove, onChipClick, disabled = false }: Props) {
  if (attachments.length === 0) return null

  return (
    <div className="composer-staged-chips" role="list" aria-label="Attachments for this message">
      {attachments.map((att) => {
        const uploading = att.upload_status === 'uploading' || isPendingAttachmentId(att.id)
        const failed = att.upload_status === 'failed' || att.parse_status === 'failed'
        const parsing = !uploading && !failed && isAttachmentParsing(att)
        const ready = !failed && isAttachmentReady(att)
        const chipClass = [
          'composer-staged-chip',
          uploading || parsing ? 'composer-staged-chip-uploading' : '',
          failed ? 'composer-staged-chip-failed' : '',
          ready ? 'composer-staged-chip-ready' : '',
        ]
          .filter(Boolean)
          .join(' ')

        return (
          <div key={att.id} className={chipClass} role="listitem">
            {uploading || parsing ? (
              <span className="composer-staged-chip-spinner" aria-label={parsing ? 'Parsing' : 'Uploading'}>
                <LoadingSpinner size="sm" />
              </span>
            ) : null}
            <button
              type="button"
              className="composer-staged-chip-name composer-staged-chip-name-btn"
              title={att.filename}
              onClick={() => onChipClick?.(att)}
            >
              {att.filename}
              {parsing ? (
                <span className="proposal-draft-bagel composer-staged-chip-bagel">Parsing</span>
              ) : null}
              {failed ? <span className="composer-staged-chip-failed-label">Failed</span> : null}
            </button>
            <button
              type="button"
              className="composer-staged-chip-remove"
              aria-label={`Remove ${att.filename}`}
              title="Remove"
              disabled={disabled}
              onClick={() => onRemove(att.id)}
            >
              <X size={14} strokeWidth={2} aria-hidden="true" />
            </button>
          </div>
        )
      })}
    </div>
  )
}
