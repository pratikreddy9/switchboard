import { useEffect, useState, useMemo } from 'react'
import type { Workspace, WorkspaceLatest, Service, ServiceRunResult } from '../types/switchboard'
import { getWorkspace, getWorkspaceLatest, triggerCollect } from '../api/client'
import { isApiError } from '../types/switchboard'
import { ServiceCard } from '../components/ServiceCard'
import { RunStatus } from '../components/RunStatus'
import { loadFallbackWorkspaceList } from '../data/fallback'
import { ProjectOnboardingPanel } from '../components/ProjectOnboardingPanel'
import { ProjectsPanel } from '../components/ProjectsPanel'
import { TaskLedgerPanel } from '../components/TaskLedgerPanel'
import { InfoDropdown } from '../components/InfoDropdown'
import { ConfirmationModal, ACTION_EXPLAIN } from '../components/ConfirmationModal'
import { TECH_STACK_LINES, HOW_TO_USE_LINES } from '../App'
import type { TaskLedgerEntry } from '../types/switchboard'

interface Props {
  workspaceId: string
  offline: boolean
  onSelectService: (id: string) => void
}

export function WorkspacePage({ workspaceId, offline, onSelectService }: Props) {
  const [workspace, setWorkspace] = useState<Workspace | null>(null)
  const [latest, setLatest] = useState<WorkspaceLatest | null>(null)
  const [collecting, setCollecting] = useState(false)
  const [healthChecking, setHealthChecking] = useState(false)
  const [healthConfirmOpen, setHealthConfirmOpen] = useState(false)
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

  async function handleHealthCheck() {
    setHealthConfirmOpen(false)
    setHealthChecking(true)
    // Let's import workspaceHealthCheck
    const { workspaceHealthCheck } = await import('../api/client')
    const result = await workspaceHealthCheck(workspaceId)
    setHealthChecking(false)
    if (!isApiError(result)) {
      // Refresh latest workspace results to see health status
      getWorkspaceLatest(workspaceId).then((lat) => {
        if (!isApiError(lat)) setLatest(lat)
      })
    }
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

  const allTasks = useMemo(() => {
    let list: TaskLedgerEntry[] = []
    services.forEach(s => {
      if (s.task_ledger) {
        const enriched = s.task_ledger.map(t => ({ ...t, service_name: s.display_name }))
        list = list.concat(enriched)
      }
    })
    return list.sort((a, b) => new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime()).slice(0, 50)
  }, [services])

  return (
    <div>
      <div className="mb-6 flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h2 className="text-xl font-semibold text-white">
            {workspace?.display_name ?? workspaceId}
          </h2>
          <div className="mt-1 text-xs text-gray-500">
            {workspaceId}
          </div>
        </div>
        <div className="flex items-center gap-2">
          <InfoDropdown label="Tech" title="Framework Stack" lines={TECH_STACK_LINES} />
          <InfoDropdown label="How To" title="Control Center Usage" lines={HOW_TO_USE_LINES} />
        </div>
      </div>

      {/* Run status bar */}
      <div className="mb-6 bg-gray-900 border border-gray-800 rounded-xl px-4 py-3">
        <RunStatus
          summary={latest?.summary}
          onCollect={handleCollect}
          collecting={collecting}
          offline={offline}
          onHealthCheck={() => setHealthConfirmOpen(true)}
          healthChecking={healthChecking}
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

      <div className="mb-6">
        <ProjectsPanel workspaceId={workspaceId} offline={offline} />
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

      {allTasks.length > 0 && (
        <div className="mt-8">
          <TaskLedgerPanel tasks={allTasks} title="Task Ledger (Cross-Node Summary)" showServiceLabel />
        </div>
      )}

      {healthConfirmOpen && ACTION_EXPLAIN['workspace_health_check'] && (
        <ConfirmationModal
          open={healthConfirmOpen}
          title={ACTION_EXPLAIN['workspace_health_check'].title}
          willDo={ACTION_EXPLAIN['workspace_health_check'].happens}
          willNotChange={ACTION_EXPLAIN['workspace_health_check'].untouched}
          writesTo={ACTION_EXPLAIN['workspace_health_check'].writesTo}
          onConfirm={handleHealthCheck}
          onCancel={() => setHealthConfirmOpen(false)}
        />
      )}
    </div>
  )
}
