import type { WorkOrderStatus } from '../types/domain'

const statusClass: Record<WorkOrderStatus, string> = {
  待审批: 'status status-pending',
  已批准: 'status status-done',
  执行中: 'status status-running',
  待接管: 'status status-takeover',
  已完成: 'status status-done',
  已撤销: 'status status-cancelled',
  已删除: 'status status-cancelled',
}

export function StatusBadge({ status }: { status: WorkOrderStatus }) {
  return <span className={statusClass[status]}><i />{status}</span>
}
