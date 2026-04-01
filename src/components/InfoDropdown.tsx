import { useEffect, useRef, useState } from 'react'
import { ChevronDown } from 'lucide-react'

interface Props {
  label: string
  title: string
  lines: string[]
}

export function InfoDropdown({ label, title, lines }: Props) {
  const [open, setOpen] = useState(false)
  const rootRef = useRef<HTMLDivElement | null>(null)

  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (!rootRef.current?.contains(event.target as Node)) {
        setOpen(false)
      }
    }
    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [])

  return (
    <div ref={rootRef} className="relative">
      <button
        type="button"
        aria-expanded={open}
        onClick={() => setOpen((current) => !current)}
        className="inline-flex items-center gap-2 rounded-lg border border-gray-800 bg-gray-900 px-3 py-2 text-xs text-gray-300 transition-colors hover:border-cyan-500 hover:text-white"
      >
        {label}
        <ChevronDown className={`h-3.5 w-3.5 transition-transform ${open ? 'rotate-180' : ''}`} />
      </button>

      {open && (
        <div className="absolute right-0 z-20 mt-2 w-96 rounded-xl border border-gray-800 bg-gray-950 p-4 shadow-2xl">
          <div className="text-sm font-medium text-white">{title}</div>
          <div className="mt-3 space-y-2 text-sm text-gray-300">
            {lines.map((line) => (
              <div key={line} className="rounded-lg border border-gray-800 bg-gray-900 px-3 py-2">
                {line}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
