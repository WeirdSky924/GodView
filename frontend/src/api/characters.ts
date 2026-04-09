import { api } from './client'

export interface Character {
  id?: string
  name: string
  role: string
  status: 'active' | 'inactive' | 'deceased'
  description: string
  personality?: string
  appearance?: string
  background?: string
  relationships?: string[]
  speech_pattern?: string
  lexicon?: string[]
  forbidden_words?: string[]
  voice_samples?: string[]
}

export interface CreateCharacterDTO {
  name: string
  role: string
  status: Character['status']
  description: string
  personality?: string
  appearance?: string
  background?: string
  speech_pattern?: string
  lexicon?: string[]
  forbidden_words?: string[]
  voice_samples?: string[]
}

export interface UpdateCharacterDTO extends CreateCharacterDTO {
  id: string
}

export interface CharacterVoiceSample {
  id: string
  character_id: string
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

export async function getCharacterVoiceSamples(characterId: string, limit: number = 10) {
  return await api.get<CharacterVoiceSampleSearchResult[]>(`/characters/${characterId}/voice-samples`, {
    params: { limit },
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
) {
  return await api.post<CharacterVoiceSampleSearchResult[]>(
    `/characters/${characterId}/voice-samples/search`,
    null,
    {
      params: {
        query_text: queryText,
        limit,
      },
    },
  )
}
