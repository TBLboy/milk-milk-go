import { dashboardData } from '../data/mockData'
import type { DashboardData } from '../types/domain'

// This adapter is the only data boundary used by pages. Replace mock methods with fetch calls later.
export const api = {
  async getDashboard(): Promise<DashboardData> {
    await new Promise((resolve) => setTimeout(resolve, 180))
    return dashboardData
  },
  async approve(id: string): Promise<{ id: string; status: 'approved' }> {
    return { id, status: 'approved' }
  },
}
