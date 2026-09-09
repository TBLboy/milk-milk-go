import { useEffect, useRef, useState } from 'react'
import { ChevronDown } from 'lucide-react'

export function StatusFilter({ options, value, onChange }: {
  options: string[]
  value: string
  onChange: (value: string) => void
}) {
  const [open, setOpen] = useState(false)
  const rootRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (rootRef.current && !rootRef.current.contains(event.target as Node)) {
        setOpen(false)
      }
    }
    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [])

  const cycle = () => {
    onChange(options[(options.indexOf(value) + 1) % options.length])
  }

  return (
    <div className="status-filter" ref={rootRef}>
      <div className="status-filter-button filter-button">
        <button type="button" onClick={cycle}>{value}</button>
        <button
          type="button"
          className="filter-arrow"
          aria-label="选择筛选状态"
          onClick={(event) => {
            event.stopPropagation()
            setOpen((current) => !current)
          }}
        >
          <ChevronDown size={14} />
        </button>
      </div>
      {open && (
        <div className="filter-menu">
          {options.map((option) => (
            <button
              key={option}
              type="button"
              className={option === value ? 'active' : ''}
              onClick={() => {
                onChange(option)
                setOpen(false)
              }}
            >
              {option}
            </button>
          ))}
        </div>
      )}
    </div>
  )
}
