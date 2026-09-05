import { useEffect, useState } from 'react'
import { agentIconSrc } from '../lib/agentIcon'

type Props = {
  className?: string
  slug?: string | null
}

function AgentIconFallback({ className = 'h-6 w-6' }: Pick<Props, 'className'>) {
  return (
    <svg
      className={className}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.75"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden
    >
      <path d="M12 3v2" />
      <rect x="5" y="7" width="14" height="11" rx="2" />
      <circle cx="9.5" cy="12" r="1" fill="currentColor" stroke="none" />
      <circle cx="14.5" cy="12" r="1" fill="currentColor" stroke="none" />
      <path d="M9.5 16h5" />
      <path d="M8 7V5a4 4 0 0 1 8 0v2" />
    </svg>
  )
}

/** Agent avatar from `/public/agents/{slug}.png`, with SVG fallback. */
export function AgentIcon({ className = 'h-6 w-6', slug }: Props) {
  const [failed, setFailed] = useState(false)
  const src = agentIconSrc(slug)

  useEffect(() => {
    setFailed(false)
  }, [slug])

  if (src && !failed) {
    return (
      <img
        src={src}
        alt=""
        className={`${className} shrink-0 rounded-full object-cover`}
        aria-hidden
        onError={() => setFailed(true)}
      />
    )
  }

  return <AgentIconFallback className={className} />
}
