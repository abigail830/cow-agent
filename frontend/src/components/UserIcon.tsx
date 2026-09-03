type Props = {
  className?: string
}

export function UserIcon({ className = 'h-4 w-4' }: Props) {
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
      <circle cx="12" cy="8" r="3.5" />
      <path d="M5.5 19.5c.9-3 3.6-5 6.5-5s5.6 2 6.5 5" />
    </svg>
  )
}
