import { api } from './client'

export interface EmbeddingProviderInfo {
  id: string
  name: string
  description: string
  default_model: string
  default_url: string
  requires_api_key: boolean
  requires_local_install: boolean
  install_command?: string
  models?: EmbeddingModelInfo[]
}

export interface EmbeddingModelInfo {
  id: string
  name: string
  dimension: number
  description: string
}

export interface LLMProviderInfo {
  id: string
  name: string
  description: string
  default_model: string
  default_url: string
  requires_api_key: boolean
  api_key_url?: string
  models?: LLMModelInfo[]
}

export interface LLMModelInfo {
  id: string
  name: string
  context_length: number
  description: string
}

export interface ProviderModelsResponse {
  provider_id: string
  provider_name: string
  models: LLMModelInfo[]
  default_model: string
}

export interface EmbeddingConfig {
  provider: string
  model: string
  api_key: string
  base_url: string
}

export interface LLMConfig {
  provider: string
  model: string
  api_key: string
  base_url: string
  temperature: number
  max_tokens: number
}

export interface ConfigResult {
  success: boolean
  message: string
  dimension?: number
}

export interface DownloadProgress {
  status: 'idle' | 'downloading' | 'completed' | 'error'
  progress: number
  message: string
  model: string
}

// Note: api interceptor already returns response.data, so we don't need .data here
export async function getEmbeddingProviders(): Promise<EmbeddingProviderInfo[]> {
  return await api.get<EmbeddingProviderInfo[]>('/config/embedding/providers')
}

export async function getEmbeddingConfig(): Promise<EmbeddingConfig & { dimension: number }> {
  return await api.get<EmbeddingConfig & { dimension: number }>('/config/embedding')
}

export async function getEmbeddingProviderConfig(provider: string): Promise<EmbeddingConfig & { dimension?: number }> {
  return await api.get<EmbeddingConfig & { dimension?: number }>(`/config/embedding/${provider}`)
}

export async function updateEmbeddingConfig(config: EmbeddingConfig): Promise<ConfigResult> {
  return await api.put<ConfigResult>('/config/embedding', config)
}

export async function testEmbeddingConfig(config?: Partial<EmbeddingConfig>): Promise<ConfigResult> {
  return await api.post<ConfigResult>('/config/embedding/test', config || {})
}

export async function getEmbeddingDownloadProgress(): Promise<DownloadProgress> {
  return await api.get<DownloadProgress>('/config/embedding/download-progress')
}

export interface CacheStatus {
  provider: string
  model: string
  is_cached: boolean | null
  dimension?: number
  message: string
}

export async function getEmbeddingCacheStatus(
  provider: string,
  model?: string,
  cacheFolder?: string
): Promise<CacheStatus> {
  const params = new URLSearchParams()
  params.append('provider', provider)
  if (model) params.append('model', model)
  if (cacheFolder) params.append('cache_folder', cacheFolder)
  return await api.get<CacheStatus>(`/config/embedding/cache-status?${params.toString()}`)
}

export async function getLLMProviders(): Promise<LLMProviderInfo[]> {
  return await api.get<LLMProviderInfo[]>('/config/llm/providers')
}

export async function getLLMConfig(): Promise<LLMConfig> {
  return await api.get<LLMConfig>('/config/llm')
}

export async function getLLMProviderConfig(provider: string): Promise<LLMConfig> {
  return await api.get<LLMConfig>(`/config/llm/${provider}`)
}

export async function updateLLMConfig(config: LLMConfig): Promise<ConfigResult> {
  return await api.put<ConfigResult>('/config/llm', config)
}

export async function testLLMConfig(config?: Partial<LLMConfig>): Promise<ConfigResult> {
  return await api.post<ConfigResult>('/config/llm/test', config || {})
}

export async function getProviderModels(providerId: string): Promise<ProviderModelsResponse> {
  return await api.get<ProviderModelsResponse>(`/config/llm/providers/${providerId}/models`)
}

export interface DatabaseStatus {
  name: string
  type: string
  status: 'connected' | 'disconnected' | 'reachable' | 'error'
  message: string
  host: string
}

export interface DatabaseStatusResponse {
  databases: DatabaseStatus[]
  summary: {
    connected: number
    total: number
    status: 'healthy' | 'degraded' | 'error'
  }
}

export async function getDatabaseStatus(): Promise<DatabaseStatusResponse> {
  return await api.get<DatabaseStatusResponse>('/config/database/status')
}

export interface GlobalStats {
  project_count: number
  character_count: number
  world_count: number
  chapter_count: number
  total_tokens: number
  total_cost: number
}

export async function getGlobalStats(projectId?: string): Promise<GlobalStats> {
  const params = projectId ? { project_id: projectId } : {}
  return await api.get<GlobalStats>('/config/stats', { params })
}
