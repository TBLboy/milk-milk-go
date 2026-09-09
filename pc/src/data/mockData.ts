import type { DashboardData } from '../types/domain'

export const dashboardData: DashboardData = {
  stats: [
    { label: '今日工单', value: '18', detail: '+3 较昨日', tone: 'blue' },
    { label: '执行中', value: '06', detail: '4 个即将完成', tone: 'orange' },
    { label: '待审批', value: '03', detail: '需要及时处理', tone: 'orange' },
    { label: '今日完成率', value: '92.4%', detail: '+4.8% 较昨日', tone: 'green' },
  ],
  workOrders: [
    { id: 'WO-20260909-018', product: '高钙纯牛奶 1L', batch: '09-09 A班', targetWeight: 2000, completedSteps: 7, totalSteps: 9, operator: '李师傅', status: '执行中', updatedAt: '10:42', alert: '当前称量：维生素 D3' },
    { id: 'WO-20260909-017', product: '草莓风味酸牛奶', batch: '09-09 A班', targetWeight: 1000, completedSteps: 8, totalSteps: 8, operator: '王师傅', status: '已完成', updatedAt: '10:18' },
    { id: 'WO-20260909-016', product: '原味风味发酵乳', batch: '09-09 B班', targetWeight: 1500, completedSteps: 3, totalSteps: 10, operator: '赵师傅', status: '待审批', updatedAt: '09:56' },
    { id: 'WO-20260909-015', product: '低脂高蛋白牛奶', batch: '09-09 B班', targetWeight: 3000, completedSteps: 0, totalSteps: 12, operator: '—', status: '待接管', updatedAt: '09:31' },
    { id: 'WO-20260909-014', product: '高钙纯牛奶 250ml', batch: '09-09 A班', targetWeight: 800, completedSteps: 12, totalSteps: 12, operator: '李师傅', status: '已完成', updatedAt: '09:12' },
  ],
  pendingApprovals: [
    { id: 'AP-018', title: '无码辅料放行申请', description: 'WO-20260909-018 · 维生素 D3', time: '5分钟前', type: 'photo' },
    { id: 'AP-017', title: '工单接管申请', description: 'WO-20260909-015 · 申请人：赵师傅', time: '18分钟前', type: 'takeover' },
    { id: 'AP-016', title: '工单撤销申请', description: 'WO-20260908-011 · 原味风味发酵乳', time: '42分钟前', type: 'cancel' },
  ],
}
