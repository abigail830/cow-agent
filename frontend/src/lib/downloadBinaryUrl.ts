import { resolveApiPath, toSameOriginApiUrl } from './apiBase'

/**
 * Download a binary via fetch + object URL.
 * Always prefer same-origin `/api` so custom-domain frontends use the Vercel
 * rewrite (avoids CORS on PPTX/DOCX responses from the backend host).
 */
export async function downloadBinaryUrl(downloadUrl: string, filename: string): Promise<void> {
  const url = toSameOriginApiUrl(resolveApiPath(downloadUrl))
  const res = await fetch(url, { credentials: 'include' })
  if (!res.ok) {
    throw new Error(await res.text())
  }
  const blob = await res.blob()
  const objectUrl = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = objectUrl
  link.download = filename
  link.rel = 'noopener'
  document.body.appendChild(link)
  link.click()
  link.remove()
  URL.revokeObjectURL(objectUrl)
}
