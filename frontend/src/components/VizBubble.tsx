import { useEffect, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import * as echarts from 'echarts'
import type { VizSpec } from '../types/viz'
import { buildVizChartOption, isChartSpec } from '../lib/vizChart'
import { VizCloseIcon } from './VizCloseIcon'
import { VizMaximizeIcon } from './VizMaximizeIcon'

type Props = {
  spec: VizSpec
}

function canMaximize(spec: VizSpec): boolean {
  if (isChartSpec(spec)) return true
  if (spec.kind === 'table') {
    return Boolean(spec.columns?.length && spec.rows?.length)
  }
  if (spec.kind === 'list') {
    return Boolean(spec.items?.length)
  }
  return false
}

function scheduleResize(chart: echarts.ECharts) {
  requestAnimationFrame(() => {
    chart.resize()
    requestAnimationFrame(() => chart.resize())
  })
}

function ChartView({ spec, className = 'viz-chart' }: { spec: VizSpec; className?: string }) {
  const ref = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const el = ref.current
    if (!el) return
    const option = buildVizChartOption(spec)
    if (!option) return

    const chart = echarts.init(el, undefined, { renderer: 'canvas' })
    chart.setOption(option)
    scheduleResize(chart)

    const ro = new ResizeObserver(() => chart.resize())
    ro.observe(el)
    if (el.parentElement) {
      ro.observe(el.parentElement)
    }

    return () => {
      ro.disconnect()
      chart.dispose()
    }
  }, [spec, className])

  return <div ref={ref} className={className} role="img" aria-label={spec.title} />
}

function TableView({ spec, expanded = false }: { spec: VizSpec; expanded?: boolean }) {
  const columns = spec.columns ?? []
  const rows = spec.rows ?? []
  if (!columns.length) return <p className="viz-empty">No table data</p>
  return (
    <div className={`viz-table-wrap${expanded ? ' viz-table-wrap-expanded' : ''}`}>
      <table className="viz-table">
        <thead>
          <tr>
            {columns.map((col) => (
              <th key={col.key}>{col.label ?? col.key}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, idx) => (
            <tr key={idx}>
              {columns.map((col) => (
                <td key={col.key}>{String(row[col.key] ?? '')}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function ListView({ spec, expanded = false }: { spec: VizSpec; expanded?: boolean }) {
  const items = spec.items ?? []
  if (!items.length) return <p className="viz-empty">No list items</p>
  return (
    <ul className={`viz-list${expanded ? ' viz-list-expanded' : ''}`}>
      {items.map((item, idx) => (
        <li key={idx} className="viz-list-item">
          <span className="viz-list-title">{item.title}</span>
          {item.subtitle && <span className="viz-list-sub">{item.subtitle}</span>}
          {item.meta && <span className="viz-list-meta">{item.meta}</span>}
        </li>
      ))}
    </ul>
  )
}

function VizContent({ spec, expanded = false }: { spec: VizSpec; expanded?: boolean }) {
  const useTable = spec.kind === 'table'
  const useList = spec.kind === 'list'
  const chartReady = isChartSpec(spec)

  if (useTable) return <TableView spec={spec} expanded={expanded} />
  if (useList) return <ListView spec={spec} expanded={expanded} />
  if (chartReady) {
    return <ChartView spec={spec} className={expanded ? 'viz-chart-maximized' : 'viz-chart'} />
  }
  return <TableView spec={spec} expanded={expanded} />
}

function VizMaximizeOverlay({ spec, onClose }: { spec: VizSpec; onClose: () => void }) {
  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape') onClose()
    }
    document.addEventListener('keydown', onKey)
    const prevOverflow = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    return () => {
      document.removeEventListener('keydown', onKey)
      document.body.style.overflow = prevOverflow
    }
  }, [onClose])

  return createPortal(
    <div className="viz-maximize-overlay" role="dialog" aria-modal="true" aria-label={spec.title}>
      <button type="button" className="viz-maximize-backdrop" aria-label="Close" onClick={onClose} />
      <div className="viz-maximize-panel">
        <div className="viz-maximize-header">
          <h3 className="viz-maximize-title">{spec.title}</h3>
          <button type="button" className="viz-widget-btn" aria-label="Close" onClick={onClose}>
            <VizCloseIcon />
          </button>
        </div>
        <div className="viz-widget-body viz-widget-body-expanded">
          <VizContent spec={spec} expanded />
        </div>
      </div>
    </div>,
    document.body,
  )
}

export function VizBubble({ spec }: Props) {
  const [maximized, setMaximized] = useState(false)
  const maximizable = canMaximize(spec)

  return (
    <>
      <div className="viz-widget-frame">
        <div className="viz-bubble-header">
          <h4 className="viz-bubble-title">{spec.title}</h4>
          <div className="viz-widget-toolbar">
            {spec.fallback && <span className="viz-bubble-badge">Table fallback</span>}
            {spec.truncated && <span className="viz-bubble-badge">Truncated</span>}
            {maximizable && (
              <button
                type="button"
                className="viz-widget-btn"
                aria-label="Maximize"
                title="Maximize"
                onClick={() => setMaximized(true)}
              >
                <VizMaximizeIcon />
              </button>
            )}
          </div>
        </div>
        <div className="viz-widget-body">
          <VizContent spec={spec} />
        </div>
      </div>
      {maximized && maximizable && (
        <VizMaximizeOverlay spec={spec} onClose={() => setMaximized(false)} />
      )}
    </>
  )
}
