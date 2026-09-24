import { FileText, Plug } from 'lucide-react'

type Props = {
  collapsed: boolean
  documentsOpen: boolean
  integrationsOpen: boolean
  onOpenDocuments: () => void
  onOpenIntegrations: () => void
}

export function SidebarUtilityNav({
  collapsed,
  documentsOpen,
  integrationsOpen,
  onOpenDocuments,
  onOpenIntegrations,
}: Props) {
  return (
    <div className="agent-sidebar-utility">
      {!collapsed ? (
        <p className="agent-sidebar-utility-heading">Workspace</p>
      ) : null}
      <ul className={`agent-sidebar-utility-list${collapsed ? ' agent-sidebar-utility-list-collapsed' : ''}`}>
        <li>
          <button
            type="button"
            title={collapsed ? 'Chat Documents' : undefined}
            className={`agent-nav-item ${documentsOpen ? 'agent-nav-item-active' : ''} ${
              collapsed ? 'agent-nav-item-collapsed' : ''
            }`}
            onClick={onOpenDocuments}
          >
            <FileText className="h-[1.375rem] w-[1.375rem] shrink-0" strokeWidth={1.75} aria-hidden="true" />
            {!collapsed ? <span className="agent-nav-label">Chat Documents</span> : null}
          </button>
        </li>
        <li>
          <button
            type="button"
            title={collapsed ? 'Integrations' : undefined}
            className={`agent-nav-item ${integrationsOpen ? 'agent-nav-item-active' : ''} ${
              collapsed ? 'agent-nav-item-collapsed' : ''
            }`}
            onClick={onOpenIntegrations}
          >
            <Plug className="h-[1.375rem] w-[1.375rem] shrink-0" strokeWidth={1.75} aria-hidden="true" />
            {!collapsed ? <span className="agent-nav-label">Integrations</span> : null}
          </button>
        </li>
      </ul>
    </div>
  )
}
