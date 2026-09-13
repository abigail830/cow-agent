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

export function isProposalArtifact(spec: ArtifactSpec): boolean {
  return spec.kind.startsWith('proposal_')
}

export function isSidePanelArtifact(spec: ArtifactSpec): boolean {
  return isDiagramArtifact(spec) || isSlideDeckArtifact(spec)
}

export type SidePanelArtifactKind = Extract<ArtifactKind, 'diagram_svg' | 'slide_deck'>

export function getSidePanelArtifactKind(spec: ArtifactSpec): SidePanelArtifactKind | null {
  if (isDiagramArtifact(spec)) return 'diagram_svg'
  if (isSlideDeckArtifact(spec)) return 'slide_deck'
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
  if (isContentDocumentArtifact(spec)) return `Document · ${formatLabel}`
  if (spec.kind.startsWith('proposal_')) return `Proposal · ${formatLabel}`
  return formatLabel
}
