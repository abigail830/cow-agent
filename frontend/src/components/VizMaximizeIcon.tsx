type Props = {
  className?: string
}

export function VizMaximizeIcon({ className = 'h-4 w-4' }: Props) {
  return (
    <svg
      className={className}
      viewBox="0 0 16 16"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      aria-hidden
    >
      <path
        d="M3.5 2.5H6V3.5H4.5V5H3.5V2.5ZM10 2.5H13.5V5H12.5V3.5H10V2.5ZM12.5 11H13.5V13.5H10V12.5H12.5V11ZM3.5 11H4.5V12.5H6V13.5H3.5V11Z"
        fill="currentColor"
      />
    </svg>
  )
}
