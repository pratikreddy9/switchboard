// Loads cached evidence snapshots when the backend is unreachable.
// Files are synced by: npm run sync-evidence
import type { WorkspaceLatest, Workspace, RunRecord } from '../types/switchboard'

const evidenceModules = import.meta.glob('./*.json')

async function loadJson<T>(name: string): Promise<T | null> {
  const loader = evidenceModules[`./${name}`]
  if (!loader) return null
  try {
    const mod = (await loader()) as { default: T }
    return mod.default as T
  } catch {
    return null
  }
}

export async function loadFallbackWorkspace(id: string): Promise<WorkspaceLatest | null> {
  const workspaces = await loadFallbackWorkspaceList()
  const workspace = workspaces.find((item) => item.workspace_id === id)
  if (!workspace) return null
  return {
    workspace,
    servers: [],
    services: workspace.services.map((service) => ({
      service_id: service.service_id,
      status: 'unverified',
      ports: [],
      firewall_status: '',
      firewall_active: false,
      repo_summaries: [],
      docs_count: 0,
      logs_count: 0,
      docs_files: [],
      logs_files: [],
      secret_path_count: 0,
      collected_at: '',
    })),
    summary: {
      run_id: 'offline',
      workspace_id: id,
      timestamp: '',
      status: 'unverified',
      triggered_by: 'offline',
    },
    repo_inventory: [],
    docs_index: [],
    logs_index: [],
  }
}

export async function loadFallbackWorkspaceList(): Promise<Workspace[]> {
  const registry = await loadJson<{ workspaces: any[] }>('workspace-registry.json')
  const inventory = await loadJson<{ services: any[] }>('service-inventory.json')
  const services = inventory?.services ?? []
  return (
    registry?.workspaces.map((workspace) => ({
      workspace_id: workspace.workspace_id,
      display_name: workspace.display_name ?? workspace.name ?? workspace.workspace_id,
      services: services
        .filter((service) => service.workspace_id === workspace.workspace_id)
        .map((service) => ({
          service_id: service.service_id,
          workspace_id: service.workspace_id,
          display_name: service.display_name,
          tags: service.tags ?? [],
          favorite_tier:
            service.favorite_tier === 'primary'
              ? 1
              : service.favorite_tier === 'secondary'
                ? 2
                : 99,
          locations: [],
          repo_paths: [],
          docs_paths: [],
          log_paths: [],
          allowed_git_pull_paths: [],
          exclude_globs: [],
          scope_entries: [],
          managed_docs: [],
          repo_policies: [],
          notes: service.notes ?? '',
          path_aliases: [],
        })),
      server_ids: workspace.server_ids ?? workspace.servers ?? [],
    })) ?? []
  )
}

export const EVIDENCE_FILES = [
  'workspace-registry.json',
  'server-registry.json',
  'service-inventory.json',
  'repo-inventory.json',
  'docs-index.json',
  'logs-index.json',
  'run-history.json',
] as const
