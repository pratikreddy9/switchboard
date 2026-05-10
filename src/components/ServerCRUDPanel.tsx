import React, { useState } from 'react'
import { Server, Plus, Pencil, Trash2, ChevronDown, ChevronRight, Save } from 'lucide-react'
import { createServer, updateServer, deleteServer } from '../api/client'
import { isApiError } from '../types/switchboard'
import type { ServerRecord, Workspace } from '../types/switchboard'

interface Props {
  servers: ServerRecord[]
  companies: Workspace[]
  offline: boolean
  onReload: () => void
}

export function ServerCRUDPanel({ servers, companies, offline, onReload }: Props) {
  const [expanded, setExpanded] = useState(false)
  const [adding, setAdding] = useState(false)
  const [editingId, setEditingId] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  const [draftId, setDraftId] = useState('')
  const [draftName, setDraftName] = useState('')
  const [draftHost, setDraftHost] = useState('')
  const [draftPort, setDraftPort] = useState<number | ''>('')
  const [draftUser, setDraftUser] = useState('')
  const [draftConnType, setDraftConnType] = useState<'local' | 'ssh'>('ssh')
  const [draftCompanyId, setDraftCompanyId] = useState('')
  const [draftDeploymentMode, setDraftDeploymentMode] = useState<'native_agent' | 'local_bundle_only'>('native_agent')
  const [draftVpnRequired, setDraftVpnRequired] = useState(false)
  const [draftPassword, setDraftPassword] = useState('')
  const [draftNotes, setDraftNotes] = useState('')

  function startAdd() {
    setAdding(true)
    setEditingId(null)
    setDraftId('')
    setDraftName('')
    setDraftHost('')
    setDraftPort('')
    setDraftUser('')
    setDraftConnType('ssh')
    setDraftCompanyId(companies[0]?.workspace_id ?? '')
    setDraftDeploymentMode('native_agent')
    setDraftVpnRequired(false)
    setDraftPassword('')
    setDraftNotes('')
    setError(null)
  }

  function startEdit(s: ServerRecord) {
    setAdding(false)
    setEditingId(s.server_id)
    setDraftId(s.server_id)
    setDraftName(s.name || '')
    setDraftHost(s.host || '')
    setDraftPort(s.port || '')
    setDraftUser(s.username || '')
    setDraftConnType(s.connection_type || 'ssh')
    setDraftCompanyId(s.company_id || '')
    setDraftDeploymentMode(s.deployment_mode || 'native_agent')
    setDraftVpnRequired(Boolean(s.vpn_required))
    setDraftPassword('')
    setDraftNotes(s.notes || '')
    setError(null)
  }

  function cancel() {
    setAdding(false)
    setEditingId(null)
    setError(null)
  }

  async function handleSave() {
    if (!draftId) {
      setError('Server ID is required.')
      return
    }
    setError(null)
    if (adding) {
      const res = await createServer({
        server_id: draftId,
        company_id: draftCompanyId || undefined,
        name: draftName,
        connection_type: draftConnType,
        host: draftHost || undefined,
        username: draftUser || undefined,
        port: draftPort || undefined,
        deployment_mode: draftDeploymentMode,
        vpn_required: draftVpnRequired,
        tags: [],
        notes: draftNotes,
        local_password: draftPassword || undefined,
      })
      if (isApiError(res)) {
        setError(res.message)
      } else {
        setAdding(false)
        onReload()
      }
    } else if (editingId) {
      const res = await updateServer(editingId, {
        company_id: draftCompanyId || undefined,
        name: draftName,
        host: draftHost || undefined,
        username: draftUser || undefined,
        port: draftPort || undefined,
        deployment_mode: draftDeploymentMode,
        vpn_required: draftVpnRequired,
        notes: draftNotes,
        local_password: draftPassword || undefined,
      })
      if (isApiError(res)) {
        setError(res.message)
      } else {
        setEditingId(null)
        onReload()
      }
    }
  }

  async function handleDelete(id: string) {
    if (!confirm('Are you sure you want to delete this server?')) return
    const res = await deleteServer(id)
    if (isApiError(res)) {
      setError(res.message)
    } else {
      onReload()
    }
  }

  return (
    <div className="rounded-xl border border-gray-800 bg-gray-900 mb-6">
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full flex items-center justify-between p-4 focus:outline-none"
      >
        <div className="flex items-center gap-2 text-sm font-medium text-gray-300">
          <Server className="h-4 w-4 text-cyan-400" />
          Servers Inventory
        </div>
        {expanded ? <ChevronDown className="h-4 w-4 text-gray-500" /> : <ChevronRight className="h-4 w-4 text-gray-500" />}
      </button>

      {expanded && (
        <div className="border-t border-gray-800 p-4">
          <div className="flex justify-between items-center mb-4">
            <p className="text-xs text-gray-500">
              Manage company-owned deployment targets. Passwords stay local-only in <code>.env.local</code>.
            </p>
            {!offline && !adding && !editingId && (
              <button
                onClick={startAdd}
                className="flex items-center gap-1 bg-gray-800 hover:bg-gray-700 text-gray-200 border border-gray-700 text-xs px-3 py-1.5 rounded-lg transition-colors"
              >
                <Plus className="h-3 w-3" /> Add Server
              </button>
            )}
          </div>

          {error && <div className="mb-4 text-xs text-red-400 bg-red-950/30 p-2 rounded">{error}</div>}

          {(adding || editingId) && (
            <div className="mb-6 bg-gray-950 border border-gray-800 p-4 rounded-xl">
              <h4 className="text-sm font-medium text-gray-300 mb-3">{adding ? 'Add Server' : 'Edit Server'}</h4>
              <div className="grid gap-3 md:grid-cols-2">
                <div>
                  <label className="block text-xs text-gray-500 mb-1">Server ID</label>
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
                  <label className="block text-xs text-gray-500 mb-1">Company</label>
                  <select
                    value={draftCompanyId}
                    onChange={e => setDraftCompanyId(e.target.value)}
                    className="w-full bg-gray-900 border border-gray-800 rounded px-2 py-1.5 text-sm text-gray-200 focus:outline-none focus:border-cyan-500"
                  >
                    <option value="">Unassigned</option>
                    {companies.map(company => (
                      <option key={company.workspace_id} value={company.workspace_id}>{company.display_name}</option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="block text-xs text-gray-500 mb-1">Connection Type</label>
                  <select
                    value={draftConnType}
                    onChange={e => setDraftConnType(e.target.value as 'local' | 'ssh')}
                    disabled={!adding}
                    className="w-full bg-gray-900 border border-gray-800 rounded px-2 py-1.5 text-sm text-gray-200 focus:outline-none focus:border-cyan-500 disabled:opacity-50"
                  >
                    <option value="ssh">SSH</option>
                    <option value="local">Local</option>
                  </select>
                </div>
                <div>
                  <label className="block text-xs text-gray-500 mb-1">Host</label>
                  <input
                    value={draftHost}
                    onChange={e => setDraftHost(e.target.value)}
                    className="w-full bg-gray-900 border border-gray-800 rounded px-2 py-1.5 text-sm text-gray-200 focus:outline-none focus:border-cyan-500"
                  />
                </div>
                <div>
                  <label className="block text-xs text-gray-500 mb-1">Username</label>
                  <input
                    value={draftUser}
                    onChange={e => setDraftUser(e.target.value)}
                    className="w-full bg-gray-900 border border-gray-800 rounded px-2 py-1.5 text-sm text-gray-200 focus:outline-none focus:border-cyan-500"
                  />
                </div>
                <div>
                  <label className="block text-xs text-gray-500 mb-1">Port</label>
                  <input
                    type="number"
                    value={draftPort}
                    onChange={e => setDraftPort(e.target.value ? parseInt(e.target.value) : '')}
                    className="w-full bg-gray-900 border border-gray-800 rounded px-2 py-1.5 text-sm text-gray-200 focus:outline-none focus:border-cyan-500"
                  />
                </div>
                <div>
                  <label className="block text-xs text-gray-500 mb-1">Agent Deploy Mode</label>
                  <select
                    value={draftDeploymentMode}
                    onChange={e => setDraftDeploymentMode(e.target.value as 'native_agent' | 'local_bundle_only')}
                    className="w-full bg-gray-900 border border-gray-800 rounded px-2 py-1.5 text-sm text-gray-200 focus:outline-none focus:border-cyan-500"
                  >
                    <option value="native_agent">Native agent allowed</option>
                    <option value="local_bundle_only">Work locally, ship bundles</option>
                  </select>
                </div>
                <div>
                  <label className="block text-xs text-gray-500 mb-1">Local-only Password</label>
                  <input
                    type="password"
                    value={draftPassword}
                    onChange={e => setDraftPassword(e.target.value)}
                    placeholder={adding ? 'Optional' : 'Leave blank to keep unchanged'}
                    className="w-full bg-gray-900 border border-gray-800 rounded px-2 py-1.5 text-sm text-gray-200 focus:outline-none focus:border-cyan-500"
                  />
                </div>
                <label className="md:col-span-2 flex items-center gap-3 rounded border border-gray-800 bg-gray-900 px-3 py-2 text-sm text-gray-300">
                  <input
                    type="checkbox"
                    checked={draftVpnRequired}
                    onChange={e => setDraftVpnRequired(e.target.checked)}
                    className="h-4 w-4 rounded border-gray-600 bg-gray-950 text-cyan-500 focus:ring-cyan-500"
                  />
                  This server requires VPN before any activity.
                </label>
                <div className="md:col-span-2">
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

          {servers.length === 0 && !adding ? (
            <div className="text-xs text-gray-600 italic">No servers found.</div>
          ) : (
            <div className="grid gap-3 md:grid-cols-2 lg:grid-cols-3">
              {servers.map(s => (
                <div key={s.server_id} className="border border-gray-800 bg-gray-950 rounded-xl p-3">
                  <div className="flex items-center justify-between mb-2">
                    <div>
                  <div className="text-sm font-medium text-gray-200">{s.name || s.server_id}</div>
                  <div className="text-[10px] text-gray-500 font-mono mt-0.5">{s.server_id}</div>
                </div>
                    {!offline && (
                      <div className="flex gap-2">
                        <button onClick={() => startEdit(s)} className="p-1 text-gray-500 hover:text-cyan-400 transition-colors"><Pencil className="h-3.5 w-3.5" /></button>
                        <button onClick={() => handleDelete(s.server_id)} className="p-1 text-gray-500 hover:text-red-400 transition-colors"><Trash2 className="h-3.5 w-3.5" /></button>
                      </div>
                    )}
                  </div>
                  <div className="text-xs text-gray-400 space-y-0.5">
                    <div>Company: <span className="text-gray-300">{companies.find(company => company.workspace_id === s.company_id)?.display_name || s.company_id || 'Unassigned'}</span></div>
                    <div>Type: <span className="text-gray-300">{s.connection_type}</span></div>
                    <div>Deploy: <span className="text-gray-300">{s.deployment_mode === 'local_bundle_only' ? 'Local bundle only' : 'Native agent allowed'}</span></div>
                    <div>VPN: <span className={s.vpn_required ? 'text-amber-300' : 'text-gray-300'}>{s.vpn_required ? 'Required before actions' : 'Not required'}</span></div>
                    {s.connection_type === 'ssh' && (
                      <div>Connect: <span className="font-mono text-gray-300">{s.username ? `${s.username}@` : ''}{s.host}{s.port ? `:${s.port}` : ''}</span></div>
                    )}
                  </div>
                  {s.notes && <div className="mt-2 pt-2 border-t border-gray-800 text-xs text-gray-500">{s.notes}</div>}
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  )
}
