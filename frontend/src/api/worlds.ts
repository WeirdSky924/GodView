import { api } from './client'

export interface World {
  id?: string
  name: string
  description: string
  world_type?: string
  tone?: string
  rules?: string[]
  power_system?: string
  technology_level?: string
  history?: string
  geography?: string
  factions?: string[]
  created_at?: string
  updated_at?: string
}

export interface CreateWorldDTO {
  name: string
  description: string
  world_type?: string
  tone?: string
}

export interface UpdateWorldDTO {
  name: string
  description: string
  world_type?: string
  tone?: string
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
