import { useEffect, useMemo, useState, useCallback, useRef } from 'react'
import { Card, Button, Input, TextArea, Modal } from '@/components/ui'
import PageLayout from '@/components/PageLayout'
import { useDynamicWebSocket } from '@/hooks/useWebSocket'
import { getDirectorState, getSnapshotTree } from '@/api/director'
import { getCharacters } from '@/api/characters'
import { getWorkflows, type WorkflowDefinition } from '@/api/workflows'
import { useWorkflowAgents, type AgentStatus, getAgentDisplayName } from '@/hooks/useWorkflowAgents'
import {
  Play, Pause, RotateCcw, Target, BookOpen, MessageSquare, GitBranch, Settings,
  Sparkles, FileText, Network, FolderOpen, UserPlus, UserMinus, Users, ChevronDown,
  ChevronUp, Send, X, Circle, Copy, Check, Shield, Zap, Brain
} from 'lucide-react'
import { useProject } from '@/contexts/ProjectContext'
import { useTheme } from '@/contexts/ThemeContext'
import { motion, AnimatePresence } from 'framer-motion'
import WorkflowHelp from '@/components/workflow/WorkflowHelp'
import GoldenThreeChecker from '@/components/quality/GoldenThreeChecker'
import SatisfactionAnalyzer from '@/components/quality/SatisfactionAnalyzer'
import MemoryViewer from '@/components/memory/MemoryViewer'
import OpeningDesigner from '@/components/OpeningDesigner'
import VillainManager from '@/components/VillainManager'
import VolumePlanner from '@/components/VolumePlanner'

// ==================== Types ====================

type WorkflowOrigin = 'project' | 'global_template'

interface SnapshotNode {
  id: string
  name?: string
  snapshot_type?: string
  parent_snapshot_id?: string | null
  children?: SnapshotNode[]
}

// ==================== Sub Components ====================

const LEGACY_AGENT_KEY_MAP: Record<string, string> = {
  Summarizer: 'summarizer',
  'Master Plotter': 'master_plotter',
  Plotter: 'plotter',
  'Hook Manager': 'hook_manager',
  Writer: 'writer',
  Evaluator: 'evaluator',
  'Character Agent': 'character',
  Setting: 'setting',
  'Setting Agent': 'setting',
  'Event Generator': 'event_generator',
  'Event Agent': 'event_generator',
  'World Map': 'world_map_manager',
  'Map Agent': 'world_map_manager',
  ProcGen: 'proc_gen',
  'ProcGen Agent': 'proc_gen',
  'Dungeon Generator': 'dungeon_generator',
  'Dungeon Generator Agent': 'dungeon_generator',
  'Dungeon Agent': 'dungeon_generator',
  'Plot Outline': 'plot_outline',
  'Plot Outline Agent': 'plot_outline',
  'Scene Coordinator': 'scene_coordinator',
  'Scene Coordinator Agent': 'scene_coordinator',
  '摘要 Agent': 'summarizer',
  '总编剧 Agent': 'master_plotter',
  '编剧 Agent': 'plotter',
  '伏笔 Agent': 'hook_manager',
  '作家 Agent': 'writer',
  '评估 Agent': 'evaluator',
  '角色 Agent': 'character',
  '设定 Agent': 'setting',
  '事件 Agent': 'event_generator',
  '地图 Agent': 'world_map_manager',
  '过程生成 Agent': 'proc_gen',
  '副本生成 Agent': 'dungeon_generator',
  '章节大纲 Agent': 'plot_outline',
  '场景协调 Agent': 'scene_coordinator',
}

function normalizeAgentIdentifier(value?: string): string | null {
  if (!value) return null
  return LEGACY_AGENT_KEY_MAP[value] || value
}

function resolveAgentKey(data: {
  agent?: string
  agent_type?: string
  label?: string
  node_type?: string
  node_id?: string
}): string | null {
  const normalizedAgent = normalizeAgentIdentifier(data.agent)
  const normalizedAgentType = normalizeAgentIdentifier(data.agent_type)

  if (data.node_type === 'scene_performance' && data.node_id) {
    return `scene_performance:${data.node_id}`
  }

  if (normalizedAgent === 'character' && data.label) {
    return `character:${data.label}`
  }

  if (normalizedAgentType === 'character' && data.label) {
    return `character:${data.label}`
  }

  if (normalizedAgent) {
    return normalizedAgent
  }

  if (normalizedAgentType) {
    return normalizedAgentType
  }

  if (data.node_id) {
    return data.node_id
  }

  return null
}

function getNodeDisplayName(data: {
  agent?: string
  agent_type?: string
  label?: string
  node_type?: string
  node_id?: string
}): string {
  return getAgentDisplayName({
    agent_type: normalizeAgentIdentifier(data.agent) ?? normalizeAgentIdentifier(data.agent_type) ?? undefined,
    label: data.label,
    node_type: data.node_type,
    node_id: data.node_id,
  }) || data.node_id || '未知节点'
}

function getAgentStateKey(data: {
  agent?: string
  agent_type?: string
  label?: string
  node_type?: string
  node_id?: string
}): string | null {
  const preferredKey = resolveAgentKey(data)
  if (preferredKey) {
    return preferredKey
  }

  const displayName = getAgentDisplayName({
    agent_type: normalizeAgentIdentifier(data.agent) ?? normalizeAgentIdentifier(data.agent_type) ?? undefined,
    label: data.label,
    node_type: data.node_type,
    node_id: data.node_id,
  })
  return displayName || null
}

function getWorkflowOrigin(workflow: WorkflowDefinition): WorkflowOrigin {
  return workflow.is_template && workflow.project_id === null ? 'global_template' : 'project'
}

function getWorkflowDisplayName(workflow: WorkflowDefinition): string {
  return getWorkflowOrigin(workflow) === 'global_template'
    ? `${workflow.name}（全局模板）`
    : workflow.name
}

function getSelectedWorkflow(workflows: WorkflowDefinition[], workflowId: string): WorkflowDefinition | null {
  return workflows.find(w => w.id === workflowId) || null
}

function getPreferredWorkflowId(workflows: WorkflowDefinition[], currentWorkflowId: string): string {
  if (currentWorkflowId && workflows.some(w => w.id === currentWorkflowId)) {
    return currentWorkflowId
  }

  const allBuiltinTemplate = workflows.find(w => w.id === 'template_all_builtin_workflow')
  if (allBuiltinTemplate) {
    return allBuiltinTemplate.id
  }

  const globalTemplate = workflows.find(w => getWorkflowOrigin(w) === 'global_template')
  if (globalTemplate) {
    return globalTemplate.id
  }

  return workflows[0]?.id || ''
}

// Agent 状态指示器
function AgentStatusBar({ agents, isDark }: { agents: AgentStatus[], isDark: boolean }) {
  const getStatusColor = (status: AgentStatus['status']) => {
    switch (status) {
      case 'working': return 'bg-blue-500 animate-pulse'
      case 'completed': return 'bg-green-500'
      case 'error': return 'bg-red-500'
      default: return isDark ? 'bg-gray-600' : 'bg-gray-400'
    }
  }

  return (
    <div className="flex items-center gap-1.5">
      {agents.map((agent) => (
        <div
          key={agent.id || agent.agent_type || agent.name}
          className={`w-2.5 h-2.5 rounded-full ${getStatusColor(agent.status)} transition-all cursor-pointer hover:scale-125`}
          title={`${agent.name} - ${agent.message}`}
        />
      ))}
    </div>
  )
}

// Agent 详细状态卡片 - 新设计：输出+干预一体化
function AgentStatusCard({
  agent,
  isDark,
  lastOutput,
  streamingContent,
  interventionInput,
  onInterventionChange,
  onSendIntervention,
}: {
  agent: AgentStatus
  isDark: boolean
  lastOutput?: string
  streamingContent?: string
  interventionInput: string
  onInterventionChange: (value: string) => void
  onSendIntervention: () => void
}) {
  // 优先使用 agent 自带的配置
  const config = {
    icon: agent.icon || '🤖',
    color: agent.color || 'gray',
    description: agent.description || agent.name,
  }
  const isWorking = agent.status === 'working'
  const hasOutput = streamingContent || lastOutput

  const statusStyles = {
    working: isDark ? 'border-blue-500 bg-blue-900/10' : 'border-blue-400 bg-blue-50',
    completed: isDark ? 'border-green-500 bg-green-900/10' : 'border-green-400 bg-green-50',
    error: isDark ? 'border-red-500 bg-red-900/10' : 'border-red-400 bg-red-50',
    idle: isDark ? 'border-gray-700 bg-gray-800/30' : 'border-gray-200 bg-gray-50',
  }

  return (
    <div className={`rounded-lg border-2 transition-all overflow-hidden ${statusStyles[agent.status] || statusStyles.idle}`}>
      {/* 第一行：Agent名称和状态 */}
      <div className={`flex items-center justify-between px-4 py-2 ${isDark ? 'bg-gray-800/50' : 'bg-gray-100'}`}>
        <div className="flex items-center gap-2">
          <span className={`text-xl ${isWorking ? 'animate-bounce' : ''}`}>{config.icon}</span>
          <div>
            <h4 className={`text-sm font-semibold ${isDark ? 'text-white' : 'text-gray-800'}`}>
              {agent.name}
            </h4>
            <p className={`text-xs ${isDark ? 'text-gray-500' : 'text-gray-400'}`}>
              {config.description}
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          {isWorking && (
            <span className="flex items-center gap-1.5 text-xs text-blue-500 font-medium">
              <div className="w-2 h-2 rounded-full bg-blue-500 animate-pulse" />
              工作中
            </span>
          )}
          {agent.status === 'completed' && (
            <span className="text-xs text-green-500 font-medium">✓ 完成</span>
          )}
          {agent.status === 'error' && (
            <span className="text-xs text-red-500 font-medium">✗ 错误</span>
          )}
        </div>
      </div>

      {/* 第二行：输出文本框 */}
      <div className={`min-h-[120px] max-h-[200px] overflow-y-auto p-3 ${
        isDark ? 'bg-gray-900/50' : 'bg-white'
      }`}>
        {isWorking && streamingContent ? (
          <div className="text-sm leading-relaxed whitespace-pre-wrap">
            {streamingContent}
            <span className="inline-block w-1.5 h-4 ml-0.5 bg-blue-500 animate-pulse" />
          </div>
        ) : hasOutput ? (
          <div className={`text-sm leading-relaxed whitespace-pre-wrap ${isDark ? 'text-gray-300' : 'text-gray-700'}`}>
            {streamingContent || lastOutput}
          </div>
        ) : (
          <div className={`text-sm italic ${isDark ? 'text-gray-600' : 'text-gray-400'}`}>
            等待输出...
          </div>
        )}
      </div>

      {/* 第三行：干预输入框 */}
      <div className={`flex gap-2 p-2 border-t ${isDark ? 'border-gray-700 bg-gray-800/30' : 'border-gray-200 bg-gray-50'}`}>
        <input
          type="text"
          value={interventionInput}
          onChange={(e) => onInterventionChange(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && onSendIntervention()}
          placeholder="输入干预指令..."
          className={`flex-1 px-3 py-1.5 text-sm rounded border ${
            isDark
              ? 'bg-gray-900 border-gray-700 text-white placeholder-gray-500'
              : 'bg-white border-gray-300 text-gray-800 placeholder-gray-400'
          } focus:outline-none focus:ring-1 focus:ring-blue-500`}
        />
        <button
          onClick={onSendIntervention}
          disabled={!interventionInput.trim()}
          className="px-3 py-1.5 bg-blue-600 hover:bg-blue-700 disabled:bg-gray-500 disabled:cursor-not-allowed text-white text-sm rounded transition-colors"
        >
          发送
        </button>
      </div>
    </div>
  )
}

// 集体会话卡片 - 与Agent卡片结构一致
function GroupDiscussionCard({
  discussion,
  isDark,
  input,
  onInputChange,
  onSend,
  onEnd,
}: {
  discussion: {
    topic: string
    messages: Array<{ character: string; content: string; timestamp: string }>
    characters: string[]
    participants?: Array<{ type: string; name: string; role: string }>
    isActive: boolean
  }
  isDark: boolean
  input: string
  onInputChange: (value: string) => void
  onSend: () => void
  onEnd: () => void
}) {
  const hasDiscussion = discussion.characters.length > 0 || discussion.messages.length > 0 || (discussion.participants?.length || 0) > 0
  const recentMessages = discussion.messages.slice(-10)

  // 判断消息是否来自Agent
  const isAgentMessage = (character: string) => {
    const agentNames = ['编剧', '作家', '评估', '伏笔', '设定', '地图', '事件', '摘要', '总编剧', '角色', '过程生成', '副本', '章节大纲', '场景协调']
    return agentNames.some(name => character.includes(name)) || character.startsWith('角色')
  }

  return (
    <div className={`rounded-lg border-2 overflow-hidden ${
      hasDiscussion
        ? isDark ? 'border-purple-700 bg-purple-900/10' : 'border-purple-300 bg-purple-50'
        : isDark ? 'border-gray-700 bg-gray-800/30' : 'border-gray-200 bg-gray-50'
    }`}>
      {/* 第一行：标题和状态 */}
      <div className={`flex items-center justify-between px-4 py-2 ${
        hasDiscussion
          ? isDark ? 'bg-purple-900/30' : 'bg-purple-100'
          : isDark ? 'bg-gray-800/50' : 'bg-gray-100'
      }`}>
        <div className="flex items-center gap-2">
          <span className="text-xl">💬</span>
          <div>
            <h4 className={`text-sm font-semibold ${isDark ? 'text-white' : 'text-gray-800'}`}>
              集体会话
            </h4>
            <p className={`text-xs ${hasDiscussion ? (isDark ? 'text-purple-300' : 'text-purple-600') : (isDark ? 'text-gray-500' : 'text-gray-400')}`}>
              {discussion.topic || (hasDiscussion ? '讨论进行中' : '等待工作流启动集体会话')}
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          {discussion.isActive ? (
            <span className="flex items-center gap-1.5 text-xs text-green-500 font-medium">
              <div className="w-2 h-2 rounded-full bg-green-500 animate-pulse" />
              进行中
            </span>
          ) : hasDiscussion ? (
            <span className="text-xs text-gray-500">已结束</span>
          ) : (
            <span className={`text-xs ${isDark ? 'text-gray-600' : 'text-gray-400'}`}>待激活</span>
          )}
          {/* 参与者头像 */}
          {(discussion.participants?.length || discussion.characters.length) > 0 ? (
            <div className="flex -space-x-2">
              {(discussion.participants || discussion.characters).slice(0, 5).map((p: any, i: number) => (
                <div
                  key={i}
                  className={`w-6 h-6 rounded-full flex items-center justify-center text-xs font-medium ${
                    isDark ? 'bg-purple-800 text-purple-200' : 'bg-purple-200 text-purple-700'
                  }`}
                  title={typeof p === 'string' ? p : p.name}
                >
                  {(typeof p === 'string' ? p : p.name).charAt(0)}
                </div>
              ))}
              {(discussion.participants?.length || discussion.characters.length) > 5 && (
                <div className={`w-6 h-6 rounded-full flex items-center justify-center text-xs ${
                  isDark ? 'bg-gray-700 text-gray-300' : 'bg-gray-200 text-gray-500'
                }`}>
                  +{(discussion.participants?.length || discussion.characters.length) - 5}
                </div>
              )}
            </div>
          ) : (
            <div className={`w-6 h-6 rounded-full flex items-center justify-center text-xs ${
              isDark ? 'bg-gray-700 text-gray-500' : 'bg-gray-200 text-gray-400'
            }`}>
              ?
            </div>
          )}
        </div>
      </div>

      {/* 第二行：消息输出区域 */}
      <div className={`min-h-[150px] max-h-[250px] overflow-y-auto p-3 space-y-2 ${
        isDark ? 'bg-gray-900/50' : 'bg-white'
      }`}>
        {!hasDiscussion ? (
          <div className="flex flex-col items-center justify-center h-full py-8">
            <div className={`text-4xl mb-3 ${isDark ? 'opacity-50' : 'opacity-30'}`}>💬</div>
            <p className={`text-sm ${isDark ? 'text-gray-500' : 'text-gray-400'}`}>
              工作流执行时，Agent集体讨论将在此显示
            </p>
            <p className={`text-xs mt-1 ${isDark ? 'text-gray-600' : 'text-gray-300'}`}>
              使用工作流编辑器启动创作流程
            </p>
          </div>
        ) : recentMessages.length === 0 ? (
          <div className={`text-sm italic text-center py-4 ${isDark ? 'text-gray-600' : 'text-gray-400'}`}>
            等待Agent发言...
          </div>
        ) : (
          recentMessages.map((msg, i) => (
            <div
              key={i}
              className={`p-2 rounded-lg ${
                msg.character === '你'
                  ? isDark ? 'bg-blue-900/30 border border-blue-800' : 'bg-blue-50 border border-blue-200'
                  : isAgentMessage(msg.character)
                    ? isDark ? 'bg-purple-900/20 border border-purple-800' : 'bg-purple-50 border border-purple-200'
                    : isDark ? 'bg-gray-800' : 'bg-gray-50'
              }`}
            >
              <div className="flex items-center gap-2 mb-1">
                <span className={`text-xs font-medium ${
                  msg.character === '你' ? 'text-blue-500' : isAgentMessage(msg.character) ? 'text-purple-500' : 'text-green-500'
                }`}>
                  {msg.character === '你' ? '👤 你' : isAgentMessage(msg.character) ? `🤖 ${msg.character}` : `🎭 ${msg.character}`}
                </span>
                <span className={`text-[10px] ${isDark ? 'text-gray-600' : 'text-gray-400'}`}>
                  {msg.timestamp}
                </span>
              </div>
              <p className={`text-sm ${isDark ? 'text-gray-300' : 'text-gray-700'}`}>{msg.content}</p>
            </div>
          ))
        )}
      </div>

      {/* 第三行：输入区域 */}
      <div className={`flex gap-2 p-2 border-t ${hasDiscussion ? (isDark ? 'border-purple-800 bg-purple-900/20' : 'border-purple-200 bg-purple-50') : (isDark ? 'border-gray-700 bg-gray-800/30' : 'border-gray-200 bg-gray-50')}`}>
        <input
          type="text"
          value={input}
          onChange={(e) => onInputChange(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && onSend()}
          placeholder={hasDiscussion ? "参与讨论..." : "等待集体会话开始..."}
          disabled={!discussion.isActive}
          className={`flex-1 px-3 py-1.5 text-sm rounded border ${
            isDark
              ? 'bg-gray-900 border-gray-700 text-white placeholder-gray-500'
              : 'bg-white border-gray-300 text-gray-800 placeholder-gray-400'
          } focus:outline-none focus:ring-1 focus:ring-purple-500 disabled:opacity-50`}
        />
        <button
          onClick={onSend}
          disabled={!input.trim() || !discussion.isActive}
          className="px-3 py-1.5 bg-purple-600 hover:bg-purple-700 disabled:bg-gray-500 disabled:cursor-not-allowed text-white text-sm rounded transition-colors"
        >
          发送
        </button>
        {discussion.isActive && (
          <button
            onClick={onEnd}
            className="px-3 py-1.5 bg-gray-600 hover:bg-gray-700 text-white text-sm rounded transition-colors"
          >
            结束
          </button>
        )}
      </div>
    </div>
  )
}

// 连接状态徽章
function ConnectionBadge({ status, isDark }: { status: string, isDark: boolean }) {
  const config = {
    connected: { color: 'bg-green-500', text: '已连接', icon: Circle },
    connecting: { color: 'bg-yellow-500 animate-pulse', text: '连接中', icon: Circle },
    disconnected: { color: isDark ? 'bg-gray-600' : 'bg-gray-400', text: '未连接', icon: Circle },
  }
  const { color, text } = config[status as keyof typeof config] || config.disconnected

  return (
    <div className={`flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium ${
      isDark ? 'bg-gray-800 text-gray-300' : 'bg-gray-100 text-gray-600'
    }`}>
      <div className={`w-2 h-2 rounded-full ${color}`} />
      {text}
    </div>
  )
}

// 工作状态横幅
function WorkingBanner({ agentName, isDark }: { agentName: string | null, isDark: boolean }) {
  if (!agentName) return null

  return (
    <motion.div
      initial={{ opacity: 0, height: 0 }}
      animate={{ opacity: 1, height: 'auto' }}
      exit={{ opacity: 0, height: 0 }}
      className={`flex items-center gap-2 px-4 py-2 text-sm ${
        isDark ? 'bg-blue-900/30 text-blue-300' : 'bg-blue-50 text-blue-600'
      }`}
    >
      <div className="w-2 h-2 rounded-full bg-blue-500 animate-pulse" />
      <span>{agentName} 正在工作...</span>
    </motion.div>
  )
}

// 快速操作按钮
function QuickActionButton({
  icon: Icon,
  label,
  onClick,
  disabled,
  color = 'default',
  isDark
}: {
  icon: React.ElementType
  label: string
  onClick: () => void
  disabled?: boolean
  color?: 'default' | 'primary' | 'danger'
  isDark: boolean
}) {
  const colorClasses = {
    default: isDark
      ? 'bg-gray-800 hover:bg-gray-700 text-gray-300 border-gray-700'
      : 'bg-white hover:bg-gray-50 text-gray-700 border-gray-200',
    primary: 'bg-blue-600 hover:bg-blue-700 text-white border-blue-600',
    danger: 'bg-red-600 hover:bg-red-700 text-white border-red-600',
  }

  return (
    <button
      onClick={onClick}
      disabled={disabled}
      className={`flex items-center gap-2 px-4 py-2.5 rounded-lg border text-sm font-medium transition-all disabled:opacity-50 disabled:cursor-not-allowed ${colorClasses[color]}`}
    >
      <Icon size={16} />
      {label}
    </button>
  )
}

// 章节卡片
function ChapterCard({
  chapter,
  onCopy,
  isDark
}: {
  chapter: { chapter_num: number; title: string; word_count: number; content: string }
  onCopy: () => void
  isDark: boolean
}) {
  const [copied, setCopied] = useState(false)

  const handleCopy = () => {
    navigator.clipboard.writeText(chapter.content)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
    onCopy()
  }

  return (
    <details className={`group rounded-lg border ${isDark ? 'border-gray-700' : 'border-gray-200'}`}>
      <summary className={`flex items-center justify-between p-4 cursor-pointer list-none ${
        isDark ? 'hover:bg-gray-800/50' : 'hover:bg-gray-50'
      }`}>
        <div className="flex items-center gap-3">
          <span className={`text-xs font-mono px-2 py-0.5 rounded ${
            isDark ? 'bg-gray-700 text-gray-400' : 'bg-gray-100 text-gray-500'
          }`}>
            #{chapter.chapter_num}
          </span>
          <span className={`font-medium ${isDark ? 'text-white' : 'text-gray-800'}`}>
            {chapter.title}
          </span>
          <span className={`text-xs ${isDark ? 'text-gray-500' : 'text-gray-400'}`}>
            {chapter.word_count.toLocaleString()} 字
          </span>
        </div>
        <button
          onClick={(e) => { e.stopPropagation(); handleCopy() }}
          className={`p-2 rounded-lg transition-colors ${
            isDark ? 'hover:bg-gray-700' : 'hover:bg-gray-100'
          }`}
        >
          {copied ? <Check size={16} className="text-green-500" /> : <Copy size={16} />}
        </button>
      </summary>
      <div className={`px-4 pb-4 ${isDark ? 'text-gray-300' : 'text-gray-600'}`}>
        <div className={`p-4 rounded-lg max-h-64 overflow-y-auto text-sm leading-relaxed whitespace-pre-wrap ${
          isDark ? 'bg-gray-800/50' : 'bg-gray-50'
        }`}>
          {chapter.content}
        </div>
      </div>
    </details>
  )
}

// 日志条目
function LogEntry({ log, isDark }: { log: string, isDark: boolean }) {
  const isInfo = log.includes('✅') || log.includes('📖') || log.includes('🎉')
  const isError = log.includes('❌') || log.includes('错误')
  const isWarning = log.includes('⚠️') || log.includes('警告')

  const colorClass = isError
    ? 'text-red-400'
    : isWarning
      ? 'text-yellow-400'
      : isInfo
        ? 'text-green-400'
        : isDark ? 'text-gray-300' : 'text-gray-600'

  return (
    <p className={`text-xs font-mono ${colorClass} leading-relaxed`}>
      {log}
    </p>
  )
}

// ==================== Main Component ====================

export default function Director() {
  const { currentProject } = useProject()
  const { theme } = useTheme()
  const isDark = theme === 'dark'

  // Core state
  const [sessionId, setSessionId] = useState('')
  const [isConnected, setIsConnected] = useState(false) // 是否已主动连接
  const [isGenerating, setIsGenerating] = useState(false)
  const [logs, setLogs] = useState<string[]>([])
  const [runtimeState, setRuntimeState] = useState<Record<string, any> | null>(null)
  const [snapshotTree, setSnapshotTree] = useState<SnapshotNode[]>([])

  // Workflow state
  const [savedWorkflows, setSavedWorkflows] = useState<WorkflowDefinition[]>([])
  const [selectedWorkflowId, setSelectedWorkflowId] = useState('')

  const selectedWorkflow = useMemo(
    () => getSelectedWorkflow(savedWorkflows, selectedWorkflowId),
    [savedWorkflows, selectedWorkflowId],
  )

  // 检查当前选中的工作流是否包含 group_discussion 节点
  const hasGroupDiscussionNode = useMemo(() => {
    if (!selectedWorkflow) return false
    return selectedWorkflow.nodes.some(node => node.node_type === 'group_discussion')
  }, [selectedWorkflow])

  // 使用 useWorkflowAgents hook 动态生成 Agent 列表
  const {
    agents,
    agentOutputs,
    agentStreaming,
    updateAgentStatus,
    setAgentOutput,
    setAgentOutputs,
    appendAgentStreaming,
    clearAgentStreaming,
    updateAgentStreaming,
    resetAll: resetWorkflowAgents,
  } = useWorkflowAgents(selectedWorkflowId, savedWorkflows, currentProject?.id)

  // Auto mode state
  const [autoModeRunning, setAutoModeRunning] = useState(false)
  const [autoModeChapters, setAutoModeChapters] = useState<Array<{
    chapter_num: number
    title: string
    word_count: number
    content: string
  }>>([])
  const [showAutoModeModal, setShowAutoModeModal] = useState(false)
  const [autoModeForm, setAutoModeForm] = useState({
    chapter_count: 3,
    words_per_chapter: 2000,
    style_reference: '',
  })

  // UI state
  const [showLogs, setShowLogs] = useState(true)

  // Character state
  const [availableCharacters, setAvailableCharacters] = useState<Array<{ id: string; name: string }>>([])
  const [showAddCharacterModal, setShowAddCharacterModal] = useState(false)
  const [newCharacterForm, setNewCharacterForm] = useState({
    name: '',
    description: '',
    importance_tier: 'npc' as string,
    role: '',
  })

  // 生成单章 state
  const [showWriteChapterModal, setShowWriteChapterModal] = useState(false)
  const [chapterForm, setChapterForm] = useState({
    title: '',
    goal: '',
    targetWordCount: 2000,
  })

  // Discussion state
  const [groupDiscussion, setGroupDiscussion] = useState<{
    topic: string
    messages: Array<{ character: string; content: string; timestamp: string }>
    characters: string[]
    participants?: Array<{ type: string; name: string; role: string }>
    isActive: boolean
  } | null>(null)
  const [discussionInput, setDiscussionInput] = useState('')

  // Intervention state - 每个Agent独立的干预输入
  const [agentInterventionInputs, setAgentInterventionInputs] = useState<Record<string, string>>({})
  const [interventionHistory, setInterventionHistory] = useState<Array<{
    agent: string
    message: string
    response?: string
    timestamp: string
  }>>([])

  // 设置特定Agent的干预输入
  const setAgentInput = (agentKey: string, value: string) => {
    setAgentInterventionInputs(prev => ({ ...prev, [agentKey]: value }))
  }

  // 发送干预到特定Agent
  const sendAgentIntervention = (agent: AgentStatus) => {
    const agentKey = agent.id || agent.agent_type || agent.name
    const input = agentInterventionInputs[agentKey] || ''
    if (!input.trim() || !isGenerating || wsStatus !== 'connected') return

    const timestamp = new Date().toLocaleTimeString()

    send({
      type: 'intervention',
      agent: agent.name,
      agent_type: agent.agent_type,
      message: input.trim(),
    })
    addLog(`📤 向 ${agent.name} 发送干预: ${input.trim()}`)
    setInterventionHistory(prev => [...prev, { agent: agent.name, message: input.trim(), timestamp }])
    setAgentInput(agentKey, '')
  }

  // Modals
  const [showCommandModal, setShowCommandModal] = useState(false)
  const [selectedAgent, setSelectedAgent] = useState('')
  const [agentCommand, setAgentCommand] = useState('')

  // Quality panels state
  const [activeQualityPanel, setActiveQualityPanel] = useState<string | null>(null)

  // Ref to track if we've already attempted to start the session
  const sessionStartAttempted = useRef(false)

  // Helpers
  const addLog = (message: string) => {
    const timestamp = new Date().toLocaleTimeString()
    setLogs(prev => [`[${timestamp}] ${message}`, ...prev.slice(0, 199)])
  }

  const updateAgentFromNode = (
    data: { agent?: string; agent_type?: string; label?: string; node_type?: string; node_id?: string },
    patch: Partial<AgentStatus>,
  ) => {
    if (!patch.status) return

    const agentKey = getAgentStateKey(data)
    if (agentKey) {
      updateAgentStatus(agentKey, patch.status, patch.message)
      return
    }

    const displayName = getNodeDisplayName(data)
    updateAgentStatus(displayName, patch.status, patch.message)
  }

  const getWorkingAgentName = () => agents.find(a => a.status === 'working')?.message || null

  // WebSocket - 只有点击启动后才连接
  const wsPath = useMemo(
    () => (isConnected && sessionId.trim()) ? `/api/ws/connect/${sessionId.trim()}` : '',
    [isConnected, sessionId]
  )

  const { status: wsStatus, send } = useDynamicWebSocket(wsPath, {
    onOpen: () => addLog('✅ WebSocket 已连接，正在启动会话...'),
    onClose: () => {
      addLog('WebSocket 已断开')
      setIsGenerating(false)
    },
    onError: () => {
      addLog('❌ WebSocket 连接异常')
      setIsConnected(false)
    },
    onMessage: (data) => {
      switch (data.type) {
        case 'log':
          addLog(data.message)
          break
        case 'agent_status': {
          const statusKey = getAgentStateKey({
            agent: data.agent,
            agent_type: data.agent_type,
            label: data.label,
            node_type: data.node_type,
            node_id: data.node_id,
          })

          if (statusKey) {
            updateAgentStatus(statusKey, data.status, data.message)
          }

          if (data.output) {
            const output = typeof data.output === 'string' ? data.output : JSON.stringify(data.output, null, 2)
            if (statusKey) {
              setAgentOutput(statusKey, output)
            }
          }

          if (data.status !== 'working' && statusKey) {
            clearAgentStreaming(statusKey)
          }
          break
        }
        case 'agent_streaming': {
          const streamData = data.data || data
          if (streamData.chunk) {
            const streamKey = getAgentStateKey({
              agent: streamData.agent,
              agent_type: streamData.agent_type,
              label: streamData.label,
              node_type: streamData.node_type,
              node_id: streamData.node_id,
            })

            if (streamKey) {
              appendAgentStreaming(streamKey, streamData.chunk)
            }
          }
          break
        }
        case 'agent_output': {
          const outputData = data.data || data
          if (outputData.output) {
            const outputStr = typeof outputData.output === 'string' ? outputData.output : JSON.stringify(outputData.output, null, 2)
            const outputKey = getAgentStateKey({
              agent: outputData.agent,
              agent_type: outputData.agent_type,
              label: outputData.label,
              node_type: outputData.node_type,
              node_id: outputData.node_id,
            })

            if (outputKey) {
              setAgentOutput(outputKey, outputStr)
              clearAgentStreaming(outputKey)
            }
          }
          break
        }
        case 'node_output': {
          const nodeData = data.data || data
          if (nodeData.output) {
            const outputStr = typeof nodeData.output === 'string' ? nodeData.output : JSON.stringify(nodeData.output, null, 2)
            const nodeKey = getAgentStateKey(nodeData)
            const displayName = getNodeDisplayName(nodeData)

            if (nodeKey) {
              setAgentOutput(nodeKey, outputStr)
            }

            addLog(`📤 ${displayName}: ${outputStr}`)
          }
          break
        }
        case 'node_started': {
          const nodeData = data.data || data
          const displayName = getNodeDisplayName(nodeData)
          addLog(`🔄 ${displayName} 开始执行`)
          updateAgentFromNode(nodeData, { status: 'working', message: nodeData.label || '执行中' })

          const nodeKey = getAgentStateKey(nodeData)
          if (nodeKey) {
            updateAgentStreaming(prev => ({
              ...prev,
              [nodeKey]: prev[nodeKey] || '',
            }))
          }
          break
        }
        case 'node_completed': {
          const nodeData = data.data || data
          const displayName = getNodeDisplayName(nodeData)
          const nodeKey = getAgentStateKey(nodeData)

          if (nodeData.status === 'failed' || nodeData.error) {
            addLog(`❌ ${displayName} 执行失败: ${nodeData.error || '未知错误'}`)
            updateAgentFromNode(nodeData, { status: 'error', message: nodeData.error || '执行失败' })
          } else {
            addLog(`✅ ${displayName} 完成`)
            updateAgentFromNode(nodeData, { status: 'completed', message: nodeData.label || '完成' })
          }

          if (nodeKey) {
            clearAgentStreaming(nodeKey)
          }
          break
        }
        case 'node_streaming': {
          const nodeData = data.data || data
          if (nodeData.chunk) {
            const streamKey = getAgentStateKey(nodeData)
            if (streamKey) {
              appendAgentStreaming(streamKey, nodeData.chunk)
            }
          }
          break
        }
        case 'session_started':
          addLog(`✅ 会话已启动`)
          setIsGenerating(true)
          loadRuntimePanels()
          break
        case 'session_stopped':
          addLog('会话已停止')
          setIsGenerating(false)
          setIsConnected(false)
          loadRuntimePanels()
          break
        case 'hooks_managed':
          addLog('🎯 伏笔管理完成')
          setAgentOutput('hook_manager', JSON.stringify(data.data || {}, null, 2))
          loadRuntimePanels()
          break
        case 'group_discussion_started':
          addLog(`🌟 集体讨论开始`)
          // 处理从工作流引擎发送的讨论消息
          const discussionMessages = data.data?.messages || []
          const formattedMessages = discussionMessages.map((msg: any) => ({
            character: msg.agent || msg.character || 'Agent',
            content: msg.content || '',
            timestamp: new Date().toLocaleTimeString(),
          }))
          setGroupDiscussion({
            topic: data.data?.discussion_topic || '讨论',
            messages: formattedMessages,
            characters: data.data?.characters || [],
            participants: data.data?.participants || [],
            isActive: true,
          })
          break
        case 'discussion_message':
          const speakerName = data.data?.agent || data.data?.character || '未知'
          const messageContent = data.data?.content || ''
          const isLLMGenerated = data.data?.is_llm_generated
          // 添加日志
          addLog(`💬 ${speakerName}: ${messageContent}${isLLMGenerated ? ' 🤖' : ''}`)
          // 更新讨论状态
          setGroupDiscussion(prev => {
            if (prev) {
              return {
                ...prev,
                messages: [...prev.messages, {
                  character: speakerName,
                  content: messageContent,
                  timestamp: new Date().toLocaleTimeString(),
                  isLLMGenerated,
                }],
              }
            } else {
              // 如果讨论还未初始化，创建一个新的讨论状态
              return {
                topic: '创作讨论会',
                messages: [{
                  character: speakerName,
                  content: messageContent,
                  timestamp: new Date().toLocaleTimeString(),
                  isLLMGenerated,
                }],
                characters: [],
                participants: [],
                isActive: true,
              }
            }
          })
          break
        case 'discussion_ended':
          addLog('📝 集体讨论结束')
          if (groupDiscussion) {
            setGroupDiscussion(prev => prev ? { ...prev, isActive: false } : null)
          }
          break
        case 'auto_mode_chapter_start':
          addLog(`📖 开始写作第 ${data.chapter_num} 章: ${data.title}`)
          break
        case 'auto_mode_chapter_completed':
          addLog(`✅ 第 ${data.chapter_num} 章完成: ${data.title} (${data.word_count} 字)`)
          setAutoModeChapters(prev => [...prev, {
            chapter_num: data.chapter_num,
            title: data.title,
            word_count: data.word_count,
            content: data.content,
          }])
          break
        case 'auto_mode_completed':
          setAutoModeRunning(false)
          addLog(`🎉 连续创作完成！共 ${data.data?.total_chapters} 章，${data.data?.total_words} 字`)
          loadRuntimePanels()
          break
        case 'auto_mode_error':
          setAutoModeRunning(false)
          addLog(`❌ 错误: ${data.error}`)
          break
        case 'auto_write_chapter_result':
          if (data.status === 'success') {
            addLog(`✅ 章节生成完成: ${data.data?.title} (${data.data?.word_count} 字)`)
            setAutoModeChapters(prev => [...prev, {
              chapter_num: data.data?.chapter_num || prev.length + 1,
              title: data.data?.title || '',
              word_count: data.data?.word_count || 0,
              content: data.data?.content || '',
            }])
            loadRuntimePanels()
          } else {
            addLog(`❌ 章节生成失败: ${data.error}`)
          }
          break
        case 'character_added':
          addLog(`👤 角色已添加: ${data.data?.name}`)
          if (currentProject) loadCharacters()
          break
        case 'character_removed':
          addLog(`👤 角色已移除`)
          if (currentProject) loadCharacters()
          break
        case 'agent_response':
          // Agent 干预响应
          addLog(`💬 ${data.agent}: ${data.response || '已响应'}`)
          setInterventionHistory(prev => prev.map(item =>
            item.agent === data.agent && !item.response
              ? { ...item, response: data.response }
              : item
          ))
          if (data.agent) {
            const responseKey = getAgentStateKey({ agent: data.agent, agent_type: data.agent_type, label: data.label })
            if (responseKey) {
              setAgentOutput(responseKey, data.response || '')
            }
          }
          break
        case 'intervention_response':
          // 干预响应
          addLog(`💬 ${data.agent}: ${data.response || '已响应'}`)
          setInterventionHistory(prev => prev.map(item =>
            item.agent === data.agent && !item.response
              ? { ...item, response: data.response }
              : item
          ))
          if (data.agent) {
            const responseKey = getAgentStateKey({ agent: data.agent, agent_type: data.agent_type, label: data.label })
            if (responseKey) {
              setAgentOutput(responseKey, data.response || '')
            }
          }
          break
        case 'intervention_queued':
          // 干预已加入工作流队列
          addLog(`📤 干预已排队，等待 ${data.agent} 执行`)
          break
        case 'intervention_applied':
          // 干预已应用到Agent
          addLog(`✅ 干预已应用到 ${data.agent} (${data.intervention_count} 条)`)
          break
        case 'intervention_logged':
          addLog(`📝 干预已记录`)
          break
        case 'error':
          addLog(`❌ ${data.message}`)
          break
        default:
          if (data.type !== 'heartbeat') {
            addLog(`${data.type}: ${JSON.stringify(data.data || {})}`)
          }
      }
    },
  })

  // Data loading
  const loadRuntimePanels = async () => {
    if (!sessionId.trim()) return
    try {
      const stateRes = await getDirectorState(sessionId.trim())
      setRuntimeState(stateRes.data)
      if (stateRes.data?.world_id) {
        const treeRes = await getSnapshotTree(stateRes.data.world_id)
        setSnapshotTree(treeRes.data || [])
      }
    } catch (error) {
      console.error('Failed to load runtime panels:', error)
    }
  }

  const loadCharacters = async () => {
    if (!currentProject) return setAvailableCharacters([])
    try {
      const chars = await getCharacters(currentProject.id)
      setAvailableCharacters(chars.map((c: any) => ({ id: c.id, name: c.name })))
    } catch (error) {
      console.error('Failed to load characters:', error)
    }
  }

  const loadWorkflows = useCallback(async () => {
    if (!currentProject) return setSavedWorkflows([])
    try {
      const workflows = await getWorkflows(currentProject.id, true)
      setSavedWorkflows(workflows)
      setSelectedWorkflowId((currentId) => getPreferredWorkflowId(workflows, currentId))
    } catch (error) {
      console.error('Failed to load workflows:', error)
    }
  }, [currentProject])

  useEffect(() => { loadCharacters() }, [currentProject])
  useEffect(() => { loadWorkflows() }, [loadWorkflows])
  useEffect(() => { if (sessionId.trim()) loadRuntimePanels() }, [sessionId])

  // 当 WebSocket 连接成功后，发送 start_session
  useEffect(() => {
    if (wsStatus === 'connected' && isConnected && !sessionStartAttempted.current && currentProject) {
      sessionStartAttempted.current = true
      const worldId = currentProject.world_id || `project-${currentProject.id}`
      send({
        type: 'start_session',
        world_id: worldId,
        project_id: currentProject.id,  // 传递 project_id
        character_ids: availableCharacters.map(c => c.id)
      })
      setIsGenerating(true)
    }
    // Note: send and availableCharacters are intentionally omitted to prevent re-triggering
    // sessionStartAttempted ref prevents multiple calls
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [wsStatus, isConnected, currentProject])

  // Actions
  const startSession = () => {
    if (!sessionId.trim()) return addLog('请输入会话 ID')
    if (!currentProject) return addLog('请先选择项目')
    // 重置标志并设置连接状态，触发 WebSocket 连接
    sessionStartAttempted.current = false
    setIsConnected(true)
  }

  const stopSession = () => {
    send({ type: 'stop_session' }) // 先发送停止消息
    setIsGenerating(false)
    setIsConnected(false) // 然后断开 WebSocket
    sessionStartAttempted.current = false // 重置以便下次启动
  }

  const resetAll = () => {
    resetWorkflowAgents()
    setLogs([])
    setRuntimeState(null)
    setSnapshotTree([])
    setAutoModeChapters([])
    setIsConnected(false)
    setIsGenerating(false)
    sessionStartAttempted.current = false
  }

  const handleStartAutoMode = () => {
    if (!selectedWorkflowId) return addLog('请先选择工作流')
    setAutoModeRunning(true)
    setAutoModeChapters([])
    send({
      type: 'start_auto_mode',
      workflow_id: selectedWorkflowId,
      chapter_count: autoModeForm.chapter_count,
      words_per_chapter: autoModeForm.words_per_chapter,
      style_reference: autoModeForm.style_reference,
    })
    setShowAutoModeModal(false)
  }

  const handleStopAutoMode = () => {
    send({ type: 'stop_auto_mode' })
    setAutoModeRunning(false)
  }

  const sendDiscussionMessage = () => {
    if (!discussionInput.trim() || !groupDiscussion) return
    send({ type: 'discussion_message', message: discussionInput.trim() })
    setGroupDiscussion(prev => prev ? {
      ...prev,
      messages: [...prev.messages, { character: '你', content: discussionInput.trim(), timestamp: new Date().toLocaleTimeString() }],
    } : null)
    setDiscussionInput('')
  }

  const endDiscussion = () => {
    send({ type: 'end_discussion' })
    setGroupDiscussion(prev => prev ? { ...prev, isActive: false } : null)
  }

  const handleAddCharacter = () => {
    if (!newCharacterForm.name.trim()) return addLog('请输入角色名称')
    if (!currentProject) return addLog('请先选择项目')
    send({
      type: 'add_character',
      character_data: { ...newCharacterForm, project_id: currentProject.id },
    })
    setNewCharacterForm({ name: '', description: '', importance_tier: 'npc', role: '' })
    setShowAddCharacterModal(false)
  }

  const handleRemoveCharacter = (characterId: string) => {
    if (!confirm('确定移除该角色？')) return
    send({ type: 'remove_character', character_id: characterId })
  }

  const handleWriteChapter = () => {
    if (!chapterForm.title.trim() || !chapterForm.goal.trim() || !selectedWorkflowId) return
    send({
      type: 'auto_write_chapter',
      workflow_id: selectedWorkflowId,
      chapter_title: chapterForm.title.trim(),
      chapter_goal: chapterForm.goal.trim(),
      target_word_count: chapterForm.targetWordCount,
    })
    addLog(`📝 开始生成章节: ${chapterForm.title}`)
    setChapterForm({ title: '', goal: '', targetWordCount: 2000 })
    setShowWriteChapterModal(false)
  }

  // Header actions
  const headerActions = (
    <div className="flex items-center gap-4">
      <AgentStatusBar agents={agents} isDark={isDark} />
      <ConnectionBadge status={wsStatus} isDark={isDark} />
      <WorkflowHelp />
    </div>
  )

  if (!currentProject) {
    return (
      <PageLayout title="上帝模式">
        <div className={`flex flex-col items-center justify-center h-[60vh] ${isDark ? 'text-gray-500' : 'text-gray-400'}`}>
          <FolderOpen size={48} className="mb-4 opacity-50" />
          <p className="text-lg">请先在侧边栏选择一个项目</p>
        </div>
      </PageLayout>
    )
  }

  return (
    <PageLayout
      title="上帝模式"
      description={currentProject.name}
      actions={headerActions}
    >
      <div className="space-y-4">
        {/* ========== 顶部控制栏 ========== */}
        <div className={`rounded-xl border overflow-hidden ${isDark ? 'border-gray-800' : 'border-gray-200'}`}>
          <div className={`grid grid-cols-1 lg:grid-cols-2 divide-y lg:divide-y-0 lg:divide-x ${
            isDark ? 'divide-gray-800 bg-gray-900/50' : 'divide-gray-200 bg-white'
          }`}>
            {/* 会话控制 */}
            <div className="p-4">
              <div className="flex items-center gap-3">
                <div className={`flex items-center gap-2 px-3 py-1.5 rounded-lg ${
                  isDark ? 'bg-gray-800' : 'bg-gray-100'
                }`}>
                  <span className={`text-xs font-medium uppercase tracking-wide ${
                    isDark ? 'text-gray-500' : 'text-gray-400'
                  }`}>会话</span>
                </div>
                <div className="flex-1 flex items-center gap-2">
                  <input
                    type="text"
                    placeholder="输入会话 ID..."
                    value={sessionId}
                    onChange={(e) => setSessionId(e.target.value)}
                    disabled={isConnected}
                    className={`flex-1 max-w-xs px-4 py-2 rounded-lg border text-sm transition-colors disabled:opacity-50 ${
                      isDark
                        ? 'bg-gray-800 border-gray-700 text-white placeholder-gray-500 focus:border-blue-500'
                        : 'bg-white border-gray-200 text-gray-800 placeholder-gray-400 focus:border-blue-500'
                    }`}
                  />
                  {!isConnected ? (
                    <button
                      onClick={startSession}
                      disabled={!currentProject || !sessionId.trim()}
                      className="flex items-center gap-2 px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white text-sm font-medium rounded-lg transition-colors disabled:opacity-50"
                    >
                      <Play size={16} /> 启动
                    </button>
                  ) : (
                    <button
                      onClick={stopSession}
                      className="flex items-center gap-2 px-4 py-2 bg-red-600 hover:bg-red-700 text-white text-sm font-medium rounded-lg transition-colors"
                    >
                      <Pause size={16} /> 停止
                    </button>
                  )}
                  <button
                    onClick={resetAll}
                    className={`p-2 rounded-lg transition-colors ${
                      isDark ? 'hover:bg-gray-800 text-gray-400' : 'hover:bg-gray-100 text-gray-500'
                    }`}
                    title="重置"
                  >
                    <RotateCcw size={18} />
                  </button>
                </div>
              </div>
              {/* 运行时状态 */}
              {runtimeState && (
                <div className={`flex items-center gap-6 mt-3 text-sm ${
                  isDark ? 'text-gray-400' : 'text-gray-500'
                }`}>
                  <span>阶段: <strong className={isDark ? 'text-white' : 'text-gray-800'}>{runtimeState?.state_machine?.phase || '-'}</strong></span>
                  <span>进度: <strong className={isDark ? 'text-white' : 'text-gray-800'}>{
                    typeof runtimeState?.main_plot_progress === 'number'
                      ? `${Math.round(runtimeState.main_plot_progress * 100)}%`
                      : '-'
                  }</strong></span>
                  <span>伏笔: <strong className={isDark ? 'text-white' : 'text-gray-800'}>{runtimeState?.hooks_planted?.length || 0}</strong></span>
                </div>
              )}
            </div>

            {/* 工作流控制 */}
            <div className="p-4">
              <div className="flex items-center gap-3">
                <div className={`flex items-center gap-2 px-3 py-1.5 rounded-lg ${
                  isDark ? 'bg-gray-800' : 'bg-gray-100'
                }`}>
                  <Network size={14} className={isDark ? 'text-blue-400' : 'text-blue-600'} />
                  <span className={`text-xs font-medium uppercase tracking-wide ${
                    isDark ? 'text-gray-500' : 'text-gray-400'
                  }`}>工作流</span>
                </div>
                <div className="flex-1 flex items-center gap-2 flex-wrap">
                  <select
                    value={selectedWorkflowId}
                    onChange={(e) => setSelectedWorkflowId(e.target.value)}
                    className={`flex-1 max-w-[260px] px-4 py-2 rounded-lg border text-sm ${
                      isDark
                        ? 'bg-gray-800 border-gray-700 text-white'
                        : 'bg-white border-gray-200 text-gray-800'
                    }`}
                  >
                    <option value="">选择工作流...</option>
                    {savedWorkflows.map(wf => (
                      <option key={wf.id} value={wf.id}>
                        {getWorkflowOrigin(wf) === 'global_template' ? '[模板] ' : ''}
                        {wf.name} ({wf.nodes.length} 节点)
                      </option>
                    ))}
                  </select>
                  <button
                    onClick={() => setShowWriteChapterModal(true)}
                    disabled={!selectedWorkflowId || !isGenerating || wsStatus !== 'connected' || autoModeRunning}
                    className="flex items-center gap-2 px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white text-sm font-medium rounded-lg transition-colors disabled:opacity-50"
                    title={!selectedWorkflowId ? '请先选择工作流' : ''}
                  >
                    <FileText size={16} /> 生成单章
                  </button>
                  <button
                    onClick={() => setShowAutoModeModal(true)}
                    disabled={!selectedWorkflowId || !isGenerating || wsStatus !== 'connected'}
                    className="flex items-center gap-2 px-4 py-2 bg-purple-600 hover:bg-purple-700 text-white text-sm font-medium rounded-lg transition-colors disabled:opacity-50"
                    title={!selectedWorkflowId ? '请先选择工作流' : ''}
                  >
                    <Sparkles size={16} /> 连续创作
                  </button>
                </div>
              </div>
              {savedWorkflows.length === 0 ? (
                <p className={`mt-3 text-xs ${isDark ? 'text-gray-600' : 'text-gray-400'}`}>
                  💡 请先在「可视化工作台」创建工作流
                </p>
              ) : selectedWorkflow ? (
                <div className={`mt-3 flex items-center gap-2 text-xs ${isDark ? 'text-gray-400' : 'text-gray-500'}`}>
                  {getWorkflowOrigin(selectedWorkflow) === 'global_template' && (
                    <span className={`px-2 py-1 rounded-full border ${
                      isDark
                        ? 'border-blue-800 bg-blue-900/30 text-blue-300'
                        : 'border-blue-200 bg-blue-50 text-blue-700'
                    }`}>
                      全局模板
                    </span>
                  )}
                  <span>
                    当前将执行：
                    <strong className={isDark ? 'text-white' : 'text-gray-800'}>
                      {' '}
                      {getWorkflowDisplayName(selectedWorkflow)}
                    </strong>
                  </span>
                </div>
              ) : null}
            </div>
          </div>

          {/* 工作状态横幅 */}
          <AnimatePresence>
            {isGenerating && getWorkingAgentName() && (
              <WorkingBanner agentName={getWorkingAgentName()} isDark={isDark} />
            )}
          </AnimatePresence>
        </div>

        {/* ========== 连续创作进度 ========== */}
        {autoModeRunning && (
          <Card className={`border-2 ${isDark ? 'border-purple-800 bg-purple-900/20' : 'border-purple-300 bg-purple-50'}`}>
            <div className="p-4 flex items-center justify-between">
              <div className="flex items-center gap-3">
                <div className={`p-2 rounded-lg ${isDark ? 'bg-purple-800' : 'bg-purple-100'}`}>
                  <Sparkles size={20} className="text-purple-500" />
                </div>
                <div>
                  <h3 className={`font-semibold ${isDark ? 'text-white' : 'text-gray-800'}`}>连续创作进行中</h3>
                  <p className={`text-sm ${isDark ? 'text-purple-300' : 'text-purple-600'}`}>
                    已完成 {autoModeChapters.length} 章
                  </p>
                </div>
              </div>
              <button
                onClick={handleStopAutoMode}
                className="flex items-center gap-2 px-4 py-2 bg-red-600 hover:bg-red-700 text-white text-sm font-medium rounded-lg"
              >
                <Pause size={16} /> 停止
              </button>
            </div>
          </Card>
        )}

        {/* ========== 主内容区：Agent状态为核心 ========== */}
        <div className="grid grid-cols-1 xl:grid-cols-4 gap-4">
          {/* 左侧：Agent状态面板（大） */}
          <div className="xl:col-span-3 space-y-4">
            {/* 集体会话卡片 - 仅当工作流包含 group_discussion 节点时显示 */}
            {hasGroupDiscussionNode && (
              <GroupDiscussionCard
                discussion={groupDiscussion || { topic: '', messages: [], characters: [], isActive: false }}
                isDark={isDark}
                input={discussionInput}
                onInputChange={setDiscussionInput}
                onSend={sendDiscussionMessage}
                onEnd={endDiscussion}
              />
            )}

            {/* Agent 卡片网格 */}
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-2 gap-4">
              {agents.map(agent => (
                <AgentStatusCard
                  key={agent.id || agent.agent_type || agent.name}
                  agent={agent}
                  isDark={isDark}
                  lastOutput={agentOutputs[agent.id || agent.agent_type || agent.name]}
                  streamingContent={agentStreaming[agent.id || agent.agent_type || agent.name]}
                  interventionInput={agentInterventionInputs[agent.id || agent.agent_type || agent.name] || ''}
                  onInterventionChange={(value) => setAgentInput(agent.id || agent.agent_type || agent.name, value)}
                  onSendIntervention={() => sendAgentIntervention(agent)}
                />
              ))}
            </div>

            {/* 已生成章节 */}
            {autoModeChapters.length > 0 && (
              <Card>
                <div className="p-4">
                  <h3 className={`text-sm font-semibold mb-3 ${isDark ? 'text-gray-300' : 'text-gray-700'}`}>
                    已生成章节 ({autoModeChapters.length} 章)
                  </h3>
                  <div className="space-y-2 max-h-[300px] overflow-y-auto">
                    {autoModeChapters.map((chapter, i) => (
                      <ChapterCard
                        key={i}
                        chapter={chapter}
                        onCopy={() => addLog(`已复制: ${chapter.title}`)}
                        isDark={isDark}
                      />
                    ))}
                  </div>
                </div>
              </Card>
            )}
          </div>

          {/* 右侧：操作区 */}
          <div className="space-y-4">
            {/* Agent 状态总览 */}
            <Card>
              <div className="p-4">
                <h3 className={`text-sm font-semibold mb-3 ${isDark ? 'text-gray-300' : 'text-gray-700'}`}>
                  状态总览
                </h3>
                <AgentStatusBar agents={agents} isDark={isDark} />
                <p className={`text-xs mt-2 ${isDark ? 'text-gray-500' : 'text-gray-400'}`}>
                  {agents.filter(a => a.status === 'working').length} / {agents.length} 工作中
                </p>
              </div>
            </Card>

            {/* 快速操作 */}
            <Card>
              <div className="p-4">
                <h3 className={`text-sm font-semibold mb-3 ${isDark ? 'text-gray-300' : 'text-gray-700'}`}>
                  快速操作
                </h3>
                <div className="grid grid-cols-2 gap-2">
                  <QuickActionButton
                    icon={Target}
                    label="管理伏笔"
                    onClick={() => send({ type: 'manage_hooks' })}
                    disabled={!isGenerating || wsStatus !== 'connected' || autoModeRunning}
                    isDark={isDark}
                  />
                  <QuickActionButton
                    icon={BookOpen}
                    label="章节判定"
                    onClick={() => send({ type: 'chapter_end_check' })}
                    disabled={!isGenerating || wsStatus !== 'connected' || autoModeRunning}
                    isDark={isDark}
                  />
                  <QuickActionButton
                    icon={GitBranch}
                    label="创建快照"
                    onClick={() => send({ type: 'create_snapshot', snapshot_type: 'manual', is_branch: true })}
                    disabled={!isGenerating || wsStatus !== 'connected'}
                    isDark={isDark}
                  />
                </div>
              </div>
            </Card>

            {/* 质量检测入口 */}
            <Card>
              <div className="p-4">
                <h3 className={`text-sm font-semibold mb-3 ${isDark ? 'text-gray-300' : 'text-gray-700'}`}>
                  质量检测
                </h3>
                <div className="grid grid-cols-2 gap-2">
                  <button
                    onClick={() => setActiveQualityPanel('goldenThree')}
                    className={`flex items-center gap-2 px-3 py-2 rounded-lg border text-sm transition-colors ${
                      isDark
                        ? 'bg-gray-800 hover:bg-gray-700 text-gray-300 border-gray-700'
                        : 'bg-white hover:bg-gray-50 text-gray-700 border-gray-200'
                    }`}
                  >
                    <Shield size={14} className="text-yellow-500" />
                    黄金三章
                  </button>
                  <button
                    onClick={() => setActiveQualityPanel('satisfaction')}
                    className={`flex items-center gap-2 px-3 py-2 rounded-lg border text-sm transition-colors ${
                      isDark
                        ? 'bg-gray-800 hover:bg-gray-700 text-gray-300 border-gray-700'
                        : 'bg-white hover:bg-gray-50 text-gray-700 border-gray-200'
                    }`}
                  >
                    <Zap size={14} className="text-purple-500" />
                    爽点分析
                  </button>
                  <button
                    onClick={() => setActiveQualityPanel('memory')}
                    className={`flex items-center gap-2 px-3 py-2 rounded-lg border text-sm transition-colors ${
                      isDark
                        ? 'bg-gray-800 hover:bg-gray-700 text-gray-300 border-gray-700'
                        : 'bg-white hover:bg-gray-50 text-gray-700 border-gray-200'
                    }`}
                  >
                    <Brain size={14} className="text-blue-500" />
                    记忆系统
                  </button>
                  <button
                    onClick={() => setActiveQualityPanel('opening')}
                    className={`flex items-center gap-2 px-3 py-2 rounded-lg border text-sm transition-colors ${
                      isDark
                        ? 'bg-gray-800 hover:bg-gray-700 text-gray-300 border-gray-700'
                        : 'bg-white hover:bg-gray-50 text-gray-700 border-gray-200'
                    }`}
                  >
                    <Sparkles size={14} className="text-green-500" />
                    开局设计
                  </button>
                  <button
                    onClick={() => setActiveQualityPanel('villain')}
                    className={`flex items-center gap-2 px-3 py-2 rounded-lg border text-sm transition-colors ${
                      isDark
                        ? 'bg-gray-800 hover:bg-gray-700 text-gray-300 border-gray-700'
                        : 'bg-white hover:bg-gray-50 text-gray-700 border-gray-200'
                    }`}
                  >
                    <Users size={14} className="text-red-500" />
                    反派管理
                  </button>
                  <button
                    onClick={() => setActiveQualityPanel('volume')}
                    className={`flex items-center gap-2 px-3 py-2 rounded-lg border text-sm transition-colors ${
                      isDark
                        ? 'bg-gray-800 hover:bg-gray-700 text-gray-300 border-gray-700'
                        : 'bg-white hover:bg-gray-50 text-gray-700 border-gray-200'
                    }`}
                  >
                    <BookOpen size={14} className="text-indigo-500" />
                    卷规划
                  </button>
                </div>
              </div>
            </Card>

            {/* 实时日志 */}
            <Card>
              <button
                onClick={() => setShowLogs(!showLogs)}
                className={`w-full flex items-center justify-between p-4 ${isDark ? 'hover:bg-gray-800/50' : 'hover:bg-gray-50'}`}
              >
                <span className={`text-sm font-semibold ${isDark ? 'text-gray-300' : 'text-gray-700'}`}>
                  实时日志
                </span>
                <span className={`text-xs px-2 py-0.5 rounded ${isDark ? 'bg-gray-800 text-gray-500' : 'bg-gray-100 text-gray-500'}`}>
                  {logs.length} 条
                </span>
              </button>
              <AnimatePresence>
                {showLogs && (
                  <motion.div
                    initial={{ height: 0, opacity: 0 }}
                    animate={{ height: 'auto', opacity: 1 }}
                    exit={{ height: 0, opacity: 0 }}
                    className="overflow-hidden"
                  >
                    <div className="px-4 pb-4">
                      <div className={`h-48 overflow-y-auto p-3 rounded-lg space-y-1 ${
                        isDark ? 'bg-gray-900' : 'bg-gray-900'
                      }`}>
                        {logs.length === 0 ? (
                          <p className="text-gray-500 text-xs font-mono">暂无日志...</p>
                        ) : (
                          logs.map((log, i) => <LogEntry key={i} log={log} isDark={isDark} />)
                        )}
                      </div>
                    </div>
                  </motion.div>
                )}
              </AnimatePresence>
            </Card>

            {/* 快照版本 */}
            <Card>
              <div className="p-4">
                <h3 className={`text-sm font-semibold mb-3 ${isDark ? 'text-gray-300' : 'text-gray-700'}`}>
                  快照版本
                </h3>
                {snapshotTree.length > 0 ? (
                  <div className="space-y-2 max-h-32 overflow-y-auto">
                    {snapshotTree.map(node => (
                      <div
                        key={node.id}
                        className={`p-2 rounded-lg flex items-center justify-between ${
                          isDark ? 'bg-gray-800' : 'bg-gray-50'
                        }`}
                      >
                        <span className="text-xs truncate">{node.name || node.id}</span>
                        <button
                          onClick={() => send({ type: 'rollback_snapshot', snapshot_id: node.id })}
                          disabled={!isGenerating || wsStatus !== 'connected'}
                          className="text-xs text-blue-500 hover:text-blue-600 disabled:opacity-50"
                        >
                          回档
                        </button>
                      </div>
                    ))}
                  </div>
                ) : (
                  <p className={`text-sm text-center py-4 ${isDark ? 'text-gray-600' : 'text-gray-400'}`}>
                    暂无快照
                  </p>
                )}
              </div>
            </Card>
          </div>
        </div>
      </div>

      {/* ========== Quality Panels ========== */}
      <Modal
        isOpen={activeQualityPanel !== null}
        onClose={() => setActiveQualityPanel(null)}
        title={
          activeQualityPanel === 'goldenThree' ? '黄金三章检测' :
          activeQualityPanel === 'satisfaction' ? '爽点分析' :
          activeQualityPanel === 'memory' ? '记忆系统' :
          activeQualityPanel === 'opening' ? '开局设计向导' :
          activeQualityPanel === 'villain' ? '反派与冲突管理' :
          activeQualityPanel === 'volume' ? '卷规划编辑器' : ''
        }
        size="lg"
      >
        <div className="max-h-[70vh] overflow-y-auto">
          {activeQualityPanel === 'goldenThree' && currentProject && (
            <GoldenThreeChecker
              projectId={currentProject.id}
              onCheckComplete={(result) => addLog(`黄金三章检测完成: ${result.total_score}分`)}
            />
          )}
          {activeQualityPanel === 'satisfaction' && currentProject && (
            <SatisfactionAnalyzer
              projectId={currentProject.id}
              onAnalyzeComplete={(result) => addLog(`爽点分析完成: ${result.satisfaction_score}分`)}
            />
          )}
          {activeQualityPanel === 'memory' && currentProject && (
            <MemoryViewer projectId={currentProject.id} />
          )}
          {activeQualityPanel === 'opening' && currentProject && (
            <OpeningDesigner
              projectId={currentProject.id}
              onDesignComplete={(result) => addLog(`开局设计完成: ${result.golden_finger.name}`)}
            />
          )}
          {activeQualityPanel === 'villain' && currentProject && (
            <VillainManager projectId={currentProject.id} />
          )}
          {activeQualityPanel === 'volume' && currentProject && (
            <VolumePlanner projectId={currentProject.id} />
          )}
        </div>
      </Modal>

      {/* ========== Modals ========== */}
      <Modal isOpen={showCommandModal} onClose={() => setShowCommandModal(false)} title="手动 Agent 指令">
        <div className="space-y-4">
          <div>
            <label className={`block text-sm font-medium mb-2 ${isDark ? 'text-gray-300' : 'text-gray-700'}`}>
              选择 Agent
            </label>
            <select
              value={selectedAgent}
              onChange={(e) => setSelectedAgent(e.target.value)}
              className={`w-full px-3 py-2 rounded-lg border ${
                isDark ? 'bg-gray-800 border-gray-700 text-white' : 'border-gray-200'
              }`}
            >
              <option value="">请选择...</option>
              {agents.map(a => <option key={a.name} value={a.name}>{a.name}</option>)}
            </select>
          </div>
          <TextArea
            label="指令内容"
            placeholder='{"action": "..."}'
            value={agentCommand}
            onChange={(e) => setAgentCommand(e.target.value)}
          />
          <div className="flex justify-end gap-3">
            <Button variant="secondary" onClick={() => setShowCommandModal(false)}>取消</Button>
            <Button onClick={() => { send({ type: 'agent_command', agent: selectedAgent, command: agentCommand }); setShowCommandModal(false) }}>
              发送
            </Button>
          </div>
        </div>
      </Modal>

      <Modal isOpen={showAddCharacterModal} onClose={() => setShowAddCharacterModal(false)} title="添加角色" size="lg">
        <div className="space-y-4">
          <div className="grid grid-cols-2 gap-4">
            <Input
              label="角色名称 *"
              value={newCharacterForm.name}
              onChange={(e) => setNewCharacterForm({ ...newCharacterForm, name: e.target.value })}
            />
            <div>
              <label className={`block text-sm font-medium mb-1 ${isDark ? 'text-gray-300' : 'text-gray-700'}`}>
                角色类型
              </label>
              <select
                value={newCharacterForm.role}
                onChange={(e) => setNewCharacterForm({ ...newCharacterForm, role: e.target.value })}
                className={`w-full px-3 py-2 rounded-lg border ${
                  isDark ? 'bg-gray-800 border-gray-700 text-white' : 'border-gray-200'
                }`}
              >
                <option value="main">主角</option>
                <option value="supporting">配角</option>
                <option value="npc">NPC</option>
                <option value="antagonist">反派</option>
              </select>
            </div>
          </div>

          <div>
            <label className={`block text-sm font-medium mb-1 ${isDark ? 'text-gray-300' : 'text-gray-700'}`}>
              角色重要性层级
            </label>
            <select
              value={newCharacterForm.importance_tier}
              onChange={(e) => setNewCharacterForm({ ...newCharacterForm, importance_tier: e.target.value })}
              className={`w-full px-3 py-2 rounded-lg border text-sm ${
                isDark ? 'bg-gray-800 border-gray-700 text-white' : 'border-gray-200'
              }`}
            >
              <optgroup label="主角层 (Tier 1)">
                <option value="protagonist">主角 - 故事核心</option>
                <option value="co_protagonist">共同主角</option>
              </optgroup>
              <optgroup label="核心配角层 (Tier 2)">
                <option value="deuteragonist">第二主角</option>
                <option value="mentor">导师/引路人</option>
                <option value="love_interest">恋爱对象</option>
                <option value="best_friend">挚友/跟班</option>
                <option value="archenemy">宿敌/主要反派</option>
              </optgroup>
              <optgroup label="重要配角层 (Tier 3)">
                <option value="major_ally">重要盟友</option>
                <option value="major_antagonist">重要反派</option>
                <option value="rival">竞争对手</option>
                <option value="family_member">家人</option>
                <option value="guardian">守护者</option>
              </optgroup>
              <optgroup label="阶段性角色层 (Tier 4)">
                <option value="arc_antagonist">篇章反派</option>
                <option value="arc_ally">篇章盟友</option>
                <option value="recurring">常驻配角</option>
                <option value="catalyst">催化剂角色</option>
                <option value="mystery_figure">神秘人物</option>
              </optgroup>
              <optgroup label="功能性角色层 (Tier 5)">
                <option value="minion">爪牙/手下</option>
                <option value="informant">消息提供者</option>
                <option value="comic_relief">喜剧担当</option>
                <option value="victim">受害者</option>
              </optgroup>
              <optgroup label="背景层 (Tier 6)">
                <option value="npc">NPC</option>
                <option value="background">背景人物</option>
                <option value="cameo">客串</option>
              </optgroup>
            </select>
            <p className={`mt-1 text-xs ${isDark ? 'text-gray-500' : 'text-gray-400'}`}>
              层级越高，Agent 在生成剧情时越优先考虑该角色
            </p>
          </div>

          <TextArea
            label="角色描述"
            value={newCharacterForm.description}
            onChange={(e) => setNewCharacterForm({ ...newCharacterForm, description: e.target.value })}
            placeholder="简要描述角色的背景、性格特点..."
          />

          <div className="flex justify-end gap-3">
            <Button variant="secondary" onClick={() => setShowAddCharacterModal(false)}>取消</Button>
            <Button onClick={handleAddCharacter} disabled={!newCharacterForm.name.trim()}>添加</Button>
          </div>
        </div>
      </Modal>

      <Modal isOpen={showAutoModeModal} onClose={() => setShowAutoModeModal(false)} title="连续创作模式" size="lg">
        <div className="space-y-4">
          <div className={`p-4 rounded-lg ${isDark ? 'bg-purple-900/30' : 'bg-purple-50'}`}>
            <p className={`text-sm ${isDark ? 'text-purple-300' : 'text-purple-700'}`}>
              连续创作将循环执行选中的工作流，每执行一次生成一个章节。
            </p>
          </div>

          {selectedWorkflowId && (
            <div className={`p-3 rounded-lg border ${isDark ? 'border-blue-800 bg-blue-900/20' : 'border-blue-200 bg-blue-50'}`}>
              <p className={`text-xs font-medium mb-1 ${isDark ? 'text-blue-400' : 'text-blue-600'}`}>当前工作流</p>
              <p className={`text-sm font-semibold ${isDark ? 'text-blue-300' : 'text-blue-700'}`}>
                {selectedWorkflow ? getWorkflowDisplayName(selectedWorkflow) : ''}
              </p>
            </div>
          )}

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className={`block text-sm font-medium mb-1 ${isDark ? 'text-gray-300' : 'text-gray-700'}`}>
                章节数量
              </label>
              <input
                type="number"
                value={autoModeForm.chapter_count}
                onChange={(e) => setAutoModeForm({ ...autoModeForm, chapter_count: parseInt(e.target.value) || 3 })}
                className={`w-full px-3 py-2 rounded-lg border ${
                  isDark ? 'bg-gray-800 border-gray-700 text-white' : 'border-gray-200'
                }`}
                min={1}
                max={20}
              />
            </div>
            <div>
              <label className={`block text-sm font-medium mb-1 ${isDark ? 'text-gray-300' : 'text-gray-700'}`}>
                每章字数
              </label>
              <input
                type="number"
                value={autoModeForm.words_per_chapter}
                onChange={(e) => setAutoModeForm({ ...autoModeForm, words_per_chapter: parseInt(e.target.value) || 2000 })}
                className={`w-full px-3 py-2 rounded-lg border ${
                  isDark ? 'bg-gray-800 border-gray-700 text-white' : 'border-gray-200'
                }`}
                min={500}
                max={5000}
              />
            </div>
          </div>

          <TextArea
            label="风格参考（可选）"
            value={autoModeForm.style_reference}
            onChange={(e) => setAutoModeForm({ ...autoModeForm, style_reference: e.target.value })}
            placeholder="粘贴一段希望模仿风格的文字..."
          />

          <div className="flex justify-end gap-3 pt-2">
            <Button variant="secondary" onClick={() => setShowAutoModeModal(false)}>取消</Button>
            <Button onClick={handleStartAutoMode}>
              <Play size={16} className="mr-1" /> 开始
            </Button>
          </div>
        </div>
      </Modal>

      <Modal isOpen={showWriteChapterModal} onClose={() => setShowWriteChapterModal(false)} title="生成单章" size="lg">
        <div className="space-y-4">
          <div className={`p-4 rounded-lg ${isDark ? 'bg-green-900/30' : 'bg-green-50'}`}>
            <p className={`text-sm ${isDark ? 'text-green-300' : 'text-green-700'}`}>
              执行一次工作流生成单个章节，适合快速测试或补充章节。
            </p>
          </div>

          {selectedWorkflowId && (
            <div className={`p-3 rounded-lg border ${isDark ? 'border-blue-800 bg-blue-900/20' : 'border-blue-200 bg-blue-50'}`}>
              <p className={`text-xs font-medium mb-1 ${isDark ? 'text-blue-400' : 'text-blue-600'}`}>当前工作流</p>
              <p className={`text-sm font-semibold ${isDark ? 'text-blue-300' : 'text-blue-700'}`}>
                {selectedWorkflow ? getWorkflowDisplayName(selectedWorkflow) : ''}
              </p>
            </div>
          )}

          <Input
            label="章节标题 *"
            value={chapterForm.title}
            onChange={(e) => setChapterForm({ ...chapterForm, title: e.target.value })}
            placeholder="输入章节标题..."
          />

          <TextArea
            label="章节目标 *"
            value={chapterForm.goal}
            onChange={(e) => setChapterForm({ ...chapterForm, goal: e.target.value })}
            placeholder="描述本章要完成的剧情目标、要发生的冲突或转折..."
            rows={3}
          />

          <div>
            <label className={`block text-sm font-medium mb-1 ${isDark ? 'text-gray-300' : 'text-gray-700'}`}>
              目标字数
            </label>
            <input
              type="number"
              value={chapterForm.targetWordCount}
              onChange={(e) => setChapterForm({ ...chapterForm, targetWordCount: parseInt(e.target.value) || 2000 })}
              className={`w-full px-3 py-2 rounded-lg border ${
                isDark ? 'bg-gray-800 border-gray-700 text-white' : 'border-gray-200'
              }`}
              min={500}
              max={10000}
              step={100}
            />
            <p className={`mt-1 text-xs ${isDark ? 'text-gray-500' : 'text-gray-400'}`}>
              建议 1500-3000 字
            </p>
          </div>

          <div className="flex justify-end gap-3 pt-2">
            <Button variant="secondary" onClick={() => setShowWriteChapterModal(false)}>取消</Button>
            <Button onClick={handleWriteChapter} disabled={!chapterForm.title.trim() || !chapterForm.goal.trim()}>
              <FileText size={16} className="mr-1" /> 生成章节
            </Button>
          </div>
        </div>
      </Modal>
    </PageLayout>
  )
}
