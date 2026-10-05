import { ArrowDownRight, ArrowUpRight, Minus } from 'lucide-react'

import { cn } from '@/lib/utils'

interface KpiCardProps {
  label: string
  value: string
  pctChange?: number | null
  /** true when a higher number is worse (exception rate, cycle time) */
  invertGood?: boolean
  compareEnabled: boolean
  previousValue?: string
}

export function KpiCard({
  label,
  value,
  pctChange,
  invertGood,
  compareEnabled,
  previousValue,
}: KpiCardProps) {
  const hasDelta = compareEnabled && pctChange !== null && pctChange !== undefined
  const up = hasDelta && pctChange > 0
  const good = hasDelta && (invertGood ? !up : up)
  return (
    <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
      <p className="text-sm text-slate-500">{label}</p>
      <p className="mt-2 text-2xl font-semibold text-brand-navy">{value}</p>
      {compareEnabled ? (
        <p className="mt-2 flex items-center gap-1 text-xs text-slate-500">
          {hasDelta ? (
            <span
              className={cn(
                'inline-flex items-center gap-0.5 font-medium',
                good
                  ? 'text-(--color-success)'
                  : pctChange === 0
                    ? 'text-slate-500'
                    : 'text-(--color-danger)',
              )}
            >
              {pctChange === 0 ? (
                <Minus className="size-3" aria-hidden="true" />
              ) : up ? (
                <ArrowUpRight className="size-3" aria-hidden="true" />
              ) : (
                <ArrowDownRight className="size-3" aria-hidden="true" />
              )}
              {Math.abs(pctChange).toFixed(1)}%
            </span>
          ) : (
            <span>No comparison</span>
          )}
          {previousValue ? <span>vs {previousValue}</span> : null}
        </p>
      ) : null}
    </div>
  )
}
