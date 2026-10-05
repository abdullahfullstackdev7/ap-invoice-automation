import type { EChartsOption } from 'echarts'
import { EChart } from '@/components/charts/EChart'
import { ExportButton } from '@/components/analytics/ExportButton'
import { KpiCard } from '@/components/analytics/KpiCard'
import {
  type CycleTimeResponse,
  type ExceptionsByReasonItem,
  type ExceptionsTrendPoint,
  type HeatmapTimeCell,
  type SlaComplianceResponse,
  type WorkflowFunnelItem,
  useAnalytics,
} from '@/lib/analytics/api'
import { type AnalyticsFilterState, toApiParams } from '@/lib/analytics/filters'
import { formatPercent } from '@/lib/format'

const WEEKDAYS = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
const FUNNEL_ORDER = [
  'uploaded',
  'ocr_done',
  'extracted',
  'matched',
  'auto_approved',
  'exception',
  'blocked',
  'approved',
  'paid',
  'needs_review',
]

export function OperationsTab({ filters }: { filters: AnalyticsFilterState }) {
  const params = toApiParams(filters)
  const funnel = useAnalytics<WorkflowFunnelItem[]>('workflow-funnel', params)
  const byReason = useAnalytics<ExceptionsByReasonItem[]>('exceptions-by-reason', params)
  const trend = useAnalytics<ExceptionsTrendPoint[]>('exceptions-trend', {
    ...params,
    granularity: 'week',
  })
  const cycle = useAnalytics<CycleTimeResponse>('cycle-time', params)
  const sla = useAnalytics<SlaComplianceResponse>('sla-compliance', params)
  const heat = useAnalytics<HeatmapTimeCell[]>('exception-heatmap-time', params)

  const funnelRows = FUNNEL_ORDER.map((status) => ({
    status,
    count: funnel.data?.find((f) => f.status === status)?.count ?? 0,
  })).filter((r) => r.count > 0)
  const funnelOption: EChartsOption = {
    tooltip: { trigger: 'item' },
    series: [
      {
        type: 'funnel',
        left: '10%',
        width: '80%',
        sort: 'descending',
        label: { formatter: '{b}: {c}' },
        data: funnelRows.map((r) => ({ name: r.status.replace('_', ' '), value: r.count })),
      },
    ],
  }

  const reasonOption: EChartsOption = {
    tooltip: { trigger: 'axis' },
    xAxis: { type: 'category', data: byReason.data?.map((r) => r.reason_code) ?? [] },
    yAxis: { type: 'value', name: 'Exceptions' },
    series: [{ type: 'bar', data: byReason.data?.map((r) => r.count) ?? [] }],
  }

  const trendOption: EChartsOption = {
    tooltip: { trigger: 'axis' },
    xAxis: { type: 'category', data: trend.data?.map((p) => p.period) ?? [] },
    yAxis: { type: 'value', name: 'Exceptions opened' },
    series: [
      { type: 'line', areaStyle: {}, smooth: true, data: trend.data?.map((p) => p.count) ?? [] },
    ],
  }

  const dist = cycle.data?.distribution ?? {}
  const cycleOption: EChartsOption = {
    tooltip: { trigger: 'axis' },
    xAxis: { type: 'category', data: Object.keys(dist) },
    yAxis: { type: 'value', name: 'Invoices' },
    series: [{ type: 'bar', data: Object.values(dist) }],
  }

  const heatData = (heat.data ?? []).map((c) => [c.hour, c.weekday, c.count])
  const heatMax = Math.max(1, ...(heat.data ?? []).map((c) => c.count))
  const heatOption: EChartsOption = {
    tooltip: { position: 'top' },
    grid: { height: '60%', top: 10 },
    xAxis: {
      type: 'category',
      data: Array.from({ length: 24 }, (_, h) => `${h}:00`),
      splitArea: { show: true },
    },
    yAxis: { type: 'category', data: WEEKDAYS, splitArea: { show: true } },
    visualMap: {
      min: 0,
      max: heatMax,
      calculable: true,
      orient: 'horizontal',
      left: 'center',
      bottom: 0,
      inRange: { color: ['#eff6ff', '#1f5eff'] },
    },
    series: [{ type: 'heatmap', data: heatData, label: { show: false } }],
  }

  const slaPct = sla.data?.sla_compliance_pct ?? null
  const slaGauge: EChartsOption = {
    series: [
      {
        type: 'gauge',
        min: 0,
        max: 100,
        progress: { show: true },
        detail: { formatter: '{value}%' },
        data: [{ value: slaPct ?? 0 }],
      },
    ],
  }

  return (
    <div className="flex flex-col gap-6">
      <div className="grid gap-4 sm:grid-cols-3">
        <KpiCard label="SLA compliance" value={formatPercent(slaPct)} compareEnabled={false} />
        <KpiCard
          label="Overdue, still open"
          value={String(sla.data?.overdue_open_count ?? '-')}
          compareEnabled={false}
        />
        <KpiCard
          label="Resolved in period"
          value={String(sla.data?.resolved_count ?? '-')}
          compareEnabled={false}
        />
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        <section
          aria-labelledby="funnel-heading"
          className="rounded-xl border border-slate-200 bg-white p-5"
        >
          <h2 id="funnel-heading" className="mb-3 text-base font-semibold text-brand-navy">
            Workflow funnel
          </h2>
          <EChart
            label="workflow funnel"
            option={funnelOption}
            height={320}
            isLoading={funnel.isLoading}
            isError={funnel.isError}
            isEmpty={!funnel.isLoading && funnelRows.length === 0}
          />
        </section>
        <section
          aria-labelledby="sla-heading"
          className="rounded-xl border border-slate-200 bg-white p-5"
        >
          <h2 id="sla-heading" className="mb-3 text-base font-semibold text-brand-navy">
            SLA compliance
          </h2>
          <EChart
            label="SLA compliance gauge"
            option={slaGauge}
            height={320}
            isLoading={sla.isLoading}
            isError={sla.isError}
            isEmpty={!sla.isLoading && slaPct === null}
          />
        </section>
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        <section
          aria-labelledby="reason-heading"
          className="rounded-xl border border-slate-200 bg-white p-5"
        >
          <div className="mb-3 flex items-center justify-between">
            <h2 id="reason-heading" className="text-base font-semibold text-brand-navy">
              Exceptions by reason code
            </h2>
            <ExportButton rows={byReason.data ?? []} filename="exceptions_by_reason.csv" />
          </div>
          <EChart
            label="exceptions by reason code"
            option={reasonOption}
            height={280}
            isLoading={byReason.isLoading}
            isError={byReason.isError}
            isEmpty={!byReason.isLoading && (byReason.data?.length ?? 0) === 0}
          />
        </section>
        <section
          aria-labelledby="trend-heading"
          className="rounded-xl border border-slate-200 bg-white p-5"
        >
          <h2 id="trend-heading" className="mb-3 text-base font-semibold text-brand-navy">
            Exception trend (weekly)
          </h2>
          <EChart
            label="exception trend"
            option={trendOption}
            height={280}
            isLoading={trend.isLoading}
            isError={trend.isError}
            isEmpty={!trend.isLoading && (trend.data?.length ?? 0) === 0}
          />
        </section>
        <section
          aria-labelledby="cycle-heading"
          className="rounded-xl border border-slate-200 bg-white p-5"
        >
          <h2 id="cycle-heading" className="mb-3 text-base font-semibold text-brand-navy">
            Cycle time distribution
          </h2>
          <EChart
            label="cycle time distribution"
            option={cycleOption}
            height={280}
            isLoading={cycle.isLoading}
            isError={cycle.isError}
            isEmpty={!cycle.isLoading && (cycle.data?.sample_size ?? 0) === 0}
          />
        </section>
        <section
          aria-labelledby="heat-heading"
          className="rounded-xl border border-slate-200 bg-white p-5"
        >
          <h2 id="heat-heading" className="mb-3 text-base font-semibold text-brand-navy">
            Exception heatmap by weekday and hour (UTC)
          </h2>
          <EChart
            label="exception heatmap"
            option={heatOption}
            height={280}
            isLoading={heat.isLoading}
            isError={heat.isError}
            isEmpty={!heat.isLoading && (heat.data?.length ?? 0) === 0}
          />
        </section>
      </div>
    </div>
  )
}
