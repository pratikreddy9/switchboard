import { Clock, Play } from 'lucide-react'
import type { CollectSummary, CollectStatus } from '../types/switchboard'
import { StatusBadge } from './StatusBadge'

interface Props {
  summary?: CollectSummary
  onCollect?: () => void
  collecting?: boolean
  offline?: boolean
}

export function RunStatus({ summary, onCollect, collecting, offline }: Props) {
  return (
    <div className="flex items-center gap-4">
      {summary ? (
        <>
          <div className="flex items-center gap-2 text-sm text-gray-400">
            <Clock className="w-4 h-4" />
            {new Date(summary.timestamp).toLocaleString()}
          </div>
          <StatusBadge status={summary.status as CollectStatus} size="md" />
        </>
      ) : (
        <span className="text-sm text-gray-600">No runs yet</span>
      )}

      {!offline && onCollect && (
        <button
          onClick={onCollect}
          disabled={collecting}
          className="ml-auto flex items-center gap-2 bg-blue-600 hover:bg-blue-500 disabled:opacity-50 text-white text-sm px-4 py-1.5 rounded-lg transition-colors"
        >
          <Play className={`w-3.5 h-3.5 ${collecting ? 'animate-pulse' : ''}`} />
          {collecting ? 'Collecting…' : 'Collect'}
        </button>
      )}

      {offline && (
        <span className="ml-auto text-xs bg-orange-900 text-orange-300 border border-orange-700 px-3 py-1 rounded-full">
          Offline — cached snapshot
        </span>
      )}
    </div>
  )
}
