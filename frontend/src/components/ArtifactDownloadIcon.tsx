type Props = {
  className?: string
}

export function ArtifactDownloadIcon({ className = 'h-4 w-4' }: Props) {
  return (
    <svg
      className={className}
      viewBox="0 0 16 16"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      aria-hidden
    >
      <path
        d="M8 2.5V9.17M8 9.17L5.75 6.92M8 9.17L10.25 6.92M3.5 11.5V12.5C3.5 12.7761 3.72386 13 4 13H12C12.2761 13 12.5 12.7761 12.5 12.5V11.5"
        stroke="currentColor"
        strokeWidth="1.25"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  )
}
