import { useEffect, useMemo, useState } from 'react'
import { Archive, Download, LoaderCircle, PackagePlus } from 'lucide-react'
import { createPullBundle, listPullBundles } from '../api/client'
import type { PullBundleRecord, ScopeEntry, Service } from '../types/switchboard'
import { isApiError } from '../types/switchboard'
import { StatusBadge } from './StatusBadge'

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
  const [creating, setCreating] = useState(false)
  const [message, setMessage] = useState('')

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

  async function handleCreate() {
    setCreating(true)
    setMessage('')
    const result = await createPullBundle(service.service_id, {
      extra_includes: extraIncludes,
      extra_excludes: extraExcludes
        .split('\n')
        .map((line) => line.trim())
        .filter(Boolean),
    })
    setCreating(false)
    if (isApiError(result)) {
      setMessage(result.message)
      return
    }
    setBundleResult(result)
    setHistory((current) => [result, ...current])
    setMessage(`Bundle ${result.bundle_id} created.`)
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
            onClick={handleCreate}
            disabled={disabled || creating}
            className="inline-flex items-center gap-2 rounded-lg bg-white px-4 py-2 text-sm font-medium text-black transition-colors hover:bg-gray-200 disabled:opacity-50"
          >
            {creating ? <LoaderCircle className="h-4 w-4 animate-spin" /> : <Archive className="h-4 w-4" />}
            {creating ? 'Creating' : 'Create bundle'}
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
                      <span className="font-mono text-xs text-gray-300">{entry.path}</span>
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
                  <div>
                    <div className="font-mono text-xs text-gray-300">{bundle.bundle_id}</div>
                    <div className="mt-1 text-xs text-gray-500">
                      {new Date(bundle.created_at).toLocaleString()} · {bundle.file_count} files
                    </div>
                  </div>
                  <div className="text-right text-xs text-gray-400">
                    <div>{bundle.docs_count} docs</div>
                    <div>{bundle.logs_count} logs</div>
                    <div>{bundle.skipped_entry_count ?? 0} missed</div>
                  </div>
                </div>
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  )
}
