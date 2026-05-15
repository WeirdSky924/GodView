import { useEffect, useMemo, useState, useCallback, useRef } from 'react'
import { Link } from 'react-router-dom'
import { Card, Button, Input, TextArea, Modal } from '@/components/ui'
import PageLayout from '@/components/PageLayout'
import { useDynamicWebSocket } from '@/hooks/useWebSocket'
import { getDirectorState, getSnapshotTree } from '@/api/director'
import { getCharacters } from '@/api/characters'
import {
  executeWorkflow,
  extractChapterReadinessGateDetail,
  formatChapterReadinessGateMessage,
  formatApiErrorMessage,
  getActiveWorkflowExecution,
  getWorkflows,
  getExecution,
  getExecutionOperationEvents,
  getExecutionOperationSummary,
  pauseExecution,
  resumeExecution,
  recoverExecution,
  resetDirectorSessionWorkflow,
  cancelExecution,
  createWorkflowExecutionEventSource,
  type WorkflowDefinition,
  type WorkflowExecution,
  type WorkflowEventMessage,
  type WorkflowOperationEvent,
  type WorkflowOperationSummary,
  type ChapterReadinessGateDetail,
} from '@/api/workflows'
import {
  getOutlines,
  getOutlineResourceRequirements,
  getChapterResourceReadiness,
  type ChapterOutline,
  type OutlineStatus,
  type OutlineResourceRequirement,
  type ChapterResourceReadiness,
} from '@/api/outlines'
import {
  formatRequirementList,
  formatRequirementSummary,
  getRequirementRecoveryActionLabel,
  getRequirementRecoveryPath,
  getRequirementTypeLabel,
  getRequirementTargetType,
} from '@/utils/resourceRequirementDisplay'
import { useWorkflowAgents, type AgentStatus, getAgentDisplayName } from '@/hooks/useWorkflowAgents'
import {
  Play, Pause, RotateCcw, Target, BookOpen, MessageSquare, GitBranch, Settings,
  Sparkles, FileText, Network, FolderOpen, UserPlus, UserMinus, Users, ChevronDown,
  ChevronUp, Send, X, Circle, Copy, Check, Shield, Zap, Brain, Keyboard,
  ExternalLink, RefreshCw, Square, Activity, AlertTriangle
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
type AutoOutlineMode = 'selected' | 'auto_progression'
type GeneratedChapterStatus = 'generated' | 'saved' | 'failed'

type DirectorGeneratedChapter = {
  chapter_num: number
  title: string
  word_count: number
  content: string
  chapter_id?: string
  chapter_outline_id?: string
  snapshot_id?: string
  execution_id?: string
  workflow_id?: string
  project_id?: string
  status?: GeneratedChapterStatus
  saved_at?: string
  content_storage?: string
  content_path?: string
  content_size_bytes?: number
  content_checksum?: string
  content_chars?: number
  quality_gate_status?: string
  quality_gate_passed?: boolean
  quality_gate_score?: number
  quality_gate_attempts?: number
  revision_attempts?: number
}

type PendingUserInput = {
  node_id: string
  node_type?: string
  label?: string
  description?: string
  prompt?: string
  input_key?: string
  input_type?: string
  placeholder?: string
  required?: boolean
  default_value?: string
}


const OUTLINE_STATUS_CONFIG: Record<OutlineStatus, { label: string; className: string }> = {
  draft: { label: '草稿', className: 'bg-gray-100 text-gray-700' },
  approved: { label: '已审批', className: 'bg-green-100 text-green-700' },
  in_writing: { label: '写作中', className: 'bg-blue-100 text-blue-700' },
  completed: { label: '已完成', className: 'bg-purple-100 text-purple-700' },
  revision: { label: '修订提案', className: 'bg-orange-100 text-orange-700' },
  rejected: { label: '已拒绝', className: 'bg-red-100 text-red-700' },
}

function isOutlineWritable(outline?: ChapterOutline | null) {
  return !!outline && outline.status === 'approved'
}

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

function isWorkflowExecutionEventType(type?: string): boolean {
  return [
    'execution_snapshot',
    'workflow_started',
    'workflow_completed',
    'workflow_failed',
    'workflow_paused',
    'workflow_resumed',
    'workflow_cancelled',
    'chapter_saved',
    'chapter_save_failed',
    'node_started',
    'node_failed',
    'node_completed',
    'node_output',
    'node_streaming',
    'agent_status',
    'agent_streaming',
    'agent_output',
    'group_discussion_started',
    'discussion_message',
    'discussion_ended',
    'user_input_required',
    'user_input_received',
    'intervention_queued',
    'intervention_applied',
  ].includes(type || '')
}

function extractNodeOutputText(outputData?: unknown): string | null {
  if (typeof outputData === 'string') {
    return outputData.trim() ? outputData : null
  }

  if (!outputData || typeof outputData !== 'object' || Object.keys(outputData).length === 0) {
    return null
  }

  const data = outputData as Record<string, any>
  const preferredOutput =
    data.output ??
    data.content ??
    data.result ??
    data.response ??
    data.text ??
    data.message ??
    data.chapter_content

  if (typeof preferredOutput === 'string' && preferredOutput.trim()) {
    return preferredOutput
  }

  if (preferredOutput !== undefined && preferredOutput !== null) {
    return typeof preferredOutput === 'string'
      ? preferredOutput
      : JSON.stringify(preferredOutput, null, 2)
  }

  return JSON.stringify(data, null, 2)
}

function getExecutionIdFromPayload(payload: any): string | null {
  return payload?.execution_id || payload?.data?.execution_id || null
}

function getNodeDataFromWorkflowExecution(
  execution: WorkflowExecution,
  nodeId: string,
  workflow: WorkflowDefinition | null,
) {
  const workflowNode = workflow?.nodes.find((node) => node.id === nodeId)
  return {
    agent_type: workflowNode?.agent_type,
    label: workflowNode?.label,
    node_type: workflowNode?.node_type,
    node_id: nodeId,
    execution_id: execution.id,
  }
}

function mapNodeExecutionStatus(status?: string): AgentStatus['status'] {
  switch (status) {
    case 'running':
      return 'working'
    case 'completed':
      return 'completed'
    case 'failed':
      return 'error'
    default:
      return 'idle'
  }
}

function getWorkflowDisplayName(workflow: WorkflowDefinition): string {
  return getWorkflowOrigin(workflow) === 'global_template'
    ? `${workflow.name}（全局模板）`
    : workflow.name
}

function getSelectedWorkflow(workflows: WorkflowDefinition[], workflowId: string): WorkflowDefinition | null {
  return workflows.find(w => w.id === workflowId) || null
}

function extractDiscussionSpeaker(message: any): string {
  const speaker = message?.speaker || message?.agent || message?.character || message?.role || message?.source_character || message?.name
  return typeof speaker === 'string' && speaker.trim() ? speaker.trim() : 'Agent'
}

function extractDiscussionContent(message: any): string {
  const keys = ['content', 'public_content', 'summary', 'dialogue', 'action', 'message', 'text']
  for (const key of keys) {
    const value = message?.[key]
    if (typeof value === 'string' && value.trim()) return value.trim()
  }
  const data = message?.data
  if (data && typeof data === 'object') {
    for (const key of keys) {
      const value = data[key]
      if (typeof value === 'string' && value.trim()) return value.trim()
    }
  }
  return ''
}

function formatDiscussionMessage(message: any) {
  return {
    character: extractDiscussionSpeaker(message),
    content: extractDiscussionContent(message),
    timestamp: new Date().toLocaleTimeString(),
    isLLMGenerated: message?.is_llm_generated,
    speakerType: message?.speaker_type,
  }
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

function getDirectorStorageKey(projectId: string, key: 'workflow' | 'execution', sessionId?: string): string {
  const sessionScope = sessionId?.trim()
  return sessionScope
    ? `godview.director.${projectId}.${sessionScope}.${key}`
    : `godview.director.${projectId}.${key}`
}

function getDirectorExecutionSessionId(execution: WorkflowExecution): string {
  return String(execution.director_session_id || execution.context?.director_session_id || '')
}

function getDirectorChapterFromPayload(
  payload: any,
  fallback: Partial<DirectorGeneratedChapter> = {},
): DirectorGeneratedChapter | null {
  const data = payload?.data || payload || {}
  const chapterId = data.chapter_id || data.id || data.chapter?.id || fallback.chapter_id
  const outlineId = data.chapter_outline_id || data.chapter?.chapter_outline_id || data.outline_id || fallback.chapter_outline_id
  const chapterNum = data.chapter_num ?? data.chapter_number ?? data.chapter?.chapter_num ?? data.chapter?.chapter_number ?? fallback.chapter_num
  const title = data.title || data.chapter_title || data.chapter?.title || fallback.title || (chapterNum ? `第 ${chapterNum} 章` : '已保存章节')
  const content = data.content ?? data.chapter_content ?? data.chapter?.content ?? fallback.content ?? ''
  const wordCount = data.word_count ?? data.chapter?.word_count ?? fallback.word_count ?? (typeof content === 'string' ? content.length : 0)

  if (!chapterId && !outlineId && chapterNum === undefined) return null

  return {
    chapter_num: Number(chapterNum || fallback.chapter_num || 0),
    title,
    word_count: Number(wordCount || 0),
    content: typeof content === 'string' ? content : '',
    chapter_id: chapterId,
    chapter_outline_id: outlineId,
    snapshot_id: data.snapshot_id || data.chapter?.snapshot_id || fallback.snapshot_id,
    execution_id: data.execution_id || fallback.execution_id,
    workflow_id: data.workflow_id || fallback.workflow_id,
    project_id: data.project_id || data.chapter?.project_id || fallback.project_id,
    status: data.status || fallback.status || (chapterId ? 'saved' : 'generated'),
    saved_at: data.saved_at || data.created_at || fallback.saved_at,
    content_storage: data.content_storage || data.chapter?.content_storage || fallback.content_storage,
    content_path: data.content_path || data.chapter?.content_path || fallback.content_path,
    content_size_bytes: data.content_size_bytes ?? data.chapter?.content_size_bytes ?? fallback.content_size_bytes,
    content_checksum: data.content_checksum || data.chapter?.content_checksum || fallback.content_checksum,
    content_chars: data.content_chars ?? data.chapter?.content_chars ?? fallback.content_chars,
    quality_gate_status: data.quality_gate_status ?? data.chapter?.quality_gate_status ?? fallback.quality_gate_status,
    quality_gate_passed: data.quality_gate_passed ?? data.chapter?.quality_gate_passed ?? fallback.quality_gate_passed,
    quality_gate_score: data.quality_gate_score ?? data.chapter?.quality_gate_score ?? fallback.quality_gate_score,
    quality_gate_attempts: data.quality_gate_attempts ?? data.chapter?.quality_gate_attempts ?? fallback.quality_gate_attempts,
    revision_attempts: data.revision_attempts ?? data.chapter?.revision_attempts ?? fallback.revision_attempts,
  }
}

function upsertDirectorChapter(
  chapters: DirectorGeneratedChapter[],
  nextChapter: DirectorGeneratedChapter,
): DirectorGeneratedChapter[] {
  const index = chapters.findIndex((chapter) => (
    (nextChapter.chapter_id && chapter.chapter_id === nextChapter.chapter_id) ||
    (nextChapter.chapter_outline_id && chapter.chapter_outline_id === nextChapter.chapter_outline_id) ||
    (nextChapter.chapter_num > 0 && chapter.chapter_num === nextChapter.chapter_num)
  ))

  if (index === -1) return [nextChapter, ...chapters]

  return chapters.map((chapter, chapterIndex) => (
    chapterIndex === index
      ? { ...chapter, ...nextChapter, content: nextChapter.content || chapter.content }
      : chapter
  ))
}

function isTerminalExecutionStatus(status?: string): boolean {
  return ['completed', 'failed', 'cancelled'].includes(status || '')
}

function isActiveExecutionStatus(status?: string): boolean {
  return ['running', 'paused', 'pending'].includes(status || '')
}

function getFailureDiagnosticsHref(projectId?: string, executionId?: string | null, nodeId?: string | null): string {
  if (!projectId || !executionId) return ''
  const params = new URLSearchParams({ project_id: projectId, execution_id: executionId })
  if (nodeId) params.set('node_id', nodeId)
  return `/visualize?${params.toString()}`
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
    messages: Array<{ character: string; content: string; timestamp: string; isLLMGenerated?: boolean; speakerType?: string }>
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
  isDark,
  projectId,
}: {
  chapter: DirectorGeneratedChapter
  onCopy: () => void
  isDark: boolean
  projectId?: string
}) {
  const [copied, setCopied] = useState(false)

  const handleCopy = () => {
    navigator.clipboard.writeText(chapter.content)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
    onCopy()
  }

  const links = chapter.chapter_id
    ? [
      { label: '正文', href: `/novel?chapter_id=${encodeURIComponent(chapter.chapter_id)}` },
      { label: '对比', href: `/diff?left_chapter_id=${encodeURIComponent(chapter.chapter_id)}` },
      { label: '评估', href: `/chapter-evaluator?chapter_id=${encodeURIComponent(chapter.chapter_id)}` },
      { label: '读者', href: `/simulator?chapter_id=${encodeURIComponent(chapter.chapter_id)}` },
      { label: '状态', href: `/state-changes?chapter_id=${encodeURIComponent(chapter.chapter_id)}&status=proposed` },
    ]
    : []
  const diagnosticsHref = getFailureDiagnosticsHref(projectId, chapter.execution_id)
  const isFailed = chapter.status === 'failed'

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
          {chapter.status && (
            <span className={`text-xs px-2 py-0.5 rounded-full ${chapter.status === 'saved'
              ? isDark ? 'bg-green-900/40 text-green-300' : 'bg-green-100 text-green-700'
              : isDark ? 'bg-gray-800 text-gray-400' : 'bg-gray-100 text-gray-500'
            }`}>
              {chapter.status === 'saved' ? '已保存' : chapter.status === 'failed' ? '失败' : '已生成'}
            </span>
          )}
          {chapter.quality_gate_status && (
            <span className={`text-xs px-2 py-0.5 rounded-full ${chapter.quality_gate_passed
              ? isDark ? 'bg-emerald-900/40 text-emerald-300' : 'bg-emerald-100 text-emerald-700'
              : isDark ? 'bg-amber-900/40 text-amber-300' : 'bg-amber-100 text-amber-700'
            }`}>
              质量门 {chapter.quality_gate_status}{typeof chapter.quality_gate_score === 'number' ? ` · ${chapter.quality_gate_score}` : ''}
            </span>
          )}
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
        {isFailed && diagnosticsHref && (
          <div className={`mb-3 rounded-lg border px-3 py-2 text-xs ${isDark ? 'border-red-800 bg-red-950/30 text-red-200' : 'border-red-200 bg-red-50 text-red-700'}`}>
            保存或生成失败。请从诊断入口查看失败节点、原因和恢复操作，Director 不内嵌修复面板。
          </div>
        )}
        {(chapter.quality_gate_status || typeof chapter.quality_gate_attempts === 'number' || typeof chapter.revision_attempts === 'number') && (
          <div className={`mb-3 rounded-lg border px-3 py-2 text-xs ${isDark ? 'border-emerald-900/60 bg-emerald-950/20 text-emerald-200' : 'border-emerald-200 bg-emerald-50 text-emerald-700'}`}>
            质量门：{chapter.quality_gate_status || '-'}
            {typeof chapter.quality_gate_score === 'number' ? ` · 分数 ${chapter.quality_gate_score}` : ''}
            {typeof chapter.quality_gate_attempts === 'number' ? ` · 尝试 ${chapter.quality_gate_attempts}` : ''}
            {typeof chapter.revision_attempts === 'number' ? ` · 修订 ${chapter.revision_attempts}` : ''}
          </div>
        )}
        {(links.length > 0 || diagnosticsHref) && (
          <div className="flex flex-wrap gap-2 mb-3">
            {links.map((link) => (
              <a
                key={link.label}
                href={link.href}
                className={`inline-flex items-center gap-1 px-2.5 py-1 rounded-md text-xs font-medium ${
                  isDark ? 'bg-gray-800 text-blue-300 hover:bg-gray-700' : 'bg-blue-50 text-blue-700 hover:bg-blue-100'
                }`}
              >
                {link.label}<ExternalLink size={12} />
              </a>
            ))}
            {diagnosticsHref && (
              <a
                href={diagnosticsHref}
                className={`inline-flex items-center gap-1 px-2.5 py-1 rounded-md text-xs font-medium ${
                  isDark ? 'bg-gray-800 text-amber-300 hover:bg-gray-700' : 'bg-amber-50 text-amber-700 hover:bg-amber-100'
                }`}
              >
                {isFailed ? '诊断/修复' : '诊断'}<ExternalLink size={12} />
              </a>
            )}
          </div>
        )}
        <div className={`p-4 rounded-lg max-h-64 overflow-y-auto text-sm leading-relaxed whitespace-pre-wrap ${
          isDark ? 'bg-gray-800/50' : 'bg-gray-50'
        }`}>
          {chapter.content || '章节已保存，可通过上方链接进入正文页面查看完整内容。'}
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
  const [executionId, setExecutionId] = useState('')
  const [isExecutionStreamReady, setIsExecutionStreamReady] = useState(false)
  const [operationSummary, setOperationSummary] = useState<WorkflowOperationSummary | null>(null)
  const [operationEvents, setOperationEvents] = useState<WorkflowOperationEvent[]>([])
  const [operationBusy, setOperationBusy] = useState<string | null>(null)
  const [directorResetToken, setDirectorResetToken] = useState('')
  const pendingSnapshotRef = useRef<{ execution: WorkflowExecution; workflow: WorkflowDefinition | null } | null>(null)

  const selectedWorkflow = useMemo(
    () => getSelectedWorkflow(savedWorkflows, selectedWorkflowId),
    [savedWorkflows, selectedWorkflowId],
  )
  const selectedWorkflowRef = useRef<WorkflowDefinition | null>(null)

  useEffect(() => {
    selectedWorkflowRef.current = selectedWorkflow
  }, [selectedWorkflow])

  const stateHandoffSummary = useMemo(() => {
    const handoffEvents = operationEvents.filter(event => [
      'chapter_state_writeback_proposed',
      'chapter_state_writeback_applied',
      'chapter_state_writeback_failed',
      'chapter_state_handoff_loaded',
    ].includes(event.event_type))
    if (!handoffEvents.length) return null
    return handoffEvents.reduce(
      (acc, event) => {
        const data = event.data || {}
        acc.proposed = Math.max(acc.proposed, Number(data.proposed_count || 0))
        acc.applied = Math.max(acc.applied, Number(data.applied_count || 0))
        acc.pending = Math.max(acc.pending, Number(data.pending_count || 0))
        acc.errors = Math.max(acc.errors, Number(data.error_count || 0))
        acc.prior = Math.max(acc.prior, Number(data.prior_chapter_count || 0))
        acc.confirmed = Math.max(acc.confirmed, Number(data.confirmed_state_count || 0))
        return acc
      },
      { proposed: 0, applied: 0, pending: 0, errors: 0, prior: 0, confirmed: 0 },
    )
  }, [operationEvents])

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
  const [autoModeChapters, setAutoModeChapters] = useState<DirectorGeneratedChapter[]>([])
  const [showAutoModeModal, setShowAutoModeModal] = useState(false)
  const [autoModeForm, setAutoModeForm] = useState({
    chapter_count: 3,
    words_per_chapter: 2000,
    style_reference: '',
  })
  const [chapterOutlines, setChapterOutlines] = useState<ChapterOutline[]>([])
  const [outlineResourceRequirementsByKey, setOutlineResourceRequirementsByKey] = useState<Record<string, OutlineResourceRequirement[]>>({})
  const [outlineReadinessByKey, setOutlineReadinessByKey] = useState<Record<string, ChapterResourceReadiness>>({})
  const [resourceRequirementRefreshMessage, setResourceRequirementRefreshMessage] = useState('')
  const [outlinesLoading, setOutlinesLoading] = useState(false)
  const [outlineRefreshNonce, setOutlineRefreshNonce] = useState(0)
  const [runtimeRefreshNonce, setRuntimeRefreshNonce] = useState(0)
  const [selectedSingleOutlineId, setSelectedSingleOutlineId] = useState('')
  const [selectedAutoOutlineIds, setSelectedAutoOutlineIds] = useState<string[]>([])
  const [autoOutlineMode, setAutoOutlineMode] = useState<AutoOutlineMode>('selected')
  const [autoStartOutlineId, setAutoStartOutlineId] = useState('')

  // UI state
  const [showLogs, setShowLogs] = useState(true)

  const [pendingUserInput, setPendingUserInput] = useState<PendingUserInput | null>(null)
  const [workflowUserInput, setWorkflowUserInput] = useState('')

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
    targetWordCount: 2000,
  })
  const [singleChapterGateDetail, setSingleChapterGateDetail] = useState<ChapterReadinessGateDetail | null>(null)

  // Discussion state
  const [groupDiscussion, setGroupDiscussion] = useState<{
    topic: string
    messages: Array<{ character: string; content: string; timestamp: string; isLLMGenerated?: boolean; speakerType?: string }>
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
  const addLog = useCallback((message: string) => {
    const timestamp = new Date().toLocaleTimeString()
    setLogs(prev => [`[${timestamp}] ${message}`, ...prev.slice(0, 199)])
  }, [])

  const refreshWorkflowOperations = useCallback(async (targetExecutionId = executionId) => {
    if (!targetExecutionId) {
      setOperationSummary(null)
      setOperationEvents([])
      return null
    }

    try {
      const [summary, events] = await Promise.all([
        getExecutionOperationSummary(targetExecutionId),
        getExecutionOperationEvents(targetExecutionId, 8),
      ])
      setOperationSummary(summary)
      setOperationEvents(events)
      return summary
    } catch (error) {
      console.error('Failed to refresh workflow operations:', error)
      return null
    }
  }, [executionId])

  const updateAgentFromNode = useCallback((
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
  }, [updateAgentStatus])

  const getWorkingAgentName = () => agents.find(a => a.status === 'working')?.message || null

  const applyWorkflowExecutionSnapshot = useCallback((execution: WorkflowExecution, workflow: WorkflowDefinition | null) => {
    if (!execution) return

    setExecutionId(execution.id)
    if (execution.operation_summary) {
      setOperationSummary(execution.operation_summary)
    }

    const savedPayload = execution.context?.chapter_saved_payload
    const hasFinalSavedChapter = execution.context?.chapter_saved === true || savedPayload?.status === 'saved'
    if (hasFinalSavedChapter) {
      const savedChapter = getDirectorChapterFromPayload(savedPayload || execution.context, {
        execution_id: execution.id,
        workflow_id: execution.workflow_id,
        project_id: execution.project_id,
        chapter_id: execution.context?.chapter_id,
        chapter_outline_id: execution.context?.chapter_outline_id,
        content_storage: execution.context?.chapter_content_storage,
        content_path: execution.context?.chapter_content_path,
        content_size_bytes: execution.context?.chapter_content_size_bytes,
        content_checksum: execution.context?.chapter_content_checksum,
        status: 'saved',
        saved_at: execution.context?.chapter_saved_at,
      })
      if (savedChapter && savedChapter.chapter_id) {
        setAutoModeChapters(prev => upsertDirectorChapter(prev, savedChapter))
      }
    }

    const pendingInput = execution.status === 'paused'
      ? execution.context?.pending_user_input
      : null
    if (pendingInput?.node_id) {
      setPendingUserInput(pendingInput as PendingUserInput)
      setWorkflowUserInput(String(pendingInput.default_value || ''))
      setIsGenerating(true)
    } else {
      setPendingUserInput(null)
      setWorkflowUserInput('')
    }

    Object.entries(execution.node_states || {}).forEach(([nodeId, nodeState]) => {
      const nodeData = getNodeDataFromWorkflowExecution(execution, nodeId, workflow)
      const nodeKey = getAgentStateKey(nodeData)
      const mappedStatus = mapNodeExecutionStatus(nodeState.status)
      const outputText = extractNodeOutputText(nodeState.output_data)
      const statusMessage =
        nodeState.error ||
        (mappedStatus === 'working' ? '执行中' : undefined)

      updateAgentFromNode(nodeData, { status: mappedStatus, message: statusMessage })

      if (nodeKey && outputText) {
        setAgentOutput(nodeKey, outputText)
      }

      if (nodeKey) {
        if (mappedStatus === 'working') {
          updateAgentStreaming((prev) => ({
            ...prev,
            [nodeKey]: prev[nodeKey] || '',
          }))
        } else {
          clearAgentStreaming(nodeKey)
        }
      }
    })

    if (isTerminalExecutionStatus(execution.status)) {
      setIsGenerating(false)
    } else if (isActiveExecutionStatus(execution.status)) {
      setIsGenerating(true)
    }
  }, [clearAgentStreaming, setAgentOutput, updateAgentFromNode, updateAgentStreaming])

  useEffect(() => {
    const pendingSnapshot = pendingSnapshotRef.current
    if (!pendingSnapshot || pendingSnapshot.workflow?.id !== selectedWorkflowId) return

    pendingSnapshotRef.current = null
    applyWorkflowExecutionSnapshot(pendingSnapshot.execution, pendingSnapshot.workflow)
  }, [applyWorkflowExecutionSnapshot, selectedWorkflowId])

  const getGatePayloadMessage = useCallback((payload?: any) => {
    const detail = extractChapterReadinessGateDetail({ data: payload })
    if (detail) {
      return formatChapterReadinessGateMessage(
        detail,
        requirements => formatRequirementList(requirements as OutlineResourceRequirement[], 5),
      )
    }
    return formatApiErrorMessage({ data: payload }, '')
  }, [])

  const applyDirectorEvent = useCallback((payload: any) => {
    const eventType = payload?.type
    const eventData = payload?.data || payload

    if (eventType === 'execution_snapshot') {
      applyWorkflowExecutionSnapshot(eventData as WorkflowExecution, selectedWorkflowRef.current)
      return true
    }

    switch (eventType) {
      case 'workflow_started': {
        const nextExecutionId = getExecutionIdFromPayload(payload)
        if (nextExecutionId) {
          setExecutionId(nextExecutionId)
        }
        addLog('🚀 工作流已启动')
        setIsGenerating(true)
        void refreshWorkflowOperations(nextExecutionId || executionId)
        return true
      }
      case 'workflow_completed': {
        addLog('✅ 工作流执行完成')
        setIsGenerating(false)
        setPendingUserInput(null)
        setWorkflowUserInput('')
        void refreshWorkflowOperations(getExecutionIdFromPayload(payload) || executionId)
        return true
      }
      case 'workflow_start_blocked': {
        const detail = extractChapterReadinessGateDetail({ data: eventData || payload })
        addLog(`⛔ 工作流启动阻塞: ${formatChapterReadinessGateMessage(
          detail,
          requirements => formatRequirementList(requirements as OutlineResourceRequirement[], 5),
        )}`)
        setIsGenerating(false)
        return true
      }
      case 'workflow_failed': {
        const failedExecutionId = getExecutionIdFromPayload(payload) || executionId
        const failedNodeId = eventData?.failed_node_id || eventData?.node_id || eventData?.current_node || eventData?.failed_node?.id
        const diagnosticsHref = getFailureDiagnosticsHref(currentProject?.id, failedExecutionId, failedNodeId)
        addLog(`❌ 工作流执行失败: ${getGatePayloadMessage(eventData) || eventData?.error || '未知错误'}${diagnosticsHref ? `；诊断/修复: ${diagnosticsHref}` : ''}`)
        setIsGenerating(false)
        void refreshWorkflowOperations(failedExecutionId)
        return true
      }
      case 'workflow_paused': {
        const pendingInput = eventData?.pending_user_input || eventData?.pending_input
        if (pendingInput?.node_id) {
          setPendingUserInput(pendingInput as PendingUserInput)
          setWorkflowUserInput(String(pendingInput.default_value || ''))
          addLog(`⌨️ 工作流等待用户输入：${pendingInput.label || '用户输入'}`)
        } else {
          addLog('⏸️ 工作流已暂停')
        }
        void refreshWorkflowOperations(getExecutionIdFromPayload(payload) || executionId)
        return true
      }
      case 'workflow_resumed': {
        addLog('▶️ 工作流已恢复')
        setIsGenerating(true)
        void refreshWorkflowOperations(getExecutionIdFromPayload(payload) || executionId)
        return true
      }
      case 'workflow_cancelled': {
        addLog('🛑 工作流已取消')
        setIsGenerating(false)
        void refreshWorkflowOperations(getExecutionIdFromPayload(payload) || executionId)
        return true
      }
      case 'chapter_saved': {
        const savedChapter = getDirectorChapterFromPayload(eventData, {
          execution_id: getExecutionIdFromPayload(payload) || executionId,
          workflow_id: selectedWorkflowId,
          project_id: currentProject?.id,
          status: 'saved',
        })
        if (savedChapter) {
          setAutoModeChapters(prev => upsertDirectorChapter(prev, savedChapter))
          addLog(`💾 章节已保存并可交接: ${savedChapter.title}${savedChapter.chapter_id ? ` (${savedChapter.chapter_id})` : ''}`)
          setRuntimeRefreshNonce(value => value + 1)
          setOutlineRefreshNonce(value => value + 1)
          void refreshWorkflowOperations(savedChapter.execution_id || executionId)
        }
        return true
      }
      case 'chapter_save_failed': {
        const failedChapter = getDirectorChapterFromPayload(eventData, {
          execution_id: getExecutionIdFromPayload(payload) || executionId,
          workflow_id: selectedWorkflowId,
          project_id: currentProject?.id,
          status: 'failed',
        })
        if (failedChapter) {
          setAutoModeChapters(prev => upsertDirectorChapter(prev, { ...failedChapter, status: 'failed' }))
        }
        addLog(`❌ 章节保存失败: ${eventData?.title || failedChapter?.title || '未知章节'}${eventData?.error ? ` — ${eventData.error}` : ''}`)
        setRuntimeRefreshNonce(value => value + 1)
        void refreshWorkflowOperations(eventData?.execution_id || executionId)
        return true
      }
      case 'agent_status': {
        const statusKey = getAgentStateKey({
          agent: payload.agent,
          agent_type: payload.agent_type,
          label: payload.label,
          node_type: payload.node_type,
          node_id: payload.node_id,
        })

        if (statusKey) {
          updateAgentStatus(statusKey, payload.status, payload.message)
        }

        if (payload.output) {
          const output = typeof payload.output === 'string' ? payload.output : JSON.stringify(payload.output, null, 2)
          if (statusKey) {
            setAgentOutput(statusKey, output)
          }
        }

        if (payload.status !== 'working' && statusKey) {
          clearAgentStreaming(statusKey)
        }
        return true
      }
      case 'agent_streaming': {
        if (eventData.chunk) {
          const streamKey = getAgentStateKey({
            agent: eventData.agent,
            agent_type: eventData.agent_type,
            label: eventData.label,
            node_type: eventData.node_type,
            node_id: eventData.node_id,
          })

          if (streamKey) {
            appendAgentStreaming(streamKey, eventData.chunk)
          }
        }
        return true
      }
      case 'agent_output': {
        if (eventData.output) {
          const outputStr = typeof eventData.output === 'string' ? eventData.output : JSON.stringify(eventData.output, null, 2)
          const outputKey = getAgentStateKey({
            agent: eventData.agent,
            agent_type: eventData.agent_type,
            label: eventData.label,
            node_type: eventData.node_type,
            node_id: eventData.node_id,
          })

          if (outputKey) {
            setAgentOutput(outputKey, outputStr)
            clearAgentStreaming(outputKey)
          }
        }
        return true
      }
      case 'node_output': {
        if (eventData.output) {
          const outputStr = typeof eventData.output === 'string' ? eventData.output : JSON.stringify(eventData.output, null, 2)
          const nodeKey = getAgentStateKey(eventData)
          const displayName = getNodeDisplayName(eventData)

          if (nodeKey) {
            setAgentOutput(nodeKey, outputStr)
          }

          addLog(`📤 ${displayName}: ${outputStr}`)
        }
        return true
      }
      case 'user_input_required': {
        setPendingUserInput(eventData as PendingUserInput)
        setWorkflowUserInput(String(eventData?.default_value || ''))
        addLog(`⌨️ 工作流等待用户输入：${eventData?.label || '用户输入'}`)
        updateAgentFromNode(eventData, { status: 'working', message: '等待用户输入' })
        return true
      }
      case 'user_input_received': {
        setPendingUserInput(null)
        setWorkflowUserInput('')
        addLog('✅ 用户输入已提交，工作流继续执行')
        return true
      }
      case 'node_started': {
        const displayName = getNodeDisplayName(eventData)
        addLog(`🔄 ${displayName} 开始执行`)
        updateAgentFromNode(eventData, { status: 'working', message: displayName || '执行中' })

        const nodeKey = getAgentStateKey(eventData)
        if (nodeKey) {
          updateAgentStreaming(prev => ({
            ...prev,
            [nodeKey]: prev[nodeKey] || '',
          }))
        }
        return true
      }
      case 'node_failed':
      case 'node_completed': {
        const displayName = getNodeDisplayName(eventData)
        const nodeKey = getAgentStateKey(eventData)
        const outputText = extractNodeOutputText(eventData.output_data ?? eventData.output)

        if (eventType === 'node_failed' || eventData.status === 'failed' || eventData.error) {
          const message = getGatePayloadMessage(eventData) || eventData.error || '未知错误'
          const nodeId = eventData?.node_id || eventData?.id
          const diagnosticsHref = getFailureDiagnosticsHref(currentProject?.id, getExecutionIdFromPayload(payload) || executionId, nodeId)
          addLog(`❌ ${displayName} 执行失败: ${message}${diagnosticsHref ? `；诊断/修复: ${diagnosticsHref}` : ''}`)
          updateAgentFromNode(eventData, { status: 'error', message })
        } else {
          addLog(`✅ ${displayName} 完成`)
          updateAgentFromNode(eventData, { status: 'completed', message: displayName || '完成' })
        }

        if (nodeKey && outputText) {
          setAgentOutput(nodeKey, outputText)
        }

        if (nodeKey) {
          clearAgentStreaming(nodeKey)
        }
        return true
      }
      case 'node_streaming': {
        if (eventData.chunk) {
          const streamKey = getAgentStateKey(eventData)
          if (streamKey) {
            appendAgentStreaming(streamKey, eventData.chunk)
          }
        }
        return true
      }
      case 'group_discussion_started': {
        addLog('🌟 集体讨论开始')
        const discussionMessages = eventData?.messages || []
        const formattedMessages = discussionMessages
          .map(formatDiscussionMessage)
          .filter((msg: any) => msg.content)
        setGroupDiscussion({
          topic: eventData?.discussion_topic || '讨论',
          messages: formattedMessages,
          characters: eventData?.characters || [],
          participants: eventData?.participants || [],
          isActive: true,
        })
        return true
      }
      case 'discussion_message': {
        const sourceMessage = eventData?.message && typeof eventData.message === 'object'
          ? { ...eventData.message, ...eventData }
          : eventData
        const formattedMessage = formatDiscussionMessage(sourceMessage)
        if (!formattedMessage.content) return true
        addLog(`💬 ${formattedMessage.character}: ${formattedMessage.content}${formattedMessage.isLLMGenerated ? ' 🤖' : ''}`)
        setGroupDiscussion(prev => {
          if (prev) {
            return {
              ...prev,
              messages: [...prev.messages, formattedMessage],
            }
          }
          return {
            topic: '创作讨论会',
            messages: [formattedMessage],
            characters: [],
            participants: [],
            isActive: true,
          }
        })
        return true
      }
      case 'discussion_ended': {
        addLog('📝 集体讨论结束')
        setGroupDiscussion(prev => prev ? { ...prev, isActive: false } : null)
        return true
      }
      case 'intervention_queued': {
        const agentName = eventData?.agent || 'Agent'
        addLog(`📤 干预已排队，等待 ${agentName} 执行`)
        return true
      }
      case 'intervention_applied': {
        const agentName = eventData?.agent || 'Agent'
        addLog(`✅ 干预已应用到 ${agentName} (${eventData?.intervention_count || 0} 条)`)
        return true
      }
      default:
        return false
    }
  }, [
    addLog,
    appendAgentStreaming,
    applyWorkflowExecutionSnapshot,
    clearAgentStreaming,
    getGatePayloadMessage,
    executionId,
    refreshWorkflowOperations,
    selectedWorkflowId,
    setAgentOutput,
    updateAgentFromNode,
    updateAgentStatus,
    updateAgentStreaming,
  ])

  const { status: wsStatus, send } = useDynamicWebSocket(
    isConnected && sessionId.trim() ? `/api/ws/connect/${sessionId.trim()}` : '',
    {
      onOpen: () => addLog('✅ WebSocket 已连接，正在启动会话...'),
      onClose: () => {
        addLog('WebSocket 已断开')
        if (!executionId) {
          setIsGenerating(false)
        }
      },
      onError: () => {
        addLog('❌ WebSocket 连接异常')
        setIsConnected(false)
      },
      onMessage: (data) => {
        if (data.type === 'log') {
          addLog(data.message)
          return
        }

        if (data.type === 'workflow_started') {
          applyDirectorEvent(data)
          return
        }

        if (isWorkflowExecutionEventType(data.type)) {
          if (!isExecutionStreamReady) {
            applyDirectorEvent(data)
          }
          return
        }

        switch (data.type) {
          case 'session_started':
            addLog('✅ 会话已启动')
            setIsGenerating(true)
            loadRuntimePanels()
            break
          case 'session_stopped':
            addLog('✅ 后端确认：导演会话已停止')
            setIsGenerating(false)
            setExecutionId('')
            setPendingUserInput(null)
            setWorkflowUserInput('')
            setIsExecutionStreamReady(false)
            setIsConnected(false)
            if (currentProject) {
              localStorage.removeItem(getDirectorStorageKey(currentProject.id, 'execution', sessionId.trim()))
            }
            sessionStartAttempted.current = false
            loadRuntimePanels()
            break
          case 'hooks_managed':
            addLog('🎯 伏笔管理完成')
            setAgentOutput('hook_manager', JSON.stringify(data.data || {}, null, 2))
            loadRuntimePanels()
            break
          case 'auto_mode_chapter_start':
            addLog(`📖 开始写作第 ${data.chapter_num} 章: ${data.title}`)
            break
          case 'auto_mode_chapter_completed': {
            addLog(`✅ 第 ${data.chapter_num} 章完成: ${data.title} (${data.word_count} 字)`)
            const chapter = getDirectorChapterFromPayload(data, { status: data.chapter_id ? 'saved' : 'generated' })
            if (chapter) {
              setAutoModeChapters(prev => upsertDirectorChapter(prev, chapter))
            }
            break
          }
          case 'auto_mode_completed':
            setAutoModeRunning(false)
            addLog(`🎉 连续创作完成！共 ${data.data?.total_chapters} 章，${data.data?.total_words} 字`)
            loadRuntimePanels()
            break
          case 'auto_mode_blocked':
            setAutoModeRunning(false)
            addLog(`⛔ 连续创作启动阻塞: ${getGatePayloadMessage(data)}`)
            void loadChapterOutlines()
            break
          case 'auto_mode_error':
            setAutoModeRunning(false)
            addLog(`❌ 错误: ${getGatePayloadMessage(data) || data.error || '未知错误'}`)
            break
          case 'auto_mode_chapter_blocked':
            setAutoModeRunning(false)
            addLog(`⛔ 第 ${data.chapter_num || data.data?.chapter_num || '?'} 章启动阻塞: ${getGatePayloadMessage(data)}`)
            void loadChapterOutlines()
            break
          case 'auto_write_chapter_started':
            if (data.data?.execution_id) {
              setExecutionId(data.data.execution_id)
            }
            setIsGenerating(true)
            addLog(`🚀 章节工作流已启动: ${data.data?.title || '未命名章节'}`)
            break
          case 'auto_write_chapter_result':
            if (data.status === 'success') {
              addLog(`✅ 章节生成完成: ${data.data?.title} (${data.data?.word_count} 字)`)
              const chapter = getDirectorChapterFromPayload(data.data, {
                chapter_num: autoModeChapters.length + 1,
                execution_id: executionId,
                workflow_id: selectedWorkflowId,
                status: data.data?.chapter_id ? 'saved' : 'generated',
              })
              if (chapter) {
                setAutoModeChapters(prev => upsertDirectorChapter(prev, chapter))
              }
              loadRuntimePanels()
            } else if (data.status === 'blocked') {
              setIsGenerating(false)
              addLog(`⛔ 章节启动阻塞: ${getGatePayloadMessage(data)}`)
              void loadChapterOutlines()
            } else {
              addLog(`❌ 章节生成失败: ${getGatePayloadMessage(data) || data.error || '未知错误'}`)
            }
            break
          case 'character_added':
            addLog(`👤 角色已添加: ${data.data?.name}`)
            if (currentProject) loadCharacters()
            break
          case 'character_removed':
            addLog('👤 角色已移除')
            if (currentProject) loadCharacters()
            break
          case 'workflow_user_input_received':
            setPendingUserInput(null)
            setWorkflowUserInput('')
            addLog('✅ 用户输入已提交')
            break
          case 'agent_response':
          case 'intervention_response':
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
          case 'intervention_logged':
            addLog('📝 干预已记录')
            break
          case 'error':
            addLog(`❌ ${getGatePayloadMessage(data) || data.message || data.error || '未知错误'}`)
            break
          default:
            if (data.type !== 'heartbeat') {
              addLog(`${data.type}: ${JSON.stringify(data.data || {})}`)
            }
        }
      },
    }
  )

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
      const storedWorkflowId = sessionId.trim()
        ? localStorage.getItem(getDirectorStorageKey(currentProject.id, 'workflow', sessionId)) || ''
        : ''
      setSelectedWorkflowId((currentId) => getPreferredWorkflowId(workflows, currentId || storedWorkflowId))
    } catch (error) {
      console.error('Failed to load workflows:', error)
    }
  }, [currentProject, sessionId])

  const loadChapterOutlines = useCallback(async () => {
    if (!currentProject) {
      setChapterOutlines([])
      setOutlineResourceRequirementsByKey({})
      setOutlineReadinessByKey({})
      return
    }

    setOutlinesLoading(true)
    try {
      const result = await getOutlines(currentProject.id)
      const sorted = [...result.outlines].sort((a, b) => a.chapter_number - b.chapter_number)
      const [requirementsResult, readinessResult] = await Promise.all([
        getOutlineResourceRequirements(currentProject.id, { cache: { forceRefresh: true } }),
        getChapterResourceReadiness(currentProject.id, { refresh: true }),
      ])
      const nextRequirementsByKey: Record<string, OutlineResourceRequirement[]> = {}
      for (const requirement of requirementsResult.requirements || []) {
        const keys = [
          requirement.outline_id ? `outline:${requirement.outline_id}` : '',
          requirement.chapter_num !== null && requirement.chapter_num !== undefined ? `chapter:${requirement.chapter_num}` : '',
        ].filter(Boolean)
        for (const key of keys) {
          nextRequirementsByKey[key] = [...(nextRequirementsByKey[key] || []), requirement]
        }
      }
      const nextReadinessByKey: Record<string, ChapterResourceReadiness> = {}
      for (const readiness of readinessResult.readiness || []) {
        if (readiness.outline_id) nextReadinessByKey[`outline:${readiness.outline_id}`] = readiness
        nextReadinessByKey[`chapter:${readiness.chapter_num}`] = readiness
      }
      setOutlineResourceRequirementsByKey(nextRequirementsByKey)
      setOutlineReadinessByKey(nextReadinessByKey)
      setChapterOutlines(sorted)
      setSelectedSingleOutlineId((currentId) => {
        if (currentId && sorted.some(outline => outline.id === currentId)) return currentId
        return sorted.find(isOutlineWritable)?.id || ''
      })
      setAutoStartOutlineId((currentId) => {
        if (currentId && sorted.some(outline => outline.id === currentId)) return currentId
        return sorted.find(isOutlineWritable)?.id || ''
      })
      setSelectedAutoOutlineIds((currentIds) => currentIds.filter(id => sorted.some(outline => outline.id === id)))
    } catch (error) {
      console.error('Failed to load chapter outlines:', error)
      addLog('❌ 加载章节大纲失败')
    } finally {
      setOutlinesLoading(false)
    }
  }, [addLog, currentProject])

  const selectedSingleOutline = useMemo(
    () => chapterOutlines.find(outline => outline.id === selectedSingleOutlineId) || null,
    [chapterOutlines, selectedSingleOutlineId],
  )

  const selectedAutoOutlines = useMemo(
    () => chapterOutlines
      .filter(outline => selectedAutoOutlineIds.includes(outline.id))
      .sort((a, b) => a.chapter_number - b.chapter_number),
    [chapterOutlines, selectedAutoOutlineIds],
  )

  const selectedAutoStartOutline = useMemo(
    () => chapterOutlines.find(outline => outline.id === autoStartOutlineId) || null,
    [autoStartOutlineId, chapterOutlines],
  )

  const toggleAutoOutline = (outlineId: string) => {
    setSelectedAutoOutlineIds((currentIds) => (
      currentIds.includes(outlineId)
        ? currentIds.filter(id => id !== outlineId)
        : [...currentIds, outlineId]
    ))
  }

  const getOutlineRequirements = useCallback((outline?: ChapterOutline | null) => {
    if (!outline) return []
    return outlineResourceRequirementsByKey[`outline:${outline.id}`] || outlineResourceRequirementsByKey[`chapter:${outline.chapter_number}`] || []
  }, [outlineResourceRequirementsByKey])

  const getOutlineReadiness = useCallback((outline?: ChapterOutline | null) => {
    if (!outline) return null
    return outlineReadinessByKey[`outline:${outline.id}`] || outlineReadinessByKey[`chapter:${outline.chapter_number}`] || null
  }, [outlineReadinessByKey])

  const getOutlineBlockingRequirements = useCallback((outline?: ChapterOutline | null) => {
    if (!outline) return []
    const unresolvedStatuses = new Set(['pending', 'in_progress'])
    return getOutlineRequirements(outline).filter(requirement => requirement.severity === 'blocking' && unresolvedStatuses.has(requirement.status))
  }, [getOutlineRequirements])

  const getOutlineReadinessBlockMessage = useCallback((outline?: ChapterOutline | null) => {
    if (!outline) return ''
    const readiness = getOutlineReadiness(outline)
    const blocking = getOutlineBlockingRequirements(outline)
    if (readiness?.readiness_status !== 'blocked' && blocking.length === 0) return ''
    const requirementText = blocking.length > 0 ? formatRequirementList(blocking, 5) : ''
    return requirementText
      ? `第 ${outline.chapter_number} 章资源未就绪：${requirementText}`
      : `第 ${outline.chapter_number} 章资源未就绪，请先刷新资源 readiness。`
  }, [getOutlineBlockingRequirements, getOutlineReadiness])

  const selectedSingleOutlineBlockMessage = useMemo(
    () => getOutlineReadinessBlockMessage(selectedSingleOutline),
    [getOutlineReadinessBlockMessage, selectedSingleOutline],
  )

  const selectedAutoOutlineBlockMessage = useMemo(() => {
    if (autoOutlineMode === 'selected') {
      const blockedOutline = selectedAutoOutlines.find(outline => getOutlineReadinessBlockMessage(outline))
      return blockedOutline ? getOutlineReadinessBlockMessage(blockedOutline) : ''
    }
    return getOutlineReadinessBlockMessage(selectedAutoStartOutline)
  }, [autoOutlineMode, getOutlineReadinessBlockMessage, selectedAutoOutlines, selectedAutoStartOutline])

  const autoModeStartDisabledReason = useMemo(() => {
    if (outlinesLoading) return '章节大纲正在加载中，请稍候。'
    if (autoOutlineMode === 'selected') {
      if (selectedAutoOutlines.length === 0) return '请至少选择一个已审批章节大纲。'
      if (selectedAutoOutlines.some(outline => !isOutlineWritable(outline))) return '连续创作只能选择已审批章节大纲。'
      return selectedAutoOutlineBlockMessage
    }
    if (!selectedAutoStartOutline || !isOutlineWritable(selectedAutoStartOutline)) return '请选择已审批的起始章节大纲。'
    return selectedAutoOutlineBlockMessage
  }, [autoOutlineMode, outlinesLoading, selectedAutoOutlineBlockMessage, selectedAutoOutlines, selectedAutoStartOutline])

  const handleResourceRequirementRefresh = useCallback(async () => {
    setResourceRequirementRefreshMessage('正在刷新资源需求和 readiness...')
    try {
      await loadChapterOutlines()
      setSingleChapterGateDetail(null)
      setResourceRequirementRefreshMessage('资源需求和 readiness 已刷新。')
      addLog('🔄 已刷新章节资源需求和 readiness')
    } catch (error) {
      console.error('Failed to refresh resource requirements:', error)
      setResourceRequirementRefreshMessage('刷新失败，请稍后重试。')
    }
  }, [addLog, loadChapterOutlines])

  const renderRequirementActionLink = useCallback((requirement: OutlineResourceRequirement) => {
    const recoveryPath = getRequirementRecoveryPath(requirement)
    const projectId = requirement.project_id || currentProject?.id || ''
    return (
      <Link
        key={requirement.id}
        to={`${recoveryPath}${recoveryPath.includes('?') ? '&' : '?'}project_id=${encodeURIComponent(projectId)}`}
        className={`block rounded-lg border px-3 py-2 text-xs transition-colors ${isDark ? 'border-gray-700 bg-gray-900 hover:bg-gray-800 text-gray-200' : 'border-gray-200 bg-white hover:bg-gray-50 text-gray-700'}`}
      >
        <div className="flex items-center justify-between gap-2">
          <span className="font-medium">{formatRequirementSummary(requirement)}</span>
          <ExternalLink className="h-3 w-3 shrink-0" />
        </div>
        <div className={`mt-1 ${isDark ? 'text-gray-400' : 'text-gray-500'}`}>
          {getRequirementRecoveryActionLabel(requirement)} · {getRequirementTypeLabel(getRequirementTargetType(requirement))}
        </div>
      </Link>
    )
  }, [currentProject, isDark])

  const renderResourceRequirementWorkbench = useCallback((outline?: ChapterOutline | null, compact = false, gateDetail?: ChapterReadinessGateDetail | null) => {
    if (!outline) return null
    const gateRequirements = [
      ...(gateDetail?.blocking_requirements || []),
      ...(gateDetail?.advisory_requirements || []),
    ] as OutlineResourceRequirement[]
    const requirements = gateRequirements.length > 0 ? gateRequirements : getOutlineRequirements(outline)
    const unresolvedStatuses = new Set(['pending', 'in_progress'])
    const unresolved = requirements.filter(requirement => unresolvedStatuses.has(requirement.status || 'pending'))
    const blocking = unresolved.filter(requirement => requirement.severity === 'blocking')
    const advisory = unresolved.filter(requirement => requirement.severity === 'advisory')
    if (unresolved.length === 0) return null

    return (
      <div className={`mt-3 rounded-xl border p-3 ${blocking.length > 0 ? (isDark ? 'border-red-800 bg-red-950/20' : 'border-red-200 bg-red-50') : (isDark ? 'border-amber-800 bg-amber-950/20' : 'border-amber-200 bg-amber-50')}`}>
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <div className={`flex items-center gap-2 text-sm font-semibold ${blocking.length > 0 ? (isDark ? 'text-red-200' : 'text-red-800') : (isDark ? 'text-amber-200' : 'text-amber-800')}`}>
              <AlertTriangle className="h-4 w-4" />
              资源补齐闭环
            </div>
            <p className={`mt-1 text-xs ${isDark ? 'text-gray-300' : 'text-gray-600'}`}>
              {blocking.length > 0
                ? '阻塞资源未解决前不会启动章节生成；请创建、绑定、忽略或人工标记解决后刷新 readiness。'
                : '存在建议补齐资源；可先处理，也可在确认风险后继续。'}
            </p>
          </div>
          <Button size="sm" variant="secondary" loading={outlinesLoading} onClick={handleResourceRequirementRefresh}>
            <RefreshCw className="mr-1 h-3 w-3" />刷新 readiness
          </Button>
        </div>

        <div className="mt-3 grid gap-2">
          {(compact ? unresolved.slice(0, 3) : unresolved).map(renderRequirementActionLink)}
        </div>
        {compact && unresolved.length > 3 && (
          <p className={`mt-2 text-xs ${isDark ? 'text-gray-400' : 'text-gray-500'}`}>还有 {unresolved.length - 3} 项资源需求，请打开单章生成面板查看完整列表。</p>
        )}
        <p className={`mt-2 text-xs ${isDark ? 'text-gray-400' : 'text-gray-500'}`}>
          当前未解决：blocking {blocking.length} · advisory {advisory.length}
          {resourceRequirementRefreshMessage ? ` · ${resourceRequirementRefreshMessage}` : ''}
        </p>
      </div>
    )
  }, [getOutlineRequirements, handleResourceRequirementRefresh, isDark, outlinesLoading, renderRequirementActionLink, resourceRequirementRefreshMessage])

  const renderOutlineReadiness = useCallback((outline?: ChapterOutline | null, compact = false) => {
    if (!outline) return null
    const readiness = getOutlineReadiness(outline)
    const requirements = getOutlineRequirements(outline)
    const unresolvedStatuses = new Set(['pending', 'in_progress'])
    const blocking = requirements.filter(requirement => requirement.severity === 'blocking' && unresolvedStatuses.has(requirement.status))
    const advisory = requirements.filter(requirement => requirement.severity === 'advisory' && unresolvedStatuses.has(requirement.status))
    const status = readiness?.readiness_status || (blocking.length > 0 ? 'blocked' : 'not_audited')
    const statusLabel = status === 'ready'
      ? 'ready'
      : status === 'ready_with_warnings'
        ? 'ready with warnings'
        : status === 'blocked'
          ? 'blocked'
          : status === 'stale'
            ? 'stale'
            : 'not audited'
    const statusClass = status === 'ready'
      ? isDark ? 'bg-green-900/30 text-green-300' : 'bg-green-100 text-green-700'
      : status === 'ready_with_warnings'
        ? isDark ? 'bg-yellow-900/30 text-yellow-300' : 'bg-yellow-100 text-yellow-700'
        : status === 'blocked'
          ? isDark ? 'bg-red-900/30 text-red-300' : 'bg-red-100 text-red-700'
          : isDark ? 'bg-gray-800 text-gray-400' : 'bg-gray-100 text-gray-600'

    return (
      <div className={compact ? 'mt-2 space-y-1' : 'mt-3 space-y-2'}>
        <div className="flex flex-wrap items-center gap-2">
          <span className={`rounded px-2 py-0.5 text-xs ${statusClass}`}>readiness: {statusLabel}</span>
          <span className={`text-xs ${isDark ? 'text-gray-500' : 'text-gray-400'}`}>blocking {blocking.length} · advisory {advisory.length}</span>
        </div>
        {blocking.length > 0 && (
          <p className={`text-xs ${isDark ? 'text-red-300' : 'text-red-600'}`}>阻塞资源：{formatRequirementList(blocking, compact ? 2 : 5)}</p>
        )}
        {!compact && advisory.length > 0 && (
          <p className={`text-xs ${isDark ? 'text-yellow-300' : 'text-yellow-700'}`}>建议补齐：{formatRequirementList(advisory, 5)}</p>
        )}
      </div>
    )
  }, [getOutlineReadiness, getOutlineRequirements, isDark])

  const openWriteChapterModal = () => {
    setSingleChapterGateDetail(null)
    void loadChapterOutlines()
    setShowWriteChapterModal(true)
  }

  const openAutoModeModal = () => {
    void loadChapterOutlines()
    setShowAutoModeModal(true)
  }

  useEffect(() => { loadCharacters() }, [currentProject])
  useEffect(() => { loadWorkflows() }, [loadWorkflows])
  useEffect(() => { loadChapterOutlines() }, [loadChapterOutlines, outlineRefreshNonce])
  useEffect(() => { if (sessionId.trim()) loadRuntimePanels() }, [sessionId, runtimeRefreshNonce])

  useEffect(() => {
    if (!currentProject || !selectedWorkflowId || !sessionId.trim()) return
    localStorage.setItem(getDirectorStorageKey(currentProject.id, 'workflow', sessionId), selectedWorkflowId)
  }, [currentProject, selectedWorkflowId, sessionId])

  useEffect(() => {
    if (!currentProject || !sessionId.trim()) return
    const storageKey = getDirectorStorageKey(currentProject.id, 'execution', sessionId)
    if (executionId) {
      localStorage.setItem(storageKey, executionId)
    }
  }, [currentProject, executionId, sessionId])

  useEffect(() => {
    if (!currentProject || savedWorkflows.length === 0 || !selectedWorkflowId || !sessionId.trim()) return

    let active = true

    const hydrateActiveExecution = async () => {
      const normalizedSessionId = sessionId.trim()
      const storedExecutionId = localStorage.getItem(getDirectorStorageKey(currentProject.id, 'execution', normalizedSessionId)) || ''
      const workflowId = selectedWorkflowId || localStorage.getItem(getDirectorStorageKey(currentProject.id, 'workflow', normalizedSessionId)) || undefined

      try {
        let execution: WorkflowExecution | null = null

        try {
          const activeResult = await getActiveWorkflowExecution(currentProject.id, workflowId, normalizedSessionId)
          execution = activeResult.execution
        } catch (error) {
          console.warn('Active workflow execution could not be loaded:', error)
        }

        if (!execution && storedExecutionId) {
          try {
            const storedExecution = await getExecution(storedExecutionId)
            if (getDirectorExecutionSessionId(storedExecution) === normalizedSessionId) {
              execution = storedExecution
            } else {
              localStorage.removeItem(getDirectorStorageKey(currentProject.id, 'execution', normalizedSessionId))
            }
          } catch (error) {
            console.warn('Stored workflow execution could not be loaded:', error)
          }
        }

        if (!active || !execution) return

        if (getDirectorExecutionSessionId(execution) !== normalizedSessionId) return
        if (isTerminalExecutionStatus(execution.status)) {
          localStorage.removeItem(getDirectorStorageKey(currentProject.id, 'execution', normalizedSessionId))
          return
        }

        const workflow = savedWorkflows.find(item => item.id === execution.workflow_id) || selectedWorkflowRef.current
        if (execution.workflow_id && savedWorkflows.some(item => item.id === execution.workflow_id)) {
          if (execution.workflow_id !== selectedWorkflowId) {
            pendingSnapshotRef.current = { execution, workflow }
            setSelectedWorkflowId(execution.workflow_id)
            return
          }
        }
        applyWorkflowExecutionSnapshot(execution, workflow)
        if (isActiveExecutionStatus(execution.status)) {
          addLog(`已恢复当前会话后台执行：${execution.id}`)
        } else if (isTerminalExecutionStatus(execution.status)) {
          addLog(`已恢复当前会话最近执行快照：${execution.id}`)
        }
      } catch (error) {
        if (!active) return
        console.error('Failed to restore workflow execution:', error)
      }
    }

    void hydrateActiveExecution()

    return () => {
      active = false
    }
  }, [addLog, applyWorkflowExecutionSnapshot, currentProject, savedWorkflows, selectedWorkflowId, sessionId])
  useEffect(() => {
    if (!executionId) {
      setIsExecutionStreamReady(false)
      setOperationSummary(null)
      setOperationEvents([])
      return
    }

    let active = true
    let eventSource: EventSource | null = null

    const hydrateExecutionState = async (showErrorLog = false) => {
      try {
        const execution = await getExecution(executionId)
        if (!active) return false
        applyWorkflowExecutionSnapshot(execution, selectedWorkflowRef.current)
        void refreshWorkflowOperations(execution.id)
        return true
      } catch (error) {
        if (!active) return false
        console.error('Failed to hydrate workflow execution:', error)
        setIsExecutionStreamReady(false)
        if (showErrorLog) {
          addLog('❌ 获取工作流执行快照失败')
        }
        return false
      }
    }

    const connectExecutionStream = async () => {
      setIsExecutionStreamReady(false)
      await hydrateExecutionState(false)
      if (!active) return

      eventSource = createWorkflowExecutionEventSource(executionId)

      const handleWorkflowEvent = (event: MessageEvent<string>) => {
        try {
          const payload = JSON.parse(event.data) as WorkflowEventMessage
          applyDirectorEvent(payload)
        } catch (error) {
          console.error('Failed to parse workflow SSE message:', error)
        }
      }

      eventSource.addEventListener('workflow_event', handleWorkflowEvent as EventListener)

      eventSource.onopen = () => {
        if (!active) return
        setIsExecutionStreamReady(true)
        void hydrateExecutionState(false)
      }

      eventSource.onerror = () => {
        if (!active) return
        setIsExecutionStreamReady(false)
      }
    }

    void connectExecutionStream()

    return () => {
      active = false
      setIsExecutionStreamReady(false)
      if (eventSource) {
        eventSource.close()
      }
    }
  }, [addLog, applyDirectorEvent, applyWorkflowExecutionSnapshot, executionId, refreshWorkflowOperations])

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
    const normalizedSessionId = sessionId.trim()
    setExecutionId('')
    localStorage.removeItem(getDirectorStorageKey(currentProject.id, 'execution', normalizedSessionId))
    setPendingUserInput(null)
    setWorkflowUserInput('')
    setIsExecutionStreamReady(false)
    // 重置标志并设置连接状态，触发 WebSocket 连接
    sessionStartAttempted.current = false
    setIsConnected(true)
  }

  const stopSession = () => {
    const sent = send({ type: 'stop_session' })
    if (!sent) {
      addLog('❌ 停止请求发送失败：WebSocket 未连接')
      setIsGenerating(false)
      setExecutionId('')
      if (currentProject) {
        localStorage.removeItem(getDirectorStorageKey(currentProject.id, 'execution', sessionId.trim()))
      }
      setIsExecutionStreamReady(false)
      setIsConnected(false)
      sessionStartAttempted.current = false
      return
    }

    addLog('⏹️ 已发送停止请求，等待后端确认...')
    setIsGenerating(false)
    setIsExecutionStreamReady(false)
  }

  const clearCurrentWorkflowRunView = useCallback(() => {
    resetWorkflowAgents()
    setLogs([])
    setRuntimeState(null)
    setSnapshotTree([])
    setAutoModeChapters([])
    setExecutionId('')
    setOperationSummary(null)
    setOperationEvents([])
    if (currentProject) {
      localStorage.removeItem(getDirectorStorageKey(currentProject.id, 'execution', sessionId.trim()))
    }
    setPendingUserInput(null)
    setWorkflowUserInput('')
    setIsExecutionStreamReady(false)
    setIsConnected(false)
    setIsGenerating(false)
    sessionStartAttempted.current = false
  }, [currentProject, resetWorkflowAgents, sessionId])

  const resetAll = () => {
    void handleRefreshWorkflowRun()
  }

  const handleRefreshWorkflowRun = async () => {
    if (!currentProject) return addLog('请先选择项目')
    if (!selectedWorkflowId) return addLog('请先选择工作流')
    const normalizedSessionId = sessionId.trim()
    if (!normalizedSessionId) return addLog('请先启动或输入导演会话 ID')

    setOperationBusy('reset')
    try {
      const result = await resetDirectorSessionWorkflow({
        projectId: currentProject.id,
        workflowId: selectedWorkflowId,
        directorSessionId: normalizedSessionId,
        reason: 'director_user_reset',
      })
      setDirectorResetToken(result.reset_token)
      clearCurrentWorkflowRunView()
      addLog(`🔄 后端已废弃当前会话工作流${result.previous_execution_id ? `：${result.previous_execution_id}` : ''}，可重新生成单章`)
    } catch (error) {
      addLog(`❌ 重置失败: ${formatApiErrorMessage(error, '重置失败')}`)
    } finally {
      setOperationBusy(null)
    }
  }

  const handleStartAutoMode = () => {
    if (!selectedWorkflowId) return addLog('请先选择工作流')
    if (!currentProject) return addLog('请先选择项目')

    if (autoOutlineMode === 'selected') {
      if (selectedAutoOutlines.length === 0) return addLog('请至少选择一个已审批章节大纲')
      if (selectedAutoOutlines.some(outline => !isOutlineWritable(outline))) return addLog('连续创作只能选择已审批章节大纲')
      const blockedOutline = selectedAutoOutlines.find(outline => getOutlineReadinessBlockMessage(outline))
      if (blockedOutline) return addLog(`⛔ ${getOutlineReadinessBlockMessage(blockedOutline)}`)
    } else {
      if (!selectedAutoStartOutline || !isOutlineWritable(selectedAutoStartOutline)) return addLog('请选择已审批的起始章节大纲')
      const blockMessage = getOutlineReadinessBlockMessage(selectedAutoStartOutline)
      if (blockMessage) return addLog(`⛔ ${blockMessage}`)
    }

    setAutoModeRunning(true)
    setAutoModeChapters([])

    if (autoOutlineMode === 'selected') {
      send({
        type: 'start_auto_mode',
        workflow_id: selectedWorkflowId,
        project_id: currentProject.id,
        outline_mode: 'selected',
        director_session_id: sessionId.trim(),
        outline_ids: selectedAutoOutlines.map(outline => outline.id),
        outline_chapter_numbers: selectedAutoOutlines.map(outline => outline.chapter_number),
        style_reference: autoModeForm.style_reference,
      })
      addLog(`🚀 开始按 ${selectedAutoOutlines.length} 个大纲连续创作`)
    } else {
      const startOutline = selectedAutoStartOutline
      if (!startOutline || !isOutlineWritable(startOutline)) return addLog('请选择已审批的起始章节大纲')
      send({
        type: 'start_auto_mode',
        workflow_id: selectedWorkflowId,
        project_id: currentProject.id,
        outline_mode: 'auto_progression',
        director_session_id: sessionId.trim(),
        auto_advance_outlines: true,
        start_chapter_num: startOutline.chapter_number,
        chapter_count: autoModeForm.chapter_count,
        style_reference: autoModeForm.style_reference,
      })
      addLog(`🚀 从第 ${startOutline.chapter_number} 章大纲开始自动推进`)
    }

    setShowAutoModeModal(false)
  }

  useEffect(() => {
    if (selectedSingleOutline) {
      setChapterForm({ targetWordCount: selectedSingleOutline.target_word_count || 2000 })
    }
  }, [selectedSingleOutline])

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

  const handleSubmitWorkflowUserInput = () => {
    if (!pendingUserInput) return
    if (pendingUserInput.required !== false && !workflowUserInput.trim()) {
      addLog('请填写用户输入内容')
      return
    }
    if (!executionId) {
      addLog('❌ 当前没有可提交输入的工作流执行')
      return
    }

    const sent = send({
      type: 'workflow_user_input',
      execution_id: executionId,
      node_id: pendingUserInput.node_id,
      input_key: pendingUserInput.input_key,
      value: workflowUserInput,
    })
    if (!sent) {
      addLog('❌ 用户输入提交失败：WebSocket 未连接')
      return
    }
    addLog(`📨 已提交用户输入：${pendingUserInput.label || '用户输入'}`)
  }

  const handleWorkflowOperation = async (
    operation: 'pause' | 'resume' | 'cancel' | 'recover',
    action: () => Promise<{ execution?: WorkflowExecution | null; status?: string; message?: string; success?: boolean }>,
  ) => {
    if (!executionId) return addLog('当前没有可操作的工作流执行')
    setOperationBusy(operation)
    try {
      const result = await action()
      if (result.execution) {
        applyWorkflowExecutionSnapshot(result.execution, selectedWorkflowRef.current)
      } else if (result.status) {
        const execution = await getExecution(executionId)
        applyWorkflowExecutionSnapshot(execution, selectedWorkflowRef.current)
      }
      addLog(`✅ ${result.message || '操作已提交'}`)
      void refreshWorkflowOperations(executionId)
    } catch (error) {
      addLog(`❌ 操作失败: ${formatApiErrorMessage(error, '操作失败')}`)
    } finally {
      setOperationBusy(null)
    }
  }

  const handleWriteChapter = async () => {
    if (!selectedWorkflowId) return addLog('请先选择工作流')
    if (!currentProject) return addLog('请先选择项目')
    if (!sessionId.trim()) return addLog('请先启动或输入导演会话 ID')
    if (!selectedSingleOutline || !isOutlineWritable(selectedSingleOutline)) return addLog('请选择已审批章节大纲')
    if (selectedSingleOutlineBlockMessage) return addLog(`⛔ ${selectedSingleOutlineBlockMessage}`)

    const normalizedSessionId = sessionId.trim()
    const targetWordCount = chapterForm.targetWordCount || selectedSingleOutline.target_word_count
    const requestIdParts = ['director', currentProject.id, selectedWorkflowId, normalizedSessionId]
    if (directorResetToken) requestIdParts.push(directorResetToken)
    requestIdParts.push(selectedSingleOutline.id)
    const requestId = requestIdParts.join(':')
    const initialContext: Record<string, any> = {
      director_session_id: normalizedSessionId,
      ...(directorResetToken ? { director_reset_token: directorResetToken } : {}),
      chapter_outline_id: selectedSingleOutline.id,
      chapter_outline: selectedSingleOutline,
      chapter_num: selectedSingleOutline.chapter_number,
      chapter_title: selectedSingleOutline.title,
      target_word_count: targetWordCount,
    }
    if (autoModeForm.style_reference.trim()) {
      initialContext.style_reference = autoModeForm.style_reference.trim()
    }

    setSingleChapterGateDetail(null)
    setOperationBusy('start')
    try {
      const result = await executeWorkflow(selectedWorkflowId, currentProject.id, initialContext, { requestId })
      setExecutionId(result.execution_id)
      localStorage.setItem(getDirectorStorageKey(currentProject.id, 'execution', normalizedSessionId), result.execution_id)
      setIsGenerating(true)
      addLog(`${result.deduplicated ? '♻️ 复用' : '📝 开始'}章节工作流: 第 ${selectedSingleOutline.chapter_number} 章《${selectedSingleOutline.title}》`)
      void refreshWorkflowOperations(result.execution_id)
      setSelectedSingleOutlineId('')
      setChapterForm({ targetWordCount: 2000 })
      setShowWriteChapterModal(false)
    } catch (error) {
      const detail = extractChapterReadinessGateDetail(error)
      if (detail) {
        setSingleChapterGateDetail(detail)
        setOutlineRefreshNonce(value => value + 1)
        addLog(`⛔ ${formatChapterReadinessGateMessage(
          detail,
          requirements => formatRequirementList(requirements as OutlineResourceRequirement[], 5),
        )}`)
      } else {
        addLog(`❌ 章节工作流启动失败: ${formatApiErrorMessage(error, '启动失败')}`)
      }
      setIsGenerating(false)
    } finally {
      setOperationBusy(null)
    }
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
                    onClick={openWriteChapterModal}
                    disabled={!selectedWorkflowId || !isGenerating || wsStatus !== 'connected' || autoModeRunning}
                    className="flex items-center gap-2 px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white text-sm font-medium rounded-lg transition-colors disabled:opacity-50"
                    title={!selectedWorkflowId ? '请先选择工作流' : ''}
                  >
                    <FileText size={16} /> 生成单章
                  </button>
                  <button
                    onClick={openAutoModeModal}
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

        {pendingUserInput && (
          <Card className={`border-2 ${isDark ? 'border-amber-800 bg-amber-900/20' : 'border-amber-300 bg-amber-50'}`}>
            <div className="p-4 space-y-3">
              <div className="flex items-start gap-3">
                <div className={`p-2 rounded-lg ${isDark ? 'bg-amber-800' : 'bg-amber-100'}`}>
                  <Keyboard size={20} className={isDark ? 'text-amber-200' : 'text-amber-700'} />
                </div>
                <div className="min-w-0 flex-1">
                  <h3 className={`font-semibold ${isDark ? 'text-amber-100' : 'text-amber-800'}`}>
                    工作流等待用户输入：{pendingUserInput.label || '用户输入'}
                  </h3>
                  <p className={`mt-1 text-sm ${isDark ? 'text-amber-200/80' : 'text-amber-700'}`}>
                    {pendingUserInput.prompt || pendingUserInput.description || '请补充信息后继续工作流。'}
                  </p>
                  {pendingUserInput.input_key && (
                    <p className={`mt-1 text-xs ${isDark ? 'text-amber-300/70' : 'text-amber-600'}`}>
                      写入上下文字段：{pendingUserInput.input_key}
                    </p>
                  )}
                </div>
              </div>
              <TextArea
                label="输入内容"
                value={workflowUserInput}
                onChange={(e) => setWorkflowUserInput(e.target.value)}
                placeholder={pendingUserInput.placeholder || '请输入补充要求或修订意见...'}
                rows={4}
              />
              <div className="flex justify-end gap-2">
                <Button
                  variant="secondary"
                  onClick={() => setWorkflowUserInput(String(pendingUserInput.default_value || ''))}
                >
                  重置输入
                </Button>
                <Button
                  onClick={handleSubmitWorkflowUserInput}
                  disabled={pendingUserInput.required !== false && !workflowUserInput.trim()}
                >
                  <Send size={16} className="mr-1" /> 提交并继续
                </Button>
              </div>
            </div>
          </Card>
        )}

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
                        projectId={currentProject.id}
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

            {executionId && (
              <Card>
                <div className="p-4 space-y-3">
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <h3 className={`text-sm font-semibold ${isDark ? 'text-gray-300' : 'text-gray-700'}`}>工作流运行</h3>
                      <p className={`text-xs mt-1 ${isDark ? 'text-gray-500' : 'text-gray-400'}`}>
                        {operationSummary?.status || '同步中'} · {isExecutionStreamReady ? 'SSE 已连接' : 'SSE 连接中'}
                      </p>
                    </div>
                    <div className="flex items-center gap-1">
                      <button
                        onClick={() => void refreshWorkflowOperations(executionId)}
                        className={`p-2 rounded-lg ${isDark ? 'hover:bg-gray-800 text-gray-400' : 'hover:bg-gray-100 text-gray-500'}`}
                        title="刷新运行状态"
                      >
                        <RefreshCw size={15} />
                      </button>
                      <button
                        onClick={() => void handleRefreshWorkflowRun()}
                        disabled={operationBusy !== null}
                        className={`p-2 rounded-lg disabled:opacity-50 ${isDark ? 'hover:bg-gray-800 text-gray-400' : 'hover:bg-gray-100 text-gray-500'}`}
                        title="后端废弃当前运行并允许重新生成"
                      >
                        <RotateCcw size={15} />
                      </button>
                    </div>
                  </div>
                  {operationSummary?.attention?.[0] && (
                    <p className={`text-xs rounded-lg px-3 py-2 ${isDark ? 'bg-amber-950/30 text-amber-300' : 'bg-amber-50 text-amber-700'}`}>
                      {operationSummary.attention[0].message}
                    </p>
                  )}
                  <div className="grid grid-cols-2 gap-2">
                    {[
                      { key: 'pause' as const, icon: Pause, label: '暂停', run: () => pauseExecution(executionId) },
                      { key: 'resume' as const, icon: Play, label: '恢复', run: () => resumeExecution(executionId) },
                      { key: 'cancel' as const, icon: Square, label: '取消', run: () => cancelExecution(executionId) },
                      { key: 'recover' as const, icon: RotateCcw, label: '恢复失败点', run: () => recoverExecution(executionId, { reason: 'Director run control recovery' }) },
                    ].map(({ key, icon: Icon, label, run }) => {
                      const capability = operationSummary?.capabilities?.[key]
                      const disabled = operationBusy !== null || !capability?.allowed
                      return (
                        <button
                          key={key}
                          onClick={() => void handleWorkflowOperation(key, run)}
                          disabled={disabled}
                          title={capability?.reason || label}
                          className={`flex items-center justify-center gap-2 px-3 py-2 rounded-lg border text-xs font-medium transition-colors disabled:opacity-50 disabled:cursor-not-allowed ${
                            isDark ? 'bg-gray-800 hover:bg-gray-700 text-gray-300 border-gray-700' : 'bg-white hover:bg-gray-50 text-gray-700 border-gray-200'
                          }`}
                        >
                          <Icon size={14} /> {operationBusy === key ? '处理中' : label}
                        </button>
                      )
                    })}
                  </div>
                  {operationSummary?.capabilities?.recover?.reason && !operationSummary.capabilities.recover.allowed && (
                    <p className={`text-xs ${isDark ? 'text-gray-500' : 'text-gray-400'}`}>{operationSummary.capabilities.recover.reason}</p>
                  )}
                  {stateHandoffSummary && (
                    <div className={`rounded-xl border px-3 py-2 text-xs ${isDark ? 'border-cyan-900/60 bg-cyan-950/20 text-cyan-200' : 'border-cyan-200 bg-cyan-50 text-cyan-800'}`}>
                      <div className="flex items-center justify-between gap-2">
                        <span className="font-semibold">状态交接</span>
                        <span className={isDark ? 'text-cyan-300/80' : 'text-cyan-700/80'}>
                          前文 {stateHandoffSummary.prior} · 确认 {stateHandoffSummary.confirmed}
                        </span>
                      </div>
                      <div className="mt-1 flex flex-wrap gap-1.5">
                        <span>已提案 {stateHandoffSummary.proposed}</span>
                        <span>已应用 {stateHandoffSummary.applied}</span>
                        <span>待确认 {stateHandoffSummary.pending}</span>
                        <span className={stateHandoffSummary.errors > 0 ? 'text-red-400' : undefined}>错误 {stateHandoffSummary.errors}</span>
                      </div>
                    </div>
                  )}
                  <a
                    href={getFailureDiagnosticsHref(currentProject.id, executionId)}
                    className={`inline-flex items-center gap-1 text-xs font-medium ${isDark ? 'text-blue-300 hover:text-blue-200' : 'text-blue-600 hover:text-blue-700'}`}
                  >
                    打开工作流诊断 <ExternalLink size={12} />
                  </a>
                  {operationEvents.length > 0 && (
                    <div className={`space-y-1 pt-2 border-t ${isDark ? 'border-gray-800' : 'border-gray-100'}`}>
                      {operationEvents.slice(0, 3).map((event, index) => (
                        <div key={`${event.sequence_no || index}-${event.event_type}`} className="flex items-start gap-2 text-xs">
                          <Activity size={12} className={event.severity === 'error' ? 'text-red-400 mt-0.5' : 'text-gray-400 mt-0.5'} />
                          <span className={isDark ? 'text-gray-400' : 'text-gray-500'}>{event.summary}</span>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              </Card>
            )}

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
              连续创作将按已经生成好的章节大纲执行工作流。可以手动选择多个大纲，也可以从某一章开始自动推进已有大纲。
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

          <div className="grid grid-cols-2 gap-2">
            {[
              { key: 'selected' as AutoOutlineMode, label: '手动选择大纲序列' },
              { key: 'auto_progression' as AutoOutlineMode, label: '从起始大纲自动推进' },
            ].map(option => (
              <button
                key={option.key}
                type="button"
                onClick={() => setAutoOutlineMode(option.key)}
                className={`rounded-lg border px-3 py-2 text-sm font-medium transition-colors ${
                  autoOutlineMode === option.key
                    ? isDark ? 'border-purple-500 bg-purple-900/40 text-purple-200' : 'border-purple-500 bg-purple-50 text-purple-700'
                    : isDark ? 'border-gray-700 bg-gray-800 text-gray-300 hover:bg-gray-700' : 'border-gray-200 bg-white text-gray-600 hover:bg-gray-50'
                }`}
              >
                {option.label}
              </button>
            ))}
          </div>

          <div className={`rounded-lg border ${isDark ? 'border-gray-700 bg-gray-900/40' : 'border-gray-200 bg-gray-50'}`}>
            <div className="flex items-center justify-between border-b px-3 py-2 text-sm font-medium border-inherit">
              <span className={isDark ? 'text-gray-200' : 'text-gray-700'}>章节大纲</span>
              <button
                type="button"
                onClick={() => void loadChapterOutlines()}
                className={`text-xs ${isDark ? 'text-blue-300 hover:text-blue-200' : 'text-blue-600 hover:text-blue-700'}`}
              >
                {outlinesLoading ? '加载中...' : '刷新'}
              </button>
            </div>

            {chapterOutlines.length === 0 ? (
              <div className={`p-4 text-sm ${isDark ? 'text-gray-500' : 'text-gray-400'}`}>
                暂无已生成的章节大纲，请先到“大纲”页面生成并保存章节大纲。
              </div>
            ) : autoOutlineMode === 'selected' ? (
              <div className="max-h-72 overflow-y-auto p-3 space-y-2">
                {chapterOutlines.map(outline => {
                  const writable = isOutlineWritable(outline)
                  const status = OUTLINE_STATUS_CONFIG[outline.status]
                  const checked = selectedAutoOutlineIds.includes(outline.id)
                  return (
                    <label
                      key={outline.id}
                      className={`flex gap-3 rounded-lg border p-3 text-sm transition-colors ${
                        writable
                          ? isDark ? 'cursor-pointer border-gray-700 bg-gray-800 hover:border-purple-600' : 'cursor-pointer border-gray-200 bg-white hover:border-purple-300'
                          : isDark ? 'cursor-not-allowed border-gray-800 bg-gray-900 opacity-60' : 'cursor-not-allowed border-gray-100 bg-gray-100 opacity-60'
                      }`}
                    >
                      <input
                        type="checkbox"
                        checked={checked}
                        disabled={!writable}
                        onChange={() => toggleAutoOutline(outline.id)}
                        className="mt-1"
                      />
                      <div className="min-w-0 flex-1">
                        <div className="flex items-center gap-2">
                          <span className={`font-medium ${isDark ? 'text-white' : 'text-gray-800'}`}>第 {outline.chapter_number} 章：{outline.title}</span>
                          <span className={`rounded px-2 py-0.5 text-xs ${status.className}`}>{status.label}</span>
                        </div>
                        <p className={`mt-1 line-clamp-2 ${isDark ? 'text-gray-400' : 'text-gray-500'}`}>{outline.summary || '暂无摘要'}</p>
                        <p className={`mt-1 text-xs ${isDark ? 'text-gray-500' : 'text-gray-400'}`}>{outline.scenes.length} 个场景 · 目标 {outline.target_word_count} 字</p>
                        {renderOutlineReadiness(outline, true)}
                        {checked && renderResourceRequirementWorkbench(outline, true)}
                      </div>
                    </label>
                  )
                })}
              </div>
            ) : (
              <div className="p-3 space-y-3">
                <div>
                  <label className={`block text-sm font-medium mb-1 ${isDark ? 'text-gray-300' : 'text-gray-700'}`}>
                    起始大纲
                  </label>
                  <select
                    value={autoStartOutlineId}
                    onChange={(e) => setAutoStartOutlineId(e.target.value)}
                    className={`w-full px-3 py-2 rounded-lg border text-sm ${isDark ? 'bg-gray-800 border-gray-700 text-white' : 'bg-white border-gray-200 text-gray-800'}`}
                  >
                    <option value="">选择起始章节大纲...</option>
                    {chapterOutlines.map(outline => (
                      <option key={outline.id} value={outline.id} disabled={!isOutlineWritable(outline)}>
                        第 {outline.chapter_number} 章：{outline.title}（{OUTLINE_STATUS_CONFIG[outline.status].label}）
                      </option>
                    ))}
                  </select>
                  {selectedAutoStartOutline && renderOutlineReadiness(selectedAutoStartOutline)}
                  {selectedAutoStartOutline && renderResourceRequirementWorkbench(selectedAutoStartOutline)}
                </div>
                <div>
                  <label className={`block text-sm font-medium mb-1 ${isDark ? 'text-gray-300' : 'text-gray-700'}`}>
                    最多推进章节数
                  </label>
                  <input
                    type="number"
                    value={autoModeForm.chapter_count}
                    onChange={(e) => setAutoModeForm({ ...autoModeForm, chapter_count: parseInt(e.target.value) || 1 })}
                    className={`w-full px-3 py-2 rounded-lg border ${isDark ? 'bg-gray-800 border-gray-700 text-white' : 'border-gray-200'}`}
                    min={1}
                    max={20}
                  />
                  <p className={`mt-1 text-xs ${isDark ? 'text-gray-500' : 'text-gray-400'}`}>
                    后端只会推进当前项目中已经存在且可写的章节大纲。
                  </p>
                </div>
              </div>
            )}
          </div>

          {selectedAutoOutlineBlockMessage && (
            <div className={`rounded-lg border px-3 py-2 text-xs ${isDark ? 'border-red-800 bg-red-950/30 text-red-200' : 'border-red-200 bg-red-50 text-red-700'}`}>
              {selectedAutoOutlineBlockMessage}
            </div>
          )}

          <TextArea
            label="风格参考（可选）"
            value={autoModeForm.style_reference}
            onChange={(e) => setAutoModeForm({ ...autoModeForm, style_reference: e.target.value })}
            placeholder="粘贴一段希望模仿风格的文字..."
          />

          <div className="flex justify-end gap-3 pt-2">
            <Button variant="secondary" onClick={() => setShowAutoModeModal(false)}>取消</Button>
            <Button
              onClick={handleStartAutoMode}
              disabled={!!autoModeStartDisabledReason}
              title={autoModeStartDisabledReason || undefined}
            >
              <Play size={16} className="mr-1" /> 开始
            </Button>
          </div>
        </div>
      </Modal>

      <Modal isOpen={showWriteChapterModal} onClose={() => setShowWriteChapterModal(false)} title="生成单章" size="lg">
        <div className="space-y-4">
          <div className={`p-4 rounded-lg ${isDark ? 'bg-green-900/30' : 'bg-green-50'}`}>
            <p className={`text-sm ${isDark ? 'text-green-300' : 'text-green-700'}`}>
              选择一个已经生成好的章节大纲，工作流会使用该大纲的章节号、摘要、目标和场景信息生成正文。
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

          <div>
            <div className="mb-2 flex items-center justify-between">
              <label className={`block text-sm font-medium ${isDark ? 'text-gray-300' : 'text-gray-700'}`}>
                章节大纲 *
              </label>
              <button
                type="button"
                onClick={() => void loadChapterOutlines()}
                className={`text-xs ${isDark ? 'text-blue-300 hover:text-blue-200' : 'text-blue-600 hover:text-blue-700'}`}
              >
                {outlinesLoading ? '加载中...' : '刷新'}
              </button>
            </div>
            <select
              value={selectedSingleOutlineId}
              onChange={(e) => setSelectedSingleOutlineId(e.target.value)}
              className={`w-full px-3 py-2 rounded-lg border text-sm ${isDark ? 'bg-gray-800 border-gray-700 text-white' : 'bg-white border-gray-200 text-gray-800'}`}
            >
              <option value="">选择章节大纲...</option>
              {chapterOutlines.map(outline => (
                <option key={outline.id} value={outline.id} disabled={!isOutlineWritable(outline)}>
                  第 {outline.chapter_number} 章：{outline.title}（{OUTLINE_STATUS_CONFIG[outline.status].label}）
                </option>
              ))}
            </select>
            {chapterOutlines.length === 0 && (
              <p className={`mt-2 text-xs ${isDark ? 'text-gray-500' : 'text-gray-400'}`}>
                暂无已生成的章节大纲，请先到“大纲”页面生成并保存章节大纲。
              </p>
            )}
          </div>

          {selectedSingleOutline && (
            <div className={`rounded-lg border p-4 ${isDark ? 'border-gray-700 bg-gray-900/50' : 'border-gray-200 bg-gray-50'}`}>
              <div className="mb-2 flex items-center gap-2">
                <h4 className={`font-semibold ${isDark ? 'text-white' : 'text-gray-800'}`}>
                  第 {selectedSingleOutline.chapter_number} 章：{selectedSingleOutline.title}
                </h4>
                <span className={`rounded px-2 py-0.5 text-xs ${OUTLINE_STATUS_CONFIG[selectedSingleOutline.status].className}`}>
                  {OUTLINE_STATUS_CONFIG[selectedSingleOutline.status].label}
                </span>
              </div>
              <p className={`text-sm ${isDark ? 'text-gray-300' : 'text-gray-600'}`}>
                {selectedSingleOutline.summary || '暂无摘要'}
              </p>
              {selectedSingleOutline.chapter_goals.length > 0 && (
                <div className="mt-3">
                  <p className={`mb-1 text-xs font-medium ${isDark ? 'text-gray-400' : 'text-gray-500'}`}>章节目标</p>
                  <ul className={`list-disc space-y-1 pl-5 text-sm ${isDark ? 'text-gray-300' : 'text-gray-600'}`}>
                    {selectedSingleOutline.chapter_goals.map((goal, index) => <li key={index}>{goal}</li>)}
                  </ul>
                </div>
              )}
              <div className={`mt-3 flex gap-4 text-xs ${isDark ? 'text-gray-500' : 'text-gray-400'}`}>
                <span>{selectedSingleOutline.scenes.length} 个场景</span>
                <span>目标 {selectedSingleOutline.target_word_count} 字</span>
              </div>
              {renderOutlineReadiness(selectedSingleOutline)}
              {renderResourceRequirementWorkbench(selectedSingleOutline)}
            </div>
          )}

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
              默认使用所选大纲的目标字数，可在生成前临时覆盖。
            </p>
          </div>

          {selectedSingleOutlineBlockMessage && (
            <div className={`rounded-lg border px-3 py-2 text-xs ${isDark ? 'border-red-800 bg-red-950/30 text-red-200' : 'border-red-200 bg-red-50 text-red-700'}`}>
              {selectedSingleOutlineBlockMessage}
            </div>
          )}

          {singleChapterGateDetail && selectedSingleOutline && (
            <div className={`rounded-xl border p-3 text-xs ${isDark ? 'border-red-800 bg-red-950/30 text-red-100' : 'border-red-200 bg-red-50 text-red-700'}`}>
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div>
                  <p className="font-semibold">后端 readiness gate 已拒绝本次启动</p>
                  <p className="mt-1">
                    {formatChapterReadinessGateMessage(
                      singleChapterGateDetail,
                      requirements => formatRequirementList(requirements as OutlineResourceRequirement[], 5),
                    )}
                  </p>
                </div>
                <Button size="sm" variant="secondary" loading={outlinesLoading} onClick={handleResourceRequirementRefresh}>
                  <RefreshCw className="mr-1 h-3 w-3" />刷新后重试
                </Button>
              </div>
              {renderResourceRequirementWorkbench(selectedSingleOutline, false, singleChapterGateDetail)}
            </div>
          )}

          <div className="flex justify-end gap-3 pt-2">
            <Button variant="secondary" onClick={() => setShowWriteChapterModal(false)}>取消</Button>
            <Button
              onClick={handleWriteChapter}
              disabled={outlinesLoading || !isOutlineWritable(selectedSingleOutline) || !!selectedSingleOutlineBlockMessage}
              title={selectedSingleOutlineBlockMessage || undefined}
            >
              <FileText size={16} className="mr-1" /> 生成章节
            </Button>
          </div>
        </div>
      </Modal>
    </PageLayout>
  )
}
