/** API origin for production; empty in local dev (Vite proxies /api). */
const raw = (import.meta.env.VITE_API_BASE_URL as string | undefined)?.trim() ?? ''

export const API_ORIGIN = raw.replace(/\/$/, '')

/** e.g. `/api/v1` locally or `https://backend.example.com/api/v1` in production. */
export const API_V1 = API_ORIGIN ? `${API_ORIGIN}/api/v1` : '/api/v1'

export function resolveApiPath(path: string): string {
  if (path.startsWith('http://') || path.startsWith('https://')) return path
  if (path.startsWith('/api/')) {
    return API_ORIGIN ? `${API_ORIGIN}${path}` : path
  }
  if (path.startsWith('/')) {
    return `${API_V1}${path}`
  }
  return `${API_V1}/${path}`
}
