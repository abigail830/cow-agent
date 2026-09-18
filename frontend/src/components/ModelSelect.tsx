import { useEffect, useRef, useState } from 'react'
import type { ModelOption } from '../types'

interface ModelSelectProps {
  value: string | null
  options: ModelOption[]
  onChange: (modelId: string) => void
  disabled?: boolean
}

export function ModelSelect({ value, options, onChange, disabled }: ModelSelectProps) {
  const [open, setOpen] = useState(false)
  const rootRef = useRef<HTMLDivElement>(null)

  const selectable = options.filter((option) => option.available !== false)
  const selectedId =
    value && selectable.some((option) => option.id === value)
      ? value
      : selectable[0]?.id ?? value ?? options[0]?.id ?? null

  const selectedOption = options.find((option) => option.id === selectedId) ?? null

  useEffect(() => {
    if (!open) return
    const onDocClick = (event: MouseEvent) => {
      if (rootRef.current && !rootRef.current.contains(event.target as Node)) {
        setOpen(false)
      }
    }
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') setOpen(false)
    }
    document.addEventListener('mousedown', onDocClick)
    document.addEventListener('keydown', onKeyDown)
    return () => {
      document.removeEventListener('mousedown', onDocClick)
      document.removeEventListener('keydown', onKeyDown)
    }
  }, [open])

  if (selectable.length === 0 && options.length === 0) return null

  return (
    <div ref={rootRef} className="chat-model-select-wrap">
      <button
        type="button"
        className={`chat-model-select${open ? ' chat-model-select-open' : ''}`}
        disabled={disabled}
        aria-label="Model"
        aria-haspopup="listbox"
        aria-expanded={open}
        onClick={() => {
          if (disabled) return
          setOpen((prev) => !prev)
        }}
      >
        <span className="chat-model-select-label">
          {selectedOption?.label ?? 'Model'}
        </span>
      </button>
      {open ? (
        <ul className="chat-model-menu" role="listbox" aria-label="Model">
          {options.map((option) => {
            const unavailable = option.available === false
            const selected = option.id === selectedId
            return (
              <li key={option.id} role="presentation">
                <button
                  type="button"
                  role="option"
                  aria-selected={selected}
                  disabled={unavailable}
                  className={`chat-model-menu-item${selected ? ' chat-model-menu-item-selected' : ''}`}
                  onClick={() => {
                    if (unavailable) return
                    onChange(option.id)
                    setOpen(false)
                  }}
                >
                  {selected ? (
                    <span className="chat-model-menu-check" aria-hidden>
                      <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" strokeWidth="2.5">
                        <path d="M5 13l4 4L19 7" />
                      </svg>
                    </span>
                  ) : (
                    <span className="chat-model-menu-check" aria-hidden />
                  )}
                  <span>
                    {option.label}
                    {unavailable ? ' (not configured)' : ''}
                  </span>
                </button>
              </li>
            )
          })}
        </ul>
      ) : null}
    </div>
  )
}
