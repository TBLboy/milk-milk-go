import { useEffect, useRef, useState } from 'react'
import { Check, ChevronRight, CircleAlert, Copy, Download, Edit, Eye, FileSpreadsheet, Image, Mail, Network, Plus, Printer, QrCode, RotateCcw, Search, Settings2, ShieldCheck, Trash2, X } from 'lucide-react'
import QRCode from 'qrcode'
import { StatusBadge } from '../components/StatusBadge'
import { api } from '../services/api'
import { CreateMaterialModal, CreateOrderModal, CreateProductModal, CreateUserModal, EvidenceThumb, MaterialImageModal, Modal, OrderDetailModal, RecipeDetailModal } from '../components/Modals'
import { StatusFilter } from '../components/StatusFilter'
import { Pagination } from '../components/Pagination'
import { SearchableSelect } from '../components/SearchableSelect'
import { useAutoRefresh } from '../hooks/useAutoRefresh'
import type {
  BugReportRecord,
  BugReportStatus,
  EvidenceIntegrityItem,
  EvidenceIntegrityResult,
} from '../types/domain'

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

  const load = async (showLoading = false) => {
    if (showLoading) setLoading(true)
    try {
      const res = await api.getDashboard()
      setOrders(res.workOrders || [])
    } finally {
      if (showLoading) setLoading(false)
    }
  }

  useEffect(() => {
    void load(true).catch(() => {})
  }, [])
  useAutoRefresh(() => load(false))

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

  const load = async (showLoading = false) => {
    if (showLoading) setLoading(true)
    try {
      const res = await api.getDashboard()
      setItems(res.pendingApprovals || [])
    } finally {
      if (showLoading) setLoading(false)
    }
  }

  useEffect(() => {
    void load(true).catch(() => {})
  }, [])
  useAutoRefresh(() => load(false))

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
          目前暂无待审批申请
        </div>
      ) : (
        pagedItems.map((item) => {
          return (
            <div className="approval-card" key={item.id}>
              <div className={`approval-icon ${item.type}`}>{item.type === 'delete' ? <Trash2 size={18} /> : <CircleAlert size={18} />}</div>
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
                    <X size={15} />{item.type === 'delete' ? '拒绝' : '驳回'}
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
  const [importErrors, setImportErrors] = useState<Array<{
    row: number
    product_name?: string
    material_code?: string
    message: string
  }>>([])
  const [page, setPage] = useState(1)
  const excelInputRef = useRef<HTMLInputElement>(null)
  const pageSize = recipesPage ? 12 : 10

  const loadData = async (showLoading = true) => {
    if (showLoading) setLoading(true)
    try {
      if (recipesPage) {
        setProducts(await api.getProducts() || [])
      } else {
        setMaterials(await api.getMaterials() || [])
      }
    } finally {
      if (showLoading) setLoading(false)
    }
  }

  useEffect(() => {
    void loadData().catch(() => {})
  }, [recipesPage])
  useAutoRefresh(() => loadData(false))

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
    setImportMessage(recipesPage ? '正在校验 Excel ...' : '正在导入 Excel ...')
    setImportErrors([])
    try {
      if (recipesPage) {
        const validation = await api.validateProductRecipeExcel(file)
        if (!validation.valid_product_count) {
          setImportErrors(validation.errors || [])
          setImportMessage(`校验完成：没有可导入的产品，发现 ${validation.error_count} 个错误。`)
          return
        }
        setImportMessage(`校验通过，正在导入 ${validation.valid_product_count} 个产品 ...`)
        const result = await api.importProductRecipeExcel(file)
        setImportErrors(result.errors || [])
        setImportMessage(
          `导入完成：成功新增 ${result.imported_product_count} 个产品、${result.imported_row_count} 行配方，未导入错误 ${result.error_count} 个。`,
        )
        await loadData(false)
        return
      }
      const result = await api.importExcel(file)
      setImportMessage(`导入完成：成功 ${result.imported_count} 条，失败 ${result.error_count} 条。`)
      await loadData(false)
    } catch (e: any) {
      setImportMessage(`导入失败：${e.message}`)
    } finally {
      if (excelInputRef.current) excelInputRef.current.value = ''
    }
  }

  const handleDownloadTemplate = async () => {
    setImportMessage('正在下载模板 ...')
    setImportErrors([])
    try {
      if (recipesPage) {
        await api.downloadProductRecipeTemplate()
      } else {
        await api.downloadExcelTemplate()
      }
      setImportMessage('模板下载完成。')
    } catch (e: any) {
      setImportMessage(`模板下载失败：${e.message}`)
    }
  }

  const handleExport = async () => {
    setImportMessage(recipesPage ? '正在导出产品配方 ...' : '正在导出辅料 ...')
    setImportErrors([])
    try {
      if (recipesPage) {
        await api.exportProductRecipes()
        setImportMessage('产品配方导出完成。')
      } else {
        await api.exportMaterials()
        setImportMessage('辅料导出完成。')
      }
    } catch (e: any) {
      setImportMessage(`导出失败：${e.message}`)
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
        <button className="outline-button" onClick={handleDownloadTemplate}><Download size={15} />下载模板</button>
        <button className="outline-button" onClick={handleExport}><Download size={15} />{recipesPage ? '导出配方' : '导出辅料'}</button>
        <input ref={excelInputRef} type="file" accept=".xlsx" hidden onChange={(e) => handleExcelImport(e.target.files?.[0])} />
      </div>
      {(importMessage || importErrors.length > 0) && (
        <div className="excel-import-result">
          {importMessage && <div className="info-note">{importMessage}</div>}
          {importErrors.length > 0 && (
            <div className="excel-error-list">
              <strong>未导入明细</strong>
              <div className="excel-error-table">
                {importErrors.map((error, index) => (
                  <div className="excel-error-row" key={`${error.row}-${index}`}>
                    <span>第 {error.row} 行</span>
                    <code>{error.product_name || '—'} / {error.material_code || '—'}</code>
                    <em>{error.message}</em>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

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
  const [quantityText, setQuantityText] = useState('10')
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [successNotice, setSuccessNotice] = useState<string | null>(null)
  const [previewLabel, setPreviewLabel] = useState<any>(null)
  const [labelSize, setLabelSize] = useState('60x40')
  const [qrSrc, setQrSrc] = useState<string | null>(null)
  const [previewOpen, setPreviewOpen] = useState(false)
  const [largeQrSrc, setLargeQrSrc] = useState<string | null>(null)
  const [batchPage, setBatchPage] = useState(1)
  const batchPageSize = 10

  const loadBatches = async () => {
    setBatches(await api.getPrintBatches() || [])
  }

  const loadMaterials = async () => {
    const list = await api.getMaterials() || []
    setMaterials(list)
    setSelectedMat((current: any) => {
      const currentId = current?.material_id
      return list.find((material) => material.material_id === currentId) || list[0] || null
    })
  }

  const loadSettings = async () => {
    const values = await api.getSettings()
    setLabelSize(values.label_size_mm || '60x40')
  }

  const loadData = async () => {
    await Promise.all([loadMaterials(), loadBatches(), loadSettings()])
  }

  const buildPreviewLabel = (material: any, size: string) => ({
    v: 1,
    preview: true,
    materialId: material.material_id,
    materialCode: material.material_code,
    name: material.name_zh,
    labelSize: size,
  })

  useEffect(() => {
    void loadData().catch(() => {})
  }, [])
  useAutoRefresh(loadData)

  useEffect(() => {
    setSuccessNotice(null)
    setPreviewOpen(false)
    setQrSrc(null)
    setLargeQrSrc(null)
    setPreviewLabel(selectedMat ? buildPreviewLabel(selectedMat, labelSize) : null)
  }, [selectedMat?.material_id, selectedMat?.material_code, selectedMat?.name_zh, labelSize])

  useEffect(() => {
    if (!previewLabel) {
      setQrSrc(null)
      return
    }
    let active = true
    buildQrDataUrl(previewLabel, 180)
      .then((source) => {
        if (active) setQrSrc(source)
      })
      .catch(() => {
        if (active) setQrSrc(null)
      })
    return () => { active = false }
  }, [previewLabel])

  useEffect(() => {
    if (!previewOpen || !previewLabel) {
      setLargeQrSrc(null)
      return
    }
    let active = true
    buildQrDataUrl(previewLabel, 360)
      .then((source) => {
        if (active) setLargeQrSrc(source)
      })
      .catch(() => {
        if (active) setLargeQrSrc(null)
      })
    return () => { active = false }
  }, [previewOpen, previewLabel])

  const openPreview = () => {
    if (!previewLabel) return
    setPreviewOpen(true)
  }

  const clampQuantity = (value: number) => Math.min(10000, Math.max(1, Math.trunc(value)))

  const updateQuantityText = (value: string) => {
    const digits = value.replace(/\D/g, '').slice(0, 5)
    if (!digits) {
      setQuantityText('')
      return
    }
    const next = clampQuantity(Number(digits))
    setQuantity(next)
    setQuantityText(String(next))
  }

  const commitQuantity = () => {
    const parsed = Number(quantityText)
    const next = Number.isFinite(parsed) && parsed > 0 ? clampQuantity(parsed) : 1
    setQuantity(next)
    setQuantityText(String(next))
    return next
  }

  const adjustQuantity = (delta: number) => {
    const parsed = Number(quantityText)
    const current = Number.isFinite(parsed) && parsed > 0 ? parsed : quantity
    const next = clampQuantity(current + delta)
    setQuantity(next)
    setQuantityText(String(next))
  }

  const handlePrint = async () => {
    if (!selectedMat) return
    const generateQuantity = commitQuantity()
    setIsSubmitting(true)
    try {
      const batch = await api.createPrintBatch(selectedMat.material_id, generateQuantity)
      const firstLabel = batch.label_payloads?.[0]
      if (!firstLabel?.labelId) throw new Error('后端未返回可扫描的真实标签编号')
      setPreviewLabel(firstLabel)
      setSuccessNotice(`已按打印张数生成批次 ${batch.batch_id}，共 ${batch.quantity} 张正式标签记录。当前版本尚未连接打印机，未发送真实打印任务。`)
      loadBatches()
    } catch (e: any) {
      alert(`生成失败: ${e.message}`)
    } finally {
      setIsSubmitting(false)
    }
  }

  const labelPreviewMetrics = getLabelPreviewMetrics(labelSize)
  const largeLabelPreviewMetrics = getLabelPreviewMetrics(labelSize, true)

  return (
    <div className="page-wrap">
      <PageTitle
        eyebrow="LABEL PRINTING"
        title="标签打印"
        sub="选择辅料即可预览标签；点击打印后按张数生成正式标签记录。当前 Demo 不发送真实打印任务。"
      />
      <div className="label-layout">
        <section className="panel form-panel">
          <div className="panel-head">
            <div>
              <h2>标签打印</h2>
              <p>点击打印后生成正式标签记录，每张标签拥有独立编号</p>
            </div>
            <Printer size={20} className="panel-head-icon" />
          </div>
          {successNotice && <div className="info-note success" style={{ color: '#16a34a', borderColor: '#bbf7d0', background: '#f0fdf4' }}>{successNotice}</div>}
          <label>
            选择辅料
            <SearchableSelect
              value={selectedMat?.material_id || ''}
              options={materials.map((m) => ({
                value: m.material_id,
                label: `${m.name_zh} · ${m.material_code}`,
                keywords: `${m.name_zh} ${m.material_code} ${m.name_en || ''} ${m.material_id}`,
              }))}
              onChange={(nextValue) => {
                const found = materials.find((m) => m.material_id === nextValue)
                if (found) setSelectedMat(found)
              }}
              placeholder="输入辅料名称或代号搜索"
              emptyMessage="没有匹配的辅料"
            />
          </label>
          <div className="quantity-field">
            <span className="field-label">打印张数</span>
            <div className="stepper">
              <button type="button" aria-label="减少打印张数" onClick={() => adjustQuantity(-1)}>−</button>
              <input
                type="text"
                inputMode="numeric"
                pattern="[0-9]*"
                maxLength={5}
                aria-label="打印张数"
                value={quantityText}
                onChange={(e) => updateQuantityText(e.target.value)}
                onBlur={commitQuantity}
                onKeyDown={(e) => {
                  if (e.key === 'Enter') e.currentTarget.blur()
                }}
              />
              <button type="button" aria-label="增加打印张数" onClick={() => adjustQuantity(1)}>＋</button>
            </div>
          </div>
          <div className="info-note">
            <CircleAlert size={16} />
            <span>选择辅料后右侧立即显示预览，不会写入标签记录；点击“打印”才会生成正式记录。当前 Demo 尚未连接打印机，不发送真实打印任务。</span>
          </div>
          <button type="button" className="primary-button print-button" disabled={isSubmitting || !selectedMat} onClick={handlePrint}>
            <Printer size={16} />
            {isSubmitting ? '正在生成记录...' : '打印'}
          </button>
        </section>

        <section className="panel preview-panel">
          <div className="panel-head">
            <div>
              <h2>标签预览</h2>
              <p>{previewLabel?.preview ? '选择辅料后的即时预览' : '正式标签已生成'} · {formatLabelSize(previewLabel?.labelSize || labelSize)}</p>
            </div>
            <button type="button" className="preview-tag" disabled={!previewLabel} onClick={openPreview}>放大预览</button>
          </div>
          <div className="label-preview" style={{ width: labelPreviewMetrics.width, height: labelPreviewMetrics.height }}>
            {qrSrc ? (
              <img className="qr-preview" style={{ width: labelPreviewMetrics.qrSize, height: labelPreviewMetrics.qrSize }} src={qrSrc} alt="辅料二维码预览" />
            ) : (
              <div className="fake-qr label-placeholder" style={{ width: labelPreviewMetrics.qrSize, height: labelPreviewMetrics.qrSize }}>
                <QrCode size={34} />
                <span>{selectedMat ? '生成后显示可扫描二维码' : '等待选择辅料'}</span>
              </div>
            )}
            <strong className="preview-material">{previewLabel?.name || selectedMat?.name_zh || '等待选择辅料'}</strong>
            <span className="preview-code">{previewLabel?.printedAt ? new Date(previewLabel.printedAt).toLocaleString('zh-CN', { hour12: false }) : '预览标签 · 点击打印后生成正式记录'}</span>
          </div>
        </section>
      </div>

      <div className="section-label">
        <span>最近生成批次</span>
        <i />
      </div>
      <div className="panel full-panel">
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>生成批次</th>
                <th>辅料</th>
                <th>张数</th>
                <th>生成人</th>
                <th>生成时间</th>
                <th>状态</th>
              </tr>
            </thead>
            <tbody>
              {batches.slice((batchPage - 1) * batchPageSize, batchPage * batchPageSize).length === 0 ? (
                <tr><td colSpan={6} className="muted" style={{ textAlign: 'center' }}>暂无生成批次</td></tr>
              ) : batches.slice((batchPage - 1) * batchPageSize, batchPage * batchPageSize).map((batch) => (
                <tr key={batch.batch_id}>
                  <td className="order-id">{batch.batch_id}</td>
                  <td>{batch.material_name} · {batch.material_id}</td>
                  <td>{batch.quantity} 张</td>
                  <td>{batch.created_by_name || '未知用户'}</td>
                  <td>{new Date(batch.printed_at).toLocaleString('zh-CN', { hour12: false })}</td>
                  <td><span className="status status-running"><i />{batch.status === 'pending' ? '已生成' : batch.status}</span></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
      {batches.length > batchPageSize && <Pagination page={batchPage} pageSize={batchPageSize} total={batches.length} onPageChange={setBatchPage} />}
      {previewOpen && (
        <Modal title="标签放大预览" onClose={() => setPreviewOpen(false)}>
          <div className="label-preview large-label-preview" style={{ width: largeLabelPreviewMetrics.width, height: largeLabelPreviewMetrics.height }}>
            {largeQrSrc ? <img className="qr-preview large-qr" style={{ width: largeLabelPreviewMetrics.qrSize, height: largeLabelPreviewMetrics.qrSize }} src={largeQrSrc} alt="放大辅料二维码" /> : <div className="fake-qr label-placeholder" style={{ width: largeLabelPreviewMetrics.qrSize, height: largeLabelPreviewMetrics.qrSize }}><QrCode size={42} /><span>二维码生成中</span></div>}
            <strong className="preview-material">{previewLabel?.name || '等待选择辅料'}</strong>
            <span className="preview-code">{previewLabel?.printedAt ? new Date(previewLabel.printedAt).toLocaleString('zh-CN', { hour12: false }) : '预览标签 · 点击打印后生成正式记录'}</span>
          </div>
        </Modal>
      )}
    </div>
  )
}

const AUDIT_ACTION_LABELS: Record<string, string> = {
  'account.activation_changed': '账号启用状态变更',
  'account.admin_profile_updated': '管理员修改账号资料',
  'account.approved': '账号审批通过',
  'account.created': '创建账号',
  'account.password_changed': '用户修改密码',
  'account.password_reset': '管理员重置密码',
  'account.profile_updated': '用户修改资料',
  'account.rejected': '账号审批驳回',
  'account.registered': '提交注册申请',
  'admin_password.recovered': '管理员紧急恢复',
  'admin_password.recovery_failed': '管理员恢复失败',
  'admin_password.recovery_locked': '管理员恢复锁定',
  'auth.admin_login': '电脑管理员登录',
  'auth.login': '用户登录',
  'backup.created': '手动备份',
  'backup.failed': '手动备份失败',
  'backup.scheduled.created': '自动备份',
  'backup.scheduled.failed': '自动备份失败',
  'bug_report.email_failed': 'BUG反馈邮件失败',
  'bug_report.email_not_configured': 'BUG反馈邮件未配置',
  'bug_report.sent': '提交BUG反馈',
  'label.batch_created': '生成标签批次',
  'material.created': '新增辅料',
  'material.deleted': '删除辅料',
  'material.updated': '修改辅料',
  'product.activation_changed': '产品启用状态变更',
  'product.created': '新增产品配方',
  'product.deleted': '删除产品配方',
  'product.updated': '修改产品配方',
  'settings.updated': '修改系统设置',
  'system.restored': '恢复系统数据',
  'system.restore_failed': '系统恢复失败',
  'type_confirmation.approved': '拍照放行通过',
  'type_confirmation.passed': '扫码类型确认',
  'type_confirmation.photo_requested': '提交拍照放行',
  'type_confirmation.rejected': '类型确认驳回',
  'weighing.passed': '称重确认通过',
  'weighing.rejected': '称重超差',
  'work_order.approved': '审批工单',
  'work_order.cancelled': '撤销工单',
  'work_order.completed': '完成工单',
  'work_order.created': '创建工单',
  'work_order.request_approved': '批准工单申请',
  'work_order.request_created': '提交工单申请',
  'work_order.request_rejected': '驳回工单申请',
  'work_order.started': '开始执行工单',
}

function auditActionLabel(action: string) {
  return AUDIT_ACTION_LABELS[action] || action
}

function auditResultView(result: string) {
  if (result === 'success') return { label: '成功', className: 'status-running' }
  if (result === 'rejected') return { label: '已驳回', className: 'status-cancelled' }
  return { label: '失败', className: 'status-cancelled' }
}

type AuditFilters = {
  actorId: string
  workOrderNo: string
  action: string
  result: string
  startAt: string
  endAt: string
}

const EMPTY_AUDIT_FILTERS: AuditFilters = {
  actorId: '',
  workOrderNo: '',
  action: '',
  result: '',
  startAt: '',
  endAt: '',
}

export function AuditLogsPage() {
  const [users, setUsers] = useState<any[]>([])
  const [draft, setDraft] = useState<AuditFilters>(EMPTY_AUDIT_FILTERS)
  const [filters, setFilters] = useState<AuditFilters>(EMPTY_AUDIT_FILTERS)
  const [page, setPage] = useState(1)
  const [data, setData] = useState<any>({ items: [], total: 0, page: 1, page_size: 20, pages: 0 })
  const [loading, setLoading] = useState(true)
  const [selected, setSelected] = useState<any | null>(null)
  const pageSize = 20

  const load = async (showLoading = false) => {
    if (showLoading) setLoading(true)
    const startAt = filters.startAt ? new Date(filters.startAt).toISOString() : undefined
    const endAt = filters.endAt ? new Date(filters.endAt).toISOString() : undefined
    try {
      setData(await api.getAuditLogs({
        actor_id: filters.actorId ? Number(filters.actorId) : undefined,
        work_order_no: filters.workOrderNo.trim() || undefined,
        action: filters.action || undefined,
        result: filters.result || undefined,
        start_at: startAt,
        end_at: endAt,
        page,
        page_size: pageSize,
      }))
    } finally {
      if (showLoading) setLoading(false)
    }
  }

  useEffect(() => {
    api.listUsers().then((items) => setUsers(items || [])).catch(() => setUsers([]))
  }, [])

  useEffect(() => {
    void load(true).catch(() => {})
  }, [page, filters])
  useAutoRefresh(() => load(false))

  const applyFilters = (event: React.FormEvent) => {
    event.preventDefault()
    setPage(1)
    setFilters({ ...draft })
  }

  const resetFilters = () => {
    setDraft(EMPTY_AUDIT_FILTERS)
    setFilters(EMPTY_AUDIT_FILTERS)
    setPage(1)
  }

  return (
    <div className="page-wrap">
      <PageTitle
        eyebrow="AUDIT TRAIL"
        title="审计日志"
        sub="追踪登录、账号、主数据、工单、审批、扫码、称重、标签和系统运维操作。"
      />
      <form className="audit-filter-panel" onSubmit={applyFilters}>
        <label>
          开始时间
          <input type="datetime-local" value={draft.startAt} onChange={(event) => setDraft({ ...draft, startAt: event.target.value })} />
        </label>
        <label>
          结束时间
          <input type="datetime-local" value={draft.endAt} onChange={(event) => setDraft({ ...draft, endAt: event.target.value })} />
        </label>
        <label>
          操作人员
          <SearchableSelect
            value={draft.actorId}
            options={[
              { value: '', label: '全部人员', keywords: '全部' },
              ...users.map((user) => ({
                value: String(user.id),
                label: `${user.display_name} · ${user.username}`,
                keywords: `${user.display_name} ${user.username} ${user.employee_no || ''}`,
              })),
            ]}
            onChange={(nextValue) => setDraft({ ...draft, actorId: nextValue })}
            placeholder="输入姓名或账号搜索"
            emptyMessage="没有匹配的人员"
          />
        </label>
        <label>
          工单号
          <input value={draft.workOrderNo} onChange={(event) => setDraft({ ...draft, workOrderNo: event.target.value })} placeholder="例如 WO-20260913..." />
        </label>
        <label>
          操作类型
          <SearchableSelect
            value={draft.action}
            options={[
              { value: '', label: '全部动作', keywords: '全部' },
              ...Object.entries(AUDIT_ACTION_LABELS).map(([action, label]) => ({
                value: action,
                label,
                keywords: `${action} ${label}`,
              })),
            ]}
            onChange={(nextValue) => setDraft({ ...draft, action: nextValue })}
            placeholder="输入动作搜索"
            emptyMessage="没有匹配的动作"
          />
        </label>
        <label>
          结果
          <SearchableSelect
            value={draft.result}
            options={[
              { value: '', label: '全部结果', keywords: '全部' },
              { value: 'success', label: '成功', keywords: 'success 成功' },
              { value: 'rejected', label: '已驳回', keywords: 'rejected 驳回' },
              { value: 'failure', label: '失败', keywords: 'failure 失败' },
            ]}
            onChange={(nextValue) => setDraft({ ...draft, result: nextValue })}
            placeholder="输入结果搜索"
            emptyMessage="没有匹配的结果"
          />
        </label>
        <div className="audit-filter-actions">
          <button type="button" className="outline-button" onClick={resetFilters}><RotateCcw size={15} />重置</button>
          <button type="submit" className="primary-button"><Search size={15} />查询</button>
        </div>
      </form>

      <div className="panel full-panel audit-log-panel">
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>时间</th>
                <th>操作人员</th>
                <th>操作</th>
                <th>结果</th>
                <th>工单号</th>
                <th>对象</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {loading ? (
                <tr><td colSpan={7} className="muted audit-empty">正在加载审计记录...</td></tr>
              ) : data.items.length === 0 ? (
                <tr><td colSpan={7} className="muted audit-empty">当前筛选条件下没有审计记录。</td></tr>
              ) : data.items.map((item: any) => {
                const result = auditResultView(item.result)
                return (
                  <tr key={item.id}>
                    <td className="audit-time">{new Date(item.created_at).toLocaleString('zh-CN', { hour12: false })}</td>
                    <td>
                      <strong>{item.actor_name || (item.actor_id ? `用户 #${item.actor_id}` : '系统')}</strong>
                      <small className="muted audit-subline">{item.actor_username || '系统任务'}</small>
                    </td>
                    <td>
                      <strong>{auditActionLabel(item.action)}</strong>
                      <small className="muted audit-subline">{item.action}</small>
                    </td>
                    <td><span className={`status ${result.className}`}><i />{result.label}</span></td>
                    <td className="order-id">{item.work_order_no || '—'}</td>
                    <td>
                      <span>{item.resource_type}</span>
                      <small className="muted audit-subline">{item.resource_id || '—'}</small>
                    </td>
                    <td><button type="button" className="icon-btn" title="查看详情" onClick={() => setSelected(item)}><Eye size={16} /></button></td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
        <Pagination page={page} pageSize={pageSize} total={data.total || 0} onPageChange={setPage} />
      </div>

      {selected && (
        <Modal title="审计记录详情" onClose={() => setSelected(null)}>
          <div className="audit-detail">
            <div className="audit-detail-grid">
              <span>操作时间<strong>{new Date(selected.created_at).toLocaleString('zh-CN', { hour12: false })}</strong></span>
              <span>操作人员<strong>{selected.actor_name || selected.actor_username || '系统'}</strong></span>
              <span>操作动作<strong>{auditActionLabel(selected.action)}</strong></span>
              <span>执行结果<strong>{auditResultView(selected.result).label}</strong></span>
              <span>工单号<strong>{selected.work_order_no || '—'}</strong></span>
              <span>业务对象<strong>{selected.resource_type} / {selected.resource_id || '—'}</strong></span>
            </div>
            <div>
              <span className="field-label">附加数据</span>
              <pre className="audit-detail-json">{selected.detail ? JSON.stringify(selected.detail, null, 2) : '无附加数据'}</pre>
            </div>
          </div>
        </Modal>
      )}
    </div>
  )
}

function buildQrDataUrl(payload: any, size: number): Promise<string> {
  const canvas = document.createElement('canvas')
  return QRCode.toCanvas(canvas, JSON.stringify(payload), {
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

function parseLabelSize(value: string | undefined): { width: number; height: number } {
  const match = /^(\d{1,3})\s*[xX×]\s*(\d{1,3})$/.exec(value?.trim() || '')
  if (!match) return { width: 60, height: 40 }
  const width = Number(match[1])
  const height = Number(match[2])
  if (width < 10 || width > 300 || height < 10 || height > 300) {
    return { width: 60, height: 40 }
  }
  return { width, height }
}

function formatLabelSize(value: string | undefined) {
  const size = parseLabelSize(value)
  return `${size.width} × ${size.height} mm`
}

function getLabelPreviewMetrics(value: string | undefined, large = false) {
  const size = parseLabelSize(value)
  const width = large
    ? Math.min(420, Math.max(300, size.width * 5))
    : Math.min(280, Math.max(210, size.width * 4))
  const height = large
    ? Math.min(360, Math.max(235, Math.round(width * size.height / size.width)))
    : Math.min(260, Math.max(180, Math.round(width * size.height / size.width)))
  const qrSize = large
    ? Math.min(200, Math.max(120, Math.round(height * 0.5)))
    : Math.min(104, Math.max(76, Math.round(height * 0.44)))
  return { width, height, qrSize }
}

function UserAvatar({ user }: { user: any }) {
  const [url, setUrl] = useState('')
  useEffect(() => {
    if (!user.avatar_file_id) return
    let active = true
    api.getFileUrl(user.avatar_file_id).then((value) => {
      if (active) setUrl(value)
    }).catch(() => {})
    return () => { active = false }
  }, [user.avatar_file_id])
  if (url) return <img src={url} alt="" className="operator-avatar" />
  return <span className="operator-dot">{user.display_name.slice(0, 1)}</span>
}

function networkKindLabel(kind: string) {
  if (kind === 'hotspot') return '移动热点'
  if (kind === 'wireless') return '无线网卡'
  if (kind === 'ethernet') return '有线网卡'
  if (kind === 'virtual') return '虚拟网卡'
  return '其他网卡'
}

function tabletAddressHint(ipv4: string) {
  const parts = ipv4.split('.')
  if (parts.length === 4 && parts[0] === '192' && parts[1] === '168') {
    return `当前平板服务器设置填写后两段：${parts[2]} / ${parts[3]}`
  }
  return '该地址不在当前平板固定支持的 192.168 网段，请开启电脑热点并选择 192.168 地址。'
}

const evidenceIntegrityLabels: Record<EvidenceIntegrityItem['status'], string> = {
  ok: '正常',
  missing: '文件缺失',
  size_mismatch: '大小不一致',
  hash_mismatch: '哈希不一致',
  unhashed: '缺少历史哈希',
}

const bugReportStatusLabels: Record<BugReportStatus, string> = {
  pending: '待发送',
  sending: '发送中',
  sent: '已提交',
  failed: '发送失败',
}

function bugReportStatusClass(status: BugReportStatus) {
  if (status === 'sent') return 'status-running'
  if (status === 'failed') return 'status-cancelled'
  return 'status-pending'
}

function formatFileSize(value: number | null) {
  if (value === null || value === undefined) return '—'
  if (value < 1024) return `${value} B`
  if (value < 1024 * 1024) return `${(value / 1024).toFixed(1)} KB`
  return `${(value / 1024 / 1024).toFixed(1)} MB`
}

function csvCell(value: unknown) {
  const text = value === null || value === undefined ? '' : String(value)
  return `"${text.replace(/"/g, '""')}"`
}

export function SettingsPage({ accounts = false }: { accounts?: boolean }) {
  const [showModal, setShowModal] = useState(false)
  const [editUser, setEditUser] = useState<any | null>(null)
  const [resetResult, setResetResult] = useState<any | null>(null)
  const [copied, setCopied] = useState(false)
  const [users, setUsers] = useState<any[]>([])
  const [settings, setSettings] = useState<Record<string, string>>({})
  const [backupMessage, setBackupMessage] = useState<string | null>(null)
  const [networkInfo, setNetworkInfo] = useState<Awaited<ReturnType<typeof api.getNetworkAddresses>> | null>(null)
  const [networkError, setNetworkError] = useState<string | null>(null)
  const [detectingIp, setDetectingIp] = useState(false)
  const [networkCopied, setNetworkCopied] = useState(false)
  const [backups, setBackups] = useState<any[]>([])
  const [integrityResult, setIntegrityResult] = useState<EvidenceIntegrityResult | null>(null)
  const [integrityError, setIntegrityError] = useState<string | null>(null)
  const [integrityChecking, setIntegrityChecking] = useState(false)
  const [bugReports, setBugReports] = useState<BugReportRecord[]>([])
  const [bugReportMessage, setBugReportMessage] = useState<string | null>(null)
  const [bugReportError, setBugReportError] = useState<string | null>(null)
  const [smtpTesting, setSmtpTesting] = useState(false)
  const [retryingBugReportId, setRetryingBugReportId] = useState<number | null>(null)
  const [accountPage, setAccountPage] = useState(1)
  const [backupPage, setBackupPage] = useState(1)
  const pageSize = 10

  const loadUsers = () => {
    api.listUsers().then((res) => setUsers(res || [])).catch(() => setUsers([]))
  }

  const loadSettings = () => {
    api.getSettings().then(setSettings).catch(() => setSettings({}))
    api.getBackups().then(setBackups).catch(() => setBackups([]))
    api.getBugReports().then(setBugReports).catch(() => setBugReports([]))
  }

  useEffect(() => {
    if (accounts) loadUsers()
    else loadSettings()
    setAccountPage(1)
    setBackupPage(1)
  }, [accounts])
  useAutoRefresh(() => accounts ? loadUsers() : loadSettings())

  const handleBackup = async () => {
    setBackupMessage('正在生成完整备份...')
    try {
      const result = await api.createBackup()
      setBackupMessage(`完整备份成功：${result.file_name}`)
      api.getBackups().then(setBackups).catch(() => setBackups([]))
    } catch (e: any) {
      setBackupMessage(`备份失败：${e.message}`)
    }
  }

  const handleDetectIp = async () => {
    setDetectingIp(true)
    setNetworkError(null)
    setNetworkCopied(false)
    try {
      setNetworkInfo(await api.getNetworkAddresses())
    } catch (e: any) {
      setNetworkInfo(null)
      setNetworkError(`检测失败：${e.message}`)
    } finally {
      setDetectingIp(false)
    }
  }

  const copyNetworkAddress = async () => {
    const text = networkInfo?.recommended?.ipv4
    if (!text) return
    try {
      await navigator.clipboard.writeText(text)
    } catch {
      const area = document.createElement('textarea')
      area.value = text
      document.body.appendChild(area)
      area.select()
      document.execCommand('copy')
      document.body.removeChild(area)
    }
    setNetworkCopied(true)
  }

  const handleIntegrityCheck = async () => {
    setIntegrityChecking(true)
    setIntegrityError(null)
    try {
      setIntegrityResult(await api.checkEvidenceIntegrity())
    } catch (e: any) {
      setIntegrityResult(null)
      setIntegrityError(`检查失败：${e.message}`)
    } finally {
      setIntegrityChecking(false)
    }
  }

  const exportIntegrityIssues = () => {
    if (!integrityResult?.issues.length) return
    const rows = [
      ['文件编号', '异常类型', '预期大小（字节）', '实际大小（字节）', '预期 SHA-256', '实际 SHA-256'],
      ...integrityResult.issues.map((item) => [
        item.file_id,
        evidenceIntegrityLabels[item.status],
        item.expected_size_bytes,
        item.actual_size_bytes,
        item.expected_sha256,
        item.actual_sha256,
      ]),
    ]
    const blob = new Blob(
      [`\uFEFF${rows.map((row) => row.map(csvCell).join(',')).join('\r\n')}`],
      { type: 'text/csv;charset=utf-8' },
    )
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = `证据完整性异常-${new Date().toISOString().slice(0, 10)}.csv`
    link.click()
    URL.revokeObjectURL(url)
  }

  const handleTestSmtp = async () => {
    setSmtpTesting(true)
    setBugReportMessage(null)
    setBugReportError(null)
    try {
      const result = await api.testBugReportSmtp()
      setBugReportMessage(result.message || 'SMTP 测试邮件已提交')
    } catch (e: any) {
      setBugReportError(`测试失败：${e.message}`)
    } finally {
      setSmtpTesting(false)
    }
  }

  const handleRetryBugReport = async (report: BugReportRecord) => {
    setRetryingBugReportId(report.id)
    setBugReportMessage(null)
    setBugReportError(null)
    try {
      const result = await api.retryBugReport(report.id)
      setBugReportMessage(result.message || '反馈邮件重试成功')
      const refreshed = await api.getBugReports()
      setBugReports(refreshed)
    } catch (e: any) {
      setBugReportError(`重试失败：${e.message}`)
      api.getBugReports().then(setBugReports).catch(() => undefined)
    } finally {
      setRetryingBugReportId(null)
    }
  }

  const handleResetPassword = async (user: any) => {
    try {
      const result = await api.resetUserPassword(user.id)
      setCopied(false)
      setResetResult(result)
    } catch (e: any) {
      window.alert(e.message)
    }
  }

  const handleEditUser = async (user: any) => {
    try {
      setEditUser(await api.getUser(user.id))
    } catch (e: any) {
      window.alert(e.message)
    }
  }

  const handleUserApproval = async (user: any, approved: boolean) => {
    try {
      if (approved) await api.approve(`AP-USER-${user.id}`)
      else await api.reject(`AP-USER-${user.id}`)
      loadUsers()
    } catch (e: any) {
      window.alert(e.message)
    }
  }

  const copyResetPassword = async () => {
    const text = resetResult?.temporary_password
    if (!text) return
    try {
      await navigator.clipboard.writeText(text)
      setCopied(true)
    } catch {
      const area = document.createElement('textarea')
      area.value = text
      document.body.appendChild(area)
      area.select()
      document.execCommand('copy')
      document.body.removeChild(area)
      setCopied(true)
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
  const integrityIssueCount = (status: EvidenceIntegrityItem['status']) => (
    integrityResult?.issues.filter((item) => item.status === status).length ?? 0
  )

  return (
    <div className="page-wrap">
      <PageTitle
        eyebrow="SYSTEM CONFIGURATION"
        title={accounts ? '账号管理' : '系统设置'}
        sub={accounts ? '创建和管理普通操作员账号，管理员权限由系统预置。' : '维护称重允差、标签尺寸、系统备份和现场设备连接参数。'}
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
                  <th>电话</th>
                  <th>工号</th>
                  <th>状态</th>
                  <th>操作</th>
                </tr>
              </thead>
              <tbody>
                {pagedUsers.length === 0 ? (
                  <tr><td colSpan={6} className="muted" style={{ textAlign: 'center' }}>暂无账号</td></tr>
                ) : pagedUsers.map((user) => (
                  <tr key={user.id}>
                    <td>
                      <span className="operator">
                        {user.avatar_file_id ? (
                          <UserAvatar user={user} />
                        ) : (
                          <span className="operator-dot">{user.display_name.slice(0, 1)}</span>
                        )}
                        <span>
                          <span className="order-id">{user.username}</span>
                          <small className="muted">{user.role === 'admin' ? '管理员' : '普通操作员'}</small>
                        </span>
                      </span>
                    </td>
                    <td>{user.display_name}</td>
                    <td>{user.phone || '—'}</td>
                    <td>{user.employee_no || '—'}</td>
                    <td>
                      {user.status === 'pending' && <span className="status status-pending"><i />待审批</span>}
                      {user.status === 'rejected' && <span className="status status-cancelled"><i />已驳回</span>}
                      {user.status !== 'pending' && user.status !== 'rejected' && (
                        <span className={`status ${user.is_active ? 'status-running' : 'status-cancelled'}`}><i />{user.is_active ? '正常' : '停用'}</span>
                      )}
                    </td>
                    <td>
                      {user.role !== 'admin' && (
                        <div style={{ display: 'flex', gap: 6 }}>
                          <button className="icon-btn" title="编辑资料" onClick={() => handleEditUser(user)}><Edit size={16} /></button>
                          {user.status === 'pending' ? (
                            <>
                              <button className="text-button" onClick={() => handleUserApproval(user, false)}>驳回</button>
                              <button className="text-button" onClick={() => handleUserApproval(user, true)}>批准</button>
                            </>
                          ) : (
                            <>
                              <button className="icon-btn" title="重置密码" onClick={() => handleResetPassword(user)}><Settings2 size={16} /></button>
                              <button className="text-button" onClick={() => handleToggleActive(user)}>{user.is_active ? '停用' : '启用'}</button>
                            </>
                          )}
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
            <Setting title="自动备份" description="每天自动备份数据库、证据和配置" value={settings.backup_enabled === 'true' ? '已启用' : '已停用'} onClick={() => handleEditSetting('backup_enabled', settings.backup_enabled ?? 'true', '自动备份（true/false）')} />
            <Setting title="自动备份时间" description="后端按本机时间执行每日备份" value={settings.backup_time ?? '02:00'} onClick={() => handleEditSetting('backup_time', settings.backup_time ?? '02:00', '自动备份时间（HH:MM）')} />
            <Setting title="标签尺寸" description="标签预览和后续打印使用的宽 × 高（毫米）" value={formatLabelSize(settings.label_size_mm)} onClick={() => handleEditSetting('label_size_mm', settings.label_size_mm ?? '60x40', '标签尺寸（宽x高，毫米）')} />
            <Setting title="服务端口" description="局域网访问端口" value={settings.server_port ?? '8011'} onClick={() => handleEditSetting('server_port', settings.server_port ?? '8011', '服务端口')} />
          </div>
          <div className="settings-actions">
            <button className="primary-button" onClick={handleBackup}>
              <DatabaseIcon />立即完整备份
            </button>
            <button className="outline-button" disabled={detectingIp} onClick={handleDetectIp}>
              <Network size={16} />{detectingIp ? '正在检测...' : '检测本机 IP'}
            </button>
          </div>
          {networkError && <div className="network-message error"><CircleAlert size={16} />{networkError}</div>}
          {networkInfo && (
            <div className="network-result">
              <div className="network-result-head">
                <div>
                  <strong>本机 IPv4 检测结果</strong>
                  <span>检测时间：{new Date(networkInfo.detected_at).toLocaleString('zh-CN', { hour12: false })}</span>
                </div>
              </div>
              {networkInfo.recommended ? (
                <>
                  <div className="network-recommendation">
                    <div className="network-result-icon"><Network size={20} /></div>
                    <div className="network-address-main">
                      <span>建议平板连接</span>
                      <code>{networkInfo.recommended.ipv4}</code>
                      <small>{networkInfo.recommended.name} · {networkKindLabel(networkInfo.recommended.kind)}</small>
                      <p>{tabletAddressHint(networkInfo.recommended.ipv4)}</p>
                    </div>
                    <button type="button" className="outline-button" onClick={copyNetworkAddress}>
                      {networkCopied ? <Check size={15} /> : <Copy size={15} />}
                      {networkCopied ? '已复制' : '复制地址'}
                    </button>
                  </div>
                  {networkInfo.addresses.filter((item) => !item.is_recommended).length > 0 && (
                    <div className="network-address-list">
                      <span>其他检测到的地址</span>
                      {networkInfo.addresses.filter((item) => !item.is_recommended).map((item) => (
                        <div className="network-address-row" key={`${item.name}-${item.ipv4}`}>
                          <span>{item.name}</span>
                          <code>{item.ipv4}</code>
                          <small>{networkKindLabel(item.kind)}{item.is_up ? '' : ' · 未连接'}</small>
                        </div>
                      ))}
                    </div>
                  )}
                </>
              ) : (
                <div className="network-message"><CircleAlert size={16} />未检测到可供平板访问的局域网 IPv4，请确认电脑热点或网络连接已开启。</div>
              )}
            </div>
          )}
          <div className="panel full-panel" style={{ marginTop: 24 }}>
            <div className="table-wrap">
              <table>
                <thead>
                  <tr><th>备份文件</th><th>类型</th><th>大小</th><th>状态</th><th>校验值</th><th>时间</th></tr>
                </thead>
                <tbody>
                  {pagedBackups.length === 0 ? (
                    <tr><td colSpan={6} className="muted" style={{ textAlign: 'center' }}>暂无备份记录</td></tr>
                  ) : pagedBackups.map((backup) => (
                    <tr key={backup.file_path}>
                      <td className="order-id">{backup.file_path.split('/').pop()}</td>
                      <td>{backup.trigger === 'scheduled' ? '自动' : backup.trigger === 'pre_restore' ? '恢复前' : '手动'}</td>
                      <td>{backup.size_bytes ? `${(backup.size_bytes / 1024).toFixed(1)} KB` : '—'}</td>
                      <td><span className={`status ${backup.status === 'success' ? 'status-running' : 'status-cancelled'}`}><i />{backup.status === 'success' ? '成功' : '失败'}</span></td>
                      <td title={backup.checksum_sha256 || ''}>{backup.checksum_sha256 ? `${backup.checksum_sha256.slice(0, 12)}…` : '—'}</td>
                      <td>{new Date(backup.created_at).toLocaleString('zh-CN', { hour12: false })}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
          {backups.length > pageSize && <Pagination page={backupPage} pageSize={pageSize} total={backups.length} onPageChange={setBackupPage} />}
          <div className="panel full-panel integrity-panel">
            <div className="integrity-head">
              <div className="integrity-title">
                <span className="integrity-title-icon"><ShieldCheck size={19} /></span>
                <div>
                  <h2>证据完整性检查</h2>
                  <p>核对生产照片的大小和 SHA-256，发现缺失、替换或历史未哈希文件。</p>
                </div>
              </div>
              <div className="integrity-actions">
                <button
                  type="button"
                  className="outline-button"
                  disabled={integrityChecking}
                  onClick={handleIntegrityCheck}
                >
                  <ShieldCheck size={15} />
                  {integrityChecking ? '正在检查...' : '开始检查'}
                </button>
                <button
                  type="button"
                  className="outline-button"
                  disabled={!integrityResult?.issues.length}
                  onClick={exportIntegrityIssues}
                >
                  <Download size={15} />导出异常清单
                </button>
              </div>
            </div>
            {integrityError && <div className="network-message error integrity-message"><CircleAlert size={16} />{integrityError}</div>}
            {integrityResult ? (
              <>
                <div className="integrity-summary">
                  <div className="integrity-stat">
                    <span>检查文件</span>
                    <strong>{integrityResult.total}</strong>
                  </div>
                  <div className="integrity-stat ok">
                    <span>正常</span>
                    <strong>{integrityResult.ok}</strong>
                  </div>
                  <div className={`integrity-stat ${integrityIssueCount('missing') ? 'issue' : ''}`}>
                    <span>文件缺失</span>
                    <strong>{integrityIssueCount('missing')}</strong>
                  </div>
                  <div className={`integrity-stat ${integrityIssueCount('size_mismatch') ? 'issue' : ''}`}>
                    <span>大小异常</span>
                    <strong>{integrityIssueCount('size_mismatch')}</strong>
                  </div>
                  <div className={`integrity-stat ${integrityIssueCount('hash_mismatch') ? 'issue' : ''}`}>
                    <span>哈希异常</span>
                    <strong>{integrityIssueCount('hash_mismatch')}</strong>
                  </div>
                  <div className={`integrity-stat ${integrityIssueCount('unhashed') ? 'warning' : ''}`}>
                    <span>历史未哈希</span>
                    <strong>{integrityIssueCount('unhashed')}</strong>
                  </div>
                </div>
                <div className="integrity-result-meta">
                  检查时间：{new Date(integrityResult.checked_at).toLocaleString('zh-CN', { hour12: false })}
                </div>
                {integrityResult.issue_count === 0 ? (
                  <div className="integrity-success"><Check size={17} />本次检查未发现证据完整性异常。</div>
                ) : (
                  <div className="table-wrap integrity-table">
                    <table>
                      <thead>
                        <tr>
                          <th>文件编号</th>
                          <th>异常类型</th>
                          <th>预期大小</th>
                          <th>实际大小</th>
                          <th>预期 SHA-256</th>
                          <th>实际 SHA-256</th>
                        </tr>
                      </thead>
                      <tbody>
                        {integrityResult.issues.map((item) => (
                          <tr key={item.file_id}>
                            <td className="order-id">{item.file_id}</td>
                            <td>
                              <span className={`status ${item.status === 'unhashed' ? 'status-pending' : 'status-cancelled'}`}>
                                <i />{evidenceIntegrityLabels[item.status]}
                              </span>
                            </td>
                            <td>{formatFileSize(item.expected_size_bytes)}</td>
                            <td>{formatFileSize(item.actual_size_bytes)}</td>
                            <td><code className="integrity-hash">{item.expected_sha256 || '—'}</code></td>
                            <td><code className="integrity-hash">{item.actual_sha256 || '—'}</code></td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </>
            ) : !integrityError ? (
              <div className="integrity-empty">尚未执行检查。该操作只读取文件和哈希，不会修改或删除证据。</div>
            ) : null}
          </div>
          <div className="panel full-panel bug-report-panel">
            <div className="integrity-head">
              <div className="integrity-title">
                <span className="integrity-title-icon bug-report-title-icon"><CircleAlert size={19} /></span>
                <div>
                  <h2>BUG 反馈邮件</h2>
                  <p>查看反馈发送状态，并在邮件服务恢复后重试失败记录。</p>
                </div>
              </div>
              <div className="integrity-actions">
                <button
                  type="button"
                  className="outline-button"
                  disabled={smtpTesting}
                  onClick={handleTestSmtp}
                >
                  <Mail size={15} />
                  {smtpTesting ? '正在发送...' : '发送测试邮件'}
                </button>
              </div>
            </div>
            {bugReportMessage && <div className="network-message success bug-report-message"><Check size={16} />{bugReportMessage}</div>}
            {bugReportError && <div className="network-message error bug-report-message"><CircleAlert size={16} />{bugReportError}</div>}
            {bugReports.length === 0 ? (
              <div className="integrity-empty">暂无 BUG 反馈记录。</div>
            ) : (
              <div className="table-wrap bug-report-table">
                <table>
                  <thead>
                    <tr>
                      <th>状态</th>
                      <th>来源</th>
                      <th>提交人</th>
                      <th>问题描述</th>
                      <th>图片</th>
                      <th>创建时间</th>
                      <th>操作</th>
                    </tr>
                  </thead>
                  <tbody>
                    {bugReports.map((report) => (
                      <tr key={report.id}>
                        <td>
                          <span className={`status ${bugReportStatusClass(report.status)}`}>
                            <i />{bugReportStatusLabels[report.status]}
                          </span>
                        </td>
                        <td>{report.source === 'pc' ? '电脑端' : '平板端'}</td>
                        <td>
                          <span className="order-id">{report.reporter_username || '—'}</span>
                          <small className="muted bug-report-reporter">{report.reporter_name || '—'}</small>
                        </td>
                        <td>
                          <span className="bug-report-description" title={report.description}>{report.description}</span>
                          {report.error_message && <small className="bug-report-error" title={report.error_message}>{report.error_message}</small>}
                        </td>
                        <td>{report.image_count}</td>
                        <td>{new Date(report.created_at).toLocaleString('zh-CN', { hour12: false })}</td>
                        <td>
                          {(report.status === 'failed' || report.status === 'pending') ? (
                            <button
                              type="button"
                              className="text-button"
                              disabled={retryingBugReportId === report.id}
                              onClick={() => handleRetryBugReport(report)}
                            >
                              {retryingBugReportId === report.id ? '正在重试...' : '重试发送'}
                            </button>
                          ) : report.status === 'sending' ? (
                            <span className="muted">发送中</span>
                          ) : (
                            <span className="muted">—</span>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
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
      {editUser && (
        <CreateUserModal
          existing={editUser}
          onClose={() => setEditUser(null)}
          onSuccess={() => {
            loadUsers()
          }}
        />
      )}
      {resetResult && (
        <Modal title="密码已重置" onClose={() => setResetResult(null)}>
          <div className="modal-form">
            <label>
              账号
              <strong className="reset-password-field">{resetResult.username}</strong>
            </label>
            <label>
              操作员
              <strong className="reset-password-field">{resetResult.display_name}</strong>
            </label>
            <label>
              一次初始密码
              <div className="reset-password-line">
                <code>{resetResult.temporary_password}</code>
                <button type="button" className="outline-button" onClick={copyResetPassword}>
                  {copied ? <Check size={15} /> : <Copy size={15} />}
                  {copied ? '已复制' : '复制'}
                </button>
              </div>
            </label>
            <p className="muted" style={{ margin: 0 }}>
              关闭窗口后管理员将无法再次查看该初始密码。
            </p>
            <div className="modal-footer">
              <button className="primary-button" onClick={() => setResetResult(null)}>我已复制并关闭</button>
            </div>
          </div>
        </Modal>
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
