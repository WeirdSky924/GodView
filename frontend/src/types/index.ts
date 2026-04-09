export interface Character {
  id?: string
  name: string
  role: string
  status: 'active' | 'inactive' | 'dead' | 'paused'
  description: string
  personality?: string
  appearance?: string
  background?: string
}

export interface World {
  id?: string
  name: string
  description: string
  type?: 'fantasy' | 'scifi' | 'historical' | 'modern' | 'other'
  regions?: Region[]
}

export interface Region {
  id?: string
  name: string
  description: string
  type?: string
}

export interface Chapter {
  id?: string
  title: string
  content?: string
  status?: 'draft' | 'published' | 'archived'
  wordCount?: number
  order?: number
}

export interface Config {
  embedding: EmbeddingConfig
  llm: LLMConfig
}

export interface EmbeddingConfig {
  provider: 'openai' | 'sentence_transformers' | 'ollama'
  model: string
  apiKey: string
  baseUrl: string
  dimension: number
}

export interface LLMConfig {
  provider: string
  model: string
  apiKey: string
  temperature: number
  maxTokens: number
}

export interface EmbeddingProviderInfo {
  id: string
  name: string
  description: string
  defaultModel: string
  defaultUrl: string
  defaultDimension: number
  requiresApiKey: boolean
  requiresLocalInstall: boolean
  installCommand?: string
}

export interface DirectorMessage {
  type: string
  status?: 'processing' | 'success' | 'error'
  message?: string
  data?: any
}
