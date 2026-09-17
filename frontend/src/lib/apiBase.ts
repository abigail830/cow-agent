/**
 * API origin for browser fetches.
 *
 * Prefer same-origin `/api` (Vite proxy locally; frontend vercel.json rewrite in
 * production). Absolute `VITE_API_BASE_URL` forces cross-origin calls and breaks
 * binary downloads on custom domains (CORS / cookie SameSite).
 *
 * Mode B (true cross-origin): set BOTH
 *   VITE_API_FORCE_ABSOLUTE=1
 *   VITE_API_BASE_URL=https://your-backend.vercel.app
 * and configure AUTH_COOKIE_SAMESITE=none + CORS_ORIGINS.
 */
const forceAbsolute =
  (import.meta.env.VITE_API_FORCE_ABSOLUTE as string | undefined)?.trim() === '1'
const raw = forceAbsolute
  ? ((import.meta.env.VITE_API_BASE_URL as string | undefined)?.trim() ?? '')
  : ''

export const API_ORIGIN = raw.replace(/\/$/, '')

/** e.g. `/api/v1` (default) or absolute backend when FORCE_ABSOLUTE is on. */
export const API_V1 = API_ORIGIN ? `${API_ORIGIN}/api/v1` : '/api/v1'

/** Strip a baked absolute API origin so the request stays same-origin. */
export function toSameOriginApiUrl(pathOrUrl: string): string {
  const trimmed = pathOrUrl.trim()
  if (!trimmed) return trimmed
  if (trimmed.startsWith('/api/')) return trimmed
  try {
    const u = new URL(trimmed)
    if (u.pathname.startsWith('/api/')) {
      return `${u.pathname}${u.search}`
    }
  } catch {
    // not an absolute URL
  }
  return trimmed
}

export function resolveApiPath(path: string): string {
  if (path.startsWith('http://') || path.startsWith('https://')) {
    // Artifact download_url may already be absolute (legacy). Prefer same-origin.
    if (!API_ORIGIN) return toSameOriginApiUrl(path)
    return path
  }
  if (path.startsWith('/api/')) {
    return API_ORIGIN ? `${API_ORIGIN}${path}` : path
  }
  if (path.startsWith('/')) {
    return `${API_V1}${path}`
  }
  return `${API_V1}/${path}`
}
