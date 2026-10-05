import { useQuery } from '@tanstack/react-query'
import { useId } from 'react'

import { apiRequest } from '@/lib/api-client'
import {
  type AnalyticsFilterState,
  type DatePreset,
  PRESET_LABELS,
  rangeForPreset,
} from '@/lib/analytics/filters'

interface VendorOption {
  id: string
  name: string
}

export function FiltersBar({
  state,
  onChange,
  categories,
}: {
  state: AnalyticsFilterState
  onChange: (next: AnalyticsFilterState) => void
  categories: string[]
}) {
  const baseId = useId()
  const vendorsQuery = useQuery({
    queryKey: ['vendors', 'options'],
    queryFn: () => apiRequest<{ items: { id: string; name: string }[] }>('/vendors?limit=200'),
  })
  const vendors: VendorOption[] = vendorsQuery.data?.items ?? []

  function setPreset(preset: DatePreset) {
    if (preset === 'custom') {
      onChange({ ...state, preset })
      return
    }
    const range = rangeForPreset(preset)
    onChange({ ...state, preset, from: range.from, to: range.to })
  }

  return (
    <div className="flex flex-wrap items-end gap-4 rounded-xl border border-slate-200 bg-white p-4">
      <div>
        <label
          htmlFor={`${baseId}-preset`}
          className="mb-1 block text-xs font-medium text-slate-600"
        >
          Period
        </label>
        <select
          id={`${baseId}-preset`}
          value={state.preset}
          onChange={(e) => setPreset(e.target.value as DatePreset)}
          className="rounded-lg border border-slate-300 px-3 py-2 text-sm"
        >
          {(Object.keys(PRESET_LABELS) as DatePreset[]).map((p) => (
            <option key={p} value={p}>
              {PRESET_LABELS[p]}
            </option>
          ))}
        </select>
      </div>
      {state.preset === 'custom' ? (
        <>
          <div>
            <label
              htmlFor={`${baseId}-from`}
              className="mb-1 block text-xs font-medium text-slate-600"
            >
              From
            </label>
            <input
              id={`${baseId}-from`}
              type="date"
              value={state.from}
              onChange={(e) => onChange({ ...state, from: e.target.value })}
              className="rounded-lg border border-slate-300 px-3 py-2 text-sm"
            />
          </div>
          <div>
            <label
              htmlFor={`${baseId}-to`}
              className="mb-1 block text-xs font-medium text-slate-600"
            >
              To
            </label>
            <input
              id={`${baseId}-to`}
              type="date"
              value={state.to}
              onChange={(e) => onChange({ ...state, to: e.target.value })}
              className="rounded-lg border border-slate-300 px-3 py-2 text-sm"
            />
          </div>
        </>
      ) : null}
      <div>
        <label
          htmlFor={`${baseId}-vendor`}
          className="mb-1 block text-xs font-medium text-slate-600"
        >
          Vendor
        </label>
        <select
          id={`${baseId}-vendor`}
          value={state.vendorId ?? ''}
          onChange={(e) => onChange({ ...state, vendorId: e.target.value || null })}
          className="rounded-lg border border-slate-300 px-3 py-2 text-sm"
        >
          <option value="">All vendors</option>
          {vendors.map((v) => (
            <option key={v.id} value={v.id}>
              {v.name}
            </option>
          ))}
        </select>
      </div>
      <div>
        <label
          htmlFor={`${baseId}-category`}
          className="mb-1 block text-xs font-medium text-slate-600"
        >
          Category
        </label>
        <select
          id={`${baseId}-category`}
          value={state.category ?? ''}
          onChange={(e) => onChange({ ...state, category: e.target.value || null })}
          className="rounded-lg border border-slate-300 px-3 py-2 text-sm"
        >
          <option value="">All categories</option>
          {categories.map((c) => (
            <option key={c} value={c}>
              {c}
            </option>
          ))}
        </select>
      </div>
      <label className="flex items-center gap-2 pb-2 text-sm text-slate-700">
        <input
          type="checkbox"
          checked={state.compare}
          onChange={(e) => onChange({ ...state, compare: e.target.checked })}
          className="size-4"
        />
        Compare to previous period
      </label>
    </div>
  )
}
