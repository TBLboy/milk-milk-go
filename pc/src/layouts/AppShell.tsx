import { useEffect, useRef, useState } from 'react'
import { Bell, Bug, ChevronDown, ClipboardList, Database, FileText, KeyRound, LayoutDashboard, LogOut, Menu, Printer, ScrollText, Settings, ShieldCheck, UserRound, Users, X } from 'lucide-react'
import { api } from '../services/api'
import { DATA_SYNC_EVENT, emitDataSync } from '../services/dataSync'
import { BugReportModal, ChangePasswordModal, UserProfileModal } from '../components/Modals'

const nav = [
  { label: '工作台', icon: LayoutDashboard, key: 'dashboard' },
  { label: '工单管理', icon: ClipboardList, key: 'orders' },
  { label: '审批中心', icon: ShieldCheck, key: 'approvals' },
  { label: '辅料管理', icon: Database, key: 'materials' },
  { label: '产品与配方', icon: FileText, key: 'recipes' },
  { label: '标签生成', icon: Printer, key: 'labels' },
]

function UserAvatar({ name, avatarUrl, small = false }: { name: string; avatarUrl: string; small?: boolean }) {
  return <div className={small ? 'admin-avatar small' : 'admin-avatar'}>
    {avatarUrl ? <img src={avatarUrl} alt="用户头像" /> : name.slice(0, 1)}
  </div>
}

export function AppShell({ page, onPageChange, children, user, onLogout, onUserChange }: {
  page: string
  onPageChange: (page: string) => void
  children: React.ReactNode
  user?: any
  onLogout?: () => void
  onUserChange?: (user: any) => void
}) {
  const [open, setOpen] = useState(false)
  const [pendingCount, setPendingCount] = useState(0)
  const [userMenuOpen, setUserMenuOpen] = useState(false)
  const [profileOpen, setProfileOpen] = useState(false)
  const [passwordOpen, setPasswordOpen] = useState(false)
  const [bugReportOpen, setBugReportOpen] = useState(false)
  const [avatarUrl, setAvatarUrl] = useState('')
  const userMenuRef = useRef<HTMLDivElement>(null)
  const displayName = user?.display_name || user?.username || '系统管理员'
  const displayRole = user?.role === 'admin' ? '管理员账号' : '普通操作员'

  useEffect(() => {
    if (!user?.avatar_file_id) {
      setAvatarUrl('')
      return
    }
    let active = true
    api.getFileUrl(user.avatar_file_id).then((value) => {
      if (active) setAvatarUrl(value)
    }).catch(() => {
      if (active) setAvatarUrl('')
    })
    return () => {
      active = false
      setAvatarUrl((current) => {
        if (current.startsWith('blob:')) URL.revokeObjectURL(current)
        return ''
      })
    }
  }, [user?.avatar_file_id])

  useEffect(() => {
    if (!userMenuOpen) return
    const closeOnOutsideClick = (event: MouseEvent) => {
      if (!userMenuRef.current?.contains(event.target as Node)) setUserMenuOpen(false)
    }
    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key === 'Escape') setUserMenuOpen(false)
    }
    document.addEventListener('mousedown', closeOnOutsideClick)
    document.addEventListener('keydown', closeOnEscape)
    return () => {
      document.removeEventListener('mousedown', closeOnOutsideClick)
      document.removeEventListener('keydown', closeOnEscape)
    }
  }, [userMenuOpen])

  useEffect(() => {
    let active = true
    let requestInFlight = false

    const refreshPendingCount = () => {
      if (!active || requestInFlight || document.visibilityState === 'hidden') return
      requestInFlight = true
      api.getPendingApprovalCount()
        .then((count) => {
          if (active) setPendingCount(count)
        })
        .catch(() => {
          // Keep the last known count during a transient network failure.
        })
        .finally(() => {
          requestInFlight = false
        })
    }

    const refreshWhenVisible = () => {
      if (document.visibilityState === 'visible') emitDataSync()
    }

    window.addEventListener(DATA_SYNC_EVENT, refreshPendingCount)
    window.addEventListener('focus', refreshWhenVisible)
    document.addEventListener('visibilitychange', refreshWhenVisible)
    refreshPendingCount()
    emitDataSync()
    const timer = window.setInterval(emitDataSync, 5000)

    return () => {
      active = false
      window.clearInterval(timer)
      window.removeEventListener(DATA_SYNC_EVENT, refreshPendingCount)
      window.removeEventListener('focus', refreshWhenVisible)
      document.removeEventListener('visibilitychange', refreshWhenVisible)
    }
  }, [])

  return <div className="app-shell">
    <aside className={open ? 'sidebar sidebar-open' : 'sidebar'}>
      <div className="brand"><div className="brand-mark brand-logo"><img src="/logo.png" alt="公司 Logo" /></div><div><strong>牧衡</strong><span>辅料称重防错系统</span></div><button className="icon-btn mobile-close" onClick={() => setOpen(false)} aria-label="关闭菜单"><X size={19} /></button></div>
      <div className="site-chip"><span className="online-dot" />生产一厂 · 主控端</div>
      <nav>{nav.map(({ label, icon: Icon, key }) => <button onClick={() => { onPageChange(key); setOpen(false) }} className={page === key ? 'nav-item active' : 'nav-item'} key={label}><Icon size={18} strokeWidth={1.8} /><span>{label}</span>{key === 'approvals' && pendingCount > 0 && <em>{pendingCount}</em>}</button>)}</nav>
      <div className="nav-divider" />
      <nav><button onClick={() => { onPageChange('accounts'); setOpen(false) }} className={page === 'accounts' ? 'nav-item active' : 'nav-item'}><Users size={18} strokeWidth={1.8} /><span>账号管理</span></button><button onClick={() => { onPageChange('audit'); setOpen(false) }} className={page === 'audit' ? 'nav-item active' : 'nav-item'}><ScrollText size={18} strokeWidth={1.8} /><span>审计日志</span></button><button onClick={() => { onPageChange('settings'); setOpen(false) }} className={page === 'settings' ? 'nav-item active' : 'nav-item'}><Settings size={18} strokeWidth={1.8} /><span>系统设置</span></button></nav>
      <div className="sidebar-footer"><UserAvatar name={displayName} avatarUrl={avatarUrl} /><div><strong>{displayName}</strong><span>{displayRole}</span></div><button className="icon-btn" onClick={onLogout} aria-label="退出登录"><LogOut size={16} /></button></div>
    </aside>
    {open && <button className="sidebar-overlay" onClick={() => setOpen(false)} aria-label="关闭菜单" />}
    <main className="main-content"><header className="topbar"><button className="icon-btn menu-btn" onClick={() => setOpen(true)} aria-label="打开菜单"><Menu size={21} /></button><div className="crumb"><span>生产管理</span><b>/</b><strong>{nav.find((item) => item.key === page)?.label ?? ({ accounts: '账号管理', audit: '审计日志', settings: '系统设置' } as Record<string, string>)[page] ?? '工作台'}</strong></div><div className="top-actions"><button className="icon-btn notification" aria-label="提交 BUG 反馈" title="提交 BUG 反馈" onClick={() => setBugReportOpen(true)}><Bug size={19} /></button><button className="icon-btn notification" aria-label="通知" onClick={() => onPageChange('approvals')}><Bell size={19} />{pendingCount > 0 && <i />}</button><div className="user-menu-wrap" ref={userMenuRef}><button className={userMenuOpen ? 'top-user open' : 'top-user'} onClick={() => setUserMenuOpen((value) => !value)} aria-haspopup="menu" aria-expanded={userMenuOpen}><UserAvatar name={displayName} avatarUrl={avatarUrl} small /><span>{displayName}</span><ChevronDown className="user-menu-arrow" size={15} /></button>{userMenuOpen && <div className="user-menu" role="menu"><div className="user-menu-head"><UserAvatar name={displayName} avatarUrl={avatarUrl} /><div><strong>{displayName}</strong><span>{user?.username || 'admin'} · {displayRole}</span></div></div><div className="user-menu-list"><button role="menuitem" onClick={() => { setUserMenuOpen(false); setProfileOpen(true) }}><UserRound size={17} /><span>用户信息</span></button><button role="menuitem" onClick={() => { setUserMenuOpen(false); setPasswordOpen(true) }}><KeyRound size={17} /><span>密码管理</span></button><div className="user-menu-divider" /><button role="menuitem" className="danger" onClick={() => { setUserMenuOpen(false); onLogout?.() }}><LogOut size={17} /><span>退出登录</span></button></div></div>}</div></div></header>{children}</main>
    {profileOpen && <UserProfileModal user={user} onClose={() => setProfileOpen(false)} onSuccess={(updated) => onUserChange?.(updated)} />}
    {passwordOpen && <ChangePasswordModal onClose={() => setPasswordOpen(false)} />}
    {bugReportOpen && <BugReportModal onClose={() => setBugReportOpen(false)} />}
  </div>
}
