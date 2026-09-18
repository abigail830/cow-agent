const STORAGE_PREFIX = 'fork-banner:'

export type ForkBannerState = {
  sourceChatId: string
  sourceTitle: string
  /** Message count at fork time; hide banner once the chat grows past this. */
  baselineMessageCount: number
}

export function readForkBanner(chatId: string): ForkBannerState | null {
  try {
    const raw = sessionStorage.getItem(`${STORAGE_PREFIX}${chatId}`)
    if (!raw) return null
    const parsed = JSON.parse(raw) as Partial<ForkBannerState>
    if (!parsed?.sourceChatId) return null
    const baseline = Number(parsed.baselineMessageCount)
    return {
      sourceChatId: String(parsed.sourceChatId),
      sourceTitle: String(parsed.sourceTitle || 'New Chat'),
      baselineMessageCount: Number.isFinite(baseline) ? baseline : 0,
    }
  } catch {
    return null
  }
}

export function writeForkBanner(chatId: string, banner: ForkBannerState): void {
  try {
    sessionStorage.setItem(`${STORAGE_PREFIX}${chatId}`, JSON.stringify(banner))
  } catch {
    /* ignore quota / private mode */
  }
}

export function clearForkBanner(chatId: string): void {
  try {
    sessionStorage.removeItem(`${STORAGE_PREFIX}${chatId}`)
  } catch {
    /* ignore */
  }
}
