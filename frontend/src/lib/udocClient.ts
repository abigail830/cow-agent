import { UDocClient } from '@docmentis/udoc-viewer'

export function udocAssetsBaseUrl(): string {
  if (typeof window === 'undefined') return '/udoc/'
  return `${window.location.origin}/udoc/`
}

let clientPromise: Promise<UDocClient> | null = null

/** Idempotent: starts WASM/worker download as early as possible. */
export function warmUdocClient(): Promise<UDocClient> {
  if (typeof window === 'undefined') {
    return Promise.reject(new Error('UDoc is browser-only'))
  }
  if (!clientPromise) {
    clientPromise = UDocClient.create({
      disableUpdateCheck: true,
      baseUrl: udocAssetsBaseUrl(),
    })
  }
  return clientPromise
}

export function getUdocClient(): Promise<UDocClient> {
  return warmUdocClient()
}
