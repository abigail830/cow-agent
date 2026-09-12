import { useCallback, useEffect, useState } from 'react'
import { ExternalLink, X } from 'lucide-react'
import { useSearchParams } from 'react-router-dom'
import { api } from '../api/client'
import { LoadingSpinner } from './LoadingSpinner'
import type { IntegrationStatus } from '../types'

type Props = {
  open: boolean
  onClose: () => void
}

const PROVIDER_DOCS: Record<string, string> = {
  notion: 'https://developers.notion.com/docs/mcp',
  hubspot:
    'https://developers.hubspot.com/docs/apps/developer-platform/build-apps/integrate-with-the-remote-hubspot-mcp-server',
}

function providerInitial(provider: string): string {
  return provider.slice(0, 1).toUpperCase()
}

function statusLabel(item: IntegrationStatus): string {
  if (item.connected) return 'Connected'
  if (item.configured) return 'Available'
  return 'Not configured'
}

export function IntegrationsDrawer({ open, onClose }: Props) {
  const [searchParams, setSearchParams] = useSearchParams()
  const [integrations, setIntegrations] = useState<IntegrationStatus[]>([])
  const [loading, setLoading] = useState(true)
  const [busyProvider, setBusyProvider] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [notice, setNotice] = useState<string | null>(null)

  const refresh = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const rows = await api.listIntegrations()
      setIntegrations(rows)
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to load integrations'
      setError(
        message === 'Not Found'
          ? 'Integrations API not found — restart the backend to load the new routes.'
          : message,
      )
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    if (!open) return
    void refresh()
  }, [open, refresh])

  useEffect(() => {
    if (!open) return

    const provider = searchParams.get('provider')
    const status = searchParams.get('status')
    const oauthError = searchParams.get('error')
    if (!provider || !status) return

    if (status === 'connected') {
      setNotice(`${provider} connected successfully.`)
    } else if (status === 'error') {
      setError(oauthError || `${provider} connection failed.`)
    }

    setSearchParams(
      (prev) => {
        const next = new URLSearchParams(prev)
        next.delete('provider')
        next.delete('status')
        next.delete('error')
        next.delete('integrations')
        return next
      },
      { replace: true },
    )
    void refresh()
  }, [open, searchParams, setSearchParams, refresh])

  useEffect(() => {
    if (!open) return
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') onClose()
    }
    document.addEventListener('keydown', onKeyDown)
    return () => document.removeEventListener('keydown', onKeyDown)
  }, [open, onClose])

  const handleConnect = async (provider: string) => {
    setBusyProvider(provider)
    setError(null)
    setNotice(null)
    try {
      const { authorize_url: authorizeUrl } = await api.connectIntegration(provider)
      window.location.assign(authorizeUrl)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to start OAuth')
      setBusyProvider(null)
    }
  }

  const handleDisconnect = async (provider: string) => {
    setBusyProvider(provider)
    setError(null)
    try {
      await api.disconnectIntegration(provider)
      setNotice(`${provider} disconnected.`)
      await refresh()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to disconnect')
    } finally {
      setBusyProvider(null)
    }
  }

  return (
    <aside className={`integrations-drawer ${open ? 'integrations-drawer-open' : ''}`} aria-hidden={!open}>
      <div className="integrations-drawer-inner">
        <div className="integrations-drawer-header">
          <div>
            <h2 className="integrations-drawer-title">Integrations</h2>
            <p className="integrations-drawer-subtitle">Connect once, reuse across agents.</p>
          </div>
          <button
            type="button"
            className="integrations-drawer-close"
            onClick={onClose}
            aria-label="Close integrations"
          >
            <X size={18} aria-hidden="true" />
          </button>
        </div>

        {notice ? <div className="integrations-drawer-notice">{notice}</div> : null}
        {error ? <div className="integrations-drawer-error">{error}</div> : null}

        <div className="integrations-drawer-scroll">
          {loading ? (
            <div className="integrations-drawer-loading">
              <LoadingSpinner />
            </div>
          ) : integrations.length === 0 ? (
            <p className="integrations-drawer-empty">No integrations available.</p>
          ) : (
            <ul className="integrations-drawer-list">
              {integrations.map((item) => {
                const docsUrl = PROVIDER_DOCS[item.provider]
                const busy = busyProvider === item.provider
                const connected = item.connected

                return (
                  <li key={item.provider}>
                    <article
                      className={`integration-tile integration-tile-${item.provider}${
                        connected ? ' integration-tile-connected' : ''
                      }`}
                    >
                      <div className="integration-tile-main">
                        <span className={`integration-tile-icon integration-tile-icon-${item.provider}`}>
                          {providerInitial(item.provider)}
                        </span>
                        <div className="integration-tile-copy">
                          <div className="integration-tile-headline">
                            <h3 className="integration-tile-name">{item.display_name}</h3>
                            <span
                              className={`integration-tile-status${
                                connected ? ' integration-tile-status-on' : ''
                              }`}
                            >
                              <span className="integration-tile-status-dot" aria-hidden="true" />
                              {statusLabel(item)}
                            </span>
                          </div>
                          <p className="integration-tile-description">{item.description}</p>
                          {connected && item.account_label ? (
                            <p className="integration-tile-account">{item.account_label}</p>
                          ) : null}
                          {!item.configured ? (
                            <p className="integration-tile-hint">OAuth credentials not configured on server.</p>
                          ) : null}
                        </div>
                      </div>

                      <div className="integration-tile-footer">
                        {connected ? (
                          <button
                            type="button"
                            className="integration-tile-btn integration-tile-btn-ghost"
                            disabled={busy}
                            onClick={() => void handleDisconnect(item.provider)}
                          >
                            Disconnect
                          </button>
                        ) : (
                          <button
                            type="button"
                            className="integration-tile-btn integration-tile-btn-primary"
                            disabled={!item.configured || busy}
                            onClick={() => void handleConnect(item.provider)}
                          >
                            Connect
                          </button>
                        )}
                        {docsUrl ? (
                          <a
                            className="integration-tile-docs"
                            href={docsUrl}
                            target="_blank"
                            rel="noreferrer"
                          >
                            Docs
                            <ExternalLink size={12} aria-hidden="true" />
                          </a>
                        ) : null}
                      </div>
                    </article>
                  </li>
                )
              })}
            </ul>
          )}
        </div>
      </div>
    </aside>
  )
}
