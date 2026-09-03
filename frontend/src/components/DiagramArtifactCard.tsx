import type { ArtifactSpec } from '../types/artifact'
import { DiagramArtifactActions } from './DiagramArtifactActions'

type Props = {
  spec: ArtifactSpec
  expanded?: boolean
  onExpand?: (spec: ArtifactSpec) => void
}

export function DiagramArtifactCard({ spec, expanded = false, onExpand }: Props) {
  return (
    <div
      className={`diagram-artifact-card${expanded ? ' diagram-artifact-card-expanded' : ''}`}
      aria-label={spec.title}
    >
      <h4 className="diagram-artifact-card-title" title={spec.title}>
        {spec.title}
      </h4>
      <DiagramArtifactActions
        spec={spec}
        variant="card"
        expanded={expanded}
        onExpand={onExpand}
      />
    </div>
  )
}
