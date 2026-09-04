import type { ModelOption } from '../types'

interface ModelSelectProps {
  value: string | null
  options: ModelOption[]
  onChange: (modelId: string) => void
  disabled?: boolean
}

export function ModelSelect({ value, options, onChange, disabled }: ModelSelectProps) {
  if (options.length === 0) return null

  const selected = value && options.some((option) => option.id === value)
    ? value
    : options[0]?.id

  return (
    <select
      className="chat-model-select"
      value={selected ?? ''}
      onChange={(event) => onChange(event.target.value)}
      disabled={disabled}
      aria-label="Model"
    >
        {options.map((option) => (
          <option key={option.id} value={option.id}>
            {option.label}
          </option>
        ))}
      </select>
  )
}
