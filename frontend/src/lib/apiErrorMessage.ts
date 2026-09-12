export function formatApiError(raw: unknown, fallback: string): string {
  const text = raw instanceof Error ? raw.message : fallback
  try {
    const parsed = JSON.parse(text) as { detail?: unknown }
    if (typeof parsed.detail === 'string') {
      if (parsed.detail === 'Not Found') {
        return 'API resource not found. If you recently updated the code, restart the backend (./scripts/stop.sh && ./scripts/start.sh).'
      }
      return parsed.detail
    }
    if (Array.isArray(parsed.detail)) {
      return parsed.detail.map((item) => JSON.stringify(item)).join('; ')
    }
  } catch {
    /* keep text */
  }
  if (text === 'Failed to fetch') {
    return 'Could not reach the server. Check that the backend is running and try again.'
  }
  return text || fallback
}
