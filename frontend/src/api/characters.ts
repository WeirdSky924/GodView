import { api } from './client'

// 角色重要性层级枚举
export enum CharacterImportanceTier {
  // 主角层 (Tier 1)
  PROTAGONIST = 'protagonist',
  CO_PROTAGONIST = 'co_protagonist',
  // 核心配角层 (Tier 2)
  DEUTERAGONIST = 'deuteragonist',
  MENTOR = 'mentor',
  LOVE_INTEREST = 'love_interest',
  BEST_FRIEND = 'best_friend',
  ARCHENEMY = 'archenemy',
  // 重要配角层 (Tier 3)
  MAJOR_ALLY = 'major_ally',
  MAJOR_ANTAGONIST = 'major_antagonist',
  RIVAL = 'rival',
  FAMILY_MEMBER = 'family_member',
  GUARDIAN = 'guardian',
  // 阶段性角色层 (Tier 4)
  ARC_ANTAGONIST = 'arc_antagonist',
  ARC_ALLY = 'arc_ally',
  RECURRING = 'recurring',
  CATALYST = 'catalyst',
  MYSTERY_FIGURE = 'mystery_figure',
  // 功能性角色层 (Tier 5)
  MINION = 'minion',
  INFORMANT = 'informant',
  MENTOR_FIGURE = 'mentor_figure',
  COMIC_RELIEF = 'comic_relief',
  VICTIM = 'victim',
  // 背景层 (Tier 6)
  NPC = 'npc',
  BACKGROUND = 'background',
  CAMEO = 'cameo',
}

// 叙事权重枚举
export enum NarrativeWeight {
  FULL_FOCUS = 'full_focus',
  MAJOR_FOCUS = 'major_focus',
  MODERATE = 'moderate',
  MINIMAL = 'minimal',
  BACKGROUND = 'background',
}

// 故事弧角色枚举
export enum StoryArcRole {
  HERO = 'hero',
  GUIDE = 'guide',
  HELPER = 'helper',
  PROTECTOR = 'protector',
  MENTOR_ROLE = 'mentor_role',
  VILLAIN = 'villain',
  OBSTACLE = 'obstacle',
  BETRAYER = 'betrayer',
  CORRUPTOR = 'corruptor',
  NEUTRAL = 'neutral',
  WILD_CARD = 'wild_card',
  DOUBLE_AGENT = 'double_agent',
  SACRIFICE = 'sacrifice',
  REDEEMED = 'redeemed',
  TRAGIC = 'tragic',
  HERALD = 'herald',
}

// 层级显示名称映射
export const TIER_DISPLAY_NAMES: Record<CharacterImportanceTier, string> = {
  [CharacterImportanceTier.PROTAGONIST]: '主角',
  [CharacterImportanceTier.CO_PROTAGONIST]: '共同主角',
  [CharacterImportanceTier.DEUTERAGONIST]: '第二主角',
  [CharacterImportanceTier.MENTOR]: '导师',
  [CharacterImportanceTier.LOVE_INTEREST]: '恋爱对象',
  [CharacterImportanceTier.BEST_FRIEND]: '挚友/跟班',
  [CharacterImportanceTier.ARCHENEMY]: '宿敌',
  [CharacterImportanceTier.MAJOR_ALLY]: '重要盟友',
  [CharacterImportanceTier.MAJOR_ANTAGONIST]: '重要反派',
  [CharacterImportanceTier.RIVAL]: '竞争对手',
  [CharacterImportanceTier.FAMILY_MEMBER]: '家人',
  [CharacterImportanceTier.GUARDIAN]: '守护者',
  [CharacterImportanceTier.ARC_ANTAGONIST]: '篇章反派',
  [CharacterImportanceTier.ARC_ALLY]: '篇章盟友',
  [CharacterImportanceTier.RECURRING]: '常驻配角',
  [CharacterImportanceTier.CATALYST]: '催化剂角色',
  [CharacterImportanceTier.MYSTERY_FIGURE]: '神秘人物',
  [CharacterImportanceTier.MINION]: '爪牙',
  [CharacterImportanceTier.INFORMANT]: '消息提供者',
  [CharacterImportanceTier.MENTOR_FIGURE]: '指导型NPC',
  [CharacterImportanceTier.COMIC_RELIEF]: '喜剧担当',
  [CharacterImportanceTier.VICTIM]: '受害者',
  [CharacterImportanceTier.NPC]: 'NPC',
  [CharacterImportanceTier.BACKGROUND]: '背景人物',
  [CharacterImportanceTier.CAMEO]: '客串',
}

// 层级分组
export const TIER_GROUPS = {
  protagonist: {
    name: '主角层',
    tiers: [CharacterImportanceTier.PROTAGONIST, CharacterImportanceTier.CO_PROTAGONIST],
  },
  coreSupporting: {
    name: '核心配角层',
    tiers: [
      CharacterImportanceTier.DEUTERAGONIST,
      CharacterImportanceTier.MENTOR,
      CharacterImportanceTier.LOVE_INTEREST,
      CharacterImportanceTier.BEST_FRIEND,
      CharacterImportanceTier.ARCHENEMY,
    ],
  },
  majorSupporting: {
    name: '重要配角层',
    tiers: [
      CharacterImportanceTier.MAJOR_ALLY,
      CharacterImportanceTier.MAJOR_ANTAGONIST,
      CharacterImportanceTier.RIVAL,
      CharacterImportanceTier.FAMILY_MEMBER,
      CharacterImportanceTier.GUARDIAN,
    ],
  },
  arc: {
    name: '阶段性角色层',
    tiers: [
      CharacterImportanceTier.ARC_ANTAGONIST,
      CharacterImportanceTier.ARC_ALLY,
      CharacterImportanceTier.RECURRING,
      CharacterImportanceTier.CATALYST,
      CharacterImportanceTier.MYSTERY_FIGURE,
    ],
  },
  functional: {
    name: '功能性角色层',
    tiers: [
      CharacterImportanceTier.MINION,
      CharacterImportanceTier.INFORMANT,
      CharacterImportanceTier.MENTOR_FIGURE,
      CharacterImportanceTier.COMIC_RELIEF,
      CharacterImportanceTier.VICTIM,
    ],
  },
  background: {
    name: '背景层',
    tiers: [CharacterImportanceTier.NPC, CharacterImportanceTier.BACKGROUND, CharacterImportanceTier.CAMEO],
  },
}

export interface Character {
  id?: string
  name: string
  role: string
  status: 'active' | 'inactive' | 'dead' | 'paused' | 'ghost' | 'resurrected'
  description: string
  project_id?: string

  // 角色层级系统（核心分类字段）
  importance_tier?: CharacterImportanceTier
  narrative_weight?: NarrativeWeight
  story_arc_role?: StoryArcRole
  plot_priority?: number // 0-10

  // 登场控制
  debut_chapter?: number
  debut_scene?: string
  exit_chapter?: number
  exit_reason?: string
  active_arc?: string

  // 角色关系
  relationships?: string[]
  key_relationships?: Record<string, string>

  // 基础信息
  personality?: string
  personality_traits?: Array<{ name: string; value: number; description?: string }>
  appearance?: string
  background_story?: string
  age?: number
  gender?: string

  // 语言风格
  speech_pattern?: string
  lexicon?: string[]
  forbidden_words?: string[]
  voice_samples?: string[]

  // Agent 配置
  has_agent?: boolean
  agent_enabled?: boolean
  agent_goals?: string[]
  agent_memory?: string[]

  // 统计信息
  total_scenes?: number
  dialogue_count?: number
  major_events?: string[]
}

export interface CreateCharacterDTO {
  name: string
  role?: string
  status: Character['status']
  description: string
  project_id?: string

  // 角色层级系统
  importance_tier?: CharacterImportanceTier
  narrative_weight?: NarrativeWeight
  story_arc_role?: StoryArcRole
  plot_priority?: number

  // 登场控制
  debut_chapter?: number
  exit_chapter?: number
  active_arc?: string

  // 基础信息
  personality?: string
  appearance?: string
  background_story?: string
  background?: string  // 别名
  age?: number
  gender?: string

  // 语言风格
  speech_pattern?: string
  lexicon?: string[]
  forbidden_words?: string[]
  voice_samples?: string[]

  // Agent 配置
  has_agent?: boolean
  agent_enabled?: boolean
  agent_goals?: string[]
  agent_memory?: string[]
}

export interface UpdateCharacterDTO extends CreateCharacterDTO {
  id: string
}

export interface CharacterVoiceSample {
  id: string
  character_id: string
  project_id?: string
  text: string
  context?: string
  embedding?: number[]
}

export interface CharacterVoiceSampleSearchResult {
  id: string
  score: number
  payload: {
    type: 'voice_sample'
    character_id: string
    text: string
    context?: string
  }
}

export async function getCharacters(projectId?: string) {
  const params = projectId ? { project_id: projectId } : {}
  return await api.get<Character[]>('/characters', { params })
}

export async function getCharacter(id: string) {
  return await api.get<Character>(`/characters/${id}`)
}

export async function createCharacter(data: CreateCharacterDTO) {
  return await api.post<Character>('/characters', data)
}

export async function updateCharacter(id: string, data: UpdateCharacterDTO) {
  return await api.put<Character>(`/characters/${id}`, data)
}

export async function deleteCharacter(id: string) {
  return await api.delete(`/characters/${id}`)
}

export async function getCharacterMemories(characterId: string) {
  return await api.get<{ memories: any[] }>(`/characters/${characterId}/memories`)
}

export async function addCharacterMemory(
  characterId: string,
  content: string,
  memoryType: string = 'experience',
  importance: number = 0.5
) {
  return await api.post<{ success: boolean; message: string }>(
    `/characters/${characterId}/memories`,
    { content, memory_type: memoryType, importance }
  )
}

export async function getCharacterVoiceSamples(characterId: string, limit: number = 10, projectId?: string) {
  const params: Record<string, string | number> = { limit }
  if (projectId) {
    params.project_id = projectId
  }
  return await api.get<CharacterVoiceSampleSearchResult[]>(`/characters/${characterId}/voice-samples`, {
    params,
  })
}

export async function addCharacterVoiceSample(characterId: string, data: CharacterVoiceSample) {
  return await api.post<{ success: boolean; id: string; vector_id?: string | null; message: string }>(
    `/characters/${characterId}/voice-samples`,
    data,
  )
}

export async function syncCharacterVoiceSamples(characterId: string) {
  return await api.post<{ success: boolean; deleted: number; inserted: number; message: string }>(
    `/characters/${characterId}/voice-samples/sync`,
  )
}

export async function searchCharacterVoiceSamples(
  characterId: string,
  queryText: string,
  limit: number = 5,
  projectId?: string,
) {
  const params: Record<string, string | number> = {
    query_text: queryText,
    limit,
  }
  if (projectId) {
    params.project_id = projectId
  }
  return await api.post<CharacterVoiceSampleSearchResult[]>(
    `/characters/${characterId}/voice-samples/search`,
    null,
    { params },
  )
}

export interface CharacterAgentPrompt {
  has_agent: boolean
  agent_enabled?: boolean
  character_id?: string
  character_name?: string
  variables?: {
    character_background: string
    character_personality: string
    character_goals: string
  }
  prompt?: string
  prompt_length?: number
  agent_goals?: string[]
  agent_memory?: string[]
  message?: string
}

export async function getCharacterAgentPrompt(characterId: string) {
  return await api.get<CharacterAgentPrompt>(`/characters/${characterId}/agent-prompt`)
}

export interface BatchEnableAgentsResult {
  success: boolean
  message: string
  updated_count: number
  skipped_count: number
  error_count: number
  errors: string[]
}

export async function batchEnableCharacterAgents(projectId: string, roles?: string) {
  const params = new URLSearchParams()
  params.append('project_id', projectId)
  if (roles) {
    params.append('roles', roles)
  } else {
    params.append('roles', 'main,antagonist,supporting')
  }
  return await api.post<BatchEnableAgentsResult>(`/characters/batch-enable-agents?${params.toString()}`)
}

export interface GeneratePersonalityResult {
  success: boolean
  message: string
  appearance?: string
  personality?: string
  speech_pattern?: string
  agent_goals?: string[]
  agent_memory?: string[]
}

export async function generateCharacterPersonality(characterId: string) {
  return await api.post<GeneratePersonalityResult>(`/characters/${characterId}/generate-personality`)
}
