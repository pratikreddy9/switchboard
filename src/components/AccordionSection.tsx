import type { ReactNode } from 'react'
import { ChevronDown, ChevronRight } from 'lucide-react'

interface Props {
  title: string
  summary?: ReactNode
  open: boolean
  onToggle: () => void
  children: ReactNode
  icon?: ReactNode
  className?: string
}

export function AccordionSection({ title, summary, open, onToggle, children, icon, className = '' }: Props) {
  return (
    <section className={`mb-6 rounded-xl border border-gray-800 bg-gray-900 ${className}`.trim()}>
      <button
        type="button"
        onClick={onToggle}
        className="flex w-full items-center justify-between gap-3 p-4 text-left"
      >
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2 text-sm font-medium text-gray-300">
            {icon}
            <span>{title}</span>
          </div>
          {summary && <div className="mt-1 text-xs text-gray-500">{summary}</div>}
        </div>
        {open ? <ChevronDown className="h-4 w-4 text-gray-500" /> : <ChevronRight className="h-4 w-4 text-gray-500" />}
      </button>
      {open && <div className="border-t border-gray-800 p-4">{children}</div>}
    </section>
  )
}
