import { FileText, Plug } from 'lucide-react'
import { NavLink } from 'react-router-dom'
import { CHAT_DOCUMENTS_PATH, CHAT_INTEGRATIONS_PATH } from '../lib/chatRoutes'

type Props = {
  collapsed: boolean
}

export function SidebarUtilityNav({ collapsed }: Props) {
  return (
    <div className="agent-sidebar-utility">
      {!collapsed ? (
        <p className="agent-sidebar-utility-heading">Workspace</p>
      ) : null}
      <ul className={`agent-sidebar-utility-list${collapsed ? ' agent-sidebar-utility-list-collapsed' : ''}`}>
        <li>
          <NavLink
            to={CHAT_DOCUMENTS_PATH}
            title={collapsed ? 'Chat Documents' : undefined}
            className={({ isActive }) =>
              `agent-nav-item ${isActive ? 'agent-nav-item-active' : ''} ${
                collapsed ? 'agent-nav-item-collapsed' : ''
              }`
            }
          >
            <FileText className="h-[1.375rem] w-[1.375rem] shrink-0" strokeWidth={1.75} aria-hidden="true" />
            {!collapsed ? <span className="agent-nav-label">Chat Documents</span> : null}
          </NavLink>
        </li>
        <li>
          <NavLink
            to={CHAT_INTEGRATIONS_PATH}
            title={collapsed ? 'Integrations' : undefined}
            className={({ isActive }) =>
              `agent-nav-item ${isActive ? 'agent-nav-item-active' : ''} ${
                collapsed ? 'agent-nav-item-collapsed' : ''
              }`
            }
          >
            <Plug className="h-[1.375rem] w-[1.375rem] shrink-0" strokeWidth={1.75} aria-hidden="true" />
            {!collapsed ? <span className="agent-nav-label">Integrations</span> : null}
          </NavLink>
        </li>
      </ul>
    </div>
  )
}
