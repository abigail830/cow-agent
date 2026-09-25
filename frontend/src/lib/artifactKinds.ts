import type { ArtifactKind, ArtifactSpec } from '../types/artifact'

export function isDiagramArtifact(spec: ArtifactSpec): boolean {
  return spec.kind === 'diagram_svg'
}

export function isSlideDeckArtifact(spec: ArtifactSpec): boolean {
  return spec.kind === 'slide_deck'
}

export function isContentDocumentArtifact(spec: ArtifactSpec): boolean {
  return spec.kind === 'content_document'
}

export function isAudioTranscriptArtifact(spec: ArtifactSpec): boolean {
  return spec.kind === 'audio_transcript'
}

/** Download-first chat artifacts rendered as inline cowork-style cards. */
export function isInlineDownloadArtifact(spec: ArtifactSpec): boolean {
  return spec.kind === 'proposal_word' || spec.kind === 'proposal_document'
}

const UDOC_FORMATS = new Set(['pptx', 'docx', 'pdf'])

function contentDocumentFormat(spec: ArtifactSpec): string {
  return (spec.format || '').toLowerCase()
}

function contentDocumentFilename(spec: ArtifactSpec): string {
  return (spec.filename || '').toLowerCase()
}

/** Markdown content_document that can open as a rendered preview in the side panel. */
export function isMarkdownPreviewableArtifact(spec: ArtifactSpec): boolean {
  if (isAudioTranscriptArtifact(spec)) {
    return (
      spec.job_status === 'ready' &&
      (Boolean(spec.content?.trim()) || Boolean(spec.download_url?.trim() || spec.preview_url?.trim()))
    )
  }
  if (!isContentDocumentArtifact(spec)) return false
  const format = contentDocumentFormat(spec)
  const name = contentDocumentFilename(spec)
  const isMd = format === 'markdown' || format === 'md' || name.endsWith('.md')
  if (!isMd) return false
  return Boolean(spec.content?.trim()) || Boolean(spec.download_url?.trim())
}

/** Office/PDF content_document that can open in the udoc side panel. */
export function isUdocPreviewableArtifact(spec: ArtifactSpec): boolean {
  if (!isContentDocumentArtifact(spec)) return false
  if (!spec.download_url?.trim()) return false
  const format = contentDocumentFormat(spec)
  if (UDOC_FORMATS.has(format)) return true
  const name = contentDocumentFilename(spec)
  return name.endsWith('.pptx') || name.endsWith('.docx') || name.endsWith('.pdf')
}

export function isProposalArtifact(spec: ArtifactSpec): boolean {
  return spec.kind.startsWith('proposal_')
}

export function isSidePanelArtifact(spec: ArtifactSpec): boolean {
  return (
    isDiagramArtifact(spec) ||
    isSlideDeckArtifact(spec) ||
    isUdocPreviewableArtifact(spec) ||
    isMarkdownPreviewableArtifact(spec) ||
    (isAudioTranscriptArtifact(spec) && isMarkdownPreviewableArtifact(spec))
  )
}

export type SidePanelArtifactKind = Extract<
  ArtifactKind,
  'diagram_svg' | 'slide_deck' | 'content_document'
>

export function getSidePanelArtifactKind(spec: ArtifactSpec): SidePanelArtifactKind | null {
  if (isDiagramArtifact(spec)) return 'diagram_svg'
  if (isSlideDeckArtifact(spec)) return 'slide_deck'
  if (isUdocPreviewableArtifact(spec) || isMarkdownPreviewableArtifact(spec)) return 'content_document'
  return null
}

const FORMAT_LABELS: Record<string, string> = {
  html: 'HTML',
  slidev: 'Slidev',
  markdown: 'Markdown',
  docx: 'Word',
  pptx: 'PowerPoint',
  pdf: 'PDF',
  svg: 'SVG',
}

/** Secondary line on inline artifact cards (e.g. "Slides · HTML"). */
export function artifactCardSubtitle(spec: ArtifactSpec): string {
  const formatLabel = FORMAT_LABELS[spec.format] ?? spec.format.toUpperCase()
  if (isSlideDeckArtifact(spec)) return `Slides · ${formatLabel}`
  if (isDiagramArtifact(spec)) return `Diagram · ${formatLabel}`
  if (isAudioTranscriptArtifact(spec)) {
    const status = spec.job_status === 'running' ? 'Transcribing' : spec.job_status === 'failed' ? 'Failed' : 'Transcript'
    return `Audio · ${status}`
  }
  if (isContentDocumentArtifact(spec)) return `Document · ${formatLabel}`
  if (spec.kind === 'proposal_preview') return 'Proposal · Preview'
  if (spec.kind.startsWith('proposal_')) return `Proposal · ${formatLabel}`
  return formatLabel
}
