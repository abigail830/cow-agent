import type { ArtifactSpec } from '../types/artifact'
import { artifactCardSubtitle } from '../lib/artifactKinds'
import { ArtifactCoverIllustration } from './ArtifactCoverIllustration'
import { DiagramArtifactActions } from './DiagramArtifactActions'

type Props = {
  spec: ArtifactSpec
  expanded?: boolean
  onExpand?: (spec: ArtifactSpec) => void
}

export function DiagramArtifactCard({ spec, expanded = false, onExpand }: Props) {
  return (
    <div
      className={`artifact-inline-card diagram-artifact-card${expanded ? ' artifact-inline-card-expanded' : ''}`}
      aria-label={spec.title}
    >
      <ArtifactCoverIllustration kind="diagram" />
      <div className="artifact-inline-card-main">
        <h4 className="artifact-inline-card-title" title={spec.title}>
          {spec.title}
        </h4>
        <p className="artifact-inline-card-subtitle">{artifactCardSubtitle(spec)}</p>
      </div>
      <DiagramArtifactActions
        spec={spec}
        variant="card"
        expanded={expanded}
        onExpand={onExpand}
      />
    </div>
  )
}
