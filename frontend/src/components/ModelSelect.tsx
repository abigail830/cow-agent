import type { ModelOption } from '../types'

interface ModelSelectProps {
  value: string | null
  options: ModelOption[]
  onChange: (modelId: string) => void
  disabled?: boolean
}

export function ModelSelect({ value, options, onChange, disabled }: ModelSelectProps) {
  const selectable = options.filter((option) => option.available !== false)
  if (selectable.length === 0 && options.length === 0) return null

  const selected =
    value && selectable.some((option) => option.id === value)
      ? value
      : selectable[0]?.id ?? value ?? options[0]?.id

  return (
    <select
      className="chat-model-select"
      value={selected ?? ''}
      onChange={(event) => onChange(event.target.value)}
      disabled={disabled}
      aria-label="Model"
    >
      {options.map((option) => (
        <option
          key={option.id}
          value={option.id}
          disabled={option.available === false}
        >
          {option.label}
          {option.available === false ? ' (未配置)' : ''}
        </option>
      ))}
    </select>
  )
}
