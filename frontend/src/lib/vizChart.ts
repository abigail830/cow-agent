import type { EChartsOption } from 'echarts'
import type { VizSpec } from '../types/viz'

/** Multi-series comparison (bar / line / combo) */
export const VIZ_PALETTE = [
  '#FF9860',
  '#F3C27A',
  '#4E9086',
  '#9CDDD6',
  '#C44C52',
  '#EDBBD0',
] as const

/** Heatmap intensity — orange shades only (low → high) */
export const HEATMAP_ORANGE_SCALE = [
  '#FFF5EE',
  '#FFE8D6',
  '#FFCFA8',
  '#FF9860',
  '#E86A20',
  '#C45C26',
] as const

export function buildVizChartOption(spec: VizSpec): EChartsOption | null {
  if (spec.kind === 'heatmap' && spec.heatmap_rows?.length && spec.heatmap_cols?.length) {
    const data: [number, number, number][] = []
    let max = 0
    spec.heatmap_values?.forEach((row, y) => {
      row.forEach((value, x) => {
        const v = Number(value) || 0
        max = Math.max(max, v)
        data.push([x, y, v])
      })
    })
    return {
      tooltip: { position: 'top' },
      grid: { left: 120, right: 24, top: 48, bottom: 80 },
      xAxis: {
        type: 'category',
        data: spec.heatmap_cols,
        splitArea: { show: true },
        axisLabel: { rotate: 35, fontSize: 10 },
      },
      yAxis: {
        type: 'category',
        data: spec.heatmap_rows,
        splitArea: { show: true },
        axisLabel: { fontSize: 10, width: 110, overflow: 'truncate' },
      },
      visualMap: {
        min: 0,
        max: max || 1,
        calculable: true,
        orient: 'horizontal',
        left: 'center',
        bottom: 0,
        inRange: { color: [...HEATMAP_ORANGE_SCALE] },
      },
      series: [
        {
          type: 'heatmap',
          data,
          label: { show: true, fontSize: 9 },
          emphasis: { itemStyle: { shadowBlur: 6, shadowColor: 'rgba(0,0,0,0.2)' } },
        },
      ],
    }
  }

  if (
    (spec.kind === 'bar' || spec.kind === 'line' || spec.kind === 'combo') &&
    spec.x?.length &&
    spec.series?.length
  ) {
    const hasSecondary = spec.kind === 'combo' && spec.series.some((s) => (s.y_axis_index ?? 0) > 0)
    return {
      color: [...VIZ_PALETTE],
      tooltip: { trigger: 'axis' },
      legend: { bottom: 0, textStyle: { fontSize: 11 } },
      grid: {
        left: 56,
        right: hasSecondary ? 56 : 24,
        top: 24,
        bottom: spec.x.length > 6 ? 64 : 48,
        containLabel: true,
      },
      xAxis: {
        type: 'category',
        data: spec.x,
        axisLabel: {
          fontSize: 10,
          rotate: spec.x.length > 6 ? 35 : 0,
          hideOverlap: true,
        },
      },
      yAxis: hasSecondary
        ? [
            { type: 'value', axisLabel: { fontSize: 10 } },
            { type: 'value', axisLabel: { fontSize: 10 } },
          ]
        : { type: 'value', axisLabel: { fontSize: 10 } },
      series: spec.series.map((s) => ({
        name: s.name,
        type: s.type,
        data: s.data,
        yAxisIndex: s.y_axis_index ?? 0,
        smooth: s.type === 'line',
      })),
    }
  }

  return null
}

export function isChartSpec(spec: VizSpec): boolean {
  return spec.kind !== 'table' && spec.kind !== 'list' && buildVizChartOption(spec) != null
}
