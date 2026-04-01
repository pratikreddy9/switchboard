import { useEffect, useState } from 'react'
import { Lock } from 'lucide-react'
import { getSecretPathCount } from '../api/client'
import { isApiError } from '../types/switchboard'

interface Props {
  serviceId: string
  disabled?: boolean
}

export function SecretPathGuard({ serviceId, disabled }: Props) {
  const [count, setCount] = useState<number | null>(null)

  useEffect(() => {
    if (disabled) return
    getSecretPathCount(serviceId).then((res) => {
      if (!isApiError(res)) setCount(res.count)
    })
  }, [serviceId, disabled])

  return (
    <div className="flex items-center gap-2 text-sm text-gray-400 bg-gray-900 border border-gray-800 rounded-lg px-3 py-2">
      <Lock className="w-4 h-4 text-yellow-500" />
      {disabled ? (
        <span>Secret file count unavailable (offline)</span>
      ) : count === null ? (
        <span className="text-gray-600">Checking…</span>
      ) : count === 0 ? (
        <span>No secret files detected</span>
      ) : (
        <span>
          <strong className="text-yellow-400">{count}</strong> secret file{count !== 1 ? 's' : ''} detected —
          view in terminal only
        </span>
      )}
    </div>
  )
}
