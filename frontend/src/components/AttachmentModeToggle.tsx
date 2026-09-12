import {
  ATTACHMENT_MODE_OPTIONS,
  type AttachmentProcessingMode,
} from '../lib/attachmentMode'

interface AttachmentModeToggleProps {
  value: AttachmentProcessingMode
  onChange: (mode: AttachmentProcessingMode) => void
  disabled?: boolean
}

export function AttachmentModeToggle({
  value,
  onChange,
  disabled = false,
}: AttachmentModeToggleProps) {
  return (
    <div
      className="attachment-mode-toggle"
      role="group"
      aria-label="Attachment processing mode"
    >
      {ATTACHMENT_MODE_OPTIONS.map((option) => (
        <button
          key={option.value}
          type="button"
          className={`attachment-mode-toggle-btn${value === option.value ? ' attachment-mode-toggle-btn-active' : ''}`}
          aria-pressed={value === option.value}
          title={option.description}
          disabled={disabled}
          onClick={() => onChange(option.value)}
        >
          {option.label}
        </button>
      ))}
    </div>
  )
}
