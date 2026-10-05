import type { EChartsOption } from 'echarts'
import ReactECharts from 'echarts-for-react'
import { useEffect } from 'react'

import { CHART_THEME_NAME, registerChartTheme } from '@/components/charts/echarts-theme'

registerChartTheme()

interface EChartProps {
  option: EChartsOption
  height?: number
  isLoading?: boolean
  isError?: boolean
  isEmpty?: boolean
  label: string
  onEvents?: Record<string, (params: unknown) => void>
}

export function EChart({
  option,
  height = 300,
  isLoading,
  isError,
  isEmpty,
  label,
  onEvents,
}: EChartProps) {
  useEffect(() => {
    registerChartTheme()
  }, [])

  if (isLoading) {
    return (
      <div
        role="status"
        aria-label={`Loading ${label}`}
        style={{ height }}
        className="animate-pulse rounded-lg bg-slate-100"
      />
    )
  }
  if (isError) {
    return (
      <div
        role="alert"
        style={{ height }}
        className="flex items-center justify-center rounded-lg bg-(--color-danger-bg) text-sm text-(--color-danger)"
      >
        Could not load {label}.
      </div>
    )
  }
  if (isEmpty) {
    return (
      <div
        style={{ height }}
        className="flex items-center justify-center rounded-lg border border-dashed border-slate-300 text-sm text-slate-500"
      >
        No data for this period.
      </div>
    )
  }
  return (
    <div role="img" aria-label={label} style={{ height }}>
      <ReactECharts
        option={option}
        style={{ height: '100%', width: '100%' }}
        theme={CHART_THEME_NAME}
        onEvents={onEvents}
        notMerge
      />
    </div>
  )
}
