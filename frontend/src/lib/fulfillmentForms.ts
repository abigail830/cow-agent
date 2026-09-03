import type { FulfillmentForm, FulfillmentFormStatus } from '../types/fulfillmentForms'

export const FULFILLMENT_STATUS_LABELS: Record<FulfillmentFormStatus, string> = {
  editing: '待审阅',
  confirmed: '已确认',
  rejected: '已取消',
  activated: '已生效',
}

export function parseFulfillmentForms(raw: unknown): FulfillmentForm[] {
  if (!Array.isArray(raw)) return []
  return raw.filter((item): item is FulfillmentForm => {
    if (!item || typeof item !== 'object') return false
    const row = item as FulfillmentForm
    return typeof row.form_id === 'string' && row.payload && typeof row.payload === 'object'
  })
}

export function isoToDatetimeLocal(value: string): string {
  if (!value) return ''
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value.slice(0, 16)
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(date.getHours())}:${pad(date.getMinutes())}`
}

export function datetimeLocalToIso(value: string): string {
  if (!value) return ''
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return date.toISOString().replace('.000', '')
}

export function formatDatetimeDisplay(value: string): string {
  const local = isoToDatetimeLocal(value)
  if (!local) return '—'
  return local.replace('T', ' ')
}

export function fulfillmentFormSummary(form: FulfillmentForm, index: number): {
  title: string
  subtitle: string
  qtyLabel: string
} {
  const ctx = form.context
  const fromName = ctx.from_site_name || ctx.from_site_code || '调出仓'
  const toName = ctx.to_site_name || ctx.to_site_code || '调入仓'
  const alloc = ctx.allocation_type === 'lateral' ? '横向调拨' : '正向补货'
  const qty = form.payload.transfer_qty
  return {
    title: `${index + 1}. ${toName}${alloc}`,
    subtitle: `${fromName} → ${toName}`,
    qtyLabel: `${qty} 件`,
  }
}

export function productDisplayLabel(form: FulfillmentForm): string {
  const name = form.context.product_name
  const code = form.payload.product_code
  if (name && code) return `${name}（${code}）`
  return name || code || '—'
}
