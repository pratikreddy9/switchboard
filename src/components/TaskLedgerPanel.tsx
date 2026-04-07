import React, { useEffect, useState } from 'react'
import { ChevronDown, ChevronRight, Activity, Cpu, Network, PenTool, Hash, LayoutTemplate, Braces } from 'lucide-react'
import type { TaskLedgerEntry } from '../types/switchboard'

interface Props {
  tasks: TaskLedgerEntry[]
  title?: string
  showServiceLabel?: boolean
}

export function TaskLedgerPanel({ tasks, title = 'Task Ledger', showServiceLabel = false }: Props) {
  const [expanded, setExpanded] = useState<Record<string, boolean>>({})

  useEffect(() => {
    const first = tasks[0]
    if (!first) return
    const firstId = first.task_id || `${first.timestamp}-0`
    setExpanded((current) => (Object.keys(current).length > 0 ? current : { [firstId]: true }))
  }, [tasks])

  if (!tasks || tasks.length === 0) {
    return null
  }

  function toggle(id: string) {
    setExpanded((curr) => ({ ...curr, [id]: !curr[id] }))
  }

  function stripFence(value?: string) {
    if (!value) return ''
    const trimmed = value.trim()
    const match = /^```[a-zA-Z0-9_-]*\n([\s\S]*?)\n```$/.exec(trimmed)
    return match ? match[1].trim() : trimmed
  }

  return (
    <div className="space-y-4">
      {title && (
        <h3 className="text-sm font-medium text-gray-300 mb-3 flex items-center gap-2">
          <Activity className="h-4 w-4 text-cyan-400" />
          {title}
        </h3>
      )}
      <div className="space-y-3">
        {tasks.map((task, idx) => {
          const rowId = task.task_id || `${task.timestamp}-${idx}`
          const isExpanded = expanded[rowId]
          return (
            <div key={rowId} className="rounded-xl border border-gray-800 bg-gray-900 overflow-hidden">
              <button
                type="button"
                onClick={() => toggle(rowId)}
                className="w-full flex items-start justify-between p-3 text-left hover:bg-gray-800/50 transition-colors"
              >
                <div className="flex items-start gap-3 min-w-0">
                  {isExpanded ? (
                    <ChevronDown className="h-4 w-4 text-gray-500 mt-1 shrink-0" />
                  ) : (
                    <ChevronRight className="h-4 w-4 text-gray-500 mt-1 shrink-0" />
                  )}
                  <div className="min-w-0">
                    <div className="flex flex-wrap items-center gap-2">
                      {showServiceLabel && task.service_name && (
                        <span className="rounded border border-indigo-900 bg-indigo-950/60 px-1.5 py-0.5 text-[10px] font-medium text-indigo-300">
                          {task.service_name}
                        </span>
                      )}
                      {showServiceLabel && task.node_id && (
                        <span className="rounded bg-gray-800 px-1.5 py-0.5 text-[10px] font-medium text-gray-300">
                          {task.node_id}
                        </span>
                      )}
                      <span className="text-sm font-medium text-gray-200 truncate">
                        {task.title}
                      </span>
                      {task.agent && (
                        <span className="rounded-full border border-cyan-900 bg-cyan-950/60 px-2 py-0.5 text-[10px] uppercase tracking-[0.1em] text-cyan-300 flex items-center gap-1">
                          <Cpu className="h-3 w-3" />
                          {task.agent}
                        </span>
                      )}
                      {task.tool && (
                        <span className="rounded-full border border-purple-900 bg-purple-950/60 px-2 py-0.5 text-[10px] uppercase tracking-[0.1em] text-purple-300 flex items-center gap-1">
                          <PenTool className="h-3 w-3" />
                          {task.tool}
                        </span>
                      )}
                      {task.task_id && (
                        <span className="rounded border border-gray-700 bg-gray-800/50 px-1.5 py-0.5 text-[10px] font-mono text-gray-400 flex items-center gap-1">
                          <Hash className="h-3 w-3" />
                          {task.task_id}
                        </span>
                      )}
                    </div>
                    <div className="mt-1 flex flex-wrap items-center gap-2 text-xs text-gray-500">
                      <span>{new Date(task.timestamp).toLocaleString()}</span>
                      {task.tags && task.tags.length > 0 && (
                        <>
                          <span className="text-gray-700">•</span>
                          <span className="flex gap-1">
                            {task.tags.map((tag) => (
                              <span key={tag} className="text-gray-400">#{tag}</span>
                            ))}
                          </span>
                        </>
                      )}
                    </div>
                  </div>
                </div>
              </button>

              {isExpanded && (
                <div className="border-t border-gray-800 p-4 space-y-4 bg-gray-950">
                  {task.summary && (
                    <div>
                      <div className="text-xs uppercase tracking-[0.1em] text-gray-500 mb-1">Summary</div>
                      <p className="text-sm text-gray-300">{task.summary}</p>
                    </div>
                  )}

                  {task.notes && task.notes.length > 0 && (
                    <div>
                      <div className="text-xs uppercase tracking-[0.1em] text-gray-500 mb-2">Notes</div>
                      <div className="space-y-2">
                        {task.notes.map((note, index) => (
                          <div key={`${note}:${index}`} className="rounded-lg border border-gray-800 bg-black/20 px-3 py-2 text-sm text-gray-300">
                            {note}
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {task.changed_paths && task.changed_paths.length > 0 && (
                    <div>
                      <div className="text-xs uppercase tracking-[0.1em] text-gray-500 mb-1">Changed Paths</div>
                      <ul className="list-disc pl-4 space-y-0.5">
                        {task.changed_paths.map((path) => (
                          <li key={path} className="text-xs font-mono text-gray-400">{path}</li>
                        ))}
                      </ul>
                    </div>
                  )}

                  {task.runtime_services && task.runtime_services.length > 0 && (
                    <div>
                      <div className="text-xs uppercase tracking-[0.1em] text-gray-500 mb-2 flex items-center gap-1">
                        <LayoutTemplate className="h-3.5 w-3.5" />
                        Runtime Services
                      </div>
                      <div className="overflow-x-auto">
                        <table className="w-full text-left text-xs">
                          <thead className="bg-gray-900 text-gray-400">
                            <tr>
                              <th className="px-3 py-2 font-medium">Name</th>
                              <th className="px-3 py-2 font-medium">Host:Port</th>
                              <th className="px-3 py-2 font-medium">Purpose</th>
                            </tr>
                          </thead>
                          <tbody className="divide-y divide-gray-800 bg-gray-900/50">
                            {task.runtime_services.map((rs, i) => (
                              <tr key={i}>
                                <td className="px-3 py-2 text-gray-300">{rs.name}</td>
                                <td className="px-3 py-2 font-mono text-gray-400">
                                  {rs.host || '*'}:{rs.port || 'any'}
                                </td>
                                <td className="px-3 py-2 text-gray-400">{rs.purpose}</td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    </div>
                  )}

                  {(task.readme || task.api || task.changelog) && (
                    <div className="grid gap-3 lg:grid-cols-3">
                      {task.readme && (
                        <div>
                          <div className="text-xs uppercase tracking-[0.1em] text-gray-500 mb-1">README</div>
                          <pre className="max-h-72 overflow-auto rounded-lg border border-gray-800 bg-black/50 p-3 text-[11px] text-gray-300 whitespace-pre-wrap">
                            {stripFence(task.readme)}
                          </pre>
                        </div>
                      )}
                      {task.api && (
                        <div>
                          <div className="text-xs uppercase tracking-[0.1em] text-gray-500 mb-1">API</div>
                          <pre className="max-h-72 overflow-auto rounded-lg border border-gray-800 bg-black/50 p-3 text-[11px] text-gray-300 whitespace-pre-wrap">
                            {stripFence(task.api)}
                          </pre>
                        </div>
                      )}
                      {task.changelog && (
                        <div>
                          <div className="text-xs uppercase tracking-[0.1em] text-gray-500 mb-1">CHANGELOG</div>
                          <pre className="max-h-72 overflow-auto rounded-lg border border-gray-800 bg-black/50 p-3 text-[11px] text-gray-300 whitespace-pre-wrap">
                            {stripFence(task.changelog)}
                          </pre>
                        </div>
                      )}
                    </div>
                  )}

                  {task.dependencies && task.dependencies.length > 0 && (
                    <div>
                      <div className="text-xs uppercase tracking-[0.1em] text-gray-500 mb-2 flex items-center gap-1">
                        <Braces className="h-3.5 w-3.5" />
                        Dependencies
                      </div>
                      <div className="overflow-x-auto">
                        <table className="w-full text-left text-xs">
                          <thead className="bg-gray-900 text-gray-400">
                            <tr>
                              <th className="px-3 py-2 font-medium">Kind</th>
                              <th className="px-3 py-2 font-medium">Name</th>
                              <th className="px-3 py-2 font-medium">Host:Port</th>
                              <th className="px-3 py-2 font-medium">Notes</th>
                            </tr>
                          </thead>
                          <tbody className="divide-y divide-gray-800 bg-gray-900/50">
                            {task.dependencies.map((dep, i) => (
                              <tr key={i}>
                                <td className="px-3 py-2">
                                  <span className="rounded border border-gray-700 px-1.5 py-0.5 text-[10px] uppercase text-gray-400">
                                    {dep.kind}
                                  </span>
                                </td>
                                <td className="px-3 py-2 text-gray-300">{dep.name}</td>
                                <td className="px-3 py-2 font-mono text-gray-400">
                                  {dep.host || '*'}:{dep.port || 'any'}
                                </td>
                                <td className="px-3 py-2 text-gray-400">{dep.notes}</td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    </div>
                  )}

                  {task.cross_dependencies && task.cross_dependencies.length > 0 && (
                    <div>
                      <div className="text-xs uppercase tracking-[0.1em] text-gray-500 mb-2 flex items-center gap-1">
                        <Network className="h-3.5 w-3.5" />
                        Cross Dependencies
                      </div>
                      <div className="overflow-x-auto">
                        <table className="w-full text-left text-xs">
                          <thead className="bg-gray-900 text-gray-400">
                            <tr>
                              <th className="px-3 py-2 font-medium">Kind</th>
                              <th className="px-3 py-2 font-medium">Name</th>
                              <th className="px-3 py-2 font-medium">Host:Port</th>
                              <th className="px-3 py-2 font-medium">Notes</th>
                            </tr>
                          </thead>
                          <tbody className="divide-y divide-gray-800 bg-gray-900/50">
                            {task.cross_dependencies.map((dep, i) => (
                              <tr key={i}>
                                <td className="px-3 py-2">
                                  <span className="rounded border border-gray-700 px-1.5 py-0.5 text-[10px] uppercase text-gray-400">
                                    {dep.kind}
                                  </span>
                                </td>
                                <td className="px-3 py-2 text-gray-300">{dep.name}</td>
                                <td className="px-3 py-2 font-mono text-gray-400">
                                  {dep.host || '*'}:{dep.port || 'any'}
                                </td>
                                <td className="px-3 py-2 text-gray-400">{dep.notes}</td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    </div>
                  )}

                  {task.scope_entries && task.scope_entries.length > 0 && (
                    <div>
                      <div className="text-xs uppercase tracking-[0.1em] text-gray-500 mb-2">Scope Entries</div>
                      <div className="space-y-2">
                        {task.scope_entries.map((entry, index) => (
                          <div key={`${entry.kind}:${entry.path}:${index}`} className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-gray-800 bg-black/20 px-3 py-2 text-xs">
                            <div className="min-w-0">
                              <span className="rounded border border-gray-700 px-1.5 py-0.5 uppercase text-gray-400">{entry.kind}</span>
                              <span className="ml-2 font-mono text-gray-300 break-all">{entry.path}</span>
                            </div>
                            <div className="text-gray-500">{entry.path_type}</div>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {task.diagram && (
                    <div>
                      <div className="text-xs uppercase tracking-[0.1em] text-gray-500 mb-1">Diagram</div>
                      <pre className="rounded-lg border border-gray-800 bg-black/50 p-3 text-[11px] text-gray-300 overflow-x-auto font-mono">
                        {stripFence(task.diagram)}
                      </pre>
                    </div>
                  )}
                </div>
              )}
            </div>
          )
        })}
      </div>
    </div>
  )
}
