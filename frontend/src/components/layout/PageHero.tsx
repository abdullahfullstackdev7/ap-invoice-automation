import { Container } from '@/components/ui/Container'

export function PageHero({
  eyebrow,
  title,
  subtitle,
}: {
  eyebrow?: string
  title: string
  subtitle?: string
}) {
  return (
    <div className="bg-gradient-to-b from-slate-50 to-white pt-24 pb-16">
      <Container className="max-w-3xl text-center">
        {eyebrow ? (
          <p className="mb-3 text-sm font-semibold tracking-wide text-brand-blue uppercase">
            {eyebrow}
          </p>
        ) : null}
        <h1 className="font-serif text-4xl font-semibold text-brand-navy sm:text-5xl">{title}</h1>
        {subtitle ? <p className="mt-5 text-lg text-slate-600">{subtitle}</p> : null}
      </Container>
    </div>
  )
}
