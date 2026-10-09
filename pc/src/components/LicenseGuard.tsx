import { useCallback, useEffect, useState } from 'react'
import { AlertTriangle, KeyRound, Lock } from 'lucide-react'
import { api } from '../services/api'

type LicenseMode = 'active' | 'read_only' | 'locked'

type LicenseStatus = {
  mode: LicenseMode
  source: 'trial' | 'license'
  licensee: string | null
  expires_at: string | null
  deadline: string | null
  days_remaining: number
  grace_days_remaining: number
  warn: boolean
  warn_days: number
  grace_days: number
  clock_rollback_detected: boolean
}

const POLL_MS = 60_000

const bannerStyle: React.CSSProperties = {
  display: 'flex',
  alignItems: 'center',
  gap: 10,
  padding: '10px 18px',
  fontSize: 14,
  fontWeight: 500,
  borderBottom: '1px solid rgba(0,0,0,.08)',
}

const overlayStyle: React.CSSProperties = {
  position: 'fixed',
  inset: 0,
  zIndex: 4000,
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'center',
  background: 'rgba(15,23,42,.82)',
  backdropFilter: 'blur(3px)',
  padding: 24,
}

const cardStyle: React.CSSProperties = {
  width: 'min(520px, 100%)',
  background: '#fff',
  borderRadius: 14,
  padding: '26px 28px',
  boxShadow: '0 24px 60px rgba(0,0,0,.35)',
}

const inputStyle: React.CSSProperties = {
  width: '100%',
  minHeight: 92,
  padding: 12,
  fontFamily: 'monospace',
  fontSize: 13,
  borderRadius: 8,
  border: '1px solid #cbd5e1',
  resize: 'vertical',
}

const primaryButtonStyle: React.CSSProperties = {
  marginTop: 14,
  width: '100%',
  padding: '11px 16px',
  borderRadius: 8,
  border: 'none',
  background: '#0f766e',
  color: '#fff',
  fontSize: 15,
  fontWeight: 600,
  cursor: 'pointer',
}

function formatDate(value: string | null): string {
  if (!value) return '—'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')}`
}

export function LicenseGuard({ role }: { role?: string }) {
  const [status, setStatus] = useState<LicenseStatus | null>(null)
  const [dialogOpen, setDialogOpen] = useState(false)
  const [code, setCode] = useState('')
  const [message, setMessage] = useState('')
  const [busy, setBusy] = useState(false)

  const isAdmin = role === 'admin'

  const refresh = useCallback(() => {
    api.getLicenseStatus().then(setStatus).catch(() => {
      // 授权状态查询失败时保持上次已知状态，避免误报
    })
  }, [])

  useEffect(() => {
    refresh()
    const timer = window.setInterval(refresh, POLL_MS)
    return () => window.clearInterval(timer)
  }, [refresh])

  const submit = async () => {
    if (!code.trim() || busy) return
    setBusy(true)
    setMessage('')
    try {
      const next = await api.unlockLicense(code.trim())
      setStatus(next)
      setCode('')
      setDialogOpen(false)
      setMessage('')
    } catch (error: any) {
      setMessage(error?.message || '解锁码无效')
    } finally {
      setBusy(false)
    }
  }

  if (!status) return null

  const locked = status.mode === 'locked'
  const readOnly = status.mode === 'read_only'
  const showBanner = locked || readOnly || status.warn
  if (!showBanner && !dialogOpen) return null

  const banner = locked
    ? {
        background: '#fef2f2',
        color: '#991b1b',
        icon: <Lock size={18} />,
        text: '软件授权已到期并被锁定，生产功能已停止，请输入解锁码后继续使用',
      }
    : readOnly
    ? {
        background: '#fff7ed',
        color: '#9a3412',
        icon: <AlertTriangle size={18} />,
        text: `软件授权已到期，当前为只读状态（宽限期剩余 ${status.grace_days_remaining} 天）：可查看、导出与备份，但不能新建工单或提交称重`,
      }
    : {
        background: '#fffbeb',
        color: '#92400e',
        icon: <AlertTriangle size={18} />,
        text: `${status.source === 'trial' ? '试用期' : '授权'}剩余 ${status.days_remaining} 天（${formatDate(status.deadline)} 到期），请及时联系供应商续期`,
      }

  return <>
    {showBanner && <div style={{ ...bannerStyle, background: banner.background, color: banner.color }} role="status">
      {banner.icon}
      <span style={{ flex: 1 }}>{banner.text}</span>
      {isAdmin && <button
        type="button"
        onClick={() => { setDialogOpen(true); setMessage('') }}
        style={{ display: 'inline-flex', alignItems: 'center', gap: 6, padding: '6px 12px', borderRadius: 8, border: '1px solid currentColor', background: 'transparent', color: 'inherit', fontWeight: 600, cursor: 'pointer' }}
      >
        <KeyRound size={15} />输入解锁码
      </button>}
    </div>}

    {locked && !dialogOpen && <div style={overlayStyle} role="alertdialog" aria-modal="true" aria-label="软件已锁定">
      <div style={{ ...cardStyle, textAlign: 'center' }}>
        <Lock size={40} style={{ color: '#dc2626' }} />
        <h2 style={{ margin: '14px 0 8px', fontSize: 21 }}>软件授权已到期</h2>
        <p style={{ margin: 0, color: '#475569', lineHeight: 1.7 }}>
          系统已停止生产功能，历史数据与备份完整保留。<br />
          请输入供应商提供的解锁码以恢复使用。
        </p>
        <div style={{ marginTop: 18, fontSize: 13, color: '#64748b' }}>
          {status.licensee ? `授权客户：${status.licensee}` : '当前为试用授权'}
        </div>
        {isAdmin ? <button type="button" style={primaryButtonStyle} onClick={() => { setDialogOpen(true); setMessage('') }}>
          输入解锁码
        </button> : <p style={{ marginTop: 18, color: '#64748b' }}>请联系系统管理员输入解锁码</p>}
      </div>
    </div>}

    {dialogOpen && <div style={overlayStyle} role="dialog" aria-modal="true" aria-label="输入解锁码">
      <div style={cardStyle}>
        <h2 style={{ margin: '0 0 6px', fontSize: 19 }}>输入解锁码</h2>
        <p style={{ margin: '0 0 14px', color: '#64748b', fontSize: 13.5, lineHeight: 1.6 }}>
          解锁码由供应商签发，可直接粘贴。校验通过后立即恢复使用，无需重启。
        </p>
        <textarea
          style={inputStyle}
          value={code}
          onChange={(event) => setCode(event.target.value)}
          placeholder="粘贴解锁码（形如 xxxxx.yyyyy）"
          spellCheck={false}
        />
        {message && <div style={{ marginTop: 10, color: '#b91c1c', fontSize: 13.5 }}>{message}</div>}
        <button type="button" style={{ ...primaryButtonStyle, opacity: busy ? 0.6 : 1 }} disabled={busy} onClick={submit}>
          {busy ? '校验中…' : '解锁'}
        </button>
        <button
          type="button"
          onClick={() => { setDialogOpen(false); setMessage('') }}
          style={{ marginTop: 8, width: '100%', padding: '9px 16px', borderRadius: 8, border: '1px solid #cbd5e1', background: '#fff', cursor: 'pointer' }}
        >
          关闭
        </button>
      </div>
    </div>}
  </>
}
