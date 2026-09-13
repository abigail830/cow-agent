import type { ArtifactSpec } from '../types/artifact'
import { artifactCardSubtitle } from '../lib/artifactKinds'
import { SlideDeckArtifactActions } from './SlideDeckArtifactActions'

type Props = {
  spec: ArtifactSpec
  expanded?: boolean
  onExpand?: (spec: ArtifactSpec) => void
}

export function SlideDeckArtifactCard({ spec, expanded = false, onExpand }: Props) {
  return (
    <div
      className={`artifact-inline-card slide-deck-artifact-card${expanded ? ' artifact-inline-card-expanded' : ''}`}
      aria-label={spec.title}
    >
      <div className="artifact-inline-card-icon slide-deck-artifact-icon" aria-hidden>
        P
      </div>
      <div className="artifact-inline-card-main">
        <h4 className="artifact-inline-card-title" title={spec.title}>
          {spec.title}
        </h4>
        <p className="artifact-inline-card-subtitle">{artifactCardSubtitle(spec)}</p>
      </div>
      <SlideDeckArtifactActions
        spec={spec}
        variant="card"
        expanded={expanded}
        onExpand={onExpand}
      />
    </div>
  )
}
