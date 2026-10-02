import { Quote } from 'lucide-react'

import { Badge } from '@/components/ui/Badge'
import { Card } from '@/components/ui/Card'
import { Container } from '@/components/ui/Container'
import { Section, SectionHeading } from '@/components/ui/Section'
import { customerStories } from '@/lib/content/home'

export function CustomerStories() {
  return (
    <Section>
      <Container>
        <SectionHeading eyebrow="Customer stories" title="What finance teams say" />
        <div className="mt-14 grid gap-6 lg:grid-cols-3">
          {customerStories.map((story) => (
            <Card key={story.company} className="flex flex-col">
              <Quote className="size-6 text-brand-blue" aria-hidden="true" />
              <p className="mt-4 flex-1 text-sm text-slate-700">&ldquo;{story.quote}&rdquo;</p>
              <div className="mt-6 border-t border-slate-100 pt-4">
                <p className="text-sm font-semibold text-brand-navy">{story.person}</p>
                <p className="text-xs text-slate-500">
                  {story.role} &middot; {story.company}
                </p>
              </div>
              <Badge tone="warning" className="mt-3 self-start">
                Illustrative scenario
              </Badge>
            </Card>
          ))}
        </div>
      </Container>
    </Section>
  )
}
