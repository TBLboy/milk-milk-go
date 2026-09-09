import type { WorkOrderStatus } from '../types/domain'

const statusClass: Record<WorkOrderStatus, string> = {
  待审批: 'status status-pending',
  执行中: 'status status-running',
  待接管: 'status status-takeover',
  已完成: 'status status-done',
  已撤销: 'status status-cancelled',
}

export function StatusBadge({ status }: { status: WorkOrderStatus }) {
  return <span className={statusClass[status]}><i />{status}</span>
}
