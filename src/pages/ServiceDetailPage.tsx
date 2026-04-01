import { useEffect, useState } from 'react'
import { ArrowLeft, FileStack, FolderTree, Pencil, Save, Server, Trash2, X } from 'lucide-react'
import type { Service, ServiceRunResult, RunRecord, ScopeEntry } from '../types/switchboard'
import { deleteService, getService, getServiceScope, getWorkspaceRuns, updateService } from '../api/client'
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

  useEffect(() => {
    if (offline) return
    getService(serviceId).then((res) => {
      if (!isApiError(res)) setService(res)
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
