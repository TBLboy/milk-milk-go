import React from 'react'
import ReactDOM from 'react-dom/client'
import { AppShell } from './layouts/AppShell'
import { Login } from './components/Login'
import { Dashboard } from './pages/Dashboard'
import { LabelsPage, MaterialsPage, SettingsPage, WorkOrdersPage } from './pages/ManagementPages'
import { api } from './services/api'
import './styles/global.css'
import './styles/app.css'

function App() {
  const [page, setPage] = React.useState('dashboard')
  const [user, setUser] = React.useState<any>(() => {
    const saved = localStorage.getItem('milk_user')
    return saved ? JSON.parse(saved) : null
  })
  const [checking, setChecking] = React.useState(Boolean(api.hasToken()))

  React.useEffect(() => {
    if (!api.hasToken()) {
      setChecking(false)
      return
    }
    api.getMe()
      .then(setUser)
      .catch(() => {
        api.logout()
        setUser(null)
      })
      .finally(() => setChecking(false))
  }, [])

  const handleLogout = () => {
    api.logout()
    setUser(null)
    setPage('dashboard')
  }

  if (checking) return <div className="loading">正在恢复登录状态<span /></div>
  if (!user) return <Login onLogin={setUser} />

  const renderPage = () => {
    switch (page) {
      case 'dashboard':
        return <Dashboard onNavigate={setPage} />
      case 'orders':
        return <WorkOrdersPage />
      case 'approvals':
        return <WorkOrdersPage approvals />
      case 'materials':
        return <MaterialsPage />
      case 'recipes':
        return <MaterialsPage recipesPage />
      case 'labels':
        return <LabelsPage />
      case 'accounts':
        return <SettingsPage accounts />
      case 'settings':
      default:
        return <SettingsPage />
    }
  }

  return (
    <AppShell page={page} onPageChange={setPage} user={user} onLogout={handleLogout}>
      {renderPage()}
    </AppShell>
  )
}

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
)
