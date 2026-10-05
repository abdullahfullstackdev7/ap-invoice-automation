import { Download } from 'lucide-react'

import { Button } from '@/components/ui/Button'

type Row = object

function toCsv(rows: Row[]): string {
  if (rows.length === 0) return ''
  const headers = Object.keys(rows[0]!)
  const escape = (v: unknown) => {
    const text = v === null || v === undefined ? '' : String(v)
    return /[",\n]/.test(text) ? `"${text.replace(/"/g, '""')}"` : text
  }
  return [
    headers.join(','),
    ...rows.map((row) => headers.map((h) => escape((row as Record<string, unknown>)[h])).join(',')),
  ].join('\n')
}

export function ExportButton({ rows, filename }: { rows: Row[]; filename: string }) {
  return (
    <Button
      variant="outline"
      size="sm"
      disabled={rows.length === 0}
      onClick={() => {
        const blob = new Blob([toCsv(rows)], { type: 'text/csv;charset=utf-8' })
        const url = URL.createObjectURL(blob)
        const link = document.createElement('a')
        link.href = url
        link.download = filename
        link.click()
        URL.revokeObjectURL(url)
      }}
    >
      <Download className="size-4" aria-hidden="true" />
      Export CSV
    </Button>
  )
}
