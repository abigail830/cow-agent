/** Public PNG path for an agent avatar (scheme A: `/agents/{slug}.png`). */
export function agentIconSrc(slug: string | null | undefined): string | null {
  const normalized = slug?.trim()
  if (!normalized) return null
  return `/agents/${encodeURIComponent(normalized)}.png`
}
