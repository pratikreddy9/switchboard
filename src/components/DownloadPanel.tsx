import { useState } from 'react'
import { Download, FileText, ScrollText } from 'lucide-react'
import type { FileEntry } from '../types/switchboard'
import { requestDownload } from '../api/client'
import { isApiError } from '../types/switchboard'

interface Props {
  serviceId: string
  docs: FileEntry[]
  logs: FileEntry[]
  disabled?: boolean
}

function formatBytes(b: number) {
  if (b < 1024) return `${b}B`
  if (b < 1024 * 1024) return `${(b / 1024).toFixed(1)}KB`
  return `${(b / 1024 / 1024).toFixed(1)}MB`
}

function FileList({
  files,
  kind,
  serviceId,
  disabled,
}: {
  files: FileEntry[]
  kind: 'doc' | 'log'
  serviceId: string
  disabled?: boolean
}) {
  const [downloading, setDownloading] = useState<string | null>(null)
  const [done, setDone] = useState<Set<string>>(new Set())

  async function handleDownload(file: FileEntry) {
    setDownloading(file.path)
    const result = await requestDownload(serviceId, { files: [file.path], kind })
    setDownloading(null)
    if (!isApiError(result)) {
      setDone((d) => new Set(d).add(file.path))
    }
  }

  if (files.length === 0) {
    return <p className="text-xs text-gray-500 italic py-2">No {kind}s found.</p>
  }

  return (
    <ul className="space-y-1">
      {files.map((f) => (
        <li key={f.path} className="flex items-center justify-between text-sm py-1.5 border-b border-gray-800 last:border-0">
          <div className="flex-1 min-w-0 mr-2">
            <span className="text-gray-300 truncate block">{f.name}</span>
            <span className="text-xs text-gray-600">{formatBytes(f.size_bytes)}</span>
          </div>
          {!disabled && (
            <button
              onClick={() => handleDownload(f)}
              disabled={downloading === f.path}
              className={`flex items-center gap-1 text-xs px-2 py-1 rounded transition-colors ${
                done.has(f.path)
                  ? 'text-green-400 bg-green-900/30'
                  : 'text-blue-400 hover:bg-blue-900/30'
              } disabled:opacity-50`}
            >
              <Download className="w-3 h-3" />
              {done.has(f.path) ? 'Saved' : downloading === f.path ? '…' : 'Get'}
            </button>
          )}
        </li>
      ))}
    </ul>
  )
}

export function DownloadPanel({ serviceId, docs, logs, disabled }: Props) {
  return (
    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
      <div>
        <h4 className="flex items-center gap-2 text-sm font-medium text-gray-300 mb-2">
          <FileText className="w-4 h-4 text-blue-400" />
          Documents ({docs.length})
        </h4>
        <FileList files={docs} kind="doc" serviceId={serviceId} disabled={disabled} />
      </div>
      <div>
        <h4 className="flex items-center gap-2 text-sm font-medium text-gray-300 mb-2">
          <ScrollText className="w-4 h-4 text-purple-400" />
          Logs ({logs.length})
        </h4>
        <FileList files={logs} kind="log" serviceId={serviceId} disabled={disabled} />
      </div>
    </div>
  )
}
