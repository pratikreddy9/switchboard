import type {
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
  PullBundleRecord,
  PullBundleRequest,
  RepoStateResult,
  RepoActionRequest,
  RepoPolicy,
  RunRecord,
  SafetyCheckResult,
  ScanRootRequest,
  ScanRootResult,
  SecretPathsResult,
  Service,
  ServerRecord,
  ScopeEntry,
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
    tags: service.tags ?? [],
    favorite_tier: favoriteRank(service.favorite_tier),
    locations: (service.locations ?? []).map((location: any) => ({
      server_id: location.server_id,
      path: location.root ?? location.path ?? '',
    })),
    repo_paths: service.repo_paths ?? [],
    docs_paths: service.docs_paths ?? [],
    log_paths: service.log_paths ?? [],
    allowed_git_pull_paths: service.allowed_git_pull_paths ?? [],
    exclude_globs: service.exclude_globs ?? [],
    scope_entries: (service.scope_entries ?? []).map(normalizeScopeEntry),
    repo_policies: (service.repo_policies ?? []).map(normalizeRepoPolicy),
    notes: service.notes ?? '',
    path_aliases: service.path_aliases ?? [],
  } satisfies Service
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

function normalizeWorkspace(workspace: any, services: any[] = []): Workspace {
  const workspaceServiceIds = Array.isArray(workspace.services) ? workspace.services : []
  const workspaceServerIds = workspace.server_ids ?? workspace.servers ?? []
  return {
    workspace_id: workspace.workspace_id,
    display_name: workspace.display_name ?? workspace.name ?? workspace.workspace_id,
    services: services.map(normalizeService),
    server_ids: workspaceServerIds,
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
    ports: entry.ports ?? [],
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
      return {
        status: res.status === 404 ? 'path_missing' : 'unreachable',
        message: body?.detail ?? `HTTP ${res.status}`,
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
      name: server.name,
      connection_type: server.connection_type,
      host: server.host,
      username: server.username,
      port: server.port ?? 22,
      tags: server.tags ?? [],
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
