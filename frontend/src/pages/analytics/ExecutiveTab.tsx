import type { EChartsOption } from 'echarts'
import { EChart } from '@/components/charts/EChart'
import { ExportButton } from '@/components/analytics/ExportButton'
import { KpiCard } from '@/components/analytics/KpiCard'
import { type AnalyticsFilterState } from '@/lib/analytics/filters'
import {
  type KpisResponse,
  type SavingsTrendPoint,
  type SpendByVendorResponse,
  type VolumeValuePoint,
  useAnalytics,
} from '@/lib/analytics/api'
import { formatCompactCurrency, formatCurrency, formatNumber, formatPercent } from '@/lib/format'
import { toApiParams } from '@/lib/analytics/filters'

export function ExecutiveTab({ filters }: { filters: AnalyticsFilterState }) {
  const params = toApiParams(filters)
  const kpis = useAnalytics<KpisResponse>('kpis', params)
  const volume = useAnalytics<VolumeValuePoint[]>('volume-value-trend', {
    ...params,
    granularity: 'month',
  })
  const savings = useAnalytics<SavingsTrendPoint[]>('savings-trend', {
    ...params,
    granularity: 'month',
  })
  const vendors = useAnalytics<SpendByVendorResponse>('spend-by-vendor', { ...params, limit: 10 })

  const k = kpis.data
  const pct = (key: keyof KpisResponse) => k?.[key].pct_change
  const prev = (key: keyof KpisResponse) => k?.[key].previous

  const volumeOption: EChartsOption = {
    tooltip: { trigger: 'axis' },
    legend: { data: ['Invoice value', 'Invoice count'] },
    xAxis: { type: 'category', data: volume.data?.map((p) => p.period) ?? [] },
    yAxis: [
      {
        type: 'value',
        name: 'Value (USD)',
        axisLabel: { formatter: (v: number) => formatCompactCurrency(v) },
      },
      { type: 'value', name: 'Count' },
    ],
    series: [
      { name: 'Invoice value', type: 'bar', data: volume.data?.map((p) => Number(p.value)) ?? [] },
      {
        name: 'Invoice count',
        type: 'line',
        yAxisIndex: 1,
        data: volume.data?.map((p) => p.invoices_count) ?? [],
      },
    ],
  }

  const cumulativeSavings = (savings.data ?? []).reduce<number[]>((series, p) => {
    const previous = series[series.length - 1] ?? 0
    const next = previous + Number(p.savings_prevented) + Number(p.discounts_captured)
    return [...series, Number(next.toFixed(2))]
  }, [])
  const savingsOption: EChartsOption = {
    tooltip: { trigger: 'axis' },
    xAxis: { type: 'category', data: savings.data?.map((p) => p.period) ?? [] },
    yAxis: { type: 'value', axisLabel: { formatter: (v: number) => formatCompactCurrency(v) } },
    series: [
      {
        name: 'Cumulative net savings',
        type: 'line',
        areaStyle: {},
        smooth: true,
        data: cumulativeSavings,
      },
    ],
  }

  const vendorOption: EChartsOption = {
    tooltip: { trigger: 'axis' },
    grid: { left: 160 },
    xAxis: { type: 'value', axisLabel: { formatter: (v: number) => formatCompactCurrency(v) } },
    yAxis: {
      type: 'category',
      data: [...(vendors.data?.items ?? [])].reverse().map((v) => v.vendor_name),
    },
    series: [
      {
        name: 'Spend',
        type: 'bar',
        data: [...(vendors.data?.items ?? [])].reverse().map((v) => Number(v.value)),
      },
    ],
  }

  return (
    <div className="flex flex-col gap-6">
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-6">
        <KpiCard
          label="Invoice value processed"
          value={formatCurrency(k?.total_value.current)}
          pctChange={pct('total_value')}
          compareEnabled={filters.compare}
          previousValue={formatCurrency(prev('total_value'))}
        />
        <KpiCard
          label="Invoices processed"
          value={formatNumber(
            typeof k?.total_invoices.current === 'number' ? k.total_invoices.current : null,
          )}
          pctChange={pct('total_invoices')}
          compareEnabled={filters.compare}
        />
        <KpiCard
          label="Straight-through rate"
          value={formatPercent(typeof k?.stp_rate.current === 'number' ? k.stp_rate.current : null)}
          pctChange={pct('stp_rate')}
          compareEnabled={filters.compare}
        />
        <KpiCard
          label="Avg cycle time"
          value={
            k?.avg_cycle_time_hours.current
              ? `${Number(k.avg_cycle_time_hours.current).toFixed(1)} h`
              : '-'
          }
          pctChange={pct('avg_cycle_time_hours')}
          invertGood
          compareEnabled={filters.compare}
        />
        <KpiCard
          label="Exception rate"
          value={formatPercent(
            typeof k?.exception_rate.current === 'number' ? k.exception_rate.current : null,
          )}
          pctChange={pct('exception_rate')}
          invertGood
          compareEnabled={filters.compare}
        />
        <KpiCard
          label="Discounts captured"
          value={formatCurrency(k?.discounts_captured.current)}
          pctChange={pct('discounts_captured')}
          compareEnabled={filters.compare}
        />
      </div>

      <section
        aria-labelledby="volume-heading"
        className="rounded-xl border border-slate-200 bg-white p-5"
      >
        <div className="mb-3 flex items-center justify-between">
          <h2 id="volume-heading" className="text-base font-semibold text-brand-navy">
            Monthly invoice value and count
          </h2>
          <ExportButton
            rows={(volume.data ?? []).map((p) => ({
              period: p.period,
              value: p.value,
              invoices_count: p.invoices_count,
            }))}
            filename="monthly_volume.csv"
          />
        </div>
        <EChart
          label="monthly invoice value and count"
          option={volumeOption}
          height={320}
          isLoading={volume.isLoading}
          isError={volume.isError}
          isEmpty={!volume.isLoading && (volume.data?.length ?? 0) === 0}
        />
      </section>

      <div className="grid gap-6 lg:grid-cols-2">
        <section
          aria-labelledby="savings-heading"
          className="rounded-xl border border-slate-200 bg-white p-5"
        >
          <h2 id="savings-heading" className="mb-3 text-base font-semibold text-brand-navy">
            Cumulative net savings
          </h2>
          <EChart
            label="cumulative savings"
            option={savingsOption}
            height={280}
            isLoading={savings.isLoading}
            isError={savings.isError}
            isEmpty={!savings.isLoading && cumulativeSavings.length === 0}
          />
        </section>
        <section
          aria-labelledby="vendor-heading"
          className="rounded-xl border border-slate-200 bg-white p-5"
        >
          <div className="mb-3 flex items-center justify-between">
            <h2 id="vendor-heading" className="text-base font-semibold text-brand-navy">
              Top 10 vendors by spend
            </h2>
            <ExportButton
              rows={(vendors.data?.items ?? []).map((v) => ({
                vendor: v.vendor_name,
                value: v.value,
                invoices_count: v.invoices_count,
              }))}
              filename="top_vendors.csv"
            />
          </div>
          <EChart
            label="top vendors by spend"
            option={vendorOption}
            height={280}
            isLoading={vendors.isLoading}
            isError={vendors.isError}
            isEmpty={!vendors.isLoading && (vendors.data?.items.length ?? 0) === 0}
          />
        </section>
      </div>
    </div>
  )
}
