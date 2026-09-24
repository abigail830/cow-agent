import { ArtifactPanelShell } from './ArtifactPanelShell'
import { ArtifactSidePanel } from './ArtifactSidePanel'
import { ContentDocumentPanel } from './ContentDocumentPanel'
import { SlideDeckPanel } from './SlideDeckPanel'
import { getSidePanelArtifactKind } from '../lib/artifactRegistry'
import type { ArtifactSpec } from '../types/artifact'

type Props = {
  open: boolean
  spec: ArtifactSpec | null
  width: number
  onWidthChange: (width: number) => void
  onClose: () => void
}

export function ArtifactPanelContent({
  spec,
  onClose,
}: {
  spec: ArtifactSpec
  onClose: () => void
}) {
  const panelKind = getSidePanelArtifactKind(spec)

  if (panelKind === 'slide_deck') {
    return (
      <aside className="artifact-side-panel artifact-side-panel-open artifact-side-panel-embedded artifact-side-panel-shell-hosted" aria-label={spec.title}>
        <div className="artifact-side-panel-inner">
          <SlideDeckPanel spec={spec} onClose={onClose} />
        </div>
      </aside>
    )
  }

  if (panelKind === 'content_document') {
    return (
      <aside className="artifact-side-panel artifact-side-panel-open artifact-side-panel-embedded artifact-side-panel-shell-hosted" aria-label={spec.title}>
        <div className="artifact-side-panel-inner">
          <ContentDocumentPanel spec={spec} onClose={onClose} />
        </div>
      </aside>
    )
  }

  return <ArtifactSidePanel open spec={spec} embedded onClose={onClose} />
}

export function ArtifactPanelHost({ open, spec, width, onWidthChange, onClose }: Props) {
  return (
    <ArtifactPanelShell open={open} width={width} onWidthChange={onWidthChange}>
      {spec ? <ArtifactPanelContent spec={spec} onClose={onClose} /> : null}
    </ArtifactPanelShell>
  )
}
