import type { ApiError } from './types'

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000'

export class CaseApiError extends Error {
  constructor(public readonly code: string, message: string, public readonly status: number) { super(message) }
}

export async function apiRequest<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response
  try { response = await fetch(`${API_BASE_URL}${path}`, { ...init, headers: { 'Content-Type': 'application/json', ...init?.headers } }) }
  catch { throw new CaseApiError('BACKEND_UNAVAILABLE', 'Unable to load live case state.', 0) }
  if (!response.ok) {
    const body = await response.json().catch(() => ({ code: 'BACKEND_UNAVAILABLE', message: 'Unable to load live case state.' })) as ApiError
    throw new CaseApiError(body.code, body.message, response.status)
  }
  return response.json() as Promise<T>
}
