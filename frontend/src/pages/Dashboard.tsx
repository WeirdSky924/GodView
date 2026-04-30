/**
 * 仪表盘页面
 * v7 美化版：渐变背景、卡片动画、数字跳动、支持明亮/黑暗主题
 * v8 更新：动态加载Agent状态，包含角色Agent
 */

import { useEffect, useState } from 'react'
import { BookOpen, Users, Globe, Sliders, Sparkles, FolderOpen, Bot, User, Lock, ToggleRight } from 'lucide-react'
import TokenStats from '@/components/TokenStats'
import { AnimatedCard, AnimatedList, AnimatedListItem, AnimatedNumber, GradientBackground } from '@/components/animations'
import { useTheme } from '@/contexts/ThemeContext'
import { useProject } from '@/contexts/ProjectContext'
import { getGlobalStats, type GlobalStats } from '@/api/config'
import { getAgentTemplates } from '@/api/agentTemplates'
import {
  CharacterImportanceTier,
  TIER_DISPLAY_NAMES,
  getCharacters,
  type Character,
} from '@/api/characters'
import { useAgentTypes } from '@/hooks/useAgentTypes'

const characterImportanceOrder: Record<string, number> = {
  [CharacterImportanceTier.PROTAGONIST]: 10,
  [CharacterImportanceTier.CO_PROTAGONIST]: 20,
  [CharacterImportanceTier.DEUTERAGONIST]: 30,
  [CharacterImportanceTier.MENTOR]: 40,
  [CharacterImportanceTier.LOVE_INTEREST]: 50,
  [CharacterImportanceTier.BEST_FRIEND]: 60,
  [CharacterImportanceTier.ARCHENEMY]: 70,
  [CharacterImportanceTier.MAJOR_ALLY]: 80,
  [CharacterImportanceTier.MAJOR_ANTAGONIST]: 90,
  [CharacterImportanceTier.RIVAL]: 100,
  [CharacterImportanceTier.FAMILY_MEMBER]: 110,
  [CharacterImportanceTier.GUARDIAN]: 120,
  [CharacterImportanceTier.ARC_ANTAGONIST]: 130,
  [CharacterImportanceTier.ARC_ALLY]: 140,
  [CharacterImportanceTier.RECURRING]: 150,
  [CharacterImportanceTier.CATALYST]: 160,
  [CharacterImportanceTier.MYSTERY_FIGURE]: 170,
  [CharacterImportanceTier.MINION]: 180,
  [CharacterImportanceTier.INFORMANT]: 190,
  [CharacterImportanceTier.MENTOR_FIGURE]: 200,
  [CharacterImportanceTier.COMIC_RELIEF]: 210,
  [CharacterImportanceTier.VICTIM]: 220,
  [CharacterImportanceTier.NPC]: 230,
  [CharacterImportanceTier.BACKGROUND]: 240,
  [CharacterImportanceTier.CAMEO]: 250,
}

function sortCharactersByImportance(items: Character[]) {
  return [...items].sort((a, b) => {
    const aTier = characterImportanceOrder[a.importance_tier || CharacterImportanceTier.NPC] ?? 999
    const bTier = characterImportanceOrder[b.importance_tier || CharacterImportanceTier.NPC] ?? 999
    if (aTier !== bTier) return aTier - bTier

    const aPriority = a.plot_priority ?? 0
    const bPriority = b.plot_priority ?? 0
    if (aPriority !== bPriority) return bPriority - aPriority

    return a.name.localeCompare(b.name, 'zh-CN')
  })
}

interface AgentStatus {
  id: string
  name: string
  type: string
  desc: string
  status: 'ready' | 'disabled' | 'inactive'
  isOptional: boolean
  isEnabled: boolean
  isCore: boolean
  isCharacter?: boolean
  characterName?: string
}

export default function Dashboard() {
  const { theme } = useTheme()
  const { currentProject } = useProject()
  const isDark = theme === 'dark'
  const [stats, setStats] = useState<GlobalStats | null>(null)
  const [loading, setLoading] = useState(true)
  const [agents, setAgents] = useState<AgentStatus[]>([])
  const [characters, setCharacters] = useState<Character[]>([])

  // 动态加载 Agent 类型元数据
  const { getLabel, isCoreType } = useAgentTypes()

  useEffect(() => {
    loadStats()
    loadAgentStatus()
  }, [currentProject])

  const loadStats = async () => {
    setLoading(true)
    try {
      const data = await getGlobalStats(currentProject?.id)
      setStats(data)
    } catch (error) {
      console.error('Failed to load stats:', error)
    } finally {
      setLoading(false)
    }
  }

  const loadAgentStatus = async () => {
    try {
      const templates = await getAgentTemplates(undefined, undefined, undefined, 100)

      const systemAgents: AgentStatus[] = templates.map((template) => ({
        id: template.id,
        name: template.name,
        type: template.agent_type,
        desc: template.description || getLabel(template.agent_type),
        status: template.is_optional ? (template.is_enabled ? 'ready' : 'disabled') : 'ready',
        isOptional: template.is_optional,
        isEnabled: template.is_enabled,
        isCore: isCoreType(template.agent_type),
      }))

      setAgents(systemAgents)

      if (currentProject?.id) {
        setCharacters(await getCharacters(currentProject.id))
      } else {
        setCharacters([])
      }
    } catch (error) {
      console.error('Failed to load agent status:', error)
      setAgents([])
      setCharacters([])
    }
  }

  const statCards = currentProject ? [
    { icon: <Users size={24} />, label: '角色数量', value: stats?.character_count || 0, color: 'from-blue-500 to-blue-600', glow: 'glow-primary' },
    { icon: <Globe size={24} />, label: '世界设定', value: stats?.world_count || 0, color: 'from-green-500 to-emerald-600', glow: 'glow-success' },
    { icon: <BookOpen size={24} />, label: '已生成章节', value: stats?.chapter_count || 0, color: 'from-purple-500 to-violet-600', glow: 'glow-secondary' },
    { icon: <Bot size={24} />, label: '系统 Agent', value: agents.length, color: 'from-orange-500 to-red-600', glow: 'glow-secondary' },
  ] : [
    { icon: <FolderOpen size={24} />, label: '项目数量', value: stats?.project_count || 0, color: 'from-cyan-500 to-blue-600', glow: 'glow-primary' },
    { icon: <Users size={24} />, label: '角色数量', value: stats?.character_count || 0, color: 'from-blue-500 to-blue-600', glow: 'glow-primary' },
    { icon: <Globe size={24} />, label: '世界设定', value: stats?.world_count || 0, color: 'from-green-500 to-emerald-600', glow: 'glow-success' },
    { icon: <BookOpen size={24} />, label: '已生成章节', value: stats?.chapter_count || 0, color: 'from-purple-500 to-violet-600', glow: 'glow-secondary' },
  ]

  const roleLabels: Record<string, string> = {
    main: '主角',
    protagonist: '主角',
    antagonist: '反派',
    supporting: '配角',
    mentor: '导师',
    ally: '盟友',
    villain: '反派',
  }
  const sortedCharacters = sortCharactersByImportance(characters)
  const coreAgents = agents.filter(a => a.isCore || (!a.isOptional))
  const optionalAgents = agents.filter(a => a.isOptional && !a.isCore)

  return (
    <div className="min-h-screen">
      {/* 顶部欢迎区域 */}
      <div className="mb-8">
        <h1 className="text-3xl font-bold gradient-text mb-2">
          {currentProject ? `${currentProject.name} - 仪表盘` : '仪表盘'}
        </h1>
        <p className={isDark ? 'text-gray-400' : 'text-gray-500'}>
          {currentProject ? '当前项目统计数据' : '全局统计数据，选择项目查看详细信息'}
        </p>
      </div>

      {/* 统计卡片 */}
      <AnimatedList className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
        {statCards.map((stat, index) => (
          <AnimatedListItem key={stat.label}>
            <AnimatedCard delay={index * 0.1} className={`overflow-hidden ${isDark ? 'glass-card' : 'bg-white shadow-md border border-gray-100'}`}>
              <div className="p-6">
                <div className="flex items-center gap-4">
                  <div className={`bg-gradient-to-br ${stat.color} text-white p-3 rounded-xl shadow-lg ${stat.glow}`}>
                    {stat.icon}
                  </div>
                  <div>
                    <p className={`text-sm ${isDark ? 'text-gray-400' : 'text-gray-500'}`}>{stat.label}</p>
                    <p className={`text-2xl font-bold ${isDark ? 'text-white' : 'text-gray-800'}`}>
                      {loading ? '...' : <AnimatedNumber value={stat.value} />}
                    </p>
                  </div>
                </div>
              </div>
              <div className={`h-1 bg-gradient-to-r ${stat.color}`} />
            </AnimatedCard>
          </AnimatedListItem>
        ))}
      </AnimatedList>

      {/* Token 统计 */}
      <AnimatedCard delay={0.4} className={`mb-8 ${isDark ? 'glass-card' : 'bg-white shadow-md border border-gray-100'}`}>
        <div className="p-6">
          <h2 className={`text-lg font-semibold mb-4 flex items-center gap-2 ${isDark ? 'text-white' : 'text-gray-800'}`}>
            <span className="text-xl">📊</span> Token 消耗统计
          </h2>
          <TokenStats />
        </div>
      </AnimatedCard>

      {/* 快速入口 */}
      <AnimatedList className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-8">
        <AnimatedListItem>
          <AnimatedCard hover className="relative overflow-hidden">
            <GradientBackground colors={['#3b82f6', '#8b5cf6']} className="absolute inset-0" />
            <div className="relative p-6 text-white">
              <div className="flex items-center gap-2 mb-2">
                <Sparkles className="w-5 h-5" />
                <h2 className="text-xl font-semibold">开始创作</h2>
              </div>
              <p className="text-blue-100 mb-4">进入上帝模式，让 AI 协助你创作小说</p>
              <a
                href="/director"
                className="inline-block bg-white/20 backdrop-blur-sm text-white px-4 py-2 rounded-lg font-medium hover:bg-white/30 transition-all border border-white/20"
              >
                进入上帝模式 →
              </a>
            </div>
          </AnimatedCard>
        </AnimatedListItem>

        <AnimatedListItem>
          <AnimatedCard hover className="relative overflow-hidden">
            <GradientBackground colors={['#8b5cf6', '#ec4899']} className="absolute inset-0" />
            <div className="relative p-6 text-white">
              <div className="flex items-center gap-2 mb-2">
                <Sliders className="w-5 h-5" />
                <h2 className="text-xl font-semibold">配置系统</h2>
              </div>
              <p className="text-purple-100 mb-4">设置 AI 模型、Embedding 服务和其他选项</p>
              <a
                href="/settings"
                className="inline-block bg-white/20 backdrop-blur-sm text-white px-4 py-2 rounded-lg font-medium hover:bg-white/30 transition-all border border-white/20"
              >
                系统设置 →
              </a>
            </div>
          </AnimatedCard>
        </AnimatedListItem>
      </AnimatedList>

      {/* Agent 状态概览 */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-8 items-stretch">
        {/* 系统 Agent */}
        <AnimatedCard delay={0.5} className={`${isDark ? 'glass-card' : 'bg-white shadow-md border border-gray-100'} h-full`}>
          <div className="p-6 h-full flex flex-col">
            <h2 className={`text-lg font-semibold mb-4 flex items-center gap-2 ${isDark ? 'text-white' : 'text-gray-800'}`}>
              <Bot className="w-5 h-5" />
              系统 Agent
            </h2>
            <AnimatedList className="space-y-2">
              {coreAgents.map((agent, index) => (
                <AgentStatusItem key={agent.id} agent={agent} isDark={isDark} index={index} />
              ))}
            </AnimatedList>

            {/* 可选 Agent */}
            {optionalAgents.length > 0 && (
              <>
                <h3 className={`text-sm font-medium mt-4 mb-2 flex items-center gap-1 ${isDark ? 'text-gray-400' : 'text-gray-500'}`}>
                  <ToggleRight className="w-4 h-4" />
                  可选 Agent
                </h3>
                <AnimatedList className="space-y-2">
                  {optionalAgents.map((agent, index) => (
                    <AgentStatusItem key={agent.id} agent={agent} isDark={isDark} index={index} />
                  ))}
                </AnimatedList>
              </>
            )}
          </div>
        </AnimatedCard>

        {/* 角色列表 */}
        <AnimatedCard delay={0.6} className={`${isDark ? 'glass-card' : 'bg-white shadow-md border border-gray-100'} h-full`}>
          <div className="p-6 h-full flex flex-col">
            <h2 className={`text-lg font-semibold mb-4 flex items-center gap-2 ${isDark ? 'text-white' : 'text-gray-800'}`}>
              <User className="w-5 h-5" />
              角色列表
              {currentProject && (
                <span className={`text-sm font-normal ${isDark ? 'text-gray-400' : 'text-gray-500'}`}>
                  ({characters.length})
                </span>
              )}
            </h2>
            {!currentProject ? (
              <div className={`text-sm flex-1 flex items-center justify-center rounded-lg border border-dashed ${isDark ? 'text-gray-500 border-gray-700 bg-gray-800/30' : 'text-gray-400 border-gray-200 bg-gray-50'}`}>
                选择项目后查看角色列表
              </div>
            ) : characters.length === 0 ? (
              <div className={`text-sm flex-1 flex items-center justify-center rounded-lg border border-dashed ${isDark ? 'text-gray-500 border-gray-700 bg-gray-800/30' : 'text-gray-400 border-gray-200 bg-gray-50'}`}>
                当前项目暂无角色
              </div>
            ) : (
              <AnimatedList className="space-y-2 flex-1 overflow-y-auto pr-1">
                {sortedCharacters.map((character, index) => (
                  <CharacterItem key={character.id || character.name} character={character} isDark={isDark} index={index} roleLabels={roleLabels} />
                ))}
              </AnimatedList>
            )}
          </div>
        </AnimatedCard>
      </div>
    </div>
  )
}

// Agent 状态项组件
function AgentStatusItem({ agent, isDark, index }: { agent: AgentStatus; isDark: boolean; index: number }) {
  const statusColors = {
    ready: isDark ? 'bg-green-500' : 'bg-green-500',
    disabled: isDark ? 'bg-gray-500' : 'bg-gray-400',
    inactive: isDark ? 'bg-yellow-500' : 'bg-yellow-500',
  }

  const statusLabels = {
    ready: '就绪',
    disabled: '已禁用',
    inactive: '未激活',
  }

  const statusBadgeColors = {
    ready: isDark
      ? 'bg-green-900/50 text-green-400 border border-green-700'
      : 'bg-green-100 text-green-600 border border-green-200',
    disabled: isDark
      ? 'bg-gray-700 text-gray-400 border border-gray-600'
      : 'bg-gray-200 text-gray-500 border border-gray-300',
    inactive: isDark
      ? 'bg-yellow-900/50 text-yellow-400 border border-yellow-700'
      : 'bg-yellow-100 text-yellow-600 border border-yellow-200',
  }

  return (
    <AnimatedListItem key={agent.id}>
      <div
        className={`flex items-center justify-between p-3 rounded-lg transition-colors border ${
          isDark
            ? 'bg-gray-800/50 hover:bg-gray-800 border-gray-700'
            : 'bg-gray-50 hover:bg-gray-100 border-gray-200'
        } ${agent.status === 'disabled' ? 'opacity-60' : ''}`}
        style={{ animationDelay: `${index * 0.03}s` }}
      >
        <div className="flex items-center gap-3">
          <span className={`w-2 h-2 rounded-full ${statusColors[agent.status]} ${agent.status === 'ready' ? 'animate-pulse' : ''}`} />
          <div>
            <div className="flex items-center gap-2">
              <p className={`font-medium text-sm ${isDark ? 'text-white' : 'text-gray-800'}`}>{agent.name}</p>
              {agent.isCore && !agent.isCharacter && (
                <span title="核心Agent">
                  <Lock className={`w-3 h-3 ${isDark ? 'text-gray-500' : 'text-gray-400'}`} />
                </span>
              )}
              {agent.isOptional && (
                <span className={`text-xs px-1.5 py-0.5 rounded ${isDark ? 'bg-purple-900/50 text-purple-400' : 'bg-purple-100 text-purple-600'}`}>
                  可选
                </span>
              )}
            </div>
            <p className={`text-xs ${isDark ? 'text-gray-500' : 'text-gray-400'}`}>{agent.desc}</p>
          </div>
        </div>
        <span className={`px-2 py-0.5 text-xs rounded-full ${statusBadgeColors[agent.status]}`}>
          {statusLabels[agent.status]}
        </span>
      </div>
    </AnimatedListItem>
  )
}

// 角色列表项组件
function CharacterItem({
  character,
  isDark,
  index,
  roleLabels,
}: {
  character: Character
  isDark: boolean
  index: number
  roleLabels: Record<string, string>
}) {
  const statusLabels: Record<string, string> = {
    active: '活跃',
    inactive: '未激活',
    dead: '死亡',
    paused: '暂停',
    ghost: '幽灵',
    resurrected: '复活',
  }

  const statusBadgeColors: Record<string, string> = {
    active: isDark
      ? 'bg-green-900/50 text-green-400 border border-green-700'
      : 'bg-green-100 text-green-600 border border-green-200',
    inactive: isDark
      ? 'bg-gray-700 text-gray-400 border border-gray-600'
      : 'bg-gray-200 text-gray-500 border border-gray-300',
    dead: isDark
      ? 'bg-red-900/50 text-red-400 border border-red-700'
      : 'bg-red-100 text-red-600 border border-red-200',
    paused: isDark
      ? 'bg-yellow-900/50 text-yellow-400 border border-yellow-700'
      : 'bg-yellow-100 text-yellow-600 border border-yellow-200',
    ghost: isDark
      ? 'bg-indigo-900/50 text-indigo-400 border border-indigo-700'
      : 'bg-indigo-100 text-indigo-600 border border-indigo-200',
    resurrected: isDark
      ? 'bg-purple-900/50 text-purple-400 border border-purple-700'
      : 'bg-purple-100 text-purple-600 border border-purple-200',
  }

  const roleLabel = character.importance_tier
    ? TIER_DISPLAY_NAMES[character.importance_tier as CharacterImportanceTier] || roleLabels[character.role] || character.role
    : roleLabels[character.role] || character.role || '角色'
  const statusLabel = statusLabels[character.status] || character.status || '未知'
  const statusClass = statusBadgeColors[character.status] || statusBadgeColors.inactive

  return (
    <AnimatedListItem key={character.id || character.name}>
      <div
        className={`flex items-center justify-between p-3 rounded-lg transition-colors border ${
          isDark
            ? 'bg-gray-800/50 hover:bg-gray-800 border-gray-700'
            : 'bg-gray-50 hover:bg-gray-100 border-gray-200'
        }`}
        style={{ animationDelay: `${index * 0.03}s` }}
      >
        <div className="flex items-center gap-3 min-w-0">
          <div className="w-8 h-8 rounded-full bg-gradient-to-br from-blue-500 to-purple-600 flex items-center justify-center text-white text-xs font-semibold flex-shrink-0">
            {character.name.slice(0, 1)}
          </div>
          <div className="min-w-0">
            <div className="flex items-center gap-2">
              <p className={`font-medium text-sm truncate ${isDark ? 'text-white' : 'text-gray-800'}`}>{character.name}</p>
              <span className={`text-xs px-1.5 py-0.5 rounded flex-shrink-0 ${isDark ? 'bg-blue-900/50 text-blue-400' : 'bg-blue-100 text-blue-600'}`}>
                {roleLabel}
              </span>
              {character.has_agent && (
                <span className={`text-xs px-1.5 py-0.5 rounded flex-shrink-0 ${isDark ? 'bg-purple-900/50 text-purple-400' : 'bg-purple-100 text-purple-600'}`}>
                  Agent
                </span>
              )}
            </div>
            {character.description && (
              <p className={`text-xs truncate ${isDark ? 'text-gray-500' : 'text-gray-400'}`}>{character.description}</p>
            )}
          </div>
        </div>
        <span className={`px-2 py-0.5 text-xs rounded-full flex-shrink-0 ${statusClass}`}>
          {statusLabel}
        </span>
      </div>
    </AnimatedListItem>
  )
}

