import type { AxiosError } from 'axios'

export interface StartupRetryOptions {
  retries?: number
  initialDelayMs?: number
  maxDelayMs?: number
  label?: string
}

function delay(ms: number): Promise<void> {
  return new Promise(resolve => setTimeout(resolve, ms))
}

function isStartupConnectionError(error: unknown): boolean {
  const axiosError = error as AxiosError | undefined
  if (axiosError?.response) return false
  const code = String((axiosError as any)?.code || '').toUpperCase()
  if (['ERR_NETWORK', 'ECONNABORTED', 'ECONNREFUSED'].includes(code)) return true
  const message = String((error as any)?.message || '').toLowerCase()
  return message.includes('network error') || message.includes('econnrefused') || message.includes('failed to fetch')
}

function isStartupProxyFailure(error: unknown): boolean {
  const axiosError = error as AxiosError | undefined
  if (!axiosError?.response) return false
  const status = axiosError.response.status
  if (status !== 500 && status !== 502 && status !== 503 && status !== 504) return false

  const data = axiosError.response.data
  const payload = typeof data === 'string' ? data : JSON.stringify(data || {})
  const message = `${payload} ${(axiosError as any)?.message || ''}`.toLowerCase()
  return message.includes('econnrefused') || message.includes('proxy error')
}

export async function withStartupRetry<T>(
  operation: () => Promise<T>,
  options: StartupRetryOptions = {}
): Promise<T> {
  const retries = options.retries ?? 6
  const initialDelayMs = options.initialDelayMs ?? 500
  const maxDelayMs = options.maxDelayMs ?? 4000
  let attempt = 0
  let delayMs = initialDelayMs

  while (true) {
    try {
      return await operation()
    } catch (error) {
      if (!(isStartupConnectionError(error) || isStartupProxyFailure(error)) || attempt >= retries) {
        throw error
      }
      attempt += 1
      await delay(delayMs)
      delayMs = Math.min(delayMs * 2, maxDelayMs)
    }
  }
}
