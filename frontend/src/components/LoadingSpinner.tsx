type Props = {
  className?: string
  size?: 'sm' | 'md' | 'lg'
}

export function LoadingSpinner({ className = '', size = 'md' }: Props) {
  return (
    <svg
      className={`loading-spinner loading-spinner-${size} ${className}`.trim()}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      aria-hidden
    >
      <path d="M12 2v4" />
      <path d="M12 18v4" opacity="0.3" />
      <path d="m4.93 4.93 2.83 2.83" opacity="0.7" />
      <path d="m16.24 16.24 2.83 2.83" opacity="0.3" />
    </svg>
  )
}
