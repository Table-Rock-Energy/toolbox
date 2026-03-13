import { useState, useRef, useEffect } from 'react'

interface EditableCellProps {
  value: string | number | undefined
  onCommit: (newValue: string) => void
  className?: string
  editable?: boolean
}

export default function EditableCell({
  value,
  onCommit,
  className = '',
  editable = true,
}: EditableCellProps) {
  const [isEditing, setIsEditing] = useState(false)
  const [editValue, setEditValue] = useState('')
  const inputRef = useRef<HTMLInputElement>(null)

  const displayValue = value !== undefined && value !== '' ? String(value) : '-'

  useEffect(() => {
    if (isEditing && inputRef.current) {
      inputRef.current.focus()
      inputRef.current.select()
    }
  }, [isEditing])

  const handleClick = () => {
    if (!editable) return
    setEditValue(value !== undefined && value !== '' ? String(value) : '')
    setIsEditing(true)
  }

  const handleCommit = () => {
    setIsEditing(false)
    if (editValue !== (value !== undefined ? String(value) : '')) {
      onCommit(editValue)
    }
  }

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter') {
      handleCommit()
    } else if (e.key === 'Escape') {
      setIsEditing(false)
    }
  }

  if (isEditing) {
    return (
      <input
        ref={inputRef}
        type="text"
        value={editValue}
        onChange={(e) => setEditValue(e.target.value)}
        onBlur={handleCommit}
        onKeyDown={handleKeyDown}
        className={`w-full px-1 py-0.5 text-sm border border-tre-teal rounded focus:outline-none focus:ring-1 focus:ring-tre-teal ${className}`}
      />
    )
  }

  return (
    <span
      onClick={editable ? handleClick : undefined}
      className={`px-1 py-0.5 rounded text-sm ${
        editable ? 'cursor-pointer hover:bg-tre-teal/5' : ''
      } ${className}`}
    >
      {displayValue}
    </span>
  )
}
