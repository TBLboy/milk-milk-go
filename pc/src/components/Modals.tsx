import React, { useState, useEffect } from 'react'
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
            <strong><span className={`status ${order.status === 'in_progress' ? 'status-running' : order.status === 'completed' ? 'status-done' : order.status === 'cancelled' ? 'status-cancelled' : 'status-pending'}`}><i />{order.status === 'in_progress' ? '执行中' : order.status === 'completed' ? '已完成' : order.status === 'cancelled' ? '已撤销' : '待审批'}</span></strong>
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
              </div>
              <span className="step-status">{step.status === 'completed' ? '已完成' : step.status === 'weighing' ? '待称重' : step.status === 'type_confirmation' ? '待审批' : '待确认'}</span>
            </div>
          ))}
        </div>
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

export function RecipeDetailModal({ product, onClose }: { product: any; onClose: () => void }) {
  return (
    <Modal title={`产品配方 · ${product.name}`} onClose={onClose}>
      <div className="order-detail">
        <div className="detail-summary">
          <div><span>产品名称</span><strong>{product.name}</strong></div>
          <div><span>配方版本</span><strong>{product.recipe_version || 1}</strong></div>
          <div><span>辅料种类</span><strong>{(product.items || []).length} 种</strong></div>
          <div><span>配方状态</span><strong><span className="status status-running"><i />启用</span></strong></div>
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

// 2. 新增辅料弹窗
export function CreateMaterialModal({ onClose, onSuccess }: { onClose: () => void; onSuccess: () => void }) {
  const [code, setCode] = useState('')
  const [name, setName] = useState('')
  const [nameEn, setNameEn] = useState('')
  const [shelfLife, setShelfLife] = useState(24)
  const [imageFileIds, setImageFileIds] = useState<string[]>([])
  const [previews, setPreviews] = useState<string[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

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

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setLoading(true)
    setError(null)
    try {
      await api.createMaterial({
        material_code: code.trim().toUpperCase(),
        name_zh: name.trim(),
        name_en: nameEn.trim() || undefined,
        shelf_life_months: Number(shelfLife),
        image_file_ids: imageFileIds,
      })
      onSuccess()
      onClose()
    } catch (err: any) {
      setError(err.message || '新增辅料失败')
    } finally {
      setLoading(false)
    }
  }

  return (
    <Modal title="新增辅料物料" onClose={onClose}>
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
          <div className="image-preview-row">
            {previews.map((url, index) => <img key={`${url}-${index}`} src={url} alt={`包装图片 ${index + 1}`} />)}
          </div>
        )}
        <div className="modal-footer">
          <button type="button" className="outline-button" onClick={onClose}>取消</button>
          <button type="submit" className="primary-button" disabled={loading}>
            {loading ? '保存中...' : '保存辅料'}
          </button>
        </div>
      </form>
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
          <button type="button" className="outline-button" onClick={onClose}>取消</button>
          <button type="submit" className="primary-button" disabled={loading}>
            {loading ? '保存中...' : '保存配方'}
          </button>
        </div>
      </form>
    </Modal>
  )
}

// 4. 新建账号弹窗
export function CreateUserModal({ onClose, onSuccess }: { onClose: () => void; onSuccess: () => void }) {
  const [username, setUsername] = useState('')
  const [displayName, setDisplayName] = useState('')
  const [password, setPassword] = useState('12345678')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setLoading(true)
    setError(null)
    try {
      await api.registerUser({
        username: username.trim(),
        display_name: displayName.trim(),
        password: password.trim(),
        role: 'operator',
      })
      onSuccess()
      onClose()
    } catch (err: any) {
      setError(err.message || '创建账号失败')
    } finally {
      setLoading(false)
    }
  }

  return (
    <Modal title="新建操作员账号" onClose={onClose}>
      <form onSubmit={handleSubmit} className="modal-form">
        {error && <div className="modal-error">{error}</div>}
        <label>
          登录工号 / 用户名
          <input
            type="text"
            placeholder="例如: operator05"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
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
