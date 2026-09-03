type Props = {
  collapsed: boolean
  className?: string
}

/** Sidebar expand/collapse panel icon. */
export function SidebarToggleIcon({ collapsed, className = 'h-[18px] w-[18px]' }: Props) {
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
      <rect x="3" y="4" width="18" height="16" rx="2" />
      <path d={collapsed ? 'M9 4v16' : 'M9 4v16M15 8v8'} />
    </svg>
  )
}
