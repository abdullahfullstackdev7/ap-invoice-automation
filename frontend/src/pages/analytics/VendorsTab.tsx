import type { EChartsOption } from 'echarts'
import { ExportButton } from '@/components/analytics/ExportButton'
import { EChart } from '@/components/charts/EChart'
import { type VendorScorecardsResponse, useAnalytics } from '@/lib/analytics/api'
import { type AnalyticsFilterState } from '@/lib/analytics/filters'
import { formatCompactCurrency, formatCurrency, formatPercent } from '@/lib/format'

export function VendorsTab({ filters }: { filters: AnalyticsFilterState }) {
  const scorecards = useAnalytics<VendorScorecardsResponse>('vendor-scorecards', {
    date_from: filters.from,
    date_to: filters.to,
    limit: 200,
  })
  const items = scorecards.data?.items ?? []
  const plotted = items.filter((v) => v.exception_rate !== null)

  const scatterOption: EChartsOption = {
    tooltip: {
      formatter: (raw: unknown) => {
        const p = raw as { data: [number, number, number, string] }
        return `${p.data[3]}<br/>Spend ${formatCurrency(p.data[0])}<br/>Exception rate ${formatPercent(p.data[1])}<br/>Invoices ${p.data[2]}`
      },
    },
    xAxis: {
      type: 'value',
      name: 'Spend (USD)',
      axisLabel: { formatter: (v: number) => formatCompactCurrency(v) },
    },
    yAxis: { type: 'value', name: 'Exception rate (%)' },
    series: [
      {
        type: 'scatter',
        symbolSize: (d: number[]) => Math.max(8, Math.min(48, d[2] * 3)),
        data: plotted.map((v) => [
          Number(v.value),
          v.exception_rate,
          v.invoices_count,
          v.vendor_name,
        ]),
      },
    ],
  }

  return (
    <div className="flex flex-col gap-6">
      <section
        aria-labelledby="scatter-heading"
        className="rounded-xl border border-slate-200 bg-white p-5"
      >
        <h2 id="scatter-heading" className="mb-1 text-base font-semibold text-brand-navy">
          Exception rate vs spend
        </h2>
        <p className="mb-3 text-xs text-slate-500">Bubble size is invoice count.</p>
        <EChart
          label="exception rate versus spend by vendor"
          option={scatterOption}
          height={340}
          isLoading={scorecards.isLoading}
          isError={scorecards.isError}
          isEmpty={!scorecards.isLoading && plotted.length === 0}
        />
      </section>

      <section
        aria-labelledby="scorecard-heading"
        className="rounded-xl border border-slate-200 bg-white p-5"
      >
        <div className="mb-3 flex items-center justify-between">
          <h2 id="scorecard-heading" className="text-base font-semibold text-brand-navy">
            Vendor scorecards
          </h2>
          <ExportButton
            rows={items.map((v) => ({
              vendor: v.vendor_name,
              invoices: v.invoices_count,
              value: v.value,
              exception_rate: v.exception_rate,
              stp_rate: v.stp_rate,
            }))}
            filename="vendor_scorecards.csv"
          />
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm">
            <caption className="sr-only">Vendor scorecards for the selected period</caption>
            <thead className="border-b border-slate-200 text-xs uppercase text-slate-500">
              <tr>
                <th scope="col" className="py-2 pr-4">
                  Vendor
                </th>
                <th scope="col" className="py-2 pr-4 text-right">
                  Invoices
                </th>
                <th scope="col" className="py-2 pr-4 text-right">
                  Spend
                </th>
                <th scope="col" className="py-2 pr-4 text-right">
                  Exception rate
                </th>
                <th scope="col" className="py-2 text-right">
                  STP rate
                </th>
              </tr>
            </thead>
            <tbody>
              {items.map((v) => (
                <tr key={v.vendor_id} className="border-b border-slate-100">
                  <td className="py-2 pr-4">{v.vendor_name}</td>
                  <td className="py-2 pr-4 text-right tabular-nums">{v.invoices_count}</td>
                  <td className="py-2 pr-4 text-right tabular-nums">{formatCurrency(v.value)}</td>
                  <td className="py-2 pr-4 text-right tabular-nums">
                    {formatPercent(v.exception_rate)}
                  </td>
                  <td className="py-2 text-right tabular-nums">{formatPercent(v.stp_rate)}</td>
                </tr>
              ))}
              {items.length === 0 && !scorecards.isLoading ? (
                <tr>
                  <td colSpan={5} className="py-6 text-center text-slate-500">
                    No vendor activity in this period.
                  </td>
                </tr>
              ) : null}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  )
}
