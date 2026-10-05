import type { EChartsOption } from 'echarts'
import { KpiCard } from '@/components/analytics/KpiCard'
import { EChart } from '@/components/charts/EChart'
import {
  type ExtractionAccuracyResponse,
  type LlmUsageDailyPoint,
  type LlmUsageResponse,
  useAnalytics,
} from '@/lib/analytics/api'
import { type AnalyticsFilterState } from '@/lib/analytics/filters'
import { formatNumber, formatPercent } from '@/lib/format'

export function PlatformTab({ filters }: { filters: AnalyticsFilterState }) {
  const range = { date_from: filters.from, date_to: filters.to }
  const llm = useAnalytics<LlmUsageResponse>('llm-usage', range)
  const llmDaily = useAnalytics<LlmUsageDailyPoint[]>('llm-usage-daily', range)
  const accuracy = useAnalytics<ExtractionAccuracyResponse>('extraction-accuracy', {})

  const providers = llm.data?.by_provider ?? {}
  const providerRows = Object.entries(providers)
  const totalTokens = Object.values(providers).reduce(
    (acc, p) => acc + p.tokens_in + p.tokens_out,
    0,
  )
  const invoicesInPeriod = llm.data ? llm.data.total_calls + llm.data.calls_avoided_by_rules : 0
  const avgTokens = invoicesInPeriod ? Math.round(totalTokens / invoicesInPeriod) : null

  const days = [...new Set((llmDaily.data ?? []).map((d) => d.day))].sort()
  const providerNames = [...new Set((llmDaily.data ?? []).map((d) => d.provider))]
  const tokensByDayOption: EChartsOption = {
    tooltip: { trigger: 'axis' },
    legend: { data: providerNames },
    xAxis: { type: 'category', data: days },
    yAxis: { type: 'value', name: 'Tokens' },
    series: providerNames.map((name) => ({
      name,
      type: 'bar',
      stack: 'tokens',
      data: days.map((day) => {
        const row = (llmDaily.data ?? []).find((d) => d.day === day && d.provider === name)
        return row ? row.tokens_in + row.tokens_out : 0
      }),
    })),
  }

  const shareOption: EChartsOption = {
    tooltip: { trigger: 'item' },
    series: [
      {
        type: 'pie',
        radius: ['40%', '70%'],
        data: providerRows.map(([name, p]) => ({ name, value: p.calls })),
      },
    ],
  }

  return (
    <div className="flex flex-col gap-6">
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <KpiCard
          label="Rules-only share"
          value={formatPercent(llm.data?.rules_only_rate ?? null)}
          compareEnabled={false}
        />
        <KpiCard
          label="LLM calls"
          value={formatNumber(llm.data?.total_calls ?? null)}
          compareEnabled={false}
        />
        <KpiCard
          label="Calls avoided by rules"
          value={formatNumber(llm.data?.calls_avoided_by_rules ?? null)}
          compareEnabled={false}
        />
        <KpiCard
          label="Avg tokens per invoice"
          value={avgTokens === null ? '-' : formatNumber(avgTokens)}
          compareEnabled={false}
        />
      </div>
      <div className="grid gap-6 lg:grid-cols-2">
        <section
          aria-labelledby="tok-heading"
          className="rounded-xl border border-slate-200 bg-white p-5"
        >
          <h2 id="tok-heading" className="mb-3 text-base font-semibold text-brand-navy">
            LLM tokens by provider and day
          </h2>
          <EChart
            label="LLM tokens by day and provider"
            option={tokensByDayOption}
            height={300}
            isLoading={llmDaily.isLoading}
            isError={llmDaily.isError}
            isEmpty={!llmDaily.isLoading && days.length === 0}
          />
        </section>
        <section
          aria-labelledby="share-heading"
          className="rounded-xl border border-slate-200 bg-white p-5"
        >
          <h2 id="share-heading" className="mb-3 text-base font-semibold text-brand-navy">
            Calls by provider
          </h2>
          <EChart
            label="calls by provider"
            option={shareOption}
            height={300}
            isLoading={llm.isLoading}
            isError={llm.isError}
            isEmpty={!llm.isLoading && providerRows.length === 0}
          />
        </section>
      </div>
      <section
        aria-labelledby="acc-heading"
        className="rounded-xl border border-slate-200 bg-white p-5"
      >
        <h2 id="acc-heading" className="mb-2 text-base font-semibold text-brand-navy">
          Extraction and matching accuracy
        </h2>
        <p className="text-sm text-slate-600">
          {accuracy.data?.note ?? 'Loading accuracy record...'}
        </p>
        <p className="mt-2 text-xs text-slate-500">
          This is a single snapshot from the latest evaluation run. No per-run history is stored in
          the database, so there is no accuracy-over-time series yet.
        </p>
      </section>
    </div>
  )
}
