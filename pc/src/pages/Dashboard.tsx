import { useEffect, useState } from 'react'
import { ArrowUpRight, Camera, Check, ChevronRight, Clock3, Database, MoreHorizontal, PackageCheck, ScanLine, Search, Scale, Trash2, UserRoundCheck } from 'lucide-react'
import { api } from '../services/api'
import { StatusBadge } from '../components/StatusBadge'
import { CreateOrderModal, OrderDetailModal } from '../components/Modals'
import { StatusFilter } from '../components/StatusFilter'
import type { DashboardData } from '../types/domain'

const filterOptions = ['全部状态', '待审批', '已批准', '执行中', '已完成']

export function Dashboard({ onNavigate }: { onNavigate?: (page: string) => void }) {
  const [data, setData] = useState<DashboardData | null>(null)
  const [approved, setApproved] = useState<string[]>([])
  const [showCreateModal, setShowCreateModal] = useState(false)
  const [selectedOrderNo, setSelectedOrderNo] = useState<string | null>(null)
  const [query, setQuery] = useState('')
  const [statusFilter, setStatusFilter] = useState('全部状态')

  const loadData = () => {
    api.getDashboard().then(setData)
  }

  useEffect(() => {
    loadData()
  }, [])

  if (!data) return <div className="loading">正在加载工作台<span /></div>

  const visibleOrders = data.workOrders.filter((order) => {
    if (order.status === '已撤销' || order.status === '已删除') return false
    const textMatch = `${order.id}${order.product}`.toLowerCase().includes(query.toLowerCase())
    const statusMatch = statusFilter === '全部状态' || order.status === statusFilter
    return textMatch && statusMatch
  })

  return (
    <div className="page-wrap">
      <section className="page-heading">
        <div>
          <p className="eyebrow">WEDNESDAY · 09 SEP 2026</p>
          <h1>早上好，管理员</h1>
          <p className="heading-sub">这里是今天的生产称量概况，及时处理异常审批，确保每一份辅料都准确无误。</p>
        </div>
        <button className="primary-button" onClick={() => setShowCreateModal(true)}>
          <Scale size={16} />新建工单
        </button>
      </section>

      <section className="stat-grid">
        {data.stats.map((stat) => (
          <div className="stat-card" key={stat.label}>
            <div className={`stat-icon ${stat.tone}`}><StatIcon label={stat.label} /></div>
            <div className="stat-copy">
              <span>{stat.label}</span>
              <strong>{stat.value}</strong>
              <small className={stat.tone === 'green' ? 'positive' : ''}>
                {stat.tone === 'green' && <ArrowUpRight size={13} />}
                {stat.detail}
              </small>
            </div>
          </div>
        ))}
      </section>

      <div className="content-grid">
        <section className="panel orders-panel">
          <div className="panel-head">
            <div>
              <h2>最新工单</h2>
              <p>实时查看生产工单的执行状态</p>
            </div>
            <button className="text-button" onClick={() => onNavigate?.('orders')}>
              查看全部 <ChevronRight size={15} />
            </button>
          </div>
          <div className="toolbar">
            <div className="search-box">
              <Search size={16} />
              <input placeholder="搜索工单号或产品名称" value={query} onChange={(e) => setQuery(e.target.value)} />
            </div>
            <StatusFilter options={filterOptions} value={statusFilter} onChange={setStatusFilter} />
          </div>
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>工单信息</th>
                  <th>目标产量</th>
                  <th>执行进度</th>
                  <th>操作员</th>
                  <th>状态</th>
                  <th>更新</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {visibleOrders.length === 0 ? (
                  <tr><td colSpan={7} className="muted" style={{ textAlign: 'center' }}>没有符合条件的工单。</td></tr>
                ) : visibleOrders.map((order) => (
                  <tr key={order.id}>
                    <td>
                      <strong className="order-id">{order.id}</strong>
                      <span className="order-product">{order.product}<small>{order.batch}</small></span>
                    </td>
                    <td>{order.targetWeight.toLocaleString()} kg</td>
                    <td>
                      <div className="progress-row">
                        <div className="progress"><i style={{ width: `${(order.completedSteps / order.totalSteps) * 100}%` }} /></div>
                        <span>{order.completedSteps}/{order.totalSteps}</span>
                      </div>
                      {order.alert && <small className="row-alert">{order.alert}</small>}
                    </td>
                    <td>
                      <span className="operator">
                        <span className="operator-dot">{order.operator === '—' ? '—' : order.operator.slice(0, 1)}</span>
                        {order.operator}
                      </span>
                    </td>
                    <td><StatusBadge status={order.status} /></td>
                    <td className="muted">{order.updatedAt}</td>
                    <td><button className="icon-btn" onClick={() => setSelectedOrderNo(order.id)}><MoreHorizontal size={17} /></button></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>

        <aside className="panel approval-panel">
          <div className="panel-head">
            <div>
              <h2>待处理审批</h2>
              <p>需要管理员确认的事项</p>
            </div>
            <span className="approval-count">{data.pendingApprovals.length}</span>
          </div>
          <div className="approval-list">
            {data.pendingApprovals.length === 0 ? (
              <div className="approval-empty">暂无待处理审批</div>
            ) : data.pendingApprovals.map((item) => (
              <div className={approved.includes(item.id) ? 'approval-item approved' : 'approval-item'} key={item.id}>
                <div className={`approval-icon ${item.type}`}>
                  {item.type === 'photo' ? <Camera size={17} /> : item.type === 'takeover' ? <UserRoundCheck size={17} /> : item.type === 'delete' ? <Trash2 size={17} /> : <PackageCheck size={17} />}
                </div>
                <div className="approval-copy">
                  <strong>{item.title}</strong>
                  <span>{item.description}</span>
                  <small>{item.time}</small>
                </div>
                <button
                  className="approve-button"
                  onClick={() => api.approve(item.id).then(() => setApproved((ids) => [...ids, item.id]))}
                  aria-label={`批准 ${item.title}`}
                >
                  {approved.includes(item.id) ? <Check size={16} /> : <ChevronRight size={17} />}
                </button>
              </div>
            ))}
          </div>
          <button className="approval-footer" onClick={() => onNavigate?.('approvals')}>
            进入审批中心 <ArrowUpRight size={15} />
          </button>
        </aside>
      </div>

      <section className="quick-section">
        <div className="section-label"><span>快捷入口</span><i /></div>
        <div className="quick-grid">
          <Quick onClick={() => onNavigate?.('labels')} icon={<ScanLine />} title="标签打印" text="生成与打印公司自制二维码" />
          <Quick onClick={() => setShowCreateModal(true)} icon={<Scale />} title="新建工单" text="开始一次新的生产称量" />
          <Quick onClick={() => onNavigate?.('materials')} icon={<Database />} title="辅料资料" text="维护辅料和内部代号" />
          <Quick onClick={() => onNavigate?.('recipes')} icon={<FileIcon />} title="产品配方" text="编辑每吨辅料用量" />
        </div>
      </section>

      {showCreateModal && (
        <CreateOrderModal
          onClose={() => setShowCreateModal(false)}
          onSuccess={() => loadData()}
        />
      )}
      {selectedOrderNo && (
        <OrderDetailModal
          orderNo={selectedOrderNo}
          onClose={() => setSelectedOrderNo(null)}
          onSuccess={loadData}
        />
      )}
    </div>
  )
}

function Quick({ icon, title, text, onClick }: { icon: React.ReactNode; title: string; text: string; onClick?: () => void }) {
  return (
    <button className="quick-card" onClick={onClick}>
      <span className="quick-icon">{icon}</span>
      <span><strong>{title}</strong><small>{text}</small></span>
      <ArrowUpRight size={16} />
    </button>
  )
}
function FileIcon() { return <PackageCheck size={20} /> }
function StatIcon({ label }: { label: string }) { return label === '今日工单' ? <PackageCheck size={19} /> : label === '执行中' ? <Scale size={19} /> : label === '待审批' ? <Clock3 size={19} /> : <Check size={19} /> }
