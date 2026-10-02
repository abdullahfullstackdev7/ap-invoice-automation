import { useMutation } from '@tanstack/react-query'

import { apiRequest } from '@/lib/api-client'

export interface ContactFormValues {
  name: string
  email: string
  company?: string
  message: string
}

export function useSubmitContactForm() {
  return useMutation({
    mutationFn: (body: ContactFormValues) =>
      apiRequest<{ status: string }>('/contact', { method: 'POST', body }),
  })
}
