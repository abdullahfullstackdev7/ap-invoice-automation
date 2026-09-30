import { useQuery } from '@tanstack/react-query'

import { apiRequest } from '@/lib/api-client'

interface HealthResponse {
  status: string
}

export function useHealth() {
  return useQuery({
    queryKey: ['health'],
    queryFn: () => apiRequest<HealthResponse>('/healthz'),
    staleTime: 30_000,
  })
}
