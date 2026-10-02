import type { HTMLAttributes } from 'react'

import { cn } from '@/lib/utils'

interface BadgeProps extends HTMLAttributes<HTMLSpanElement> {
  tone?: 'navy' | 'teal' | 'warning' | 'neutral'
}

const toneClasses: Record<NonNullable<BadgeProps['tone']>, string> = {
  navy: 'bg-brand-navy/10 text-brand-navy',
  teal: 'bg-brand-teal/10 text-(--color-brand-teal-text)',
  warning: 'bg-(--color-warning-bg) text-(--color-warning)',
  neutral: 'bg-slate-100 text-slate-600',
}

export function Badge({ className, tone = 'neutral', ...props }: BadgeProps) {
  return (
    <span
      className={cn(
        'inline-flex items-center rounded-full px-3 py-1 text-xs font-semibold',
        toneClasses[tone],
        className,
      )}
      {...props}
    />
  )
}
