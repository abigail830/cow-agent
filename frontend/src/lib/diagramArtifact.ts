import type { ArtifactSpec } from '../types/artifact'
import { isDiagramArtifact, isSlideDeckArtifact } from './artifactKinds'

export { isDiagramArtifact, isProposalArtifact, isSlideDeckArtifact } from './artifactKinds'

/** PNG download URL — uses explicit field or derives from SVG URL. */
export function resolvePngDownloadUrl(spec: ArtifactSpec): string | null {
  if (!isDiagramArtifact(spec)) return null
  if (spec.png_download_url) return spec.png_download_url
  if (!spec.download_url) return null
  const joiner = spec.download_url.includes('?') ? '&' : '?'
  return `${spec.download_url}${joiner}format=png`
}

export function canDownloadDiagramPng(spec: ArtifactSpec): boolean {
  return Boolean(resolvePngDownloadUrl(spec))
}

export function resolvePngFilename(spec: ArtifactSpec): string {
  if (spec.png_filename) return spec.png_filename
  return spec.filename.replace(/\.svg$/i, '.png')
}

export function resolveSlidePdfDownloadUrl(spec: ArtifactSpec): string | null {
  if (!isSlideDeckArtifact(spec)) return null
  if (spec.pdf_download_url) return spec.pdf_download_url
  if (!spec.download_url) return null
  const joiner = spec.download_url.includes('?') ? '&' : '?'
  return `${spec.download_url}${joiner}format=pdf`
}

export function resolveSlidePdfFilename(spec: ArtifactSpec): string {
  if (spec.pdf_filename) return spec.pdf_filename
  return spec.filename.replace(/\.md$/i, '.pdf')
}

export function canDownloadSlidePdf(spec: ArtifactSpec): boolean {
  return Boolean(resolveSlidePdfDownloadUrl(spec))
}
