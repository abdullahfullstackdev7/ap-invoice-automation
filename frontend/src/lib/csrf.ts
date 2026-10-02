/** Reads the `csrf_token` cookie the backend's double-submit CSRF
 * protection sets (non-HttpOnly by design, see backend app/core/cookies.py),
 * for the `X-CSRF-Token` header state-changing requests must send. */
export function getCsrfToken(): string | null {
  const match = document.cookie.match(/(?:^|; )csrf_token=([^;]*)/)
  return match ? decodeURIComponent(match[1]) : null
}
