import type { Workspace } from '../types/switchboard'

interface Props {
  workspaces: Workspace[]
  active: string
  onChange: (id: string) => void
}

export function WorkspaceSwitcher({ workspaces, active, onChange }: Props) {
  return (
    <div className="flex gap-1 bg-gray-900 rounded-lg p-1">
      {workspaces.map((ws) => (
        <button
          key={ws.workspace_id}
          onClick={() => onChange(ws.workspace_id)}
          className={`px-4 py-1.5 rounded-md text-sm font-medium transition-colors ${
            active === ws.workspace_id
              ? 'bg-blue-600 text-white'
              : 'text-gray-400 hover:text-white hover:bg-gray-800'
          }`}
        >
          {ws.display_name}
        </button>
      ))}
    </div>
  )
}
