import { useCallback, useEffect, useState } from 'react'
import { Link, Navigate, useSearchParams } from 'react-router-dom'
import { ArrowLeft, ExternalLink } from 'lucide-react'
import { api } from '../api/client'
import { LoadingSpinner } from '../components/LoadingSpinner'
import { useAuth } from '../context/AuthContext'
import type { IntegrationStatus } from '../types'

export function IntegrationsSettingsPage() {
  const { user, loading: authLoading } = useAuth()
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
          ? 'Integrations API not found — restart the backend (`./scripts/restart.sh`) to load the new routes.'
          : message,
      )
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    if (!user) return
    void refresh()
  }, [user, refresh])

  useEffect(() => {
    const provider = searchParams.get('provider')
    const status = searchParams.get('status')
    const oauthError = searchParams.get('error')
    if (!provider || !status) return

    if (status === 'connected') {
      setNotice(`${provider} connected successfully.`)
    } else if (status === 'error') {
      setError(oauthError || `${provider} connection failed.`)
    }

    setSearchParams({}, { replace: true })
    void refresh()
  }, [searchParams, setSearchParams, refresh])

  if (authLoading) {
    return (
      <div className="auth-loading">
        <LoadingSpinner />
      </div>
    )
  }

  if (!user) {
    return <Navigate to="/login" replace />
  }

  const handleConnect = async (provider: string) => {
    setBusyProvider(provider)
    setError(null)
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
    <div className="integrations-page">
      <header className="integrations-header">
        <Link to="/" className="integrations-back-link">
          <ArrowLeft size={16} aria-hidden="true" />
          Back to chat
        </Link>
        <div>
          <h1 className="integrations-title">Integrations</h1>
          <p className="integrations-subtitle">
            Connect external services once per user. Agents with MCP access reuse your connection.
          </p>
        </div>
      </header>

      {notice ? <div className="integrations-notice">{notice}</div> : null}
      {error ? <div className="integrations-error">{error}</div> : null}

      {loading ? (
        <div className="integrations-loading">
          <LoadingSpinner />
        </div>
      ) : (
        <div className="integrations-grid">
          {integrations.filter((item) => item.provider === 'notion').map((item) => (
            <article key={item.provider} className="integration-card">
              <div className="integration-card-head">
                <div>
                  <h2 className="integration-card-title">{item.display_name}</h2>
                  <p className="integration-card-description">{item.description}</p>
                </div>
                <span
                  className={`integration-status-badge ${
                    item.connected ? 'integration-status-badge-connected' : 'integration-status-badge-idle'
                  }`}
                >
                  {item.connected ? 'Connected' : item.configured ? 'Not connected' : 'Not configured'}
                </span>
              </div>

              {item.connected && item.account_label ? (
                <p className="integration-account-label">{item.account_label}</p>
              ) : null}

              {!item.configured ? (
                <p className="integration-hint">
                  Platform OAuth credentials are not configured for this deployment.
                </p>
              ) : null}

              <div className="integration-card-actions">
                {item.connected ? (
                  <button
                    type="button"
                    className="integration-btn integration-btn-secondary"
                    disabled={busyProvider === item.provider}
                    onClick={() => void handleDisconnect(item.provider)}
                  >
                    Disconnect
                  </button>
                ) : (
                  <button
                    type="button"
                    className="integration-btn integration-btn-primary"
                    disabled={!item.configured || busyProvider === item.provider}
                    onClick={() => void handleConnect(item.provider)}
                  >
                    Connect
                  </button>
                )}
                {item.provider === 'notion' ? (
                  <a
                    className="integration-link"
                    href="https://developers.notion.com/docs/mcp"
                    target="_blank"
                    rel="noreferrer"
                  >
                    Docs
                    <ExternalLink size={14} aria-hidden="true" />
                  </a>
                ) : null}
              </div>
            </article>
          ))}
        </div>
      )}
    </div>
  )
}
