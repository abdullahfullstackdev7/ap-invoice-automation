import { Badge } from '@/components/ui/Badge'
import { Container } from '@/components/ui/Container'
import { Section, SectionHeading } from '@/components/ui/Section'
import { integrationItems } from '@/lib/content/home'

export function Integrations() {
  return (
    <Section tone="muted">
      <Container>
        <SectionHeading eyebrow="Integrations" title="Connect to your ERP" />
        <div className="mt-12 grid grid-cols-2 gap-5 sm:grid-cols-3 lg:grid-cols-5">
          {integrationItems.map((item) => (
            <div
              key={item.title}
              className="flex flex-col items-center gap-3 rounded-xl border border-slate-200 bg-white p-6 text-center"
            >
              <item.icon className="size-8 text-brand-navy" aria-hidden="true" />
              <p className="text-sm font-medium text-brand-navy">{item.title}</p>
              <Badge tone={item.status === 'Available' ? 'teal' : 'neutral'}>{item.status}</Badge>
            </div>
          ))}
        </div>
      </Container>
    </Section>
  )
}
