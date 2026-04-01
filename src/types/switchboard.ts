export type CollectStatus =
  | 'ok'
  | 'partial'
  | 'auth_failed'
  | 'unreachable'
  | 'vpn_or_network_blocked'
  | 'command_missing'
  | 'path_missing'
  | 'not_git_repo'
  | 'dirty_repo'
  | 'permission_limited'
  | 'unverified'

export interface PortInfo {
  port: number
  protocol: string
  process: string
  state?: string
}

export interface RepoSummary {
  path: string
  branch: string
  commit: string
  dirty: boolean
  status: CollectStatus
  is_allowlisted: boolean
  server_id?: string
  remotes?: string[]
  push_mode?: 'allowed' | 'blocked'
  safety_profile?: 'generic_python' | 'secret_heavy'
  push_eligible?: boolean
}

export interface ServiceLocation {
  server_id: string
  path: string
}

export interface ServiceLocationDraft {
  location_id: string
  server_id: string
  access_mode: 'local' | 'ssh'
  root: string
  role: string
  is_primary: boolean
  path_aliases: string[]
}

export interface ScopeEntry {
  entry_id?: string
  kind: 'repo' | 'doc' | 'log' | 'exclude'
  path: string
  path_type: 'file' | 'dir' | 'glob'
  source: 'seeded' | 'user_added'
  enabled: boolean
}

export interface RepoPolicy {
  repo_path: string
  push_mode: 'allowed' | 'blocked'
  safety_profile: 'generic_python' | 'secret_heavy'
  allowed_branches: string[]
  allowed_remotes: string[]
}

export interface Service {
  service_id: string
  workspace_id: string
  display_name: string
  tags: string[]
  favorite_tier: number
  locations: ServiceLocation[]
  repo_paths: string[]
  docs_paths: string[]
  log_paths: string[]
  allowed_git_pull_paths: string[]
  exclude_globs: string[]
  scope_entries: ScopeEntry[]
  repo_policies: RepoPolicy[]
  notes: string
  path_aliases: string[]
}

export interface ServiceRunResult {
  service_id: string
  status: CollectStatus
  ports: PortInfo[]
  firewall_status: string
  firewall_active: boolean
  repo_summaries: RepoSummary[]
  docs_count: number
  logs_count: number
  docs_files: FileEntry[]
  logs_files: FileEntry[]
  secret_path_count: number
  collected_at: string
}

export interface FileEntry {
  path: string
  name: string
  size_bytes: number
  modified: string
  kind: 'doc' | 'log'
}

export interface Workspace {
  workspace_id: string
  display_name: string
  services: Service[]
  server_ids: string[]
  service_count?: number
  server_count?: number
}

export interface WorkspaceLatest {
  workspace: Workspace
  servers: ServerInfo[]
  services: ServiceRunResult[]
  summary: CollectSummary
  repo_inventory: RepoSummary[]
  docs_index: FileEntry[]
  logs_index: FileEntry[]
}

export interface ServerInfo {
  server_id: string
  host: string
  type: string
  role: string
  port: number
  status?: CollectStatus
}

export interface ServerRecord {
  server_id: string
  name: string
  connection_type: 'local' | 'ssh'
  host: string
  username: string
  port: number
  tags: string[]
}

export interface CollectSummary {
  run_id: string
  workspace_id: string
  timestamp: string
  status: CollectStatus
  triggered_by?: string
}

export interface RunRecord {
  run_id: string
  workspace_id: string
  timestamp: string
  status: CollectStatus
  triggered_by: string
}

export interface HealthResponse {
  status: string
  version?: string
  timestamp?: string
  framework?: string
  vpn_note?: string
}

export interface ApiError {
  status: CollectStatus
  message: string
  code?: number
}

export type ApiResult<T> = T | ApiError

export function isApiError(v: unknown): v is ApiError {
  return typeof v === 'object' && v !== null && 'message' in v && 'status' in v
}

export interface CollectOptions {
  service_filter?: string[]
  password_overrides?: Record<string, string>
}

export interface DownloadRequest {
  server_id?: string
  files: string[]
  kind: 'doc' | 'log'
}

export interface RepoActionRequest {
  repo_path: string
  server_id?: string
  runtime_password?: string
}

export interface GitPullRequest extends RepoActionRequest {}

export interface GitPushRequest extends RepoActionRequest {
  remote?: string
  branch?: string
}

export interface GitPullResult {
  repo_path: string
  status: CollectStatus
  output: string
  stdout?: string
  stderr?: string
}

export interface RepoStateResult extends RepoSummary {
  repo_path: string
}

export interface SecretPathsResult {
  generated: string
  service_id: string
  count: number
  // entries intentionally omitted from UI types — use count only
}

export interface ScanEntry {
  path: string
  name: string
  entry_type: 'file' | 'dir'
  depth: number
  suggested_kind: 'repo' | 'doc' | 'log' | 'exclude'
}

export interface TreeNodeEntry {
  path: string
  name: string
  node_type: 'file' | 'dir'
  entry_type?: 'file' | 'dir'
  has_children: boolean
  children_loaded: boolean
  suggested_kind: 'repo' | 'doc' | 'log' | 'exclude'
  default_selected: boolean
}

export interface ScanRootRequest {
  server_id: string
  root: string
  runtime_password?: string
  max_depth?: number
}

export interface ScanRootResult {
  status: CollectStatus
  generated?: string
  server_id: string
  root: string
  entries: ScanEntry[]
}

export interface DiscoveryTreeRequest {
  server_id: string
  root: string
  node_path?: string
  runtime_password?: string
}

export interface DiscoveryTreeResult {
  status: CollectStatus
  generated?: string
  server_id: string
  root: string
  node_path: string
  message?: string
  current_node: TreeNodeEntry | null
  entries: TreeNodeEntry[]
}

export interface SafetyCheckResult {
  generated: string
  service_id: string
  repo_path: string
  server_id: string
  scanner: string
  push_mode: 'allowed' | 'blocked'
  safety_profile: 'generic_python' | 'secret_heavy'
  finding_count: number
  blocking_reason_count: number
  blocking_reasons: string[]
  safe_to_push: boolean
  safe_to_deploy: boolean
  status: CollectStatus
  repo_state: RepoSummary
}

export interface PullBundleRequest {
  server_id?: string
  runtime_password?: string
  extra_includes: ScopeEntry[]
  extra_excludes: string[]
}

export interface PullBundleRecord {
  bundle_id: string
  created_at: string
  workspace_id: string
  service_id: string
  server_id: string
  file_count: number
  docs_count: number
  logs_count: number
  bundle_path: string
  source_tree_path?: string
  manifest_path: string
  repo_commits: string[]
}

export interface CreateServiceRequest {
  service_id: string
  display_name: string
  kind?: string
  ownership_tier?: 'owned' | 'shared' | 'infra'
  tags?: string[]
  favorite_tier?: 'primary' | 'secondary' | 'none'
  locations: ServiceLocationDraft[]
  repo_paths?: string[]
  docs_paths?: string[]
  log_paths?: string[]
  allowed_git_pull_paths?: string[]
  exclude_globs?: string[]
  scope_entries: ScopeEntry[]
  repo_policies?: RepoPolicy[]
  notes?: string
  path_aliases?: string[]
}
