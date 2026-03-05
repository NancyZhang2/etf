interface ErrorDisplayProps {
  message: string
  onRetry?: () => void
}

export default function ErrorDisplay({ message, onRetry }: ErrorDisplayProps) {
  return (
    <div className="flex flex-col items-center justify-center py-20 text-gray-500">
      <p className="text-sm mb-3">{message}</p>
      {onRetry && (
        <button
          onClick={onRetry}
          className="px-4 py-2 text-sm bg-primary text-white rounded-lg hover:bg-primary/90 transition-colors"
        >
          重试
        </button>
      )}
    </div>
  )
}
