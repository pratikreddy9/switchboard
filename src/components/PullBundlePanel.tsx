import { useEffect, useMemo, useState } from 'react'
import { Archive, ChevronDown, ChevronRight, Download, LoaderCircle, PackagePlus } from 'lucide-react'
import { createPullBundle, listPullBundles, acquireActionLock, releaseActionLock } from '../api/client'
import type { PullBundleRecord, ScopeEntry, Service } from '../types/switchboard'
import { isApiError } from '../types/switchboard'
import { StatusBadge } from './StatusBadge'
import { ConfirmationModal, ACTION_EXPLAIN } from './ConfirmationModal'

interface Props {
  service: Service
  disabled?: boolean
}

function uniqueByPath(entries: ScopeEntry[]) {
  const seen = new Set<string>()
  return entries.filter((entry) => {
    if (seen.has(`${entry.kind}:${entry.path}`)) return false
    seen.add(`${entry.kind}:${entry.path}`)
    return true
  })
}

export function PullBundlePanel({ service, disabled }: Props) {
  const [history, setHistory] = useState<PullBundleRecord[]>([])
  const [bundleResult, setBundleResult] = useState<PullBundleRecord | null>(null)
  const [includePath, setIncludePath] = useState('')
  const [includeKind, setIncludeKind] = useState<'doc' | 'log'>('doc')
  const [includePathType, setIncludePathType] = useState<'file' | 'dir' | 'glob'>('file')
  const [extraIncludes, setExtraIncludes] = useState<ScopeEntry[]>([])
  const [extraExcludes, setExtraExcludes] = useState('')
  const [note, setNote] = useState('')
  const [creating, setCreating] = useState(false)
  const [message, setMessage] = useState('')
  const [expandedHistory, setExpandedHistory] = useState<Record<string, boolean>>({})
  const [confirmOpen, setConfirmOpen] = useState(false)
  const [pendingActions, setPendingActions] = useState<Record<string, boolean>>({})

  useEffect(() => {
    const keys = Object.keys(sessionStorage)
    const pending: Record<string, boolean> = {}
    for (const key of keys) {
      if (key.startsWith('pending:')) pending[key] = true
    }
    setPendingActions(pending)
  }, [])

  useEffect(() => {
    if (disabled) return
    listPullBundles(service.service_id).then((result) => {
      if (!isApiError(result)) setHistory(result)
    })
  }, [disabled, service.service_id])

  const savedScope = useMemo(
    () => service.scope_entries.filter((entry) => entry.enabled && entry.kind !== 'exclude'),
    [service.scope_entries],
  )
  const latestBundleWithFiles = useMemo(() => {
    if (bundleResult?.files?.length) return bundleResult
    return history.find((bundle) => (bundle.files?.length ?? 0) > 0) ?? null
  }, [bundleResult, history])

  function matchingFilesForScope(scopePath: string) {
    const files = latestBundleWithFiles?.files ?? []
    return files.filter((file) => file.source_path.startsWith(scopePath))
  }

  function addExtraInclude() {
    const trimmed = includePath.trim()
    if (!trimmed) return
    setExtraIncludes((current) =>
      uniqueByPath([
        ...current,
        {
          kind: includeKind,
          path: trimmed,
          path_type: includePathType,
          source: 'user_added',
          enabled: true,
        },
      ]),
    )
    setIncludePath('')
  }

  function initiateCreate() {
    setConfirmOpen(true)
  }

  async function handleCreate() {
    const actionKey = 'pull_bundle'
    const sessionKey = `pending:${actionKey}:${service.service_id}`
    
    sessionStorage.setItem(sessionKey, 'true')
    setPendingActions(prev => ({ ...prev, [sessionKey]: true }))
    setConfirmOpen(false)
    setCreating(true)
    setMessage('')

    const lockRes = await acquireActionLock(service.service_id, actionKey)
    if (isApiError(lockRes) || lockRes.status !== 'ok') {
      setMessage((lockRes as any)?.message || 'Action is already in progress.')
      setCreating(false)
      sessionStorage.removeItem(sessionKey)
      setPendingActions(prev => { const next = { ...prev }; delete next[sessionKey]; return next })
      return
    }

    try {
      const result = await createPullBundle(service.service_id, {
        extra_includes: extraIncludes,
        extra_excludes: extraExcludes
          .split('\n')
          .map((line) => line.trim())
          .filter(Boolean),
        note,
      })
      if (isApiError(result)) {
        setMessage(result.message)
        return
      }
      setBundleResult(result)
      setHistory((current) => [result, ...current])
      setMessage(`Bundle ${result.bundle_id} created.`)
    } finally {
      await releaseActionLock(service.service_id, actionKey)
      setCreating(false)
      sessionStorage.removeItem(sessionKey)
      setPendingActions(prev => { const next = { ...prev }; delete next[sessionKey]; return next })
    }
  }

  return (
    <div className="space-y-5">
      <div className="rounded-xl border border-gray-800 bg-gray-950 p-4">
        <div className="flex items-center justify-between gap-3">
          <div>
            <div className="flex items-center gap-2 text-sm font-medium text-white">
              <PackagePlus className="h-4 w-4 text-cyan-400" />
              Create pull bundle
            </div>
            <p className="mt-1 text-sm text-gray-500">
              Pull saved scope plus one-run extras into a versioned local mirror of the source tree.
            </p>
          </div>
          <button
            onClick={initiateCreate}
            disabled={disabled || creating || pendingActions[`pending:pull_bundle:${service.service_id}`]}
            className="inline-flex items-center gap-2 rounded-lg bg-white px-4 py-2 text-sm font-medium text-black transition-colors hover:bg-gray-200 disabled:opacity-50"
          >
            {creating || pendingActions[`pending:pull_bundle:${service.service_id}`] ? <LoaderCircle className="h-4 w-4 animate-spin" /> : <Archive className="h-4 w-4" />}
            {creating || pendingActions[`pending:pull_bundle:${service.service_id}`] ? 'Creating' : 'Create bundle'}
          </button>
        </div>

        <div className="mt-4 grid gap-4 lg:grid-cols-2">
          <div className="rounded-xl border border-gray-800 bg-gray-900 p-3">
            <div className="text-xs uppercase tracking-[0.16em] text-gray-500">Saved scope</div>
            <div className="mt-3 space-y-2">
              {savedScope.length === 0 ? (
                <div className="text-sm text-gray-500">No saved scope entries yet.</div>
              ) : (
                savedScope.map((entry) => (
                  <div key={`${entry.kind}:${entry.path}`} className="rounded-lg border border-gray-800 bg-gray-950 px-3 py-2">
                    <div className="flex items-center justify-between gap-3">
                      <div className="min-w-0 flex-1">
                        <div className="font-mono text-xs text-gray-300 break-all">{entry.path}</div>
                        {matchingFilesForScope(entry.path).length > 0 && (
                          <div className="mt-2 max-h-32 space-y-1 overflow-auto rounded border border-gray-800 bg-black/20 p-2">
                            {matchingFilesForScope(entry.path)
                              .slice(0, 20)
                              .map((file) => (
                                <div key={`${file.target_path}:${file.sha256}`} className="font-mono text-[11px] text-gray-400 break-all">
                                  {file.relative_path}
                                </div>
                              ))}
                          </div>
                        )}
                      </div>
                      <span className="rounded-full border border-gray-700 px-2 py-0.5 text-[11px] uppercase tracking-[0.14em] text-cyan-300">
                        {entry.kind}
                      </span>
                    </div>
                  </div>
                ))
              )}
            </div>
          </div>

          <div className="rounded-xl border border-gray-800 bg-gray-900 p-3">
            <div className="text-xs uppercase tracking-[0.16em] text-gray-500">One-run extras</div>
            <div className="mt-3 grid gap-3 md:grid-cols-[2fr,1fr,1fr,auto]">
              <input
                value={includePath}
                onChange={(event) => setIncludePath(event.target.value)}
                className="rounded-lg border border-gray-700 bg-gray-950 px-3 py-2 text-sm text-white outline-none focus:border-cyan-500"
                placeholder="/path/to/extra/file.log"
                disabled={disabled}
              />
              <select
                value={includeKind}
                onChange={(event) => setIncludeKind(event.target.value as 'doc' | 'log')}
                className="rounded-lg border border-gray-700 bg-gray-950 px-3 py-2 text-sm text-white outline-none focus:border-cyan-500"
                disabled={disabled}
              >
                <option value="doc">Doc</option>
                <option value="log">Log</option>
              </select>
              <select
                value={includePathType}
                onChange={(event) => setIncludePathType(event.target.value as 'file' | 'dir' | 'glob')}
                className="rounded-lg border border-gray-700 bg-gray-950 px-3 py-2 text-sm text-white outline-none focus:border-cyan-500"
                disabled={disabled}
              >
                <option value="file">File</option>
                <option value="dir">Dir</option>
                <option value="glob">Glob</option>
              </select>
              <button
                onClick={addExtraInclude}
                disabled={disabled}
                className="rounded-lg border border-gray-700 px-3 py-2 text-sm text-gray-200 transition-colors hover:border-cyan-500 hover:text-white disabled:opacity-50"
              >
                Add
              </button>
            </div>

            <div className="mt-3 space-y-2">
              {extraIncludes.length === 0 ? (
                <div className="text-sm text-gray-500">No extra include paths for this run.</div>
              ) : (
                extraIncludes.map((entry) => (
                  <div key={`${entry.kind}:${entry.path}`} className="flex items-center justify-between rounded-lg border border-gray-800 bg-gray-950 px-3 py-2">
                    <div>
                      <div className="font-mono text-xs text-gray-300">{entry.path}</div>
                      <div className="mt-1 text-[11px] uppercase tracking-[0.14em] text-gray-500">
                        {entry.kind} · {entry.path_type}
                      </div>
                    </div>
                    <button
                      onClick={() => setExtraIncludes((current) => current.filter((candidate) => candidate.path !== entry.path))}
                      className="text-xs text-red-300 transition-colors hover:text-red-200"
                    >
                      Remove
                    </button>
                  </div>
                ))
              )}
            </div>

            <label className="mt-4 block text-sm text-gray-300">
              <div className="mb-1">Extra excludes</div>
              <textarea
                value={extraExcludes}
                onChange={(event) => setExtraExcludes(event.target.value)}
                className="min-h-28 w-full rounded-lg border border-gray-700 bg-gray-950 px-3 py-2 text-sm text-white outline-none focus:border-cyan-500"
                placeholder="One path or glob per line"
                disabled={disabled}
              />
            </label>

            <label className="mt-4 block text-sm text-gray-300">
              <div className="mb-1">Pull note</div>
              <textarea
                value={note}
                onChange={(event) => setNote(event.target.value)}
                className="min-h-24 w-full rounded-lg border border-gray-700 bg-gray-950 px-3 py-2 text-sm text-white outline-none focus:border-cyan-500"
                placeholder="Optional note for this pull bundle."
                disabled={disabled}
              />
            </label>
          </div>
        </div>

        <div className="mt-4 text-sm text-gray-400">
          {message || 'Bundle creation stays read-safe. Files are mirrored under the original tree shape, and doc/log labels stay in metadata.'}
        </div>
        {bundleResult && (
          <div className="mt-3 rounded-xl border border-green-800 bg-green-950/20 p-3 text-sm text-green-200">
            <div className="flex items-center justify-between gap-3">
              <div>
                <div className="font-medium">{bundleResult.bundle_id}</div>
                <div className="mt-1 text-xs text-green-300/80">
                  {bundleResult.source_tree_path ?? bundleResult.bundle_path}
                </div>
              </div>
              <StatusBadge status="ok" />
            </div>
            {bundleResult.diff_summary && (
              <div className="mt-3 rounded-lg border border-amber-800/40 bg-amber-950/20 px-3 py-2 text-xs text-amber-200">
                {bundleResult.diff_summary.summary}
              </div>
            )}
            {bundleResult.note && (
              <div className="mt-3 rounded-lg border border-gray-800 bg-black/20 px-3 py-2 text-xs text-gray-200">
                {bundleResult.note}
              </div>
            )}
            <div className="mt-3 grid gap-3 md:grid-cols-2">
              <div className="rounded-lg border border-green-900/40 bg-black/20 p-3">
                <div className="text-xs uppercase tracking-[0.16em] text-green-300/80">Pulled files</div>
                <div className="mt-2 max-h-56 space-y-1 overflow-auto">
                  {(bundleResult.files ?? []).length === 0 ? (
                    <div className="text-xs text-green-200/70">No copied files recorded.</div>
                  ) : (
                    (bundleResult.files ?? []).slice(0, 40).map((file) => (
                      <div key={`${file.target_path}:${file.sha256}`} className="rounded border border-green-900/30 px-2 py-1">
                        <div className="font-mono text-[11px] break-all">{file.relative_path}</div>
                        <div className="mt-1 text-[10px] uppercase tracking-[0.14em] text-green-300/70">{file.kind}</div>
                      </div>
                    ))
                  )}
                </div>
              </div>
              <div className="rounded-lg border border-yellow-900/40 bg-black/20 p-3">
                {(bundleResult.exposure_findings?.length ?? 0) > 0 && (
                  <div className="mb-3 rounded-lg border border-yellow-900/30 bg-yellow-950/20 px-3 py-2 text-xs text-yellow-200">
                    {bundleResult.exposure_findings?.length} exposure finding{bundleResult.exposure_findings?.length === 1 ? '' : 's'} in pulled files.
                  </div>
                )}
                <div className="text-xs uppercase tracking-[0.16em] text-yellow-200/80">Missed scope</div>
                <div className="mt-2 max-h-56 space-y-1 overflow-auto">
                  {(bundleResult.skipped_entries ?? []).length === 0 ? (
                    <div className="text-xs text-green-200/70">No skipped scope entries.</div>
                  ) : (
                    (bundleResult.skipped_entries ?? []).map((entry) => (
                      <div key={`${entry.path}:${entry.reason}`} className="rounded border border-yellow-900/30 px-2 py-1">
                        <div className="font-mono text-[11px] break-all">{entry.path}</div>
                        <div className="mt-1 text-[10px] uppercase tracking-[0.14em] text-yellow-200/70">
                          {entry.kind} · {entry.path_type} · {entry.reason}
                        </div>
                      </div>
                    ))
                  )}
                </div>
              </div>
            </div>
          </div>
        )}
      </div>

      <div className="rounded-xl border border-gray-800 bg-gray-950 p-4">
        <div className="flex items-center gap-2 text-sm font-medium text-white">
          <Download className="h-4 w-4 text-cyan-400" />
          Bundle history
        </div>
        <div className="mt-3 space-y-3">
          {history.length === 0 ? (
            <div className="text-sm text-gray-500">No bundle history yet.</div>
          ) : (
            history.map((bundle) => (
              <div key={bundle.bundle_id} className="rounded-xl border border-gray-800 bg-gray-900 px-4 py-3">
                <div className="flex items-start justify-between gap-3">
                  <button
                    type="button"
                    onClick={() =>
                      setExpandedHistory((current) => ({
                        ...current,
                        [bundle.bundle_id]: !current[bundle.bundle_id],
                      }))
                    }
                    className="flex min-w-0 flex-1 items-start gap-2 text-left"
                  >
                    {expandedHistory[bundle.bundle_id] ? (
                      <ChevronDown className="mt-0.5 h-4 w-4 text-gray-500" />
                    ) : (
                      <ChevronRight className="mt-0.5 h-4 w-4 text-gray-500" />
                    )}
                    <div className="min-w-0">
                      <div className="font-mono text-xs text-gray-300 break-all">{bundle.bundle_id}</div>
                      <div className="mt-1 text-xs text-gray-500">
                        {new Date(bundle.created_at).toLocaleString()} · {bundle.file_count} files
                      </div>
                      {bundle.diff_summary && (
                        <div className="mt-2 inline-flex rounded-full border border-amber-900/50 bg-amber-950/20 px-2 py-0.5 text-[11px] text-amber-200">
                          {bundle.diff_summary.summary}
                        </div>
                      )}
                    </div>
                  </button>
                  <div className="text-right text-xs text-gray-400">
                    <div>{bundle.docs_count} docs</div>
                    <div>{bundle.logs_count} logs</div>
                    <div>{bundle.skipped_entry_count ?? 0} missed</div>
                  </div>
                </div>
                {expandedHistory[bundle.bundle_id] && (
                  <div className="mt-3 space-y-3">
                    {(bundle.note || bundle.dependency_context || (bundle.exposure_findings?.length ?? 0) > 0) && (
                      <div className="rounded-lg border border-gray-800 bg-gray-950 p-3">
                        <div className="text-xs uppercase tracking-[0.16em] text-gray-500">Bundle Notes</div>
                        {bundle.note && <div className="mt-2 text-sm text-gray-300">{bundle.note}</div>}
                        {bundle.dependency_context && (
                          <div className="mt-3 grid gap-3 md:grid-cols-2">
                            <div>
                              <div className="text-[11px] uppercase tracking-[0.16em] text-gray-500">Dependencies</div>
                              <div className="mt-2 space-y-1">
                                {(bundle.dependency_context.dependencies ?? []).length === 0 ? (
                                  <div className="text-xs text-gray-600">None</div>
                                ) : (
                                  bundle.dependency_context.dependencies?.map((dep, idx) => (
                                    <div key={idx} className="text-xs text-gray-300">
                                      {dep.kind} · {dep.name} · {dep.host || 'local'}{dep.port ? `:${dep.port}` : ''}
                                    </div>
                                  ))
                                )}
                              </div>
                            </div>
                            <div>
                              <div className="text-[11px] uppercase tracking-[0.16em] text-gray-500">Cross-System Notes</div>
                              <div className="mt-2 space-y-1">
                                {(bundle.dependency_context.cross_dependencies ?? []).length === 0 ? (
                                  <div className="text-xs text-gray-600">None</div>
                                ) : (
                                  bundle.dependency_context.cross_dependencies?.map((dep, idx) => (
                                    <div key={idx} className="text-xs text-gray-300">
                                      {dep.kind} · {dep.name} · {dep.host || 'local'}{dep.port ? `:${dep.port}` : ''}
                                    </div>
                                  ))
                                )}
                              </div>
                            </div>
                          </div>
                        )}
                        {(bundle.exposure_findings?.length ?? 0) > 0 && (
                          <div className="mt-3">
                            <div className="text-[11px] uppercase tracking-[0.16em] text-yellow-300">Exposure Notes</div>
                            <div className="mt-2 space-y-1">
                              {bundle.exposure_findings?.map((finding, idx) => (
                                <div key={idx} className="text-xs text-yellow-100/90">
                                  {finding.relative_path} · {finding.finding_kind}{finding.variable_name ? ` · ${finding.variable_name}` : ''} · line {finding.line_number}
                                </div>
                              ))}
                            </div>
                          </div>
                        )}
                      </div>
                    )}
                    {(bundle.diff_entries?.length ?? 0) > 0 && (
                      <div className="rounded-lg border border-gray-800 bg-gray-950 p-3">
                        <div className="text-xs uppercase tracking-[0.16em] text-gray-500">Diff</div>
                        <div className="mt-2 max-h-48 space-y-1 overflow-auto">
                          {bundle.diff_entries?.map((entry, idx) => (
                            <div key={`${bundle.bundle_id}:${entry.relative_path}:${idx}`} className="flex items-center gap-2 rounded border border-gray-800 px-2 py-1 text-xs">
                              <span className={entry.change === 'added' ? 'text-green-400' : entry.change === 'removed' ? 'text-red-400' : 'text-amber-300'}>
                                {entry.change === 'added' ? '+' : entry.change === 'removed' ? '-' : '~'}
                              </span>
                              <span className="font-mono text-gray-300 break-all">{entry.relative_path}</span>
                              <span className="ml-auto uppercase tracking-[0.14em] text-gray-500">{entry.kind}</span>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}
                  <div className="grid gap-3 md:grid-cols-2">
                    <div className="rounded-lg border border-gray-800 bg-gray-950 p-3">
                      <div className="text-xs uppercase tracking-[0.16em] text-gray-500">Pulled files</div>
                      <div className="mt-2 max-h-56 space-y-1 overflow-auto">
                        {(bundle.files ?? []).length === 0 ? (
                          <div className="text-xs text-gray-500">No copied file list stored for this bundle.</div>
                        ) : (
                          (bundle.files ?? []).map((file) => (
                            <div key={`${bundle.bundle_id}:${file.target_path}:${file.sha256}`} className="rounded border border-gray-800 px-2 py-1">
                              <div className="font-mono text-[11px] text-gray-300 break-all">{file.relative_path}</div>
                              <div className="mt-1 text-[10px] uppercase tracking-[0.14em] text-gray-500">{file.kind}</div>
                            </div>
                          ))
                        )}
                      </div>
                    </div>
                    <div className="rounded-lg border border-gray-800 bg-gray-950 p-3">
                      <div className="text-xs uppercase tracking-[0.16em] text-gray-500">Missed scope</div>
                      <div className="mt-2 max-h-56 space-y-1 overflow-auto">
                        {(bundle.skipped_entries ?? []).length === 0 ? (
                          <div className="text-xs text-gray-500">No missed scope entries.</div>
                        ) : (
                          (bundle.skipped_entries ?? []).map((entry) => (
                            <div key={`${bundle.bundle_id}:${entry.path}:${entry.reason}`} className="rounded border border-gray-800 px-2 py-1">
                              <div className="font-mono text-[11px] text-gray-300 break-all">{entry.path}</div>
                              <div className="mt-1 text-[10px] uppercase tracking-[0.14em] text-gray-500">
                                {entry.kind} · {entry.path_type} · {entry.reason}
                              </div>
                            </div>
                          ))
                        )}
                      </div>
                    </div>
                  </div>
                  </div>
                )}
              </div>
            ))
          )}
        </div>
      </div>

      <div className="rounded-xl border border-gray-800 bg-gray-950 p-4">
        <div className="flex items-center gap-2 text-sm font-medium text-white mb-3">
          <Archive className="h-4 w-4 text-gray-500" />
          Left Out Scope
        </div>
        <div className="grid gap-3 md:grid-cols-3">
          <div className="rounded-lg border border-gray-800 bg-gray-900 p-3">
            <div className="text-xs uppercase tracking-[0.16em] text-gray-500 mb-2">Saved Excludes</div>
            <div className="space-y-1 max-h-40 overflow-auto">
              {service.scope_entries.filter(e => e.kind === 'exclude' && e.enabled).length === 0 ? (
                <div className="text-xs text-gray-600">None</div>
              ) : (
                service.scope_entries.filter(e => e.kind === 'exclude' && e.enabled).map((e, idx) => (
                  <div key={idx} className="font-mono text-[10px] text-gray-400 break-all">{e.path}</div>
                ))
              )}
            </div>
          </div>
          <div className="rounded-lg border border-gray-800 bg-gray-900 p-3">
            <div className="text-xs uppercase tracking-[0.16em] text-gray-500 mb-2">One-run Excludes</div>
            <div className="space-y-1 max-h-40 overflow-auto">
              {!extraExcludes.trim() ? (
                <div className="text-xs text-gray-600">None</div>
              ) : (
                extraExcludes.split('\n').filter(Boolean).map((e, idx) => (
                  <div key={idx} className="font-mono text-[10px] text-gray-400 break-all">{e.trim()}</div>
                ))
              )}
            </div>
          </div>
          <div className="rounded-lg border border-gray-800 bg-gray-900 p-3">
            <div className="text-xs uppercase tracking-[0.16em] text-gray-500 mb-2">Latest Skipped</div>
            <div className="space-y-1 max-h-40 overflow-auto">
              {(latestBundleWithFiles?.skipped_entries ?? []).length === 0 ? (
                <div className="text-xs text-gray-600">None</div>
              ) : (
                (latestBundleWithFiles?.skipped_entries ?? []).map((entry, idx) => (
                  <div key={idx} className="font-mono text-[10px] text-gray-400 break-all">
                    {entry.path} <span className="text-gray-600">({entry.reason})</span>
                  </div>
                ))
              )}
            </div>
          </div>
        </div>
      </div>

      {confirmOpen && ACTION_EXPLAIN['pull_bundle'] && (
        <ConfirmationModal
          open={confirmOpen}
          title={ACTION_EXPLAIN['pull_bundle'].title}
          willDo={ACTION_EXPLAIN['pull_bundle'].happens}
          willNotChange={ACTION_EXPLAIN['pull_bundle'].untouched}
          writesTo={ACTION_EXPLAIN['pull_bundle'].writesTo}
          onConfirm={handleCreate}
          onCancel={() => setConfirmOpen(false)}
        />
      )}
    </div>
  )
}
