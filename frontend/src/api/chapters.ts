import { api } from './client'

export interface Chapter {
  id?: string
  title: string
  project_id?: string
  world_id?: string
  chapter_outline_id?: string
  summary?: string
  content?: string
  content_path?: string
  content_storage?: 'database' | 'filesystem'
  content_size_bytes?: number
  content_checksum?: string
  word_count?: number
  status: 'draft' | 'published' | 'archived' | 'in_progress' | 'completed'
  events?: string[]
  hooks_planted?: string[]
  hooks_resolved?: string[]
  main_plot_progress?: number
  reader_scores?: Record<string, number>
  created_at?: string
  updated_at?: string
  completed_at?: string
}

export interface CreateChapterDTO {
  title: string
  project_id?: string
  world_id?: string
  summary?: string
  content?: string
  status?: string
}

export interface UpdateChapterDTO {
  title?: string
  summary?: string
  content?: string
  status?: string
  world_id?: string
}

export interface ReaderSimulationResult {
  scores: {
    opening: number
    pacing: number
    suspense: number
    character: number
    emotion: number
    flow: number
  }
  overall: number
  comments: string
  suggestions: string[]
}

export interface ChapterEvaluationResult {
  should_end: boolean
  reason: string
  missing_elements?: string[]
  suggested_continuation?: string
  scores: {
    info_gain: number
    suspense: number
    pacing: number
    completeness: number
  }
}

export async function getChapters(projectId?: string, worldId?: string) {
  const params: Record<string, string> = {}
  if (projectId) params.project_id = projectId
  if (worldId) params.world_id = worldId
  return await api.get<Chapter[]>('/plots/chapters', { params })
}

export async function getChapter(id: string) {
  return await api.get<Chapter>(`/plots/chapters/${id}`)
}

export async function createChapter(data: CreateChapterDTO) {
  return await api.post<Chapter>('/plots/chapters', data)
}

export async function updateChapter(id: string, data: UpdateChapterDTO) {
  return await api.put<Chapter>(`/plots/chapters/${id}`, data)
}

export async function deleteChapter(id: string) {
  return await api.delete(`/plots/chapters/${id}`)
}

export async function evaluateChapter(id: string) {
  return await api.post<ChapterEvaluationResult>(`/plots/chapters/${id}/evaluate`)
}

export async function simulateReader(id: string) {
  return await api.post<ReaderSimulationResult>(`/plots/chapters/${id}/reader-simulate`)
}

export async function getHooks(
  projectId?: string,
  status?: string,
  options?: {
    worldId?: string
    includeInherited?: boolean
    scopeType?: string
    characterId?: string
  },
) {
  const params: Record<string, string | boolean> = {}
  if (projectId) params.project_id = projectId
  if (status) params.status = status
  if (options?.worldId) params.world_id = options.worldId
  if (options?.includeInherited !== undefined) params.include_inherited = options.includeInherited
  if (options?.scopeType) params.scope_type = options.scopeType
  if (options?.characterId) params.character_id = options.characterId
  return await api.get<any[]>('/plots/hooks', { params })
}

export async function createHook(data: {
  title: string
  description?: string
  hook_type?: string
  related_characters?: string[]
  priority?: number
  project_id?: string
  world_id?: string | null
  scope_type?: string
}) {
  return await api.post<any>('/plots/hooks', data)
}

export async function updateHookStatus(hookId: string, status: string) {
  return await api.put<any>(`/plots/hooks/${hookId}/status`, null, {
    params: { status },
  })
}

export async function updateHook(hookId: string, data: {
  title: string
  description?: string
  hook_type?: string
  related_characters?: string[]
  priority?: number
  project_id?: string
  status?: string
  world_id?: string | null
  scope_type?: string
}) {
  return await api.put<any>(`/plots/hooks/${hookId}`, data)
}

export async function deleteHook(hookId: string) {
  return await api.delete<any>(`/plots/hooks/${hookId}`)
}
