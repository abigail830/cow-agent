type Props = {
  className?: string
}

export function VizCloseIcon({ className = 'h-4 w-4' }: Props) {
  return (
    <svg
      className={className}
      viewBox="0 0 16 16"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      aria-hidden
    >
      <path
        d="M4.1 4.1L11.9 11.9M11.9 4.1L4.1 11.9"
        stroke="currentColor"
        strokeWidth="1.4"
        strokeLinecap="round"
      />
    </svg>
  )
}
