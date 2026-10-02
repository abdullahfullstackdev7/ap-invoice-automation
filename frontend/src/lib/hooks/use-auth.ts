import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { apiRequest } from '@/lib/api-client'
import { getCsrfToken } from '@/lib/csrf'

export interface LoginRequest {
  email: string
  password: string
}

export interface LoginResponse {
  status: 'ok' | 'mfa_required'
  mfa_token?: string | null
}

export interface MFAVerifyRequest {
  mfa_token: string
  code: string
}

export type UserRole = 'admin' | 'ap_clerk' | 'approver' | 'finance_manager' | 'auditor'

export interface CurrentUser {
  id: string
  email: string
  full_name: string
  role: UserRole
  approval_limit: string | null
  is_active: boolean
  last_login_at: string | null
}

const ME_QUERY_KEY = ['auth', 'me']

export function useLogin() {
  return useMutation({
    mutationFn: (body: LoginRequest) =>
      apiRequest<LoginResponse>('/auth/login', { method: 'POST', body }),
  })
}

export function useVerifyMfa() {
  return useMutation({
    mutationFn: (body: MFAVerifyRequest) =>
      apiRequest<LoginResponse>('/auth/mfa/verify', { method: 'POST', body }),
  })
}

export function useCurrentUser(enabled = true) {
  return useQuery({
    queryKey: ME_QUERY_KEY,
    queryFn: () => apiRequest<CurrentUser>('/auth/me'),
    retry: false,
    enabled,
  })
}

export function useLogout() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: () =>
      apiRequest<void>('/auth/logout', {
        method: 'POST',
        headers: { 'X-CSRF-Token': getCsrfToken() ?? '' },
      }),
    onSuccess: () => {
      queryClient.removeQueries({ queryKey: ME_QUERY_KEY })
    },
  })
}
