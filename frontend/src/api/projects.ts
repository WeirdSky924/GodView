import { client } from './client'

export interface Project {
  id: string
  name: string
  description?: string
  user_id?: string
  status: string
  world_id?: string
  created_at: string
  updated_at: string
  metadata: Record<string, any>
}

export interface CreateProjectRequest {
  name: string
  description?: string
  user_id?: string
  metadata?: Record<string, any>
}

export interface UpdateProjectRequest {
  name?: string
  description?: string
  status?: string
  metadata?: Record<string, any>
}

export interface ProjectSummary extends Project {
  character_count: number
  chapter_count: number
}

export async function getProjects(status?: string): Promise<Project[]> {
  const params = status ? `?status=${status}` : ''
  return client.get(`/projects${params}`)
}

export async function getProjectSummaries(status?: string): Promise<ProjectSummary[]> {
  const params = status ? `?status=${status}` : ''
  return client.get(`/projects/summary${params}`)
}

export async function getProject(id: string): Promise<Project> {
  return client.get(`/projects/${id}`)
}

export async function getProjectSummary(id: string): Promise<ProjectSummary> {
  return client.get(`/projects/${id}/summary`)
}

export async function createProject(data: CreateProjectRequest): Promise<Project> {
  return client.post('/projects', data)
}

export async function updateProject(id: string, data: UpdateProjectRequest): Promise<Project> {
  return client.put(`/projects/${id}`, data)
}

export async function deleteProject(id: string): Promise<void> {
  return client.delete(`/projects/${id}`)
}