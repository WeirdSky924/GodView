import { api } from './client'

export interface Character {
  id?: string
  name: string
  role: string
  status: 'active' | 'inactive' | 'dead' | 'paused'
  description: string
  project_id?: string
  personality?: string
  appearance?: string
  background?: string
  relationships?: string[]
  speech_pattern?: string
  lexicon?: string[]
  forbidden_words?: string[]
  voice_samples?: string[]
  // Agent 配置
  has_agent?: boolean
  agent_enabled?: boolean
  agent_goals?: string[]
  agent_memory?: string[]
}

export interface CreateCharacterDTO {
  name: string
  role: string
  status: Character['status']
  description: string
  project_id?: string
  personality?: string
  appearance?: string
  background?: string
  speech_pattern?: string
  lexicon?: string[]
  forbidden_words?: string[]
  voice_samples?: string[]
  // Agent 配置
  has_agent?: boolean
  agent_enabled?: boolean
  agent_goals?: string[]
  agent_memory?: string[]
}

export interface UpdateCharacterDTO extends CreateCharacterDTO {
  id: string
}

export interface CharacterVoiceSample {
  id: string
  character_id: string
  project_id?: string
  text: string
  context?: string
  embedding?: number[]
}

export interface CharacterVoiceSampleSearchResult {
  id: string
  score: number
  payload: {
    type: 'voice_sample'
    character_id: string
    text: string
    context?: string
  }
}

export async function getCharacters(projectId?: string) {
  const params = projectId ? { project_id: projectId } : {}
  return await api.get<Character[]>('/characters', { params })
}

export async function getCharacter(id: string) {
  return await api.get<Character>(`/characters/${id}`)
}

export async function createCharacter(data: CreateCharacterDTO) {
  return await api.post<Character>('/characters', data)
}

export async function updateCharacter(id: string, data: UpdateCharacterDTO) {
  return await api.put<Character>(`/characters/${id}`, data)
}

export async function deleteCharacter(id: string) {
  return await api.delete(`/characters/${id}`)
}

export async function getCharacterMemories(characterId: string) {
  return await api.get<{ memories: any[] }>(`/characters/${characterId}/memories`)
}

export async function addCharacterMemory(
  characterId: string,
  content: string,
  memoryType: string = 'experience',
  importance: number = 0.5
) {
  return await api.post<{ success: boolean; message: string }>(
    `/characters/${characterId}/memories`,
    { content, memory_type: memoryType, importance }
  )
}

export async function getCharacterVoiceSamples(characterId: string, limit: number = 10, projectId?: string) {
  const params: Record<string, string | number> = { limit }
  if (projectId) {
    params.project_id = projectId
  }
  return await api.get<CharacterVoiceSampleSearchResult[]>(`/characters/${characterId}/voice-samples`, {
    params,
  })
}

export async function addCharacterVoiceSample(characterId: string, data: CharacterVoiceSample) {
  return await api.post<{ success: boolean; id: string; vector_id?: string | null; message: string }>(
    `/characters/${characterId}/voice-samples`,
    data,
  )
}

export async function syncCharacterVoiceSamples(characterId: string) {
  return await api.post<{ success: boolean; deleted: number; inserted: number; message: string }>(
    `/characters/${characterId}/voice-samples/sync`,
  )
}

export async function searchCharacterVoiceSamples(
  characterId: string,
  queryText: string,
  limit: number = 5,
  projectId?: string,
) {
  const params: Record<string, string | number> = {
    query_text: queryText,
    limit,
  }
  if (projectId) {
    params.project_id = projectId
  }
  return await api.post<CharacterVoiceSampleSearchResult[]>(
    `/characters/${characterId}/voice-samples/search`,
    null,
    { params },
  )
}

export interface CharacterAgentPrompt {
  has_agent: boolean
  agent_enabled?: boolean
  character_id?: string
  character_name?: string
  variables?: {
    character_background: string
    character_personality: string
    character_goals: string
  }
  prompt?: string
  prompt_length?: number
  agent_goals?: string[]
  agent_memory?: string[]
  message?: string
}

export async function getCharacterAgentPrompt(characterId: string) {
  return await api.get<CharacterAgentPrompt>(`/characters/${characterId}/agent-prompt`)
}

export interface BatchEnableAgentsResult {
  success: boolean
  message: string
  updated_count: number
  skipped_count: number
  error_count: number
  errors: string[]
}

export async function batchEnableCharacterAgents(projectId: string, roles?: string) {
  const params = new URLSearchParams()
  params.append('project_id', projectId)
  if (roles) {
    params.append('roles', roles)
  } else {
    params.append('roles', 'main,antagonist,supporting')
  }
  return await api.post<BatchEnableAgentsResult>(`/characters/batch-enable-agents?${params.toString()}`)
}

export interface GeneratePersonalityResult {
  success: boolean
  message: string
  personality?: string
  speech_pattern?: string
  agent_goals?: string[]
  agent_memory?: string[]
}

export async function generateCharacterPersonality(characterId: string) {
  return await api.post<GeneratePersonalityResult>(`/characters/${characterId}/generate-personality`)
}
