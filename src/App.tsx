import { useEffect, useState } from 'react'
import type { Workspace, ServiceRunResult, WorkspaceLatest } from './types/switchboard'
import { getHealth, listWorkspaces, getWorkspaceLatest } from './api/client'
import { isApiError } from './types/switchboard'
import { WorkspaceSwitcher } from './components/WorkspaceSwitcher'
import { InfoDropdown } from './components/InfoDropdown'
import { WorkspacePage } from './pages/WorkspacePage'
import { ServiceDetailPage } from './pages/ServiceDetailPage'
import { ControlCenterPage } from './pages/ControlCenterPage'
import { loadFallbackWorkspaceList } from './data/fallback'

const TECH_STACK_LINES = [
  'Backend: FastAPI, Pydantic Settings, Paramiko SSH/SFTP, file-based evidence JSON.',
  'Frontend: React 19, Vite, TypeScript, Tailwind, Lucide icons.',
  'Versioning: Git for repo status/pull/push actions and commit metadata.',
  'Operations: local path walking plus remote SSH/SFTP collection from declared servers.',
  'Runtime: per-location ports, health-check commands, run-command hints, and manual runtime checks.',
  'Node sync: manual, control-center initiated only. Nodes do not call back into the control center.',
  'Testing: Vitest for frontend contract checks and Python unittest for backend regressions.',
]

const HOW_TO_USE_LINES = [
  'Pick a workspace, then run Collect to refresh ports, repo state, docs, and logs.',
  'Use Add Project to open one root path, expand the tree, and uncheck dump paths you do not want.',
  'Category rules are simple: repo, doc, log, or exclude. You can override the auto-suggestion.',
  'Create service saves the chosen scope and per-location runtime config into the manifest.',
  'Pull Bundles create a new timestamped local copy while preserving the source tree.',
  'Service detail pages now handle runtime checks plus Sync From Node and Sync To Node.',
  'Repo actions stay per service: git status, safety check, git pull, git push.',
]

export default function App() {
  const [online, setOnline] = useState<boolean | null>(null)
  const [workspaces, setWorkspaces] = useState<Workspace[]>([])
  const [activeWorkspace, setActiveWorkspace] = useState<string | null>(null)
  const [selectedService, setSelectedService] = useState<string | null>(null)
  const [latestResults, setLatestResults] = useState<Record<string, WorkspaceLatest>>({})

  // Check backend health
  useEffect(() => {
    getHealth().then((res) => {
      setOnline(!isApiError(res))
    })
  }, [])

  // Load workspaces
  useEffect(() => {
    if (online === null) return
    if (!online) {
      loadFallbackWorkspaceList().then((wss) => {
        if (wss.length > 0) {
          setWorkspaces(wss)
        }
      })
      return
    }
    listWorkspaces().then((res) => {
      if (!isApiError(res) && res.length > 0) {
        setWorkspaces(res)
      }
    })
  }, [online])

  // Load latest for active workspace
  useEffect(() => {
    if (!online || workspaces.length === 0) return
    const missing = workspaces
      .map((workspace) => workspace.workspace_id)
      .filter((workspaceId) => !latestResults[workspaceId])
    if (missing.length === 0) return
    missing.forEach((workspaceId) => {
      getWorkspaceLatest(workspaceId).then((res) => {
        if (!isApiError(res)) {
          setLatestResults((prev) => ({ ...prev, [workspaceId]: res }))
        }
      })
    })
  }, [workspaces, online, latestResults])

  const currentLatest = activeWorkspace ? latestResults[activeWorkspace] : undefined

  function handleServiceDeleted(serviceId: string, workspaceId: string) {
    setSelectedService(null)
    setWorkspaces((current) =>
      current.map((workspace) =>
        workspace.workspace_id === workspaceId
          ? {
              ...workspace,
              services: workspace.services.filter((service) => service.service_id !== serviceId),
              service_count: Math.max(
                0,
                (workspace.service_count ?? workspace.services.length) - 1,
              ),
            }
          : workspace,
      ),
    )
    setLatestResults((current) => {
      if (!current[workspaceId]) return current
      const next = { ...current }
      delete next[workspaceId]
      return next
    })
  }

  // Find run result for a service
  function getServiceResult(serviceId: string): ServiceRunResult | undefined {
    return currentLatest?.services.find((s) => s.service_id === serviceId)
  }

  const offline = online === false

  return (
    <div className="min-h-screen bg-gray-950">
      {/* Top bar */}
      <header className="border-b border-gray-800 bg-gray-950 sticky top-0 z-10">
        <div className="max-w-6xl mx-auto px-4 py-3 flex items-center gap-4">
          <button
            onClick={() => {
              setSelectedService(null)
              setActiveWorkspace(null)
            }}
            className="text-lg font-bold text-white tracking-tight"
          >
            Switchboard Control Center
          </button>

          {workspaces.length > 0 && (
            <WorkspaceSwitcher
              workspaces={workspaces}
              active={activeWorkspace ?? ''}
              onChange={(id) => {
                setSelectedService(null)
                setActiveWorkspace(id)
              }}
            />
          )}

          <div className="ml-auto flex items-center gap-2">
            <InfoDropdown label="Tech" title="Framework Stack" lines={TECH_STACK_LINES} />
            <InfoDropdown label="How To" title="Control Center Usage" lines={HOW_TO_USE_LINES} />
            <span
              className={`w-2 h-2 rounded-full ${
                online === null ? 'bg-gray-600' : online ? 'bg-green-500' : 'bg-red-500'
              }`}
            />
            <span className="text-xs text-gray-500">
              {online === null ? 'Connecting…' : online ? 'Live' : 'Offline'}
            </span>
          </div>
        </div>
      </header>

      {/* Main */}
      <main className="max-w-6xl mx-auto px-4 py-6">
        {selectedService && activeWorkspace ? (
          <ServiceDetailPage
            serviceId={selectedService}
            runResult={getServiceResult(selectedService)}
            offline={offline}
            onBack={() => setSelectedService(null)}
            onDeleted={handleServiceDeleted}
          />
        ) : activeWorkspace ? (
          <WorkspacePage
            workspaceId={activeWorkspace}
            offline={offline}
            onSelectService={setSelectedService}
          />
        ) : (
          <ControlCenterPage
            workspaces={workspaces}
            latestResults={latestResults}
            online={online}
            onOpenWorkspace={(workspaceId) => {
              setSelectedService(null)
              setActiveWorkspace(workspaceId)
            }}
          />
        )}
      </main>
    </div>
  )
}
