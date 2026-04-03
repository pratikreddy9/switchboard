import React, { Fragment } from 'react'
import { Dialog, Transition } from '@headlessui/react'
import type { ActionExplainConfig } from '../types/switchboard'

export const ACTION_EXPLAIN: Record<string, ActionExplainConfig> = {
  sync_to_node: { title: 'Sync to node', happens: ['Writes the selected service scope to the node scope snapshot.', 'Writes runtime config and named services for this location.', 'Mirrors managed-doc and task-ledger metadata to the node.'], untouched: ['Does not rename ids.', 'Does not change other services or sibling locations.', 'Does not run the project for you.'], writesTo: ['switchboard/node.manifest.json', 'switchboard/evidence/scope.snapshot.json'] },
  sync_from_node: { title: 'Sync from node', happens: ['Imports node scope, runtime config, and task ledger.', 'Updates control center configurations.'], untouched: ['Does not touch sibling locations.', 'Does not alter unselected services.'], writesTo: ['switchboard/manifests/services.json'] },
  runtime_check: { title: 'Run runtime check', happens: ['Connects to the server.', 'Checks ports and processes.'], untouched: ['Does not restart the application.', 'Does not alter application code.'], writesTo: ['switchboard/state/run/'] },
  pull_bundle: { title: 'Create bundle', happens: ['Copies files specified in scope.', 'Creates a zip or directory payload.'], untouched: ['Does not delete original files.', 'Does not deploy anything.'], writesTo: ['downloads/'] },
  workspace_health_check: { title: 'Run all health checks', happens: ['Iterates all services in workspace.', 'Calls runtime_check for each location.', 'Aggregates and returns per-service per-location results.'], untouched: ['Does not restart the applications.', 'Does not alter application code.'], writesTo: ['switchboard/state/run/'] },
}

export interface ConfirmationModalProps {
  open: boolean
  title: string
  willDo: string[]
  willNotChange: string[]
  writesTo: string[]
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
  onConfirm,
  onCancel,
  loading = false,
  confirmLabel = 'Proceed',
}: ConfirmationModalProps) {
  return (
    <Transition appear show={open} as={Fragment}>
      <Dialog as="div" className="relative z-50" onClose={() => !loading && onCancel()}>
        <Transition.Child
          as={Fragment}
          enter="ease-out duration-300"
          enterFrom="opacity-0"
          enterTo="opacity-100"
          leave="ease-in duration-200"
          leaveFrom="opacity-100"
          leaveTo="opacity-0"
        >
          <div className="fixed inset-0 bg-black/50" />
        </Transition.Child>

        <div className="fixed inset-0 overflow-y-auto">
          <div className="flex min-h-full items-center justify-center p-4 text-center">
            <Transition.Child
              as={Fragment}
              enter="ease-out duration-300"
              enterFrom="opacity-0 scale-95"
              enterTo="opacity-100 scale-100"
              leave="ease-in duration-200"
              leaveFrom="opacity-100 scale-100"
              leaveTo="opacity-0 scale-95"
            >
              <Dialog.Panel className="w-full max-w-md transform overflow-hidden rounded bg-surface p-6 text-left align-middle shadow-xl transition-all border border-border">
                <Dialog.Title as="h3" className="text-lg font-medium leading-6 text-text">
                  {title}
                </Dialog.Title>
                <div className="mt-4 space-y-4">
                  {willDo.length > 0 && (
                    <div>
                      <h4 className="text-sm font-semibold text-text-subtle mb-1">What will happen:</h4>
                      <ul className="list-disc pl-5 text-sm text-text space-y-1">
                        {willDo.map((item, idx) => (
                          <li key={idx}>{item}</li>
                        ))}
                      </ul>
                    </div>
                  )}
                  {willNotChange.length > 0 && (
                    <div>
                      <h4 className="text-sm font-semibold text-text-subtle mb-1">What will NOT change:</h4>
                      <ul className="list-disc pl-5 text-sm text-text space-y-1">
                        {willNotChange.map((item, idx) => (
                          <li key={idx}>{item}</li>
                        ))}
                      </ul>
                    </div>
                  )}
                  {writesTo.length > 0 && (
                    <div>
                      <h4 className="text-sm font-semibold text-text-subtle mb-1">Writes to:</h4>
                      <ul className="list-disc pl-5 text-sm font-mono text-primary space-y-1">
                        {writesTo.map((item, idx) => (
                          <li key={idx}>{item}</li>
                        ))}
                      </ul>
                    </div>
                  )}
                </div>

                <div className="mt-6 flex justify-end gap-3">
                  <button
                    type="button"
                    className="inline-flex justify-center rounded border border-border bg-transparent px-4 py-2 text-sm font-medium text-text hover:bg-surface-hover focus:outline-none disabled:opacity-50"
                    onClick={onCancel}
                    disabled={loading}
                  >
                    Cancel
                  </button>
                  <button
                    type="button"
                    className="inline-flex justify-center rounded border border-transparent bg-primary px-4 py-2 text-sm font-medium text-white hover:bg-primary-hover focus:outline-none disabled:opacity-50"
                    onClick={onConfirm}
                    disabled={loading}
                  >
                    {loading ? 'Processing...' : confirmLabel}
                  </button>
                </div>
              </Dialog.Panel>
            </Transition.Child>
          </div>
        </div>
      </Dialog>
    </Transition>
  )
}
