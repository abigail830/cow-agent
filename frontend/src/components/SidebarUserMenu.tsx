import { useEffect, useRef, useState } from 'react'
import { UserIcon } from './UserIcon'
import type { User } from '../types'

function userDisplayName(user: User): string {
  const name = user.name?.trim()
  return name || user.email
}

interface SidebarUserMenuProps {
  user: User | null
  collapsed: boolean
  onLogout: () => void | Promise<void>
}

export function SidebarUserMenu({ user, collapsed, onLogout }: SidebarUserMenuProps) {
  const [open, setOpen] = useState(false)
  const rootRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!open) return
    const onDocClick = (event: MouseEvent) => {
      if (rootRef.current && !rootRef.current.contains(event.target as Node)) {
        setOpen(false)
      }
    }
    document.addEventListener('mousedown', onDocClick)
    return () => document.removeEventListener('mousedown', onDocClick)
  }, [open])

  if (!user) return null

  const displayName = userDisplayName(user)

  return (
    <div className="agent-sidebar-user-wrap" ref={rootRef}>
      <button
        type="button"
        className="agent-sidebar-user-btn"
        onClick={() => setOpen((value) => !value)}
        aria-expanded={open}
        aria-haspopup="menu"
        title={displayName}
      >
        <span className="agent-sidebar-avatar">
          <UserIcon className="h-4 w-4" />
        </span>
        {!collapsed ? <span className="agent-sidebar-display-name">{displayName}</span> : null}
      </button>
      {open ? (
        <div className="agent-sidebar-user-menu" role="menu">
          <button
            type="button"
            role="menuitem"
            className="agent-sidebar-user-menu-item"
            onClick={() => {
              setOpen(false)
              void onLogout()
            }}
          >
            退出登录
          </button>
        </div>
      ) : null}
    </div>
  )
}
