/**
 * 仪表盘页面
 * v7 美化版：渐变背景、卡片动画、数字跳动、支持明亮/黑暗主题
 * v8 更新：动态加载Agent状态，包含角色Agent
 */

import { useEffect, useState } from 'react'
import { BookOpen, Users, Globe, Sliders, Sparkles, FolderOpen, Bot, User, Lock, ToggleRight, ToggleLeft } from 'lucide-react'
import TokenStats from '@/components/TokenStats'
import { AnimatedCard, AnimatedList, AnimatedListItem, AnimatedNumber, GradientBackground } from '@/components/animations'
import { useTheme } from '@/contexts/ThemeContext'
import { useProject } from '@/contexts/ProjectContext'
import { getGlobalStats, type GlobalStats } from '@/api/config'
import { getAgentTemplates, type AgentTemplate, type AgentType } from '@/api/agentTemplates'
import { getCharacters, type Character } from '@/api/characters'

// Agent 类型中文标签
const AGENT_TYPE_LABELS: Record<string, string> = {
  character: '角色 Agent',
  setting: '设定 Agent',
  summarizer: '摘要 Agent',
  master_plotter: '总编剧 Agent',
  hook_manager: '伏笔管理 Agent',
  writer: '作家 Agent',
  evaluator: '评估 Agent',
  proc_gen: '过程生成 Agent',
  event_generator: '事件生成 Agent',
  dungeon_generator: '副本生成 Agent',
  world_map_manager: '世界地图 Agent',
}

// 核心 Agent 类型
const CORE_AGENT_TYPES: AgentType[] = [
  'setting',
  'writer',
  'master_plotter',
  'summarizer',
  'evaluator',
  'hook_manager',
  'event_generator',
  'world_map_manager',
]

interface AgentStatus {
  id: string
  name: string
  type: string
  desc: string
  status: 'ready' | 'disabled' | 'inactive'
  isOptional: boolean
  isEnabled: boolean
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
  const [characterAgents, setCharacterAgents] = useState<AgentStatus[]>([])

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
      // 获取 Agent 模板列表
      const templates = await getAgentTemplates()

      // 转换为 Agent 状态
      const systemAgents: AgentStatus[] = templates.map((t: AgentTemplate) => ({
        id: t.id,
        name: t.name,
        type: t.agent_type,
        desc: AGENT_TYPE_LABELS[t.agent_type] || t.agent_type,
        status: t.is_optional ? (t.is_enabled ? 'ready' : 'disabled') : 'ready',
        isOptional: t.is_optional,
        isEnabled: t.is_enabled,
      }))

      setAgents(systemAgents)

      // 如果有当前项目，加载角色 Agent
      if (currentProject?.id) {
        const characters = await getCharacters(currentProject.id)
        const charAgents: AgentStatus[] = characters
          .filter((c: Character) => c.has_agent)
          .map((c: Character) => ({
            id: c.id || '',
            name: `${c.name} Agent`,
            type: 'character',
            desc: c.role === 'main' ? '主角' : c.role === 'antagonist' ? '反派' : '配角',
            status: c.agent_enabled ? 'ready' : 'inactive',
            isOptional: false,
            isEnabled: c.agent_enabled || false,
            isCharacter: true,
            characterName: c.name,
          }))
        setCharacterAgents(charAgents)
      } else {
        setCharacterAgents([])
      }
    } catch (error) {
      console.error('Failed to load agent status:', error)
    }
  }

  const statCards = currentProject ? [
    { icon: <Users size={24} />, label: '角色数量', value: stats?.character_count || 0, color: 'from-blue-500 to-blue-600', glow: 'glow-primary' },
    { icon: <Globe size={24} />, label: '世界设定', value: stats?.world_count || 0, color: 'from-green-500 to-emerald-600', glow: 'glow-success' },
    { icon: <BookOpen size={24} />, label: '已生成章节', value: stats?.chapter_count || 0, color: 'from-purple-500 to-violet-600', glow: 'glow-secondary' },
    { icon: <Bot size={24} />, label: '角色 Agent', value: characterAgents.length, color: 'from-orange-500 to-red-600', glow: 'glow-secondary' },
  ] : [
    { icon: <FolderOpen size={24} />, label: '项目数量', value: stats?.project_count || 0, color: 'from-cyan-500 to-blue-600', glow: 'glow-primary' },
    { icon: <Users size={24} />, label: '角色数量', value: stats?.character_count || 0, color: 'from-blue-500 to-blue-600', glow: 'glow-primary' },
    { icon: <Globe size={24} />, label: '世界设定', value: stats?.world_count || 0, color: 'from-green-500 to-emerald-600', glow: 'glow-success' },
    { icon: <BookOpen size={24} />, label: '已生成章节', value: stats?.chapter_count || 0, color: 'from-purple-500 to-violet-600', glow: 'glow-secondary' },
  ]

  // 分离核心和可选 Agent
  const coreAgents = agents.filter(a => !a.isOptional || CORE_AGENT_TYPES.includes(a.type as AgentType))
  const optionalAgents = agents.filter(a => a.isOptional && !CORE_AGENT_TYPES.includes(a.type as AgentType))

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
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-8">
        {/* 系统 Agent */}
        <AnimatedCard delay={0.5} className={isDark ? 'glass-card' : 'bg-white shadow-md border border-gray-100'}>
          <div className="p-6">
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

        {/* 角色 Agent */}
        <AnimatedCard delay={0.6} className={isDark ? 'glass-card' : 'bg-white shadow-md border border-gray-100'}>
          <div className="p-6">
            <h2 className={`text-lg font-semibold mb-4 flex items-center gap-2 ${isDark ? 'text-white' : 'text-gray-800'}`}>
              <User className="w-5 h-5" />
              角色 Agent
              {currentProject && (
                <span className={`text-sm font-normal ${isDark ? 'text-gray-400' : 'text-gray-500'}`}>
                  ({characterAgents.length})
                </span>
              )}
            </h2>
            {!currentProject ? (
              <p className={`text-sm ${isDark ? 'text-gray-500' : 'text-gray-400'}`}>
                选择项目后查看角色 Agent 状态
              </p>
            ) : characterAgents.length === 0 ? (
              <p className={`text-sm ${isDark ? 'text-gray-500' : 'text-gray-400'}`}>
                暂无启用 Agent 的角色，在角色管理中为主角启用 Agent
              </p>
            ) : (
              <AnimatedList className="space-y-2">
                {characterAgents.map((agent, index) => (
                  <AgentStatusItem key={agent.id} agent={agent} isDark={isDark} index={index} />
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
              {!agent.isOptional && !agent.isCharacter && (
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
