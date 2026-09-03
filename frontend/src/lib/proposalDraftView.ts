const HIDDEN_DRAFT_KEYS = ['version', 'meta'] as const
const TOP_LEVEL_KEYS = ['facts'] as const

export const CLIENT_FACT_FIELDS = [
  'company_name',
  'short_name',
  'address',
  'contract_name',
  'contract_title',
  'contract_email',
] as const

export type ClientFactField = (typeof CLIENT_FACT_FIELDS)[number]

export type DraftTopLevelKey = (typeof TOP_LEVEL_KEYS)[number]

export function formatDraftJson(value: unknown): string {
  if (value === undefined) return ''
  try {
    return JSON.stringify(value, null, 2)
  } catch {
    return String(value)
  }
}

export function draftTopLevelEntries(
  draft: Record<string, unknown>,
): Array<{ key: DraftTopLevelKey; value: unknown }> {
  return TOP_LEVEL_KEYS.filter((key) => key in draft).map((key) => ({
    key,
    value: draft[key],
  }))
}

export function draftFactsEntries(
  facts: Record<string, unknown>,
): Array<{ key: string; value: unknown }> {
  return Object.entries(facts).map(([key, value]) => ({ key, value }))
}

export function isClientFactRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value) && typeof value === 'object' && !Array.isArray(value)
}

export function formatClientFactFieldValue(value: unknown): string {
  if (value === null || value === undefined) return '—'
  if (typeof value === 'string') {
    const trimmed = value.trim()
    return trimmed || '—'
  }
  return String(value)
}

export function draftExtraTopLevel(draft: Record<string, unknown>): Record<string, unknown> | null {
  const extra: Record<string, unknown> = {}
  for (const [key, value] of Object.entries(draft)) {
    if (
      TOP_LEVEL_KEYS.includes(key as DraftTopLevelKey) ||
      HIDDEN_DRAFT_KEYS.includes(key as (typeof HIDDEN_DRAFT_KEYS)[number]) ||
      key === 'document'
    ) {
      continue
    }
    extra[key] = value
  }
  return Object.keys(extra).length > 0 ? extra : null
}

export function draftTemplateId(draft: Record<string, unknown>): string | null {
  const meta = draft.meta
  if (!meta || typeof meta !== 'object' || Array.isArray(meta)) return null
  const templateId = (meta as Record<string, unknown>).template_id
  if (typeof templateId !== 'string') return null
  const trimmed = templateId.trim()
  return trimmed || null
}

export function draftSections(draft: Record<string, unknown>): Record<string, unknown>[] {
  const document = draft.document
  if (!document || typeof document !== 'object' || Array.isArray(document)) return []
  const sections = (document as Record<string, unknown>).sections
  if (!Array.isArray(sections)) return []
  return sections.filter(
    (section): section is Record<string, unknown> =>
      Boolean(section) && typeof section === 'object' && !Array.isArray(section),
  )
}

export function draftSectionTitle(section: Record<string, unknown>, index: number): string {
  const title = section.title
  if (typeof title === 'string' && title.trim()) return title.trim()
  const id = section.id
  if (typeof id === 'string' && id.trim()) return id.trim()
  return `Section ${index + 1}`
}

export function draftSectionFlags(section: Record<string, unknown>): {
  enabled: boolean
  required: boolean
} {
  return {
    enabled: section.enabled === true,
    required: section.required === true,
  }
}

export function draftSectionKey(section: Record<string, unknown>, index: number): string {
  const id = section.id
  if (typeof id === 'string' && id.trim()) return id.trim()
  return `section-${index}`
}

export function isFeeSection(section: Record<string, unknown>): boolean {
  return section.kind === 'fee_section'
}

export function isMarkdownBlockNode(node: Record<string, unknown>): boolean {
  return node.kind === 'markdown_block'
}

/** Document-level markdown section (same shape as fee_section.tables[].brief). */
export function isMarkdownBlockSection(section: Record<string, unknown>): boolean {
  return isMarkdownBlockNode(section)
}

export function isCollectionSection(section: Record<string, unknown>): boolean {
  return section.kind === 'collection'
}

/** collection with markdown_block children (e.g. appendices). */
export function isCollectionBlocksSection(section: Record<string, unknown>): boolean {
  return isCollectionSection(section) && Array.isArray(section.blocks)
}

export function collectionBlocks(section: Record<string, unknown>): Record<string, unknown>[] {
  return draftRecordList(section.blocks)
}

export function markdownBlockContent(section: Record<string, unknown>): string {
  const content = section.content
  return typeof content === 'string' ? content : ''
}

export function draftBlockTitle(block: Record<string, unknown>, index: number): string {
  const title = block.title
  if (typeof title === 'string' && title.trim()) return title.trim()
  const id = block.id
  if (typeof id === 'string' && id.trim()) return id.trim()
  return `Item ${index + 1}`
}

export function draftBlockKey(block: Record<string, unknown>, index: number): string {
  const id = block.id
  if (typeof id === 'string' && id.trim()) return id.trim()
  return `block-${index}`
}

export function draftRecordList(value: unknown): Record<string, unknown>[] {
  if (!Array.isArray(value)) return []
  return value.filter(
    (item): item is Record<string, unknown> =>
      Boolean(item) && typeof item === 'object' && !Array.isArray(item),
  )
}

export function feeSectionIntroBlock(section: Record<string, unknown>): Record<string, unknown> | null {
  const intro = section.intro
  if (!intro || typeof intro !== 'object' || Array.isArray(intro)) return null
  const block = intro as Record<string, unknown>
  if (isMarkdownBlockNode(block)) return block

  const content = typeof block.content === 'string' ? block.content : ''
  const source = block.source
  const hasSource = Boolean(source) && typeof source === 'object' && !Array.isArray(source)
  if (!content.trim() && !hasSource) return null

  const legacyEditState = block.edit_state
  let contentEditState = 'empty'
  if (typeof legacyEditState === 'object' && legacyEditState && !Array.isArray(legacyEditState)) {
    contentEditState = String((legacyEditState as Record<string, unknown>).content || 'empty')
  } else if (legacyEditState === 'source' || content.trim()) {
    contentEditState = 'source'
  }

  return {
    id: typeof block.id === 'string' ? block.id : 'intro',
    kind: 'markdown_block',
    title: typeof block.title === 'string' ? block.title : 'Intro',
    content,
    source: hasSource ? source : {},
    policy: {
      editable: block.editable !== false,
      removable: false,
    },
    edit_state: { content: contentEditState },
  }
}

export function feeSectionHasIntro(section: Record<string, unknown>): boolean {
  return feeSectionIntroBlock(section) !== null
}

export function feeTableBriefBlock(table: Record<string, unknown>): Record<string, unknown> | null {
  const brief = table.brief
  if (!brief || typeof brief !== 'object' || Array.isArray(brief)) return null
  const block = brief as Record<string, unknown>
  return isMarkdownBlockNode(block) ? block : null
}

export function isFeeTableBlock(block: Record<string, unknown>): boolean {
  return block.kind === 'fee_table'
}

export function feeTablePackageId(table: Record<string, unknown>): string | null {
  const source = table.source
  if (!source || typeof source !== 'object' || Array.isArray(source)) return null
  const packageId = (source as Record<string, unknown>).package_id
  return typeof packageId === 'string' && packageId.trim() ? packageId.trim() : null
}

export type FeeRowSummary = {
  id: string
  sku: string
  label: string
  amount: string | null
  sow: string | null
  footnote: string | null
  frequencyColumns: Record<string, string> | null
  totalDisplay: string | null
  onceOffDisplay: string | null
  recurringDisplay: string | null
}

export type FeeTableLayout = 'simple' | 'frequency_columns' | 'one_off_recurring'

export function feeSectionTableStyle(section: Record<string, unknown>): FeeTableLayout {
  const layout = section.fee_layout
  if (!layout || typeof layout !== 'object' || Array.isArray(layout)) return 'simple'
  const style = String((layout as Record<string, unknown>).table_style || 'simple')
    .trim()
    .toLowerCase()
  if (style === 'frequency_columns') return 'frequency_columns'
  if (style === 'one_off_recurring') return 'one_off_recurring'
  return 'simple'
}

function readDisplay(row: Record<string, unknown>): Record<string, unknown> {
  const display = row.display
  if (!display || typeof display !== 'object' || Array.isArray(display)) return {}
  return display as Record<string, unknown>
}

export function summarizeFeeRow(
  row: Record<string, unknown>,
  layout: FeeTableLayout = 'simple',
): FeeRowSummary {
  const source =
    row.source && typeof row.source === 'object' && !Array.isArray(row.source)
      ? (row.source as Record<string, unknown>)
      : {}
  const display = readDisplay(row)

  const sku = typeof source.sku === 'string' ? source.sku.trim() : ''
  const previewPrimary =
    typeof display.preview_primary === 'string' ? display.preview_primary.trim() : ''
  const label = previewPrimary || sku || String(row.id || 'Row')

  const footnote =
    typeof display.footnotes_display === 'string' && display.footnotes_display.trim()
      ? display.footnotes_display.trim()
      : null
  const sow =
    typeof display.scope_of_work_display === 'string' && display.scope_of_work_display.trim()
      ? display.scope_of_work_display.trim()
      : null

  let amount: string | null = null
  let frequencyColumns: Record<string, string> | null = null
  let totalDisplay: string | null = null
  let onceOffDisplay: string | null = null
  let recurringDisplay: string | null = null

  if (layout === 'frequency_columns') {
    const rawCols = display.frequency_columns_display
    if (rawCols && typeof rawCols === 'object' && !Array.isArray(rawCols)) {
      frequencyColumns = {}
      for (const [key, value] of Object.entries(rawCols as Record<string, unknown>)) {
        const text = typeof value === 'string' ? value.trim() : ''
        if (text) frequencyColumns[key] = text
      }
      if (Object.keys(frequencyColumns).length === 0) frequencyColumns = null
    }
    totalDisplay =
      typeof display.total_display === 'string' && display.total_display.trim()
        ? display.total_display.trim()
        : null
    amount = totalDisplay
  } else if (layout === 'one_off_recurring') {
    onceOffDisplay =
      typeof display.once_off_display === 'string' && display.once_off_display.trim()
        ? display.once_off_display.trim()
        : null
    recurringDisplay =
      typeof display.recurring_display === 'string' && display.recurring_display.trim()
        ? display.recurring_display.trim()
        : null
  } else {
    amount =
      typeof display.amount_display === 'string' && display.amount_display.trim()
        ? display.amount_display.trim()
        : null
  }

  return {
    id: typeof row.id === 'string' ? row.id : sku || label,
    sku,
    label,
    amount,
    sow,
    footnote,
    frequencyColumns,
    totalDisplay,
    onceOffDisplay,
    recurringDisplay,
  }
}

export function collectFeeTableFootnotes(rows: Record<string, unknown>[]): string[] {
  const seen = new Set<string>()
  const notes: string[] = []
  for (const row of rows) {
    const display = readDisplay(row)
    const note =
      typeof display.footnotes_display === 'string' ? display.footnotes_display.trim() : ''
    if (!note || seen.has(note)) continue
    seen.add(note)
    notes.push(note)
  }
  return notes
}
