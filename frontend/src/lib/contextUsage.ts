import type { ContextUsage } from '../types'

export function parseContextUsage(raw: unknown): ContextUsage | null {
  if (!raw || typeof raw !== 'object') return null
  const data = raw as Record<string, unknown>
  if (
    typeof data.tokens !== 'number' ||
    typeof data.budget_tokens !== 'number' ||
    typeof data.percent !== 'number'
  ) {
    return null
  }
  return {
    tokens: data.tokens,
    budget_tokens: data.budget_tokens,
    percent: data.percent,
  }
}
