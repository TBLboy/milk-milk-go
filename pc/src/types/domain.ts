export type WorkOrderStatus = '待审批' | '已批准' | '执行中' | '待接管' | '已完成' | '已撤销' | '已删除'

export type WorkOrder = {
  id: string
  product: string
  batch: string
  targetWeight: number
  completedSteps: number
  totalSteps: number
  operator: string
  status: WorkOrderStatus
  updatedAt: string
  alert?: string
}

export type DashboardData = {
  workOrders: WorkOrder[]
  stats: { label: string; value: string; detail: string; tone: 'blue' | 'orange' | 'green' | 'slate' }[]
  pendingApprovals: {
    id: string
    title: string
    description: string
    time: string
    type: 'photo' | 'takeover' | 'cancel' | 'delete'
    fileId?: string | null
    orderNo?: string | null
    stepNo?: number | null
  }[]
}
