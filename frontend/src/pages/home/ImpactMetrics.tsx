import { AnimatedCounter } from '@/components/ui/AnimatedCounter'
import { Container } from '@/components/ui/Container'
import { Section } from '@/components/ui/Section'
import { impactMetrics } from '@/lib/content/home'

export function ImpactMetrics() {
  return (
    <Section tone="navy">
      <Container>
        <div className="grid gap-10 sm:grid-cols-2 lg:grid-cols-4">
          {impactMetrics.map((metric) => (
            <div key={metric.label} className="text-center">
              <p className="font-serif text-4xl font-semibold text-white sm:text-5xl">
                <AnimatedCounter
                  value={metric.value}
                  suffix={metric.suffix}
                  decimals={metric.decimals}
                />
              </p>
              <p className="mt-2 text-sm font-medium text-slate-200">{metric.label}</p>
              <p className="mt-1 text-xs text-slate-400">{metric.note}</p>
            </div>
          ))}
        </div>
      </Container>
    </Section>
  )
}
