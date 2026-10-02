import { Card } from '@/components/ui/Card'
import { Container } from '@/components/ui/Container'
import { Section, SectionHeading } from '@/components/ui/Section'
import { featureCards } from '@/lib/content/home'

export function FeatureGrid() {
  return (
    <Section tone="muted">
      <Container>
        <SectionHeading
          eyebrow="Platform"
          title="Everything from capture to payment, in one system"
        />
        <div className="mt-14 grid gap-5 sm:grid-cols-2 lg:grid-cols-4">
          {featureCards.map((feature) => (
            <Card key={feature.title}>
              <feature.icon className="size-8 text-brand-blue" aria-hidden="true" />
              <h3 className="mt-4 text-base font-semibold text-brand-navy">{feature.title}</h3>
              <p className="mt-2 text-sm text-slate-600">{feature.description}</p>
            </Card>
          ))}
        </div>
      </Container>
    </Section>
  )
}
