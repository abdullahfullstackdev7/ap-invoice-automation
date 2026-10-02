/** A built-with-CSS stand-in for a real product screenshot. Plan.md section
 * 10 asks for a Playwright-captured screenshot of the running app; this
 * sandbox doesn't run a seeded, screenshot-ready instance, and no external
 * stock photo service is reachable here either (see docs/image-credits.md),
 * so this mockup is a deliberate, documented substitute. */
export function DashboardMockup() {
  const bars = [62, 80, 45, 90, 70, 55, 85]

  return (
    <div className="rounded-2xl border border-slate-200 bg-white shadow-2xl">
      <div className="flex items-center gap-1.5 rounded-t-2xl border-b border-slate-200 bg-slate-50 px-4 py-3">
        <span className="size-2.5 rounded-full bg-red-300" />
        <span className="size-2.5 rounded-full bg-amber-300" />
        <span className="size-2.5 rounded-full bg-emerald-300" />
        <span className="ml-3 text-xs text-slate-600">app.veridianpayables.demo</span>
      </div>
      <div className="grid grid-cols-3 gap-3 p-5">
        <div className="col-span-3 grid grid-cols-3 gap-3">
          {[
            { label: 'Straight-through rate', value: '70%' },
            { label: 'Open exceptions', value: '12' },
            { label: 'Avg. cycle time', value: '48h' },
          ].map((stat) => (
            <div key={stat.label} className="rounded-xl border border-slate-200 bg-slate-50 p-3">
              <p className="text-xs text-slate-500">{stat.label}</p>
              <p className="mt-1 text-xl font-semibold text-brand-navy">{stat.value}</p>
            </div>
          ))}
        </div>
        <div className="col-span-2 flex items-end gap-2 rounded-xl border border-slate-200 p-4">
          {bars.map((height, index) => (
            <div
              key={index}
              className="flex-1 rounded-t bg-brand-blue/80"
              style={{ height: `${height}px` }}
              aria-hidden="true"
            />
          ))}
        </div>
        <div className="flex flex-col gap-2 rounded-xl border border-slate-200 p-4">
          <p className="text-xs font-semibold text-slate-500">Exceptions by reason</p>
          {[
            { label: 'Price variance', pct: 44, color: 'bg-brand-blue' },
            { label: 'Qty not received', pct: 31, color: 'bg-brand-teal' },
            { label: 'Duplicate', pct: 25, color: 'bg-amber-400' },
          ].map((row) => (
            <div key={row.label} className="text-[11px]">
              <div className="mb-1 flex justify-between text-slate-500">
                <span>{row.label}</span>
                <span>{row.pct}%</span>
              </div>
              <div className="h-1.5 rounded-full bg-slate-100">
                <div
                  className={`h-1.5 rounded-full ${row.color}`}
                  style={{ width: `${row.pct}%` }}
                />
              </div>
            </div>
          ))}
        </div>
      </div>
      <div
        className="absolute -right-6 -bottom-6 hidden rounded-xl border border-slate-200 bg-white p-4 shadow-lg sm:block"
        aria-hidden="true"
      >
        <p className="text-xs text-slate-500">Discounts captured</p>
        <p className="text-lg font-semibold text-(--color-brand-teal-text)">+$18,420</p>
      </div>
    </div>
  )
}
