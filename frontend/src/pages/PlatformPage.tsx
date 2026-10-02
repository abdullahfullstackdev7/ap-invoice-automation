import { PageHero } from '@/components/layout/PageHero'
import { Container } from '@/components/ui/Container'
import { LinkButton } from '@/components/ui/LinkButton'
import { Section } from '@/components/ui/Section'
import { platformMenuItems } from '@/lib/content/nav'

const sectionAnchors: Record<string, string> = {
  '/platform#capture': 'capture',
  '/platform#extraction': 'extraction',
  '/platform#match': 'match',
  '/platform#exceptions': 'exceptions',
  '/platform#approvals': 'approvals',
  '/platform#payments': 'payments',
  '/platform#analytics': 'analytics',
  '/platform#audit': 'audit',
}

export function PlatformPage() {
  return (
    <>
      <PageHero
        eyebrow="Platform"
        title="One platform, from intake to payment"
        subtitle="Every stage of accounts payable, reconciled against the same source of truth."
      />
      {platformMenuItems.map((item, index) => (
        <Section
          key={item.href}
          id={sectionAnchors[item.href]}
          tone={index % 2 === 0 ? 'default' : 'muted'}
        >
          <Container className="grid items-center gap-10 lg:grid-cols-2">
            <div className={index % 2 === 1 ? 'lg:order-2' : undefined}>
              <item.icon className="size-10 text-brand-blue" aria-hidden="true" />
              <h2 className="mt-4 font-serif text-2xl font-semibold text-brand-navy sm:text-3xl">
                {item.title}
              </h2>
              <p className="mt-4 text-slate-600">{item.description}</p>
            </div>
            <div
              className="flex aspect-[4/3] items-center justify-center rounded-2xl bg-gradient-to-br from-brand-navy to-brand-blue text-white"
              aria-hidden="true"
            >
              <item.icon className="size-16 opacity-50" />
            </div>
          </Container>
        </Section>
      ))}
      <Section tone="navy">
        <Container className="text-center">
          <h2 className="font-serif text-3xl font-semibold text-white">
            See the whole platform in action
          </h2>
          <div className="mt-8">
            <LinkButton to="/login" size="lg">
              Log in to the platform
            </LinkButton>
          </div>
        </Container>
      </Section>
    </>
  )
}
