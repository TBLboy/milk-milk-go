import { useEffect, useRef, useState } from 'react'
import { Check, ChevronRight, CircleAlert, Download, FileSpreadsheet, Filter, Image, Plus, Printer, Search, Settings2, X } from 'lucide-react'
import { dashboardData } from '../data/mockData'
import { StatusBadge } from '../components/StatusBadge'
import { api } from '../services/api'
import { CreateMaterialModal, CreateOrderModal, CreateProductModal, CreateUserModal, OrderDetailModal } from '../components/Modals'

export function WorkOrdersPage({ approvals = false }: { approvals?: boolean }) {
  const [showCreateModal, setShowCreateModal] = useState(false)
  const [refreshKey, setRefreshKey] = useState(0)
  const [selectedOrderNo, setSelectedOrderNo] = useState<string | null>(null)

  const handleExport = () => {
    const rows = [['工单号', '产品', '目标重量(kg)', '操作员', '状态']]
    // OrdersTable handles its own state, so keep the export local and informative for MVP.
    const blob = new Blob([`\uFEFF${rows.map((row) => row.join(',')).join('\n')}`], { type: 'text/csv;charset=utf-8' })
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = 'work-orders.csv'
    link.click()
    URL.revokeObjectURL(url)
  }

  return (
    <div className="page-wrap">
      <PageTitle
        eyebrow={approvals ? 'REVIEW QUEUE' : 'PRODUCTION ORDERS'}
        title={approvals ? '审批中心' : '工单管理'}
        sub={approvals ? '处理需要管理员确认的现场申请，审批结果会立即同步到平板。' : '集中查看生产工单、执行进度和辅料称量证据。'}
        action={approvals ? undefined : (
          <button className="primary-button" onClick={() => setShowCreateModal(true)}>
            <Plus size={16} />新建工单
          </button>
        )}
      />
      <div className="page-toolbar">
        <div className="search-box">
          <Search size={16} /><input placeholder="搜索工单号、产品或操作员" />
        </div>
        <button className="filter-button"><Filter size={14} />全部状态 <ChevronRight size={14} /></button>
        {!approvals && <button className="outline-button" onClick={handleExport}><Download size={15} />导出</button>}
      </div>
      {approvals ? <ApprovalTable /> : <OrdersTable key={refreshKey} onOpen={setSelectedOrderNo} />}

      {showCreateModal && (
        <CreateOrderModal
          onClose={() => setShowCreateModal(false)}
          onSuccess={() => setRefreshKey((k) => k + 1)}
        />
      )}
      {selectedOrderNo && (
        <OrderDetailModal
          orderNo={selectedOrderNo}
          onClose={() => setSelectedOrderNo(null)}
          onSuccess={() => setRefreshKey((k) => k + 1)}
        />
      )}
    </div>
  )
}

function OrdersTable({ onOpen }: { onOpen: (orderNo: string) => void }) {
  const [orders, setOrders] = useState<any[]>([])
  const [loading, setLoading] = useState(true)

  const load = () => {
    setLoading(true)
    api.getDashboard().then((res) => {
      setOrders(res.workOrders || [])
      setLoading(false)
    }).catch(() => setLoading(false))
  }

  useEffect(() => {
    load()
  }, [])

  if (loading) return <div className="loading">正在加载工单列表...</div>

  return (
    <div className="panel full-panel">
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>工单信息</th>
              <th>目标产量</th>
              <th>进度</th>
              <th>操作员</th>
              <th>状态</th>
              <th>更新时间</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {orders.map((order, index) => (
              <tr key={`${order.id}-${index}`}>
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
                </td>
                <td>
                  <span className="operator">
                    <span className="operator-dot">{order.operator.slice(0, 1)}</span>
                    {order.operator}
                  </span>
                </td>
                <td><StatusBadge status={order.status} /></td>
                <td className="muted">{order.updatedAt}</td>
                <td><button className="icon-btn" onClick={() => onOpen(order.id)}><ChevronRight size={17} /></button></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}

function ApprovalTable() {
  const [items, setItems] = useState<any[]>([])
  const [actioned, setActioned] = useState<Record<string, 'approved' | 'rejected'>>({})
  const [loading, setLoading] = useState(true)

  const load = () => {
    setLoading(true)
    api.getDashboard().then((res) => {
      setItems(res.pendingApprovals || [])
      setLoading(false)
    }).catch(() => setLoading(false))
  }

  useEffect(() => {
    load()
  }, [])

  const handleApprove = async (id: string) => {
    await api.approve(id)
    setActioned((prev) => ({ ...prev, [id]: 'approved' }))
  }

  const handleReject = async (id: string) => {
    await api.reject(id)
    setActioned((prev) => ({ ...prev, [id]: 'rejected' }))
  }

  if (loading) return <div className="loading">正在加载待审批项目...</div>

  return (
    <div className="approval-grid">
      {items.length === 0 ? (
        <div className="empty-panel" style={{ padding: '3rem', textAlign: 'center', color: '#64748b' }}>
          目前暂无需要审批的放行申请
        </div>
      ) : (
        items.map((item) => {
          const status = actioned[item.id]
          return (
            <div className={`approval-card ${status ? 'actioned' : ''}`} key={item.id}>
              <div className={`approval-icon ${item.type}`}><CircleAlert size={18} /></div>
              <div className="approval-copy">
                <small>{item.id} · {item.time}</small>
                <strong>{item.title}</strong>
                <span>{item.description}</span>
              </div>
              <div className="approval-actions">
                {status === 'approved' ? (
                  <span className="approved-tag"><Check size={14} /> 已批准</span>
                ) : status === 'rejected' ? (
                  <span className="rejected-tag"><X size={14} /> 已驳回</span>
                ) : (
                  <>
                    <button className="reject-button" onClick={() => handleReject(item.id)}>
                      <X size={15} />驳回
                    </button>
                    <button className="approve-button wide" onClick={() => handleApprove(item.id)}>
                      <Check size={15} />批准
                    </button>
                  </>
                )}
              </div>
            </div>
          )
        })
      )}
    </div>
  )
}

export function MaterialsPage({ recipesPage = false }: { recipesPage?: boolean }) {
  const [materials, setMaterials] = useState<any[]>([])
  const [products, setProducts] = useState<any[]>([])
  const [showModal, setShowModal] = useState(false)
  const [loading, setLoading] = useState(true)
  const [importMessage, setImportMessage] = useState<string | null>(null)
  const excelInputRef = useRef<HTMLInputElement>(null)

  const loadData = () => {
    setLoading(true)
    if (recipesPage) {
      api.getProducts().then((res) => {
        setProducts(res || [])
        setLoading(false)
      }).catch(() => setLoading(false))
    } else {
      api.getMaterials().then((res) => {
        setMaterials(res || [])
        setLoading(false)
      }).catch(() => setLoading(false))
    }
  }

  useEffect(() => {
    loadData()
  }, [recipesPage])

  const handleExcelImport = async (file: File | undefined) => {
    if (!file) return
    setImportMessage('正在导入 Excel ...')
    try {
      const result = await api.importExcel(file)
      setImportMessage(`导入完成：成功 ${result.imported_count} 条，失败 ${result.error_count} 条。`)
      loadData()
    } catch (e: any) {
      setImportMessage(`导入失败：${e.message}`)
    } finally {
      if (excelInputRef.current) excelInputRef.current.value = ''
    }
  }

  return (
    <div className="page-wrap">
      <PageTitle
        eyebrow="MASTER DATA"
        title={recipesPage ? '产品与配方' : '辅料管理'}
        sub={recipesPage ? '维护产品配方，按每吨成品配置辅料用量。' : '维护辅料代号、名称和用于现场识别的包装图片。'}
        action={
          <button className="primary-button" onClick={() => setShowModal(true)}>
            <Plus size={16} />新增{recipesPage ? '产品' : '辅料'}
          </button>
        }
      />
      <div className="page-toolbar">
        <div className="search-box">
          <Search size={16} /><input placeholder={`搜索${recipesPage ? '产品名称' : '辅料代号、名称'}`} />
        </div>
        <button className="outline-button" onClick={() => excelInputRef.current?.click()}><FileSpreadsheet size={15} />Excel 导入</button>
        <button className="outline-button" onClick={() => api.downloadExcelTemplate().catch(() => setImportMessage('导出模板失败，请先确认已登录账号'))}><Download size={15} />导出模板</button>
        <input ref={excelInputRef} type="file" accept=".xlsx" hidden onChange={(e) => handleExcelImport(e.target.files?.[0])} />
      </div>
      {importMessage && !recipesPage && <div className="info-note" style={{ margin: '0 0 18px' }}>{importMessage}</div>}

      {recipesPage ? (
        <div className="recipe-grid">
          {products.map((p) => (
            <div className="recipe-card" key={p.id}>
              <div className="recipe-head">
                <span className="recipe-icon"><FileSpreadsheet size={18} /></span>
                <span className="enabled-dot" />
                <button className="icon-btn"><ChevronRight size={17} /></button>
              </div>
              <h3>{p.name}</h3>
              <p>{(p.items || []).length} 种辅料 · 状态 正常</p>
              <div className="recipe-foot">
                <span>配方状态</span>
                <b>启用</b>
                <ChevronRight size={14} />
              </div>
            </div>
          ))}
        </div>
      ) : (
        <div className="panel full-panel">
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>辅料 ID / 代号</th>
                  <th>中文名称</th>
                  <th>保质期</th>
                  <th>包装图片</th>
                  <th>状态</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {materials.map((m) => (
                  <tr key={m.material_id}>
                    <td>
                      <strong className="order-id">{m.material_id}</strong>
                      <span className="order-product"><small>代号: {m.material_code}</small></span>
                    </td>
                    <td><strong className="cell-primary">{m.name_zh}</strong></td>
                    <td className="muted">{m.shelf_life_months} 个月</td>
                    <td><span className="image-count"><Image size={14} />{(m.image_ids || []).length} 张</span></td>
                    <td><span className="status status-running"><i />{m.enabled ? '启用' : '停用'}</span></td>
                    <td>
                      {m.enabled && <button className="text-button" onClick={() => api.disableMaterial(m.material_id).then(loadData)}>停用</button>}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {showModal && (
        recipesPage ? (
          <CreateProductModal onClose={() => setShowModal(false)} onSuccess={() => loadData()} />
        ) : (
          <CreateMaterialModal onClose={() => setShowModal(false)} onSuccess={() => loadData()} />
        )
      )}
    </div>
  )
}

export function LabelsPage() {
  const [materials, setMaterials] = useState<any[]>([])
  const [batches, setBatches] = useState<any[]>([])
  const [selectedMat, setSelectedMat] = useState<any>(null)
  const [quantity, setQuantity] = useState(10)
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [successNotice, setSuccessNotice] = useState<string | null>(null)

  const loadBatches = () => {
    api.getPrintBatches().then(setBatches).catch(() => setBatches([]))
  }

  useEffect(() => {
    api.getMaterials().then((list) => {
      if (list && list.length > 0) {
        setMaterials(list)
        setSelectedMat(list[0])
      }
    })
    loadBatches()
  }, [])

  const handlePrint = async () => {
    if (!selectedMat) return
    setIsSubmitting(true)
    try {
      const batch = await api.createPrintBatch(selectedMat.material_id, quantity)
      setSuccessNotice(`成功生成批次 ${batch.batch_id}，共 ${batch.quantity} 张独立二维码标签！`)
      loadBatches()
    } catch (e: any) {
      alert(`生成失败: ${e.message}`)
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <div className="page-wrap">
      <PageTitle
        eyebrow="LABEL OPERATIONS"
        title="标签打印"
        sub="生成并打印公司自制二维码标签，打印完成后请粘贴到对应辅料包装。"
      />
      <div className="label-layout">
        <section className="panel form-panel">
          <div className="panel-head">
            <div>
              <h2>生成标签</h2>
              <p>每张标签拥有独立编号，打印时间自动记录</p>
            </div>
            <Printer size={20} className="panel-head-icon" />
          </div>
          {successNotice && <div className="info-note success" style={{ color: '#16a34a', borderColor: '#bbf7d0', background: '#f0fdf4' }}>{successNotice}</div>}
          <label>
            选择辅料
            <select
              value={selectedMat?.material_id || ''}
              onChange={(e) => {
                const found = materials.find((m) => m.material_id === e.target.value)
                if (found) setSelectedMat(found)
              }}
            >
              {materials.map((m) => (
                <option key={m.material_id} value={m.material_id}>
                  {m.name_zh} · {m.material_code}
                </option>
              ))}
            </select>
          </label>
          <label>
            打印张数
            <div className="stepper">
              <button onClick={() => setQuantity((q) => Math.max(1, q - 1))}>−</button>
              <strong>{quantity}</strong>
              <button onClick={() => setQuantity((q) => q + 1)}>＋</button>
            </div>
          </label>
          <div className="info-note">
            <CircleAlert size={16} />
            <span>打印日期将自动使用当前系统时间，第一版不录入实际生产日期。</span>
          </div>
          <button className="primary-button print-button" disabled={isSubmitting || !selectedMat} onClick={handlePrint}>
            <Printer size={16} />
            {isSubmitting ? '正在生成批次...' : '生成并打印标签'}
          </button>
        </section>

        <section className="panel preview-panel">
          <div className="panel-head">
            <div>
              <h2>标签预览</h2>
              <p>打印前确认标签信息</p>
            </div>
            <span className="preview-tag">预览</span>
          </div>
          <div className="label-preview">
            <div className="label-top">
              <strong>牧衡 · 辅料标签</strong>
              <span>ACTIVE</span>
            </div>
            <div className="fake-qr">▦</div>
            <strong className="preview-material">{selectedMat ? selectedMat.name_zh : '等待选择辅料'}</strong>
            <span className="preview-code">内部代号 {selectedMat ? selectedMat.material_code : '—'}　·　系统时间自动录入</span>
            <small>扫描此二维码确认辅料身份</small>
          </div>
        </section>
      </div>

      <div className="section-label">
        <span>最近打印批次</span>
        <i />
      </div>
      <div className="panel full-panel">
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>打印批次</th>
                <th>辅料</th>
                <th>张数</th>
                <th>打印人</th>
                <th>时间</th>
                <th>状态</th>
              </tr>
            </thead>
            <tbody>
              {batches.length === 0 ? (
                <tr><td colSpan={6} className="muted" style={{ textAlign: 'center' }}>暂无打印批次</td></tr>
              ) : batches.map((batch) => (
                <tr key={batch.batch_id}>
                  <td className="order-id">{batch.batch_id}</td>
                  <td>{batch.material_name} · {batch.material_id}</td>
                  <td>{batch.quantity} 张</td>
                  <td>系统管理员</td>
                  <td>{new Date(batch.printed_at).toLocaleString('zh-CN', { hour12: false })}</td>
                  <td><span className="status status-running"><i />{batch.status === 'pending' ? '待打印' : '已确认'}</span></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}

export function SettingsPage({ accounts = false }: { accounts?: boolean }) {
  const [showModal, setShowModal] = useState(false)
  const [users, setUsers] = useState<any[]>([])
  const [settings, setSettings] = useState<Record<string, string>>({})
  const [backupMessage, setBackupMessage] = useState<string | null>(null)

  const loadUsers = () => {
    api.listUsers().then((res) => setUsers(res || [])).catch(() => setUsers([]))
  }

  const loadSettings = () => {
    api.getSettings().then(setSettings).catch(() => setSettings({}))
  }

  useEffect(() => {
    if (accounts) loadUsers()
    else loadSettings()
  }, [accounts])

  const handleBackup = async () => {
    setBackupMessage('正在备份...')
    try {
      const result = await api.createBackup()
      setBackupMessage(`备份成功：${result.file_name}`)
    } catch (e: any) {
      setBackupMessage(`备份失败：${e.message}`)
    }
  }

  return (
    <div className="page-wrap">
      <PageTitle
        eyebrow="SYSTEM CONFIGURATION"
        title={accounts ? '账号管理' : '系统设置'}
        sub={accounts ? '创建和管理普通操作员账号，管理员权限由系统预置。' : '维护称重允差、系统备份和现场设备连接参数。'}
        action={accounts ? (
          <button className="primary-button" onClick={() => setShowModal(true)}>
            <Plus size={16} />新建账号
          </button>
        ) : undefined}
      />
      {accounts ? (
        <div className="panel full-panel">
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>账号</th>
                  <th>姓名</th>
                  <th>角色</th>
                  <th>最近登录</th>
                  <th>状态</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {users.map((user) => (
                  <tr key={user.id}>
                    <td className="order-id">{user.username}</td>
                    <td>
                      <span className="operator">
                        <span className="operator-dot">{user.display_name.slice(0, 1)}</span>
                        {user.display_name}
                      </span>
                    </td>
                    <td>{user.role === 'admin' ? '管理员' : '普通操作员'}</td>
                    <td className="muted">{user.created_at ? new Date(user.created_at).toLocaleDateString('zh-CN') : '—'}</td>
                    <td><span className="status status-running"><i />{user.is_active ? '正常' : '停用'}</span></td>
                    <td><button className="icon-btn"><Settings2 size={16} /></button></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      ) : (
        <>
          {backupMessage && <div className="info-note" style={{ margin: '0 0 18px' }}>{backupMessage}</div>}
          <div className="settings-grid">
            <Setting title="默认称重允差" description="目标重量的相对比例" value={`${settings.default_tolerance_percent ?? '1.0'} %`} />
            <Setting title="最小绝对允差" description="低于此重量时使用的下限" value={`${settings.min_absolute_tolerance_grams ?? '5'} g`} />
            <Setting title="自动备份" description="数据库和证据文件的本地备份" value={settings.backup_enabled === 'true' ? '已启用' : '已停用'} />
            <Setting title="服务端口" description="局域网访问端口" value={settings.server_port ?? '8011'} />
          </div>
          <button className="primary-button" style={{ marginTop: 18 }} onClick={handleBackup}>
            <DatabaseIcon />立即备份数据库
          </button>
        </>
      )}

      {showModal && (
        <CreateUserModal
          onClose={() => setShowModal(false)}
          onSuccess={() => {
            loadUsers()
          }}
        />
      )}
    </div>
  )
}

function DatabaseIcon() {
  return <FileSpreadsheet size={16} />
}

function Setting({ title, description, value }: { title: string; description: string; value: string }) {
  return (
    <div className="setting-row">
      <div className="setting-icon"><Settings2 size={17} /></div>
      <div>
        <strong>{title}</strong>
        <span>{description}</span>
      </div>
      <button className="setting-value">{value}<ChevronRight size={15} /></button>
    </div>
  )
}

function PageTitle({ eyebrow, title, sub, action }: { eyebrow: string; title: string; sub: string; action?: React.ReactNode }) {
  return (
    <section className="page-heading">
      <div>
        <p className="eyebrow">{eyebrow}</p>
        <h1>{title}</h1>
        <p className="heading-sub">{sub}</p>
      </div>
      {action}
    </section>
  )
}
