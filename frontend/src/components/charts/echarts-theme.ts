import * as echarts from 'echarts'

/** One palette for every chart, drawn from the design tokens in index.css
 * (brand navy/blue/teal plus the semantic colors). Series colors are
 * chosen to clear 3:1 against white for graphical objects. */
export const CHART_THEME_NAME = 'veridian'

export const CHART_PALETTE = [
  '#1f5eff',
  '#0b1f3a',
  '#115e59',
  '#b7791f',
  '#b91c1c',
  '#64748b',
  '#7c3aed',
  '#0e7490',
]

export function registerChartTheme() {
  echarts.registerTheme(CHART_THEME_NAME, {
    color: CHART_PALETTE,
    textStyle: { fontFamily: 'Inter, system-ui, sans-serif', color: '#334155' },
    axisLine: { lineStyle: { color: '#cbd5e1' } },
    splitLine: { lineStyle: { color: '#e2e8f0' } },
    categoryAxis: { axisLabel: { color: '#475569' } },
    valueAxis: { axisLabel: { color: '#475569' } },
    tooltip: {
      backgroundColor: '#ffffff',
      borderColor: '#cbd5e1',
      textStyle: { color: '#0f172a' },
    },
  })
}
