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

export type NetworkAddress = {
  name: string
  ipv4: string
  kind: 'hotspot' | 'wireless' | 'ethernet' | 'other' | 'virtual'
  is_up: boolean
  is_virtual: boolean
  is_hotspot: boolean
  is_recommended: boolean
}

export type NetworkAddressSnapshot = {
  detected_at: string
  recommended: NetworkAddress | null
  addresses: NetworkAddress[]
}

export type EvidenceIntegrityStatus = 'ok' | 'missing' | 'size_mismatch' | 'hash_mismatch' | 'unhashed'

export type EvidenceIntegrityItem = {
  file_id: string
  status: EvidenceIntegrityStatus
  expected_sha256: string | null
  actual_sha256: string | null
  expected_size_bytes: number
  actual_size_bytes: number | null
}

export type EvidenceIntegrityResult = {
  checked_at: string
  total: number
  ok: number
  issue_count: number
  issues: EvidenceIntegrityItem[]
  items: EvidenceIntegrityItem[]
}

export type BugReportStatus = 'pending' | 'sending' | 'sent' | 'failed'

export type BugReportRecord = {
  id: number
  source: 'pc' | 'app'
  reporter_id: number
  reporter_username: string | null
  reporter_name: string | null
  description: string
  image_count: number
  status: BugReportStatus
  error_message: string | null
  created_at: string
  sent_at: string | null
}
