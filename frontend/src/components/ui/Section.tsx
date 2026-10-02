import type { HTMLAttributes } from 'react'

import { cn } from '@/lib/utils'

interface SectionProps extends HTMLAttributes<HTMLElement> {
  tone?: 'default' | 'muted' | 'navy'
}

const toneClasses: Record<NonNullable<SectionProps['tone']>, string> = {
  default: 'bg-white',
  muted: 'bg-slate-50',
  navy: 'bg-brand-navy text-white',
}

export function Section({ className, tone = 'default', ...props }: SectionProps) {
  return (
    <section className={cn('py-16 sm:py-20 lg:py-24', toneClasses[tone], className)} {...props} />
  )
}

export function SectionHeading({
  eyebrow,
  title,
  subtitle,
  align = 'center',
}: {
  eyebrow?: string
  title: string
  subtitle?: string
  align?: 'center' | 'left'
}) {
  return (
    <div className={cn('mx-auto max-w-2xl', align === 'center' ? 'text-center' : 'text-left')}>
      {eyebrow ? (
        <p className="mb-3 text-sm font-semibold tracking-wide text-brand-blue uppercase">
          {eyebrow}
        </p>
      ) : null}
      <h2 className="font-serif text-3xl font-semibold text-brand-navy sm:text-4xl">{title}</h2>
      {subtitle ? <p className="mt-4 text-lg text-slate-600">{subtitle}</p> : null}
    </div>
  )
}
