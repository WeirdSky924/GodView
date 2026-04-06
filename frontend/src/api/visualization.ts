import { api } from './client'

export interface DiffLine {
  type: 'added' | 'removed' | 'unchanged'
  content: string
}

export interface DiffSummary {
  added: number
  removed: number
  unchanged: number
}

export interface SnapshotDiffResult {
  summary: DiffSummary
  lines: DiffLine[]
  left_label: string
  right_label: string
}

export async function compareSnapshots(leftSnapshotId: string, rightSnapshotId: string) {
  const response = await api.get<SnapshotDiffResult>('/plots/snapshots/diff', {
    params: {
      left_snapshot_id: leftSnapshotId,
      right_snapshot_id: rightSnapshotId,
    },
  })
  return response.data
}

export async function getVisualizationData(worldId: string) {
  const response = await api.get('/plots/visualization', {
    params: { world_id: worldId },
  })
  return response.data
}
