/**
 * Setting Agent API
 * 设定管理 Agent 接口
 */

import axios from 'axios'

const API_BASE = '/api/setting-agent'

// ==================== 类型定义 ====================

export interface ChatResponse {
  response: string
  session_id: string
  mode: string
}

export interface SettingConflict {
  id: string
  conflict_type: string
  description: string
  severity: 'low' | 'medium' | 'high' | 'critical'
  existing_lore_id?: string
  existing_lore_title?: string
  new_lore_title?: string
  status: 'pending' | 'negotiating' | 'resolved' | 'escalated'
  resolution_suggestions: string[]
  selected_resolution?: string
  detected_at: string
  resolved_at?: string
}

export interface SettingChangeResult {
  success: boolean
  request: {
    id: string
    project_id: string
    change_type: string
    target_lore_id?: string
    new_lore_data?: Record<string, unknown>
    conflicts: SettingConflict[]
    has_conflicts: boolean
    status: string
    created_at: string
  }
  has_conflicts: boolean
  conflicts: SettingConflict[]
}

export interface NegotiateResult {
  status: 'resolved' | 'negotiating'
  conflict?: SettingConflict
  can_proceed: boolean
  response?: string
  suggestions?: string[]
}

export interface ExecuteResult {
  success: boolean
  result?: Record<string, unknown>
  error?: string
  unresolved_conflicts?: SettingConflict[]
}

export interface LoreSummary {
  project_id: string
  total_lore_count: number
  by_category: Record<string, number>
  by_priority: Record<string, number>
  constitutional_rules: string[]
  key_entities: string[]
  recent_changes: Array<Record<string, unknown>>
  pending_conflicts: number
  generated_at: string
}

export interface ConversationHistory {
  project_id: string
  session_id: string
  history: Array<{
    role: 'user' | 'assistant'
    content: string
    timestamp: string
  }>
  total: number
}

export interface PendingConflicts {
  project_id: string
  pending_conflicts: SettingConflict[]
  count: number
}

// ==================== API 函数 ====================

/**
 * 与 Setting Agent 聊天
 */
export async function chatWithSettingAgent(
  projectId: string,
  message: string,
  context?: Record<string, unknown>
): Promise<ChatResponse> {
  const response = await axios.post(`${API_BASE}/chat`, {
    project_id: projectId,
    message,
    context,
  })
  return response.data
}

/**
 * 请求设定变更
 */
export async function requestSettingChange(
  projectId: string,
  changeType: 'add' | 'modify' | 'delete' | 'merge',
  loreData?: Record<string, unknown>,
  targetLoreId?: string,
  userIntent?: string
): Promise<SettingChangeResult> {
  const response = await axios.post(`${API_BASE}/change`, {
    project_id: projectId,
    change_type: changeType,
    lore_data: loreData,
    target_lore_id: targetLoreId,
    user_intent: userIntent,
  })
  return response.data
}

/**
 * 协商解决冲突
 */
export async function negotiateConflict(
  projectId: string,
  conflictId: string,
  userResponse: string
): Promise<NegotiateResult> {
  const response = await axios.post(`${API_BASE}/negotiate`, {
    project_id: projectId,
    conflict_id: conflictId,
    user_response: userResponse,
  })
  return response.data
}

/**
 * 执行设定变更
 */
export async function executeSettingChange(
  projectId: string,
  requestId: string,
  overrideConflicts: boolean = false
): Promise<ExecuteResult> {
  const response = await axios.post(`${API_BASE}/execute`, {
    project_id: projectId,
    request_id: requestId,
    override_conflicts: overrideConflicts,
  })
  return response.data
}

/**
 * 获取设定摘要
 */
export async function getLoreSummary(projectId: string): Promise<LoreSummary> {
  const response = await axios.get(`${API_BASE}/${projectId}/summary`)
  return response.data
}

/**
 * 获取对话历史
 */
export async function getChatHistory(
  projectId: string,
  limit: number = 50
): Promise<ConversationHistory> {
  const response = await axios.get(`${API_BASE}/${projectId}/history`, {
    params: { limit },
  })
  return response.data
}

/**
 * 获取待处理冲突
 */
export async function getPendingConflicts(projectId: string): Promise<PendingConflicts> {
  const response = await axios.get(`${API_BASE}/${projectId}/conflicts`)
  return response.data
}

/**
 * 创建或获取会话
 */
export async function createOrGetSession(
  projectId: string,
  mode: 'bootstrap' | 'management' | 'conflict_resolution' = 'management'
): Promise<{ success: boolean; session: Record<string, unknown> }> {
  const response = await axios.post(`${API_BASE}/${projectId}/session`, null, {
    params: { mode },
  })
  return response.data
}
