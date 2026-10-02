import { Container } from '@/components/ui/Container'
import { LinkButton } from '@/components/ui/LinkButton'
import { Section } from '@/components/ui/Section'

export function FinalCta() {
  return (
    <Section tone="navy">
      <Container className="text-center">
        <h2 className="font-serif text-3xl font-semibold text-white sm:text-4xl">
          Ready to see your invoices processed like this?
        </h2>
        <p className="mx-auto mt-4 max-w-xl text-slate-200">
          Log in to the sample deployment, or request a demo and we will walk you through it.
        </p>
        <div className="mt-8 flex flex-wrap items-center justify-center gap-4">
          <LinkButton to="/login" size="lg">
            Log in
          </LinkButton>
          <LinkButton
            to="/contact"
            variant="outline"
            size="lg"
            className="border-white text-white hover:bg-white/10"
          >
            Request a demo
          </LinkButton>
        </div>
      </Container>
    </Section>
  )
}
