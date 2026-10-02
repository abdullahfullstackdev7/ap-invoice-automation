import { Link, Navigate, useParams } from 'react-router-dom'

import { Badge } from '@/components/ui/Badge'
import { Container } from '@/components/ui/Container'
import { Section } from '@/components/ui/Section'
import { articles } from '@/lib/content/articles'

export function ResourceArticlePage() {
  const { slug } = useParams<{ slug: string }>()
  const article = articles.find((a) => a.slug === slug)

  if (!article) return <Navigate to="/resources" replace />

  return (
    <Section className="pt-24">
      <Container className="max-w-2xl">
        <Link to="/resources" className="text-sm text-brand-blue hover:underline">
          &larr; All articles
        </Link>
        <Badge tone="navy" className="mt-6">
          {article.category}
        </Badge>
        <h1 className="mt-4 font-serif text-3xl font-semibold text-brand-navy sm:text-4xl">
          {article.title}
        </h1>
        <p className="mt-2 text-sm text-slate-500">{article.readingTime}</p>
        <div className="mt-8">
          {article.body.map((paragraph, index) => (
            <p key={index} className="mb-5 text-base leading-relaxed text-slate-700">
              {paragraph}
            </p>
          ))}
        </div>
      </Container>
    </Section>
  )
}
