import { useEffect, useRef, useState } from 'react'
import { Check, ChevronRight, CircleAlert, Download, Edit, FileSpreadsheet, Image, Plus, Printer, Search, Settings2, X } from 'lucide-react'
import QRCode from 'qrcode'
import { StatusBadge } from '../components/StatusBadge'
import { api } from '../services/api'
import { CreateMaterialModal, CreateOrderModal, CreateProductModal, CreateUserModal, EvidenceThumb, MaterialImageModal, Modal, OrderDetailModal, RecipeDetailModal } from '../components/Modals'
import { StatusFilter } from '../components/StatusFilter'
import { Pagination } from '../components/Pagination'

export function WorkOrdersPage({ approvals = false }: { approvals?: boolean }) {
  const [showCreateModal, setShowCreateModal] = useState(false)
  const [refreshKey, setRefreshKey] = useState(0)
  const [selectedOrderNo, setSelectedOrderNo] = useState<string | null>(null)
  const [query, setQuery] = useState('')
  const [statusFilter, setStatusFilter] = useState('全部状态')
  const filterOptions = ['全部状态', '待审批', '已批准', '执行中', '已完成', '已撤销']

  const handleExport = async () => {
    const orders = await api.getWorkOrders().catch(() => [])
    const rows = [['工单号', '产品', '目标重量(kg)', '操作员', '状态']]
    for (const order of orders) {
      rows.push([order.order_no, order.product_name, String(order.target_weight_kg), order.operator_name || '待指派', order.status])
    }
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
          <Search size={16} /><input placeholder="搜索工单号、产品或操作员" value={query} onChange={(e) => setQuery(e.target.value)} />
        </div>
        {!approvals && <StatusFilter options={filterOptions} value={statusFilter} onChange={setStatusFilter} />}
        {!approvals && <button className="outline-button" onClick={handleExport}><Download size={15} />导出</button>}
      </div>
      {approvals ? <ApprovalTable onOpen={setSelectedOrderNo} /> : <OrdersTable key={refreshKey} onOpen={setSelectedOrderNo} query={query} statusFilter={statusFilter} />}

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

function OrdersTable({ onOpen, query, statusFilter }: { onOpen: (orderNo: string) => void; query?: string; statusFilter?: string }) {
  const [orders, setOrders] = useState<any[]>([])
  const [loading, setLoading] = useState(true)
  const [page, setPage] = useState(1)
  const pageSize = 10

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

  useEffect(() => {
    setPage(1)
  }, [query, statusFilter])

  if (loading) return <div className="loading">正在加载工单列表...</div>

  const filteredOrders = (orders || []).filter((order) => {
    const text = `${order.id}${order.product}${order.operator}`.toLowerCase()
    const textMatch = !query || text.includes(query.toLowerCase())
    const statusMatch = !statusFilter || statusFilter === '全部状态' || order.status === statusFilter
    return textMatch && statusMatch
  })
  const start = (page - 1) * pageSize
  const pagedOrders = filteredOrders.slice(start, start + pageSize)

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
            {pagedOrders.length === 0 ? (
              <tr><td colSpan={7} className="muted" style={{ textAlign: 'center' }}>暂无工单，请先创建生产工单。</td></tr>
            ) : pagedOrders.map((order, index) => (
              <tr key={`${order.id}-${start + index}`}>
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
      <Pagination page={page} pageSize={pageSize} total={filteredOrders.length} onPageChange={setPage} />
    </div>
  )
}

function ApprovalTable({ onOpen }: { onOpen?: (orderNo: string) => void }) {
  const [items, setItems] = useState<any[]>([])
  const [loading, setLoading] = useState(true)
  const [page, setPage] = useState(1)
  const pageSize = 10

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
    try {
      await api.approve(id)
      setItems((prev) => prev.filter((item) => item.id !== id))
    } catch (e: any) {
      window.alert(e.message)
    }
  }

  const handleReject = async (id: string) => {
    try {
      await api.reject(id)
      setItems((prev) => prev.filter((item) => item.id !== id))
    } catch (e: any) {
      window.alert(e.message)
    }
  }

  if (loading) return <div className="loading">正在加载待审批项目...</div>

  const start = (page - 1) * pageSize
  const pagedItems = items.slice(start, start + pageSize)
  return (
    <>
      <div className="approval-grid">
        {pagedItems.length === 0 ? (
        <div className="empty-panel" style={{ padding: '3rem', textAlign: 'center', color: '#64748b' }}>
          目前暂无需要审批的放行申请
        </div>
      ) : (
        pagedItems.map((item) => {
          return (
            <div className="approval-card" key={item.id}>
              <div className={`approval-icon ${item.type}`}><CircleAlert size={18} /></div>
              <div className="approval-copy">
                <small>{item.id} · {item.time}</small>
                <strong>{item.title}</strong>
                <span>{item.description}</span>
                {item.fileId && <EvidenceThumb fileId={item.fileId} className="approval-evidence" />}
                {item.orderNo && (
                  <button className="text-button" onClick={() => onOpen?.(item.orderNo)}>查看工单</button>
                )}
              </div>
              <div className="approval-actions">
                <>
                  <button className="reject-button" onClick={() => handleReject(item.id)}>
                    <X size={15} />驳回
                  </button>
                  <button className="approve-button wide" onClick={() => handleApprove(item.id)}>
                    <Check size={15} />批准
                  </button>
                </>
              </div>
            </div>
          )
        })
      )}
      </div>
      {items.length > pageSize && <Pagination page={page} pageSize={pageSize} total={items.length} onPageChange={setPage} />}
    </>
  )
}

export function MaterialsPage({ recipesPage = false }: { recipesPage?: boolean }) {
  const [materials, setMaterials] = useState<any[]>([])
  const [products, setProducts] = useState<any[]>([])
  const [showModal, setShowModal] = useState(false)
  const [selectedProduct, setSelectedProduct] = useState<any>(null)
  const [editingProduct, setEditingProduct] = useState<any>(null)
  const [editingMaterial, setEditingMaterial] = useState<any>(null)
  const [selectedMaterialImages, setSelectedMaterialImages] = useState<any>(null)
  const [statusMenuProductId, setStatusMenuProductId] = useState<number | null>(null)
  const [loading, setLoading] = useState(true)
  const [query, setQuery] = useState('')
  const [importMessage, setImportMessage] = useState<string | null>(null)
  const [page, setPage] = useState(1)
  const excelInputRef = useRef<HTMLInputElement>(null)
  const pageSize = recipesPage ? 12 : 10

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

  useEffect(() => {
    setPage(1)
  }, [query, recipesPage])

  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (!(event.target as HTMLElement).closest?.('.recipe-status-menu')) {
        setStatusMenuProductId(null)
      }
    }
    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [])

  const handleChangeProductStatus = async (p: any, isActive: boolean) => {
    setStatusMenuProductId(null)
    if (p.recipe_enabled === isActive) return
    if (!isActive && !window.confirm(`确认停用配方「${p.name}」？停用后该配方不能用于新建工单。`)) return
    try {
      await api.setProductActive(p.id, isActive)
      loadData()
    } catch (e: any) {
      window.alert(e.message)
    }
  }

  const handleDeleteMaterial = async (m: any) => {
    if (!window.confirm(`确认删除辅料「${m.name_zh}」？删除后不可恢复。`)) return
    try {
      await api.deleteMaterial(m.material_id)
      loadData()
    } catch (e: any) {
      window.alert(e.message)
    }
  }

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

  const normalizedQuery = query.trim().toLowerCase()
  const filteredProducts = products.filter((p) => !normalizedQuery || p.name.toLowerCase().includes(normalizedQuery))
  const filteredMaterials = materials.filter((m) => !normalizedQuery || `${m.material_code} ${m.name_zh}`.toLowerCase().includes(normalizedQuery))
  const start = (page - 1) * pageSize
  const pagedProducts = filteredProducts.slice(start, start + pageSize)
  const pagedMaterials = filteredMaterials.slice(start, start + pageSize)

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
          <Search size={16} /><input placeholder={`搜索${recipesPage ? '产品名称' : '辅料代号、名称'}`} value={query} onChange={(e) => setQuery(e.target.value)} />
        </div>
        <button className="outline-button" onClick={() => excelInputRef.current?.click()}><FileSpreadsheet size={15} />Excel 导入</button>
        <button className="outline-button" onClick={() => api.downloadExcelTemplate().catch(() => setImportMessage('导出模板失败，请先确认已登录账号'))}><Download size={15} />导出模板</button>
        <input ref={excelInputRef} type="file" accept=".xlsx" hidden onChange={(e) => handleExcelImport(e.target.files?.[0])} />
      </div>
      {importMessage && !recipesPage && <div className="info-note" style={{ margin: '0 0 18px' }}>{importMessage}</div>}

      {recipesPage ? (
        <>
        <div className="recipe-grid">
          {pagedProducts.length === 0 ? (
            <div className="empty-panel" style={{ padding: '3rem', textAlign: 'center', color: '#64748b', gridColumn: '1 / -1' }}>暂无产品配方，请先维护辅料后再新增产品。</div>
          ) : pagedProducts.map((p) => (
            <div className="recipe-card" key={p.id}>
              <div className="recipe-head">
                <span className="recipe-icon">{p.image_file_id ? <ProductImage fileId={p.image_file_id} /> : <FileSpreadsheet size={18} />}</span>
                <span className={p.recipe_enabled ? 'enabled-dot' : 'enabled-dot disabled'} />
                <div className="recipe-actions">
                  <button className="recipe-edit-btn" onClick={() => setEditingProduct(p)}><Edit size={15} />编辑</button>
                  <button className="icon-btn" title="查看详情" onClick={() => setSelectedProduct(p)}><ChevronRight size={18} /></button>
                </div>
              </div>
              <h3>{p.name}</h3>
              <p>{(p.items || []).length} 种辅料</p>
              <div className="recipe-foot">
                <span>配方状态</span>
                <b className={p.recipe_enabled ? '' : 'disabled'}>{p.recipe_enabled ? '启用' : '停用'}</b>
                <div className="status-filter recipe-status-menu">
                  <button
                    type="button"
                    className={statusMenuProductId === p.id ? 'recipe-status-arrow open' : 'recipe-status-arrow'}
                    title="选择配方状态"
                    onClick={(event) => {
                      event.stopPropagation()
                      setStatusMenuProductId(statusMenuProductId === p.id ? null : p.id)
                    }}
                  >
                    <ChevronRight size={15} />
                  </button>
                  {statusMenuProductId === p.id && (
                    <div className="filter-menu recipe-status-menu-list">
                      <button type="button" className={p.recipe_enabled ? 'active' : ''} onClick={() => handleChangeProductStatus(p, true)}>启用</button>
                      <button type="button" className={!p.recipe_enabled ? 'active stop' : 'stop'} onClick={() => handleChangeProductStatus(p, false)}>停用</button>
                    </div>
                  )}
                </div>
              </div>
            </div>
          ))}
        </div>
        {filteredProducts.length > pageSize && <Pagination page={page} pageSize={pageSize} total={filteredProducts.length} onPageChange={setPage} />}
        </>
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
                  <th />
                </tr>
              </thead>
              <tbody>
                {pagedMaterials.length === 0 ? (
                  <tr><td colSpan={5} className="muted" style={{ textAlign: 'center' }}>暂无辅料，请新增辅料或通过 Excel 导入。</td></tr>
                ) : pagedMaterials.map((m) => (
                  <tr key={m.material_id}>
                    <td>
                      <strong className="order-id">{m.material_id}</strong>
                      <span className="order-product"><small>代号: {m.material_code}</small></span>
                    </td>
                    <td><strong className="cell-primary">{m.name_zh}</strong></td>
                    <td className="muted">{m.shelf_life_months} 个月</td>
                    <td>
                      <button className="image-count material-image-button" title="查看包装图片" onClick={() => setSelectedMaterialImages(m)}>
                        <Image size={14} />{(m.images || []).length} 张
                      </button>
                    </td>
                    <td className="material-actions">
                      <button className="text-button" onClick={() => setEditingMaterial(m)}><Edit size={14} />编辑</button>
                      <button className="text-button danger" onClick={() => handleDeleteMaterial(m)}>删除</button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {filteredMaterials.length > pageSize && <Pagination page={page} pageSize={pageSize} total={filteredMaterials.length} onPageChange={setPage} />}
        </div>
      )}

      {showModal && (
        recipesPage ? (
          <CreateProductModal onClose={() => setShowModal(false)} onSuccess={() => loadData()} />
        ) : (
          <CreateMaterialModal onClose={() => setShowModal(false)} onSuccess={() => loadData()} />
        )
      )}
      {editingProduct && <CreateProductModal product={editingProduct} onClose={() => setEditingProduct(null)} onSuccess={() => { setEditingProduct(null); loadData() }} />}
      {selectedProduct && <RecipeDetailModal product={selectedProduct} onClose={() => setSelectedProduct(null)} />}
      {editingMaterial && <CreateMaterialModal material={editingMaterial} onClose={() => setEditingMaterial(null)} onSuccess={() => { setEditingMaterial(null); loadData() }} />}
      {selectedMaterialImages && <MaterialImageModal material={selectedMaterialImages} onClose={() => setSelectedMaterialImages(null)} />}
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
  const [qrSrc, setQrSrc] = useState<string | null>(null)
  const [printedAtText, setPrintedAtText] = useState('')
  const [previewOpen, setPreviewOpen] = useState(false)
  const [largeQrSrc, setLargeQrSrc] = useState<string | null>(null)
  const [batchPage, setBatchPage] = useState(1)
  const batchPageSize = 10

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

  useEffect(() => {
    if (!selectedMat) return
    setPrintedAtText(new Date().toLocaleString('zh-CN', { hour12: false }))
    buildQrDataUrl(selectedMat, 180)
      .then(setQrSrc)
      .catch(() => setQrSrc(null))
  }, [selectedMat])

  const openPreview = () => {
    if (!selectedMat) return
    setPreviewOpen(true)
    buildQrDataUrl(selectedMat, 360)
      .then(setLargeQrSrc)
      .catch(() => setLargeQrSrc(null))
  }

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
            <button className="preview-tag" onClick={openPreview}>预览</button>
          </div>
          <div className="label-preview">
            {qrSrc ? <img className="qr-preview" src={qrSrc} alt="辅料二维码预览" /> : <div className="fake-qr">▦</div>}
            <strong className="preview-material">{selectedMat ? selectedMat.name_zh : '等待选择辅料'}</strong>
            <span className="preview-code">{printedAtText || '—'}</span>
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
              {batches.slice((batchPage - 1) * batchPageSize, batchPage * batchPageSize).length === 0 ? (
                <tr><td colSpan={6} className="muted" style={{ textAlign: 'center' }}>暂无打印批次</td></tr>
              ) : batches.slice((batchPage - 1) * batchPageSize, batchPage * batchPageSize).map((batch) => (
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
      {batches.length > batchPageSize && <Pagination page={batchPage} pageSize={batchPageSize} total={batches.length} onPageChange={setBatchPage} />}
      {previewOpen && (
        <Modal title="标签放大预览" onClose={() => setPreviewOpen(false)}>
          <div className="label-preview large-label-preview">
            {largeQrSrc ? <img className="qr-preview large-qr" src={largeQrSrc} alt="放大辅料二维码" /> : <div className="fake-qr">▦</div>}
            <strong className="preview-material">{selectedMat ? selectedMat.name_zh : '等待选择辅料'}</strong>
            <span className="preview-code">{printedAtText || '—'}</span>
          </div>
        </Modal>
      )}
    </div>
  )
}

function buildQrPayload(material: any) {
  return {
    v: 1,
    labelId: 'PREVIEW',
    materialId: material.material_id,
    materialCode: material.material_code,
    name: material.name_zh,
    printedAt: new Date().toISOString(),
  }
}

function buildQrDataUrl(material: any, size: number): Promise<string> {
  const canvas = document.createElement('canvas')
  return QRCode.toCanvas(canvas, JSON.stringify(buildQrPayload(material)), {
    width: size,
    margin: 1,
    errorCorrectionLevel: 'H',
    color: { dark: '#1f5742', light: '#ffffff' },
  })
    .then(() => {
      const context = canvas.getContext('2d')
      if (!context) return canvas.toDataURL('image/png')
      const logo = document.createElement('img')
      logo.src = '/logo.png'
      return new Promise<string>((resolve, reject) => {
        logo.onload = () => {
          const logoSize = Math.round(size * 0.22)
          const pad = 5
          const x = (size - logoSize) / 2
          const y = (size - logoSize) / 2
          context.fillStyle = '#ffffff'
          context.beginPath()
          if (typeof context.roundRect === 'function') {
            context.roundRect(x - pad, y - pad, logoSize + pad * 2, logoSize + pad * 2, 8)
          } else {
            context.rect(x - pad, y - pad, logoSize + pad * 2, logoSize + pad * 2)
          }
          context.fill()
          context.drawImage(logo, x, y, logoSize, logoSize)
          resolve(canvas.toDataURL('image/png'))
        }
        logo.onerror = () => {
          reject(new Error('Logo 加载失败'))
        }
      })
    })
}

export function SettingsPage({ accounts = false }: { accounts?: boolean }) {
  const [showModal, setShowModal] = useState(false)
  const [users, setUsers] = useState<any[]>([])
  const [settings, setSettings] = useState<Record<string, string>>({})
  const [backupMessage, setBackupMessage] = useState<string | null>(null)
  const [backups, setBackups] = useState<any[]>([])
  const [accountPage, setAccountPage] = useState(1)
  const [backupPage, setBackupPage] = useState(1)
  const pageSize = 10

  const loadUsers = () => {
    api.listUsers().then((res) => setUsers(res || [])).catch(() => setUsers([]))
  }

  const loadSettings = () => {
    api.getSettings().then(setSettings).catch(() => setSettings({}))
    api.getBackups().then(setBackups).catch(() => setBackups([]))
  }

  useEffect(() => {
    if (accounts) loadUsers()
    else loadSettings()
    setAccountPage(1)
    setBackupPage(1)
  }, [accounts])

  const handleBackup = async () => {
    setBackupMessage('正在备份...')
    try {
      const result = await api.createBackup()
      setBackupMessage(`备份成功：${result.file_name}`)
      api.getBackups().then(setBackups).catch(() => setBackups([]))
    } catch (e: any) {
      setBackupMessage(`备份失败：${e.message}`)
    }
  }

  const handleResetPassword = async (user: any) => {
    const password = window.prompt(`请输入 ${user.display_name} 的新密码（至少 8 位）`)
    if (!password) return
    if (password.length < 8) {
      window.alert('密码长度至少 8 位')
      return
    }
    try {
      await api.resetUserPassword(user.id, password)
      loadUsers()
    } catch (e: any) {
      window.alert(e.message)
    }
  }

  const handleToggleActive = async (user: any) => {
    if (user.is_active && !window.confirm(`确认停用 ${user.display_name}？停用后该账号无法登录。`)) return
    try {
      await api.setUserActive(user.id, !user.is_active)
      loadUsers()
    } catch (e: any) {
      window.alert(e.message)
    }
  }

  const handleEditSetting = async (key: string, currentValue: string, label: string) => {
    const value = window.prompt(`请输入${label}`, currentValue)
    if (value === null) return
    try {
      await api.updateSettings({ [key]: value.trim() })
      loadSettings()
    } catch (e: any) {
      window.alert(e.message)
    }
  }

  const pagedUsers = users.slice((accountPage - 1) * pageSize, accountPage * pageSize)
  const pagedBackups = backups.slice((backupPage - 1) * pageSize, backupPage * pageSize)

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
                {pagedUsers.length === 0 ? (
                  <tr><td colSpan={6} className="muted" style={{ textAlign: 'center' }}>暂无账号</td></tr>
                ) : pagedUsers.map((user) => (
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
                    <td>
                      {user.role !== 'admin' && (
                        <div style={{ display: 'flex', gap: 6 }}>
                          <button className="icon-btn" title="重置密码" onClick={() => handleResetPassword(user)}><Settings2 size={16} /></button>
                          <button className="text-button" onClick={() => handleToggleActive(user)}>{user.is_active ? '停用' : '启用'}</button>
                        </div>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {users.length > pageSize && <Pagination page={accountPage} pageSize={pageSize} total={users.length} onPageChange={setAccountPage} />}
        </div>
      ) : (
        <>
          {backupMessage && <div className="info-note" style={{ margin: '0 0 18px' }}>{backupMessage}</div>}
          <div className="settings-grid">
            <Setting title="默认称重允差" description="目标重量的相对比例" value={`${settings.default_tolerance_percent ?? '1.0'} %`} onClick={() => handleEditSetting('default_tolerance_percent', settings.default_tolerance_percent ?? '1.0', '默认称重允差（%）')} />
            <Setting title="最小绝对允差" description="低于此重量时使用的下限" value={`${settings.min_absolute_tolerance_grams ?? '5'} g`} onClick={() => handleEditSetting('min_absolute_tolerance_grams', settings.min_absolute_tolerance_grams ?? '5', '最小绝对允差（克）')} />
            <Setting title="自动备份" description="数据库和证据文件的本地备份" value={settings.backup_enabled === 'true' ? '已启用' : '已停用'} onClick={() => handleEditSetting('backup_enabled', settings.backup_enabled ?? 'true', '自动备份（true/false）')} />
            <Setting title="服务端口" description="局域网访问端口" value={settings.server_port ?? '8011'} onClick={() => handleEditSetting('server_port', settings.server_port ?? '8011', '服务端口')} />
          </div>
          <button className="primary-button" style={{ marginTop: 18 }} onClick={handleBackup}>
            <DatabaseIcon />立即备份数据库
          </button>
          <div className="panel full-panel" style={{ marginTop: 24 }}>
            <div className="table-wrap">
              <table>
                <thead>
                  <tr><th>备份文件</th><th>大小</th><th>状态</th><th>时间</th></tr>
                </thead>
                <tbody>
                  {pagedBackups.length === 0 ? (
                    <tr><td colSpan={4} className="muted" style={{ textAlign: 'center' }}>暂无备份记录</td></tr>
                  ) : pagedBackups.map((backup) => (
                    <tr key={backup.file_path}>
                      <td className="order-id">{backup.file_path.split('/').pop()}</td>
                      <td>{backup.size_bytes ? `${(backup.size_bytes / 1024).toFixed(1)} KB` : '—'}</td>
                      <td><span className="status status-running"><i />{backup.status === 'success' ? '成功' : '失败'}</span></td>
                      <td>{new Date(backup.created_at).toLocaleString('zh-CN', { hour12: false })}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
          {backups.length > pageSize && <Pagination page={backupPage} pageSize={pageSize} total={backups.length} onPageChange={setBackupPage} />}
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

function ProductImage({ fileId }: { fileId: string }) {
  const [src, setSrc] = useState<string | null>(null)
  useEffect(() => {
    let cancelled = false
    api.getFileUrl(fileId).then((url) => {
      if (!cancelled) setSrc(url)
    }).catch(() => {
      if (!cancelled) setSrc(null)
    })
    return () => {
      cancelled = true
    }
  }, [fileId])
  return src ? <img className="recipe-logo" src={src} alt="产品图片" /> : <FileSpreadsheet size={18} />
}

function Setting({ title, description, value, onClick }: { title: string; description: string; value: string; onClick?: () => void }) {
  return (
    <div className="setting-row">
      <div className="setting-icon"><Settings2 size={17} /></div>
      <div>
        <strong>{title}</strong>
        <span>{description}</span>
      </div>
      <button className="setting-value" onClick={onClick}>{value}<ChevronRight size={15} /></button>
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
