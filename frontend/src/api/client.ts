import createClient from 'openapi-fetch'
import type { paths } from './schema'

export const api = createClient<paths>({ baseUrl: typeof window === 'undefined' ? '' : window.location.origin, fetch: request => globalThis.fetch(request) })

function csrfCookie() {
  return document.cookie.split('; ').find((item) => item.startsWith('cyberlab_csrf='))?.split('=').slice(1).join('=')
}

api.use({
  onRequest({ request }) {
    const headers = new Headers(request.headers)
    if (!['GET', 'HEAD', 'OPTIONS'].includes(request.method.toUpperCase())) {
      const csrf = csrfCookie()
      if (csrf) headers.set('X-CSRF-Token', decodeURIComponent(csrf))
    }
    return new Request(request, { credentials: 'include', headers })
  },
  onResponse({ request, response }) {
    if (response.status === 401 && !request.url.includes('/auth/login') && !request.url.includes('/auth/me')) {
      window.dispatchEvent(new Event('cyberlab:session-expired'))
    }
    return response
  },
})

export class ApiError extends Error {
  constructor(public status: number, public code: string, message: string, public details: unknown = {}) {
    super(message)
    this.name = 'ApiError'
  }
}

export async function unwrap<T>(result: { data?: T; error?: unknown; response: Response }): Promise<T> {
  if (!result.response.ok || result.error !== undefined) {
    const envelope = result.error as { error?: { code?: string; message?: string; details?: unknown }; detail?: string } | undefined
    throw new ApiError(result.response.status, envelope?.error?.code ?? 'REQUEST_FAILED', envelope?.error?.message ?? envelope?.detail ?? 'No se pudo completar la solicitud.', envelope?.error?.details)
  }
  return result.data as T
}
