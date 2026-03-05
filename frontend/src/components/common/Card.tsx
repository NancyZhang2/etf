import type { ReactNode } from 'react'

interface CardProps {
  title?: string
  extra?: ReactNode
  children: ReactNode
  className?: string
}

export default function Card({ title, extra, children, className = '' }: CardProps) {
  return (
    <div className={`bg-white rounded-xl border border-gray-200 ${className}`}>
      {(title || extra) && (
        <div className="flex items-center justify-between px-5 py-3 border-b border-gray-100">
          {title && <h3 className="text-sm font-medium text-gray-900">{title}</h3>}
          {extra && <div className="text-sm text-gray-500">{extra}</div>}
        </div>
      )}
      <div className="p-5">{children}</div>
    </div>
  )
}
