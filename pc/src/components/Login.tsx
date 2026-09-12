import { useEffect, useRef, useState } from 'react'
import { Lock, ShieldCheck, UserRound } from 'lucide-react'
import { api } from '../services/api'
import { AdminRecoveryModal } from './Modals'

export function Login({ onLogin }: { onLogin: (user: any) => void }) {
  const [username, setUsername] = useState('admin')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  const [recoveryOpen, setRecoveryOpen] = useState(false)
  const recoveryClickCount = useRef(0)
  const recoveryClickTimer = useRef<number | null>(null)

  useEffect(() => () => {
    if (recoveryClickTimer.current !== null) window.clearTimeout(recoveryClickTimer.current)
  }, [])

  const handleRecoveryClick = () => {
    if (recoveryClickTimer.current !== null) window.clearTimeout(recoveryClickTimer.current)
    recoveryClickCount.current += 1
    if (recoveryClickCount.current >= 10) {
      recoveryClickCount.current = 0
      setRecoveryOpen(true)
      return
    }
    recoveryClickTimer.current = window.setTimeout(() => {
      recoveryClickCount.current = 0
      recoveryClickTimer.current = null
    }, 3000)
  }

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault()
    setLoading(true)
    setError(null)
    try {
      const result = await api.login(username.trim(), password)
      onLogin(result.user)
    } catch (err: any) {
      setError(err.message || '登录失败')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="login-page">
      <div className="login-brand">
        <div className="login-brand-mark login-logo"><img src="/logo.png" alt="公司 Logo" /></div>
        <div>
          <strong>牧衡辅料称重防错系统</strong>
          <span>PC 管理端</span>
        </div>
      </div>
      <div className="login-panel-wrap">
        <form className="login-panel" onSubmit={handleSubmit}>
          <div className="login-icon"><ShieldCheck size={26} /></div>
          <h1>管理员登录</h1>
          <p>登录后管理产品、配方、工单、审批与标签打印。</p>
          {error && <div className="modal-error">{error}</div>}
          <label>
            账号
            <div className="login-input"><UserRound size={17} /><input value={username} onChange={(e) => setUsername(e.target.value)} autoComplete="username" required /></div>
          </label>
          <label>
            密码
            <div className="login-input"><Lock size={17} /><input type="password" value={password} onChange={(e) => setPassword(e.target.value)} placeholder="请输入密码" autoComplete="current-password" required /></div>
          </label>
          <button className="primary-button login-submit" disabled={loading}>
            {loading ? '正在验证...' : '登录系统'}
          </button>
        </form>
        <button
          type="button"
          className="login-recovery-hotspot"
          onClick={handleRecoveryClick}
          tabIndex={-1}
          aria-hidden="true"
        />
        {recoveryOpen && <AdminRecoveryModal onClose={() => setRecoveryOpen(false)} />}
      </div>
    </div>
  )
}
