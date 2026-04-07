/**
 * 时间系统API接口
 * GodView v5 时间流逝系统前端API
 */

import { api } from './client'

/**
 * 时间系统配置
 */
export interface TimeSystemConfig {
  world_id: string
  time_scale: number
  time_mode: 'linear' | 'nonlinear' | 'frozen'
  day_length: number
  enable_recording: boolean
  tick_interval_seconds: number
}

/**
 * 时间更新结果
 */
export interface TimeUpdateResult {
  current_time: string
  previous_time: string
  time_delta_minutes: number
  time_scale: number
  tick_count: number
  day_of_week: number
  day_of_week_name: string
  hour: number
  minute: number
  day_phase: string
  season: string
  triggered_events: Array<{
    event_type: string
    data: any
    trigger_time: string
  }>
}

/**
 * 时间系统状态
 */
export interface TimeSystemStatus {
  world_id: string
  time_info: {
    current_time: string
    formatted_time: string
    tick_count: number
    time_scale: number
    day_of_week: number
    day_of_week_name: string
    hour: number
    minute: number
    day_phase: string
    season: string
    month: number
    day: number
    year: number
  }
  time_mode: string
  is_frozen: boolean
}

/**
 * 时间分支信息
 */
export interface TimeBranchInfo {
  id: string
  name: string
  time: string
  tick_count: number
  created_at: string
  scheduled_events_count: number
}

/**
 * 时间点记录
 */
export interface TimePointRecord {
  id: string
  time: string
  tick_count: number
  note: string
  day_phase: string
  season: string
}

/**
 * 时间历史响应
 */
export interface TimeHistoryResponse {
  time_points: TimePointRecord[]
  branches: TimeBranchInfo[]
  current_time: string
  time_mode: string
  tick_count: number
}

/**
 * 创建时间系统
 */
export async function createTimeSystem(worldId: string, config: Partial<TimeSystemConfig> = {}) {
  return api.post('/time/systems/' + worldId, {
    world_id: worldId,
    time_scale: config.time_scale || 1.0,
    time_mode: config.time_mode || 'linear',
    day_length: config.day_length || 24,
    enable_recording: config.enable_recording !== false,
    tick_interval_seconds: config.tick_interval_seconds || 1.0,
  })
}

/**
 * 获取时间系统状态
 */
export async function getTimeSystemStatus(worldId: string): Promise<TimeSystemStatus> {
  const response = await api.get('/time/systems/' + worldId)
  return response.data
}

/**
 * 时间控制操作
 */
export async function controlTime(
  worldId: string,
  action: 'freeze' | 'unfreeze' | 'set_scale' | 'advance' | 'set_mode',
  options?: {
    time_scale?: number
    advance_minutes?: number
    mode?: 'linear' | 'nonlinear' | 'frozen'
  }
) {
  return api.post('/time/control', {
    world_id: worldId,
    action,
    ...options,
  })
}

/**
 * 时间跳跃操作
 */
export async function timeJump(
  worldId: string,
  jumpType: 'forward' | 'backward' | 'to_absolute' | 'to_year',
  options?: {
    target_time?: string
    delta_minutes?: number
    target_year?: number
    note?: string
  }
) {
  return api.post('/time/jump', {
    world_id: worldId,
    jump_type: jumpType,
    ...options,
  })
}

/**
 * 创建时间分支
 */
export async function createTimeBranch(
  worldId: string,
  branchName: string,
  note: string = ''
) {
  return api.post('/time/branches', {
    world_id: worldId,
    branch_name: branchName,
    note,
  })
}

/**
 * 获取时间分支列表
 */
export async function getTimeBranches(worldId: string): Promise<{ success: boolean; world_id: string; branches: TimeBranchInfo[]; count: number }> {
  const response = await api.get('/time/branches/' + worldId)
  return response.data
}

/**
 * 切换时间分支
 */
export async function switchTimeBranch(worldId: string, branchId: string) {
  return api.post('/time/branches/' + worldId + '/switch', null, {
    params: { branch_id: branchId }
  })
}

/**
 * 记录时间点
 */
export async function recordTimePoint(worldId: string, note: string) {
  return api.post('/time/record', {
    world_id: worldId,
    note,
  })
}

/**
 * 获取时间历史
 */
export async function getTimeHistory(worldId: string, limit: number = 100): Promise<TimeHistoryResponse> {
  const response = await api.get('/time/history/' + worldId, {
    params: { limit }
  })
  return response.data
}

// WebSocket 相关类型
export type TimeWebSocketMessage =
  | { type: 'connected'; data: any }
  | { type: 'time_update'; data: TimeUpdateResult }
  | { type: 'time_info'; data: any }
  | { type: 'tick_result'; data: any }
  | { type: 'freeze_toggle'; data: any }
  | { type: 'scale_set'; data: any }

/**
 * WebSocket 时间更新处理器类型
 */
export type TimeUpdateHandler = (update: TimeUpdateResult) => void
export type TimeConnectionHandler = (data: any) => void
export type ErrorHandler = (error: Event) => void