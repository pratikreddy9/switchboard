import type {
  ActionLock,
  CompanyCreateRequest,
  CompanyPatchRequest,
  ProjectEnvironmentCreateRequest,
  ProjectEnvironmentPatchRequest,
  ProjectEnvironmentView,
  ProjectManifest,
  ProjectPullSummary,
  ProjectCreateRequest,
  ProjectPatchRequest,
  ServerCreateRequest,
  ServerPatchRequest,
  TaskLedgerEntry,
  ApiResult,
  ApiError,
  CollectOptions,
  CreateServiceRequest,
  DiscoveryTreeRequest,
  DiscoveryTreeResult,
  DownloadRequest,
  GitPushRequest,
  GitPullRequest,
  GitPullResult,
  HealthResponse,
  NodeSyncRequest,
  NodeSyncResult,
  PullBundleRecord,
  PullBundleRequest,
  RepoStateResult,
  RepoActionRequest,
  RepoPolicy,
  RuntimeActionRequest,
  RuntimeCheckResult,
  RuntimeConfig,
  RunRecord,
  SafetyCheckResult,
  ScanRootRequest,
  ScanRootResult,
  SecretPathsResult,
  Service,
  ServerRecord,
  ScopeEntry,
  ManagedDocConfig,
  NodeActionResult,
  NodeViewerEntry,
  Workspace,
  WorkspaceLatest,
} from '../types/switchboard'
import { isApiError } from '../types/switchboard'

const BASE = '/api'

function favoriteRank(value: string | number | undefined): number {
  if (value === 1 || value === 'primary') return 1
  if (value === 2 || value === 'secondary') return 2
  return 99
}

function normalizeService(service: any) {
  return {
    service_id: service.service_id,
    workspace_id: service.workspace_id,
    display_name: service.display_name,
    kind: service.kind ?? 'service',
    execution_mode: service.execution_mode ?? 'networked',
    tags: service.tags ?? [],
    favorite_tier: favoriteRank(service.favorite_tier),
    locations: (service.locations ?? []).map((location: any) => ({
      location_id: location.location_id,
      server_id: location.server_id,
      access_mode: location.access_mode ?? 'ssh',
      root: location.root ?? location.path ?? '',
      role: location.role ?? 'primary',
      is_primary: Boolean(location.is_primary),
      path_aliases: location.path_aliases ?? [],
      runtime: normalizeRuntimeConfig(location.runtime),
    })),
    repo_paths: service.repo_paths ?? [],
    docs_paths: service.docs_paths ?? [],
    log_paths: service.log_paths ?? [],
    allowed_git_pull_paths: service.allowed_git_pull_paths ?? [],
    exclude_globs: service.exclude_globs ?? [],
    scope_entries: (service.scope_entries ?? []).map(normalizeScopeEntry),
    managed_docs: (service.managed_docs ?? []).map(normalizeManagedDoc),
    repo_policies: (service.repo_policies ?? []).map(normalizeRepoPolicy),
    notes: service.notes ?? '',
    path_aliases: service.path_aliases ?? [],
    runtime_checks: (service.runtime_checks ?? []).map(normalizeRuntimeCheck),
    node_sync: (service.node_sync ?? []).map(normalizeNodeSync),
    task_ledger: (service.task_ledger ?? []).map(normalizeTaskLedgerEntry),
    node_viewer: (service.node_viewer ?? []).map(normalizeNodeViewer),
  } satisfies Service
}

function normalizeRuntimeConfig(runtime: any): RuntimeConfig {
  return {
    expected_ports: Array.isArray(runtime?.expected_ports)
      ? runtime.expected_ports
          .map((port: unknown) => Number(port))
          .filter((port: number) => Number.isFinite(port))
      : [],
    healthcheck_command: runtime?.healthcheck_command ?? '',
    run_command_hint: runtime?.run_command_hint ?? '',
    monitoring_mode: runtime?.monitoring_mode ?? 'manual',
    notes: runtime?.notes ?? '',
  }
}

function normalizeScopeEntry(entry: any): ScopeEntry {
  return {
    entry_id: entry.entry_id,
    kind: entry.kind,
    path: entry.path,
    path_type: entry.path_type,
    source: entry.source ?? 'user_added',
    enabled: entry.enabled ?? true,
  }
}

function normalizeRepoPolicy(policy: any): RepoPolicy {
  return {
    repo_path: policy.repo_path,
    push_mode: policy.push_mode ?? 'blocked',
    safety_profile: policy.safety_profile ?? 'generic_python',
    allowed_branches: policy.allowed_branches ?? [],
    allowed_remotes: policy.allowed_remotes ?? [],
  }
}

function normalizeManagedDoc(entry: any): ManagedDocConfig {
  return {
    doc_id: entry.doc_id,
    path: entry.path ?? '',
    enabled: entry.enabled ?? false,
    generated_from: entry.generated_from ?? 'switchboard/local/tasks-completed.md',
    last_generated_at: entry.last_generated_at ?? null,
  }
}

function normalizeDocIndex(docIndex: any) {
  return {
    generated: docIndex?.generated ?? '',
    service_id: docIndex?.service_id,
    project_root: docIndex?.project_root,
    docs: Array.isArray(docIndex?.docs)
      ? docIndex.docs.map((entry: any) => ({
          doc_id: entry.doc_id,
          label: entry.label,
          path: entry.path ?? '',
          enabled: entry.enabled ?? false,
          generated_at: entry.generated_at ?? null,
          generated_from: entry.generated_from ?? 'switchboard/local/tasks-completed.md',
          contributor_timestamps: entry.contributor_timestamps ?? [],
        }))
      : [],
  }
}

function normalizeWorkspace(workspace: any, services: any[] = []): Workspace {
  const workspaceServiceIds = Array.isArray(workspace.services) ? workspace.services : []
  const workspaceServerIds = workspace.server_ids ?? workspace.servers ?? []
  return {
    workspace_id: workspace.workspace_id,
    company_id: workspace.company_id ?? workspace.workspace_id,
    display_name: workspace.display_name ?? workspace.name ?? workspace.workspace_id,
    services: services.map(normalizeService),
    server_ids: workspaceServerIds,
    tags: workspace.tags ?? [],
    notes: workspace.notes ?? '',
    service_count:
      typeof workspace.service_count === 'number'
        ? workspace.service_count
        : services.length > 0
          ? services.length
          : workspaceServiceIds.length,
    server_count:
      typeof workspace.server_count === 'number'
        ? workspace.server_count
        : workspaceServerIds.length,
  }
}

function normalizeRepoSummary(repo: any, allowedPaths: string[]) {
  const lastCommit = typeof repo.last_commit === 'string' ? repo.last_commit.split('\t')[0] : ''
  return {
    path: repo.repo_path ?? repo.path ?? '',
    server_id: repo.server_id,
    branch: repo.branch ?? '',
    commit: repo.commit ?? lastCommit ?? '',
    dirty: Boolean(repo.dirty),
    status: repo.status ?? 'unverified',
    is_allowlisted: allowedPaths.includes(repo.repo_path ?? repo.path ?? ''),
    remotes: repo.remotes ?? [],
    push_mode: repo.push_mode,
    safety_profile: repo.safety_profile,
    push_eligible: repo.push_eligible,
  }
}

function normalizeRepoState(repo: any): RepoStateResult {
  const normalized = normalizeRepoSummary(repo, [])
  return {
    ...normalized,
    repo_path: repo.repo_path ?? repo.path ?? '',
  }
}

function normalizePortInfo(port: any) {
  return {
    port: Number(port.port ?? 0),
    protocol: port.protocol ?? 'tcp',
    process: port.process ?? '',
    pid: typeof port.pid === 'number' ? port.pid : port.pid ? Number(port.pid) : undefined,
    state: port.state,
  }
}

function normalizeRuntimeCheck(result: any): RuntimeCheckResult {
  return {
    service_id: result.service_id,
    location_id: result.location_id,
    server_id: result.server_id,
    root: result.root ?? '',
    status: result.status ?? 'unverified',
    checked_at: result.checked_at ?? '',
    execution_mode: result.execution_mode ?? 'networked',
    configured_ports: Array.isArray(result.configured_ports)
      ? result.configured_ports.map((port: unknown) => Number(port)).filter((port: number) => Number.isFinite(port))
      : [],
    detected_ports: (result.detected_ports ?? []).map(normalizePortInfo),
    missing_ports: Array.isArray(result.missing_ports)
      ? result.missing_ports.map((port: unknown) => Number(port)).filter((port: number) => Number.isFinite(port))
      : [],
    healthcheck_command: result.healthcheck_command ?? '',
    healthcheck_status: result.healthcheck_status ?? 'skipped',
    healthcheck_output: result.healthcheck_output ?? '',
    detected_process_command: result.detected_process_command ?? '',
    run_command_hint: result.run_command_hint ?? '',
    monitoring_mode: result.monitoring_mode ?? 'manual',
    notes: result.notes ?? '',
    node_present: Boolean(result.node_present),
    source: result.source,
  }
}

function normalizeNodeSync(result: any): NodeSyncResult {
  return {
    service_id: result.service_id,
    location_id: result.location_id,
    direction: result.direction ?? 'from_node',
    timestamp: result.timestamp ?? '',
    status: result.status ?? 'unverified',
    source: result.source ?? '',
    target: result.target ?? '',
    include_scope_snapshot: result.include_scope_snapshot ?? true,
    include_runtime_config: result.include_runtime_config ?? true,
    managed_docs: (result.managed_docs ?? []).map(normalizeManagedDoc),
    doc_index: result.doc_index ? normalizeDocIndex(result.doc_index) : undefined,
  }
}

function normalizeNodeViewer(result: any): NodeViewerEntry {
  return {
    service_id: result.service_id ?? '',
    location_id: result.location_id ?? '',
    server_id: result.server_id ?? '',
    root: result.root ?? '',
    node_present: Boolean(result.node_present),
    bootstrap_ready: Boolean(result.bootstrap_ready),
    runtime_ready: Boolean(result.runtime_ready),
    installed_version: result.installed_version ?? '',
    bootstrap_version: result.bootstrap_version ?? '',
    manifest_updated_at: result.manifest_updated_at ?? '',
    runtime_status: result.runtime_status ?? 'missing',
    runtime_pid: typeof result.runtime_pid === 'number' ? result.runtime_pid : undefined,
    runtime_port: result.runtime_port ?? 8010,
    needs_install: Boolean(result.needs_install),
    needs_upgrade: Boolean(result.needs_upgrade),
    needs_bootstrap: Boolean(result.needs_bootstrap),
    attention_reason: result.attention_reason ?? '',
    manifest_path: result.manifest_path ?? '',
    runtime_dir: result.runtime_dir ?? '',
    log_file: result.log_file ?? '',
    last_error: result.last_error ?? '',
  }
}

function normalizeFile(file: any) {
  return {
    path: file.path,
    name: file.name,
    size_bytes: file.size_bytes ?? file.size ?? 0,
    modified: file.modified ?? file.modified_at ?? '',
    kind: file.kind,
  }
}

function normalizeWorkspaceLatest(raw: any): WorkspaceLatest {
  const services = (raw.services ?? []).map((entry: any) => ({
    service_id: entry.service_id,
    status: entry.status ?? 'unverified',
    ports: (entry.ports ?? []).map(normalizePortInfo),
    firewall_status: entry.firewall_status ?? '',
    firewall_active: Boolean(entry.firewall_active),
    repo_summaries: (raw.repo_inventory ?? [])
      .filter((repo: any) => repo.service_id === entry.service_id)
      .map((repo: any) => normalizeRepoSummary(repo, [])),
    docs_count: entry.docs_count ?? entry.doc_count ?? 0,
    logs_count: entry.logs_count ?? entry.log_count ?? 0,
    docs_files: (raw.docs_index ?? [])
      .filter((file: any) => file.service_id === entry.service_id)
      .map((file: any) => normalizeFile({ ...file, kind: 'doc' })),
    logs_files: (raw.logs_index ?? [])
      .filter((file: any) => file.service_id === entry.service_id)
      .map((file: any) => normalizeFile({ ...file, kind: 'log' })),
    secret_path_count: entry.secret_path_count ?? 0,
    collected_at: raw.generated ?? '',
    runtime_checks: (entry.runtime_checks ?? []).map(normalizeRuntimeCheck),
    node_sync: (entry.node_sync ?? []).map(normalizeNodeSync),
  }))

  return {
    workspace: normalizeWorkspace(raw.workspace, []),
    servers: (raw.servers ?? []).map((server: any) => ({
      server_id: server.server_id,
      host: server.host,
      type: server.connection_type ?? 'unknown',
      role: server.name ?? server.hostname ?? '',
      port: server.port ?? 22,
      status: server.status ?? 'unverified',
    })),
    services,
    summary: {
      run_id: raw.generated ?? 'unverified',
      workspace_id: raw.workspace?.workspace_id ?? '',
      timestamp: raw.generated ?? '',
      status: raw.summary?.status ?? 'unverified',
      triggered_by: 'system',
    },
    repo_inventory: (raw.repo_inventory ?? []).map((repo: any) => normalizeRepoSummary(repo, [])),
    docs_index: (raw.docs_index ?? []).map((file: any) => normalizeFile({ ...file, kind: 'doc' })),
    logs_index: (raw.logs_index ?? []).map((file: any) => normalizeFile({ ...file, kind: 'log' })),
  }
}

async function apiFetch<T>(
  path: string,
  options?: RequestInit,
): Promise<ApiResult<T>> {
  try {
    const res = await fetch(`${BASE}${path}`, {
      headers: { 'Content-Type': 'application/json' },
      ...options,
    })
    if (!res.ok) {
      const body = await res.json().catch(() => ({}))
      const detail = body?.detail
      const message =
        typeof detail === 'string'
          ? detail
          : typeof detail?.message === 'string'
            ? detail.message
            : `HTTP ${res.status}`
      const status =
        typeof detail?.status === 'string'
          ? detail.status
          : res.status === 404
            ? 'path_missing'
            : 'unreachable'
      return {
        status,
        message,
        code: res.status,
      } as ApiError
    }
    return (await res.json()) as T
  } catch {
    return { status: 'unreachable', message: 'Backend not reachable' } as ApiError
  }
}

type WorkspacesResponse = { workspaces: unknown[] }
type WorkspaceResponse = { workspace: unknown; services: unknown[] }
type WorkspaceRunsResponse = { workspace_id: string; runs: unknown[] }
type ServiceResponse = { service: unknown }
type ServersResponse = { servers: unknown[] }
type ServiceScopeResponse = { service_id: string; scope_entries: unknown[]; repo_policies: unknown[] }
type PullBundlesResponse = { service_id: string; bundles: unknown[] }

function hasObjectProperty<K extends string>(
  value: unknown,
  key: K,
): value is Record<K, unknown> {
  return typeof value === 'object' && value !== null && key in value
}

export const getHealth = (): Promise<ApiResult<HealthResponse>> =>
  apiFetch<HealthResponse>('/health')

export const listServers = (): Promise<ApiResult<ServerRecord[]>> =>
  apiFetch<ServersResponse>('/servers').then((res) => {
    if (isApiError(res)) return res
    if (!hasObjectProperty(res, 'servers') || !Array.isArray(res.servers)) {
      return { status: 'unverified', message: 'Invalid servers response' }
    }
    return res.servers.map((server: any) => ({
      server_id: server.server_id,
      company_id: server.company_id ?? '',
      name: server.name,
      connection_type: server.connection_type,
      host: server.host,
      username: server.username,
      port: server.port ?? 22,
      deployment_mode: server.deployment_mode ?? 'native_agent',
      vpn_required: Boolean(server.vpn_required),
      tags: server.tags ?? [],
      notes: server.notes ?? '',
    }))
  })

export const listWorkspaces = (): Promise<ApiResult<Workspace[]>> =>
  apiFetch<WorkspacesResponse>('/workspaces').then((res) => {
    if (isApiError(res)) return res
    if (!hasObjectProperty(res, 'workspaces') || !Array.isArray(res.workspaces)) {
      return { status: 'unverified', message: 'Invalid workspaces response' }
    }
    return res.workspaces.map((workspace) => normalizeWorkspace(workspace))
  })

export const listCompanies = (): Promise<ApiResult<Workspace[]>> =>
  listWorkspaces()

export const getWorkspace = (id: string): Promise<ApiResult<Workspace>> =>
  apiFetch<WorkspaceResponse>(`/workspaces/${id}`).then((res) => {
    if (isApiError(res)) return res
    if (
      !hasObjectProperty(res, 'workspace') ||
      !hasObjectProperty(res, 'services') ||
      !Array.isArray(res.services)
    ) {
      return { status: 'unverified', message: 'Invalid workspace response' }
    }
    return normalizeWorkspace(res.workspace, res.services)
  })

export const getWorkspaceLatest = (id: string): Promise<ApiResult<WorkspaceLatest>> =>
  apiFetch<any>(`/workspaces/${id}/latest`).then((res) =>
    isApiError(res) ? res : normalizeWorkspaceLatest(res),
  )

export const getWorkspaceRuns = (id: string): Promise<ApiResult<RunRecord[]>> =>
  apiFetch<WorkspaceRunsResponse>(`/workspaces/${id}/runs`).then((res) => {
    if (isApiError(res)) return res
    if (!hasObjectProperty(res, 'runs') || !Array.isArray(res.runs)) {
      return { status: 'unverified', message: 'Invalid workspace runs response' }
    }
    return res.runs.map((run: any) => ({
      run_id: run.generated ?? run.run_id ?? '',
      workspace_id: run.workspace_id ?? id,
      timestamp: run.generated ?? run.timestamp ?? '',
      status: run.status ?? 'unverified',
      triggered_by: run.triggered_by ?? 'system',
    }))
  })

export const getService = (id: string): Promise<ApiResult<Service>> =>
  apiFetch<ServiceResponse>(`/services/${id}`).then((res) => {
    if (isApiError(res)) return res
    if (!hasObjectProperty(res, 'service')) {
      return { status: 'unverified', message: 'Invalid service response' }
    }
    return normalizeService(res.service)
  })

export const getServiceScope = (
  id: string,
): Promise<ApiResult<{ service_id: string; scope_entries: ScopeEntry[]; repo_policies: RepoPolicy[] }>> =>
  apiFetch<ServiceScopeResponse>(`/services/${id}/scope`).then((res) => {
    if (isApiError(res)) return res
    return {
      service_id: String((res as any).service_id ?? id),
      scope_entries: ((res as any).scope_entries ?? []).map(normalizeScopeEntry),
      repo_policies: ((res as any).repo_policies ?? []).map(normalizeRepoPolicy),
    }
  })

export const scanRoot = (req: ScanRootRequest): Promise<ApiResult<ScanRootResult>> =>
  apiFetch<ScanRootResult>('/discovery/scan-root', {
    method: 'POST',
    body: JSON.stringify(req),
  })

export const browseTree = (
  req: DiscoveryTreeRequest,
): Promise<ApiResult<DiscoveryTreeResult>> =>
  apiFetch<DiscoveryTreeResult>('/discovery/tree', {
    method: 'POST',
    body: JSON.stringify(req),
  })

export const triggerCollect = (
  id: string,
  opts: CollectOptions = {},
): Promise<ApiResult<WorkspaceLatest>> =>
  apiFetch<any>(`/workspaces/${id}/collect`, {
    method: 'POST',
    body: JSON.stringify(opts),
  }).then((res) => (isApiError(res) ? res : normalizeWorkspaceLatest(res)))

export const addService = (
  workspaceId: string,
  data: CreateServiceRequest,
): Promise<ApiResult<Service>> =>
  apiFetch<ServiceResponse>(`/workspaces/${workspaceId}/services`, {
    method: 'POST',
    body: JSON.stringify(data),
  }).then((res) => {
    if (isApiError(res)) return res
    if (!hasObjectProperty(res, 'service')) {
      return { status: 'unverified', message: 'Invalid service create response' }
    }
    return normalizeService(res.service)
  })

export const updateService = (
  id: string,
  patch: Partial<Service>,
): Promise<ApiResult<Service>> =>
  apiFetch<ServiceResponse>(`/services/${id}`, {
    method: 'PATCH',
    body: JSON.stringify(patch),
  }).then((res) => {
    if (isApiError(res)) return res
    if (!hasObjectProperty(res, 'service')) {
      return { status: 'unverified', message: 'Invalid service update response' }
    }
    return normalizeService(res.service)
  })

export const deleteService = (
  id: string,
): Promise<ApiResult<{ deleted: boolean; service_id: string; workspace_id: string; generated: string }>> =>
  apiFetch<{ deleted: boolean; service_id: string; workspace_id: string; generated: string }>(`/services/${id}`, {
    method: 'DELETE',
  })

export const requestDownload = (
  id: string,
  req: DownloadRequest,
): Promise<ApiResult<{ path: string; files: string[] }>> =>
  apiFetch<{ path: string; files: string[] }>(`/services/${id}/downloads`, {
    method: 'POST',
    body: JSON.stringify(req),
  })

export const triggerGitPull = (
  id: string,
  req: GitPullRequest,
): Promise<ApiResult<GitPullResult>> =>
  apiFetch<GitPullResult>(`/services/${id}/actions/git-pull`, {
    method: 'POST',
    body: JSON.stringify(req),
  })

export const getGitStatus = (
  id: string,
  req: RepoActionRequest,
): Promise<ApiResult<RepoStateResult>> =>
  apiFetch<any>(`/services/${id}/actions/git-status`, {
    method: 'POST',
    body: JSON.stringify(req),
  }).then((res) => (isApiError(res) ? res : normalizeRepoState(res)))

export const runSafetyCheck = (
  id: string,
  req: RepoActionRequest,
): Promise<ApiResult<SafetyCheckResult>> =>
  apiFetch<any>(`/services/${id}/actions/safety-check`, {
    method: 'POST',
    body: JSON.stringify(req),
  }).then((res) => {
    if (isApiError(res)) return res
    return {
      ...res,
      repo_state: normalizeRepoState(res.repo_state ?? {}),
    } satisfies SafetyCheckResult
  })

export const triggerGitPush = (
  id: string,
  req: GitPushRequest,
): Promise<ApiResult<GitPullResult>> =>
  apiFetch<GitPullResult>(`/services/${id}/actions/git-push`, {
    method: 'POST',
    body: JSON.stringify(req),
  })

// Returns count only — never expose actual paths in the dashboard
export const getSecretPathCount = (
  id: string,
): Promise<ApiResult<SecretPathsResult>> =>
  apiFetch<SecretPathsResult>(`/services/${id}/secret-paths`)

export const runRuntimeCheck = (
  id: string,
  req: RuntimeActionRequest,
): Promise<ApiResult<RuntimeCheckResult>> =>
  apiFetch<RuntimeCheckResult>(`/services/${id}/actions/runtime-check`, {
    method: 'POST',
    body: JSON.stringify(req),
  }).then((res) => (isApiError(res) ? res : normalizeRuntimeCheck(res)))

export const syncFromNode = (
  id: string,
  req: NodeSyncRequest,
): Promise<ApiResult<{ service: Service; sync: NodeSyncResult }>> =>
  apiFetch<any>(`/services/${id}/actions/sync-from-node`, {
    method: 'POST',
    body: JSON.stringify(req),
  }).then((res) => {
    if (isApiError(res)) return res
    return {
      service: normalizeService(res.service),
      sync: normalizeNodeSync(res.sync),
    }
  })

export const syncToNode = (
  id: string,
  req: NodeSyncRequest,
): Promise<ApiResult<{ sync: NodeSyncResult; node_manifest_path?: string }>> =>
  apiFetch<any>(`/services/${id}/actions/sync-to-node`, {
    method: 'POST',
    body: JSON.stringify(req),
  }).then((res) => {
    if (isApiError(res)) return res
    return {
      sync: normalizeNodeSync(res.sync),
      node_manifest_path: res.node_manifest_path,
    }
  })

export const getNodeViewer = (
  id: string,
): Promise<ApiResult<{ locations: NodeViewerEntry[] }>> =>
  apiFetch<any>(`/services/${id}/node-viewer`).then((res) => {
    if (isApiError(res)) return res
    return { locations: (res.locations ?? []).map(normalizeNodeViewer) }
  })

export const inspectNode = (
  id: string,
  locationId?: string,
): Promise<ApiResult<NodeActionResult>> =>
  apiFetch<any>(`/services/${id}/actions/node-inspect`, {
    method: 'POST',
    body: JSON.stringify({ location_id: locationId }),
  }).then((res) => {
    if (isApiError(res)) return res
    return {
      node: normalizeNodeViewer(res.node),
      before: res.before ? normalizeNodeViewer(res.before) : undefined,
      after: res.after ? normalizeNodeViewer(res.after) : undefined,
      message: res.message,
    }
  })

export const deployNode = (
  id: string,
  locationId?: string,
): Promise<ApiResult<NodeActionResult>> =>
  apiFetch<any>(`/services/${id}/actions/node-deploy`, {
    method: 'POST',
    body: JSON.stringify({ location_id: locationId }),
  }).then((res) => {
    if (isApiError(res)) return res
    return {
      node: normalizeNodeViewer(res.node),
      before: res.before ? normalizeNodeViewer(res.before) : undefined,
      after: res.after ? normalizeNodeViewer(res.after) : undefined,
      message: res.message,
    }
  })

export const upgradeNode = (
  id: string,
  locationId?: string,
): Promise<ApiResult<NodeActionResult>> =>
  apiFetch<any>(`/services/${id}/actions/node-upgrade`, {
    method: 'POST',
    body: JSON.stringify({ location_id: locationId }),
  }).then((res) => {
    if (isApiError(res)) return res
    return {
      node: normalizeNodeViewer(res.node),
      before: res.before ? normalizeNodeViewer(res.before) : undefined,
      after: res.after ? normalizeNodeViewer(res.after) : undefined,
      message: res.message,
    }
  })

export const restartNode = (
  id: string,
  locationId?: string,
): Promise<ApiResult<NodeActionResult>> =>
  apiFetch<any>(`/services/${id}/actions/node-restart`, {
    method: 'POST',
    body: JSON.stringify({ location_id: locationId }),
  }).then((res) => {
    if (isApiError(res)) return res
    return {
      node: normalizeNodeViewer(res.node),
      before: res.before ? normalizeNodeViewer(res.before) : undefined,
      after: res.after ? normalizeNodeViewer(res.after) : undefined,
      message: res.message,
    }
  })

export const createPullBundle = (
  id: string,
  req: PullBundleRequest,
): Promise<ApiResult<PullBundleRecord & { files?: unknown[] }>> =>
  apiFetch<PullBundleRecord & { files?: unknown[] }>(`/services/${id}/pull-bundles`, {
    method: 'POST',
    body: JSON.stringify(req),
  })

export const listPullBundles = (
  id: string,
): Promise<ApiResult<PullBundleRecord[]>> =>
  apiFetch<PullBundlesResponse>(`/services/${id}/pull-bundles`).then((res) => {
    if (isApiError(res)) return res
    if (!hasObjectProperty(res, 'bundles') || !Array.isArray(res.bundles)) {
      return { status: 'unverified', message: 'Invalid pull bundle history response' }
    }
    return res.bundles as PullBundleRecord[]
  })

export function normalizeTaskLedgerEntry(entry: any): TaskLedgerEntry {
  return {
    timestamp: entry.timestamp ?? '',
    title: entry.title ?? '',
    task_id: entry.task_id,
    agent: entry.agent,
    tool: entry.tool,
    tags: entry.tags ?? [],
    summary: entry.summary,
    changed_paths: entry.changed_paths ?? [],
    version: entry.version,
    bootstrap_version: entry.bootstrap_version,
    runtime_services: entry.runtime_services ?? [],
    dependencies: entry.dependencies ?? [],
    cross_dependencies: entry.cross_dependencies ?? [],
    diagram: entry.diagram,
    notes: entry.notes,
    scope_entries: (entry.scope_entries ?? []).map(normalizeScopeEntry),
    runtime: entry.runtime ? normalizeRuntimeConfig(entry.runtime) : undefined,
    readme: entry.readme,
    api: entry.api,
    changelog: entry.changelog,
    node_id: entry.node_id,
  }
}

export function normalizeActionLock(lock: any): ActionLock {
  return {
    action_key: lock.action_key ?? '',
    service_id: lock.service_id ?? '',
    started_at: lock.started_at ?? '',
    expires_at: lock.expires_at ?? '',
    ttl_seconds: lock.ttl_seconds ?? 0,
    status: lock.status ?? '',
  }
}

export const getTaskLedger = (serviceId: string): Promise<ApiResult<{ tasks: TaskLedgerEntry[] }>> =>
  apiFetch<{ tasks: any[] }>(`/services/${serviceId}/task-ledger`).then((res) => {
    if (isApiError(res)) return res
    return { tasks: res.tasks.map(normalizeTaskLedgerEntry) }
  })

export const getActionLocks = (serviceId: string): Promise<ApiResult<{ locks: ActionLock[] }>> =>
  apiFetch<{ locks: any[] }>(`/services/${serviceId}/action-locks`).then((res) => {
    if (isApiError(res)) return res
    return { locks: res.locks.map(normalizeActionLock) }
  })

export const acquireActionLock = (serviceId: string, actionKey: string): Promise<ApiResult<{ status: string; lock?: ActionLock }>> =>
  apiFetch<{ status: string; lock: any }>(`/services/${serviceId}/action-locks`, {
    method: 'POST',
    body: JSON.stringify({ action_key: actionKey }),
  }).then((res) => {
    if (isApiError(res)) return res
    return { status: res.status, lock: res.lock ? normalizeActionLock(res.lock) : undefined }
  })

export const releaseActionLock = (serviceId: string, actionKey: string): Promise<ApiResult<{ status: string }>> =>
  apiFetch<{ status: string }>(`/services/${serviceId}/action-locks/${actionKey}`, {
    method: 'DELETE',
  }).then((res) => {
    if (isApiError(res)) return res
    return { status: res.status }
  })

export const workspaceHealthCheck = (workspaceId: string, runtimePasswords: Record<string, string> = {}): Promise<ApiResult<{ results: RuntimeCheckResult[] }>> =>
  apiFetch<{ results: any[] }>(`/workspaces/${workspaceId}/health-check`, {
    method: 'POST',
    body: JSON.stringify(runtimePasswords),
  }).then((res) => {
    if (isApiError(res)) return res
    return { results: res.results.map(normalizeRuntimeCheck) }
  })

export const listProjects = (
  workspaceId: string,
): Promise<ApiResult<{ projects: ProjectManifest[]; environments: ProjectEnvironmentView[]; rollups: ProjectPullSummary[] }>> =>
  apiFetch<{ projects: any[]; environments?: any[]; rollups?: any[] }>(`/workspaces/${workspaceId}/projects`).then((res) => {
    if (isApiError(res)) return res
    return {
      projects: res.projects,
      environments: (res.environments ?? []) as ProjectEnvironmentView[],
      rollups: (res.rollups ?? []) as ProjectPullSummary[],
    }
  })

export const createProject = (workspaceId: string, req: ProjectCreateRequest): Promise<ApiResult<{ project: ProjectManifest }>> =>
  apiFetch<{ project: any }>(`/workspaces/${workspaceId}/projects`, {
    method: 'POST',
    body: JSON.stringify(req),
  }).then((res) => {
    if (isApiError(res)) return res
    return { project: res.project }
  })

export const updateProject = (projectId: string, req: ProjectPatchRequest): Promise<ApiResult<{ project: ProjectManifest }>> =>
  apiFetch<{ project: any }>(`/projects/${projectId}`, {
    method: 'PATCH',
    body: JSON.stringify(req),
  }).then((res) => {
    if (isApiError(res)) return res
    return { project: res.project }
  })

export const deleteProject = (projectId: string): Promise<ApiResult<{ project: ProjectManifest }>> =>
  apiFetch<{ project: any }>(`/projects/${projectId}`, {
    method: 'DELETE',
  }).then((res) => {
    if (isApiError(res)) return res
    return { project: res.project }
  })

export const createProjectEnvironment = (
  projectId: string,
  req: ProjectEnvironmentCreateRequest,
): Promise<ApiResult<{ environment: ProjectEnvironmentView }>> =>
  apiFetch<{ environment: any }>(`/projects/${projectId}/environments`, {
    method: 'POST',
    body: JSON.stringify(req),
  }).then((res) => {
    if (isApiError(res)) return res
    return { environment: res.environment as ProjectEnvironmentView }
  })

export const updateProjectEnvironment = (
  environmentId: string,
  req: ProjectEnvironmentPatchRequest,
): Promise<ApiResult<{ environment: ProjectEnvironmentView }>> =>
  apiFetch<{ environment: any }>(`/project-environments/${environmentId}`, {
    method: 'PATCH',
    body: JSON.stringify(req),
  }).then((res) => {
    if (isApiError(res)) return res
    return { environment: res.environment as ProjectEnvironmentView }
  })

export const deleteProjectEnvironment = (
  environmentId: string,
): Promise<ApiResult<{ environment: ProjectEnvironmentView }>> =>
  apiFetch<{ environment: any }>(`/project-environments/${environmentId}`, {
    method: 'DELETE',
  }).then((res) => {
    if (isApiError(res)) return res
    return { environment: res.environment as ProjectEnvironmentView }
  })

export const createCompany = (req: CompanyCreateRequest): Promise<ApiResult<{ company: Workspace }>> =>
  apiFetch<{ company: any }>('/companies', {
    method: 'POST',
    body: JSON.stringify(req),
  }).then((res) => {
    if (isApiError(res)) return res
    return { company: normalizeWorkspace(res.company, []) }
  })

export const updateCompany = (companyId: string, req: CompanyPatchRequest): Promise<ApiResult<{ company: Workspace }>> =>
  apiFetch<{ company: any }>(`/companies/${companyId}`, {
    method: 'PATCH',
    body: JSON.stringify(req),
  }).then((res) => {
    if (isApiError(res)) return res
    return { company: normalizeWorkspace(res.company, []) }
  })

export const deleteCompany = (companyId: string): Promise<ApiResult<{ company: Workspace }>> =>
  apiFetch<{ company: any }>(`/companies/${companyId}`, {
    method: 'DELETE',
  }).then((res) => {
    if (isApiError(res)) return res
    return { company: normalizeWorkspace(res.company, []) }
  })

export const createServer = (req: ServerCreateRequest): Promise<ApiResult<{ server: any }>> =>
  apiFetch<{ server: any }>('/servers', {
    method: 'POST',
    body: JSON.stringify(req),
  })

export const updateServer = (serverId: string, req: ServerPatchRequest): Promise<ApiResult<{ server: any }>> =>
  apiFetch<{ server: any }>(`/servers/${serverId}`, {
    method: 'PATCH',
    body: JSON.stringify(req),
  })

export const deleteServer = (serverId: string): Promise<ApiResult<{ server: any }>> =>
  apiFetch<{ server: any }>(`/servers/${serverId}`, {
    method: 'DELETE',
  })
