import { useEffect, useState } from 'react'
import type { Workspace, WorkspaceLatest, Service, ServiceRunResult } from '../types/switchboard'
import { getWorkspace, getWorkspaceLatest, triggerCollect } from '../api/client'
import { isApiError } from '../types/switchboard'
import { ServiceCard } from '../components/ServiceCard'
import { RunStatus } from '../components/RunStatus'
import { loadFallbackWorkspaceList } from '../data/fallback'
import { ProjectOnboardingPanel } from '../components/ProjectOnboardingPanel'

interface Props {
  workspaceId: string
  offline: boolean
  onSelectService: (id: string) => void
}

export function WorkspacePage({ workspaceId, offline, onSelectService }: Props) {
  const [workspace, setWorkspace] = useState<Workspace | null>(null)
  const [latest, setLatest] = useState<WorkspaceLatest | null>(null)
  const [collecting, setCollecting] = useState(false)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    setLoading(true)
    if (offline) {
      loadFallbackWorkspaceList().then((wss) => {
        const ws = wss.find((w) => w.workspace_id === workspaceId) ?? null
        setWorkspace(ws)
        setLoading(false)
      })
      return
    }
    Promise.all([getWorkspace(workspaceId), getWorkspaceLatest(workspaceId)]).then(
      ([ws, lat]) => {
        if (!isApiError(ws)) setWorkspace(ws)
        if (!isApiError(lat)) setLatest(lat)
        setLoading(false)
      },
    )
  }, [workspaceId, offline])

  async function handleCollect() {
    setCollecting(true)
    const result = await triggerCollect(workspaceId)
    if (!isApiError(result)) setLatest(result)
    setCollecting(false)
  }

  function handleCreated(service: Service) {
    setWorkspace((current) =>
      current
        ? {
            ...current,
            services: [...current.services, service].sort(
              (a, b) => (a.favorite_tier ?? 99) - (b.favorite_tier ?? 99),
            ),
          }
        : current,
    )
  }

  // Build a map from service_id → run result for quick lookup
  const resultMap: Record<string, ServiceRunResult> = {}
  latest?.services.forEach((r) => {
    resultMap[r.service_id] = r
  })

  const services = (workspace?.services ?? []).sort(
    (a, b) => (a.favorite_tier ?? 99) - (b.favorite_tier ?? 99),
  )

  return (
    <div>
      {/* Run status bar */}
      <div className="mb-6 bg-gray-900 border border-gray-800 rounded-xl px-4 py-3">
        <RunStatus
          summary={latest?.summary}
          onCollect={handleCollect}
          collecting={collecting}
          offline={offline}
        />
      </div>

      <div className="mb-6">
        <ProjectOnboardingPanel
          workspaceId={workspaceId}
          serverIds={workspace?.server_ids ?? []}
          disabled={offline}
          onCreated={handleCreated}
        />
      </div>

      {/* Service grid */}
      {loading ? (
        <div className="text-gray-500 text-sm">Loading…</div>
      ) : services.length === 0 ? (
        <div className="rounded-xl border border-dashed border-gray-800 bg-gray-900 px-4 py-6 text-gray-500 text-sm italic">
          No services found. {offline ? 'Backend offline.' : 'Use Add Project to seed this workspace manually.'}
        </div>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {services.map((svc: Service) => (
            <ServiceCard
              key={svc.service_id}
              service={svc}
              result={resultMap[svc.service_id]}
              onClick={() => onSelectService(svc.service_id)}
            />
          ))}
        </div>
      )}
    </div>
  )
}
