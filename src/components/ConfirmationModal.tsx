import { Dialog, DialogPanel, DialogTitle, Transition, TransitionChild } from '@headlessui/react'
import { Fragment } from 'react'
import type { ActionExplainConfig } from '../types/switchboard'

export const ACTION_EXPLAIN: Record<string, ActionExplainConfig> = {
  node_inspect: { title: 'Inspect node state', happens: ['Connects to the selected server or local runtime.', 'Reads node manifest, pid/log status, and runtime metadata.', 'Refreshes the cached node viewer for this location.'], untouched: ['Does not restart the node.', 'Does not rewrite project files.', 'Does not deploy a new package version.'], writesTo: ['switchboard/state/private/runtime-cache.json'] },
  node_deploy: { title: 'Install node release', happens: ['Checks GitHub for the latest tracked Switchboard release asset.', 'Installs that release into the node runtime environment.', 'Scaffolds or refreshes node files for the selected project root.'], untouched: ['Does not sync project scope from the control center.', 'Does not rewrite sibling project roots.', 'Does not edit app code outside the Switchboard folder.'], writesTo: ['<project-root>/switchboard/', 'switchboard/state/private/runtime-cache.json'] },
  node_upgrade: { title: 'Reinstall or update node release', happens: ['Checks GitHub for the latest tracked Switchboard release asset.', 'Installs that release into the existing node runtime.', 'Restarts the tracked node runtime after the install completes.'], untouched: ['Does not create a brand-new service.', 'Does not change runtime scope or docs by itself.', 'Does not touch sibling project roots.'], writesTo: ['<project-root>/switchboard/', 'switchboard/runtime/node.pid', 'switchboard/runtime/node.log', 'switchboard/state/private/runtime-cache.json'] },
  node_restart: { title: 'Restart node runtime', happens: ['Stops the tracked node runtime if it is currently running.', 'Starts the node runtime again using the selected control port.', 'Verifies that the runtime comes back up.'], untouched: ['Does not sync manifest data.', 'Does not edit app code.', 'Does not change other tracked nodes unless they already conflict on the same port.'], writesTo: ['<project-root>/switchboard/runtime/node.pid', '<project-root>/switchboard/runtime/node.log', 'switchboard/state/private/runtime-cache.json'] },
  sync_to_node: { title: 'Sync to node', happens: ['Writes the selected service scope to the node scope snapshot.', 'Writes runtime config and named services for this location.', 'Mirrors managed-doc and task-ledger metadata to the node.'], untouched: ['Does not rename ids.', 'Does not change other services or sibling locations.', 'Does not run the project for you.'], writesTo: ['switchboard/node.manifest.json', 'switchboard/evidence/scope.snapshot.json'] },
  sync_from_node: { title: 'Sync from node', happens: ['Imports node scope, runtime config, and task ledger.', 'Updates control center configurations.'], untouched: ['Does not touch sibling locations.', 'Does not alter unselected services.'], writesTo: ['switchboard/manifests/services.json'] },
  runtime_check: { title: 'Refresh runtime snapshot', happens: ['Connects to the server.', 'Reads ports, processes, node state, and health hints.', 'Generates operator follow-up commands.'], untouched: ['Does not restart the application.', 'Does not alter firewall or port bindings.'], writesTo: ['switchboard/state/run/'] },
  pull_bundle: { title: 'Create bundle', happens: ['Copies files specified in scope.', 'Creates a zip or directory payload.'], untouched: ['Does not delete original files.', 'Does not deploy anything.'], writesTo: ['downloads/'] },
  workspace_health_check: { title: 'Run all health checks', happens: ['Iterates all services in workspace.', 'Calls runtime_check for each location.', 'Aggregates and returns per-service per-location results.'], untouched: ['Does not restart the applications.', 'Does not alter application code.'], writesTo: ['switchboard/state/run/'] },
}

export interface ConfirmationModalProps {
  open: boolean
  title: string
  willDo: string[]
  willNotChange: string[]
  writesTo: string[]
  preflight?: string[]
  followUp?: string[]
  commandPreview?: string[]
  onConfirm: () => void
  onCancel: () => void
  loading?: boolean
  confirmLabel?: string
}

export function ConfirmationModal({
  open,
  title,
  willDo,
  willNotChange,
  writesTo,
  preflight = [],
  followUp = [],
  commandPreview = [],
  onConfirm,
  onCancel,
  loading = false,
  confirmLabel = 'Proceed',
}: ConfirmationModalProps) {
  return (
    <Transition appear show={open} as={Fragment}>
      <Dialog as="div" className="relative z-50" onClose={() => !loading && onCancel()}>
        <TransitionChild
          as={Fragment}
          enter="ease-out duration-200"
          enterFrom="opacity-0"
          enterTo="opacity-100"
          leave="ease-in duration-150"
          leaveFrom="opacity-100"
          leaveTo="opacity-0"
        >
          <div className="fixed inset-0 bg-black/50" />
        </TransitionChild>

        <div className="fixed inset-0 overflow-y-auto">
          <div className="flex min-h-full items-center justify-center p-4">
            <TransitionChild
              as={Fragment}
              enter="ease-out duration-200"
              enterFrom="opacity-0 scale-95"
              enterTo="opacity-100 scale-100"
              leave="ease-in duration-150"
              leaveFrom="opacity-100 scale-100"
              leaveTo="opacity-0 scale-95"
            >
              <DialogPanel className="w-full max-w-md rounded bg-gray-900 border border-gray-700 p-6 shadow-xl">
                <DialogTitle as="h3" className="text-base font-semibold text-white">
                  {title}
                </DialogTitle>
                <div className="mt-4 space-y-4">
                  {willDo.length > 0 && (
                    <div>
                      <h4 className="text-xs font-semibold text-gray-400 uppercase tracking-wide mb-1">What will happen</h4>
                      <ul className="list-disc pl-5 text-sm text-gray-300 space-y-1">
                        {willDo.map((item, idx) => <li key={idx}>{item}</li>)}
                      </ul>
                    </div>
                  )}
                  {preflight.length > 0 && (
                    <div>
                      <h4 className="text-xs font-semibold text-gray-400 uppercase tracking-wide mb-1">Before this step</h4>
                      <ul className="list-disc pl-5 text-sm text-gray-300 space-y-1">
                        {preflight.map((item, idx) => <li key={idx}>{item}</li>)}
                      </ul>
                    </div>
                  )}
                  {commandPreview.length > 0 && (
                    <div>
                      <h4 className="text-xs font-semibold text-gray-400 uppercase tracking-wide mb-1">Exact command preview</h4>
                      <div className="space-y-2">
                        {commandPreview.map((item, idx) => (
                          <pre key={idx} className="overflow-x-auto rounded border border-gray-800 bg-gray-950 px-3 py-2 text-xs text-cyan-200">
                            {item}
                          </pre>
                        ))}
                      </div>
                    </div>
                  )}
                  {willNotChange.length > 0 && (
                    <div>
                      <h4 className="text-xs font-semibold text-gray-400 uppercase tracking-wide mb-1">Will not change</h4>
                      <ul className="list-disc pl-5 text-sm text-gray-300 space-y-1">
                        {willNotChange.map((item, idx) => <li key={idx}>{item}</li>)}
                      </ul>
                    </div>
                  )}
                  {writesTo.length > 0 && (
                    <div>
                      <h4 className="text-xs font-semibold text-gray-400 uppercase tracking-wide mb-1">Writes to</h4>
                      <ul className="list-disc pl-5 text-sm font-mono text-blue-400 space-y-1">
                        {writesTo.map((item, idx) => <li key={idx}>{item}</li>)}
                      </ul>
                    </div>
                  )}
                  {followUp.length > 0 && (
                    <div>
                      <h4 className="text-xs font-semibold text-gray-400 uppercase tracking-wide mb-1">After this step</h4>
                      <ul className="list-disc pl-5 text-sm text-gray-300 space-y-1">
                        {followUp.map((item, idx) => <li key={idx}>{item}</li>)}
                      </ul>
                    </div>
                  )}
                </div>
                <div className="mt-6 flex justify-end gap-3">
                  <button
                    type="button"
                    className="rounded border border-gray-600 bg-transparent px-4 py-2 text-sm text-gray-300 hover:bg-gray-800 disabled:opacity-50"
                    onClick={onCancel}
                    disabled={loading}
                  >
                    Cancel
                  </button>
                  <button
                    type="button"
                    className="rounded bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-500 disabled:opacity-50"
                    onClick={onConfirm}
                    disabled={loading}
                  >
                    {loading ? 'Processing…' : confirmLabel}
                  </button>
                </div>
              </DialogPanel>
            </TransitionChild>
          </div>
        </div>
      </Dialog>
    </Transition>
  )
}
