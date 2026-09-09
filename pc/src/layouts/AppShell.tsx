import { useState } from 'react'
import { Bell, ChevronDown, ClipboardList, Database, FileText, LayoutDashboard, LogOut, Menu, Printer, Settings, ShieldCheck, Users, X } from 'lucide-react'

const nav = [
  { label: '工作台', icon: LayoutDashboard, key: 'dashboard' },
  { label: '工单管理', icon: ClipboardList, key: 'orders' },
  { label: '审批中心', icon: ShieldCheck, key: 'approvals', badge: '3' },
  { label: '辅料管理', icon: Database, key: 'materials' },
  { label: '产品与配方', icon: FileText, key: 'recipes' },
  { label: '标签打印', icon: Printer, key: 'labels' },
]

export function AppShell({ page, onPageChange, children }: { page: string; onPageChange: (page: string) => void; children: React.ReactNode }) {
  const [open, setOpen] = useState(false)
  return <div className="app-shell">
    <aside className={open ? 'sidebar sidebar-open' : 'sidebar'}>
      <div className="brand"><div className="brand-mark">牧</div><div><strong>牧衡</strong><span>辅料称重防错系统</span></div><button className="icon-btn mobile-close" onClick={() => setOpen(false)} aria-label="关闭菜单"><X size={19} /></button></div>
      <div className="site-chip"><span className="online-dot" />生产一厂 · 主控端</div>
      <nav>{nav.map(({ label, icon: Icon, badge, key }) => <button onClick={() => { onPageChange(key); setOpen(false) }} className={page === key ? 'nav-item active' : 'nav-item'} key={label}><Icon size={18} strokeWidth={1.8} /><span>{label}</span>{badge && <em>{badge}</em>}</button>)}</nav>
      <div className="nav-divider" />
      <nav><button onClick={() => { onPageChange('accounts'); setOpen(false) }} className={page === 'accounts' ? 'nav-item active' : 'nav-item'}><Users size={18} strokeWidth={1.8} /><span>账号管理</span></button><button onClick={() => { onPageChange('settings'); setOpen(false) }} className={page === 'settings' ? 'nav-item active' : 'nav-item'}><Settings size={18} strokeWidth={1.8} /><span>系统设置</span></button></nav>
      <div className="sidebar-footer"><div className="admin-avatar">管</div><div><strong>系统管理员</strong><span>管理员账号</span></div><button className="icon-btn"><LogOut size={16} /></button></div>
    </aside>
    {open && <button className="sidebar-overlay" onClick={() => setOpen(false)} aria-label="关闭菜单" />}
    <main className="main-content"><header className="topbar"><button className="icon-btn menu-btn" onClick={() => setOpen(true)} aria-label="打开菜单"><Menu size={21} /></button><div className="crumb"><span>生产管理</span><b>/</b><strong>{nav.find((item) => item.key === page)?.label ?? ({ accounts: '账号管理', settings: '系统设置' } as Record<string, string>)[page] ?? '工作台'}</strong></div><div className="top-actions"><button className="icon-btn notification" aria-label="通知"><Bell size={19} /><i /></button><div className="top-user"><div className="admin-avatar small">管</div><span>管理员</span><ChevronDown size={15} /></div></div></header>{children}</main>
  </div>
}
