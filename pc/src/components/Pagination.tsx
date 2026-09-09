import { ChevronLeft, ChevronRight } from 'lucide-react'

export function Pagination({ page, pageSize, total, onPageChange }: {
  page: number
  pageSize: number
  total: number
  onPageChange: (page: number) => void
}) {
  const totalPages = Math.max(1, Math.ceil(total / pageSize))
  const start = total === 0 ? 0 : (page - 1) * pageSize + 1
  const end = Math.min(page * pageSize, total)
  return (
    <div className="pagination-bar">
      <span>共 {total} 条 · 第 {start}-{end} 条 / {totalPages} 页</span>
      <div className="pagination-actions">
        <button disabled={page <= 1} onClick={() => onPageChange(page - 1)}><ChevronLeft size={16} />上一页</button>
        <button disabled={page >= totalPages} onClick={() => onPageChange(page + 1)}>下一页<ChevronRight size={16} /></button>
      </div>
    </div>
  )
}
