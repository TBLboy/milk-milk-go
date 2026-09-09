import { useState } from 'react'
import { Lock, ShieldCheck, Store, UserRound } from 'lucide-react'
import { api } from '../services/api'

export function Login({ onLogin }: { onLogin: (user: any) => void }) {
  const [username, setUsername] = useState('admin')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

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
        <div className="login-brand-mark"><Store size={26} /></div>
        <div>
          <strong>牧衡辅料称重防错系统</strong>
          <span>PC 管理端</span>
        </div>
      </div>
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
    </div>
  )
}
