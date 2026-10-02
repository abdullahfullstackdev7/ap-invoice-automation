import { Container } from '@/components/ui/Container'
import { Section, SectionHeading } from '@/components/ui/Section'
import { DashboardMockup } from '@/pages/home/DashboardMockup'

export function AnalyticsShowcase() {
  return (
    <Section tone="muted">
      <Container className="grid items-center gap-12 lg:grid-cols-2">
        <div>
          <SectionHeading
            align="left"
            eyebrow="Analytics"
            title="Know your cycle time, exceptions and cash position"
            subtitle="Seventeen built-in reports cover spend, exceptions, cycle time, aging, cash flow and vendor performance - each filterable by date range, vendor and category, and exportable to CSV."
          />
        </div>
        <div className="relative">
          <DashboardMockup />
        </div>
      </Container>
    </Section>
  )
}
