import { Gauge } from 'lucide-react'
import type { ContextUsage } from '../types'

type Props = {
  usage: ContextUsage | null
}

function toneClass(percent: number): string {
  if (percent >= 90) return 'chat-context-usage-high'
  if (percent >= 50) return 'chat-context-usage-mid'
  return 'chat-context-usage-low'
}

export function ContextUsageIndicator({ usage }: Props) {
  if (usage == null) return null

  const label = `~${Math.round(usage.percent)}%`
  const title = `Context ~${Math.round(usage.percent)}% (${usage.tokens.toLocaleString()} / ${usage.budget_tokens.toLocaleString()} tokens, estimated)`

  return (
    <span
      className={`chat-context-usage ${toneClass(usage.percent)}`}
      title={title}
      aria-label={title}
    >
      <Gauge size={14} strokeWidth={1.75} aria-hidden="true" />
      <span className="chat-context-usage-label">{label}</span>
    </span>
  )
}
