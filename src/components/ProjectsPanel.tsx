import React, { useEffect, useState } from 'react'
import { FolderGit2, Plus, Pencil, Trash2, ChevronDown, ChevronRight, Save } from 'lucide-react'
import { listProjects, createProject, updateProject, deleteProject } from '../api/client'
import { isApiError } from '../types/switchboard'
import type { ProjectManifest } from '../types/switchboard'

interface Props {
  workspaceId: string
  offline: boolean
  workspaceName?: string
  workspaceNotes?: string
}

export function ProjectsPanel({ workspaceId, offline, workspaceName, workspaceNotes }: Props) {
  const [projects, setProjects] = useState<ProjectManifest[]>([])
  const [expanded, setExpanded] = useState(false)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  
  const [adding, setAdding] = useState(false)
  const [editingId, setEditingId] = useState<string | null>(null)
  const [draftId, setDraftId] = useState('')
  const [draftName, setDraftName] = useState('')
  const [draftParent, setDraftParent] = useState('')
  const [draftNotes, setDraftNotes] = useState('')
  const [draftServiceIds, setDraftServiceIds] = useState('')
  const [draftTags, setDraftTags] = useState('')
  const [openProjects, setOpenProjects] = useState<Record<string, boolean>>({})

  useEffect(() => {
    if (offline || !expanded) return
    load()
  }, [workspaceId, offline, expanded])

  async function load() {
    setLoading(true)
    const result = await listProjects(workspaceId)
    setLoading(false)
    if (!isApiError(result)) {
      setProjects(result.projects)
    }
  }

  function startAdd() {
    setAdding(true)
    setEditingId(null)
    setDraftId('')
    setDraftName('')
    setDraftParent('')
    setDraftNotes('')
    setDraftServiceIds('')
    setDraftTags('')
    setError(null)
  }

  function startEdit(p: ProjectManifest) {
    setAdding(false)
    setEditingId(p.project_id)
    setDraftId(p.project_id)
    setDraftName(p.display_name)
    setDraftParent(p.parent_project_id || '')
    setDraftNotes(p.notes || '')
    setDraftServiceIds((p.service_ids ?? []).join(', '))
    setDraftTags((p.tags ?? []).join(', '))
    setError(null)
  }

  function cancel() {
    setAdding(false)
    setEditingId(null)
    setError(null)
  }

  async function handleSave() {
    if (!draftId || !draftName) {
      setError('ID and Name are required.')
      return
    }
    setError(null)
    if (adding) {
      const res = await createProject(workspaceId, {
        project_id: draftId,
        display_name: draftName,
        parent_project_id: draftParent || undefined,
        service_ids: draftServiceIds.split(',').map((v) => v.trim()).filter(Boolean),
        tags: draftTags.split(',').map((v) => v.trim()).filter(Boolean),
        notes: draftNotes,
      })
      if (isApiError(res)) {
        setError(res.message)
      } else {
        setAdding(false)
        load()
      }
    } else if (editingId) {
      const res = await updateProject(editingId, {
        project_id: draftId,
        display_name: draftName,
        parent_project_id: draftParent || undefined,
        service_ids: draftServiceIds.split(',').map((v) => v.trim()).filter(Boolean),
        tags: draftTags.split(',').map((v) => v.trim()).filter(Boolean),
        notes: draftNotes,
      })
      if (isApiError(res)) {
        setError(res.message)
      } else {
        setEditingId(null)
        load()
      }
    }
  }

  async function handleDelete(id: string) {
    if (!confirm('Are you sure you want to delete this project?')) return
    const res = await deleteProject(id)
    if (isApiError(res)) {
      setError(res.message)
    } else {
      load()
    }
  }

  const rootProjects = projects.filter(p => !p.parent_project_id)
  const childProjects = projects.filter(p => p.parent_project_id)

  function toggleProject(projectId: string) {
    setOpenProjects((current) => ({ ...current, [projectId]: !current[projectId] }))
  }

  return (
    <div className="rounded-xl border border-gray-800 bg-gray-900 mb-6">
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full flex items-center justify-between p-4 focus:outline-none"
      >
        <div className="flex items-center gap-2 text-sm font-medium text-gray-300">
          <FolderGit2 className="h-4 w-4 text-cyan-400" />
          Projects inventory
        </div>
        {expanded ? <ChevronDown className="h-4 w-4 text-gray-500" /> : <ChevronRight className="h-4 w-4 text-gray-500" />}
      </button>

      {expanded && (
        <div className="border-t border-gray-800 p-4">
          <div className="flex justify-between items-center mb-4">
            <p className="text-xs text-gray-500">
              Group services for this company under projects and sub-projects.
            </p>
            {!offline && !adding && !editingId && (
              <button
                onClick={startAdd}
                className="flex items-center gap-1 bg-gray-800 hover:bg-gray-700 text-gray-200 border border-gray-700 text-xs px-3 py-1.5 rounded-lg transition-colors"
              >
                <Plus className="h-3 w-3" /> Add Project
              </button>
            )}
          </div>

          {error && <div className="mb-4 text-xs text-red-400 bg-red-950/30 p-2 rounded">{error}</div>}

          {(adding || editingId) && (
            <div className="mb-6 bg-gray-950 border border-gray-800 p-4 rounded-xl">
              <h4 className="text-sm font-medium text-gray-300 mb-3">{adding ? 'Add Project' : 'Edit Project'}</h4>
              <div className="grid gap-3 md:grid-cols-2">
                <div>
                  <label className="block text-xs text-gray-500 mb-1">Project ID</label>
                  <input
                    value={draftId}
                    onChange={e => setDraftId(e.target.value)}
                    disabled={!adding}
                    className="w-full bg-gray-900 border border-gray-800 rounded px-2 py-1.5 text-sm text-gray-200 focus:outline-none focus:border-cyan-500 disabled:opacity-50"
                  />
                </div>
                <div>
                  <label className="block text-xs text-gray-500 mb-1">Display Name</label>
                  <input
                    value={draftName}
                    onChange={e => setDraftName(e.target.value)}
                    className="w-full bg-gray-900 border border-gray-800 rounded px-2 py-1.5 text-sm text-gray-200 focus:outline-none focus:border-cyan-500"
                  />
                </div>
                <div>
                  <label className="block text-xs text-gray-500 mb-1">Parent Project ID (Optional)</label>
                  <input
                    value={draftParent}
                    onChange={e => setDraftParent(e.target.value)}
                    className="w-full bg-gray-900 border border-gray-800 rounded px-2 py-1.5 text-sm text-gray-200 focus:outline-none focus:border-cyan-500"
                  />
                </div>
                <div>
                  <label className="block text-xs text-gray-500 mb-1">Notes</label>
                  <input
                    value={draftNotes}
                    onChange={e => setDraftNotes(e.target.value)}
                    className="w-full bg-gray-900 border border-gray-800 rounded px-2 py-1.5 text-sm text-gray-200 focus:outline-none focus:border-cyan-500"
                  />
                </div>
                <div>
                  <label className="block text-xs text-gray-500 mb-1">Service IDs</label>
                  <input
                    value={draftServiceIds}
                    onChange={e => setDraftServiceIds(e.target.value)}
                    placeholder="aichat, sys_docs"
                    className="w-full bg-gray-900 border border-gray-800 rounded px-2 py-1.5 text-sm text-gray-200 focus:outline-none focus:border-cyan-500"
                  />
                </div>
                <div>
                  <label className="block text-xs text-gray-500 mb-1">Tags</label>
                  <input
                    value={draftTags}
                    onChange={e => setDraftTags(e.target.value)}
                    placeholder="docs, ops"
                    className="w-full bg-gray-900 border border-gray-800 rounded px-2 py-1.5 text-sm text-gray-200 focus:outline-none focus:border-cyan-500"
                  />
                </div>
              </div>
              <div className="mt-4 flex justify-end gap-2">
                <button onClick={cancel} className="px-3 py-1.5 text-xs text-gray-400 hover:text-white transition-colors">Cancel</button>
                <button onClick={handleSave} className="flex items-center gap-1 bg-cyan-600 hover:bg-cyan-500 text-white px-3 py-1.5 rounded text-xs transition-colors">
                  <Save className="h-3 w-3" /> Save
                </button>
              </div>
            </div>
          )}

          {loading && !adding && !editingId ? (
            <div className="text-xs text-gray-500">Loading...</div>
          ) : projects.length === 0 && !adding ? (
            <div className="text-xs text-gray-600 italic">No projects found.</div>
          ) : (
            <div className="space-y-4">
              <div className="border border-amber-900/40 bg-amber-950/10 rounded-xl overflow-hidden">
                <div className="p-3 flex items-center justify-between bg-amber-950/20">
                  <div>
                  <div className="text-sm font-medium text-amber-100">{workspaceName || workspaceId}</div>
                  <div className="text-[10px] text-amber-300/70 font-mono mt-0.5">{workspaceId}</div>
                </div>
                  <div className="text-[10px] uppercase tracking-[0.16em] text-amber-300">company root</div>
                </div>
                {workspaceNotes && <div className="px-3 pb-3 text-xs text-amber-100/80">{workspaceNotes}</div>}
              </div>
              {rootProjects.map(p => {
                const children = childProjects.filter(c => c.parent_project_id === p.project_id)
                const open = openProjects[p.project_id] ?? false
                return (
                  <div key={p.project_id} className="border border-gray-800 bg-gray-950 rounded-xl overflow-hidden">
                    <div className="p-3 flex items-center justify-between bg-gray-900/50">
                      <button onClick={() => toggleProject(p.project_id)} className="flex min-w-0 items-center gap-3 text-left">
                        {open ? <ChevronDown className="h-4 w-4 text-gray-500" /> : <ChevronRight className="h-4 w-4 text-gray-500" />}
                        <div>
                          <div className="text-sm font-medium text-gray-200">{p.display_name}</div>
                          <div className="mt-0.5 text-[10px] text-gray-500 font-mono">{p.project_id}</div>
                        </div>
                      </button>
                      <div className="flex items-center gap-3">
                        <div className="text-[10px] uppercase tracking-[0.14em] text-gray-500">
                          {children.length} subprojects
                        </div>
                        {!offline && (
                          <div className="flex gap-2">
                            <button onClick={() => startEdit(p)} className="p-1 text-gray-500 hover:text-cyan-400 transition-colors"><Pencil className="h-3.5 w-3.5" /></button>
                            <button onClick={() => handleDelete(p.project_id)} className="p-1 text-gray-500 hover:text-red-400 transition-colors"><Trash2 className="h-3.5 w-3.5" /></button>
                          </div>
                        )}
                      </div>
                    </div>
                    {open && (
                      <div className="border-t border-gray-800">
                        {p.notes && <div className="px-3 pt-3 text-xs text-gray-400">{p.notes}</div>}
                        <div className="px-3 py-3">
                          <div className="mb-3 grid gap-2 sm:grid-cols-3">
                            <div className="rounded border border-gray-800 bg-black/20 px-3 py-2 text-xs text-gray-400">
                              <div className="uppercase tracking-[0.14em] text-gray-600">Project ID</div>
                              <div className="mt-1 font-mono text-gray-300">{p.project_id}</div>
                            </div>
                            <div className="rounded border border-gray-800 bg-black/20 px-3 py-2 text-xs text-gray-400">
                              <div className="uppercase tracking-[0.14em] text-gray-600">Parent</div>
                              <div className="mt-1 text-gray-300">{p.parent_project_id || 'Company root'}</div>
                            </div>
                            <div className="rounded border border-gray-800 bg-black/20 px-3 py-2 text-xs text-gray-400">
                              <div className="uppercase tracking-[0.14em] text-gray-600">Services</div>
                              <div className="mt-1 text-gray-300">{p.service_ids?.length ?? 0}</div>
                            </div>
                          </div>
                          {(p.tags?.length ?? 0) > 0 && (
                            <div className="mb-3 flex flex-wrap gap-1">
                              {p.tags.map((tag) => (
                                <span key={tag} className="rounded-full border border-cyan-900/40 bg-cyan-950/30 px-2 py-0.5 text-[10px] uppercase tracking-[0.14em] text-cyan-200">
                                  {tag}
                                </span>
                              ))}
                            </div>
                          )}
                          {(p.service_ids?.length ?? 0) > 0 && (
                            <div className="mb-3 rounded border border-gray-800 bg-black/20 px-3 py-2">
                              <div className="text-[10px] uppercase tracking-[0.14em] text-gray-600">Assigned services</div>
                              <div className="mt-2 flex flex-wrap gap-1">
                                {p.service_ids.map((serviceId) => (
                                  <span key={serviceId} className="rounded border border-gray-700 px-2 py-0.5 text-[10px] font-mono text-gray-300">
                                    {serviceId}
                                  </span>
                                ))}
                              </div>
                            </div>
                          )}
                          <div className="space-y-2">
                            {children.length === 0 ? (
                              <div className="rounded border border-dashed border-gray-800 px-3 py-2 text-xs italic text-gray-600">
                                No subprojects under this project.
                              </div>
                            ) : (
                              children.map(c => (
                                <div key={c.project_id} className="flex items-center justify-between rounded border border-gray-800 bg-gray-900/30 p-2">
                                  <div>
                                    <div className="text-xs font-medium text-gray-300">{c.display_name}</div>
                                    <div className="text-[9px] text-gray-600 font-mono mt-0.5">{c.project_id}</div>
                                    {c.notes && <div className="mt-1 text-[11px] text-gray-500">{c.notes}</div>}
                                  </div>
                                  {!offline && (
                                    <div className="flex gap-2">
                                      <button onClick={() => startEdit(c)} className="p-1 text-gray-500 hover:text-cyan-400 transition-colors"><Pencil className="h-3 w-3" /></button>
                                      <button onClick={() => handleDelete(c.project_id)} className="p-1 text-gray-500 hover:text-red-400 transition-colors"><Trash2 className="h-3 w-3" /></button>
                                    </div>
                                  )}
                                </div>
                              ))
                            )}
                          </div>
                        </div>
                      </div>
                    )}
                  </div>
                )
              })}
            </div>
          )}
        </div>
      )}
    </div>
  )
}
