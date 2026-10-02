import { ArrowRight } from 'lucide-react'
import { Link } from 'react-router-dom'

import { Badge } from '@/components/ui/Badge'
import { Card } from '@/components/ui/Card'
import { Container } from '@/components/ui/Container'
import { Section, SectionHeading } from '@/components/ui/Section'
import { articles } from '@/lib/content/articles'

export function ResourcesPage() {
  return (
    <Section className="pt-24">
      <Container>
        <SectionHeading
          eyebrow="Resources"
          title="Articles on AP automation and 3-way match"
          align="left"
        />
        <div className="mt-14 grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
          {articles.map((article) => (
            <Link key={article.slug} to={`/resources/${article.slug}`}>
              <Card className="flex h-full flex-col">
                <Badge tone="navy" className="self-start">
                  {article.category}
                </Badge>
                <h3 className="mt-4 text-lg font-semibold text-brand-navy">{article.title}</h3>
                <p className="mt-2 flex-1 text-sm text-slate-600">{article.excerpt}</p>
                <div className="mt-6 flex items-center justify-between text-xs text-slate-500">
                  <span>{article.readingTime}</span>
                  <span className="inline-flex items-center gap-1 text-brand-blue">
                    Read <ArrowRight className="size-3.5" aria-hidden="true" />
                  </span>
                </div>
              </Card>
            </Link>
          ))}
        </div>
      </Container>
    </Section>
  )
}
