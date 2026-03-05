interface SignalBadgeProps {
  signal: 'BUY' | 'SELL' | 'HOLD' | string
}

export default function SignalBadge({ signal }: SignalBadgeProps) {
  const styles: Record<string, string> = {
    BUY: 'bg-rise/10 text-rise',
    SELL: 'bg-fall/10 text-fall',
    HOLD: 'bg-gray-100 text-gray-600',
  }

  return (
    <span
      className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${
        styles[signal] || styles.HOLD
      }`}
    >
      {signal}
    </span>
  )
}
