import { client } from './client'

// ==================== 类型定义 ====================

export interface BootstrapSession {
  id: string
  project_id: string
  status: string
  current_stage: string
  progress: number
  setting_agent_history: any[]
  extracted_seed: Record<string, any>
  confirmed_seed: Record<string, any>
  error_message?: string
  retry_count: number
  created_at: string
  updated_at: string
  completed_at?: string
}

export interface BootstrapStatus {
  session_id: string
  project_id: string
  status: string
  current_stage: string
  progress: number
  error_message?: string
  retry_count: number
  created_at: string
  updated_at: string
  completed_at?: string
}

export interface SeedData {
  world_setting: {
    name: string
    description: string
    world_type: string
    tone: string
  }
  world_rules: any[]
  power_system?: string
  technology_level?: string
  main_characters: any[]
  supporting_characters: any[]
  regions: any[]
  plot_hooks: any[]
  narrative_tone?: string
  writing_style?: string
}

// ==================== API 函数 ====================

export async function startBootstrap(projectId: string, initialMessage?: string): Promise<{ session: BootstrapSession }> {
  return client.post('/bootstrap/start', {
    project_id: projectId,
    initial_message: initialMessage,
  })
}

export async function getBootstrapSession(sessionId: string): Promise<BootstrapSession> {
  return client.get(`/bootstrap/${sessionId}`)
}

export async function getBootstrapStatus(sessionId: string): Promise<BootstrapStatus> {
  return client.get(`/bootstrap/${sessionId}/status`)
}

export async function sendBootstrapMessage(sessionId: string, message: string, projectId?: string): Promise<any> {
  return client.post('/bootstrap/message', {
    session_id: sessionId,
    message,
    project_id: projectId,
  })
}

export async function uploadOutline(
  sessionId: string,
  content: string,
  sourceType: string = 'pasted_text'
): Promise<any> {
  return client.post('/bootstrap/outline', {
    session_id: sessionId,
    content,
    source_type: sourceType,
  })
}

export async function confirmSeed(sessionId: string, seedData: SeedData): Promise<{ session: BootstrapSession }> {
  return client.post(`/bootstrap/${sessionId}/confirm`, {
    session_id: sessionId,
    seed_data: seedData,
  })
}

export async function reviseSeed(sessionId: string, feedback: string): Promise<{ session: BootstrapSession }> {
  return client.post(`/bootstrap/${sessionId}/revise`, {
    session_id: sessionId,
    feedback,
  })
}

export async function runBootstrap(sessionId: string): Promise<any> {
  return client.post(`/bootstrap/${sessionId}/run`)
}

export async function getSeed(sessionId: string): Promise<any> {
  return client.get(`/bootstrap/${sessionId}/seed`)
}

export async function getBootstrapMessages(sessionId: string, limit: number = 50): Promise<any[]> {
  return client.get(`/bootstrap/${sessionId}/messages?limit=${limit}`)
}

/**
 * 结束设定阶段并强制提取 Seed
 * 不依赖对话轮数阈值，直接从当前对话历史中提取结构化 seed
 */
export async function finalizeSetting(sessionId: string): Promise<{
  success: boolean
  message: string
  seed_data: SeedData
  session: BootstrapSession
}> {
  return client.post(`/bootstrap/${sessionId}/finalize-setting`)
}