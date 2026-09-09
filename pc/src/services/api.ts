import type { DashboardData, WorkOrder } from '../types/domain'
import { dashboardData as fallbackData } from '../data/mockData'

const API_BASE = '/api/v1'

function getAuthHeader(): Record<string, string> {
  const token = localStorage.getItem('milk_token')
  return token ? { Authorization: `Bearer ${token}` } : {}
}

function parseError(body: any): string {
  if (!body) return '请求失败'
  if (body.detail && typeof body.detail === 'object') return body.detail.message || body.detail.code || '请求失败'
  if (typeof body.detail === 'string') return body.detail
  return body.message || body.error || '请求失败'
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const headers: Record<string, string> = {
    ...getAuthHeader(),
    ...(options.headers as Record<string, string> | undefined || {}),
  }
  if (!(options.body instanceof FormData) && options.body !== undefined) {
    headers['Content-Type'] = 'application/json'
  }

  const response = await fetch(`${API_BASE}${path}`, { ...options, headers })
  if (!response.ok) {
    let errBody: any
    try {
      errBody = await response.json()
    } catch {
      errBody = { message: response.statusText }
    }
    throw new Error(parseError(errBody))
  }
  return response.json()
}

function orderToDomain(order: any): WorkOrder {
  const steps = order.steps || []
  const completed = steps.filter((s: any) => s.status === 'completed').length
  const hasAlert = steps.some((s: any) => s.status === 'rejected')
  return {
    id: order.order_no,
    product: order.product_name,
    batch: order.order_no.slice(-6),
    targetWeight: order.target_weight_kg,
    completedSteps: completed,
    totalSteps: steps.length || 1,
    operator: order.operator_name || (order.operator_id ? `操作员 #${order.operator_id}` : '待指派'),
    status: (order.status === 'in_progress'
      ? '执行中'
      : order.status === 'completed'
      ? '已完成'
      : order.status === 'cancelled'
      ? '已撤销'
      : order.status === 'approved'
      ? '已批准'
      : '待审批') as WorkOrder['status'],
    updatedAt: order.updated_at ? new Date(order.updated_at).toLocaleString('zh-CN', { hour12: false }) : '刚刚',
    alert: hasAlert ? '辅料扫码不匹配' : undefined,
  }
}

export const api = {
  // 认证
  async login(username: string, password: string): Promise<any> {
    const res = await request<any>('/auth/login', {
      method: 'POST',
      body: JSON.stringify({ username, password }),
    })
    localStorage.setItem('milk_token', res.access_token)
    localStorage.setItem('milk_role', res.user?.role || res.role)
    localStorage.setItem('milk_user', JSON.stringify(res.user || {}))
    return res
  },

  logout() {
    localStorage.removeItem('milk_token')
    localStorage.removeItem('milk_role')
    localStorage.removeItem('milk_user')
  },

  hasToken() {
    return Boolean(localStorage.getItem('milk_token'))
  },

  async getMe(): Promise<any> {
    const res = await request<any>('/auth/me')
    localStorage.setItem('milk_user', JSON.stringify(res.user || {}))
    return res.user
  },

  async listUsers(): Promise<any[]> {
    return request('/auth/users')
  },

  // 工作台数据
  async getDashboard(): Promise<DashboardData> {
    const ordersRes = await request<any[]>('/work-orders')
    const workOrders = (ordersRes || []).map(orderToDomain)
    const approvalsRes = await request<any[]>('/approvals').catch(() => [])
    const pendingApprovals = (approvalsRes || []).map((app) => ({
      id: String(app.confirmation_id || app.id),
      title: app.title,
      description: app.description,
      time: app.time || '刚刚',
      type: app.type || ('photo' as const),
    }))
    const inProgressCount = workOrders.filter((w) => w.status === '执行中').length
    const completedCount = workOrders.filter((w) => w.status === '已完成').length

    return {
      workOrders: workOrders.length > 0 ? workOrders : fallbackData.workOrders,
      stats: [
        { label: '今日工单', value: `${workOrders.length || fallbackData.workOrders.length}`, detail: '生产称量任务', tone: 'blue' },
        { label: '执行中', value: `${inProgressCount || 2}`, detail: '现场正在称重', tone: 'orange' },
        { label: '待审批', value: `${pendingApprovals.length}`, detail: '照片与工单申请', tone: pendingApprovals.length > 0 ? 'orange' : 'slate' },
        { label: '已完成', value: `${completedCount || 1}`, detail: '无称错记录', tone: 'green' },
      ],
      pendingApprovals: pendingApprovals.length > 0 ? pendingApprovals : fallbackData.pendingApprovals,
    }
  },

  // 工单
  async getWorkOrders(): Promise<any[]> {
    return request('/work-orders')
  },

  async getWorkOrder(orderNo: string): Promise<any> {
    return request(`/work-orders/${orderNo}`)
  },

  async createWorkOrder(payload: { product_id: number; target_weight_kg: number; operator_id?: number | null }): Promise<any> {
    return request('/work-orders', {
      method: 'POST',
      body: JSON.stringify(payload),
    })
  },

  async approveWorkOrder(orderNo: string): Promise<any> {
    return request(`/work-orders/${orderNo}/approve`, { method: 'POST' })
  },

  async startWorkOrder(orderNo: string): Promise<any> {
    return request(`/work-orders/${orderNo}/start`, { method: 'POST' })
  },

  async cancelWorkOrder(orderNo: string): Promise<any> {
    return request(`/work-orders/${orderNo}/cancel`, { method: 'POST' })
  },

  async completeWorkOrder(orderNo: string): Promise<any> {
    return request(`/work-orders/${orderNo}/complete`, { method: 'POST' })
  },

  // 审批
  async approve(id: string): Promise<{ id: string; status: 'approved' }> {
    const confId = parseInt(id.replace(/[^0-9]/g, ''), 10)
    if (!isNaN(confId) && confId > 0) {
      await request(`/evidence/confirmations/${confId}/approve`, { method: 'POST' })
    }
    return { id, status: 'approved' }
  },

  async reject(id: string): Promise<{ id: string; status: 'rejected' }> {
    const confId = parseInt(id.replace(/[^0-9]/g, ''), 10)
    if (!isNaN(confId) && confId > 0) {
      await request(`/approvals/${confId}/reject`, { method: 'POST' })
    }
    return { id, status: 'rejected' }
  },

  // 辅料
  async getMaterials(): Promise<any[]> {
    return request('/master-data/materials')
  },

  async createMaterial(payload: { material_code: string; name_zh: string; name_en?: string; shelf_life_months: number; image_file_ids?: string[] }): Promise<any> {
    return request('/master-data/materials', {
      method: 'POST',
      body: JSON.stringify(payload),
    })
  },

  async disableMaterial(materialId: string): Promise<any> {
    return request(`/master-data/materials/${materialId}/disable`, { method: 'PATCH' })
  },

  // 产品与配方
  async getProducts(): Promise<any[]> {
    return request('/master-data/products')
  },

  async createProduct(payload: { name: string; items: { material_id: string; quantity_per_ton_kg: number }[] }): Promise<any> {
    return request('/master-data/products', {
      method: 'POST',
      body: JSON.stringify(payload),
    })
  },

  // 文件与 Excel
  async uploadFile(file: File): Promise<any> {
    const form = new FormData()
    form.append('file', file)
    return request('/evidence/files', { method: 'POST', body: form })
  },

  async downloadExcelTemplate(): Promise<void> {
    const response = await fetch(`${API_BASE}/labels/excel-template`, { headers: getAuthHeader() })
    if (!response.ok) {
      throw new Error('导出模板失败')
    }
    const blob = await response.blob()
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = 'materials-template.xlsx'
    link.click()
    URL.revokeObjectURL(url)
  },

  async importExcel(file: File): Promise<any> {
    const form = new FormData()
    form.append('file', file)
    return request('/labels/excel-import', { method: 'POST', body: form })
  },

  // 标签
  async getPrintBatches(): Promise<any[]> {
    return request('/labels/print-batches')
  },

  async createPrintBatch(materialId: string, quantity: number): Promise<any> {
    return request('/labels/print-batches', {
      method: 'POST',
      body: JSON.stringify({ material_id: materialId, quantity }),
    })
  },

  // 设置与账号
  async getSettings(): Promise<Record<string, string>> {
    return request('/settings')
  },

  async updateSettings(values: Record<string, string>): Promise<Record<string, string>> {
    return request('/settings', { method: 'PUT', body: JSON.stringify({ values }) })
  },

  async registerUser(payload: { username: string; display_name: string; password: string; role?: string }): Promise<any> {
    return request('/auth/register', {
      method: 'POST',
      body: JSON.stringify({ ...payload, role: payload.role || 'operator' }),
    })
  },

  // 运维
  async getAuditLogs(): Promise<any[]> {
    return request('/operations/audit-logs')
  },

  async createBackup(): Promise<any> {
    return request('/operations/backups', { method: 'POST' })
  },

  async getBackups(): Promise<any[]> {
    return request('/operations/backups')
  },
}
