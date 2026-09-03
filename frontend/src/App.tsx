import { Navigate } from 'react-router-dom'
import { LoadingSpinner } from './components/LoadingSpinner'
import { useAuth } from './context/AuthContext'
import { ChatPage } from './pages/ChatPage'

function ProtectedApp() {
  const { user, loading } = useAuth()

  if (loading) {
    return (
      <div className="auth-loading">
        <LoadingSpinner />
      </div>
    )
  }

  if (!user) {
    return <Navigate to="/login" replace />
  }

  return <ChatPage />
}

export default ProtectedApp
