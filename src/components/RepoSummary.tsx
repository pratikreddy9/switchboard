import { useState } from 'react'
import { GitBranch, GitCommit, RefreshCw, AlertCircle, ShieldAlert, Upload } from 'lucide-react'
import type { RepoSummary as RepoSummaryType } from '../types/switchboard'
import { getGitStatus, runSafetyCheck, triggerGitPull, triggerGitPush } from '../api/client'
import { StatusBadge } from './StatusBadge'
import { isApiError } from '../types/switchboard'

interface Props {
  serviceId: string
  repos: RepoSummaryType[]
  allowedPaths?: string[]
  disabled?: boolean
}

export function RepoSummary({ serviceId, repos, allowedPaths = [], disabled }: Props) {
  const [pulling, setPulling] = useState<string | null>(null)
  const [checkingStatus, setCheckingStatus] = useState<string | null>(null)
  const [checkingSafety, setCheckingSafety] = useState<string | null>(null)
  const [pushing, setPushing] = useState<string | null>(null)
  const [results, setResults] = useState<Record<string, string>>({})
  const [repoState, setRepoState] = useState<Record<string, RepoSummaryType>>({})
  const [safetyResults, setSafetyResults] = useState<
    Record<string, { safe_to_push: boolean; blocking_reasons: string[]; finding_count: number }>
  >({})

  if (repos.length === 0) {
    return <p className="text-sm text-gray-500 italic">No repositories tracked.</p>
  }

  async function handlePull(path: string) {
    setPulling(path)
    const result = await triggerGitPull(serviceId, { repo_path: path })
    setPulling(null)
    if (isApiError(result)) {
      setResults((r) => ({ ...r, [path]: `Error: ${result.message}` }))
    } else {
      setResults((r) => ({ ...r, [path]: result.output || 'Done' }))
    }
  }

  async function handleStatus(path: string) {
    setCheckingStatus(path)
    const result = await getGitStatus(serviceId, { repo_path: path })
    setCheckingStatus(null)
    if (isApiError(result)) {
      setResults((current) => ({ ...current, [path]: `Status error: ${result.message}` }))
      return
    }
    setRepoState((current) => ({ ...current, [path]: result }))
  }

  async function handleSafety(path: string) {
    setCheckingSafety(path)
    const result = await runSafetyCheck(serviceId, { repo_path: path })
    setCheckingSafety(null)
    if (isApiError(result)) {
      setResults((current) => ({ ...current, [path]: `Safety error: ${result.message}` }))
      return
    }
    setRepoState((current) => ({ ...current, [path]: result.repo_state }))
    setSafetyResults((current) => ({
      ...current,
      [path]: {
        safe_to_push: result.safe_to_push,
        blocking_reasons: result.blocking_reasons,
        finding_count: result.finding_count,
      },
    }))
  }

  async function handlePush(path: string) {
    setPushing(path)
    const result = await triggerGitPush(serviceId, { repo_path: path })
    setPushing(null)
    if (isApiError(result)) {
      setResults((current) => ({ ...current, [path]: `Push error: ${result.message}` }))
    } else {
      setResults((current) => ({ ...current, [path]: result.output || 'Push complete' }))
    }
  }

  return (
    <div className="space-y-3">
      {repos.map((repo) => {
        const currentRepo = repoState[repo.path] ?? repo
        const safety = safetyResults[repo.path]
        const allowlisted = currentRepo.is_allowlisted || allowedPaths.includes(repo.path)
        const pushBlocked = currentRepo.push_mode === 'blocked'
        return (
        <div key={repo.path} className="bg-gray-900 border border-gray-800 rounded-lg p-3">
          <div className="flex items-center justify-between mb-2">
            <span className="text-xs font-mono text-gray-400 truncate flex-1 mr-2">{currentRepo.path}</span>
            <StatusBadge status={currentRepo.status} />
          </div>
          <div className="flex items-center gap-4 text-xs text-gray-400 mb-2">
            <span className="flex items-center gap-1">
              <GitBranch className="w-3 h-3" />
              {currentRepo.branch || '—'}
            </span>
            <span className="flex items-center gap-1">
              <GitCommit className="w-3 h-3" />
              {currentRepo.commit ? currentRepo.commit.slice(0, 7) : '—'}
            </span>
            {currentRepo.dirty && (
              <span className="text-yellow-400 flex items-center gap-1">
                <AlertCircle className="w-3 h-3" /> Dirty
              </span>
            )}
            {currentRepo.push_mode && (
              <span className={`rounded-full px-2 py-0.5 ${pushBlocked ? 'bg-red-950 text-red-300' : 'bg-green-950 text-green-300'}`}>
                push {currentRepo.push_mode}
              </span>
            )}
          </div>

          <div className="flex flex-wrap gap-2">
            <button
              onClick={() => handleStatus(repo.path)}
              disabled={disabled || checkingStatus === repo.path}
              className="text-xs flex items-center gap-1 rounded-md border border-gray-700 px-2 py-1 text-gray-200 hover:border-cyan-500 disabled:opacity-50"
            >
              <RefreshCw className={`w-3 h-3 ${checkingStatus === repo.path ? 'animate-spin' : ''}`} />
              {checkingStatus === repo.path ? 'Refreshing' : 'git status'}
            </button>
            <button
              onClick={() => handleSafety(repo.path)}
              disabled={disabled || checkingSafety === repo.path}
              className="text-xs flex items-center gap-1 rounded-md border border-gray-700 px-2 py-1 text-gray-200 hover:border-cyan-500 disabled:opacity-50"
            >
              <ShieldAlert className={`w-3 h-3 ${checkingSafety === repo.path ? 'animate-pulse' : ''}`} />
              {checkingSafety === repo.path ? 'Checking' : 'safety check'}
            </button>
            {allowlisted && !disabled ? (
              <button
                onClick={() => handlePull(repo.path)}
                disabled={pulling === repo.path}
                className="text-xs flex items-center gap-1 rounded-md border border-gray-700 px-2 py-1 text-blue-300 hover:border-blue-500 disabled:opacity-50"
              >
                <RefreshCw className={`w-3 h-3 ${pulling === repo.path ? 'animate-spin' : ''}`} />
                {pulling === repo.path ? 'Pulling' : 'git pull'}
              </button>
            ) : (
              <span className="text-xs text-gray-600">
                {disabled ? 'Offline mode' : 'Not in allowlist'}
              </span>
            )}
            <button
              onClick={() => handlePush(repo.path)}
              disabled={disabled || pushing === repo.path || pushBlocked}
              className="text-xs flex items-center gap-1 rounded-md border border-gray-700 px-2 py-1 text-emerald-300 hover:border-emerald-500 disabled:opacity-50"
            >
              <Upload className="w-3 h-3" />
              {pushing === repo.path ? 'Pushing' : 'git push'}
            </button>
          </div>

          {safety && (
            <div className={`mt-2 rounded-md border px-3 py-2 text-xs ${safety.safe_to_push ? 'border-green-800 bg-green-950/20 text-green-200' : 'border-red-800 bg-red-950/20 text-red-200'}`}>
              <div>
                {safety.safe_to_push ? 'Safe to push' : 'Push blocked'} · findings {safety.finding_count}
              </div>
              {safety.blocking_reasons.length > 0 && (
                <div className="mt-1 text-red-100/90">
                  {safety.blocking_reasons.join(' ')}
                </div>
              )}
            </div>
          )}

          {results[repo.path] && (
            <pre className="mt-2 text-xs bg-gray-950 text-green-400 p-2 rounded overflow-x-auto">
              {results[repo.path]}
            </pre>
          )}
        </div>
      )})}
    </div>
  )
}
