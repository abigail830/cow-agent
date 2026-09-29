export const HUB_RESIZE_HANDLE_WIDTH = 6
export const HUB_MIN_FOLDER_WIDTH = 140
export const HUB_MAX_FOLDER_WIDTH = 360
export const HUB_MIN_PREVIEW_WIDTH = 320
export const HUB_MAX_PREVIEW_RATIO = 0.65
export const HUB_MIN_LIST_WIDTH = 260

export const HUB_FOLDER_WIDTH_KEY = 'document-hub-folder-width'
export const HUB_PREVIEW_WIDTH_KEY = 'document-hub-preview-width'
export const HUB_LAST_FOLDER_ID_KEY = 'document-hub:last-folder-id'

export function readStoredHubFolderId(): string | null {
  try {
    return sessionStorage.getItem(HUB_LAST_FOLDER_ID_KEY)
  } catch {
    return null
  }
}

export function storeHubFolderId(folderId: string): void {
  try {
    sessionStorage.setItem(HUB_LAST_FOLDER_ID_KEY, folderId)
  } catch {
    /* ignore */
  }
}

export function readStoredHubWidth(key: string, fallback: number): number {
  try {
    const raw = localStorage.getItem(key)
    if (!raw) return fallback
    const n = Number.parseInt(raw, 10)
    return Number.isFinite(n) ? n : fallback
  } catch {
    return fallback
  }
}

export function storeHubWidth(key: string, value: number): void {
  try {
    localStorage.setItem(key, String(Math.round(value)))
  } catch {
    /* ignore */
  }
}
