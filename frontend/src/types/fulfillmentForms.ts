export type FulfillmentFormStatus = 'editing' | 'confirmed' | 'rejected' | 'activated'

export type FulfillmentFormPayload = {
  product_code: string
  business_unit: string
  initial_ship_warehouse: string
  outbound_logic_warehouse: string
  inbound_logic_warehouse: string
  transfer_qty: number
  planned_ship_at: string
  expected_arrival_at: string
  sku_code?: string
  merchant_order_no?: string
  source_order_no?: string
  transit_warehouse?: string
  shipping_remark?: string
  temp_zone?: string
}

export type FulfillmentFormContext = {
  allocation_type?: string
  from_site_code?: string
  to_site_code?: string
  from_site_name?: string
  to_site_name?: string
  adjust_date?: string
  reason?: string
  product_name?: string
  summary?: string
  simulation?: {
    stock_rate_before_pct?: number
    stock_rate_after_pct?: number
    [key: string]: unknown
  }
}

export type FulfillmentForm = {
  form_id: string
  status: FulfillmentFormStatus
  payload: FulfillmentFormPayload
  context: FulfillmentFormContext
  fingerprint: string
  fulfillment_item?: Record<string, unknown> | null
  confirmed_at?: string | null
}

export type FulfillmentFormsResponse = {
  chat_id: string
  forms: FulfillmentForm[]
  count: number
}

export type FulfillmentFormActionResponse = {
  status: string
  form: FulfillmentForm
  fulfillment_item?: Record<string, unknown> | null
}
