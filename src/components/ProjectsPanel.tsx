import React, { useEffect, useState } from 'react'
import { FolderGit2, Plus, Pencil, Trash2, ChevronDown, ChevronRight, X, Save } from 'lucide-react'
import { listProjects, createProject, updateProject, deleteProject } from '../api/client'
import { isApiError } from '../types/switchboard'
import type { ProjectManifest } from '../types/switchboard'

interface Props {
  workspaceId: string
  offline: boolean
}

export function ProjectsPanel({ workspaceId, offline }: Props) {
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
    setError(null)
  }

  function startEdit(p: ProjectManifest) {
    setAdding(false)
    setEditingId(p.project_id)
    setDraftId(p.project_id)
    setDraftName(p.display_name)
    setDraftParent(p.parent_project_id || '')
    setDraftNotes(p.notes || '')
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
        notes: draftNotes,
        tags: [],
      })
      if (isApiError(res)) {
        setError(res.message)
      } else {
        setAdding(false)
        load()
      }
    } else if (editingId) {
      const res = await updateProject(editingId, {
        display_name: draftName,
        parent_project_id: draftParent || undefined,
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

  return (
    <div className="rounded-xl border border-gray-800 bg-gray-900 mb-6">
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full flex items-center justify-between p-4 focus:outline-none"
      >
        <div className="flex items-center gap-2 text-sm font-medium text-gray-300">
          <FolderGit2 className="h-4 w-4 text-cyan-400" />
          Projects hierarchy
        </div>
        {expanded ? <ChevronDown className="h-4 w-4 text-gray-500" /> : <ChevronRight className="h-4 w-4 text-gray-500" />}
      </button>

      {expanded && (
        <div className="border-t border-gray-800 p-4">
          <div className="flex justify-between items-center mb-4">
            <p className="text-xs text-gray-500">
              Group services logically under projects and sub-projects.
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
              {rootProjects.map(p => (
                <div key={p.project_id} className="border border-gray-800 bg-gray-950 rounded-xl overflow-hidden">
                  <div className="p-3 flex items-center justify-between bg-gray-900/50">
                    <div>
                      <div className="text-sm font-medium text-gray-200">{p.display_name}</div>
                      <div className="text-[10px] text-gray-500 font-mono mt-0.5">{p.project_id}</div>
                    </div>
                    {!offline && (
                      <div className="flex gap-2">
                        <button onClick={() => startEdit(p)} className="p-1 text-gray-500 hover:text-cyan-400 transition-colors"><Pencil className="h-3.5 w-3.5" /></button>
                        <button onClick={() => handleDelete(p.project_id)} className="p-1 text-gray-500 hover:text-red-400 transition-colors"><Trash2 className="h-3.5 w-3.5" /></button>
                      </div>
                    )}
                  </div>
                  {p.notes && <div className="px-3 pb-3 text-xs text-gray-400">{p.notes}</div>}
                  
                  {/* Sub-projects */}
                  {childProjects.filter(c => c.parent_project_id === p.project_id).length > 0 && (
                    <div className="border-t border-gray-800 bg-black/20 p-3 space-y-2">
                      {childProjects.filter(c => c.parent_project_id === p.project_id).map(c => (
                        <div key={c.project_id} className="flex items-center justify-between p-2 rounded border border-gray-800 bg-gray-900/30">
                          <div>
                            <div className="text-xs font-medium text-gray-300">{c.display_name}</div>
                            <div className="text-[9px] text-gray-600 font-mono mt-0.5">{c.project_id}</div>
                          </div>
                          {!offline && (
                            <div className="flex gap-2">
                              <button onClick={() => startEdit(c)} className="p-1 text-gray-500 hover:text-cyan-400 transition-colors"><Pencil className="h-3 w-3" /></button>
                              <button onClick={() => handleDelete(c.project_id)} className="p-1 text-gray-500 hover:text-red-400 transition-colors"><Trash2 className="h-3 w-3" /></button>
                            </div>
                          )}
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  )
}