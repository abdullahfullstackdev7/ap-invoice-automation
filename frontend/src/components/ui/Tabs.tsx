import { useId, useState } from 'react'
import type { ReactNode } from 'react'

import { cn } from '@/lib/utils'

export interface TabItem {
  id: string
  label: string
  content: ReactNode
}

export function Tabs({ items, defaultId }: { items: TabItem[]; defaultId?: string }) {
  const [activeId, setActiveId] = useState(defaultId ?? items[0]?.id)
  const baseId = useId()
  const active = items.find((item) => item.id === activeId) ?? items[0]

  return (
    <div>
      <div role="tablist" aria-label="Role" className="flex flex-wrap justify-center gap-2">
        {items.map((item) => {
          const isActive = item.id === active?.id
          return (
            <button
              key={item.id}
              id={`${baseId}-tab-${item.id}`}
              role="tab"
              type="button"
              aria-selected={isActive}
              aria-controls={`${baseId}-panel-${item.id}`}
              onClick={() => setActiveId(item.id)}
              className={cn(
                'rounded-full px-4 py-2 text-sm font-medium transition-colors',
                isActive
                  ? 'bg-brand-navy text-white'
                  : 'bg-slate-100 text-slate-600 hover:bg-slate-200',
              )}
            >
              {item.label}
            </button>
          )
        })}
      </div>
      {items.map((item) => (
        <div
          key={item.id}
          id={`${baseId}-panel-${item.id}`}
          role="tabpanel"
          aria-labelledby={`${baseId}-tab-${item.id}`}
          hidden={item.id !== active?.id}
          className="mt-10"
        >
          {item.content}
        </div>
      ))}
    </div>
  )
}
