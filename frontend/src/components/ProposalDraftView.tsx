import { useEffect, useRef, useState } from 'react'
import {
  CLIENT_FACT_FIELDS,
  collectFeeTableFootnotes,
  draftBlockKey,
  draftBlockTitle,
  draftExtraTopLevel,
  draftFactsEntries,
  draftRecordList,
  draftSectionFlags,
  draftSectionKey,
  draftSections,
  draftSectionTitle,
  draftTopLevelEntries,
  feeSectionIntroBlock,
  feeSectionTableStyle,
  feeTableBriefBlock,
  formatClientFactFieldValue,
  formatDraftJson,
  isClientFactRecord,
  isCollectionBlocksSection,
  isFeeSection,
  isFeeTableBlock,
  isMarkdownBlockNode,
  isMarkdownBlockSection,
  collectionBlocks,
  markdownBlockContent,
  summarizeFeeRow,
  type FeeTableLayout,
} from '../lib/proposalDraftView'
import { MarkdownContent } from './MarkdownContent'

type Props = {
  draft: Record<string, unknown>
}

function DraftSectionStatusBadges({
  enabled,
  required,
}: {
  enabled: boolean
  required: boolean
}) {
  return (
    <span className="proposal-draft-section-badges">
      <span
        className={`proposal-draft-bagel${enabled ? ' proposal-draft-bagel-true' : ''}`}
        aria-label={`enabled ${enabled}`}
      >
        enabled
      </span>
      <span
        className={`proposal-draft-bagel${required ? ' proposal-draft-bagel-true' : ''}`}
        aria-label={`required ${required}`}
      >
        required
      </span>
    </span>
  )
}

function DraftJsonInfoButton({ value }: { value: unknown }) {
  const [open, setOpen] = useState(false)
  const wrapRef = useRef<HTMLSpanElement>(null)
  const json = formatDraftJson(value)

  useEffect(() => {
    if (!open) return
    const onPointerDown = (event: MouseEvent) => {
      if (!wrapRef.current?.contains(event.target as Node)) {
        setOpen(false)
      }
    }
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') setOpen(false)
    }
    document.addEventListener('mousedown', onPointerDown)
    document.addEventListener('keydown', onKeyDown)
    return () => {
      document.removeEventListener('mousedown', onPointerDown)
      document.removeEventListener('keydown', onKeyDown)
    }
  }, [open])

  if (!json) return null

  return (
    <span ref={wrapRef} className="proposal-draft-json-info-wrap">
      <button
        type="button"
        className="proposal-draft-json-info-btn"
        aria-label="Show raw JSON"
        aria-expanded={open}
        title="Show raw JSON"
        onClick={(event) => {
          event.preventDefault()
          event.stopPropagation()
          setOpen((prev) => !prev)
        }}
        onMouseDown={(event) => event.stopPropagation()}
      >
        i
      </button>
      {open ? (
        <div className="proposal-draft-json-info-popover" role="dialog" aria-label="Raw JSON">
          <pre className="proposal-state-json proposal-draft-section-json">{json}</pre>
        </div>
      ) : null}
    </span>
  )
}

function DraftSectionSummary({
  title,
  flags,
  infoValue,
}: {
  title: string
  flags?: { enabled: boolean; required: boolean }
  infoValue?: unknown
}) {
  return (
    <>
      <span className="proposal-draft-section-summary-title">{title}</span>
      {flags ? <DraftSectionStatusBadges enabled={flags.enabled} required={flags.required} /> : null}
      {infoValue !== undefined ? <DraftJsonInfoButton value={infoValue} /> : null}
    </>
  )
}

function DraftMarkdownBlockBody({ block }: { block: Record<string, unknown> }) {
  const content = markdownBlockContent(block)
  return (
    <div className="proposal-draft-markdown-block-body">
      {content.trim() ? (
        <MarkdownContent
          content={content}
          className="markdown-body proposal-draft-markdown-body"
        />
      ) : (
        <p className="proposal-draft-markdown-empty">No content</p>
      )}
    </div>
  )
}

function DraftFeeRowTextField({ label, text }: { label: string; text: string }) {
  const preview = text.replace(/\s+/g, ' ').trim()
  if (!preview) return null

  return (
    <details className="proposal-draft-fee-row-text">
      <summary className="proposal-draft-fee-row-text-summary">
        <span className="proposal-draft-fee-row-text-label">{label}</span>
        <span className="proposal-draft-fee-row-text-preview">{preview}</span>
      </summary>
      <p className="proposal-draft-fee-row-text-body">{text}</p>
    </details>
  )
}

function FeeRowLayoutSimple({ row }: { row: ReturnType<typeof summarizeFeeRow> }) {
  return (
    <>
      <div className="proposal-draft-fee-row-main">
        {row.sku ? <span className="proposal-draft-fee-row-sku">{row.sku}</span> : null}
        <span className="proposal-draft-fee-row-label">{row.label}</span>
        {row.amount ? (
          <span className="proposal-draft-fee-row-amount">{row.amount}</span>
        ) : (
          <span className="proposal-draft-fee-row-amount proposal-draft-fee-row-amount-missing">
            —
          </span>
        )}
      </div>
      {row.sow ? (
        <div className="proposal-draft-fee-row-texts">
          <DraftFeeRowTextField label="scope" text={row.sow} />
        </div>
      ) : null}
      {row.footnote ? (
        <div className="proposal-draft-fee-row-meta">
          <span className="proposal-draft-fee-row-footnote-flag">has footnote</span>
        </div>
      ) : null}
    </>
  )
}

const FREQUENCY_COLUMN_LABELS: Record<string, string> = {
  monthly: 'Monthly',
  quarterly: 'Quarterly',
  annual: 'Annual',
  once_off: 'Once-off',
}

function FeeRowLayoutFrequency({ row }: { row: ReturnType<typeof summarizeFeeRow> }) {
  const columns = row.frequencyColumns
  return (
    <>
      <div className="proposal-draft-fee-row-main">
        {row.sku ? <span className="proposal-draft-fee-row-sku">{row.sku}</span> : null}
        <span className="proposal-draft-fee-row-label">{row.label}</span>
        {row.totalDisplay ? (
          <span className="proposal-draft-fee-row-amount">{row.totalDisplay}</span>
        ) : (
          <span className="proposal-draft-fee-row-amount proposal-draft-fee-row-amount-missing">
            —
          </span>
        )}
      </div>
      {row.sow ? (
        <div className="proposal-draft-fee-row-texts">
          <DraftFeeRowTextField label="scope" text={row.sow} />
        </div>
      ) : null}
      {columns ? (
        <dl className="proposal-draft-fee-frequency-cols">
          {Object.entries(FREQUENCY_COLUMN_LABELS).map(([key, label]) =>
            columns[key] ? (
              <div key={key} className="proposal-draft-fee-frequency-col">
                <dt>{label}</dt>
                <dd>{columns[key]}</dd>
              </div>
            ) : null,
          )}
        </dl>
      ) : null}
      {row.footnote ? (
        <div className="proposal-draft-fee-row-meta">
          <span className="proposal-draft-fee-row-footnote-flag">has footnote</span>
        </div>
      ) : null}
    </>
  )
}

function FeeRowLayoutOneOffRecurring({ row }: { row: ReturnType<typeof summarizeFeeRow> }) {
  return (
    <>
      <div className="proposal-draft-fee-row-main">
        {row.sku ? <span className="proposal-draft-fee-row-sku">{row.sku}</span> : null}
        <span className="proposal-draft-fee-row-label">{row.label}</span>
      </div>
      {row.sow ? (
        <div className="proposal-draft-fee-row-texts">
          <DraftFeeRowTextField label="scope" text={row.sow} />
        </div>
      ) : null}
      <dl className="proposal-draft-fee-one-off-recurring-cols">
        <div className="proposal-draft-fee-one-off-recurring-col">
          <dt>One-off</dt>
          <dd>{row.onceOffDisplay ?? '—'}</dd>
        </div>
        <div className="proposal-draft-fee-one-off-recurring-col">
          <dt>Recurring</dt>
          <dd>{row.recurringDisplay ?? '—'}</dd>
        </div>
      </dl>
      {row.footnote ? (
        <div className="proposal-draft-fee-row-meta">
          <span className="proposal-draft-fee-row-footnote-flag">has footnote</span>
        </div>
      ) : null}
    </>
  )
}

function DraftFeeTableBody({
  table,
  layout,
}: {
  table: Record<string, unknown>
  layout: FeeTableLayout
}) {
  const briefBlock = feeTableBriefBlock(table)
  const rows = draftRecordList(table.rows)
  const summaries = rows.map((row) => summarizeFeeRow(row, layout))
  const footnotes = collectFeeTableFootnotes(rows)

  return (
    <div className="proposal-draft-fee-table-body">
      {briefBlock ? (
        <section className="proposal-draft-fee-table-brief">
          <h5 className="proposal-draft-root-label">brief</h5>
          <DraftMarkdownBlockBody block={briefBlock} />
        </section>
      ) : null}
      {summaries.length > 0 ? (
        <ul className="proposal-draft-fee-row-list">
          {summaries.map((row) => (
            <li key={row.id} className="proposal-draft-fee-row-item">
              {layout === 'frequency_columns' ? (
                <FeeRowLayoutFrequency row={row} />
              ) : layout === 'one_off_recurring' ? (
                <FeeRowLayoutOneOffRecurring row={row} />
              ) : (
                <FeeRowLayoutSimple row={row} />
              )}
            </li>
          ))}
        </ul>
      ) : (
        <p className="proposal-draft-markdown-empty">No rows</p>
      )}

      {footnotes.length > 0 ? (
        <section className="proposal-draft-fee-footnotes">
          <h5 className="proposal-draft-fee-footnotes-title">Footnotes</h5>
          <ol className="proposal-draft-fee-footnotes-list">
            {footnotes.map((note) => (
              <li key={note}>{note}</li>
            ))}
          </ol>
        </section>
      ) : null}
    </div>
  )
}

function DraftBlockCollapsible({
  block,
  index,
}: {
  block: Record<string, unknown>
  index: number
}) {
  const title = draftBlockTitle(block, index)
  if (isMarkdownBlockNode(block)) {
    return (
      <details className="proposal-draft-section">
        <summary className="proposal-draft-section-summary">
          <DraftSectionSummary title={title} infoValue={block} />
        </summary>
        <DraftMarkdownBlockBody block={block} />
      </details>
    )
  }
  if (isFeeTableBlock(block)) {
    return (
      <details className="proposal-draft-section">
        <summary className="proposal-draft-section-summary">
          <DraftSectionSummary title={title} infoValue={block} />
        </summary>
        <DraftFeeTableBody table={block} layout="simple" />
      </details>
    )
  }
  return <DraftJsonCollapsible title={title} value={block} />
}

function DraftJsonCollapsible({ title, value }: { title: string; value: unknown }) {
  const json = formatDraftJson(value)
  if (!json) return null
  return (
    <details className="proposal-draft-section">
      <summary className="proposal-draft-section-summary">
        <DraftSectionSummary title={title} infoValue={value} />
      </summary>
      <pre className="proposal-state-json proposal-draft-section-json">{json}</pre>
    </details>
  )
}

function ClientFactDraftView({ client }: { client: Record<string, unknown> }) {
  return (
    <details className="proposal-draft-section">
      <summary className="proposal-draft-section-summary">
        <DraftSectionSummary title="client" infoValue={client} />
      </summary>
      <dl className="proposal-draft-fact-fields">
        {CLIENT_FACT_FIELDS.map((field) => {
          const value = formatClientFactFieldValue(client[field])
          const empty = value === '—'
          return (
            <div key={field} className="proposal-draft-fact-field">
              <dt className="proposal-draft-fact-field-label">{field}</dt>
              <dd
                className={`proposal-draft-fact-field-value${empty ? ' proposal-draft-fact-field-value-empty' : ''}`}
              >
                {value}
              </dd>
            </div>
          )
        })}
      </dl>
    </details>
  )
}

function FactGroupDraftView({ name, value }: { name: string; value: unknown }) {
  if (name === 'client' && isClientFactRecord(value)) {
    return <ClientFactDraftView client={value} />
  }
  return <DraftJsonCollapsible title={name} value={value} />
}

function FactsDraftView({ facts }: { facts: Record<string, unknown> }) {
  const entries = draftFactsEntries(facts)

  return (
    <details className="proposal-draft-section">
      <summary className="proposal-draft-section-summary">
        <DraftSectionSummary title="facts" infoValue={facts} />
      </summary>
      <div className="proposal-draft-facts-wrap">
        {entries.length > 0 ? (
          <div className="proposal-draft-section-list proposal-draft-section-list-nested">
            {entries.map(({ key, value }) => (
              <FactGroupDraftView key={key} name={key} value={value} />
            ))}
          </div>
        ) : (
          <p className="proposal-draft-markdown-empty">No facts</p>
        )}
      </div>
    </details>
  )
}

function FeeTableDraftView({
  table,
  layout,
  index,
}: {
  table: Record<string, unknown>
  layout: FeeTableLayout
  index: number
}) {
  const title = draftBlockTitle(table, index)
  return (
    <details className="proposal-draft-section">
      <summary className="proposal-draft-section-summary">
        <DraftSectionSummary title={title} infoValue={table} />
      </summary>
      <DraftFeeTableBody table={table} layout={layout} />
    </details>
  )
}

function FeeSectionDraftView({ section }: { section: Record<string, unknown> }) {
  const tables = draftRecordList(section.tables)
  const introBlock = feeSectionIntroBlock(section)
  const layout = feeSectionTableStyle(section)

  return (
    <div className="proposal-draft-fee-section">
      {introBlock ? <DraftBlockCollapsible block={introBlock} index={0} /> : null}
      {tables.length > 0 ? (
        <section className="proposal-draft-sections-wrap proposal-draft-nested-group">
          <h4 className="proposal-draft-root-label">Fees</h4>
          <div className="proposal-draft-section-list proposal-draft-section-list-nested">
            {tables.map((table, index) => (
              <FeeTableDraftView key={draftBlockKey(table, index)} table={table} layout={layout} index={index} />
            ))}
          </div>
        </section>
      ) : null}
    </div>
  )
}

function CollectionBlocksDraftView({ section }: { section: Record<string, unknown> }) {
  const blocks = collectionBlocks(section)
  if (blocks.length === 0) {
    return <p className="proposal-draft-markdown-empty">No blocks</p>
  }
  return (
    <div className="proposal-draft-collection-blocks">
      {blocks.map((block, index) => (
        <details key={draftBlockKey(block, index)} className="proposal-draft-collection-block">
          <summary className="proposal-draft-collection-block-summary">
            <span className="proposal-draft-collection-block-title">
              {draftBlockTitle(block, index)}
            </span>
            <span className="proposal-draft-collection-block-kind">{String(block.kind ?? 'block')}</span>
          </summary>
          <DraftMarkdownBlockBody block={block} />
        </details>
      ))}
    </div>
  )
}

function DocumentSectionDraftView({
  section,
  index,
}: {
  section: Record<string, unknown>
  index: number
}) {
  const title = draftSectionTitle(section, index)
  const flags = draftSectionFlags(section)
  const summary = (
    <DraftSectionSummary title={title} flags={flags} infoValue={section} />
  )

  if (isFeeSection(section)) {
    return (
      <details className="proposal-draft-section">
        <summary className="proposal-draft-section-summary">{summary}</summary>
        <div className="proposal-draft-fee-section-wrap">
          <FeeSectionDraftView section={section} />
        </div>
      </details>
    )
  }

  if (isMarkdownBlockSection(section)) {
    return (
      <details className="proposal-draft-section">
        <summary className="proposal-draft-section-summary">{summary}</summary>
        <DraftMarkdownBlockBody block={section} />
      </details>
    )
  }

  if (isCollectionBlocksSection(section)) {
    return (
      <details className="proposal-draft-section">
        <summary className="proposal-draft-section-summary">{summary}</summary>
        <CollectionBlocksDraftView section={section} />
      </details>
    )
  }

  const json = formatDraftJson(section)
  if (!json) return null
  return (
    <details className="proposal-draft-section">
      <summary className="proposal-draft-section-summary">{summary}</summary>
      <pre className="proposal-state-json proposal-draft-section-json">{json}</pre>
    </details>
  )
}

export function ProposalDraftView({ draft }: Props) {
  const topLevel = draftTopLevelEntries(draft)
  const extra = draftExtraTopLevel(draft)
  const sections = draftSections(draft)

  return (
    <div className="proposal-draft-view">
      <div className="proposal-draft-section-list">
        {topLevel.map(({ key, value }) =>
          key === 'facts' && isClientFactRecord(value) ? (
            <FactsDraftView key={key} facts={value} />
          ) : (
            <DraftJsonCollapsible key={key} title={key} value={value} />
          ),
        )}

        {extra ? <DraftJsonCollapsible title="extra" value={extra} /> : null}
      </div>

      {sections.length > 0 ? (
        <section className="proposal-draft-sections-wrap">
          <h3 className="proposal-draft-root-label">sections</h3>
          <div className="proposal-draft-section-list">
            {sections.map((section, index) => (
              <DocumentSectionDraftView
                key={draftSectionKey(section, index)}
                section={section}
                index={index}
              />
            ))}
          </div>
        </section>
      ) : null}
    </div>
  )
}
