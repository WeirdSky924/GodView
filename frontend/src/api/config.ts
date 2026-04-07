import { api } from './client'

export interface EmbeddingProviderInfo {
  id: string
  name: string
  description: string
  default_model: string
  default_url: string
  default_dimension: number
  requires_api_key: boolean
  requires_local_install: boolean
  install_command?: string
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
  dimension: number
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
}

export async function getEmbeddingProviders(): Promise<EmbeddingProviderInfo[]> {
  const response = await api.get<EmbeddingProviderInfo[]>('/config/embedding/providers')
  return response.data
}

export async function getEmbeddingConfig(): Promise<EmbeddingConfig> {
  const response = await api.get<EmbeddingConfig>('/config/embedding')
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

export async function getLLMProviders(): Promise<LLMProviderInfo[]> {
  const response = await api.get<LLMProviderInfo[]>('/config/llm/providers')
  return response.data
}

export async function getLLMConfig(): Promise<LLMConfig> {
  const response = await api.get<LLMConfig>('/config/llm')
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
