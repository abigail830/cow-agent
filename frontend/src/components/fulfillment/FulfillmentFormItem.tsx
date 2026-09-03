import { useCallback, useEffect, useState } from 'react'
import { api } from '../../api/client'
import { formatApiError } from '../../lib/apiErrorMessage'
import {
  datetimeLocalToIso,
  formatDatetimeDisplay,
  FULFILLMENT_STATUS_LABELS,
  fulfillmentFormSummary,
  isoToDatetimeLocal,
  productDisplayLabel,
} from '../../lib/fulfillmentForms'
import type { FulfillmentForm, FulfillmentFormPayload } from '../../types/fulfillmentForms'
import { FormField, ReadonlyValue } from './FulfillmentFormFields'

type Props = {
  form: FulfillmentForm
  index: number
  chatId: string
  defaultOpen?: boolean
  onUpdate: (next: FulfillmentForm) => void
}

function statusBagelClass(status: FulfillmentForm['status']): string {
  if (status === 'editing') {
    return 'proposal-draft-bagel ff-bagel-review'
  }
  if (status === 'activated' || status === 'confirmed') {
    return 'proposal-draft-bagel proposal-draft-bagel-true'
  }
  if (status === 'rejected') {
    return 'proposal-draft-bagel ff-bagel-cancelled'
  }
  return 'proposal-draft-bagel'
}

export function FulfillmentFormItem({
  form,
  index,
  chatId,
  defaultOpen = false,
  onUpdate,
}: Props) {
  const [expanded, setExpanded] = useState(defaultOpen)
  const [draft, setDraft] = useState<FulfillmentFormPayload>(form.payload)
  const [dirty, setDirty] = useState(false)
  const [action, setAction] = useState<'save' | 'confirm' | 'cancel' | null>(null)
  const [actionError, setActionError] = useState<string | null>(null)

  useEffect(() => {
    setExpanded(defaultOpen)
  }, [defaultOpen, form.form_id])

  useEffect(() => {
    setDraft(form.payload)
    setDirty(false)
    setActionError(null)
  }, [form.form_id, form.fingerprint, form.status, form.payload])

  const editable = form.status === 'editing'
  const busy = action !== null
  const summary = fulfillmentFormSummary(form, index)
  const simulation = form.context.simulation

  const updateField = useCallback((key: keyof FulfillmentFormPayload, value: string | number) => {
    setDraft((prev) => ({ ...prev, [key]: value }))
    setDirty(true)
    setActionError(null)
  }, [])

  const handleSave = async () => {
    setAction('save')
    setActionError(null)
    try {
      const result = await api.patchFulfillmentForm(chatId, form.form_id, draft)
      onUpdate(result.form)
      setDirty(false)
    } catch (e) {
      setActionError(formatApiError(e, '保存失败'))
    } finally {
      setAction(null)
    }
  }

  const handleConfirm = async () => {
    setAction('confirm')
    setActionError(null)
    try {
      if (dirty) {
        const patched = await api.patchFulfillmentForm(chatId, form.form_id, draft)
        onUpdate(patched.form)
        setDirty(false)
      }
      const result = await api.confirmFulfillmentForm(chatId, form.form_id)
      onUpdate(result.form)
    } catch (e) {
      setActionError(formatApiError(e, '生效失败'))
    } finally {
      setAction(null)
    }
  }

  const handleCancel = async () => {
    setAction('cancel')
    setActionError(null)
    try {
      const result = await api.rejectFulfillmentForm(chatId, form.form_id)
      onUpdate(result.form)
      setDirty(false)
    } catch (e) {
      setActionError(formatApiError(e, '取消失败'))
    } finally {
      setAction(null)
    }
  }

  const canCancel = form.status === 'editing' || form.status === 'activated'

  return (
    <details
      className="proposal-draft-section"
      open={expanded}
      onToggle={(e) => setExpanded(e.currentTarget.open)}
    >
      <summary className="proposal-draft-section-summary">
        <span className="proposal-draft-section-summary-title">{summary.title}</span>
        <span className="proposal-draft-section-badges">
          <span className="proposal-draft-bagel">{summary.qtyLabel}</span>
          <span className={statusBagelClass(form.status)}>
            {FULFILLMENT_STATUS_LABELS[form.status] ?? form.status}
          </span>
        </span>
      </summary>

      <div className="ff-form-body">
        <p className="ff-form-route">{summary.subtitle}</p>

        <div className="ff-form-grid">
          <FormField label="商品" required full>
            <input className="input" value={productDisplayLabel(form)} readOnly disabled={busy} />
          </FormField>

          <FormField label="SKU编码">
            <input
              className="input"
              value={draft.sku_code || draft.product_code}
              readOnly
              disabled={busy}
            />
          </FormField>

          <FormField label="事业部" required>
            {editable ? (
              <input
                className="input"
                value={draft.business_unit}
                onChange={(e) => updateField('business_unit', e.target.value)}
                disabled={busy}
              />
            ) : (
              <ReadonlyValue value={draft.business_unit} />
            )}
          </FormField>

          <FormField label="调拨数量" required>
            {editable ? (
              <input
                className="input"
                type="number"
                min={1}
                value={draft.transfer_qty}
                placeholder="补货数量"
                onChange={(e) => updateField('transfer_qty', Number(e.target.value) || 0)}
                disabled={busy}
              />
            ) : (
              <ReadonlyValue value={draft.transfer_qty} />
            )}
          </FormField>

          <FormField label="初始发货仓" required>
            {editable ? (
              <input
                className="input"
                value={draft.initial_ship_warehouse}
                onChange={(e) => updateField('initial_ship_warehouse', e.target.value)}
                disabled={busy}
              />
            ) : (
              <ReadonlyValue value={draft.initial_ship_warehouse} />
            )}
          </FormField>

          <FormField label="调出逻辑仓" required>
            {editable ? (
              <input
                className="input"
                value={draft.outbound_logic_warehouse}
                onChange={(e) => updateField('outbound_logic_warehouse', e.target.value)}
                disabled={busy}
              />
            ) : (
              <ReadonlyValue value={draft.outbound_logic_warehouse} />
            )}
          </FormField>

          <FormField label="调入逻辑仓" required>
            {editable ? (
              <input
                className="input"
                value={draft.inbound_logic_warehouse}
                onChange={(e) => updateField('inbound_logic_warehouse', e.target.value)}
                disabled={busy}
              />
            ) : (
              <ReadonlyValue value={draft.inbound_logic_warehouse} />
            )}
          </FormField>

          <FormField label="拟定发货时间" required>
            {editable ? (
              <input
                className="input"
                type="datetime-local"
                value={isoToDatetimeLocal(draft.planned_ship_at)}
                onChange={(e) => updateField('planned_ship_at', datetimeLocalToIso(e.target.value))}
                disabled={busy}
              />
            ) : (
              <ReadonlyValue value={formatDatetimeDisplay(draft.planned_ship_at)} />
            )}
          </FormField>

          <FormField label="期望到货时间" required>
            {editable ? (
              <input
                className="input"
                type="datetime-local"
                value={isoToDatetimeLocal(draft.expected_arrival_at)}
                onChange={(e) => updateField('expected_arrival_at', datetimeLocalToIso(e.target.value))}
                disabled={busy}
              />
            ) : (
              <ReadonlyValue value={formatDatetimeDisplay(draft.expected_arrival_at)} />
            )}
          </FormField>
        </div>

        <p className="ff-form-section-label">选填项</p>

        <div className="ff-form-grid">
          <FormField label="商家订单号">
            {editable ? (
              <input
                className="input"
                value={draft.merchant_order_no || ''}
                onChange={(e) => updateField('merchant_order_no', e.target.value)}
                disabled={busy}
              />
            ) : (
              <ReadonlyValue value={draft.merchant_order_no || '—'} />
            )}
          </FormField>

          <FormField label="来源单号">
            {editable ? (
              <input
                className="input"
                value={draft.source_order_no || ''}
                onChange={(e) => updateField('source_order_no', e.target.value)}
                disabled={busy}
              />
            ) : (
              <ReadonlyValue value={draft.source_order_no || '—'} />
            )}
          </FormField>

          <FormField label="中转仓">
            {editable ? (
              <input
                className="input"
                value={draft.transit_warehouse || '-'}
                onChange={(e) => updateField('transit_warehouse', e.target.value)}
                disabled={busy}
              />
            ) : (
              <ReadonlyValue value={draft.transit_warehouse || '—'} />
            )}
          </FormField>

          <FormField label="温区属性">
            {editable ? (
              <input
                className="input"
                value={draft.temp_zone || '常温'}
                onChange={(e) => updateField('temp_zone', e.target.value)}
                disabled={busy}
              />
            ) : (
              <ReadonlyValue value={draft.temp_zone || '—'} />
            )}
          </FormField>

          <FormField label="特殊运输备注" full>
            {editable ? (
              <textarea
                className="textarea"
                rows={3}
                value={draft.shipping_remark || ''}
                placeholder="如防潮、指定承运商等"
                onChange={(e) => updateField('shipping_remark', e.target.value)}
                disabled={busy}
              />
            ) : (
              <ReadonlyValue value={draft.shipping_remark || '—'} />
            )}
          </FormField>
        </div>

        <div className="ff-form-meta">
          <span>调出 {form.context.from_site_code || '—'}</span>
          <span>调入 {form.context.to_site_code || '—'}</span>
          {simulation?.stock_rate_before_pct != null && simulation?.stock_rate_after_pct != null ? (
            <span>
              调后备货率 {simulation.stock_rate_before_pct.toFixed(1)}% →{' '}
              {simulation.stock_rate_after_pct.toFixed(1)}%
            </span>
          ) : null}
        </div>

        {form.fulfillment_item?.transfer_order_no ? (
          <p className="ff-form-success">调拨单号：{String(form.fulfillment_item.transfer_order_no)}</p>
        ) : null}

        {actionError ? <p className="ff-form-error">{actionError}</p> : null}

        {editable ? (
          <div className="ff-form-actions">
            <button type="button" className="btn btn-ghost" onClick={() => void handleSave()} disabled={busy || !dirty}>
              {action === 'save' ? '保存中…' : '保存修改'}
            </button>
            <button type="button" className="btn btn-secondary" onClick={() => void handleCancel()} disabled={busy}>
              {action === 'cancel' ? '处理中…' : '取消'}
            </button>
            <button type="button" className="btn btn-primary" onClick={() => void handleConfirm()} disabled={busy}>
              {action === 'confirm' ? '处理中…' : '确认生效'}
            </button>
          </div>
        ) : canCancel ? (
          <div className="ff-form-actions">
            <button type="button" className="btn btn-secondary" onClick={() => void handleCancel()} disabled={busy}>
              {action === 'cancel' ? '处理中…' : '取消'}
            </button>
          </div>
        ) : null}
      </div>
    </details>
  )
}
