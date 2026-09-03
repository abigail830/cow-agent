import type { ReactNode } from 'react'

export function FormField({
  label,
  required = false,
  full = false,
  children,
}: {
  label: string
  required?: boolean
  full?: boolean
  children: ReactNode
}) {
  return (
    <div className={`ff-form-field${full ? ' ff-form-field-full' : ''}`}>
      <label className="field-label">
        {label}
        {required ? ' *' : ''}
      </label>
      {children}
    </div>
  )
}

export function ReadonlyValue({ value }: { value: string | number }) {
  return <div className="ff-readonly-value">{value || '—'}</div>
}
