type Props = {
  className?: string
}

/** Line-style agent icon for sidebar nav. */
export function AgentIcon({ className = 'h-[18px] w-[18px]' }: Props) {
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
