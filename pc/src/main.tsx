import React from 'react'
import ReactDOM from 'react-dom/client'
import { AppShell } from './layouts/AppShell'
import { Login } from './components/Login'
import { Dashboard } from './pages/Dashboard'
import { AuditLogsPage, LabelsPage, MaterialsPage, SettingsPage, WorkOrdersPage } from './pages/ManagementPages'
import { api } from './services/api'
import './styles/global.css'
import './styles/app.css'

function App() {
  const [page, setPage] = React.useState('dashboard')
  const [user, setUser] = React.useState<any>(() => {
    const saved = localStorage.getItem('milk_user')
    if (!saved) return null
    try {
      const parsed = JSON.parse(saved)
      return parsed?.role === 'admin' ? parsed : null
    } catch {
      return null
    }
  })
  const [checking, setChecking] = React.useState(Boolean(api.hasToken()))

  React.useEffect(() => {
    if (!api.hasToken()) {
      setChecking(false)
      return
    }
    api.getMe()
      .then((currentUser) => {
        if (currentUser.role !== 'admin') {
          throw new Error('普通操作员账号不能登录电脑管理端')
        }
        setUser(currentUser)
      })
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
      case 'audit':
        return <AuditLogsPage />
      case 'settings':
      default:
        return <SettingsPage />
    }
  }

  return (
    <AppShell page={page} onPageChange={setPage} user={user} onLogout={handleLogout} onUserChange={setUser}>
      {renderPage()}
    </AppShell>
  )
}

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
)
