export interface QueryCacheOptions {
  ttlMs?: number
  forceRefresh?: boolean
}

interface CacheEntry<T> {
  value?: T
  expiresAt: number
  promise?: Promise<T>
}

const cache = new Map<string, CacheEntry<unknown>>()

export function getCachedQuery<T>(
  key: string,
  loader: () => Promise<T>,
  options: QueryCacheOptions = {}
): Promise<T> {
  const now = Date.now()
  const existing = cache.get(key) as CacheEntry<T> | undefined

  if (existing?.promise) {
    return existing.promise
  }

  if (!options.forceRefresh && existing && existing.expiresAt > now && 'value' in existing) {
    return Promise.resolve(existing.value as T)
  }

  const ttlMs = options.ttlMs ?? 0
  const entry: CacheEntry<T> = {
    expiresAt: 0,
  }

  entry.promise = loader()
    .then((value) => {
      entry.value = value
      entry.expiresAt = ttlMs > 0 ? Date.now() + ttlMs : 0
      return value
    })
    .catch((error) => {
      cache.delete(key)
      throw error
    })
    .finally(() => {
      entry.promise = undefined
      if (!('value' in entry)) {
        cache.delete(key)
      }
    })

  cache.set(key, entry as CacheEntry<unknown>)
  return entry.promise
}

export function invalidateQueryCache(keyOrPrefix?: string): void {
  if (!keyOrPrefix) {
    cache.clear()
    return
  }

  for (const key of cache.keys()) {
    if (key === keyOrPrefix || key.startsWith(`${keyOrPrefix}:`)) {
      cache.delete(key)
    }
  }
}
