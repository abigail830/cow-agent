import type { ArtifactSpec } from '../types/artifact'
import {
  getSidePanelArtifactKind,
  isProposalArtifact,
  isSidePanelArtifact,
} from './artifactKinds'

export const PROPOSAL_COMPOSER_SLUG = 'proposal-composer'

/** Proposal artifacts on proposal-composer open the live proposal panel, not the artifact side panel. */
export function shouldOpenProposalPanel(
  spec: ArtifactSpec,
  agentSlug: string | null | undefined,
): boolean {
  return agentSlug === PROPOSAL_COMPOSER_SLUG && isProposalArtifact(spec)
}

/** Whether clicking an artifact bubble should open the resizable side panel. */
export function shouldOpenArtifactSidePanel(spec: ArtifactSpec): boolean {
  return isSidePanelArtifact(spec)
}

export function isArtifactExpandedInSidePanel(
  spec: ArtifactSpec,
  expandedArtifactId: string | null | undefined,
): boolean {
  if (!expandedArtifactId) return false
  return spec.artifact_id === expandedArtifactId && isSidePanelArtifact(spec)
}

export { getSidePanelArtifactKind, isProposalArtifact, isSidePanelArtifact }
