import { useCallback, useState } from 'react'
import type { ArtifactSpec } from '../types/artifact'
import { readArtifactPanelWidth } from '../components/ArtifactPanelShell'
import {
  shouldOpenArtifactSidePanel,
  shouldOpenProposalPanel,
} from '../lib/artifactRegistry'
import type { AgentChatSession } from '../lib/agentChatSession'

type PatchSession = (
  agentId: string,
  patch:
    | Partial<AgentChatSession>
    | ((session: AgentChatSession) => Partial<AgentChatSession>),
) => void

type Options = {
  selectedId: string | null
  agentSlug: string | null | undefined
  expandedArtifact: ArtifactSpec | null
  patchSession: PatchSession
  onExpandProposalPanel: () => void
  onCloseOverlayPanels?: () => void
}

export function useArtifactPanel({
  selectedId,
  agentSlug,
  expandedArtifact,
  patchSession,
  onExpandProposalPanel,
  onCloseOverlayPanels,
}: Options) {
  const [panelWidth, setPanelWidth] = useState(readArtifactPanelWidth)

  const handleExpandArtifact = useCallback(
    (spec: ArtifactSpec) => {
      if (!selectedId) return

      if (shouldOpenProposalPanel(spec, agentSlug)) {
        onExpandProposalPanel()
        onCloseOverlayPanels?.()
        return
      }

      if (shouldOpenArtifactSidePanel(spec)) {
        patchSession(selectedId, { expandedArtifact: spec })
        onCloseOverlayPanels?.()
      }
    },
    [agentSlug, onCloseOverlayPanels, onExpandProposalPanel, patchSession, selectedId],
  )

  const closeArtifactPanel = useCallback(() => {
    if (!selectedId) return
    patchSession(selectedId, { expandedArtifact: null })
  }, [patchSession, selectedId])

  const sidePanelOpen = expandedArtifact != null && shouldOpenArtifactSidePanel(expandedArtifact)

  return {
    expandedArtifact,
    handleExpandArtifact,
    closeArtifactPanel,
    panelWidth,
    setPanelWidth,
    sidePanelOpen,
  }
}
