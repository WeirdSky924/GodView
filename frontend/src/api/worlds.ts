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
  const response = await api.get<World[]>('/worlds', { params })
  return response.data
}

export async function getWorld(id: string) {
  const response = await api.get<World>(`/worlds/${id}`)
  return response.data
}

export async function createWorld(data: CreateWorldDTO) {
  const response = await api.post<World>('/worlds', data)
  return response.data
}

export async function updateWorld(id: string, data: UpdateWorldDTO) {
  const response = await api.put<World>(`/worlds/${id}`, data)
  return response.data
}

export async function deleteWorld(id: string) {
  const response = await api.delete(`/worlds/${id}`)
  return response.data
}
