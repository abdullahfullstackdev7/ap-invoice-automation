import type { EChartsOption } from 'echarts'
import { ExportButton } from '@/components/analytics/ExportButton'
import { EChart } from '@/components/charts/EChart'
import {
  type AgingBucket,
  type CashflowWeek,
  type SavingsTrendPoint,
  useAnalytics,
} from '@/lib/analytics/api'
import { type AnalyticsFilterState, toApiParams } from '@/lib/analytics/filters'
import { formatCompactCurrency } from '@/lib/format'

interface SavingsSummary {
  duplicates_blocked: { count: number; value: string }
  price_drift_prevented: { count: number; value: string }
  over_receipt_prevented: { count: number; value: string }
  discounts_captured: { value: string }
  discounts_missed: { value: string }
}

const money = (v: number) => (v > 0 ? formatCompactCurrency(v) : '$0')

export function SavingsCashTab({ filters }: { filters: AnalyticsFilterState }) {
  const params = toApiParams(filters)
  const savings = useAnalytics<SavingsSummary>('savings', params)
  const trend = useAnalytics<SavingsTrendPoint[]>('savings-trend', {
    ...params,
    granularity: 'month',
  })
  const aging = useAnalytics<AgingBucket[]>('aging', params)
  const cashflow = useAnalytics<CashflowWeek[]>('cashflow-forecast', {
    vendor_id: params.vendor_id,
    category: params.category,
    horizon_days: 90,
  })

  const s = savings.data
  const duplicates = Number(s?.duplicates_blocked.value ?? 0)
  const priceDrift = Number(s?.price_drift_prevented.value ?? 0)
  const overReceipt = Number(s?.over_receipt_prevented.value ?? 0)
  const gross = duplicates + priceDrift + overReceipt

  const steps = [
    { name: 'Duplicates blocked', value: duplicates },
    { name: 'Price variance prevented', value: priceDrift },
    { name: 'Over-receipt prevented', value: overReceipt },
  ]
  const base: number[] = []
  const bar: number[] = []
  let running = 0
  for (const step of steps) {
    base.push(running)
    bar.push(step.value)
    running += step.value
  }
  base.push(0)
  bar.push(Number(running.toFixed(2)))

  const waterfallOption: EChartsOption = {
    tooltip: { trigger: 'axis' },
    xAxis: { type: 'category', data: [...steps.map((x) => x.name), 'Net savings'] },
    yAxis: { type: 'value', axisLabel: { formatter: (v: number) => formatCompactCurrency(v) } },
    series: [
      { type: 'bar', stack: 'w', itemStyle: { color: 'transparent' }, data: base },
      { type: 'bar', stack: 'w', name: 'Amount', data: bar },
    ],
  }

  const discountOption: EChartsOption = {
    tooltip: { trigger: 'axis' },
    legend: { data: ['Captured', 'Missed'] },
    xAxis: { type: 'category', data: trend.data?.map((p) => p.period) ?? [] },
    yAxis: { type: 'value', axisLabel: { formatter: (v: number) => formatCompactCurrency(v) } },
    series: [
      {
        name: 'Captured',
        type: 'bar',
        stack: 'd',
        data: trend.data?.map((p) => Number(p.discounts_captured)) ?? [],
      },
      {
        name: 'Missed',
        type: 'bar',
        stack: 'd',
        data: trend.data?.map((p) => Number(p.discounts_missed)) ?? [],
      },
    ],
  }

  const cashOption: EChartsOption = {
    tooltip: { trigger: 'axis' },
    xAxis: { type: 'category', data: cashflow.data?.map((w) => w.week_starting) ?? [] },
    yAxis: { type: 'value', axisLabel: { formatter: (v: number) => formatCompactCurrency(v) } },
    series: [
      {
        name: 'Scheduled outflow',
        type: 'bar',
        data: cashflow.data?.map((w) => Number(w.amount)) ?? [],
      },
    ],
  }

  const agingOption: EChartsOption = {
    tooltip: { trigger: 'axis' },
    xAxis: { type: 'category', data: aging.data?.map((b) => b.bucket.replace('_', '-')) ?? [] },
    yAxis: { type: 'value', axisLabel: { formatter: (v: number) => formatCompactCurrency(v) } },
    series: [
      { name: 'Outstanding', type: 'bar', data: aging.data?.map((b) => Number(b.value)) ?? [] },
    ],
  }

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-wrap gap-6 text-sm text-slate-600">
        <span>
          Gross exposure avoided: <strong className="text-brand-navy">{money(gross)}</strong>
        </span>
        <span>
          Discounts captured:{' '}
          <strong className="text-brand-navy">
            {money(Number(s?.discounts_captured.value ?? 0))}
          </strong>
        </span>
        <span>
          Discounts missed:{' '}
          <strong className="text-brand-navy">
            {money(Number(s?.discounts_missed.value ?? 0))}
          </strong>
        </span>
      </div>
      <div className="grid gap-6 lg:grid-cols-2">
        <section
          aria-labelledby="waterfall-heading"
          className="rounded-xl border border-slate-200 bg-white p-5"
        >
          <h2 id="waterfall-heading" className="mb-3 text-base font-semibold text-brand-navy">
            Savings waterfall
          </h2>
          <EChart
            label="savings waterfall"
            option={waterfallOption}
            height={300}
            isLoading={savings.isLoading}
            isError={savings.isError}
            isEmpty={!savings.isLoading && gross === 0}
          />
        </section>
        <section
          aria-labelledby="disc-heading"
          className="rounded-xl border border-slate-200 bg-white p-5"
        >
          <div className="mb-3 flex items-center justify-between">
            <h2 id="disc-heading" className="text-base font-semibold text-brand-navy">
              Discounts captured vs missed by month
            </h2>
            <ExportButton
              rows={(trend.data ?? []).map((p) => ({
                period: p.period,
                captured: p.discounts_captured,
                missed: p.discounts_missed,
              }))}
              filename="discounts_by_month.csv"
            />
          </div>
          <EChart
            label="discounts captured versus missed"
            option={discountOption}
            height={300}
            isLoading={trend.isLoading}
            isError={trend.isError}
            isEmpty={!trend.isLoading && (trend.data?.length ?? 0) === 0}
          />
        </section>
        <section
          aria-labelledby="cash-heading"
          className="rounded-xl border border-slate-200 bg-white p-5"
        >
          <h2 id="cash-heading" className="mb-3 text-base font-semibold text-brand-navy">
            Cash outflow forecast (next 90 days, by week)
          </h2>
          <EChart
            label="cash outflow forecast"
            option={cashOption}
            height={300}
            isLoading={cashflow.isLoading}
            isError={cashflow.isError}
            isEmpty={!cashflow.isLoading && (cashflow.data?.length ?? 0) === 0}
          />
        </section>
        <section
          aria-labelledby="aging-heading"
          className="rounded-xl border border-slate-200 bg-white p-5"
        >
          <h2 id="aging-heading" className="mb-3 text-base font-semibold text-brand-navy">
            AP aging
          </h2>
          <EChart
            label="AP aging buckets"
            option={agingOption}
            height={300}
            isLoading={aging.isLoading}
            isError={aging.isError}
            isEmpty={!aging.isLoading && (aging.data ?? []).every((b) => b.count === 0)}
          />
        </section>
      </div>
    </div>
  )
}
