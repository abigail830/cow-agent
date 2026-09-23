export type PageIndexData = {
  layouts?: PageIndexLayout[]
  external_job_id?: string
}

export type PageIndexLayout = {
  type?: string
  markdownContent?: string
  markdown_content?: string
  cells?: unknown[]
  layouts?: Array<{ text?: string }>
  [key: string]: unknown
}

export function parsePageIndex(raw: string): PageIndexData | null {
  try {
    const parsed = JSON.parse(raw) as PageIndexData
    return parsed && typeof parsed === 'object' ? parsed : null
  } catch {
    return null
  }
}

export function layoutTypeLabel(layout: PageIndexLayout): string {
  return String(layout.type ?? 'block')
}

export function layoutPreviewText(layout: PageIndexLayout): string {
  const type = layoutTypeLabel(layout).toLowerCase()
  if (type === 'table') {
    const cellCount = Array.isArray(layout.cells) ? layout.cells.length : 0
    return cellCount > 0 ? `Table with ${cellCount} cell${cellCount === 1 ? '' : 's'}` : 'Empty table'
  }

  const markdown = layout.markdownContent ?? layout.markdown_content
  if (typeof markdown === 'string' && markdown.trim()) {
    return truncate(markdown.trim(), 280)
  }

  const nested = layout.layouts
  if (Array.isArray(nested)) {
    const text = nested
      .map((item) => (typeof item?.text === 'string' ? item.text : ''))
      .join('')
      .trim()
    if (text) return truncate(text, 280)
  }

  return 'No preview text'
}

function truncate(value: string, max: number): string {
  if (value.length <= max) return value
  return `${value.slice(0, max)}…`
}
