import { resolveApiPath } from './apiBase'

export async function downloadBinaryUrl(downloadUrl: string, filename: string): Promise<void> {
  const res = await fetch(resolveApiPath(downloadUrl), { credentials: 'include' })
  if (!res.ok) {
    throw new Error(await res.text())
  }
  const blob = await res.blob()
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = filename
  link.rel = 'noopener'
  document.body.appendChild(link)
  link.click()
  link.remove()
  URL.revokeObjectURL(url)
}
