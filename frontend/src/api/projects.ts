import { client } from './client'
import { getCachedQuery, invalidateQueryCache, type QueryCacheOptions } from './queryCache'
import { withStartupRetry } from './startupRetry'

export interface Project {
  id: string
  name: string
  description?: string
  user_id?: string
  status: string
  world_id?: string
  world_type?: string
  tone?: string
  created_at: string
  updated_at: string
  metadata: Record<string, any>
}

export interface CreateProjectRequest {
  name: string
  description?: string
  user_id?: string
  world_type?: string
  tone?: string
  metadata?: Record<string, any>
}

export interface UpdateProjectRequest {
  name?: string
  description?: string
  status?: string
  world_type?: string
  tone?: string
  metadata?: Record<string, any>
}

export interface ProjectSummary extends Project {
  character_count: number
  chapter_count: number
}

export async function getProjects(status?: string, options: QueryCacheOptions = {}): Promise<Project[]> {
  const params = status ? `?status=${status}` : ''
  return getCachedQuery(
    `projects:list:${status || 'all'}`,
    () => withStartupRetry(
      () => client.get(`/projects${params}`),
      { label: 'projects' }
    ),
    { ttlMs: 30 * 1000, ...options }
  )
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
  const project = await client.post<Project>('/projects', data)
  invalidateProjectCaches()
  return project
}

export async function updateProject(id: string, data: UpdateProjectRequest): Promise<Project> {
  const project = await client.put<Project>(`/projects/${id}`, data)
  invalidateProjectCaches()
  return project
}

export async function deleteProject(id: string): Promise<void> {
  await client.delete(`/projects/${id}`)
  invalidateProjectCaches()
}

export function invalidateProjectCaches(): void {
  invalidateQueryCache('projects')
  invalidateQueryCache('global-stats')
}