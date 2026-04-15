/**
 * 世界模拟API接口
 * GodView v5 世界模拟系统前端API
 */

import { api } from './client'

/**
 * 模拟状态枚举
 */
export enum SimulationStatus {
  STOPPED = 'stopped',
  RUNNING = 'running',
  PAUSED = 'paused',
  ERROR = 'error'
}

/**
 * 性能统计数据
 */
export interface PerformanceStats {
  average_tick_duration: number
  max_tick_duration: number
  total_ticks: number
  error_count: number
  current_tick: number
  status: string
  is_running: boolean
  is_paused: boolean
  last_tick_time?: string
}

/**
 * 世界模拟状态响应
 */
export interface SimulationStatusResponse {
  world_id: string
  status: SimulationStatus
  performance: PerformanceStats
  current_time?: string
  entity_count: number
  active_events: number
  last_update: string
}

/**
 * 模拟初始化请求
 */
export interface SimulationInitializeRequest {
  world_id: string
  time_config?: {
    time_scale?: number
    time_mode?: 'linear' | 'nonlinear' | 'frozen'
    day_length?: number
  }
  entities?: Array<{
    id: string
    name: string
    type: string
    config?: any
  }>
  locations?: Array<{
    id: string
    name: string
    type: string
    config?: any
  }>
}

/**
 * 模拟控制请求
 */
export interface SimulationControlRequest {
  world_id: string
  action: 'start' | 'stop' | 'pause' | 'resume' | 'manual_tick' | 'set_interval'
  tick_interval?: number
}

/**
 * 模拟控制结果
 */
export interface SimulationControlResult {
  success: boolean
  world_id: string
  result: {
    action: string
    message: string
    tick_interval?: number
  }
  performance: PerformanceStats
}

/**
 * 世界状态快照
 */
export interface WorldStateSnapshot {
  world_id: string
  snapshot_id: string
  timestamp: string
  time_system?: {
    current_time: string
    time_scale: number
    tick_count: number
  }
  entities: Array<any>
  locations: Array<any>
  active_events: Array<any>
  memory_snapshots: Record<string, any>
  performance: PerformanceStats
}

/**
 * 初始化世界模拟
 */
export async function initializeSimulation(
  request: SimulationInitializeRequest
): Promise<{
  success: boolean
  world_id: string
  message: string
  time_info?: any
}> {
  return api.post('/simulation/initialize', request)
}

/**
 * 控制世界模拟
 */
export async function controlSimulation(
  request: SimulationControlRequest
): Promise<SimulationControlResult> {
  return api.post('/simulation/control', request)
}

/**
 * 启动模拟
 */
export async function startSimulation(worldId: string): Promise<SimulationControlResult> {
  return controlSimulation({ world_id: worldId, action: 'start' })
}

/**
 * 停止模拟
 */
export async function stopSimulation(worldId: string): Promise<SimulationControlResult> {
  return controlSimulation({ world_id: worldId, action: 'stop' })
}

/**
 * 暂停模拟
 */
export async function pauseSimulation(worldId: string): Promise<SimulationControlResult> {
  return controlSimulation({ world_id: worldId, action: 'pause' })
}

/**
 * 恢复模拟
 */
export async function resumeSimulation(worldId: string): Promise<SimulationControlResult> {
  return controlSimulation({ world_id: worldId, action: 'resume' })
}

/**
 * 手动执行一个时钟周期
 */
export async function manualTick(worldId: string): Promise<SimulationControlResult> {
  return controlSimulation({ world_id: worldId, action: 'manual_tick' })
}

/**
 * 设置时钟周期间隔
 */
export async function setTickInterval(
  worldId: string,
  interval: number
): Promise<SimulationControlResult> {
  return controlSimulation({ world_id: worldId, action: 'set_interval', tick_interval: interval })
}

/**
 * 获取模拟状态
 */
export async function getSimulationStatus(worldId: string): Promise<SimulationStatusResponse> {
  return await api.get('/simulation/status/' + worldId)
}

/**
 * 创建世界模拟快照
 */
export async function createSimulationSnapshot(
  worldId: string,
  note: string = ''
): Promise<{
  success: boolean
  world_id: string
  snapshot_id: string
  snapshot: WorldStateSnapshot
  message: string
}> {
  return api.post('/simulation/snapshot/' + worldId, null, {
    params: { note }
  })
}

/**
 * 列出所有模拟引擎
 */
export async function listSimulationEngines(): Promise<{
  success: boolean
  count: number
  engines: Array<{
    world_id: string
    status: string
    is_running: boolean
    is_paused: boolean
    current_tick: number
    total_ticks: number
    performance: PerformanceStats
  }>
}> {
  return await api.get('/simulation/engines')
}

// WebSocket 相关类型
export type SimulationWebSocketMessage =
  | { type: 'connected'; data: any }
  | { type: 'status_update'; data: SimulationStatusResponse }
  | { type: 'world_state_update'; data: any }
  | { type: 'simulation_started'; data: { success: boolean; status: string } }
  | { type: 'simulation_stopped'; data: { success: boolean; status: string } }
  | { type: 'pause_toggled'; data: { success: boolean; action: string; status: string } }
  | { type: 'manual_tick_executed'; data: { success: boolean; tick_count: number; performance: PerformanceStats } }
  | { type: 'interval_set'; data: { tick_interval: number; message: string } }
  | { type: 'snapshot_created'; data: { snapshot_id: string; timestamp: string; data: WorldStateSnapshot; note: string } }

/**
 * WebSocket 消息处理器类型
 */
export type StatusUpdateHandler = (data: SimulationStatusResponse) => void
export type WorldStateUpdateHandler = (data: any) => void
export type GenericHandler = (data: any) => void