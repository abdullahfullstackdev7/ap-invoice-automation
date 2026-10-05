import { Printer } from 'lucide-react'
import { useMemo } from 'react'
import { useSearchParams } from 'react-router-dom'

import { FiltersBar } from '@/components/analytics/FiltersBar'
import { Button } from '@/components/ui/Button'
import { type SpendByCategoryResponse, useAnalytics } from '@/lib/analytics/api'
import {
  type AnalyticsFilterState,
  filtersFromSearchParams,
  filtersToSearchParams,
  toApiParams,
} from '@/lib/analytics/filters'
import { cn } from '@/lib/utils'
import { ExecutiveTab } from '@/pages/analytics/ExecutiveTab'
import { OperationsTab } from '@/pages/analytics/OperationsTab'
import { PlatformTab } from '@/pages/analytics/PlatformTab'
import { SavingsCashTab } from '@/pages/analytics/SavingsCashTab'
import { VendorsTab } from '@/pages/analytics/VendorsTab'

const TABS = [
  { id: 'executive', label: 'Executive' },
  { id: 'operations', label: 'Operations' },
  { id: 'vendors', label: 'Vendors' },
  { id: 'savings', label: 'Savings and Cash' },
  { id: 'platform', label: 'Platform' },
] as const

type TabId = (typeof TABS)[number]['id']

export function AnalyticsPage() {
  const [searchParams, setSearchParams] = useSearchParams()
  const filters = useMemo(() => filtersFromSearchParams(searchParams), [searchParams])
  const tabParam = searchParams.get('tab')
  const activeTab: TabId = TABS.some((t) => t.id === tabParam) ? (tabParam as TabId) : 'executive'

  const categoriesQuery = useAnalytics<SpendByCategoryResponse>(
    'spend-by-category',
    toApiParams(filters),
  )
  const categories = (categoriesQuery.data?.items ?? [])
    .map((c) => c.category)
    .filter((c) => c !== 'Uncategorized')

  function updateFilters(next: AnalyticsFilterState) {
    const params = filtersToSearchParams(next)
    params.set('tab', activeTab)
    setSearchParams(params, { replace: true })
  }

  function selectTab(id: TabId) {
    const params = new URLSearchParams(searchParams)
    params.set('tab', id)
    setSearchParams(params, { replace: true })
  }

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="font-serif text-2xl font-semibold text-brand-navy">
            Financial performance
          </h1>
          <p className="text-sm text-slate-500">
            {filters.from} to {filters.to}
          </p>
        </div>
        <Button variant="outline" size="sm" onClick={() => window.print()}>
          <Printer className="size-4" aria-hidden="true" />
          Print
        </Button>
      </div>

      <FiltersBar state={filters} onChange={updateFilters} categories={categories} />

      <div
        role="tablist"
        aria-label="Analytics sections"
        className="flex flex-wrap gap-2 border-b border-slate-200"
      >
        {TABS.map((tab) => (
          <button
            key={tab.id}
            id={`tab-${tab.id}`}
            role="tab"
            type="button"
            aria-selected={activeTab === tab.id}
            aria-controls={`panel-${tab.id}`}
            onClick={() => selectTab(tab.id)}
            className={cn(
              '-mb-px border-b-2 px-4 py-2 text-sm font-medium',
              activeTab === tab.id
                ? 'border-brand-blue text-brand-navy'
                : 'border-transparent text-slate-500 hover:text-slate-700',
            )}
          >
            {tab.label}
          </button>
        ))}
      </div>

      <div role="tabpanel" id={`panel-${activeTab}`} aria-labelledby={`tab-${activeTab}`}>
        {activeTab === 'executive' ? <ExecutiveTab filters={filters} /> : null}
        {activeTab === 'operations' ? <OperationsTab filters={filters} /> : null}
        {activeTab === 'vendors' ? <VendorsTab filters={filters} /> : null}
        {activeTab === 'savings' ? <SavingsCashTab filters={filters} /> : null}
        {activeTab === 'platform' ? <PlatformTab filters={filters} /> : null}
      </div>
    </div>
  )
}
