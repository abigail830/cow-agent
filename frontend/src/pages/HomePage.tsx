import { useCallback, useEffect, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { api } from '../api/client'
import { AgentIcon } from '../components/AgentIcon'
import { LoadingSpinner } from '../components/LoadingSpinner'
import { SidebarUserMenu } from '../components/SidebarUserMenu'
import { formatAgentLabel } from '../lib/agentLabel'
import { formatApiError } from '../lib/apiErrorMessage'
import { greetingForUser } from '../lib/greeting'
import { useAuth } from '../context/AuthContext'
import type { Agent } from '../types'

export function HomePage() {
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const { user, logout } = useAuth()
  const [agents, setAgents] = useState<Agent[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const loadAgents = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const rows = await api.listAgents()
      setAgents(rows)
    } catch (err) {
      setAgents([])
      setError(formatApiError(err, 'Failed to load agents'))
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    if (searchParams.toString()) {
      navigate(`/chat?${searchParams.toString()}`, { replace: true })
    }
  }, [navigate, searchParams])

  useEffect(() => {
    void loadAgents()
  }, [loadAgents])

  const openAgent = (agent: Agent) => {
    navigate(`/chat?agent=${encodeURIComponent(agent.id)}`)
  }

  if (!user) return null

  return (
    <div className="home-page">
      <header className="home-header">
        <button type="button" className="home-brand sidebar-brand" aria-label="Home" onClick={() => navigate('/')}>
          <img src="/cow.png" alt="" className="sidebar-brand-icon" />
          <span className="sidebar-brand-agent">Agent</span>{' '}
          <span className="sidebar-brand-team">Team</span>
        </button>
        <SidebarUserMenu user={user} collapsed={false} onLogout={logout} />
      </header>

      <main className="home-main">
        <div className="home-main-inner">
          <p className="home-greeting">{greetingForUser(user)}</p>
          <p className="home-lead">Choose an agent to start working.</p>

          {loading ? (
            <div className="home-agents-loading">
              <LoadingSpinner size="lg" />
            </div>
          ) : error ? (
            <div className="home-agents-error">
              <p>{error}</p>
              <button type="button" className="btn btn-secondary text-[11px]" onClick={() => void loadAgents()}>
                Retry
              </button>
            </div>
          ) : agents.length === 0 ? (
            <p className="home-agents-empty">
              No agents found. Add a profile under backend/agents/, then restart the backend.
            </p>
          ) : (
            <ul className="home-agents-grid">
              {agents.map((agent) => (
                <li key={agent.id}>
                  <button type="button" className="home-agent-card" onClick={() => openAgent(agent)}>
                    <span className="home-agent-avatar-wrap">
                      <AgentIcon slug={agent.slug} className="home-agent-avatar" />
                    </span>
                    <span className="home-agent-name">{formatAgentLabel(agent)}</span>
                    {agent.description?.trim() ? (
                      <span className="home-agent-description">{agent.description.trim()}</span>
                    ) : null}
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>
      </main>

      <footer className="home-footer">
        <p className="home-tagline">Connect once. Work smarter together.</p>
      </footer>
    </div>
  )
}
