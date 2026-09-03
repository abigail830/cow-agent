import { useCallback, useMemo, useState } from 'react'
import type { FulfillmentForm } from '../../types/fulfillmentForms'
import { FulfillmentFormItem } from './FulfillmentFormItem'

type Props = {
  chatId: string
  forms: FulfillmentForm[]
  loading?: boolean
  error?: string | null
  onFormsChange: (forms: FulfillmentForm[]) => void
}

export function FulfillmentInlineBlock({
  chatId,
  forms,
  loading = false,
  error = null,
  onFormsChange,
}: Props) {
  const [collapsed, setCollapsed] = useState(false)

  const editingCount = useMemo(
    () => forms.filter((f) => f.status === 'editing').length,
    [forms],
  )

  const firstEditingId = useMemo(
    () => forms.find((f) => f.status === 'editing')?.form_id ?? forms[0]?.form_id,
    [forms],
  )

  const handleFormUpdate = useCallback(
    (updated: FulfillmentForm) => {
      onFormsChange(forms.map((f) => (f.form_id === updated.form_id ? updated : f)))
    },
    [forms, onFormsChange],
  )

  if (forms.length === 0 && !loading && !error) return null

  return (
    <div className="ff-inline-block" aria-label="补录单草案">
      <button
        type="button"
        className="ff-inline-header"
        onClick={() => setCollapsed((value) => !value)}
        aria-expanded={!collapsed}
      >
        <span className="ff-inline-title">补录单草案</span>
        {forms.length > 0 ? (
          <span className="proposal-draft-bagel ff-bagel-review">
            {editingCount > 0 ? `${editingCount} 待审阅` : `${forms.length} 张`}
          </span>
        ) : null}
        <svg
          className={`ff-inline-chevron${collapsed ? '' : ' ff-inline-chevron-open'}`}
          viewBox="0 0 24 24"
          width="16"
          height="16"
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
          aria-hidden
        >
          <path d="m6 9 6 6 6-6" />
        </svg>
      </button>

      {!collapsed ? (
        <div className="ff-inline-body">
          <p className="ff-inline-subtitle">
            方案暂存于会话；确认生效后写入履约中心并生成调拨单
          </p>
          {loading && forms.length === 0 ? (
            <p className="ff-inline-placeholder">加载补录单表单…</p>
          ) : null}
          {error && !loading ? <p className="ff-form-error">{error}</p> : null}
          {forms.length > 0 ? (
            <div className="proposal-draft-section-list">
              {forms.map((form, index) => (
                <FulfillmentFormItem
                  key={form.form_id}
                  form={form}
                  index={index}
                  chatId={chatId}
                  defaultOpen={form.form_id === firstEditingId}
                  onUpdate={handleFormUpdate}
                />
              ))}
            </div>
          ) : null}
        </div>
      ) : null}
    </div>
  )
}
