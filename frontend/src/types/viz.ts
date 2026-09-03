export type VizKind = 'table' | 'list' | 'bar' | 'line' | 'combo' | 'heatmap'

export type VizColumn = {
  key: string
  label?: string | null
}

export type VizSeries = {
  name: string
  type: 'bar' | 'line'
  data: Array<number | null>
  y_axis_index?: number
}

export type VizListItem = {
  title: string
  subtitle?: string | null
  meta?: string | null
}

export type VizSpec = {
  kind: VizKind
  title: string
  columns?: VizColumn[]
  rows?: Record<string, unknown>[]
  items?: VizListItem[]
  x?: string[]
  series?: VizSeries[]
  heatmap_rows?: string[]
  heatmap_cols?: string[]
  heatmap_values?: number[][]
  fallback?: boolean
  truncated?: boolean
}
