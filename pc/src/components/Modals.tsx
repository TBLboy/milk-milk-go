import React, { useState, useEffect, useRef } from 'react'
import { createPortal } from 'react-dom'
import { CheckCircle2, CircleDashed, Clock3, ImagePlus, PackageCheck, PlayCircle, X, Plus, Trash2 } from 'lucide-react'
import { api } from '../services/api'

export function Modal({ title, onClose, children }: { title: string; onClose: () => void; children: React.ReactNode }) {
  return (
    <div className="modal-backdrop">
      <div className="modal-dialog">
        <div className="modal-header">
          <h3>{title}</h3>
          <button className="icon-btn" onClick={onClose}><X size={18} /></button>
        </div>
        <div className="modal-body">{children}</div>
      </div>
    </div>
  )
}

// 1. 新建工单弹窗
export function CreateOrderModal({ onClose, onSuccess }: { onClose: () => void; onSuccess: () => void }) {
  const [products, setProducts] = useState<any[]>([])
  const [users, setUsers] = useState<any[]>([])
  const [productId, setProductId] = useState<number | ''>('')
  const [operatorId, setOperatorId] = useState<number | ''>('')
  const [targetWeight, setTargetWeight] = useState<number>(1000)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    api.getProducts().then((res) => {
      setProducts(res)
      if (res.length > 0) setProductId(res[0].id)
    })
    api.listUsers().then((res) => {
      setUsers((res || []).filter((item: any) => item.role === 'operator'))
    }).catch(() => setUsers([]))
  }, [])

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!productId) {
      setError('请选择产品')
      return
    }
    setLoading(true)
    setError(null)
    try {
      await api.createWorkOrder({
        product_id: Number(productId),
        target_weight_kg: Number(targetWeight),
        operator_id: operatorId === '' ? null : Number(operatorId),
      })
      onSuccess()
      onClose()
    } catch (err: any) {
      setError(err.message || '创建工单失败')
    } finally {
      setLoading(false)
    }
  }

  return (
    <Modal title="新建生产工单" onClose={onClose}>
      <form onSubmit={handleSubmit} className="modal-form">
        {error && <div className="modal-error">{error}</div>}
        <label>
          选择生产产品
          <select value={productId} onChange={(e) => setProductId(Number(e.target.value))}>
            {products.map((p) => (
              <option key={p.id} value={p.id}>{p.name}</option>
            ))}
          </select>
        </label>
        <label>
          目标生产重量 (kg)
          <input
            type="number"
            min={1}
            step={1}
            value={targetWeight}
            onChange={(e) => setTargetWeight(Number(e.target.value))}
            required
          />
        </label>
        <label>
          操作员（可选，不选则创建后待指派）
          <select value={operatorId} onChange={(e) => setOperatorId(e.target.value === '' ? '' : Number(e.target.value))}>
            <option value="">暂不指派</option>
            {users.map((user) => <option key={user.id} value={user.id}>{user.display_name} · {user.username}</option>)}
          </select>
        </label>
        <p className="form-hint">系统将根据配方比例自动计算出辅料种类与应称重量。</p>
        <div className="modal-footer">
          <button type="button" className="outline-button" onClick={onClose}>取消</button>
          <button type="submit" className="primary-button" disabled={loading}>
            {loading ? '创建中...' : '确认创建'}
          </button>
        </div>
      </form>
    </Modal>
  )
}

export function OrderDetailModal({ orderNo, onClose, onSuccess }: { orderNo: string; onClose: () => void; onSuccess?: () => void }) {
  const [order, setOrder] = useState<any>(null)
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  const load = () => {
    api.getWorkOrder(orderNo).then(setOrder).catch((err) => setError(err.message))
  }

  useEffect(() => { load() }, [orderNo])

  const act = async (action: () => Promise<any>) => {
    setBusy(true)
    setError(null)
    try {
      await action()
      await load()
      onSuccess?.()
    } catch (e: any) {
      setError(e.message)
    } finally {
      setBusy(false)
    }
  }

  if (!order) return (
    <Modal title={`工单 ${orderNo}`} onClose={onClose}>
      <div className="loading" style={{ minHeight: '180px' }}>{error || '正在加载工单...'}</div>
    </Modal>
  )

  const completed = order.steps.filter((s: any) => s.status === 'completed').length
  return (
    <Modal title={`工单详情 · ${order.order_no}`} onClose={onClose}>
      <div className="order-detail">
        <div className="detail-summary">
          <div>
            <span>产品</span>
            <strong>{order.product_name}</strong>
          </div>
          <div>
            <span>目标重量</span>
            <strong>{order.target_weight_kg.toLocaleString()} kg</strong>
          </div>
          <div>
            <span>执行人</span>
            <strong>{order.operator_name || '待指派'}</strong>
          </div>
          <div>
            <span>工单状态</span>
            <strong><span className={`status ${order.status === 'in_progress' ? 'status-running' : order.status === 'completed' ? 'status-done' : order.status === 'cancelled' || order.status === 'deleted' ? 'status-cancelled' : 'status-pending'}`}><i />{order.status === 'in_progress' ? '执行中' : order.status === 'completed' ? '已完成' : order.status === 'cancelled' ? '已撤销' : order.status === 'deleted' ? '已删除' : '待审批'}</span></strong>
          </div>
        </div>
        <div className="progress-row detail-progress">
          <span>整体进度</span>
          <div className="progress"><i style={{ width: `${(completed / (order.steps.length || 1)) * 100}%` }} /></div>
          <strong>{completed}/{order.steps.length}</strong>
        </div>
        <div className="step-list">
          {order.steps.map((step: any) => (
            <div className="step-row" key={step.step_no}>
              <div className={`step-state ${step.status === 'completed' ? 'done' : step.status === 'weighing' ? 'active' : ''}`}>
                {step.status === 'completed' ? <CheckCircle2 size={18} /> : step.status === 'weighing' ? <PackageCheck size={18} /> : step.status === 'type_confirmation' ? <CircleDashed size={18} /> : <Clock3 size={18} />}
              </div>
              <div className="step-copy">
                <strong>步骤 {step.step_no} · {step.material_name}</strong>
                <span>内部代号 {step.material_code} · 应称 {step.required_weight_kg} kg · 允差 ±{step.tolerance_kg} kg</span>
                <StepEvidence step={step} />
              </div>
              <span className="step-status">{step.status === 'completed' ? '已完成' : step.status === 'weighing' ? '待称重' : step.status === 'type_confirmation' ? '待审批' : '待确认'}</span>
            </div>
          ))}
        </div>
        {order.requests && order.requests.length > 0 && (
          <div className="step-list request-list">
            <div className="detail-section-title">工单申请</div>
            {order.requests.map((request: any) => (
              <div className="step-row request-row" key={request.id}>
                <div className="step-copy">
                  <strong>{request.request_type === 'takeover' ? '接管申请' : request.request_type === 'cancel' ? '撤销申请' : '历史删除申请'} · {request.requester_name || `用户 #${request.requested_by}`}</strong>
                  <span>{request.reason}</span>
                </div>
                <span className={`request-status ${request.status}`}>{request.status === 'pending' ? '待审批' : request.status === 'approved' ? '已通过' : '已驳回'}</span>
              </div>
            ))}
          </div>
        )}
        {error && <div className="modal-error">{error}</div>}
        <div className="modal-footer">
          <button type="button" className="outline-button" onClick={onClose}>关闭</button>
          {order.status === 'pending_approval' && (
            <button type="button" className="primary-button" disabled={busy} onClick={() => act(() => api.approveWorkOrder(order.order_no))}>
              <CheckCircle2 size={16} />批准工单
            </button>
          )}
          {order.status === 'approved' && (
            <button type="button" className="primary-button" disabled={busy} onClick={() => act(() => api.startWorkOrder(order.order_no))}>
              <PlayCircle size={16} />开始执行
            </button>
          )}
          {order.status === 'in_progress' && completed === order.steps.length && (
            <button type="button" className="primary-button" disabled={busy} onClick={() => act(() => api.completeWorkOrder(order.order_no))}>
              <CheckCircle2 size={16} />提交完成
            </button>
          )}
          {(order.status === 'pending_approval' || order.status === 'approved' || order.status === 'in_progress') && (
            <button
              type="button"
              className="reject-button"
              disabled={busy}
              onClick={() => {
                if (window.confirm(`确认撤销工单 ${order.order_no}？撤销后仍会保留历史记录。`)) {
                  act(() => api.cancelWorkOrder(order.order_no))
                }
              }}
            >
              <X size={15} />撤销工单
            </button>
          )}
        </div>
      </div>
    </Modal>
  )
}

function StepEvidence({ step }: { step: any }) {
  const confirmations = step.confirmations || []
  const attempts = step.weighing_attempts || []
  if (confirmations.length === 0 && attempts.length === 0) return null
  const statusText: Record<string, string> = { passed: '通过', rejected: '未通过', pending: '待审批' }
  return (
    <div className="step-evidence-list">
      {confirmations.map((conf: any) => (
        <div className="step-evidence-item" key={`conf-${conf.id}`}>
          <span>类型确认 · {conf.method === 'qr' ? '扫码' : '拍照'} · {statusText[conf.status] || conf.status}</span>
          {conf.scanned_material_id && <small>扫码：{conf.scanned_material_id}</small>}
          {conf.reason && <small>理由：{conf.reason}</small>}
          {conf.evidence_file_id && <EvidenceThumb fileId={conf.evidence_file_id} />}
        </div>
      ))}
      {attempts.map((item: any) => (
        <div className="step-evidence-item" key={`weight-${item.id}`}>
          <span>称重 {item.weight_kg} kg · {item.passed ? '通过' : '超差'}</span>
          <small>{item.weight_source === 'manual' ? '手动读数' : item.weight_source}</small>
          <EvidenceThumb fileId={item.scale_photo_file_id} />
        </div>
      ))}
    </div>
  )
}

export function EvidenceThumb({ fileId, className = '' }: { fileId: string; className?: string }) {
  const [src, setSrc] = useState<string | null>(null)
  const [previewOpen, setPreviewOpen] = useState(false)
  useEffect(() => {
    let cancelled = false
    api.getFileUrl(fileId).then((url) => {
      if (!cancelled) setSrc(url)
    }).catch(() => {
      if (!cancelled) setSrc(null)
    })
    return () => { cancelled = true }
  }, [fileId])
  useEffect(() => {
    if (!previewOpen) return
    const previousOverflow = document.body.style.overflow
    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key === 'Escape') setPreviewOpen(false)
    }
    document.body.style.overflow = 'hidden'
    window.addEventListener('keydown', closeOnEscape)
    return () => {
      document.body.style.overflow = previousOverflow
      window.removeEventListener('keydown', closeOnEscape)
    }
  }, [previewOpen])

  if (!src) return null
  return (
    <>
      <button
        type="button"
        className="evidence-thumb-button"
        onClick={() => setPreviewOpen(true)}
        aria-label="放大查看现场证据图片"
      >
        <img className={`evidence-thumb ${className}`.trim()} src={src} alt="现场证据图片" />
      </button>
      {previewOpen && createPortal(
        <div className="image-lightbox" onClick={() => setPreviewOpen(false)}>
          <img src={src} alt="放大后的现场证据图片" onClick={(event) => event.stopPropagation()} />
        </div>,
        document.body,
      )}
    </>
  )
}

export function RecipeDetailModal({ product, onClose }: { product: any; onClose: () => void }) {
  const enabled = product.recipe_enabled !== false
  return (
    <Modal title={`产品配方 · ${product.name}`} onClose={onClose}>
      <div className="order-detail">
        <div className="detail-summary">
          <div><span>产品名称</span><strong>{product.name}</strong></div>
          <div><span>配方版本</span><strong>{product.recipe_version || 1}</strong></div>
          <div><span>辅料种类</span><strong>{(product.items || []).length} 种</strong></div>
          <div><span>配方状态</span><strong><span className={enabled ? 'status status-running' : 'status status-cancelled'}><i />{enabled ? '启用' : '停用'}</span></strong></div>
        </div>
        <div className="step-list">
          {(product.items || []).map((item: any) => (
            <div className="step-row" key={`${item.material_id}-${item.sort_order}`}>
              <div className="step-state done"><PackageCheck size={18} /></div>
              <div className="step-copy">
                <strong>{item.name_zh} · {item.material_code}</strong>
                <span>辅料 ID：{item.material_id}</span>
              </div>
              <span className="step-status">{item.quantity_per_ton_kg} kg/吨</span>
            </div>
          ))}
        </div>
        <div className="modal-footer">
          <button type="button" className="outline-button" onClick={onClose}>关闭</button>
        </div>
      </div>
    </Modal>
  )
}

// 2. 新增/编辑辅料弹窗
export function CreateMaterialModal({ onClose, onSuccess, material }: { onClose: () => void; onSuccess: () => void; material?: any }) {
  const isEdit = Boolean(material)
  const [code, setCode] = useState(material?.material_code || '')
  const [name, setName] = useState(material?.name_zh || '')
  const [nameEn, setNameEn] = useState(material?.name_en || '')
  const [shelfLife, setShelfLife] = useState(material?.shelf_life_months ?? 24)
  const [imageFileIds, setImageFileIds] = useState<string[]>((material?.images || []).map((image: any) => image.file_id))
  const [previews, setPreviews] = useState<string[]>([])
  const [loading, setLoading] = useState(false)
  const [deleting, setDeleting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    const images = material?.images || []
    if (images.length === 0) return
    Promise.all(images.map((image: any) => api.getFileUrl(image.file_id).catch(() => '')))
      .then(setPreviews)
      .catch(() => setPreviews([]))
  }, [])

  const handleFiles = async (files: FileList | null) => {
    if (!files) return
    setLoading(true)
    setError(null)
    try {
      for (const file of Array.from(files)) {
        const uploaded = await api.uploadFile(file)
        setImageFileIds((ids) => [...ids, uploaded.file_id])
        setPreviews((urls) => [...urls, URL.createObjectURL(file)])
      }
    } catch (e: any) {
      setError(e.message || '图片上传失败')
    } finally {
      setLoading(false)
    }
  }

  const removeImage = (index: number) => {
    setImageFileIds((ids) => ids.filter((_, imageIndex) => imageIndex !== index))
    setPreviews((urls) => urls.filter((_, imageIndex) => imageIndex !== index))
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setLoading(true)
    setError(null)
    const payload = {
      material_code: code.trim().toUpperCase(),
      name_zh: name.trim(),
      name_en: nameEn.trim() || undefined,
      shelf_life_months: Number(shelfLife),
      image_file_ids: imageFileIds,
    }
    try {
      if (isEdit && material) {
        await api.updateMaterial(material.material_id, payload)
      } else {
        await api.createMaterial(payload)
      }
      onSuccess()
      onClose()
    } catch (err: any) {
      setError(err.message || (isEdit ? '编辑辅料失败' : '新增辅料失败'))
    } finally {
      setLoading(false)
    }
  }

  const handleDelete = async () => {
    if (!isEdit || !material) return
    if (!window.confirm(`确认删除辅料「${material.name_zh}」？删除后不可恢复。`)) return
    setDeleting(true)
    setError(null)
    try {
      await api.deleteMaterial(material.material_id)
      onSuccess()
      onClose()
    } catch (err: any) {
      setError(err.message || '删除辅料失败')
      setDeleting(false)
    }
  }

  return (
    <Modal title={isEdit ? `编辑辅料 · ${material?.material_code}` : '新增辅料物料'} onClose={onClose}>
      <form onSubmit={handleSubmit} className="modal-form">
        {error && <div className="modal-error">{error}</div>}
        <label>
          内部代号 (如 A1, E2, F-02)
          <input
            type="text"
            placeholder="例如: A1"
            value={code}
            onChange={(e) => setCode(e.target.value)}
            required
          />
        </label>
        <label>
          辅料中文名称
          <input
            type="text"
            placeholder="例如: 精制白砂糖"
            value={name}
            onChange={(e) => setName(e.target.value)}
            required
          />
        </label>
        <label>
          英文名称（可选）
          <input
            type="text"
            placeholder="例如: White Sugar"
            value={nameEn}
            onChange={(e) => setNameEn(e.target.value)}
          />
        </label>
        <label>
          保质期 (月)
          <input
            type="number"
            min={1}
            value={shelfLife}
            onChange={(e) => setShelfLife(Number(e.target.value))}
            required
          />
        </label>
        <div className="form-sub-header">
          <span>包装外观图片（多张）</span>
          <label className="text-button file-upload-button">
            <ImagePlus size={15} />选择图片
            <input type="file" accept="image/jpeg,image/png,image/webp" multiple hidden onChange={(e) => handleFiles(e.target.files)} />
          </label>
        </div>
        {previews.length > 0 && (
          <div className="image-preview-row material-image-edit">
            {previews.map((url, index) => (
              <div className="image-preview-item" key={`${url}-${index}`}>
                <img src={url} alt={`包装图片 ${index + 1}`} />
                <button type="button" className="image-remove-btn" onClick={() => removeImage(index)} aria-label="移除图片">
                  <X size={13} />
                </button>
              </div>
            ))}
          </div>
        )}
        <div className="modal-footer">
          {isEdit && (
            <button type="button" className="danger-button" onClick={handleDelete} disabled={deleting || loading}>
              <Trash2 size={15} />{deleting ? '删除中...' : '删除辅料'}
            </button>
          )}
          <button type="button" className="outline-button" onClick={onClose}>取消</button>
          <button type="submit" className="primary-button" disabled={loading || deleting}>
            {loading ? '保存中...' : '保存辅料'}
          </button>
        </div>
      </form>
    </Modal>
  )
}

export function MaterialImageModal({ material, onClose }: { material: any; onClose: () => void }) {
  const [urls, setUrls] = useState<string[]>([])

  useEffect(() => {
    const images = material?.images || []
    if (images.length === 0) {
      setUrls([])
      return
    }
    Promise.all(images.map((image: any) => api.getFileUrl(image.file_id).catch(() => '')))
      .then(setUrls)
      .catch(() => setUrls([]))
  }, [material])

  return (
    <Modal title={`包装图片 · ${material?.name_zh} (${material?.material_code})`} onClose={onClose}>
      {urls.length === 0 ? (
        <div className="empty-panel" style={{ padding: '2rem', textAlign: 'center', color: '#64748b' }}>暂无包装图片</div>
      ) : (
        <div className="material-image-grid">
          {urls.map((url, index) => url ? (
            <img key={`${url}-${index}`} src={url} alt={`${material?.name_zh} 包装图片 ${index + 1}`} />
          ) : null)}
        </div>
      )}
      <div className="modal-footer">
        <button type="button" className="outline-button" onClick={onClose}>关闭</button>
      </div>
    </Modal>
  )
}

// 3. 新增产品与配方弹窗
export function CreateProductModal({ onClose, onSuccess, product }: { onClose: () => void; onSuccess: () => void; product?: any }) {
  const isEdit = Boolean(product)
  const [name, setName] = useState(product?.name || '')
  const [materials, setMaterials] = useState<any[]>([])
  const [items, setItems] = useState<{ material_id: string; quantity_per_ton_kg: number }[]>([])
  const [imageFileId, setImageFileId] = useState<string | null>(product?.image_file_id || null)
  const [imagePreview, setImagePreview] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  const [deleting, setDeleting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    api.getMaterials().then((res) => {
      setMaterials(res)
      if (product?.items?.length) {
        setItems(product.items.map((it: any) => ({ material_id: it.material_id, quantity_per_ton_kg: Number(it.quantity_per_ton_kg) })))
      } else if (res.length > 0) {
        setItems([{ material_id: res[0].material_id, quantity_per_ton_kg: 5 }])
      }
    })
    if (product?.image_file_id) {
      api.getFileUrl(product.image_file_id).then(setImagePreview).catch(() => {})
    }
  }, [])

  const addItem = () => {
    if (materials.length > 0) {
      setItems([...items, { material_id: materials[0].material_id, quantity_per_ton_kg: 1 }])
    }
  }

  const removeItem = (index: number) => {
    setItems(items.filter((_, i) => i !== index))
  }

  const updateItem = (index: number, field: string, value: any) => {
    const updated = [...items]
    updated[index] = { ...updated[index], [field]: value }
    setItems(updated)
  }

  const handleImageUpload = async (file: File | undefined) => {
    if (!file) return
    setLoading(true)
    setError(null)
    try {
      const uploaded = await api.uploadFile(file)
      setImageFileId(uploaded.file_id)
      setImagePreview(URL.createObjectURL(file))
    } catch (e: any) {
      setError(e.message || '产品图片上传失败')
    } finally {
      setLoading(false)
    }
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!name.trim()) return setError('请输入产品名称')
    if (items.length === 0) return setError('请至少添加一种辅料')
    setLoading(true)
    setError(null)
    try {
      const payload = {
        name: name.trim(),
        items: items.map((it) => ({
          material_id: it.material_id,
          quantity_per_ton_kg: Number(it.quantity_per_ton_kg),
        })),
        image_file_id: imageFileId || undefined,
      }
      if (isEdit) {
        await api.updateProduct(product.id, payload)
      } else {
        await api.createProduct(payload)
      }
      onSuccess()
      onClose()
    } catch (err: any) {
      setError(err.message || (isEdit ? '编辑产品失败' : '新增产品失败'))
    } finally {
      setLoading(false)
    }
  }

  const handleDelete = async () => {
    if (!isEdit || !product) return
    if (!window.confirm(`确认删除配方「${product.name}」？删除后不可恢复。`)) return
    setDeleting(true)
    setError(null)
    try {
      await api.deleteProduct(product.id)
      onSuccess()
      onClose()
    } catch (err: any) {
      setError(err.message || '删除配方失败')
      setDeleting(false)
    }
  }

  return (
    <Modal title={isEdit ? '编辑产品及辅料配方' : '新增产品及辅料配方'} onClose={onClose}>
      <form onSubmit={handleSubmit} className="modal-form">
        {error && <div className="modal-error">{error}</div>}
        <label>
          产品名称
          <input
            type="text"
            placeholder="例如: 高钙鲜牛奶 250ml"
            value={name}
            onChange={(e) => setName(e.target.value)}
            required
          />
        </label>
        <div className="form-sub-header">
          <span>产品图片（可选）</span>
          <label className="text-button file-upload-button">
            <ImagePlus size={15} />选择图片
            <input type="file" accept="image/jpeg,image/png,image/webp" hidden onChange={(e) => handleImageUpload(e.target.files?.[0])} />
          </label>
        </div>
        {imagePreview && <div className="image-preview-row"><img src={imagePreview} alt="产品图片预览" /></div>}
        <div className="form-sub-header">
          <span>辅料用量 (每吨成品)</span>
          <button type="button" className="text-button" onClick={addItem}><Plus size={14} />添加辅料</button>
        </div>
        <div className="items-list">
          {items.map((item, idx) => (
            <div className="item-row" key={idx}>
              <select
                value={item.material_id}
                onChange={(e) => updateItem(idx, 'material_id', e.target.value)}
              >
                {materials.map((m) => (
                  <option key={m.material_id} value={m.material_id}>
                    {m.name_zh} ({m.material_code})
                  </option>
                ))}
              </select>
              <input
                type="number"
                step="any"
                min="0.001"
                placeholder="千克/吨"
                value={item.quantity_per_ton_kg}
                onChange={(e) => updateItem(idx, 'quantity_per_ton_kg', Number(e.target.value))}
                required
              />
              <span className="unit-label">kg/吨</span>
              {items.length > 1 && (
                <button type="button" className="icon-btn danger" onClick={() => removeItem(idx)}>
                  <Trash2 size={16} />
                </button>
              )}
            </div>
          ))}
        </div>
        <div className="modal-footer">
          {isEdit && (
            <button type="button" className="danger-button" onClick={handleDelete} disabled={deleting || loading}>
              <Trash2 size={15} />{deleting ? '删除中...' : '删除配方'}
            </button>
          )}
          <button type="button" className="outline-button" onClick={onClose}>取消</button>
          <button type="submit" className="primary-button" disabled={loading || deleting}>
            {loading ? '保存中...' : '保存配方'}
          </button>
        </div>
      </form>
    </Modal>
  )
}

// 4. 新建/编辑账号弹窗
export function CreateUserModal({ onClose, onSuccess, existing }: { onClose: () => void; onSuccess: () => void; existing?: any }) {
  const [username, setUsername] = useState(existing?.username || '')
  const [displayName, setDisplayName] = useState(existing?.display_name || '')
  const [password, setPassword] = useState('')
  const [phone, setPhone] = useState(existing?.phone || '')
  const [idCard, setIdCard] = useState(existing?.id_card || '')
  const [avatarFileId, setAvatarFileId] = useState(existing?.avatar_file_id || '')
  const [avatarFile, setAvatarFile] = useState<File | null>(null)
  const [avatarUrl, setAvatarUrl] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    if (!existing?.avatar_file_id) return
    let url = ''
    api.getFileUrl(existing.avatar_file_id).then((value) => {
      url = value
      setAvatarUrl(value)
    }).catch(() => setAvatarUrl(''))
    return () => { if (url) URL.revokeObjectURL(url) }
  }, [existing?.avatar_file_id])

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setLoading(true)
    setError(null)
    try {
      let avatarId = avatarFileId
      if (avatarFile) {
        const uploaded = await api.uploadFile(avatarFile)
        avatarId = uploaded.file_id
      }
      const payload = {
        display_name: displayName.trim(),
        phone: phone.trim(),
        id_card: idCard.trim(),
        avatar_file_id: avatarId || null,
      }
      if (existing) {
        await api.updateUserProfile(existing.id, payload)
      } else {
        await api.registerUser({
          ...payload,
          username: username.trim(),
          password: password.trim(),
        })
      }
      onSuccess()
      onClose()
    } catch (err: any) {
      setError(err.message || (existing ? '保存账号资料失败' : '创建账号失败'))
    } finally {
      setLoading(false)
    }
  }

  return (
    <Modal title={existing ? '编辑操作员资料' : '新建操作员账号'} onClose={onClose}>
      <form onSubmit={handleSubmit} className="modal-form">
        {error && <div className="modal-error">{error}</div>}
        <label>
          头像
          <div className="avatar-edit-row">
            <div className="avatar-edit-preview">
              {avatarUrl ? <img src={avatarUrl} alt="头像" /> : <span className="operator-dot">{displayName.slice(0, 1) || '牧'}</span>}
            </div>
            <button type="button" className="outline-button" onClick={() => fileInputRef.current?.click()}>
              {avatarFileId || avatarFile ? '更换头像' : '选择头像'}
            </button>
            <input
              ref={fileInputRef}
              type="file"
              accept="image/*"
              hidden
              onChange={(e) => {
                const file = e.target.files?.[0]
                if (!file) return
                setAvatarFile(file)
                setAvatarUrl(URL.createObjectURL(file))
              }}
            />
          </div>
        </label>
        <label>
          登录工号 / 用户名
          <input
            type="text"
            placeholder="例如: operator05"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            disabled={Boolean(existing)}
            required
          />
        </label>
        <label>
          操作员姓名
          <input
            type="text"
            placeholder="例如: 张三"
            value={displayName}
            onChange={(e) => setDisplayName(e.target.value)}
            required
          />
        </label>
        {!existing && (
          <label>
            初始密码
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              minLength={8}
              required
            />
          </label>
        )}
        <label>
          电话
          <input type="text" value={phone} onChange={(e) => setPhone(e.target.value)} placeholder="选填" />
        </label>
        <label>
          身份证
          <input type="text" value={idCard} onChange={(e) => setIdCard(e.target.value)} placeholder="管理员维护，列表脱敏显示" />
        </label>
        <div className="modal-footer">
          <button type="button" className="outline-button" onClick={onClose}>取消</button>
          <button type="submit" className="primary-button" disabled={loading}>
            {loading ? (existing ? '保存中...' : '创建中...') : existing ? '保存资料' : '确认创建'}
          </button>
        </div>
      </form>
    </Modal>
  )
}
