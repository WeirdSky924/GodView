import { api } from './client'

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
  related_locations?: string[]
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

  const response = await api.get<LoreEntry[]>('/lore', { params })
  return response.data
}

export async function getLore(id: string) {
  const response = await api.get<LoreEntry>(`/lore/${id}`)
  return response.data
}

export async function createLore(data: CreateLoreDTO) {
  const response = await api.post<LoreEntry>('/lore', data)
  return response.data
}

export async function updateLore(id: string, data: UpdateLoreDTO) {
  const response = await api.put<LoreEntry>(`/lore/${id}`, data)
  return response.data
}

export async function deleteLore(id: string) {
  const response = await api.delete(`/lore/${id}`)
  return response.data
}

export async function searchLore(
  projectId: string,
  query: string,
  category?: LoreCategory,
) {
  const response = await api.post<LoreSearchResult[]>('/lore/search', null, {
    params: {
      project_id: projectId,
      query,
      category,
    },
  })
  return response.data
}

export async function validateContent(
  projectId: string,
  content: string,
  checkConstitutional: boolean = true,
) {
  const response = await api.post<LoreValidationResult>('/lore/validate', null, {
    params: {
      project_id: projectId,
      content,
      check_constitutional: checkConstitutional,
    },
  })
  return response.data
}

export async function getLoreCategories() {
  const response = await api.get<Array<{ value: string; label: string }>>('/lore/categories')
  return response.data
}

export async function getLorePriorities() {
  const response = await api.get<Array<{ value: string; label: string }>>('/lore/priorities')
  return response.data
}
