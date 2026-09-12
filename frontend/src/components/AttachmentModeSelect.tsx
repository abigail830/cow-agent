import {
  ATTACHMENT_MODE_OPTIONS,
  type AttachmentProcessingMode,
} from '../lib/attachmentMode'

interface AttachmentModeSelectProps {
  value: AttachmentProcessingMode
  onChange: (mode: AttachmentProcessingMode) => void
  disabled?: boolean
}

export function AttachmentModeSelect({
  value,
  onChange,
  disabled,
}: AttachmentModeSelectProps) {
  return (
    <select
      className="chat-attachment-mode-select"
      value={value}
      onChange={(event) => onChange(event.target.value as AttachmentProcessingMode)}
      disabled={disabled}
      aria-label="Attachment processing mode"
      title={
        ATTACHMENT_MODE_OPTIONS.find((item) => item.value === value)?.description ??
        'Attachment processing mode'
      }
    >
      {ATTACHMENT_MODE_OPTIONS.map((option) => (
        <option key={option.value} value={option.value} title={option.description}>
          {option.label}
          {option.value === 'unify_lite' ? ' (preview)' : ''}
        </option>
      ))}
    </select>
  )
}
