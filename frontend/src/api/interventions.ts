import { api } from './client'

export interface Intervention {
  id?: string
  snapshot_id?: string
  intervention_type: 'character_edit' | 'plot_change' | 'hook_modification' | 'relationship_change' | 'world_edit'
  description: string
  details?: Record<string, any>
  affected_hooks?: string[]
  affected_relationships?: string[]
  affected_characters?: string[]
  outcome_rating?: number
  outcome_notes?: string
  created_at?: string
}

export interface SnapshotOption {
  id: string
  name: string
  description?: string
  world_id?: string
  chapter_id?: string
  created_at?: string
}

export async function getInterventions() {
  return await api.get<Intervention[]>('/plots/interventions')
}

export async function createIntervention(data: Intervention) {
  return await api.post<{ success: boolean; id: string; message: string }>('/plots/interventions', data)
}

export async function updateInterventionEvaluation(
  interventionId: string,
  data: { outcome_rating?: number; outcome_notes?: string }
) {
  return await api.put<{ success: boolean; data: Intervention }>(
    `/plots/interventions/${interventionId}/evaluation`,
    data,
  )
}

export async function getSnapshots(worldId?: string) {
  return await api.get<SnapshotOption[]>('/plots/snapshots', {
    params: worldId ? { world_id: worldId } : {},
  })
}
