import { Star, Shield, GitBranch } from 'lucide-react'
import type { Service, ServiceRunResult } from '../types/switchboard'
import { StatusBadge } from './StatusBadge'

interface Props {
  service: Service
  result?: ServiceRunResult
  onClick: () => void
}

export function ServiceCard({ service, result, onClick }: Props) {
  const status = result?.status ?? 'unverified'
  const ports = result?.ports ?? []
  const firewallActive = result?.firewall_active ?? false
  const dirty = result?.repo_summaries?.some((r) => r.dirty) ?? false

  return (
    <button
      onClick={onClick}
      className="w-full text-left bg-gray-900 border border-gray-800 rounded-xl p-4 hover:border-gray-600 transition-colors group"
    >
      {/* Header */}
      <div className="flex items-start justify-between mb-3">
        <div>
          <div className="flex items-center gap-2">
            <span className="font-semibold text-white group-hover:text-blue-400 transition-colors">
              {service.display_name}
            </span>
            {service.favorite_tier === 1 && (
              <Star className="w-3.5 h-3.5 text-yellow-400 fill-yellow-400" />
            )}
          </div>
          <div className="text-xs text-gray-500 mt-0.5">{service.service_id}</div>
        </div>
        <StatusBadge status={status} />
      </div>

      {/* Tags */}
      {service.tags.length > 0 && (
        <div className="flex flex-wrap gap-1 mb-3">
          {service.tags.map((tag) => (
            <span key={tag} className="text-xs bg-gray-800 text-gray-400 px-2 py-0.5 rounded">
              {tag}
            </span>
          ))}
        </div>
      )}

      {/* Ports */}
      {ports.length > 0 && (
        <div className="flex flex-wrap gap-1 mb-2">
          {ports.map((p) => (
            <span key={p.port} className="text-xs font-mono bg-gray-800 text-cyan-400 px-2 py-0.5 rounded">
              :{p.port}
            </span>
          ))}
        </div>
      )}

      {/* Footer indicators */}
      <div className="flex gap-3 mt-2">
        {firewallActive && (
          <span className="flex items-center gap-1 text-xs text-green-400">
            <Shield className="w-3 h-3" /> Firewall
          </span>
        )}
        {dirty && (
          <span className="flex items-center gap-1 text-xs text-yellow-400">
            <GitBranch className="w-3 h-3" /> Dirty
          </span>
        )}
        {result && (
          <span className="ml-auto text-xs text-gray-600">
            {new Date(result.collected_at).toLocaleTimeString()}
          </span>
        )}
      </div>
    </button>
  )
}
