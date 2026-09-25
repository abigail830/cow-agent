import { useCallback, useRef, useState, type DragEvent } from 'react'
import { GripVertical, Mic, Trash2, X } from 'lucide-react'
import { LoadingSpinner } from './LoadingSpinner'

export type TranscribeAudioDraftFile = {
  id: string
  file: File
}

type Props = {
  open: boolean
  maxTotalBytes: number
  submitting?: boolean
  onClose: () => void
  onSubmit: (files: File[], title: string | null) => Promise<void>
}

function formatSize(sizeBytes: number): string {
  if (sizeBytes < 1024) return `${sizeBytes} B`
  if (sizeBytes < 1024 * 1024) return `${(sizeBytes / 1024).toFixed(1)} KB`
  return `${(sizeBytes / (1024 * 1024)).toFixed(1)} MB`
}

function reorder<T>(items: T[], fromIndex: number, toIndex: number): T[] {
  const next = [...items]
  const [moved] = next.splice(fromIndex, 1)
  next.splice(toIndex, 0, moved)
  return next
}

export function TranscribeAudioPanel({
  open,
  maxTotalBytes,
  submitting = false,
  onClose,
  onSubmit,
}: Props) {
  const [title, setTitle] = useState('')
  const [files, setFiles] = useState<TranscribeAudioDraftFile[]>([])
  const [dragIndex, setDragIndex] = useState<number | null>(null)
  const [error, setError] = useState<string | null>(null)
  const inputRef = useRef<HTMLInputElement>(null)

  const totalBytes = files.reduce((sum, item) => sum + item.file.size, 0)

  const addFiles = useCallback(
    (incoming: FileList | File[]) => {
      const list = Array.from(incoming)
      if (!list.length) return
      setError(null)
      setFiles((current) => [
        ...current,
        ...list.map((file) => ({ id: `${file.name}-${file.size}-${crypto.randomUUID()}`, file })),
      ])
    },
    [],
  )

  const handleDropZone = useCallback(
    (event: DragEvent<HTMLDivElement>) => {
      event.preventDefault()
      if (submitting) return
      addFiles(event.dataTransfer.files)
    },
    [addFiles, submitting],
  )

  async function handleSubmit() {
    if (!files.length || submitting) return
    if (totalBytes > maxTotalBytes) {
      setError(`Total size exceeds ${formatSize(maxTotalBytes)}`)
      return
    }
    setError(null)
    try {
      await onSubmit(
        files.map((item) => item.file),
        title.trim() || null,
      )
      setFiles([])
      setTitle('')
      onClose()
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : 'Submit failed')
    }
  }

  if (!open) return null

  return (
    <div className="transcribe-audio-panel" role="dialog" aria-label="Transcribe audio">
      <div className="transcribe-audio-panel-header">
        <div className="transcribe-audio-panel-title-wrap">
          <Mic size={16} aria-hidden />
          <strong>Transcribe audio</strong>
        </div>
        <button type="button" className="transcribe-audio-panel-close" onClick={onClose} aria-label="Close">
          <X size={16} />
        </button>
      </div>
      <p className="transcribe-audio-panel-desc">
        Upload one or more audio files, drag to reorder, then submit. Total limit {formatSize(maxTotalBytes)}.
      </p>
      <label className="transcribe-audio-panel-label">
        Title (optional)
        <input
          type="text"
          value={title}
          disabled={submitting}
          placeholder="Meeting notes"
          onChange={(event) => setTitle(event.target.value)}
        />
      </label>
      <div
        className="transcribe-audio-dropzone"
        onDragOver={(event) => event.preventDefault()}
        onDrop={handleDropZone}
        onClick={() => inputRef.current?.click()}
      >
        Drop audio files here or click to browse
      </div>
      <input
        ref={inputRef}
        type="file"
        multiple
        accept="audio/*,.mp3,.wav,.m4a,.flac,.aac,.ogg,.opus,.webm"
        className="hidden"
        onChange={(event) => {
          if (event.target.files) addFiles(event.target.files)
          event.target.value = ''
        }}
      />
      {files.length ? (
        <ul className="transcribe-audio-file-list">
          {files.map((item, index) => (
            <li
              key={item.id}
              className={`transcribe-audio-file-item${dragIndex === index ? ' transcribe-audio-file-item-dragging' : ''}`}
              draggable={!submitting}
              onDragStart={() => setDragIndex(index)}
              onDragOver={(event) => event.preventDefault()}
              onDrop={() => {
                if (dragIndex == null || dragIndex === index) return
                setFiles((current) => reorder(current, dragIndex, index))
                setDragIndex(null)
              }}
              onDragEnd={() => setDragIndex(null)}
            >
              <GripVertical size={14} aria-hidden className="transcribe-audio-file-grip" />
              <span className="transcribe-audio-file-name">{item.file.name}</span>
              <span className="transcribe-audio-file-size">{formatSize(item.file.size)}</span>
              <button
                type="button"
                className="transcribe-audio-file-remove"
                disabled={submitting}
                aria-label={`Remove ${item.file.name}`}
                onClick={() => setFiles((current) => current.filter((row) => row.id !== item.id))}
              >
                <Trash2 size={14} />
              </button>
            </li>
          ))}
        </ul>
      ) : null}
      <div className="transcribe-audio-panel-footer">
        <span className="transcribe-audio-panel-total">
          {files.length ? `${files.length} file(s) · ${formatSize(totalBytes)}` : 'No files selected'}
        </span>
        <button
          type="button"
          className="transcribe-audio-submit-btn"
          disabled={submitting || !files.length || totalBytes > maxTotalBytes}
          onClick={() => void handleSubmit()}
        >
          {submitting ? <LoadingSpinner size="sm" /> : null}
          <span>{submitting ? 'Submitting…' : 'Start transcription'}</span>
        </button>
      </div>
      {error ? <p className="transcribe-audio-panel-error">{error}</p> : null}
    </div>
  )
}
