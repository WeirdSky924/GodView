import { api } from './client'
import type { AssistantContextSummary } from './assistantContext'

export interface World {
  id?: string
  name: string
  description: string
  world_type?: string
  tone?: string
  project_id?: string
  parent_world_id?: string | null
  scope_type?: string
  is_default?: boolean
  inherit_rules?: boolean
  order_index?: number
  metadata?: Record<string, any>
  rules?: string[]
  power_system?: string
  technology_level?: string
  history?: string
  geography?: string
  factions?: string[]
  // 多选标签字段
  content_styles?: string[]
  protagonist_types?: string[]
  character_archetypes?: string[]
  power_types?: string[]
  created_at?: string
  updated_at?: string
}

export interface Region {
  id?: string
  name: string
  world_id?: string
  region_type?: string
  terrain_type?: string
  description?: string
  atmosphere?: string
  state?: string
  state_summary?: string
  destroyed_at?: string
  coordinates?: { x?: number; y?: number; [key: string]: number | undefined }
  area_size?: number
  terrain_features?: Array<Record<string, unknown>>
  landmarks?: Array<Record<string, unknown>>
  encounters?: Array<Record<string, unknown>>
  connections?: string[]
  local_rules?: string[]
  is_generated?: boolean
  visit_count?: number
  created_at?: string
  updated_at?: string
}

export interface CreateWorldDTO {
  name: string
  description: string
  world_type?: string
  tone?: string
  project_id?: string
  parent_world_id?: string | null
  scope_type?: string
  is_default?: boolean
  inherit_rules?: boolean
  order_index?: number
  metadata?: Record<string, any>
  // 多选标签字段
  content_styles?: string[]
  protagonist_types?: string[]
  character_archetypes?: string[]
  power_types?: string[]
}

export interface UpdateWorldDTO {
  name: string
  description: string
  world_type?: string
  tone?: string
  project_id?: string
  parent_world_id?: string | null
  scope_type?: string
  is_default?: boolean
  inherit_rules?: boolean
  order_index?: number
  metadata?: Record<string, any>
  // 多选标签字段
  content_styles?: string[]
  protagonist_types?: string[]
  character_archetypes?: string[]
  power_types?: string[]
}

export type CreateRegionDTO = Omit<Region, 'id' | 'world_id' | 'created_at' | 'updated_at'> & {
  id?: string
}

export type UpdateRegionDTO = Partial<CreateRegionDTO> & {
  name: string
}

export interface WorldMapAgentGenerateRequest {
  project_id: string
  world_id: string
  message: string
  task?: 'create_draft' | 'match_or_generate' | 'query' | 'overview'
  selected_region_id?: string
  generation_count?: number
  include_existing_regions?: boolean
  assistant_session_id?: string
  request_id?: string
}

export interface WorldMapAgentDraftRegion extends CreateRegionDTO {
  client_id: string
  importance?: string
  validation_warnings?: string[]
}

export interface WorldMapAgentGenerateResponse {
  success: boolean
  message?: string
  overview?: string
  suggested_starting_location?: string
  draft_regions: WorldMapAgentDraftRegion[]
  matched_existing_region_ids?: string[]
  assistant_session_id?: string | null
  context_packet?: AssistantContextSummary | null
  metadata?: Record<string, unknown>
}

export async function getWorlds(projectId?: string) {
  const params = projectId ? { project_id: projectId } : {}
  return await api.get<World[]>('/worlds', { params })
}

export async function getWorld(id: string) {
  return await api.get<World>(`/worlds/${id}`)
}

export async function createWorld(data: CreateWorldDTO) {
  return await api.post<World>('/worlds', data)
}

export async function updateWorld(id: string, data: UpdateWorldDTO) {
  return await api.put<World>(`/worlds/${id}`, data)
}

export async function deleteWorld(id: string) {
  return await api.delete(`/worlds/${id}`)
}

export async function getRegions(worldId: string) {
  return await api.get<Region[]>(`/worlds/${worldId}/regions`)
}

export async function getRegion(worldId: string, regionId: string) {
  return await api.get<Region>(`/worlds/${worldId}/regions/${regionId}`)
}

export async function createRegion(worldId: string, data: CreateRegionDTO) {
  return await api.post<{ success: boolean; id: string; message: string }>(`/worlds/${worldId}/regions`, data)
}

export async function updateRegion(worldId: string, regionId: string, data: UpdateRegionDTO) {
  return await api.put<{ success: boolean; id: string; message: string }>(`/worlds/${worldId}/regions/${regionId}`, data)
}

export async function deleteRegion(worldId: string, regionId: string) {
  return await api.delete<{ success: boolean; id: string; message: string }>(`/worlds/${worldId}/regions/${regionId}`)
}

export async function generateWorldMapDrafts(worldId: string, data: WorldMapAgentGenerateRequest) {
  return await api.post<WorldMapAgentGenerateResponse>(`/worlds/${worldId}/agent/generate`, data)
}
