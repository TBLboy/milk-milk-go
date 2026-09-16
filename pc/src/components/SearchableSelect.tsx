import { useEffect, useId, useMemo, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import { Check, ChevronDown, Search } from 'lucide-react'

export type SearchableSelectOption = {
  value: string
  label: string
  keywords?: string
}

type SearchableSelectProps = {
  value: string | number | null | undefined
  options: SearchableSelectOption[]
  onChange: (value: string) => void
  placeholder?: string
  emptyMessage?: string
  disabled?: boolean
  className?: string
}

type MenuPosition = {
  left: number
  width: number
  top?: number
  bottom?: number
  maxHeight: number
}

function normalizeSearchText(value: string) {
  return value.trim().toLocaleLowerCase()
}

export function SearchableSelect({
  value,
  options,
  onChange,
  placeholder = '请选择',
  emptyMessage = '没有匹配项',
  disabled = false,
  className = '',
}: SearchableSelectProps) {
  const listboxId = useId()
  const rootRef = useRef<HTMLDivElement>(null)
  const menuRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLInputElement>(null)
  const [open, setOpen] = useState(false)
  const [query, setQuery] = useState('')
  const [activeIndex, setActiveIndex] = useState(0)
  const [menuPosition, setMenuPosition] = useState<MenuPosition | null>(null)
  const stringValue = value == null ? '' : String(value)
  const selectedOption = options.find((option) => option.value === stringValue)
  const filteredOptions = useMemo(() => {
    const normalizedQuery = normalizeSearchText(query)
    if (!normalizedQuery) return options
    return options.filter((option) =>
      normalizeSearchText(`${option.label} ${option.keywords || ''}`).includes(normalizedQuery),
    )
  }, [options, query])

  const updateMenuPosition = () => {
    const rect = rootRef.current?.getBoundingClientRect()
    if (!rect) return
    const viewportHeight = window.innerHeight
    const desiredHeight = 280
    const gap = 6
    const spaceBelow = viewportHeight - rect.bottom - gap - 8
    const spaceAbove = rect.top - gap - 8
    const openUp = spaceBelow < Math.min(desiredHeight, 180) && spaceAbove > spaceBelow
    const availableHeight = openUp ? spaceAbove : spaceBelow

    setMenuPosition({
      left: rect.left,
      width: rect.width,
      top: openUp ? undefined : rect.bottom + gap,
      bottom: openUp ? viewportHeight - rect.top + gap : undefined,
      maxHeight: Math.max(120, Math.min(desiredHeight, availableHeight)),
    })
  }

  useEffect(() => {
    if (!open) {
      setMenuPosition(null)
      return
    }

    updateMenuPosition()
    const handlePositionChange = () => updateMenuPosition()
    window.addEventListener('resize', handlePositionChange)
    document.addEventListener('scroll', handlePositionChange, true)
    return () => {
      window.removeEventListener('resize', handlePositionChange)
      document.removeEventListener('scroll', handlePositionChange, true)
    }
  }, [open])

  useEffect(() => {
    if (!open) return
    const handlePointerDown = (event: MouseEvent) => {
      const target = event.target as Node
      if (rootRef.current?.contains(target) || menuRef.current?.contains(target)) return
      setOpen(false)
      setQuery('')
    }
    document.addEventListener('mousedown', handlePointerDown)
    return () => document.removeEventListener('mousedown', handlePointerDown)
  }, [open])

  useEffect(() => {
    if (!open) return
    menuRef.current
      ?.querySelector('.searchable-select-option.active')
      ?.scrollIntoView({ block: 'nearest' })
  }, [activeIndex, open])

  const openMenu = () => {
    if (disabled || open) return
    setQuery('')
    const selectedIndex = options.findIndex((option) => option.value === stringValue)
    setActiveIndex(selectedIndex >= 0 ? selectedIndex : 0)
    setOpen(true)
  }

  const closeMenu = () => {
    setOpen(false)
    setQuery('')
  }

  const selectOption = (option: SearchableSelectOption) => {
    onChange(option.value)
    closeMenu()
    requestAnimationFrame(() => inputRef.current?.focus())
  }

  const handleKeyDown = (event: React.KeyboardEvent<HTMLInputElement>) => {
    if (event.key === 'ArrowDown') {
      event.preventDefault()
      if (!open) {
        openMenu()
      } else if (filteredOptions.length > 0) {
        setActiveIndex((current) => Math.min(current + 1, filteredOptions.length - 1))
      }
      return
    }
    if (event.key === 'ArrowUp') {
      event.preventDefault()
      if (!open) {
        openMenu()
      } else if (filteredOptions.length > 0) {
        setActiveIndex((current) => Math.max(current - 1, 0))
      }
      return
    }
    if (event.key === 'Enter' && open) {
      event.preventDefault()
      const activeOption = filteredOptions[activeIndex]
      if (activeOption) selectOption(activeOption)
      return
    }
    if (event.key === 'Escape') {
      event.preventDefault()
      closeMenu()
      inputRef.current?.blur()
    }
  }

  const menu = open && menuPosition
    ? createPortal(
        <div
          ref={menuRef}
          id={listboxId}
          className="searchable-select-menu"
          role="listbox"
          style={{
            left: menuPosition.left,
            width: menuPosition.width,
            top: menuPosition.top,
            bottom: menuPosition.bottom,
            maxHeight: menuPosition.maxHeight,
          }}
        >
          {filteredOptions.length > 0 ? filteredOptions.map((option, index) => {
            const selected = option.value === stringValue
            const active = index === activeIndex
            return (
              <button
                key={option.value}
                id={`${listboxId}-${option.value}`}
                type="button"
                role="option"
                aria-selected={selected}
                className={`searchable-select-option${selected ? ' selected' : ''}${active ? ' active' : ''}`}
                onMouseDown={(event) => event.preventDefault()}
                onMouseEnter={() => setActiveIndex(index)}
                onClick={() => selectOption(option)}
                title={option.label}
              >
                <span>{option.label}</span>
                {selected && <Check size={15} />}
              </button>
            )
          }) : (
            <div className="searchable-select-empty">{emptyMessage}</div>
          )}
        </div>,
        document.body,
      )
    : null

  return (
    <div
      ref={rootRef}
      className={`searchable-select${open ? ' open' : ''}${disabled ? ' disabled' : ''}${className ? ` ${className}` : ''}`}
    >
      <Search size={16} className="searchable-select-search-icon" />
      <input
        ref={inputRef}
        className="searchable-select-input"
        type="text"
        value={open ? query : selectedOption?.label || ''}
        placeholder={selectedOption ? '输入关键字搜索' : placeholder}
        disabled={disabled}
        autoComplete="off"
        role="combobox"
        aria-expanded={open}
        aria-controls={open ? listboxId : undefined}
        aria-autocomplete="list"
        aria-activedescendant={open && filteredOptions[activeIndex] ? `${listboxId}-${filteredOptions[activeIndex].value}` : undefined}
        onFocus={openMenu}
        onClick={openMenu}
        onChange={(event) => {
          setQuery(event.target.value)
          setActiveIndex(0)
          if (!open) setOpen(true)
        }}
        onKeyDown={handleKeyDown}
      />
      <button
        type="button"
        className="searchable-select-toggle"
        aria-label={open ? '收起选项' : '展开选项'}
        disabled={disabled}
        onMouseDown={(event) => event.preventDefault()}
        onClick={() => {
          if (open) {
            closeMenu()
          } else {
            openMenu()
          }
        }}
      >
        <ChevronDown size={16} />
      </button>
      {menu}
    </div>
  )
}
