import type { ArtifactKind, ArtifactSpec } from '../types/artifact'

export function isDiagramArtifact(spec: ArtifactSpec): boolean {
  return spec.kind === 'diagram_svg'
}

export function isSlideDeckArtifact(spec: ArtifactSpec): boolean {
  return spec.kind === 'slide_deck'
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
