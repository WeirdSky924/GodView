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

export async function getEmbeddingProviders(): Promise<EmbeddingProviderInfo[]> {
  const response = await api.get<EmbeddingProviderInfo[]>('/config/embedding/providers')
  return response.data
}

export async function getEmbeddingConfig(): Promise<EmbeddingConfig & { dimension: number }> {
  const response = await api.get<EmbeddingConfig & { dimension: number }>('/config/embedding')
  return response.data
}

export async function getEmbeddingProviderConfig(provider: string): Promise<EmbeddingConfig & { dimension?: number }> {
  const response = await api.get<EmbeddingConfig & { dimension?: number }>(`/config/embedding/${provider}`)
  return response.data
}

export async function updateEmbeddingConfig(config: EmbeddingConfig): Promise<ConfigResult> {
  const response = await api.put<ConfigResult>('/config/embedding', config)
  return response.data
}

export async function testEmbeddingConfig(config?: Partial<EmbeddingConfig>): Promise<ConfigResult> {
  const response = await api.post<ConfigResult>('/config/embedding/test', config || {})
  return response.data
}

export async function getEmbeddingDownloadProgress(): Promise<DownloadProgress> {
  const response = await api.get<DownloadProgress>('/config/embedding/download-progress')
  return response.data
}

export async function getLLMProviders(): Promise<LLMProviderInfo[]> {
  const response = await api.get<LLMProviderInfo[]>('/config/llm/providers')
  return response.data
}

export async function getLLMConfig(): Promise<LLMConfig> {
  const response = await api.get<LLMConfig>('/config/llm')
  return response.data
}

export async function getLLMProviderConfig(provider: string): Promise<LLMConfig> {
  const response = await api.get<LLMConfig>(`/config/llm/${provider}`)
  return response.data
}

export async function updateLLMConfig(config: LLMConfig): Promise<ConfigResult> {
  const response = await api.put<ConfigResult>('/config/llm', config)
  return response.data
}

export async function testLLMConfig(config?: Partial<LLMConfig>): Promise<ConfigResult> {
  const response = await api.post<ConfigResult>('/config/llm/test', config || {})
  return response.data
}

export async function getProviderModels(providerId: string): Promise<ProviderModelsResponse> {
  const response = await api.get<ProviderModelsResponse>(`/config/llm/providers/${providerId}/models`)
  return response.data
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
  const response = await api.get<DatabaseStatusResponse>('/config/database/status')
  return response.data
}
