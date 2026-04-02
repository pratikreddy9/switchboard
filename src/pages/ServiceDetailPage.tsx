import { useEffect, useMemo, useState } from 'react'
import { ArrowLeft, FileStack, FolderTree, Pencil, RefreshCw, Save, Server, Trash2, X } from 'lucide-react'
import type {
  ManagedDocConfig,
  RuntimeCheckResult,
  Service,
  ServiceLocationDraft,
  ServiceRunResult,
  RunRecord,
  ScopeEntry,
} from '../types/switchboard'
import {
  deleteService,
  getService,
  getServiceScope,
  getWorkspaceRuns,
  runRuntimeCheck,
  syncFromNode,
  syncToNode,
  updateService,
} from '../api/client'
import { isApiError } from '../types/switchboard'
import { StatusBadge } from '../components/StatusBadge'
import { RepoSummary } from '../components/RepoSummary'
import { DownloadPanel } from '../components/DownloadPanel'
import { SecretPathGuard } from '../components/SecretPathGuard'
import { PullBundlePanel } from '../components/PullBundlePanel'

interface Props {
  serviceId: string
  runResult?: ServiceRunResult
  offline: boolean
  onBack: () => void
  onDeleted: (serviceId: string, workspaceId: string) => void
}

function parsePorts(value: string): number[] {
  return value
    .split(',')
    .map((token) => Number(token.trim()))
    .filter((port) => Number.isFinite(port) && port > 0 && port <= 65535)
}

export function ServiceDetailPage({ serviceId, runResult, offline, onBack, onDeleted }: Props) {
  const [service, setService] = useState<Service | null>(null)
  const [runs, setRuns] = useState<RunRecord[]>([])
  const [scopeEntries, setScopeEntries] = useState<ScopeEntry[]>([])
  const [scopeDraft, setScopeDraft] = useState<ScopeEntry[]>([])
  const [editingScope, setEditingScope] = useState(false)
  const [savingScope, setSavingScope] = useState(false)
  const [scopeMessage, setScopeMessage] = useState<string | null>(null)
  const [newScopePath, setNewScopePath] = useState('')
  const [newScopeKind, setNewScopeKind] = useState<ScopeEntry['kind']>('doc')
  const [newScopePathType, setNewScopePathType] = useState<ScopeEntry['path_type']>('file')
  const [deleteError, setDeleteError] = useState<string | null>(null)
  const [deleting, setDeleting] = useState(false)
  const [deleteConfirmOpen, setDeleteConfirmOpen] = useState(false)
  const [editingRuntime, setEditingRuntime] = useState(false)
  const [runtimeDraft, setRuntimeDraft] = useState<ServiceLocationDraft[]>([])
  const [savingRuntime, setSavingRuntime] = useState(false)
  const [runtimeMessage, setRuntimeMessage] = useState<string | null>(null)
  const [managedDocsDraft, setManagedDocsDraft] = useState<ManagedDocConfig[]>([])
  const [editingManagedDocs, setEditingManagedDocs] = useState(false)
  const [savingManagedDocs, setSavingManagedDocs] = useState(false)
  const [managedDocsMessage, setManagedDocsMessage] = useState<string | null>(null)
  const [checkingRuntimeLocation, setCheckingRuntimeLocation] = useState<string | null>(null)
  const [syncingFromLocation, setSyncingFromLocation] = useState<string | null>(null)
  const [syncingToLocation, setSyncingToLocation] = useState<string | null>(null)

  useEffect(() => {
    if (offline) return
    getService(serviceId).then((res) => {
      if (!isApiError(res)) {
        setService(res)
        setRuntimeDraft(res.locations.map((location) => ({ ...location, runtime: { ...location.runtime } })))
        setManagedDocsDraft(res.managed_docs.map((entry) => ({ ...entry })))
      }
    })
    getServiceScope(serviceId).then((res) => {
      if (!isApiError(res)) {
        setScopeEntries(res.scope_entries)
        setScopeDraft(res.scope_entries.map((entry) => ({ ...entry })))
      }
    })
  }, [serviceId, offline])

  useEffect(() => {
    if (offline || !service?.workspace_id) return
    getWorkspaceRuns(service.workspace_id).then((result) => {
      if (!isApiError(result)) setRuns(result)
    })
  }, [offline, service?.workspace_id])

  const docs = runResult?.docs_files ?? []
  const logs = runResult?.logs_files ?? []
  const repos = runResult?.repo_summaries ?? []

  async function handleDelete() {
    if (!service || deleting) return
    setDeleteError(null)
    setDeleting(true)
    const result = await deleteService(serviceId)
    setDeleting(false)
    setDeleteConfirmOpen(false)
    if (isApiError(result)) {
      setDeleteError(result.message)
      return
    }
    onDeleted(serviceId, result.workspace_id)
  }

  function handleServiceUpdated(updated: Service) {
    setService(updated)
    setScopeEntries(updated.scope_entries)
    setScopeDraft(updated.scope_entries.map((entry) => ({ ...entry })))
    setRuntimeDraft(updated.locations.map((location) => ({ ...location, runtime: { ...location.runtime } })))
    setManagedDocsDraft(updated.managed_docs.map((entry) => ({ ...entry })))
  }

  const runtimeChecksByLocation = useMemo(() => {
    const map = new Map<string, RuntimeCheckResult>()
    for (const entry of service?.runtime_checks ?? []) {
      if (!map.has(entry.location_id)) map.set(entry.location_id, entry)
    }
    for (const entry of runResult?.runtime_checks ?? []) {
      if (!map.has(entry.location_id)) map.set(entry.location_id, entry)
    }
    return map
  }, [runResult?.runtime_checks, service?.runtime_checks])

  const nodeSyncByLocation = useMemo(() => {
    const map = new Map<string, NonNullable<Service['node_sync']>[number]>()
    for (const entry of service?.node_sync ?? []) {
      if (!map.has(entry.location_id)) map.set(entry.location_id, entry)
    }
    return map
  }, [service?.node_sync])

  const latestNodeDocIndex = useMemo(
    () => (service?.node_sync ?? []).find((entry) => entry.doc_index)?.doc_index,
    [service?.node_sync],
  )

  const hasNodeScope = useMemo(
    () =>
      (service?.scope_entries ?? []).some((entry) => entry.enabled && entry.path.endsWith('switchboard/node.manifest.json')),
    [service?.scope_entries],
  )

  function updateRuntimeDraftField(
    locationId: string,
    field: keyof ServiceLocationDraft['runtime'],
    value: string,
  ) {
    setRuntimeDraft((current) =>
      current.map((location) => {
        if (location.location_id !== locationId) return location
        if (field === 'expected_ports') {
          return {
            ...location,
            runtime: {
              ...location.runtime,
              expected_ports: parsePorts(value),
            },
          }
        }
        if (field === 'monitoring_mode') {
          return {
            ...location,
            runtime: {
              ...location.runtime,
              monitoring_mode: value as ServiceLocationDraft['runtime']['monitoring_mode'],
            },
          }
        }
        return {
          ...location,
          runtime: {
            ...location.runtime,
            [field]: value,
          },
        }
      }),
    )
  }

  async function handleSaveRuntime() {
    if (!service) return
    setSavingRuntime(true)
    setRuntimeMessage(null)
    const result = await updateService(service.service_id, {
      locations: runtimeDraft,
    } as Partial<Service>)
    setSavingRuntime(false)
    if (isApiError(result)) {
      setRuntimeMessage(result.message)
      return
    }
    handleServiceUpdated(result)
    setEditingRuntime(false)
    setRuntimeMessage('Runtime config updated.')
  }

  function handleCancelRuntimeEdit() {
    setRuntimeDraft(service?.locations.map((location) => ({ ...location, runtime: { ...location.runtime } })) ?? [])
    setEditingRuntime(false)
    setRuntimeMessage(null)
  }

  async function handleSaveManagedDocs() {
    if (!service) return
    setSavingManagedDocs(true)
    setManagedDocsMessage(null)
    const result = await updateService(service.service_id, {
      managed_docs: managedDocsDraft,
    } as Partial<Service>)
    setSavingManagedDocs(false)
    if (isApiError(result)) {
      setManagedDocsMessage(result.message)
      return
    }
    handleServiceUpdated(result)
    setEditingManagedDocs(false)
    setManagedDocsMessage('Managed docs updated.')
  }

  function handleCancelManagedDocsEdit() {
    setManagedDocsDraft(service?.managed_docs.map((entry) => ({ ...entry })) ?? [])
    setEditingManagedDocs(false)
    setManagedDocsMessage(null)
  }

  async function handleRuntimeCheck(locationId: string) {
    setCheckingRuntimeLocation(locationId)
    setRuntimeMessage(null)
    const result = await runRuntimeCheck(serviceId, { location_id: locationId })
    setCheckingRuntimeLocation(null)
    if (isApiError(result)) {
      setRuntimeMessage(result.message)
      return
    }
    setService((current) =>
      current
        ? {
            ...current,
            runtime_checks: [
              result,
              ...(current.runtime_checks ?? []).filter((entry) => entry.location_id !== result.location_id),
            ],
          }
        : current,
    )
    setRuntimeMessage('Runtime check completed.')
  }

  async function handleSyncFromNode(locationId: string) {
    setSyncingFromLocation(locationId)
    setRuntimeMessage(null)
    const result = await syncFromNode(serviceId, { location_id: locationId })
    setSyncingFromLocation(null)
    if (isApiError(result)) {
      setRuntimeMessage(result.message)
      return
    }
    handleServiceUpdated(result.service)
    setService((current) =>
      current
        ? {
            ...result.service,
            node_sync: [result.sync, ...(result.service.node_sync ?? []).filter((entry) => entry.location_id !== result.sync.location_id)],
          }
        : result.service,
    )
    setRuntimeMessage('Synced from node.')
  }

  async function handleSyncToNode(locationId: string) {
    setSyncingToLocation(locationId)
    setRuntimeMessage(null)
    const result = await syncToNode(serviceId, { location_id: locationId })
    setSyncingToLocation(null)
    if (isApiError(result)) {
      setRuntimeMessage(result.message)
      return
    }
    setService((current) =>
      current
        ? {
            ...current,
            node_sync: [result.sync, ...(current.node_sync ?? []).filter((entry) => entry.location_id !== result.sync.location_id)],
          }
        : current,
    )
    setRuntimeMessage(result.node_manifest_path ? `Synced to node at ${result.node_manifest_path}.` : 'Synced to node.')
  }

  function addScopeEntry() {
    const trimmed = newScopePath.trim()
    if (!trimmed) return
    setScopeDraft((current) => [
      ...current,
      {
        kind: newScopeKind,
        path: trimmed,
        path_type: newScopePathType,
        source: 'user_added',
        enabled: true,
      },
    ])
    setNewScopePath('')
  }

  async function handleSaveScope() {
    if (!service) return
    setSavingScope(true)
    setScopeMessage(null)
    const result = await updateService(service.service_id, {
      scope_entries: scopeDraft,
    } as Partial<Service>)
    setSavingScope(false)
    if (isApiError(result)) {
      setScopeMessage(result.message)
      return
    }
    handleServiceUpdated(result)
    setEditingScope(false)
    setScopeMessage('Scope updated.')
  }

  function handleCancelScopeEdit() {
    setScopeDraft(scopeEntries.map((entry) => ({ ...entry })))
    setEditingScope(false)
    setScopeMessage(null)
  }

  return (
    <div>
      {/* Back + header */}
      <div className="mb-6 flex items-start justify-between gap-4">
        <div className="flex items-center gap-3">
          <button
            onClick={onBack}
            className="flex items-center gap-1 text-sm text-gray-400 hover:text-white transition-colors"
          >
            <ArrowLeft className="w-4 h-4" />
            Back
          </button>
          <div className="flex items-center gap-3">
            <div>
              <h2 className="text-xl font-semibold text-white">
                {service?.display_name ?? serviceId}
              </h2>
              <div className="mt-0.5 flex items-center gap-2">
                <span className="text-xs text-gray-500">{serviceId}</span>
                {runResult && <StatusBadge status={runResult.status} />}
                {hasNodeScope && (
                  <span className="rounded-full border border-cyan-900 bg-cyan-950/60 px-2 py-0.5 text-[10px] uppercase tracking-[0.16em] text-cyan-300">
                    Node Linked
                  </span>
                )}
              </div>
            </div>
          </div>
        </div>
        <button
          type="button"
          onClick={() => setDeleteConfirmOpen(true)}
          disabled={offline || deleting || !service}
          className="inline-flex items-center gap-2 rounded-lg border border-red-900 bg-red-950/70 px-3 py-2 text-sm font-medium text-red-200 transition-colors hover:border-red-700 hover:text-white disabled:cursor-not-allowed disabled:opacity-50"
        >
          <Trash2 className="h-4 w-4" />
          {deleting ? 'Deleting…' : 'Delete Service'}
        </button>
      </div>

      {deleteError && (
        <div className="mb-6 rounded-xl border border-red-900/70 bg-red-950/40 px-4 py-3 text-sm text-red-200">
          {deleteError}
        </div>
      )}

      {deleteConfirmOpen && service && (
        <div className="fixed inset-0 z-30 flex items-center justify-center bg-black/70 px-4">
          <div className="w-full max-w-xl rounded-2xl border border-red-900/70 bg-gray-950 shadow-2xl">
            <div className="border-b border-gray-800 px-5 py-4">
              <div className="text-xs uppercase tracking-[0.18em] text-red-300">Warning</div>
              <h3 className="mt-2 text-lg font-semibold text-white">Delete {service.display_name}?</h3>
              <p className="mt-2 text-sm text-gray-400">
                This clears the current framework data for this service in one shot.
              </p>
            </div>

            <div className="grid gap-4 px-5 py-4 md:grid-cols-2">
              <section className="rounded-xl border border-gray-800 bg-gray-900/70 p-4">
                <div className="text-xs uppercase tracking-[0.16em] text-red-300">Will Remove</div>
                <ul className="mt-3 space-y-2 text-sm text-gray-300">
                  <li>Service manifest entry and workspace link</li>
                  <li>Current docs, logs, repo, and secret-path evidence for this service</li>
                  <li>Downloaded bundle folders stored by the framework</li>
                </ul>
              </section>

              <section className="rounded-xl border border-gray-800 bg-gray-900/70 p-4">
                <div className="text-xs uppercase tracking-[0.16em] text-cyan-300">Will Keep</div>
                <ul className="mt-3 space-y-2 text-sm text-gray-300">
                  <li>Other services in the workspace</li>
                  <li>Server definitions and workspace definitions</li>
                  <li>Archived workspace run files themselves, with this service removed from their active snapshot data</li>
                </ul>
              </section>
            </div>

            <div className="flex items-center justify-end gap-3 border-t border-gray-800 px-5 py-4">
              <button
                type="button"
                onClick={() => setDeleteConfirmOpen(false)}
                disabled={deleting}
                className="rounded-lg border border-gray-700 px-4 py-2 text-sm text-gray-300 transition-colors hover:border-gray-500 hover:text-white disabled:cursor-not-allowed disabled:opacity-50"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={handleDelete}
                disabled={deleting}
                className="inline-flex items-center gap-2 rounded-lg border border-red-800 bg-red-950 px-4 py-2 text-sm font-medium text-red-200 transition-colors hover:border-red-600 hover:text-white disabled:cursor-not-allowed disabled:opacity-50"
              >
                <Trash2 className="h-4 w-4" />
                {deleting ? 'Deleting…' : 'Delete Service'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Ports + firewall */}
      {runResult && (runResult.ports.length > 0 || runResult.firewall_active !== undefined) && (
        <section className="mb-6 bg-gray-900 border border-gray-800 rounded-xl p-4">
          <h3 className="text-sm font-medium text-gray-300 mb-3 flex items-center gap-2">
            <Server className="w-4 h-4 text-cyan-400" />
            Network
          </h3>
          <div className="flex flex-wrap gap-2 mb-2">
            {runResult.ports.map((p) => (
              <span key={p.port} className="font-mono text-sm bg-gray-800 text-cyan-400 px-3 py-1 rounded-md">
                :{p.port} <span className="text-gray-500 text-xs">{p.protocol}</span>
              </span>
            ))}
            {runResult.ports.length === 0 && (
              <span className="text-sm text-gray-500">No open ports detected</span>
            )}
          </div>
          <div className="text-xs text-gray-500">
            Firewall: <span className={runResult.firewall_active ? 'text-green-400' : 'text-yellow-400'}>
              {runResult.firewall_status || (runResult.firewall_active ? 'active' : 'inactive')}
            </span>
          </div>
        </section>
      )}

      {service && (
        <section className="mb-6 bg-gray-900 border border-gray-800 rounded-xl p-4">
          <div className="mb-4 flex items-center justify-between gap-3">
            <div>
              <h3 className="text-sm font-medium text-gray-300">Runtime</h3>
              <div className="mt-1 text-xs text-gray-500">
                Per-location ports, health checks, run-command hints, and node sync.
              </div>
            </div>
            <div className="flex items-center gap-2">
              {editingRuntime ? (
                <>
                  <button
                    type="button"
                    onClick={handleCancelRuntimeEdit}
                    disabled={savingRuntime}
                    className="inline-flex items-center gap-1 rounded-lg border border-gray-700 px-3 py-2 text-xs text-gray-300 transition-colors hover:border-gray-500 hover:text-white disabled:opacity-50"
                  >
                    <X className="h-3.5 w-3.5" />
                    Cancel
                  </button>
                  <button
                    type="button"
                    onClick={handleSaveRuntime}
                    disabled={offline || savingRuntime}
                    className="inline-flex items-center gap-1 rounded-lg bg-white px-3 py-2 text-xs font-medium text-black transition-colors hover:bg-gray-200 disabled:opacity-50"
                  >
                    <Save className="h-3.5 w-3.5" />
                    {savingRuntime ? 'Saving…' : 'Save Runtime'}
                  </button>
                </>
              ) : (
                <button
                  type="button"
                  onClick={() => {
                    setRuntimeDraft(service.locations.map((location) => ({ ...location, runtime: { ...location.runtime } })))
                    setEditingRuntime(true)
                    setRuntimeMessage(null)
                  }}
                  disabled={offline}
                  className="inline-flex items-center gap-1 rounded-lg border border-gray-700 px-3 py-2 text-xs text-gray-300 transition-colors hover:border-cyan-500 hover:text-white disabled:opacity-50"
                >
                  <Pencil className="h-3.5 w-3.5" />
                  Edit Runtime
                </button>
              )}
            </div>
          </div>

          {runtimeMessage && (
            <div className="mb-4 rounded-xl border border-gray-800 bg-gray-950 px-3 py-2 text-sm text-gray-300">
              {runtimeMessage}
            </div>
          )}

          <div className="space-y-4">
            {(editingRuntime ? runtimeDraft : service.locations).map((location) => {
              const latestRuntime = runtimeChecksByLocation.get(location.location_id)
              const latestSync = nodeSyncByLocation.get(location.location_id)
              const portsValue = location.runtime.expected_ports.join(', ')
              return (
                <div key={location.location_id} className="rounded-xl border border-gray-800 bg-gray-950 p-4">
                  <div className="flex flex-col gap-2 md:flex-row md:items-start md:justify-between">
                    <div>
                      <div className="text-xs uppercase tracking-[0.16em] text-gray-500">{location.location_id}</div>
                      <div className="mt-1 text-sm font-medium text-white">{location.server_id}</div>
                      <div className="mt-1 font-mono text-xs text-gray-400 break-all">{location.root}</div>
                    </div>
                    <div className="flex flex-wrap gap-2">
                      <button
                        type="button"
                        onClick={() => handleRuntimeCheck(location.location_id)}
                        disabled={offline || checkingRuntimeLocation === location.location_id}
                        className="inline-flex items-center gap-1 rounded-lg border border-gray-700 px-3 py-2 text-xs text-gray-200 transition-colors hover:border-cyan-500 hover:text-white disabled:opacity-50"
                      >
                        <RefreshCw className={`h-3.5 w-3.5 ${checkingRuntimeLocation === location.location_id ? 'animate-spin' : ''}`} />
                        {checkingRuntimeLocation === location.location_id ? 'Checking…' : 'Run Runtime Check'}
                      </button>
                      <button
                        type="button"
                        onClick={() => handleSyncFromNode(location.location_id)}
                        disabled={offline || syncingFromLocation === location.location_id}
                        className="inline-flex items-center gap-1 rounded-lg border border-gray-700 px-3 py-2 text-xs text-gray-200 transition-colors hover:border-cyan-500 hover:text-white disabled:opacity-50"
                      >
                        {syncingFromLocation === location.location_id ? 'Syncing…' : 'Sync From Node'}
                      </button>
                      <button
                        type="button"
                        onClick={() => handleSyncToNode(location.location_id)}
                        disabled={offline || syncingToLocation === location.location_id}
                        className="inline-flex items-center gap-1 rounded-lg border border-gray-700 px-3 py-2 text-xs text-gray-200 transition-colors hover:border-cyan-500 hover:text-white disabled:opacity-50"
                      >
                        {syncingToLocation === location.location_id ? 'Syncing…' : 'Sync To Node'}
                      </button>
                    </div>
                  </div>

                  <div className="mt-4 grid gap-3 md:grid-cols-2">
                    <label className="text-sm text-gray-300">
                      <div className="mb-1">Expected ports</div>
                      {editingRuntime ? (
                        <input
                          value={portsValue}
                          onChange={(event) => updateRuntimeDraftField(location.location_id, 'expected_ports', event.target.value)}
                          className="w-full rounded-lg border border-gray-700 bg-gray-900 px-3 py-2 text-sm text-white outline-none focus:border-cyan-500"
                        />
                      ) : (
                        <div className="rounded-lg border border-gray-800 bg-gray-900 px-3 py-2 text-sm text-gray-200">
                          {portsValue || 'Not configured'}
                        </div>
                      )}
                    </label>

                    <label className="text-sm text-gray-300">
                      <div className="mb-1">Monitoring mode</div>
                      {editingRuntime ? (
                        <select
                          value={location.runtime.monitoring_mode}
                          onChange={(event) => updateRuntimeDraftField(location.location_id, 'monitoring_mode', event.target.value)}
                          className="w-full rounded-lg border border-gray-700 bg-gray-900 px-3 py-2 text-sm text-white outline-none focus:border-cyan-500"
                        >
                          <option value="manual">manual</option>
                          <option value="detect">detect</option>
                          <option value="node_managed">node_managed</option>
                        </select>
                      ) : (
                        <div className="rounded-lg border border-gray-800 bg-gray-900 px-3 py-2 text-sm text-gray-200">
                          {location.runtime.monitoring_mode}
                        </div>
                      )}
                    </label>
                  </div>

                  <label className="mt-3 block text-sm text-gray-300">
                    <div className="mb-1">Health check command</div>
                    {editingRuntime ? (
                      <input
                        value={location.runtime.healthcheck_command}
                        onChange={(event) => updateRuntimeDraftField(location.location_id, 'healthcheck_command', event.target.value)}
                        className="w-full rounded-lg border border-gray-700 bg-gray-900 px-3 py-2 text-sm text-white outline-none focus:border-cyan-500"
                      />
                    ) : (
                      <pre className="rounded-lg border border-gray-800 bg-gray-900 p-3 text-xs text-cyan-200 overflow-x-auto">
                        {location.runtime.healthcheck_command || 'Not configured'}
                      </pre>
                    )}
                  </label>

                  <label className="mt-3 block text-sm text-gray-300">
                    <div className="mb-1">Run command hint</div>
                    {editingRuntime ? (
                      <input
                        value={location.runtime.run_command_hint}
                        onChange={(event) => updateRuntimeDraftField(location.location_id, 'run_command_hint', event.target.value)}
                        className="w-full rounded-lg border border-gray-700 bg-gray-900 px-3 py-2 text-sm text-white outline-none focus:border-cyan-500"
                      />
                    ) : (
                      <pre className="rounded-lg border border-gray-800 bg-gray-900 p-3 text-xs text-cyan-200 overflow-x-auto">
                        {location.runtime.run_command_hint || 'Not configured'}
                      </pre>
                    )}
                  </label>

                  <label className="mt-3 block text-sm text-gray-300">
                    <div className="mb-1">Runtime notes</div>
                    {editingRuntime ? (
                      <textarea
                        value={location.runtime.notes}
                        onChange={(event) => updateRuntimeDraftField(location.location_id, 'notes', event.target.value)}
                        className="min-h-24 w-full rounded-lg border border-gray-700 bg-gray-900 px-3 py-2 text-sm text-white outline-none focus:border-cyan-500"
                      />
                    ) : (
                      <div className="rounded-lg border border-gray-800 bg-gray-900 px-3 py-2 text-sm text-gray-200">
                        {location.runtime.notes || 'No notes'}
                      </div>
                    )}
                  </label>

                  <div className="mt-4 grid gap-3 md:grid-cols-2">
                    <div className="rounded-xl border border-gray-800 bg-gray-900 p-3">
                      <div className="text-xs uppercase tracking-[0.16em] text-gray-500">Latest Runtime Check</div>
                      {latestRuntime ? (
                        <div className="mt-2 space-y-2 text-sm text-gray-300">
                          <div className="flex items-center gap-2">
                            <StatusBadge status={latestRuntime.status} />
                            <span className="text-xs text-gray-500">{new Date(latestRuntime.checked_at).toLocaleString()}</span>
                          </div>
                          <div>
                            <span className="text-gray-500">Detected ports:</span>{' '}
                            {latestRuntime.detected_ports.length > 0
                              ? latestRuntime.detected_ports.map((port) => `:${port.port}`).join(', ')
                              : 'none'}
                          </div>
                          <div>
                            <span className="text-gray-500">Missing ports:</span>{' '}
                            {latestRuntime.missing_ports.length > 0 ? latestRuntime.missing_ports.join(', ') : 'none'}
                          </div>
                          <div>
                            <span className="text-gray-500">Health:</span> {latestRuntime.healthcheck_status}
                          </div>
                          <div>
                            <span className="text-gray-500">Detected command:</span>{' '}
                            {latestRuntime.detected_process_command || 'Not detected'}
                          </div>
                          <div>
                            <span className="text-gray-500">Node present:</span> {latestRuntime.node_present ? 'yes' : 'no'}
                          </div>
                        </div>
                      ) : (
                        <div className="mt-2 text-sm text-gray-500">No runtime check captured yet.</div>
                      )}
                    </div>

                    <div className="rounded-xl border border-gray-800 bg-gray-900 p-3">
                      <div className="text-xs uppercase tracking-[0.16em] text-gray-500">Latest Node Sync</div>
                      {latestSync ? (
                        <div className="mt-2 space-y-2 text-sm text-gray-300">
                          <div className="flex items-center gap-2">
                            <StatusBadge status={latestSync.status} />
                            <span className="text-xs text-gray-500">{new Date(latestSync.timestamp).toLocaleString()}</span>
                          </div>
                          <div>
                            <span className="text-gray-500">Direction:</span> {latestSync.direction}
                          </div>
                          <div>
                            <span className="text-gray-500">Source:</span> {latestSync.source}
                          </div>
                          <div>
                            <span className="text-gray-500">Target:</span> {latestSync.target}
                          </div>
                        </div>
                      ) : (
                        <div className="mt-2 text-sm text-gray-500">No node sync recorded yet.</div>
                      )}
                    </div>
                  </div>
                </div>
              )
            })}
          </div>
        </section>
      )}

      {service && (
        <section className="mb-6 bg-gray-900 border border-gray-800 rounded-xl p-4">
          <div className="mb-4 flex items-center justify-between gap-3">
            <div>
              <h3 className="text-sm font-medium text-gray-300">Managed Docs</h3>
              <div className="mt-1 text-xs text-gray-500">
                Framework-owned derived docs generated from <code>switchboard/local/tasks-completed.md</code>.
              </div>
            </div>
            <div className="flex items-center gap-2">
              {editingManagedDocs ? (
                <>
                  <button
                    type="button"
                    onClick={handleCancelManagedDocsEdit}
                    disabled={savingManagedDocs}
                    className="inline-flex items-center gap-1 rounded-lg border border-gray-700 px-3 py-2 text-xs text-gray-300 transition-colors hover:border-gray-500 hover:text-white disabled:opacity-50"
                  >
                    <X className="h-3.5 w-3.5" />
                    Cancel
                  </button>
                  <button
                    type="button"
                    onClick={handleSaveManagedDocs}
                    disabled={offline || savingManagedDocs}
                    className="inline-flex items-center gap-1 rounded-lg bg-white px-3 py-2 text-xs font-medium text-black transition-colors hover:bg-gray-200 disabled:opacity-50"
                  >
                    <Save className="h-3.5 w-3.5" />
                    {savingManagedDocs ? 'Saving…' : 'Save Managed Docs'}
                  </button>
                </>
              ) : (
                <button
                  type="button"
                  onClick={() => {
                    setManagedDocsDraft(service.managed_docs.map((entry) => ({ ...entry })))
                    setEditingManagedDocs(true)
                    setManagedDocsMessage(null)
                  }}
                  disabled={offline}
                  className="inline-flex items-center gap-1 rounded-lg border border-gray-700 px-3 py-2 text-xs text-gray-300 transition-colors hover:border-cyan-500 hover:text-white disabled:opacity-50"
                >
                  <Pencil className="h-3.5 w-3.5" />
                  Edit Managed Docs
                </button>
              )}
            </div>
          </div>

          {managedDocsMessage && (
            <div className="mb-4 rounded-xl border border-gray-800 bg-gray-950 px-3 py-2 text-sm text-gray-300">
              {managedDocsMessage}
            </div>
          )}

          <div className="grid gap-3 md:grid-cols-2">
            {(editingManagedDocs ? managedDocsDraft : service.managed_docs).map((entry, index) => (
              <div key={`${entry.doc_id}:${index}`} className="rounded-xl border border-gray-800 bg-gray-950 p-4">
                {editingManagedDocs ? (
                  <div className="space-y-3">
                    <div className="flex items-center justify-between gap-3">
                      <div className="text-sm font-medium text-white">{entry.doc_id}</div>
                      <label className="inline-flex items-center gap-2 text-xs text-gray-300">
                        <input
                          type="checkbox"
                          checked={entry.enabled}
                          onChange={(event) =>
                            setManagedDocsDraft((current) =>
                              current.map((candidate, candidateIndex) =>
                                candidateIndex === index ? { ...candidate, enabled: event.target.checked } : candidate,
                              ),
                            )
                          }
                        />
                        Enabled
                      </label>
                    </div>
                    <input
                      value={entry.path}
                      onChange={(event) =>
                        setManagedDocsDraft((current) =>
                          current.map((candidate, candidateIndex) =>
                            candidateIndex === index ? { ...candidate, path: event.target.value } : candidate,
                          ),
                        )
                      }
                      className="w-full rounded-lg border border-gray-700 bg-gray-900 px-3 py-2 text-xs text-white outline-none focus:border-cyan-500"
                    />
                  </div>
                ) : (
                  <div className="space-y-2 text-sm text-gray-300">
                    <div className="flex items-center justify-between gap-3">
                      <span className="font-medium text-white">{entry.doc_id}</span>
                      <span
                        className={`rounded-full border px-2 py-0.5 text-[11px] uppercase tracking-[0.16em] ${
                          entry.enabled
                            ? 'border-cyan-900 bg-cyan-950/60 text-cyan-300'
                            : 'border-gray-700 text-gray-500'
                        }`}
                      >
                        {entry.enabled ? 'enabled' : 'disabled'}
                      </span>
                    </div>
                    <div className="font-mono text-xs text-gray-400 break-all">{entry.path}</div>
                    <div className="text-xs text-gray-500">
                      Generated: {entry.last_generated_at ? new Date(entry.last_generated_at).toLocaleString() : 'not yet'}
                    </div>
                  </div>
                )}
              </div>
            ))}
          </div>

          <div className="mt-4 rounded-xl border border-gray-800 bg-gray-950 p-4">
            <div className="text-xs uppercase tracking-[0.16em] text-gray-500">Latest Doc Index</div>
            {latestNodeDocIndex ? (
              <div className="mt-2 space-y-3 text-sm text-gray-300">
                <div>
                  <span className="text-gray-500">Generated:</span>{' '}
                  {latestNodeDocIndex.generated ? new Date(latestNodeDocIndex.generated).toLocaleString() : 'unknown'}
                </div>
                <div className="grid gap-2 md:grid-cols-2">
                  {latestNodeDocIndex.docs.map((entry) => (
                    <div key={`${entry.doc_id}:${entry.path}`} className="rounded-lg border border-gray-800 bg-gray-900 px-3 py-2">
                      <div className="flex items-center justify-between gap-3">
                        <span className="font-medium text-white">{entry.label ?? entry.doc_id}</span>
                        <span className="text-xs text-gray-500">{entry.enabled ? 'enabled' : 'disabled'}</span>
                      </div>
                      <div className="mt-1 font-mono text-[11px] text-gray-400 break-all">{entry.path}</div>
                      <div className="mt-1 text-[11px] text-gray-500">
                        Contributors: {entry.contributor_timestamps.length > 0 ? entry.contributor_timestamps.length : 0}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            ) : (
              <div className="mt-2 text-sm text-gray-500">No doc index metadata synced from the node yet.</div>
            )}
          </div>
        </section>
      )}

      {/* Repos */}
      <section className="mb-6 bg-gray-900 border border-gray-800 rounded-xl p-4">
        <h3 className="text-sm font-medium text-gray-300 mb-3">Repositories</h3>
        <RepoSummary
          serviceId={serviceId}
          repos={repos}
          allowedPaths={service?.allowed_git_pull_paths}
          disabled={offline}
        />
      </section>

      <section className="mb-6 bg-gray-900 border border-gray-800 rounded-xl p-4">
        <div className="mb-3 flex items-center justify-between gap-3">
          <h3 className="flex items-center gap-2 text-sm font-medium text-gray-300">
            <FolderTree className="h-4 w-4 text-cyan-400" />
            Scope
          </h3>
          <div className="flex items-center gap-2">
            {editingScope ? (
              <>
                <button
                  type="button"
                  onClick={handleCancelScopeEdit}
                  disabled={savingScope}
                  className="inline-flex items-center gap-1 rounded-lg border border-gray-700 px-3 py-2 text-xs text-gray-300 transition-colors hover:border-gray-500 hover:text-white disabled:opacity-50"
                >
                  <X className="h-3.5 w-3.5" />
                  Cancel
                </button>
                <button
                  type="button"
                  onClick={handleSaveScope}
                  disabled={offline || savingScope || !service}
                  className="inline-flex items-center gap-1 rounded-lg bg-white px-3 py-2 text-xs font-medium text-black transition-colors hover:bg-gray-200 disabled:opacity-50"
                >
                  <Save className="h-3.5 w-3.5" />
                  {savingScope ? 'Saving…' : 'Save Scope'}
                </button>
              </>
            ) : (
              <button
                type="button"
                onClick={() => {
                  setScopeDraft(scopeEntries.map((entry) => ({ ...entry })))
                  setEditingScope(true)
                  setScopeMessage(null)
                }}
                disabled={offline}
                className="inline-flex items-center gap-1 rounded-lg border border-gray-700 px-3 py-2 text-xs text-gray-300 transition-colors hover:border-cyan-500 hover:text-white disabled:opacity-50"
              >
                <Pencil className="h-3.5 w-3.5" />
                Edit Scope
              </button>
            )}
          </div>
        </div>
        {scopeMessage && (
          <div className="mb-3 rounded-xl border border-gray-800 bg-gray-950 px-3 py-2 text-sm text-gray-300">
            {scopeMessage}
          </div>
        )}
        {(editingScope ? scopeDraft : scopeEntries).length === 0 ? (
          <div className="text-sm text-gray-500">No saved scope entries yet.</div>
        ) : (
          <div className="grid gap-3 md:grid-cols-2">
            {(editingScope ? scopeDraft : scopeEntries).map((entry, index) => (
              <div key={`${entry.entry_id ?? entry.kind}:${entry.path}:${index}`} className="rounded-xl border border-gray-800 bg-gray-950 px-3 py-3">
                {editingScope ? (
                  <div className="space-y-3">
                    <input
                      value={entry.path}
                      onChange={(event) =>
                        setScopeDraft((current) =>
                          current.map((candidate, candidateIndex) =>
                            candidateIndex === index ? { ...candidate, path: event.target.value } : candidate,
                          ),
                        )
                      }
                      className="w-full rounded-lg border border-gray-700 bg-gray-900 px-3 py-2 text-xs text-white outline-none focus:border-cyan-500"
                    />
                    <div className="grid gap-2 md:grid-cols-[1fr,1fr,auto,auto]">
                      <select
                        value={entry.kind}
                        onChange={(event) =>
                          setScopeDraft((current) =>
                            current.map((candidate, candidateIndex) =>
                              candidateIndex === index
                                ? { ...candidate, kind: event.target.value as ScopeEntry['kind'] }
                                : candidate,
                            ),
                          )
                        }
                        className="rounded-lg border border-gray-700 bg-gray-900 px-3 py-2 text-xs text-white outline-none focus:border-cyan-500"
                      >
                        <option value="repo">Repo</option>
                        <option value="doc">Doc</option>
                        <option value="log">Log</option>
                        <option value="exclude">Exclude</option>
                      </select>
                      <select
                        value={entry.path_type}
                        onChange={(event) =>
                          setScopeDraft((current) =>
                            current.map((candidate, candidateIndex) =>
                              candidateIndex === index
                                ? { ...candidate, path_type: event.target.value as ScopeEntry['path_type'] }
                                : candidate,
                            ),
                          )
                        }
                        className="rounded-lg border border-gray-700 bg-gray-900 px-3 py-2 text-xs text-white outline-none focus:border-cyan-500"
                      >
                        <option value="file">File</option>
                        <option value="dir">Dir</option>
                        <option value="glob">Glob</option>
                      </select>
                      <label className="inline-flex items-center gap-2 rounded-lg border border-gray-700 px-3 py-2 text-xs text-gray-300">
                        <input
                          type="checkbox"
                          checked={entry.enabled}
                          onChange={(event) =>
                            setScopeDraft((current) =>
                              current.map((candidate, candidateIndex) =>
                                candidateIndex === index
                                  ? { ...candidate, enabled: event.target.checked }
                                  : candidate,
                              ),
                            )
                          }
                        />
                        Enabled
                      </label>
                      <button
                        type="button"
                        onClick={() =>
                          setScopeDraft((current) => current.filter((_, candidateIndex) => candidateIndex !== index))
                        }
                        className="rounded-lg border border-red-900 px-3 py-2 text-xs text-red-300 transition-colors hover:border-red-700 hover:text-red-200"
                      >
                        Remove
                      </button>
                    </div>
                  </div>
                ) : (
                  <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0">
                      <div className="font-mono text-xs text-gray-300 break-all">{entry.path}</div>
                      <div className="mt-1 text-xs uppercase tracking-[0.16em] text-gray-500">
                        {entry.path_type} · {entry.source}
                      </div>
                    </div>
                    <span className="rounded-full border border-gray-700 px-2 py-0.5 text-[11px] uppercase tracking-[0.16em] text-cyan-300">
                      {entry.kind}
                    </span>
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
        {editingScope && (
          <div className="mt-4 rounded-xl border border-gray-800 bg-gray-950 p-4">
            <div className="text-xs uppercase tracking-[0.16em] text-gray-500">Add scope entry</div>
            <div className="mt-3 grid gap-3 md:grid-cols-[2fr,1fr,1fr,auto]">
              <input
                value={newScopePath}
                onChange={(event) => setNewScopePath(event.target.value)}
                className="rounded-lg border border-gray-700 bg-gray-900 px-3 py-2 text-sm text-white outline-none focus:border-cyan-500"
                placeholder="/path/to/folder/or/file"
              />
              <select
                value={newScopeKind}
                onChange={(event) => setNewScopeKind(event.target.value as ScopeEntry['kind'])}
                className="rounded-lg border border-gray-700 bg-gray-900 px-3 py-2 text-sm text-white outline-none focus:border-cyan-500"
              >
                <option value="repo">Repo</option>
                <option value="doc">Doc</option>
                <option value="log">Log</option>
                <option value="exclude">Exclude</option>
              </select>
              <select
                value={newScopePathType}
                onChange={(event) => setNewScopePathType(event.target.value as ScopeEntry['path_type'])}
                className="rounded-lg border border-gray-700 bg-gray-900 px-3 py-2 text-sm text-white outline-none focus:border-cyan-500"
              >
                <option value="file">File</option>
                <option value="dir">Dir</option>
                <option value="glob">Glob</option>
              </select>
              <button
                type="button"
                onClick={addScopeEntry}
                className="rounded-lg border border-gray-700 px-3 py-2 text-sm text-gray-200 transition-colors hover:border-cyan-500 hover:text-white"
              >
                Add
              </button>
            </div>
          </div>
        )}
      </section>

      {/* Downloads */}
      <section className="mb-6 bg-gray-900 border border-gray-800 rounded-xl p-4">
        <h3 className="text-sm font-medium text-gray-300 mb-3">Files</h3>
        <DownloadPanel serviceId={serviceId} docs={docs} logs={logs} disabled={offline} />
      </section>

      {service && (
        <section className="mb-6 bg-gray-900 border border-gray-800 rounded-xl p-4">
          <h3 className="mb-3 flex items-center gap-2 text-sm font-medium text-gray-300">
            <FileStack className="h-4 w-4 text-cyan-400" />
            Pull bundles
          </h3>
          <PullBundlePanel service={service} disabled={offline} />
        </section>
      )}

      {/* Secret paths */}
      <section className="mb-6">
        <SecretPathGuard serviceId={serviceId} disabled={offline} />
      </section>

      {/* Run history */}
      {runs.length > 0 && (
        <section className="bg-gray-900 border border-gray-800 rounded-xl p-4">
          <h3 className="text-sm font-medium text-gray-300 mb-3">Run History</h3>
          <ul className="space-y-2">
            {runs.slice(0, 5).map((r) => (
              <li key={r.run_id} className="flex items-center justify-between text-sm">
                <span className="text-gray-500 font-mono text-xs">
                  {new Date(r.timestamp).toLocaleString()}
                </span>
                <StatusBadge status={r.status} />
              </li>
            ))}
          </ul>
        </section>
      )}
    </div>
  )
}
