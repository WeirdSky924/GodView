import { api } from './client'

export interface WorkflowGraph {
  nodes: Array<{ id: string; label: string }>
  edges: Array<{ source: string; target: string }>
}

export interface SnapshotTreeNode {
  id: string
  name?: string
  snapshot_type?: string
  parent_snapshot_id?: string | null
  is_branch?: boolean
  branch_reason?: string | null
  created_at?: string
  children?: SnapshotTreeNode[]
}

export interface DirectorRuntimeState {
  world_id: string
  current_chapter?: Record<string, any> | null
  chapter_events: Array<Record<string, any>>
  dialogue_history: Array<Record<string, any>>
  hooks_planted: string[]
  hooks_resolved: string[]
  main_plot_progress: number
  current_snapshot_id?: string | null
  state_machine: Record<string, any>
  regions: Array<Record<string, any>>
}

export async function getWorkflowGraph(sessionId: string) {
  return await api.get<WorkflowGraph>(`/ws/workflow/${sessionId}`)
}

export async function getDirectorState(sessionId: string) {
  return await api.get<{ success: boolean; data: DirectorRuntimeState }>(`/ws/snapshots/${sessionId}`)
}

export async function getSnapshotTree(worldId: string) {
  return await api.get<{ success: boolean; data: SnapshotTreeNode[] }>(`/plots/snapshots/tree`, {
    params: { world_id: worldId },
  })
}
