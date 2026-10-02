import { zodResolver } from '@hookform/resolvers/zod'
import { CheckCircle2, Loader2 } from 'lucide-react'
import { useForm } from 'react-hook-form'
import { z } from 'zod'

import { PageHero } from '@/components/layout/PageHero'
import { Button } from '@/components/ui/Button'
import { Container } from '@/components/ui/Container'
import { Section } from '@/components/ui/Section'
import { ApiError } from '@/lib/api-client'
import { useSubmitContactForm } from '@/lib/hooks/use-contact'

const contactSchema = z.object({
  name: z.string().min(1, 'Name is required').max(200),
  email: z.string().min(1, 'Email is required').email('Enter a valid email address'),
  company: z.string().max(200).optional(),
  message: z.string().min(1, 'Tell us a bit about what you need').max(4000),
})

type ContactFormValues = z.infer<typeof contactSchema>

export function ContactPage() {
  const submit = useSubmitContactForm()
  const {
    register,
    handleSubmit,
    reset,
    formState: { errors },
  } = useForm<ContactFormValues>({ resolver: zodResolver(contactSchema) })

  async function onSubmit(values: ContactFormValues) {
    await submit.mutateAsync(values)
    reset()
  }

  return (
    <>
      <PageHero
        eyebrow="Contact"
        title="Request a demo"
        subtitle="Tell us a little about your team and we will be in touch."
      />
      <Section>
        <Container className="max-w-lg">
          {submit.isSuccess ? (
            <div className="flex flex-col items-center gap-3 rounded-xl border border-slate-200 bg-slate-50 p-10 text-center">
              <CheckCircle2 className="size-10 text-brand-teal" aria-hidden="true" />
              <h2 className="text-lg font-semibold text-brand-navy">Thanks for reaching out</h2>
              <p className="text-sm text-slate-600">We will get back to you shortly.</p>
            </div>
          ) : (
            <form onSubmit={handleSubmit(onSubmit)} className="flex flex-col gap-5" noValidate>
              <Field label="Name" error={errors.name?.message} htmlFor="contact-name">
                <input
                  id="contact-name"
                  className="w-full rounded-lg border border-slate-300 px-3 py-2.5 text-sm focus-visible:border-brand-blue"
                  {...register('name')}
                />
              </Field>
              <Field label="Work email" error={errors.email?.message} htmlFor="contact-email">
                <input
                  id="contact-email"
                  type="email"
                  className="w-full rounded-lg border border-slate-300 px-3 py-2.5 text-sm focus-visible:border-brand-blue"
                  {...register('email')}
                />
              </Field>
              <Field
                label="Company (optional)"
                error={errors.company?.message}
                htmlFor="contact-company"
              >
                <input
                  id="contact-company"
                  className="w-full rounded-lg border border-slate-300 px-3 py-2.5 text-sm focus-visible:border-brand-blue"
                  {...register('company')}
                />
              </Field>
              <Field
                label="How can we help?"
                error={errors.message?.message}
                htmlFor="contact-message"
              >
                <textarea
                  id="contact-message"
                  rows={5}
                  className="w-full rounded-lg border border-slate-300 px-3 py-2.5 text-sm focus-visible:border-brand-blue"
                  {...register('message')}
                />
              </Field>

              {submit.isError ? (
                <p role="alert" className="text-sm text-(--color-danger)">
                  {submit.error instanceof ApiError
                    ? (submit.error.detail ?? submit.error.title)
                    : 'Something went wrong. Please try again.'}
                </p>
              ) : null}

              <Button type="submit" disabled={submit.isPending} className="w-full">
                {submit.isPending ? (
                  <Loader2 className="size-4 animate-spin" aria-hidden="true" />
                ) : null}
                Send message
              </Button>
            </form>
          )}
        </Container>
      </Section>
    </>
  )
}

function Field({
  label,
  htmlFor,
  error,
  children,
}: {
  label: string
  htmlFor: string
  error?: string
  children: React.ReactNode
}) {
  return (
    <div>
      <label htmlFor={htmlFor} className="mb-1.5 block text-sm font-medium text-slate-700">
        {label}
      </label>
      {children}
      {error ? (
        <p role="alert" className="mt-1.5 text-sm text-(--color-danger)">
          {error}
        </p>
      ) : null}
    </div>
  )
}
