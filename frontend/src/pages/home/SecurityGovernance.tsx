import { Container } from '@/components/ui/Container'
import { Section, SectionHeading } from '@/components/ui/Section'
import { securityTiles } from '@/lib/content/home'

export function SecurityGovernance() {
  return (
    <Section>
      <Container>
        <SectionHeading
          eyebrow="Security and governance"
          title="Controls you can describe, and prove"
        />
        <div className="mt-14 grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
          {securityTiles.map((tile) => (
            <div key={tile.title} className="rounded-xl border border-slate-200 p-6">
              <tile.icon className="size-7 text-brand-navy" aria-hidden="true" />
              <h3 className="mt-3 text-base font-semibold text-brand-navy">{tile.title}</h3>
              <p className="mt-2 text-sm text-slate-600">{tile.description}</p>
            </div>
          ))}
        </div>
      </Container>
    </Section>
  )
}
