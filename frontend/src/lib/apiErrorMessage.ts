export function formatApiError(raw: unknown, fallback: string): string {
  const text = raw instanceof Error ? raw.message : fallback
  try {
    const parsed = JSON.parse(text) as { detail?: unknown }
    if (typeof parsed.detail === 'string') {
      if (parsed.detail === 'Not Found') {
        return 'API 未找到该资源。若刚更新过代码，请重启 backend（./scripts/stop.sh && ./scripts/start.sh）。'
      }
      return parsed.detail
    }
    if (Array.isArray(parsed.detail)) {
      return parsed.detail.map((item) => JSON.stringify(item)).join('; ')
    }
  } catch {
    /* keep text */
  }
  return text || fallback
}
