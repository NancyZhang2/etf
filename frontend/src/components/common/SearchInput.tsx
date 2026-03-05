import { useState, useEffect, useCallback, useRef } from 'react'

interface SearchInputProps {
  placeholder?: string
  onSearch: (value: string) => void
  delay?: number
}

export default function SearchInput({ placeholder = '搜索...', onSearch, delay = 300 }: SearchInputProps) {
  const [value, setValue] = useState('')
  const timerRef = useRef<ReturnType<typeof setTimeout>>()

  const handleChange = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const v = e.target.value
      setValue(v)
      if (timerRef.current) clearTimeout(timerRef.current)
      timerRef.current = setTimeout(() => onSearch(v), delay)
    },
    [onSearch, delay],
  )

  useEffect(() => {
    return () => {
      if (timerRef.current) clearTimeout(timerRef.current)
    }
  }, [])

  return (
    <input
      type="text"
      value={value}
      onChange={handleChange}
      placeholder={placeholder}
      className="w-full px-3 py-2 text-sm border border-gray-200 rounded-lg focus:outline-none focus:border-primary focus:ring-1 focus:ring-primary/20"
    />
  )
}
