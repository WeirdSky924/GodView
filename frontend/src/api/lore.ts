import { api } from './client'
import type { Character, CharacterImportanceTier, NarrativeWeight, StoryArcRole } from './characters'
import type { CharacterReferenceResolution, ResolvedCharacterReference, UnresolvedCharacterReference } from './settingAgent'

export interface LoreEntry {
  id: string
  project_id: string
  title: string
  category: LoreCategory
  priority: LorePriority
  content: string
  summary?: string
  keywords: string[]
  tags: string[]
  related_characters: string[]
  related_character_refs?: ResolvedCharacterReference[]
  unresolved_character_refs?: UnresolvedCharacterReference[]
  related_locations: string[]
  related_items: string[]
  parent_lore_id?: string
  constraints: string[]
  forbidden_actions: string[]
  source?: string
  created_at: string
  updated_at: string
}

export type LoreCategory =
  | 'world_rule'
  | 'geography'
  | 'history'
  | 'faction'
  | 'culture'
  | 'race'
  | 'profession'
  | 'character_setting'
  | 'item'
  | 'skill'
  | 'custom'

export type LorePriority =
  | 'constitutional'
  | 'core'
  | 'standard'
  | 'flexible'

export interface LoreSearchResult {
  id: string
  title: string
  category: LoreCategory
  priority: LorePriority
  summary?: string
  score: number
  keywords: string[]
}

export interface LoreValidationResult {
  valid: boolean
  conflicts: any[]
  warnings: string[]
  suggestions: string[]
}

export interface CreateLoreDTO {
  id: string
  project_id: string
  title: string
  category: LoreCategory
  priority: LorePriority
  content: string
  summary?: string
  keywords?: string[]
  tags?: string[]
  constraints?: string[]
  related_characters?: string[]
  related_character_refs?: ResolvedCharacterReference[]
  unresolved_character_refs?: UnresolvedCharacterReference[]
  related_locations?: string[]
  related_items?: string[]
  forbidden_actions?: string[]
  source?: string
}

export type LoreCharacterReferenceBindAction = 'bind_existing' | 'create_character'

export interface BindLoreCharacterPayload {
  name: string
  aliases?: string[]
  status?: Character['status']
  description?: string
  importance_tier?: CharacterImportanceTier
  narrative_weight?: NarrativeWeight
  story_arc_role?: StoryArcRole
  plot_priority?: number
  gender?: string
  age?: number | null
  appearance?: string
  personality?: string
  background_story?: string
  speech_pattern?: string
  lexicon?: string[]
  forbidden_words?: string[]
  voice_samples?: string[]
  has_agent?: boolean
  agent_enabled?: boolean
  agent_goals?: string[]
  agent_memory?: string[]
  world_id?: string
  current_location?: string
  current_region_id?: string
  current_location_reason?: string
}

export interface BindLoreCharacterReferenceDTO {
  project_id: string
  source_text: string
  action: LoreCharacterReferenceBindAction
  character_id?: string
  character?: BindLoreCharacterPayload
  provenance?: Record<string, unknown>
}

export interface BindLoreCharacterReferenceResponse {
  success: boolean
  lore_id: string
  project_id: string
  action: LoreCharacterReferenceBindAction
  character: {
    id: string
    name: string
    role?: string
    importance_tier?: CharacterImportanceTier | string
  }
  character_reference_resolution: CharacterReferenceResolution
  message: string
}

export interface UpdateLoreDTO {
  title?: string
  category?: LoreCategory
  priority?: LorePriority
  content?: string
  summary?: string
  keywords?: string[]
  tags?: string[]
  constraints?: string[]
  related_characters?: string[]
  related_character_refs?: ResolvedCharacterReference[]
  unresolved_character_refs?: UnresolvedCharacterReference[]
  related_locations?: string[]
  related_items?: string[]
  forbidden_actions?: string[]
  source?: string
}

export async function getLoreList(
  projectId: string,
  category?: LoreCategory,
  priority?: LorePriority,
  search?: string,
) {
  const params: Record<string, string> = { project_id: projectId }
  if (category) params.category = category
  if (priority) params.priority = priority
  if (search) params.search = search

  return await api.get<LoreEntry[]>('/lore', { params })
}

export async function getLore(id: string) {
  return await api.get<LoreEntry>(`/lore/${id}`)
}

export async function createLore(data: CreateLoreDTO) {
  return await api.post<LoreEntry>('/lore', data)
}

export async function updateLore(id: string, data: UpdateLoreDTO) {
  return await api.put<LoreEntry>(`/lore/${id}`, data)
}

export async function bindLoreCharacterReference(id: string, data: BindLoreCharacterReferenceDTO) {
  return await api.post<BindLoreCharacterReferenceResponse>(`/lore/${id}/character-references/bind`, data)
}

export async function deleteLore(id: string) {
  return await api.delete(`/lore/${id}`)
}

export async function searchLore(
  projectId: string,
  query: string,
  category?: LoreCategory,
) {
  return await api.post<LoreSearchResult[]>('/lore/search', null, {
    params: {
      project_id: projectId,
      query,
      category,
    },
  })
}

export async function validateContent(
  projectId: string,
  content: string,
  checkConstitutional: boolean = true,
) {
  return await api.post<LoreValidationResult>('/lore/validate', null, {
    params: {
      project_id: projectId,
      content,
      check_constitutional: checkConstitutional,
    },
  })
}

export async function getLoreCategories() {
  return await api.get<Array<{ value: string; label: string }>>('/lore/categories')
}

export async function getLorePriorities() {
  return await api.get<Array<{ value: string; label: string }>>('/lore/priorities')
}
