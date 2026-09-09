import React from 'react'
import ReactDOM from 'react-dom/client'
import { AppShell } from './layouts/AppShell'
import { Dashboard } from './pages/Dashboard'
import { LabelsPage, MaterialsPage, SettingsPage, WorkOrdersPage } from './pages/ManagementPages'
import './styles/global.css'

function App() {
  const [page, setPage] = React.useState('dashboard')
  const renderPage = () => page === 'dashboard' ? <Dashboard /> : page === 'orders' ? <WorkOrdersPage /> : page === 'approvals' ? <WorkOrdersPage approvals /> : page === 'materials' ? <MaterialsPage /> : page === 'recipes' ? <MaterialsPage recipesPage /> : page === 'labels' ? <LabelsPage /> : page === 'accounts' ? <SettingsPage accounts /> : <SettingsPage />
  return <AppShell page={page} onPageChange={setPage}>{renderPage()}</AppShell>
}
ReactDOM.createRoot(document.getElementById('root')!).render(<React.StrictMode><App /></React.StrictMode>)
