import { useEffect, useMemo, useState } from 'react'
import { ArrowLeft, Copy, Play, Plus, RefreshCw, Save, Trash2, ArrowUp, ArrowDown } from 'lucide-react'
import {
  createApiFlow,
  deleteApiFlow,
  getEnvironmentLab,
  listProjects,
  refreshEnvironmentRuntimeSnapshot,
  runApiFlow,
  updateApiFlow,
} from '../api/client'
import { AccordionSection } from '../components/AccordionSection'
import { ConfirmationModal } from '../components/ConfirmationModal'
import { StatusBadge } from '../components/StatusBadge'
import { isApiError } from '../types/switchboard'
import type { ApiFlowManifest, ApiFlowStep, EnvironmentLabView, ProjectEnvironmentView } from '../types/switchboard'

interface Props {
  environmentId: string
  offline: boolean
  onBack: () => void
  onSelectEnvironment: (environmentId: string) => void
}

function blankStep(order: number): ApiFlowStep {
  return {
    step_id: `step_${order + 1}`,
    order,
    display_name: `Step ${order + 1}`,
    method: 'GET',
    path: '',
    query: {},
    headers: {},
    body: '',
    expected_status: 200,
    continue_on_failure: false,
    timeout_seconds: 15,
    notes: '',
    captures: [],
  }
}

function blankFlow(environmentId: string): ApiFlowManifest {
  return {
    flow_id: '',
    environment_id: environmentId,
    service_id: '',
    display_name: '',
    target_kind: 'service',
    target_name: '',
    base_url: '',
    execution_mode: 'http',
    enabled: true,
    tags: [],
    notes: '',
    steps: [blankStep(0)],
  }
}

type StepRow = {
  key: string
  value: string
}

type CaptureRow = {
  variable_name: string
  source: 'json' | 'header'
  selector: string
}

function rowsFromRecord(record: Record<string, string>): StepRow[] {
  const entries = Object.entries(record)
  return entries.length > 0 ? entries.map(([key, value]) => ({ key, value })) : [{ key: '', value: '' }]
}

function rowsToRecord(rows: StepRow[]): Record<string, string> {
  return Object.fromEntries(rows.map((row) => [row.key.trim(), row.value]).filter(([key]) => key))
}

function rowsFromCaptures(captures: CaptureRow[]): CaptureRow[] {
  return captures.length > 0 ? captures.map((capture) => ({ ...capture })) : [{ variable_name: '', source: 'json', selector: '' }]
}

function storageKey(environmentId: string, section: string) {
  return `env-lab:${environmentId}:${section}`
}

function swapIndexedState<T>(state: Record<number, T>, left: number, right: number) {
  const next = { ...state }
  const leftValue = next[left]
  next[left] = next[right]
  next[right] = leftValue
  return next
}

function removeIndexedState<T>(state: Record<number, T>, removed: number) {
  const next: Record<number, T> = {}
  Object.entries(state).forEach(([key, value]) => {
    const index = Number(key)
    if (index === removed) return
    next[index > removed ? index - 1 : index] = value
  })
  return next
}

function swapIndexedCaptureState(state: Record<number, CaptureRow[]>, left: number, right: number) {
  return swapIndexedState(state, left, right)
}

function removeIndexedCaptureState(state: Record<number, CaptureRow[]>, removed: number) {
  return removeIndexedState(state, removed)
}

export function EnvironmentApiLabPage({ environmentId, offline, onBack, onSelectEnvironment }: Props) {
  const [lab, setLab] = useState<EnvironmentLabView | null>(null)
  const [projectEnvironments, setProjectEnvironments] = useState<ProjectEnvironmentView[]>([])
  const [message, setMessage] = useState<string>('')
  const [snapshotLoading, setSnapshotLoading] = useState(false)
  const [confirmSnapshotOpen, setConfirmSnapshotOpen] = useState(false)
  const [editingFlowId, setEditingFlowId] = useState<string | null>(null)
  const [flowDraft, setFlowDraft] = useState<ApiFlowManifest | null>(null)
  const [runningFlowId, setRunningFlowId] = useState<string | null>(null)
  const [confirmRunFlowId, setConfirmRunFlowId] = useState<string | null>(null)
  const [openRuns, setOpenRuns] = useState<Record<string, boolean>>({})
  const [openFlows, setOpenFlows] = useState<Record<string, boolean>>({})
  const [stepHeaders, setStepHeaders] = useState<Record<number, StepRow[]>>({})
  const [stepQueries, setStepQueries] = useState<Record<number, StepRow[]>>({})
  const [stepCaptures, setStepCaptures] = useState<Record<number, CaptureRow[]>>({})
  const [sections, setSections] = useState({
    runtime: true,
    flows: true,
    history: false,
    dependencies: false,
    pull: false,
    commands: false,
  })

  useEffect(() => {
    setSections({
      runtime: sessionStorage.getItem(storageKey(environmentId, 'runtime')) !== 'false',
      flows: sessionStorage.getItem(storageKey(environmentId, 'flows')) !== 'false',
      history: sessionStorage.getItem(storageKey(environmentId, 'history')) === 'true',
      dependencies: sessionStorage.getItem(storageKey(environmentId, 'dependencies')) === 'true',
      pull: sessionStorage.getItem(storageKey(environmentId, 'pull')) === 'true',
      commands: sessionStorage.getItem(storageKey(environmentId, 'commands')) === 'true',
    })
  }, [environmentId])

  async function loadLab(targetEnvironmentId: string) {
    const result = await getEnvironmentLab(targetEnvironmentId)
    if (isApiError(result)) {
      setMessage(result.message)
      return
    }
    setLab(result)
    setFlowDraft(null)
    setEditingFlowId(null)
    setMessage('')
    const projectList = await listProjects(result.project.workspace_id)
    if (!isApiError(projectList)) {
      setProjectEnvironments((projectList.environments ?? []).filter((entry) => entry.project_id === result.project.project_id))
    }
  }

  useEffect(() => {
    if (offline) return
    void loadLab(environmentId)
  }, [environmentId, offline])

  const runtimeSummary = useMemo(() => {
    if (!lab?.runtime_snapshot) return 'No runtime snapshot captured yet'
    return `${lab.runtime_snapshot.open_ports.length} open ports · ${lab.runtime_snapshot.exposed_ports.length} exposed · firewall ${lab.runtime_snapshot.firewall_status}`
  }, [lab?.runtime_snapshot])

  const environmentsByKind = useMemo(() => {
    return projectEnvironments.reduce<Record<string, ProjectEnvironmentView[]>>((acc, environment) => {
      const key = environment.kind || 'custom'
      acc[key] = [...(acc[key] ?? []), environment]
      return acc
    }, {})
  }, [projectEnvironments])

  async function handleRefreshSnapshot() {
    if (!lab) return
    setConfirmSnapshotOpen(false)
    setSnapshotLoading(true)
    const result = await refreshEnvironmentRuntimeSnapshot(lab.environment.environment_id)
    setSnapshotLoading(false)
    if (isApiError(result)) {
      setMessage(result.message)
      return
    }
    setLab((current) => (current ? { ...current, runtime_snapshot: result } : current))
    setMessage('Runtime snapshot refreshed.')
  }

  function beginCreateFlow() {
    setEditingFlowId('new')
    const next = blankFlow(environmentId)
    setFlowDraft(next)
    setStepHeaders({ 0: rowsFromRecord(next.steps[0].headers) })
    setStepQueries({ 0: rowsFromRecord(next.steps[0].query) })
    setStepCaptures({ 0: rowsFromCaptures(next.steps[0].captures) })
  }

  function beginEditFlow(flow: ApiFlowManifest) {
    setEditingFlowId(flow.flow_id)
    const next = {
      ...flow,
      tags: [...flow.tags],
      steps: flow.steps.map((step) => ({
        ...step,
        query: { ...step.query },
        headers: { ...step.headers },
        captures: step.captures.map((capture) => ({ ...capture })),
      })),
    }
    setFlowDraft(next)
    setStepHeaders(Object.fromEntries(next.steps.map((step, index) => [index, rowsFromRecord(step.headers)])))
    setStepQueries(Object.fromEntries(next.steps.map((step, index) => [index, rowsFromRecord(step.query)])))
    setStepCaptures(Object.fromEntries(next.steps.map((step, index) => [index, rowsFromCaptures(step.captures)])))
  }

  function cancelFlowEdit() {
    setEditingFlowId(null)
    setFlowDraft(null)
    setStepHeaders({})
    setStepQueries({})
    setStepCaptures({})
  }

  async function saveFlow() {
    if (!flowDraft || !lab) return
    if (!flowDraft.flow_id.trim() || !flowDraft.display_name.trim()) {
      setMessage('Flow ID and display name are required.')
      return
    }
    const payload = {
      ...flowDraft,
      tags: flowDraft.tags.filter(Boolean),
      steps: flowDraft.steps.map((step, index) => ({
        ...step,
        order: index,
        headers: rowsToRecord(stepHeaders[index] ?? rowsFromRecord(step.headers)),
        query: rowsToRecord(stepQueries[index] ?? rowsFromRecord(step.query)),
        captures: (stepCaptures[index] ?? rowsFromCaptures(step.captures))
          .map((capture) => ({
            variable_name: capture.variable_name.trim(),
            source: capture.source,
            selector: capture.selector.trim(),
          }))
          .filter((capture) => capture.variable_name && capture.selector),
      })),
    }
    const result =
      editingFlowId === 'new'
        ? await createApiFlow(lab.environment.environment_id, payload)
        : await updateApiFlow(lab.environment.environment_id, editingFlowId!, payload)
    if (isApiError(result)) {
      setMessage(result.message)
      return
    }
    await loadLab(lab.environment.environment_id)
    setMessage(`Flow ${result.flow_id} saved.`)
  }

  async function removeFlow(flowId: string) {
    if (!lab || !confirm('Delete this API flow?')) return
    const result = await deleteApiFlow(lab.environment.environment_id, flowId)
    if (isApiError(result)) {
      setMessage(result.message)
      return
    }
    await loadLab(lab.environment.environment_id)
  }

  async function executeFlow(flowId: string) {
    if (!lab) return
    setRunningFlowId(flowId)
    const result = await runApiFlow(lab.environment.environment_id, flowId)
    setRunningFlowId(null)
    if (isApiError(result)) {
      setMessage(result.message)
      return
    }
    await loadLab(lab.environment.environment_id)
    setOpenRuns((current) => ({ ...current, [flowId]: true }))
    setMessage(`Flow run ${result.run_id} completed.`)
  }

  function updateDraftStep(index: number, patch: Partial<ApiFlowStep>) {
    setFlowDraft((current) =>
      current
        ? {
            ...current,
            steps: current.steps.map((step, stepIndex) =>
              stepIndex === index ? { ...step, ...patch } : step,
            ),
          }
        : current,
    )
  }

  function updateSection(section: keyof typeof sections) {
    setSections((current) => {
      const next = { ...current, [section]: !current[section] }
      sessionStorage.setItem(storageKey(environmentId, section), String(next[section]))
      return next
    })
  }

  function updateRowState(
    setter: typeof setStepHeaders,
    index: number,
    rowIndex: number,
    patch: Partial<StepRow>,
  ) {
    setter((current) => ({
      ...current,
      [index]: (current[index] ?? [{ key: '', value: '' }]).map((row, idx) =>
        idx === rowIndex ? { ...row, ...patch } : row,
      ),
    }))
  }

  function addRow(
    setter: typeof setStepHeaders,
    index: number,
  ) {
    setter((current) => ({
      ...current,
      [index]: [...(current[index] ?? [{ key: '', value: '' }]), { key: '', value: '' }],
    }))
  }

  function removeRow(
    setter: typeof setStepHeaders,
    index: number,
    rowIndex: number,
  ) {
    setter((current) => {
      const nextRows = (current[index] ?? [{ key: '', value: '' }]).filter((_, idx) => idx !== rowIndex)
      return { ...current, [index]: nextRows.length > 0 ? nextRows : [{ key: '', value: '' }] }
    })
  }

  function updateCaptureRow(index: number, rowIndex: number, patch: Partial<CaptureRow>) {
    setStepCaptures((current) => ({
      ...current,
      [index]: (current[index] ?? rowsFromCaptures([])).map((row, idx) =>
        idx === rowIndex ? { ...row, ...patch } : row,
      ),
    }))
  }

  function addCaptureRow(index: number) {
    setStepCaptures((current) => ({
      ...current,
      [index]: [...(current[index] ?? rowsFromCaptures([])), { variable_name: '', source: 'json', selector: '' }],
    }))
  }

  function removeCaptureRow(index: number, rowIndex: number) {
    setStepCaptures((current) => {
      const nextRows = (current[index] ?? rowsFromCaptures([])).filter((_, idx) => idx !== rowIndex)
      return { ...current, [index]: nextRows.length > 0 ? nextRows : rowsFromCaptures([]) }
    })
  }

  function moveStep(index: number, direction: -1 | 1) {
    setFlowDraft((current) => {
      if (!current) return current
      const nextIndex = index + direction
      if (nextIndex < 0 || nextIndex >= current.steps.length) return current
      const nextSteps = [...current.steps]
      ;[nextSteps[index], nextSteps[nextIndex]] = [nextSteps[nextIndex], nextSteps[index]]
      return { ...current, steps: nextSteps.map((step, idx) => ({ ...step, order: idx })) }
    })
    setStepHeaders((current) => swapIndexedState(current, index, index + direction))
    setStepQueries((current) => swapIndexedState(current, index, index + direction))
    setStepCaptures((current) => swapIndexedCaptureState(current, index, index + direction))
  }

  function removeStep(index: number) {
    setFlowDraft((current) => {
      if (!current || current.steps.length === 1) return current
      return {
        ...current,
        steps: current.steps.filter((_, idx) => idx !== index).map((step, idx) => ({ ...step, order: idx })),
      }
    })
    setStepHeaders((current) => removeIndexedState(current, index))
    setStepQueries((current) => removeIndexedState(current, index))
    setStepCaptures((current) => removeIndexedCaptureState(current, index))
  }

  function duplicateFlow(flow: ApiFlowManifest) {
    const copyId = `${flow.flow_id}_copy`
    beginEditFlow({
      ...flow,
      flow_id: copyId,
      display_name: `${flow.display_name} Copy`,
    })
    setEditingFlowId('new')
  }

  function buildFlowCurlScript(flow: ApiFlowManifest) {
    return flow.steps
      .map((step) => {
        const query = Object.keys(step.query).length > 0 ? `?${new URLSearchParams(step.query).toString()}` : ''
        const parts = [`curl -X ${step.method} '${flow.base_url}${step.path}${query}'`]
        Object.entries(step.headers).forEach(([key, value]) => parts.push(`-H '${key}: ${value}'`))
        if (step.body) parts.push(`--data '${step.body.replace(/'/g, `'\"'\"'`)}'`)
        return parts.join(' ')
      })
      .join('\n')
  }

  if (!lab) {
    return <div className="text-sm text-gray-500">{offline ? 'Offline.' : 'Loading API lab…'}</div>
  }

  return (
    <div>
      <div className="mb-6 flex flex-col gap-4 md:flex-row md:items-start md:justify-between">
        <div className="flex items-start gap-3">
          <button onClick={onBack} className="flex items-center gap-1 text-sm text-gray-400 transition-colors hover:text-white">
            <ArrowLeft className="h-4 w-4" />
            Back
          </button>
          <div>
            <div className="text-xs uppercase tracking-[0.18em] text-cyan-400">Dedicated Environment API Lab</div>
            <h2 className="mt-2 text-2xl font-semibold text-white">{lab.project.display_name} · {lab.environment.display_name}</h2>
            <div className="mt-2 flex flex-wrap items-center gap-2 text-xs text-gray-400">
              <span>{lab.environment.kind}</span>
              <span>·</span>
              <span>{lab.environment.deployments.length} deployments</span>
              <span>·</span>
              <span>{lab.environment.api_flow_count ?? lab.api_flows.length} flows</span>
            </div>
          </div>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {Object.entries(environmentsByKind).map(([kind, entries]) => (
            <div key={kind} className="flex items-center gap-2 rounded-xl border border-gray-800 bg-gray-900/60 px-2 py-2">
              <span className="px-2 text-[10px] uppercase tracking-[0.16em] text-gray-500">{kind}</span>
              {entries.map((environment) => (
                <button
                  key={environment.environment_id}
                  onClick={() => onSelectEnvironment(environment.environment_id)}
                  className={`rounded-lg border px-3 py-2 text-xs transition-colors ${
                    environment.environment_id === lab.environment.environment_id
                      ? 'border-cyan-500 bg-cyan-500/10 text-cyan-200 shadow-[0_0_0_1px_rgba(34,211,238,0.16)]'
                      : 'border-gray-700 text-gray-300 hover:border-cyan-500 hover:text-white'
                  }`}
                >
                  <div>{environment.display_name}</div>
                  <div className="mt-1 text-[10px] text-gray-500">
                    {environment.runtime_snapshot_summary?.captured_at ? 'snapshot ready' : 'no snapshot'}
                  </div>
                </button>
              ))}
            </div>
          ))}
        </div>
      </div>

      {message && <div className="mb-6 rounded-xl border border-gray-800 bg-gray-900 px-4 py-3 text-sm text-gray-300">{message}</div>}

      <div className="mb-6 grid gap-4 lg:grid-cols-4">
        <div className="rounded-xl border border-gray-800 bg-gray-900 p-4">
          <div className="text-xs uppercase tracking-[0.16em] text-gray-500">Runtime Snapshot</div>
          <div className="mt-2 text-sm text-gray-300">{runtimeSummary}</div>
        </div>
        <div className="rounded-xl border border-gray-800 bg-gray-900 p-4">
          <div className="text-xs uppercase tracking-[0.16em] text-gray-500">Pull Rollup</div>
          <div className="mt-2 text-sm text-gray-300">{lab.environment.pull_summary?.summary || 'No bundles yet.'}</div>
        </div>
        <div className="rounded-xl border border-gray-800 bg-gray-900 p-4">
          <div className="text-xs uppercase tracking-[0.16em] text-gray-500">Dependencies</div>
          <div className="mt-2 text-sm text-gray-300">
            {lab.environment.dependency_summary?.dependencies.length ?? 0} direct · {lab.environment.dependency_summary?.cross_dependencies.length ?? 0} cross
          </div>
        </div>
        <div className="rounded-xl border border-gray-800 bg-gray-900 p-4">
          <div className="text-xs uppercase tracking-[0.16em] text-gray-500">Execution Modes</div>
          <div className="mt-2 flex flex-wrap gap-2">
            {lab.environment.service_summaries?.map((summary) => (
              <span key={`${summary.service_id}:${summary.location_id ?? ''}`} className="rounded-full border border-gray-700 px-2 py-1 text-xs text-gray-300">
                {summary.display_name}: {summary.execution_mode}
              </span>
            ))}
          </div>
        </div>
      </div>

      <AccordionSection
        title="Runtime Snapshot"
        open={sections.runtime}
        onToggle={() => updateSection('runtime')}
        summary={runtimeSummary}
      >
        <div className="mb-4 flex justify-end">
          <button
            onClick={() => setConfirmSnapshotOpen(true)}
            disabled={offline || snapshotLoading}
            className="inline-flex items-center gap-2 rounded-lg border border-gray-700 px-3 py-2 text-sm text-gray-200 transition-colors hover:border-cyan-500 hover:text-white disabled:opacity-50"
          >
            <RefreshCw className={`h-4 w-4 ${snapshotLoading ? 'animate-spin' : ''}`} />
            {snapshotLoading ? 'Refreshing…' : 'Runtime Snapshot'}
          </button>
        </div>
        {lab.runtime_snapshot ? (
          <div className="space-y-4">
            {lab.runtime_snapshot.locations.map((location) => (
              <div key={`${location.service_id}:${location.location_id}`} className="rounded-xl border border-gray-800 bg-gray-950 p-4">
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div>
                    <div className="text-sm font-medium text-white">{location.service_name}</div>
                    <div className="mt-1 font-mono text-xs text-gray-500">{location.root}</div>
                    <div className="mt-2 flex flex-wrap gap-2 text-[10px] uppercase tracking-[0.14em]">
                      <span className="rounded-full border border-gray-700 px-2 py-1 text-gray-300">{location.server_id}</span>
                      <span className="rounded-full border border-gray-700 px-2 py-1 text-gray-300">{location.execution_mode}</span>
                      <span className="rounded-full border border-gray-700 px-2 py-1 text-gray-300">firewall {location.firewall_status}</span>
                    </div>
                  </div>
                  <div className="text-right text-xs text-gray-400">
                    <div>open: {location.open_ports.join(', ') || 'none'}</div>
                    <div>unexpected: {location.unexpected_ports.join(', ') || 'none'}</div>
                  </div>
                </div>
                {(location.exposed_ports.length > 0 || location.operator_commands.length > 0) && (
                  <div className="mt-3 grid gap-3 lg:grid-cols-2">
                    <div className="rounded-lg border border-gray-800 bg-gray-900/50 p-3">
                      <div className="text-xs uppercase tracking-[0.16em] text-gray-500">Exposure</div>
                      <div className="mt-2 space-y-1">
                        {location.exposed_ports.length === 0 ? (
                          <div className="text-xs text-gray-500">No exposures found.</div>
                        ) : (
                          location.exposed_ports.map((entry, index) => (
                            <div key={index} className="text-xs text-gray-300">
                              {entry.port} · {entry.bind_address || 'unknown'} · {entry.exposure} {entry.expected ? '(expected)' : '(unexpected)'}
                            </div>
                          ))
                        )}
                      </div>
                    </div>
                    <div className="rounded-lg border border-gray-800 bg-gray-900/50 p-3">
                      <div className="text-xs uppercase tracking-[0.16em] text-gray-500">Operator Commands</div>
                      <div className="mt-2 space-y-2">
                        {location.operator_commands.map((command, index) => (
                          <div key={index} className="rounded border border-gray-800 px-2 py-2">
                            <div className="text-[11px] uppercase tracking-[0.14em] text-gray-500">{command.label}</div>
                            <pre className="mt-1 overflow-x-auto text-xs text-cyan-200">{command.command}</pre>
                          </div>
                        ))}
                      </div>
                    </div>
                  </div>
                )}
              </div>
            ))}
          </div>
        ) : (
          <div className="text-sm text-gray-500">No runtime snapshot captured yet.</div>
        )}
      </AccordionSection>

      <AccordionSection
        title="API Flows"
        open={sections.flows}
        onToggle={() => updateSection('flows')}
        summary={`${lab.api_flows.length} saved flows`}
      >
        <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
          <div className="text-sm text-gray-500">
            Build ordered HTTP flows per environment. Steps can capture variables, carry them forward, and always generate matching curl commands.
          </div>
          <button onClick={beginCreateFlow} className="inline-flex items-center gap-2 rounded-lg bg-white px-3 py-2 text-sm font-medium text-black transition-colors hover:bg-gray-200">
            <Plus className="h-4 w-4" />
            Add Flow
          </button>
        </div>

        {flowDraft && (
          <div className="mb-6 rounded-xl border border-cyan-900/30 bg-gray-950 p-4">
            <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
              <div>
                <div className="text-sm font-medium text-white">{editingFlowId === 'new' ? 'New API flow' : `Editing ${flowDraft.display_name || flowDraft.flow_id}`}</div>
                <div className="mt-1 text-xs text-gray-500">This editor stores flow config in the environment manifest and keeps run history separate.</div>
              </div>
              <label className="inline-flex items-center gap-2 rounded-lg border border-gray-700 px-3 py-2 text-xs text-gray-300">
                <input
                  type="checkbox"
                  checked={flowDraft.enabled}
                  onChange={(event) => setFlowDraft({ ...flowDraft, enabled: event.target.checked })}
                />
                Enabled
              </label>
            </div>

            <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
              <input value={flowDraft.flow_id} onChange={(event) => setFlowDraft({ ...flowDraft, flow_id: event.target.value })} className="rounded-lg border border-gray-700 bg-gray-900 px-3 py-2 text-sm text-white outline-none focus:border-cyan-500" placeholder="flow_id" />
              <input value={flowDraft.display_name} onChange={(event) => setFlowDraft({ ...flowDraft, display_name: event.target.value })} className="rounded-lg border border-gray-700 bg-gray-900 px-3 py-2 text-sm text-white outline-none focus:border-cyan-500" placeholder="Display name" />
              <select value={flowDraft.target_kind} onChange={(event) => setFlowDraft({ ...flowDraft, target_kind: event.target.value as ApiFlowManifest['target_kind'] })} className="rounded-lg border border-gray-700 bg-gray-900 px-3 py-2 text-sm text-white outline-none focus:border-cyan-500">
                <option value="service">service</option>
                <option value="dependency">dependency</option>
                <option value="cross_dependency">cross_dependency</option>
              </select>
              <input value={flowDraft.base_url} onChange={(event) => setFlowDraft({ ...flowDraft, base_url: event.target.value })} className="rounded-lg border border-gray-700 bg-gray-900 px-3 py-2 text-sm text-white outline-none focus:border-cyan-500 xl:col-span-2" placeholder="https://api.example.com" />
              <input value={flowDraft.service_id ?? ''} onChange={(event) => setFlowDraft({ ...flowDraft, service_id: event.target.value })} className="rounded-lg border border-gray-700 bg-gray-900 px-3 py-2 text-sm text-white outline-none focus:border-cyan-500" placeholder="service_id (optional)" />
              <input value={flowDraft.target_name} onChange={(event) => setFlowDraft({ ...flowDraft, target_name: event.target.value })} className="rounded-lg border border-gray-700 bg-gray-900 px-3 py-2 text-sm text-white outline-none focus:border-cyan-500 xl:col-span-2" placeholder="Target name or endpoint label" />
            </div>

            <input
              value={flowDraft.tags.join(', ')}
              onChange={(event) => setFlowDraft({ ...flowDraft, tags: event.target.value.split(',').map((value) => value.trim()).filter(Boolean) })}
              className="mt-3 w-full rounded-lg border border-gray-700 bg-gray-900 px-3 py-2 text-sm text-white outline-none focus:border-cyan-500"
              placeholder="auth, prod, smoke"
            />
            <textarea value={flowDraft.notes} onChange={(event) => setFlowDraft({ ...flowDraft, notes: event.target.value })} className="mt-3 min-h-20 w-full rounded-lg border border-gray-700 bg-gray-900 px-3 py-2 text-sm text-white outline-none focus:border-cyan-500" placeholder="Flow notes" />
            <div className="mt-4 space-y-3">
              {flowDraft.steps.map((step, index) => (
                <div key={`${step.step_id}:${index}`} className="rounded-lg border border-gray-800 bg-gray-900/50 p-3">
                  <div className="mb-3 flex flex-wrap items-center justify-between gap-3">
                    <div className="flex items-center gap-2">
                      <button type="button" onClick={() => moveStep(index, -1)} disabled={index === 0} className="rounded-lg border border-gray-700 p-2 text-gray-300 hover:border-cyan-500 hover:text-white disabled:opacity-40">
                        <ArrowUp className="h-3.5 w-3.5" />
                      </button>
                      <button type="button" onClick={() => moveStep(index, 1)} disabled={index === flowDraft.steps.length - 1} className="rounded-lg border border-gray-700 p-2 text-gray-300 hover:border-cyan-500 hover:text-white disabled:opacity-40">
                        <ArrowDown className="h-3.5 w-3.5" />
                      </button>
                      <span className="rounded-full border border-gray-700 px-2 py-1 text-[10px] uppercase tracking-[0.14em] text-gray-400">Step {index + 1}</span>
                    </div>
                    <button type="button" onClick={() => removeStep(index)} disabled={flowDraft.steps.length === 1} className="rounded-lg border border-red-900 px-3 py-1.5 text-xs text-red-300 hover:border-red-700 hover:text-red-200 disabled:opacity-40">
                      Remove Step
                    </button>
                  </div>

                  <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
                    <input value={step.step_id} onChange={(event) => updateDraftStep(index, { step_id: event.target.value })} className="rounded-lg border border-gray-700 bg-gray-950 px-3 py-2 text-sm text-white outline-none focus:border-cyan-500" placeholder="step_id" />
                    <input value={step.display_name} onChange={(event) => updateDraftStep(index, { display_name: event.target.value })} className="rounded-lg border border-gray-700 bg-gray-950 px-3 py-2 text-sm text-white outline-none focus:border-cyan-500" placeholder="Step name" />
                    <select value={step.method} onChange={(event) => updateDraftStep(index, { method: event.target.value as ApiFlowStep['method'] })} className="rounded-lg border border-gray-700 bg-gray-950 px-3 py-2 text-sm text-white outline-none focus:border-cyan-500">
                      {['GET', 'POST', 'PUT', 'PATCH', 'DELETE'].map((method) => <option key={method} value={method}>{method}</option>)}
                    </select>
                    <input value={step.expected_status} onChange={(event) => updateDraftStep(index, { expected_status: Number(event.target.value) || 200 })} className="rounded-lg border border-gray-700 bg-gray-950 px-3 py-2 text-sm text-white outline-none focus:border-cyan-500" placeholder="200" />
                    <input value={step.path} onChange={(event) => updateDraftStep(index, { path: event.target.value })} className="rounded-lg border border-gray-700 bg-gray-950 px-3 py-2 text-sm text-white outline-none focus:border-cyan-500 xl:col-span-2" placeholder="/v1/health or /v1/auth" />
                    <input value={step.timeout_seconds} onChange={(event) => updateDraftStep(index, { timeout_seconds: Number(event.target.value) || 15 })} className="rounded-lg border border-gray-700 bg-gray-950 px-3 py-2 text-sm text-white outline-none focus:border-cyan-500" placeholder="15" />
                    <label className="inline-flex items-center gap-2 rounded-lg border border-gray-700 px-3 py-2 text-xs text-gray-300">
                      <input
                        type="checkbox"
                        checked={step.continue_on_failure}
                        onChange={(event) => updateDraftStep(index, { continue_on_failure: event.target.checked })}
                      />
                      Continue on failure
                    </label>
                  </div>
                  <div className="mt-3 grid gap-3 xl:grid-cols-3">
                    <div className="rounded-lg border border-gray-800 bg-gray-950/70 p-3">
                      <div className="mb-2 flex items-center justify-between">
                        <div className="text-xs uppercase tracking-[0.16em] text-gray-500">Headers</div>
                        <button type="button" onClick={() => addRow(setStepHeaders, index)} className="text-xs text-cyan-300 hover:text-cyan-200">Add</button>
                      </div>
                      <div className="space-y-2">
                        {(stepHeaders[index] ?? rowsFromRecord(step.headers)).map((row, rowIndex) => (
                          <div key={`${index}:header:${rowIndex}`} className="grid grid-cols-[1fr,1fr,auto] gap-2">
                            <input value={row.key} onChange={(event) => updateRowState(setStepHeaders, index, rowIndex, { key: event.target.value })} className="rounded-lg border border-gray-700 bg-gray-900 px-2 py-2 text-xs text-white outline-none focus:border-cyan-500" placeholder="Authorization" />
                            <input value={row.value} onChange={(event) => updateRowState(setStepHeaders, index, rowIndex, { value: event.target.value })} className="rounded-lg border border-gray-700 bg-gray-900 px-2 py-2 text-xs text-white outline-none focus:border-cyan-500" placeholder="Bearer {{token}}" />
                            <button type="button" onClick={() => removeRow(setStepHeaders, index, rowIndex)} className="rounded-lg border border-gray-700 px-2 text-xs text-gray-400 hover:text-white">×</button>
                          </div>
                        ))}
                      </div>
                    </div>

                    <div className="rounded-lg border border-gray-800 bg-gray-950/70 p-3">
                      <div className="mb-2 flex items-center justify-between">
                        <div className="text-xs uppercase tracking-[0.16em] text-gray-500">Query Params</div>
                        <button type="button" onClick={() => addRow(setStepQueries, index)} className="text-xs text-cyan-300 hover:text-cyan-200">Add</button>
                      </div>
                      <div className="space-y-2">
                        {(stepQueries[index] ?? rowsFromRecord(step.query)).map((row, rowIndex) => (
                          <div key={`${index}:query:${rowIndex}`} className="grid grid-cols-[1fr,1fr,auto] gap-2">
                            <input value={row.key} onChange={(event) => updateRowState(setStepQueries, index, rowIndex, { key: event.target.value })} className="rounded-lg border border-gray-700 bg-gray-900 px-2 py-2 text-xs text-white outline-none focus:border-cyan-500" placeholder="page" />
                            <input value={row.value} onChange={(event) => updateRowState(setStepQueries, index, rowIndex, { value: event.target.value })} className="rounded-lg border border-gray-700 bg-gray-900 px-2 py-2 text-xs text-white outline-none focus:border-cyan-500" placeholder="1" />
                            <button type="button" onClick={() => removeRow(setStepQueries, index, rowIndex)} className="rounded-lg border border-gray-700 px-2 text-xs text-gray-400 hover:text-white">×</button>
                          </div>
                        ))}
                      </div>
                    </div>

                    <div className="rounded-lg border border-gray-800 bg-gray-950/70 p-3">
                      <div className="mb-2 flex items-center justify-between">
                        <div className="text-xs uppercase tracking-[0.16em] text-gray-500">Captures</div>
                        <button type="button" onClick={() => addCaptureRow(index)} className="text-xs text-cyan-300 hover:text-cyan-200">Add</button>
                      </div>
                      <div className="space-y-2">
                        {(stepCaptures[index] ?? rowsFromCaptures(step.captures)).map((row, rowIndex) => (
                          <div key={`${index}:capture:${rowIndex}`} className="grid grid-cols-[1fr,auto,1fr,auto] gap-2">
                            <input value={row.variable_name} onChange={(event) => updateCaptureRow(index, rowIndex, { variable_name: event.target.value })} className="rounded-lg border border-gray-700 bg-gray-900 px-2 py-2 text-xs text-white outline-none focus:border-cyan-500" placeholder="token" />
                            <select value={row.source} onChange={(event) => updateCaptureRow(index, rowIndex, { source: event.target.value as CaptureRow['source'] })} className="rounded-lg border border-gray-700 bg-gray-900 px-2 py-2 text-xs text-white outline-none focus:border-cyan-500">
                              <option value="json">json</option>
                              <option value="header">header</option>
                            </select>
                            <input value={row.selector} onChange={(event) => updateCaptureRow(index, rowIndex, { selector: event.target.value })} className="rounded-lg border border-gray-700 bg-gray-900 px-2 py-2 text-xs text-white outline-none focus:border-cyan-500" placeholder="data.token" />
                            <button type="button" onClick={() => removeCaptureRow(index, rowIndex)} className="rounded-lg border border-gray-700 px-2 text-xs text-gray-400 hover:text-white">×</button>
                          </div>
                        ))}
                      </div>
                    </div>
                  </div>
                  <textarea value={step.body} onChange={(event) => updateDraftStep(index, { body: event.target.value })} className="mt-3 min-h-24 w-full rounded-lg border border-gray-700 bg-gray-950 px-3 py-2 font-mono text-xs text-white outline-none focus:border-cyan-500" placeholder='{"email":"user@example.com"}' />
                  <textarea value={step.notes} onChange={(event) => updateDraftStep(index, { notes: event.target.value })} className="mt-3 min-h-20 w-full rounded-lg border border-gray-700 bg-gray-950 px-3 py-2 text-sm text-white outline-none focus:border-cyan-500" placeholder="Step notes" />
                </div>
              ))}
            </div>
            <div className="mt-4 flex justify-between">
              <button
                onClick={() => {
                  const nextStep = blankStep(flowDraft.steps.length)
                  setFlowDraft({ ...flowDraft, steps: [...flowDraft.steps, nextStep] })
                  setStepHeaders((current) => ({ ...current, [flowDraft.steps.length]: rowsFromRecord(nextStep.headers) }))
                  setStepQueries((current) => ({ ...current, [flowDraft.steps.length]: rowsFromRecord(nextStep.query) }))
                  setStepCaptures((current) => ({ ...current, [flowDraft.steps.length]: rowsFromCaptures(nextStep.captures) }))
                }}
                className="rounded-lg border border-gray-700 px-3 py-2 text-xs text-gray-300 hover:border-cyan-500 hover:text-white"
              >
                Add Step
              </button>
              <div className="flex gap-2">
                <button onClick={cancelFlowEdit} className="rounded-lg border border-gray-700 px-3 py-2 text-xs text-gray-300 hover:border-gray-500 hover:text-white">Cancel</button>
                <button onClick={saveFlow} className="inline-flex items-center gap-2 rounded-lg bg-white px-3 py-2 text-xs font-medium text-black hover:bg-gray-200">
                  <Save className="h-3.5 w-3.5" />
                  Save Flow
                </button>
              </div>
            </div>
          </div>
        )}

        <div className="space-y-3">
          {lab.api_flows.length === 0 ? (
            <div className="rounded-xl border border-dashed border-gray-800 bg-gray-950 px-4 py-6 text-sm text-gray-500">No API flows yet.</div>
          ) : (
            lab.api_flows.map((flow) => (
              <div key={flow.flow_id} className="rounded-xl border border-gray-800 bg-gray-950">
                <button onClick={() => setOpenFlows((current) => ({ ...current, [flow.flow_id]: !current[flow.flow_id] }))} className="flex w-full items-start justify-between gap-3 p-4 text-left">
                  <div>
                    <div className="text-sm font-medium text-white">{flow.display_name}</div>
                    <div className="mt-1 flex flex-wrap gap-2 text-[10px] uppercase tracking-[0.14em] text-gray-500">
                      <span>{flow.flow_id}</span>
                      <span>·</span>
                      <span>{flow.base_url || 'no base url'}</span>
                      <span>·</span>
                      <span>{flow.steps.length} steps</span>
                      <span>·</span>
                      <span>{flow.enabled ? 'enabled' : 'disabled'}</span>
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    <button onClick={(event) => { event.stopPropagation(); setConfirmRunFlowId(flow.flow_id) }} disabled={runningFlowId === flow.flow_id || !flow.enabled} className="inline-flex items-center gap-1 rounded-lg border border-gray-700 px-3 py-2 text-xs text-gray-200 hover:border-cyan-500 hover:text-white disabled:opacity-50">
                      <Play className="h-3.5 w-3.5" />
                      {runningFlowId === flow.flow_id ? 'Running…' : 'Run'}
                    </button>
                    <button onClick={(event) => { event.stopPropagation(); duplicateFlow(flow) }} className="rounded-lg border border-gray-700 px-3 py-2 text-xs text-gray-300 hover:border-cyan-500 hover:text-white">Duplicate</button>
                    <button onClick={(event) => { event.stopPropagation(); beginEditFlow(flow) }} className="rounded-lg border border-gray-700 px-3 py-2 text-xs text-gray-300 hover:border-cyan-500 hover:text-white">Edit</button>
                    <button onClick={(event) => { event.stopPropagation(); void removeFlow(flow.flow_id) }} className="rounded-lg border border-red-900 px-3 py-2 text-xs text-red-300 hover:border-red-700 hover:text-red-200">
                      <Trash2 className="h-3.5 w-3.5" />
                    </button>
                  </div>
                </button>
                {openFlows[flow.flow_id] && (
                  <div className="border-t border-gray-800 p-4">
                    <div className="grid gap-4 lg:grid-cols-2">
                      <div>
                        <div className="text-xs uppercase tracking-[0.16em] text-gray-500">Steps</div>
                        <div className="mt-2 space-y-2">
                          {flow.steps.map((step) => (
                            <div key={step.step_id} className="rounded-lg border border-gray-800 bg-gray-900/50 p-3">
                              <div className="text-sm text-gray-200">{step.order + 1}. {step.display_name}</div>
                              <div className="mt-1 text-xs text-gray-500">{step.method} {step.path}</div>
                            </div>
                          ))}
                        </div>
                      </div>
                      <div>
                        <div className="mb-2 flex items-center justify-between gap-2">
                          <div className="text-xs uppercase tracking-[0.16em] text-gray-500">Generated curl</div>
                          <button onClick={() => navigator.clipboard.writeText(buildFlowCurlScript(flow))} className="rounded-lg border border-gray-700 px-2 py-1 text-[11px] text-gray-300 hover:border-cyan-500 hover:text-white">
                            Copy full flow
                          </button>
                        </div>
                        <div className="mt-2 space-y-2">
                          {flow.steps.map((step) => (
                            <div key={`${flow.flow_id}:${step.step_id}:curl`} className="rounded-lg border border-gray-800 bg-gray-900/50 p-3">
                              <div className="flex items-center justify-between gap-2">
                                <div className="text-xs text-gray-500">{step.display_name}</div>
                                <button onClick={() => navigator.clipboard.writeText(`curl -X ${step.method} '${flow.base_url}${step.path}'`)} className="text-xs text-cyan-300 hover:text-cyan-200">
                                  <Copy className="inline h-3.5 w-3.5" />
                                </button>
                              </div>
                              <pre className="mt-2 overflow-x-auto text-xs text-cyan-200">{`curl -X ${step.method} '${flow.base_url}${step.path}'`}</pre>
                            </div>
                          ))}
                        </div>
                      </div>
                    </div>
                  </div>
                )}
              </div>
            ))
          )}
        </div>
      </AccordionSection>

      <AccordionSection
        title="Run History"
        open={sections.history}
        onToggle={() => updateSection('history')}
        summary={`${Object.values(lab.api_runs).reduce((count, runs) => count + runs.length, 0)} recorded runs`}
      >
        <div className="space-y-4">
          {lab.api_flows.map((flow) => {
            const runs = lab.api_runs[flow.flow_id] ?? []
            return (
              <div key={`${flow.flow_id}:runs`} className="rounded-xl border border-gray-800 bg-gray-950">
                <button onClick={() => setOpenRuns((current) => ({ ...current, [flow.flow_id]: !current[flow.flow_id] }))} className="flex w-full items-center justify-between gap-3 p-4 text-left">
                  <div>
                    <div className="text-sm font-medium text-white">{flow.display_name}</div>
                    <div className="mt-1 text-xs text-gray-500">{runs.length} runs</div>
                  </div>
                  {runs[0] ? <StatusBadge status={runs[0].status === 'failed' ? 'partial' : runs[0].status} /> : <span className="text-xs text-gray-600">No runs</span>}
                </button>
                {openRuns[flow.flow_id] && (
                  <div className="border-t border-gray-800 p-4">
                    {runs.length === 0 ? (
                      <div className="text-sm text-gray-500">No run history yet.</div>
                    ) : (
                      <div className="space-y-3">
                        {runs.map((run) => (
                          <div key={run.run_id} className="rounded-lg border border-gray-800 bg-gray-900/50 p-3">
                            <div className="flex items-center justify-between gap-3">
                              <div>
                                <div className="text-sm text-gray-200">{new Date(run.finished_at || run.started_at).toLocaleString()}</div>
                                <div className="mt-1 text-xs text-gray-500">{run.summary}</div>
                              </div>
                              <StatusBadge status={run.status === 'failed' ? 'partial' : run.status} />
                            </div>
                            <div className="mt-3 space-y-2">
                              {run.step_results.map((step) => (
                                <div key={`${run.run_id}:${step.step_id}`} className="rounded border border-gray-800 px-3 py-2">
                                  <div className="flex items-center justify-between gap-3">
                                    <div className="text-sm text-gray-200">{step.step_id}</div>
                                    <div className="text-xs text-gray-500">{step.duration_ms} ms · {step.response_status || 'error'}</div>
                                  </div>
                                  <div className="mt-2 text-xs text-gray-500">{step.request_preview.method} {step.request_preview.url}</div>
                                  <pre className="mt-2 overflow-x-auto text-xs text-cyan-200">{step.generated_curl}</pre>
                                  {Object.keys(step.extracted_variables).length > 0 && (
                                    <pre className="mt-2 overflow-x-auto text-xs text-emerald-200">{JSON.stringify(step.extracted_variables, null, 2)}</pre>
                                  )}
                                  {step.response_body_preview && <pre className="mt-2 overflow-x-auto text-xs text-gray-300">{step.response_body_preview}</pre>}
                                  {step.error && <div className="mt-2 text-xs text-red-300">{step.error}</div>}
                                </div>
                              ))}
                            </div>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                )}
              </div>
            )
          })}
        </div>
      </AccordionSection>

      <AccordionSection
        title="Dependencies"
        open={sections.dependencies}
        onToggle={() => updateSection('dependencies')}
        summary="Rolled up from task ledger and environment deployments"
      >
        <div className="grid gap-4 lg:grid-cols-3">
          <div className="rounded-xl border border-gray-800 bg-gray-950 p-4">
            <div className="text-xs uppercase tracking-[0.16em] text-gray-500">Composition</div>
            <div className="mt-3 flex flex-wrap gap-2 text-xs">
              {(lab.environment.dependency_summary?.composition?.language_percentages ?? []).slice(0, 4).map((item) => (
                <span key={item.name} className="rounded-full border border-gray-800 px-2 py-1 text-gray-300">
                  {item.name} {item.percentage}%
                </span>
              ))}
              <span className="rounded-full border border-cyan-900/40 bg-cyan-950/20 px-2 py-1 text-cyan-200">
                AI {lab.environment.dependency_summary?.composition?.ai_percentage ?? 0}%
              </span>
              <span className="rounded-full border border-gray-800 px-2 py-1 text-gray-300">
                LLM {lab.environment.dependency_summary?.composition?.llm_percentage ?? 0}%
              </span>
              <span className="rounded-full border border-gray-800 px-2 py-1 text-gray-300">
                Embedding {lab.environment.dependency_summary?.composition?.embedding_percentage ?? 0}%
              </span>
            </div>
            {(lab.environment.dependency_summary?.composition?.models?.length ?? 0) > 0 && (
              <div className="mt-3 text-xs text-gray-400">
                Models: {lab.environment.dependency_summary?.composition?.models?.map((model) => model.name).join(', ')}
              </div>
            )}
          </div>
          <div className="rounded-xl border border-gray-800 bg-gray-950 p-4">
            <div className="text-xs uppercase tracking-[0.16em] text-gray-500">Direct Dependencies</div>
            <div className="mt-3 space-y-2">
              {(lab.environment.dependency_summary?.dependencies ?? []).map((dependency, index) => (
                <div key={index} className="text-sm text-gray-300">{dependency.kind} · {dependency.name} · {dependency.host || 'local'}{dependency.port ? `:${dependency.port}` : ''}</div>
              ))}
            </div>
          </div>
          <div className="rounded-xl border border-gray-800 bg-gray-950 p-4">
            <div className="text-xs uppercase tracking-[0.16em] text-gray-500">Cross Dependencies</div>
            <div className="mt-3 space-y-2">
              {(lab.environment.dependency_summary?.cross_dependencies ?? []).map((dependency, index) => (
                <div key={index} className="text-sm text-gray-300">{dependency.kind} · {dependency.name} · {dependency.host || 'local'}{dependency.port ? `:${dependency.port}` : ''}</div>
              ))}
            </div>
          </div>
        </div>
      </AccordionSection>

      <AccordionSection
        title="Pull Rollup"
        open={sections.pull}
        onToggle={() => updateSection('pull')}
        summary={lab.environment.pull_summary?.summary || 'No pull rollup'}
      >
        <div className="grid gap-3 md:grid-cols-4">
          <div className="rounded-xl border border-gray-800 bg-gray-950 p-4 text-sm text-gray-300">Added: {lab.environment.pull_summary?.added_count ?? 0}</div>
          <div className="rounded-xl border border-gray-800 bg-gray-950 p-4 text-sm text-gray-300">Removed: {lab.environment.pull_summary?.removed_count ?? 0}</div>
          <div className="rounded-xl border border-gray-800 bg-gray-950 p-4 text-sm text-gray-300">Changed: {lab.environment.pull_summary?.changed_count ?? 0}</div>
          <div className="rounded-xl border border-gray-800 bg-gray-950 p-4 text-sm text-gray-300">Services: {lab.environment.pull_summary?.service_count ?? 0}</div>
        </div>
      </AccordionSection>

      <AccordionSection
        title="Operator Commands"
        open={sections.commands}
        onToggle={() => updateSection('commands')}
        summary={`${lab.runtime_snapshot?.operator_commands.length ?? 0} commands`}
      >
        <div className="space-y-2">
          {(lab.runtime_snapshot?.operator_commands ?? []).map((command, index) => (
            <div key={index} className="rounded-xl border border-gray-800 bg-gray-950 p-4">
              <div className="text-xs uppercase tracking-[0.16em] text-gray-500">{command.label}</div>
              <pre className="mt-2 overflow-x-auto text-xs text-cyan-200">{command.command}</pre>
              {command.notes && <div className="mt-2 text-sm text-gray-400">{command.notes}</div>}
            </div>
          ))}
        </div>
      </AccordionSection>

      {confirmSnapshotOpen && (
        <ConfirmationModal
          open={confirmSnapshotOpen}
          title="Refresh runtime snapshot"
          willDo={[
            'Connects to the deployment hosts for this environment.',
            'Reads listening ports, firewall state, node state, and health checks.',
            'Generates operator commands for follow-up verification.',
          ]}
          willNotChange={[
            'Does not restart processes.',
            'Does not change firewall or port bindings.',
            'Does not mutate application code or environment config.',
          ]}
          writesTo={['switchboard/state/run/']}
          onConfirm={handleRefreshSnapshot}
          onCancel={() => setConfirmSnapshotOpen(false)}
        />
      )}

      {confirmRunFlowId && (
        <ConfirmationModal
          open={Boolean(confirmRunFlowId)}
          title="Run API flow"
          willDo={[
            'Executes the saved HTTP request steps in order.',
            'Captures response previews, extracted variables, and generated curl commands.',
            'Stores a sanitized run log for this environment only.',
          ]}
          willNotChange={[
            'Does not run shell commands on servers.',
            'Does not change firewall or port bindings.',
            'Does not mutate application code or deployment files.',
          ]}
          writesTo={['switchboard/state/run/']}
          onConfirm={() => {
            const flowId = confirmRunFlowId
            setConfirmRunFlowId(null)
            if (flowId) void executeFlow(flowId)
          }}
          onCancel={() => setConfirmRunFlowId(null)}
        />
      )}
    </div>
  )
}
