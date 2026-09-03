import { type FormEvent, useState } from 'react'
import { Navigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import { formatApiError } from '../lib/apiErrorMessage'

export function LoginPage() {
  const { user, loading, login } = useAuth()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  if (!loading && user) {
    return <Navigate to="/" replace />
  }

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault()
    setSubmitting(true)
    setError(null)
    try {
      await login(email.trim(), password)
    } catch (err) {
      setError(formatApiError(err, '登录失败'))
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="login-page">
      <div className="login-backdrop" aria-hidden="true" />
      <div className="login-card">
        <div className="login-brand">
          <img src="/cow.png" alt="" className="login-brand-icon" width={56} height={56} />
          <h1 className="login-title">Agent Platform</h1>
          <p className="login-subtitle">使用邮箱与密码登录</p>
        </div>
        <form className="login-form" onSubmit={handleSubmit}>
          <label className="login-label" htmlFor="email">
            邮箱
          </label>
          <input
            id="email"
            type="email"
            autoComplete="username"
            className="login-input"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required
          />
          <label className="login-label" htmlFor="password">
            密码
          </label>
          <input
            id="password"
            type="password"
            autoComplete="current-password"
            className="login-input"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
          />
          {error ? <p className="login-error">{error}</p> : null}
          <button type="submit" className="login-submit" disabled={submitting || loading}>
            {submitting ? '登录中…' : '登录'}
          </button>
        </form>
      </div>
    </div>
  )
}
