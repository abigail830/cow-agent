import { BotMessageSquare, Boxes, FolderOpen, Plug } from 'lucide-react'
import { NavLink } from 'react-router-dom'
import {
  agentChatPath,
  agentDocumentsPath,
  agentHubPath,
  agentIntegrationsPath,
  HUB_TARGET_CHAT_STORAGE_KEY,
} from '../lib/chatRoutes'

type Props = {
  collapsed: boolean
  agentId: string | null
  activeChatId?: string | null
}

function navItemClass(collapsed: boolean, isActive: boolean): string {
  return `agent-nav-item ${isActive ? 'agent-nav-item-active' : ''} ${
    collapsed ? 'agent-nav-item-collapsed' : ''
  }`
}

export function SidebarUtilityNav({ collapsed, agentId, activeChatId }: Props) {
  if (!agentId) return null

  const chatPath = agentChatPath(agentId)
  const documentsPath = agentDocumentsPath(agentId)
  const integrationsPath = agentIntegrationsPath(agentId)
  const hubPath = agentHubPath(agentId)

  return (
    <div className="agent-sidebar-primary-nav">
      <ul
        className={`agent-sidebar-utility-list${collapsed ? ' agent-sidebar-utility-list-collapsed' : ''}`}
      >
        <li>
          <NavLink
            to={chatPath}
            end
            title={collapsed ? 'Work' : undefined}
            className={({ isActive }) => navItemClass(collapsed, isActive)}
          >
            <BotMessageSquare
              className="h-[1.375rem] w-[1.375rem] shrink-0"
              strokeWidth={1.75}
              aria-hidden="true"
            />
            {!collapsed ? <span className="agent-nav-label">Work</span> : null}
          </NavLink>
        </li>
        <li>
          <NavLink
            to={documentsPath}
            title={collapsed ? 'Artifacts' : undefined}
            className={({ isActive }) => navItemClass(collapsed, isActive)}
          >
            <Boxes
              className="h-[1.375rem] w-[1.375rem] shrink-0"
              strokeWidth={1.75}
              aria-hidden="true"
            />
            {!collapsed ? <span className="agent-nav-label">Artifacts</span> : null}
          </NavLink>
        </li>
        <li>
          <NavLink
            to={integrationsPath}
            title={collapsed ? 'Integrations' : undefined}
            className={({ isActive }) => navItemClass(collapsed, isActive)}
          >
            <Plug
              className="h-[1.375rem] w-[1.375rem] shrink-0"
              strokeWidth={1.75}
              aria-hidden="true"
            />
            {!collapsed ? <span className="agent-nav-label">Integrations</span> : null}
          </NavLink>
        </li>
        <li>
          <NavLink
            to={hubPath}
            title={collapsed ? 'Document Hub' : undefined}
            className={({ isActive }) => navItemClass(collapsed, isActive)}
            onClick={() => {
              if (activeChatId) {
                try {
                  sessionStorage.setItem(HUB_TARGET_CHAT_STORAGE_KEY, activeChatId)
                } catch {
                  /* ignore */
                }
              }
            }}
          >
            <FolderOpen
              className="h-[1.375rem] w-[1.375rem] shrink-0"
              strokeWidth={1.75}
              aria-hidden="true"
            />
            {!collapsed ? <span className="agent-nav-label">Document Hub</span> : null}
          </NavLink>
        </li>
      </ul>
    </div>
  )
}
