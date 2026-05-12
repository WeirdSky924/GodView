/**
 * Setting Agent API
 * 设定管理 Agent 接口
 */

import { api } from './client'
import type { AssistantContextSummary } from './assistantContext'

const API_BASE = '/setting-agent'

// ==================== 类型定义 ====================

export interface CharacterReferenceCandidate {
  character_id: string
  name: string
  role?: string
  importance_tier?: string
  description?: string
  match_reason: string
  confidence: number
}

export interface ResolvedCharacterReference {
  status: 'resolved'
  source_text: string
  source_payload?: unknown
  character_id: string
  character_name: string
  confidence: number
  resolution_method: string
  provenance?: Record<string, unknown>
}

export interface UnresolvedCharacterReference {
  status: 'unresolved' | 'ambiguous'
  source_text: string
  source_payload?: unknown
  reason: string
  message: string
  candidates: CharacterReferenceCandidate[]
  recommended_actions: Array<'bind_existing' | 'create_character' | 'keep_text_only' | 'ignore'>
  provenance?: Record<string, unknown>
}

export interface CharacterReferenceResolution {
  success?: boolean
  related_characters: string[]
  related_character_refs: ResolvedCharacterReference[]
  unresolved_character_refs: UnresolvedCharacterReference[]
  has_unresolved: boolean
}

export interface PendingLore {
  title: string
  category: string
  priority: string
  content: string
  summary: string
  keywords: string[]
  tags: string[]
  constraints: string[]
  related_characters: string[]
  related_character_refs?: ResolvedCharacterReference[]
  unresolved_character_refs?: UnresolvedCharacterReference[]
  related_locations: string[]
  related_items: string[]
  related_factions?: string[]
  depends_on_lore?: string[]
  supports_lore?: string[]
  potential_conflicts?: string[]
  usage_guidance?: string
  resource_requirements?: Array<Record<string, unknown>>
}

export interface PendingCharacter {
  id?: string
  name: string
  importance_tier: string
  description: string
  appearance: string
  personality: string
  background_story: string
  speech_pattern: string
  age: number | null
  gender: string
  goals: string[]
  relationships?: string[]
  key_relationships?: Record<string, string>
  lexicon?: string[]
  forbidden_words?: string[]
  voice_samples?: string[]
  attributes?: Record<string, unknown>
  inventory?: string[]
  narrative_weight?: string
  story_arc_role?: string
  plot_priority?: number
  has_agent?: boolean
  agent_enabled?: boolean
  agent_goals?: string[]
  agent_memory?: string[]
}

export interface PendingHook {
  title: string
  description: string
  hook_type: 'mystery' | 'object' | 'character' | 'event' | 'location' | 'relationship' | 'custom'
  status: 'planted' | 'triggered' | 'resolved' | 'dropped'
  related_characters: string[]
  related_locations: string[]
  related_objects: string[]
  plant_context: string
  resolution_hint: string
  priority: number
}

export interface ChatResponse {
  message: string
  session_id: string
  mode: string
  structured_data?: Record<string, unknown>
  lore_saved?: boolean
  pending_lores?: PendingLore[]
  pending_characters?: PendingCharacter[]
  pending_hooks?: PendingHook[]
  cached_pending_lores?: PendingLore[]
  cached_pending_characters?: PendingCharacter[]
  cached_pending_hooks?: PendingHook[]
  conversation_history?: Array<{
    role: 'user' | 'assistant'
    content: string
    timestamp?: string
  }>
  improvement_suggestions?: ImprovementSuggestion[]
  assistant_session_id?: string
  context_packet?: AssistantContextSummary
}

export interface ImprovementSuggestion {
  id: string
  type: 'conflict' | 'missing' | 'priority' | 'optimize' | 'relation'
  target_lore_id?: string
  target_lore_title: string
  issue: string
  suggestion: string
  suggested_content?: string
  priority: 'low' | 'medium' | 'high'
  reason: string
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
  message?: string
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
  project_id?: string
  session_id: string
  messages?: Array<{
    role: 'user' | 'assistant'
    content: string
    timestamp?: string
    created_at?: string
  }>
  history?: Array<{
    role: 'user' | 'assistant'
    content: string
    timestamp: string
  }>
  pending_lores?: PendingLore[]
  pending_characters?: PendingCharacter[]
  pending_hooks?: PendingHook[]
  context_packet?: AssistantContextSummary | null
  assistant_session_id?: string
  total?: number
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
  context?: Record<string, unknown>,
  options?: { sessionId?: string; requestId?: string },
): Promise<ChatResponse> {
  return await api.post(`${API_BASE}/chat`, {
    project_id: projectId,
    message,
    context,
    session_id: options?.sessionId,
    request_id: options?.requestId,
  })
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
  return await api.post(`${API_BASE}/change`, {
    project_id: projectId,
    change_type: changeType,
    lore_data: loreData,
    target_lore_id: targetLoreId,
    user_intent: userIntent,
  })
}

/**
 * 协商解决冲突
 */
export async function negotiateConflict(
  projectId: string,
  conflictId: string,
  userResponse: string
): Promise<NegotiateResult> {
  return await api.post(`${API_BASE}/negotiate`, {
    project_id: projectId,
    conflict_id: conflictId,
    user_response: userResponse,
  })
}

/**
 * 执行设定变更
 */
export async function executeSettingChange(
  projectId: string,
  requestId: string,
  overrideConflicts: boolean = false
): Promise<ExecuteResult> {
  return await api.post(`${API_BASE}/execute`, {
    project_id: projectId,
    request_id: requestId,
    override_conflicts: overrideConflicts,
  })
}

/**
 * 获取设定摘要
 */
export async function getLoreSummary(projectId: string): Promise<LoreSummary> {
  return await api.get(`${API_BASE}/${projectId}/summary`)
}

/**
 * 获取对话历史
 */
export async function getChatHistory(
  projectId: string,
  sessionId?: string,
): Promise<ConversationHistory> {
  return await api.get(`${API_BASE}/${projectId}/history`, {
    params: { session_id: sessionId },
  })
}

/**
 * 获取待处理冲突
 */
export async function getPendingConflicts(projectId: string): Promise<PendingConflicts> {
  return await api.get(`${API_BASE}/${projectId}/conflicts`)
}

/**
 * 创建或获取会话
 */
export async function createOrGetSession(
  projectId: string,
  mode: 'bootstrap' | 'management' | 'conflict_resolution' = 'management',
  sessionId?: string,
): Promise<{
  success: boolean
  session_id: string
  mode: string
  pending_lores?: PendingLore[]
  pending_characters?: PendingCharacter[]
  pending_hooks?: PendingHook[]
}> {
  return await api.post(`${API_BASE}/${projectId}/session`, null, {
    params: { mode, session_id: sessionId },
  })
}

/**
 * 兼容少数旧调用：读取会话必须仍然使用 POST，避免 GET /session 405。
 */
export async function getOrCreateSession(
  projectId: string,
  mode: 'bootstrap' | 'management' | 'conflict_resolution' = 'management',
  sessionId?: string,
) {
  return createOrGetSession(projectId, mode, sessionId)
}

/**
 * 保存用户确认的设定
 */
export async function resolveCharacterReferences(
  projectId: string,
  references: unknown[],
  provenance?: Record<string, unknown>,
): Promise<CharacterReferenceResolution> {
  return await api.post(`${API_BASE}/resolve-character-references`, {
    project_id: projectId,
    references,
    provenance,
  })
}

export async function savePendingLores(
  projectId: string,
  lores: PendingLore[],
  options?: { sessionId?: string; requestId?: string },
): Promise<{ success: boolean; saved_count: number; message: string; character_reference_resolution?: CharacterReferenceResolution }> {
  return await api.post(`${API_BASE}/save-lores`, {
    project_id: projectId,
    lores,
    session_id: options?.sessionId,
    request_id: options?.requestId,
  })
}

/**
 * 保存用户确认的角色
 */
export async function savePendingCharacters(
  projectId: string,
  characters: PendingCharacter[],
  options?: { sessionId?: string; requestId?: string },
): Promise<{ success: boolean; saved_count: number; message: string }> {
  return await api.post(`${API_BASE}/save-characters`, {
    project_id: projectId,
    characters,
    session_id: options?.sessionId,
    request_id: options?.requestId,
  })
}

/**
 * 保存用户确认的伏笔
 */
export async function savePendingHooks(
  projectId: string,
  hooks: PendingHook[],
  options?: { sessionId?: string; requestId?: string },
): Promise<{ success: boolean; saved_count: number; message: string }> {
  return await api.post(`${API_BASE}/save-hooks`, {
    project_id: projectId,
    hooks,
    session_id: options?.sessionId,
    request_id: options?.requestId,
  })
}

/**
 * 执行设定修改
 */
export async function executeLoreModification(
  projectId: string,
  modification: ImprovementSuggestion
): Promise<{ success: boolean; message?: string; error?: string; character_reference_resolution?: CharacterReferenceResolution }> {
  return await api.post(`${API_BASE}/execute-modification`, {
    project_id: projectId,
    modification,
  })
}

/**
 * 世界观描述结构化分析 (strict)
 */
export interface WorldDescriptionAnalysis {
  power_system: string
  technology_level: string
  history: string
  geography: string
}

export async function analyzeWorldDescription(
  projectId: string,
  description: string
): Promise<{ structured_data: WorldDescriptionAnalysis }> {
  return await api.post(`${API_BASE}/analyze-world`, {
    project_id: projectId,
    description,
  })
}
