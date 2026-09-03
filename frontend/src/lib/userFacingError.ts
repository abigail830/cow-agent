function tryParsePythonDict(text: string): Record<string, unknown> | null {
  const trimmed = text.trim()
  if (!trimmed.startsWith('{') || !trimmed.endsWith('}')) return null
  try {
    const normalized = trimmed
      .replace(/'/g, '"')
      .replace(/\bNone\b/g, 'null')
      .replace(/\bTrue\b/g, 'true')
      .replace(/\bFalse\b/g, 'false')
    const parsed: unknown = JSON.parse(normalized)
    return parsed && typeof parsed === 'object' && !Array.isArray(parsed)
      ? (parsed as Record<string, unknown>)
      : null
  } catch {
    return null
  }
}

function messageFromObject(value: Record<string, unknown>): string | null {
  const nested = value.error
  if (nested && typeof nested === 'object' && !Array.isArray(nested)) {
    const message = (nested as { message?: unknown }).message
    if (typeof message === 'string' && message.trim()) return message.trim()
    const type = (nested as { type?: unknown }).type
    if (typeof type === 'string' && type.trim()) return type.trim()
  }
  if (typeof value.message === 'string' && value.message.trim()) {
    return value.message.trim()
  }
  return null
}

function friendlyMessage(text: string): string {
  const lower = text.toLowerCase()
  if (lower.includes('overloaded_error') || lower.includes('overloaded')) {
    return 'Claude 模型服务繁忙（Overloaded），请稍后重试；若持续失败请检查 Azure 部署与容量。'
  }
  if (lower.includes('internal server error') || lower.includes('api_error')) {
    return 'Claude 模型服务异常（500），请确认 CLAUDE_AZURE_FOUNDRY_MODEL 与 Azure 部署名称一致并稍后重试。'
  }
  if (lower.includes('rate_limit') || lower.includes('rate limit')) {
    return '请求过于频繁，请稍后重试。'
  }
  return text
}

export function formatUserFacingError(raw: unknown, fallback = '请求失败，请稍后重试。'): string {
  if (raw instanceof Error) {
    return formatUserFacingError(raw.message, fallback)
  }
  if (typeof raw === 'string') {
    const trimmed = raw.trim()
    if (!trimmed) return fallback
    const parsed = tryParsePythonDict(trimmed)
    if (parsed) {
      const extracted = messageFromObject(parsed)
      if (extracted) return friendlyMessage(extracted)
    }
    return friendlyMessage(trimmed)
  }
  if (raw && typeof raw === 'object' && !Array.isArray(raw)) {
    const extracted = messageFromObject(raw as Record<string, unknown>)
    if (extracted) return friendlyMessage(extracted)
  }
  return fallback
}
