import { useEffect, useMemo, useState, useCallback } from 'react'
import { Card } from '@/components/ui'
import PageLayout from '@/components/PageLayout'
import ReactFlow, {
  Background,
  Controls,
  MiniMap,
  addEdge,
  applyNodeChanges,
  applyEdgeChanges,
  type Node,
  type Edge,
  type OnNodesChange,
  type OnEdgesChange,
  type Connection,
  type NodeTypes,
  Panel,
  Handle,
  Position,
} from 'reactflow'
import 'reactflow/dist/style.css'
import { getVisualizationData } from '@/api/visualization'
import { getWorlds, getRegions, type Region, type World } from '@/api/worlds'
import { getCharacters, type Character } from '@/api/characters'
import { getChapters } from '@/api/chapters'
import {
  getOutlines,
  getOutlineResourceRequirements,
  getChapterResourceReadiness,
  type ChapterOutline,
  type OutlineResourceRequirement,
  type ChapterResourceReadiness,
} from '@/api/outlines'
import {
  getWorkflows,
  createWorkflow,
  updateWorkflow,
  deleteWorkflow,
  executeWorkflow,
  extractChapterReadinessGateDetail,
  formatChapterReadinessGateMessage,
  formatApiErrorMessage,
  getActiveWorkflowExecution,
  getExecutions,
  getReadinessStatusLabel,
  isReadinessBlockedStatus,
  getExecution,
  getExecutionOperationEvents,
  inspectExecutionStaleness,
  resolveStaleExecution,
  createRuntimeFixture,
  cleanupRuntimeFixture,
  pauseExecution,
  resumeExecution,
  recoverExecution,
  getFailedNodeDiagnosis,
  remediateAndRecoverExecution,
  cancelExecution,
  confirmDiscussion,
  type WorkflowDefinition,
  type WorkflowExecution,
  type WorkflowNode as WfNode,
  type WorkflowEdge as WfEdge,
  type NodeInputConfig,
  type NodeOutputConfig,
  type WorkflowSseState,
  type WorkflowStatus,
  type WorkflowExecutionHistoryRow,
  type WorkflowRecoveryHistoryEntry,
  type WorkflowFailureDiagnosis,
  type WorkflowOperationSummary,
  type WorkflowOperationEvent,
  type WorkflowStaleInspection,
} from '@/api/workflows'
import { getAgentTypeOptions, getWorkflowNodeTypes, type NodeTypeInfo, type WorkflowNodeTypes } from '@/api/nodeTypes'
import WorkflowMonitor from '@/components/workflow/WorkflowMonitor'
import WorkflowTrace from '@/components/workflow/WorkflowTrace'
import { Network, Users, GitBranch, Play, Save, Trash2, Plus, Loader2, Pause, Square, RotateCcw, Orbit, Map, FileClock, ShieldAlert } from 'lucide-react'
import { useTheme } from '@/contexts/ThemeContext'
import {
  formatRequirementList,
  formatRequirementSummary,
  getRequirementRecoveryActionLabel,
  getRequirementRecoveryPath,
} from '@/utils/resourceRequirementDisplay'
import { useProject } from '@/contexts/ProjectContext'
import WorkflowHelp from '@/components/workflow/WorkflowHelp'
import WorldMap3D from '@/components/visualizer/WorldMap3D'
import CharacterRelationshipGraph3D from '@/components/visualizer/CharacterRelationshipGraph3D'

function getExecutionNodeChrome(data: VisualNodeData, baseClasses: string): string {
  const status = data.status || 'pending'
  if (status === 'running') return `${baseClasses} border-blue-500 bg-blue-50 shadow-blue-200 shadow-md animate-pulse`
  if (status === 'completed') return `${baseClasses} border-emerald-500 bg-emerald-50 shadow-emerald-100 shadow-sm`
  if (status === 'failed') return `${baseClasses} border-red-500 bg-red-50 shadow-red-100 shadow-md`
  return baseClasses
}

function NodeExecutionBadge({ data }: { data: VisualNodeData }) {
  const status = data.status || 'pending'
  if (status === 'pending') return null
  return (
    <div
      className={`mt-1 rounded px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide ${
        status === 'running'
          ? 'bg-blue-600 text-white'
          : status === 'completed'
            ? 'bg-emerald-600 text-white'
            : status === 'failed'
              ? 'bg-red-600 text-white'
              : 'bg-gray-600 text-white'
      }`}
      title={data.error || (data.duration_ms ? `${data.duration_ms}ms` : status)}
    >
      {status === 'running' ? '运行中' : status === 'completed' ? '完成' : status === 'failed' ? '失败' : status}
    </div>
  )
}

function AgentNode({ data }: { data: VisualNodeData }) {
  const { theme } = useTheme()
  const isDark = theme === 'dark'
  const base = isDark ? 'bg-gray-700 border-gray-600' : 'bg-gray-100 border-gray-300'

  return (
    <div className={getExecutionNodeChrome(data, `px-4 py-3 rounded-lg border-2 min-w-[120px] ${base}`)} title={data.error}>
      <Handle type="target" position={Position.Top} className="!bg-gray-400 !w-3 !h-3" />
      <div className="font-medium text-sm">{data.label}</div>
      {data.agent_type && <div className="text-xs opacity-70">{data.agent_type}</div>}
      <NodeExecutionBadge data={data} />
      <Handle type="source" position={Position.Bottom} className="!bg-gray-400 !w-3 !h-3" />
    </div>
  )
}

function ConditionNode({ data }: { data: VisualNodeData }) {
  return (
    <div className={getExecutionNodeChrome(data, "px-4 py-3 rounded-lg border-2 border-orange-400 bg-orange-50 min-w-[150px]")} title={data.error}>
      <Handle type="target" position={Position.Top} className="!bg-orange-400 !w-3 !h-3" />
      <div className="font-medium text-sm">条件分支</div>
      <div className="text-xs opacity-70">{data.label || '评估结果'}</div>
      <div className="flex justify-between text-xs mt-1 px-1">
        <span className="text-green-600">通过</span>
        <span className="text-red-600">重试</span>
      </div>
      <NodeExecutionBadge data={data} />
      <Handle type="source" position={Position.Left} id="pass" className="!bg-green-500 !w-3 !h-3" />
      <Handle type="source" position={Position.Right} id="retry" className="!bg-red-500 !w-3 !h-3" />
    </div>
  )
}

function ParallelNode({ data }: { data: VisualNodeData }) {
  return (
    <div className={getExecutionNodeChrome(data, "px-4 py-3 rounded-lg border-2 border-purple-400 bg-purple-50 min-w-[120px]")} title={data.error}>
      <Handle type="target" position={Position.Top} className="!bg-purple-400 !w-3 !h-3" />
      <div className="font-medium text-sm">并行执行</div>
      <div className="text-xs opacity-70">{data.label || '同时执行多个分支'}</div>
      <NodeExecutionBadge data={data} />
      <Handle type="source" position={Position.Bottom} className="!bg-purple-400 !w-3 !h-3" />
    </div>
  )
}

function ScenePerformanceNode({ data }: { data: VisualNodeData }) {
  return (
    <div className={getExecutionNodeChrome(data, "px-4 py-3 rounded-lg border-2 border-rose-400 bg-rose-50 min-w-[150px]")} title={data.error}>
      <Handle type="target" position={Position.Top} className="!bg-rose-400 !w-3 !h-3" />
      <div className="font-medium text-sm">场景演绎</div>
      <div className="text-xs opacity-70">{data.label || '多角色同台表演'}</div>
      <div className="text-xs text-rose-600 mt-1">自动协调角色 Agent</div>
      <NodeExecutionBadge data={data} />
      <Handle type="source" position={Position.Bottom} className="!bg-rose-400 !w-3 !h-3" />
    </div>
  )
}

function GroupDiscussionNode({ data }: { data: VisualNodeData }) {
  return (
    <div className={getExecutionNodeChrome(data, "px-4 py-3 rounded-lg border-2 border-indigo-400 bg-indigo-50 min-w-[150px]")} title={data.error}>
      <Handle type="target" position={Position.Top} className="!bg-indigo-400 !w-3 !h-3" />
      <div className="font-medium text-sm">集体讨论</div>
      <div className="text-xs opacity-70">{data.label || '多 Agent 讨论'}</div>
      <NodeExecutionBadge data={data} />
      <Handle type="source" position={Position.Bottom} className="!bg-indigo-400 !w-3 !h-3" />
    </div>
  )
}

function StartNode({ data }: { data: VisualNodeData }) {
  return (
    <div className={getExecutionNodeChrome(data, "px-4 py-3 rounded-lg border-2 border-green-500 bg-green-50 min-w-[100px]")} title={data.error}>
      <Handle type="target" position={Position.Top} id="loop" className="!bg-green-400 !w-3 !h-3" />
      <div className="font-medium text-sm text-center">{data.label || '开始'}</div>
      <NodeExecutionBadge data={data} />
      <Handle type="source" position={Position.Bottom} className="!bg-green-500 !w-3 !h-3" />
    </div>
  )
}

function EndNode({ data }: { data: VisualNodeData }) {
  return (
    <div className={getExecutionNodeChrome(data, "px-4 py-3 rounded-lg border-2 border-red-500 bg-red-50 min-w-[100px]")} title={data.error}>
      <Handle type="target" position={Position.Top} className="!bg-red-400 !w-3 !h-3" />
      <div className="font-medium text-sm text-center">{data.label || '结束'}</div>
      <NodeExecutionBadge data={data} />
    </div>
  )
}

function InputNode({ data }: { data: VisualNodeData }) {
  return (
    <div className={getExecutionNodeChrome(data, "px-4 py-3 rounded-lg border-2 border-blue-400 bg-blue-50 min-w-[120px]")} title={data.error}>
      <Handle type="target" position={Position.Top} className="!bg-blue-400 !w-3 !h-3" />
      <div className="font-medium text-sm">用户输入</div>
      <div className="text-xs opacity-70">{data.label || '等待用户输入'}</div>
      <NodeExecutionBadge data={data} />
      <Handle type="source" position={Position.Bottom} className="!bg-blue-400 !w-3 !h-3" />
    </div>
  )
}

const nodeTypes: NodeTypes = {
  agent: AgentNode,
  condition: ConditionNode,
  parallel: ParallelNode,
  scene_performance: ScenePerformanceNode,
  group_discussion: GroupDiscussionNode,
  start: StartNode,
  end: EndNode,
  input: InputNode,
}

type TabType = 'workflow' | 'plots' | 'snapshots' | 'world3d' | 'relationships3d'

type VisualNodeData = {
  label?: string
  agent_type?: string
  config?: Record<string, any>
  description?: string
  inputs?: NodeInputConfig[]
  outputs?: NodeOutputConfig[]
  status?: string
  error?: string
  duration_ms?: number
}

type WorkflowOrigin = 'project' | 'global_template'

const generateId = () => `node_${Date.now()}_${Math.random().toString(36).slice(2, 9)}`
const isActiveExecutionStatus = (status?: string) => status === 'pending' || status === 'running' || status === 'paused'
const executionStorageKey = (projectId: string, workflowId: string) => `workflowExecution:${projectId}:${workflowId}`
const shortExecutionId = (id: string) => id.length > 12 ? `${id.slice(0, 8)}…${id.slice(-4)}` : id
const formatExecutionDate = (value?: string | null) => value ? new Date(value).toLocaleString('zh-CN') : '-'
const formatExecutionDuration = (ms?: number | null) => {
  if (!ms) return '-'
  if (ms < 1000) return `${ms}ms`
  if (ms < 60000) return `${(ms / 1000).toFixed(1)}s`
  return `${(ms / 60000).toFixed(1)}m`
}

const operationEventKey = (event: WorkflowOperationEvent, index: number) => `${event.sequence_no ?? 'no-seq'}:${event.event_type}:${event.created_at || index}`
const operationEventCategory = (event: WorkflowOperationEvent) => {
  if (event.event_type === 'workflow_node_remediated') return 'remediation'
  if (event.event_type === 'workflow_recovery_started') return 'recovery'
  if (event.event_type === 'workflow_execution_stale') return 'stale'
  if (event.event_type === 'node_failed' || event.event_type === 'workflow_failed' || event.severity === 'error') return 'failure'
  if (event.event_type.startsWith('node_')) return 'node'
  return 'lifecycle'
}
const operationEventMatchesFilter = (event: WorkflowOperationEvent, filter: 'all' | 'lifecycle' | 'node' | 'failure' | 'recovery' | 'remediation' | 'stale') => {
  if (filter === 'all') return true
  return operationEventCategory(event) === filter
}
const formatEventPayloadValue = (value: any): string => {
  if (value === null || value === undefined || value === '') return '-'
  if (typeof value === 'string' || typeof value === 'number' || typeof value === 'boolean') return String(value)
  try {
    return JSON.stringify(value, null, 2)
  } catch {
    return String(value)
  }
}

const standardAllNodesDefinition = {
  name: '全内置节点标准流程',
  description: '包含全部内置节点的标准创作工作流，突出章节大纲驱动与逐节点输入输出观察。',
  nodes: [
    {
      id: 'start',
      node_type: 'start',
      label: '开始',
      description: '加载项目基础上下文',
      config: {},
      position: { x: 520, y: 20 },
      outputs: [
        { name: 'project_info', target: 'context', key: 'project_info', save_to_db: false },
        { name: 'world_info', target: 'context', key: 'world_info', save_to_db: false },
        { name: 'characters', target: 'context', key: 'characters', save_to_db: false },
        { name: 'lore_entries', target: 'context', key: 'lore_entries', save_to_db: false },
        { name: 'existing_hooks', target: 'context', key: 'existing_hooks', save_to_db: false },
        { name: 'events', target: 'context', key: 'events', save_to_db: false },
        { name: 'locations', target: 'context', key: 'locations', save_to_db: false },
        { name: 'previous_chapters', target: 'context', key: 'previous_chapters', save_to_db: false },
      ],
    },
    {
      id: 'plot_outline',
      node_type: 'agent',
      agent_type: 'plot_outline',
      label: '章节大纲 Agent',
      description: '优先输出已准备的章节大纲，缺失时兜底生成',
      config: {},
      position: { x: 520, y: 120 },
      inputs: [
        { name: 'chapter_num', source: 'context', key: 'chapter_num', required: true, default: 1 },
        { name: 'project_info', source: 'context', key: 'project_info', required: false },
        { name: 'world_info', source: 'context', key: 'world_info', required: false },
        { name: 'lore_entries', source: 'context', key: 'lore_entries', required: false },
        { name: 'characters', source: 'context', key: 'characters', required: false },
        { name: 'existing_hooks', source: 'context', key: 'existing_hooks', required: false },
        { name: 'previous_chapters', source: 'context', key: 'previous_chapters', required: false },
      ],
      outputs: [
        { name: 'chapter_number', target: 'context', key: 'chapter_number', save_to_db: false },
        { name: 'chapter_title', target: 'context', key: 'chapter_title', save_to_db: false },
        { name: 'chapter_outline', target: 'context', key: 'chapter_outline', save_to_db: false },
        { name: 'chapter_summary', target: 'context', key: 'chapter_summary', save_to_db: false },
        { name: 'scene_directions', target: 'context', key: 'scene_directions', save_to_db: false },
        { name: 'chapter_goals', target: 'context', key: 'chapter_goals', save_to_db: false },
      ],
    },
    {
      id: 'parallel_prep',
      node_type: 'parallel',
      label: '并行执行',
      description: '围绕章节大纲并行执行设定、事件、地图与探索素材',
      config: {},
      position: { x: 520, y: 220 },
    },
    {
      id: 'setting',
      node_type: 'agent',
      agent_type: 'setting',
      label: '设定 Agent',
      description: '根据章节上下文动态选择相关已有设定',
      config: { task: 'select_relevant_existing_lore', setting_limit: 10 },
      position: { x: 80, y: 340 },
      inputs: [
        { name: 'chapter_outline', source: 'upstream', upstream_node: 'plot_outline', upstream_field: 'chapter_outline', required: false },
        { name: 'chapter_goals', source: 'upstream', upstream_node: 'plot_outline', upstream_field: 'chapter_goals', required: false },
        { name: 'lore_entries', source: 'context', key: 'lore_entries', required: false },
        { name: 'world_info', source: 'context', key: 'world_info', required: false },
        { name: 'scene_directions', source: 'context', key: 'scene_directions', required: false },
        { name: 'selected_characters', source: 'context', key: 'selected_characters', required: false },
        { name: 'locations', source: 'context', key: 'locations', required: false },
      ],
      outputs: [
        { name: 'lore_entries', target: 'context', key: 'lore_entries', save_to_db: false },
        { name: 'fixed_lore_entries', target: 'context', key: 'fixed_lore_entries', save_to_db: false },
        { name: 'dynamic_lore_entries', target: 'context', key: 'dynamic_lore_entries', save_to_db: false },
        { name: 'selected_lore_entries', target: 'context', key: 'selected_lore_entries', save_to_db: false },
        { name: 'setting_updates', target: 'context', key: 'setting_updates', save_to_db: false },
        { name: 'setting_query', target: 'context', key: 'setting_query', save_to_db: false },
        { name: 'setting_source', target: 'context', key: 'setting_source', save_to_db: false },
        { name: 'setting_count', target: 'context', key: 'setting_count', save_to_db: false },
        { name: 'setting_read_only', target: 'context', key: 'setting_read_only', save_to_db: false },
      ],
    },
    {
      id: 'event_generator',
      node_type: 'agent',
      agent_type: 'event_generator',
      label: '事件 Agent',
      description: '根据章节大纲生成事件候选',
      config: {},
      position: { x: 280, y: 340 },
      inputs: [
        { name: 'chapter_outline', source: 'upstream', upstream_node: 'plot_outline', upstream_field: 'chapter_outline', required: false },
        { name: 'chapter_goals', source: 'upstream', upstream_node: 'plot_outline', upstream_field: 'chapter_goals', required: false },
        { name: 'events', source: 'context', key: 'events', required: false },
      ],
      outputs: [
        { name: 'events', target: 'context', key: 'events', save_to_db: false },
        { name: 'event_candidates', target: 'context', key: 'event_candidates', save_to_db: false },
      ],
    },
    {
      id: 'world_map_manager',
      node_type: 'agent',
      agent_type: 'world_map_manager',
      label: '地图 Agent',
      description: '基于场景方向准备地图与地点信息',
      config: {},
      position: { x: 480, y: 340 },
      inputs: [
        { name: 'scene_directions', source: 'upstream', upstream_node: 'plot_outline', upstream_field: 'scene_directions', required: false },
        { name: 'chapter_outline', source: 'upstream', upstream_node: 'plot_outline', upstream_field: 'chapter_outline', required: false },
        { name: 'world_info', source: 'context', key: 'world_info', required: false },
        { name: 'locations', source: 'context', key: 'locations', required: false },
      ],
      outputs: [
        { name: 'locations', target: 'context', key: 'locations', save_to_db: false },
        { name: 'world_map_plan', target: 'context', key: 'world_map_plan', save_to_db: false },
      ],
    },
    {
      id: 'proc_gen',
      node_type: 'agent',
      agent_type: 'proc_gen',
      label: '过程生成 Agent',
      description: '扩展探索区域和环境细节',
      config: {},
      position: { x: 680, y: 340 },
      inputs: [
        { name: 'scene_directions', source: 'upstream', upstream_node: 'plot_outline', upstream_field: 'scene_directions', required: false },
        { name: 'chapter_goals', source: 'upstream', upstream_node: 'plot_outline', upstream_field: 'chapter_goals', required: false },
        { name: 'world_info', source: 'context', key: 'world_info', required: false },
      ],
      outputs: [
        { name: 'regions', target: 'context', key: 'regions', save_to_db: false },
        { name: 'procgen_result', target: 'context', key: 'procgen_result', save_to_db: false },
      ],
    },
    {
      id: 'dungeon_generator',
      node_type: 'agent',
      agent_type: 'dungeon_generator',
      label: '副本生成 Agent',
      description: '如章节涉及探索/副本则生成可用结构',
      config: {},
      position: { x: 880, y: 340 },
      inputs: [
        { name: 'scene_directions', source: 'upstream', upstream_node: 'plot_outline', upstream_field: 'scene_directions', required: false },
        { name: 'chapter_outline', source: 'upstream', upstream_node: 'plot_outline', upstream_field: 'chapter_outline', required: false },
      ],
      outputs: [
        { name: 'dungeon_plan', target: 'context', key: 'dungeon_plan', save_to_db: false },
      ],
    },
    {
      id: 'group_discussion',
      node_type: 'group_discussion',
      label: '集体讨论',
      description: '汇总并行结果，形成统一创作方向',
      config: { leader_agent: 'master_plotter' },
      position: { x: 520, y: 500 },
      inputs: [
        { name: 'chapter_title', source: 'upstream', upstream_node: 'plot_outline', upstream_field: 'chapter_title', required: false },
        { name: 'chapter_outline', source: 'upstream', upstream_node: 'plot_outline', upstream_field: 'chapter_outline', required: false },
        { name: 'chapter_goals', source: 'upstream', upstream_node: 'plot_outline', upstream_field: 'chapter_goals', required: false },
        { name: 'events', source: 'upstream', upstream_node: 'event_generator', upstream_field: 'events', required: false },
        { name: 'selected_lore_entries', source: 'upstream', upstream_node: 'setting', upstream_field: 'selected_lore_entries', required: false },
        { name: 'locations', source: 'upstream', upstream_node: 'world_map_manager', upstream_field: 'locations', required: false },
        { name: 'regions', source: 'upstream', upstream_node: 'proc_gen', upstream_field: 'regions', required: false },
        { name: 'dungeon_plan', source: 'upstream', upstream_node: 'dungeon_generator', upstream_field: 'dungeon_plan', required: false },
      ],
      outputs: [
        { name: 'group_discussion', target: 'context', key: 'group_discussion', save_to_db: false },
        { name: 'last_discussion_summary', target: 'context', key: 'last_discussion_summary', save_to_db: false },
      ],
    },
    {
      id: 'hook_manager',
      node_type: 'agent',
      agent_type: 'hook_manager',
      label: '伏笔 Agent',
      description: '根据章节大纲和讨论结果规划伏笔',
      config: {},
      position: { x: 520, y: 620 },
      inputs: [
        { name: 'chapter_outline', source: 'upstream', upstream_node: 'plot_outline', upstream_field: 'chapter_outline', required: false },
        { name: 'chapter_goals', source: 'upstream', upstream_node: 'plot_outline', upstream_field: 'chapter_goals', required: false },
        { name: 'existing_hooks', source: 'context', key: 'existing_hooks', required: false },
        { name: 'last_discussion_summary', source: 'context', key: 'last_discussion_summary', required: false },
      ],
      outputs: [
        { name: 'hooks', target: 'context', key: 'hooks', save_to_db: false },
        { name: 'existing_hooks', target: 'context', key: 'existing_hooks', save_to_db: false },
      ],
    },
    {
      id: 'scene_performance',
      node_type: 'scene_performance',
      label: '场景演绎',
      description: '根据场景指令组织多角色演绎',
      config: { scene_mode: 'interactive' },
      position: { x: 520, y: 740 },
      inputs: [
        { name: 'scene_directions', source: 'upstream', upstream_node: 'plot_outline', upstream_field: 'scene_directions', required: false },
        { name: 'chapter_outline', source: 'upstream', upstream_node: 'plot_outline', upstream_field: 'chapter_outline', required: false },
        { name: 'characters', source: 'context', key: 'characters', required: false },
      ],
      outputs: [
        { name: 'performance_result', target: 'context', key: 'performance_result', save_to_db: false },
        { name: 'dialogues', target: 'context', key: 'dialogues', save_to_db: false },
      ],
    },
    {
      id: 'summarizer',
      node_type: 'agent',
      agent_type: 'summarizer',
      label: '摘要 Agent',
      description: '压缩上游结果为写作可用摘要',
      config: {},
      position: { x: 520, y: 860 },
      inputs: [
        { name: 'chapter_summary', source: 'upstream', upstream_node: 'plot_outline', upstream_field: 'chapter_summary', required: false },
        { name: 'last_discussion_summary', source: 'context', key: 'last_discussion_summary', required: false },
        { name: 'performance_result', source: 'context', key: 'performance_result', required: false },
        { name: 'hooks', source: 'context', key: 'hooks', required: false },
      ],
      outputs: [
        { name: 'summary', target: 'context', key: 'summary', save_to_db: false },
        { name: 'chapter_summary', target: 'context', key: 'chapter_summary', save_to_db: false },
      ],
    },
    {
      id: 'condition_need_input',
      node_type: 'condition',
      label: '条件分支',
      description: '保留交互检查点，通常走通过分支',
      config: { condition_key: 'need_user_input', pass_value: false, pass_when_missing: true },
      position: { x: 520, y: 980 },
      inputs: [
        { name: 'summary', source: 'context', key: 'summary', required: false },
        { name: 'chapter_outline', source: 'context', key: 'chapter_outline', required: false },
      ],
      outputs: [
        { name: 'quality_passed', target: 'context', key: 'quality_passed', save_to_db: false },
      ],
    },
    {
      id: 'input',
      node_type: 'input',
      label: '用户输入',
      description: '当需要人工补充时暂停',
      config: { prompt: '请补充本章的额外要求或修订意见' },
      position: { x: 850, y: 980 },
      outputs: [
        { name: 'status', target: 'context', key: 'input_status', save_to_db: false },
      ],
    },
    {
      id: 'master_plotter',
      node_type: 'agent',
      agent_type: 'master_plotter',
      label: '总编剧 Agent',
      description: '统一整理为写作计划',
      config: {},
      position: { x: 520, y: 1100 },
      inputs: [
        { name: 'chapter_outline', source: 'context', key: 'chapter_outline', required: false },
        { name: 'chapter_goals', source: 'context', key: 'chapter_goals', required: false },
        { name: 'summary', source: 'context', key: 'summary', required: false },
        { name: 'hooks', source: 'context', key: 'hooks', required: false },
        { name: 'events', source: 'context', key: 'events', required: false },
        { name: 'locations', source: 'context', key: 'locations', required: false },
      ],
      outputs: [
        { name: 'plot_outline', target: 'context', key: 'plot_outline', save_to_db: false },
        { name: 'chapter_outline', target: 'context', key: 'chapter_outline', save_to_db: false },
        { name: 'chapter_goals', target: 'context', key: 'chapter_goals', save_to_db: false },
      ],
    },
    {
      id: 'writer',
      node_type: 'agent',
      agent_type: 'writer',
      label: '作家 Agent',
      description: '根据大纲与摘要完成章节写作',
      config: {},
      position: { x: 520, y: 1220 },
      inputs: [
        { name: 'chapter_title', source: 'context', key: 'chapter_title', required: false },
        { name: 'chapter_outline', source: 'context', key: 'chapter_outline', required: false },
        { name: 'chapter_goals', source: 'context', key: 'chapter_goals', required: false },
        { name: 'summary', source: 'context', key: 'summary', required: false },
        { name: 'scene_directions', source: 'context', key: 'scene_directions', required: false },
        { name: 'hooks', source: 'context', key: 'hooks', required: false },
        { name: 'selected_lore_entries', source: 'context', key: 'selected_lore_entries', required: false },
        { name: 'retry_message', source: 'context', key: 'retry_message', required: false },
      ],
      outputs: [
        { name: 'content', target: 'context', key: 'chapter_content', save_to_db: false },
        { name: 'summary', target: 'context', key: 'writer_summary', save_to_db: false },
      ],
    },
    {
      id: 'evaluator',
      node_type: 'agent',
      agent_type: 'evaluator',
      label: '评估 Agent',
      description: '给出质量判定和修订建议',
      config: {},
      position: { x: 520, y: 1340 },
      inputs: [
        { name: 'chapter_content', source: 'context', key: 'chapter_content', required: false },
        { name: 'chapter_outline', source: 'context', key: 'chapter_outline', required: false },
        { name: 'chapter_goals', source: 'context', key: 'chapter_goals', required: false },
        { name: 'selected_lore_entries', source: 'context', key: 'selected_lore_entries', required: false },
      ],
      outputs: [
        { name: 'quality_passed', target: 'context', key: 'quality_passed', save_to_db: false },
        { name: 'issues', target: 'context', key: 'evaluation_issues', save_to_db: false },
        { name: 'suggestions', target: 'context', key: 'revision_notes', save_to_db: false },
      ],
    },
    {
      id: 'condition_quality',
      node_type: 'condition',
      label: '条件分支',
      description: '决定结束还是回到写作修订',
      config: { condition_key: 'evaluation_passed', pass_value: true, pass_when_missing: false },
      position: { x: 520, y: 1460 },
      inputs: [
        { name: 'quality_passed', source: 'context', key: 'evaluation_passed', required: false, default: false },
        { name: 'evaluation_feedback', source: 'context', key: 'evaluation_feedback', required: false },
      ],
      outputs: [
        { name: 'quality_passed', target: 'context', key: 'quality_passed', save_to_db: false },
        { name: 'revision_notes', target: 'context', key: 'revision_notes', save_to_db: false },
      ],
    },
    {
      id: 'end',
      node_type: 'end',
      label: '结束',
      description: '输出完成',
      config: {},
      position: { x: 520, y: 1580 },
    },
  ] as WfNode[],
  edges: [
    { id: 'e1', source: 'start', target: 'plot_outline' },
    { id: 'e2', source: 'plot_outline', target: 'parallel_prep' },
    { id: 'e3', source: 'parallel_prep', target: 'setting' },
    { id: 'e4', source: 'parallel_prep', target: 'event_generator' },
    { id: 'e5', source: 'parallel_prep', target: 'world_map_manager' },
    { id: 'e6', source: 'parallel_prep', target: 'proc_gen' },
    { id: 'e7', source: 'parallel_prep', target: 'dungeon_generator' },
    { id: 'e8', source: 'setting', target: 'group_discussion' },
    { id: 'e9', source: 'event_generator', target: 'group_discussion' },
    { id: 'e10', source: 'world_map_manager', target: 'group_discussion' },
    { id: 'e11', source: 'proc_gen', target: 'group_discussion' },
    { id: 'e12', source: 'dungeon_generator', target: 'group_discussion' },
    { id: 'e13', source: 'group_discussion', target: 'hook_manager' },
    { id: 'e14', source: 'hook_manager', target: 'scene_performance' },
    { id: 'e15', source: 'scene_performance', target: 'summarizer' },
    { id: 'e16', source: 'summarizer', target: 'condition_need_input', condition: { result: 'pass' }, label: '继续' },
    { id: 'e17', source: 'condition_need_input', target: 'master_plotter', condition: { result: 'pass' }, label: '继续' },
    { id: 'e18', source: 'condition_need_input', target: 'input', condition: { result: 'retry' }, label: '补充' },
    { id: 'e19', source: 'input', target: 'master_plotter' },
    { id: 'e20', source: 'master_plotter', target: 'writer' },
    { id: 'e21', source: 'writer', target: 'evaluator' },
    { id: 'e22', source: 'evaluator', target: 'condition_quality' },
    { id: 'e23', source: 'condition_quality', target: 'end', condition: { result: 'pass' }, label: '通过' },
    { id: 'e24', source: 'condition_quality', target: 'writer', condition: { result: 'retry' }, label: '返工' },
  ] as WfEdge[],
  variables: {
    chapter_num: 1,
    target_word_count: 2000,
  },
}

function workflowToCanvasNodes(workflow: WorkflowDefinition): Node<VisualNodeData>[] {
  return workflow.nodes.map((node) => ({
    id: node.id,
    type: node.node_type,
    position: node.position,
    data: {
      label: node.label,
      agent_type: node.agent_type,
      config: node.config,
      description: node.description,
      inputs: node.inputs || [],
      outputs: node.outputs || [],
    },
  }))
}

function workflowToCanvasEdges(workflow: WorkflowDefinition): Edge[] {
  return workflow.edges.map((edge) => {
    let sourceHandle: string | undefined
    if (edge.condition?.result === 'pass') {
      sourceHandle = 'pass'
    } else if (edge.condition?.result === 'retry') {
      sourceHandle = 'retry'
    }

    return {
      id: edge.id,
      source: edge.source,
      target: edge.target,
      sourceHandle,
      animated: true,
      label: edge.label,
      style:
        sourceHandle === 'pass'
          ? { stroke: '#22c55e', strokeWidth: 2 }
          : sourceHandle === 'retry'
            ? { stroke: '#ef4444', strokeWidth: 2 }
            : undefined,
    }
  })
}

function buildStandardTemplateWorkflow(projectId: string): WorkflowDefinition {
  return {
    id: `standard_all_nodes_${Date.now()}`,
    project_id: projectId,
    name: standardAllNodesDefinition.name,
    description: standardAllNodesDefinition.description,
    nodes: standardAllNodesDefinition.nodes.map((node) => ({
      ...node,
      config: { ...node.config },
      inputs: node.inputs ? [...node.inputs] : [],
      outputs: node.outputs ? [...node.outputs] : [],
      position: { ...node.position },
    })),
    edges: standardAllNodesDefinition.edges.map((edge) => ({
      ...edge,
      condition: edge.condition ? { ...edge.condition } : undefined,
    })),
    variables: { ...standardAllNodesDefinition.variables },
    is_template: false,
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
  }
}

function buildWorkflowNodesFromCanvas(nodes: Node<VisualNodeData>[]): WfNode[] {
  return nodes.map((node) => ({
    id: node.id,
    node_type: node.type as WfNode['node_type'],
    label: node.data.label || '节点',
    agent_type: node.data.agent_type,
    description: node.data.description,
    config: node.data.config || {},
    inputs: node.data.inputs || [],
    outputs: node.data.outputs || [],
    position: node.position,
  }))
}

function buildWorkflowEdgesFromCanvas(edges: Edge[]): WfEdge[] {
  return edges.map((edge, index) => {
    let condition: { result: string } | undefined
    if (edge.sourceHandle === 'pass') condition = { result: 'pass' }
    else if (edge.sourceHandle === 'retry') condition = { result: 'retry' }
    else if (edge.sourceHandle === 'loop') condition = { result: 'retry' }

    return {
      id: edge.id || `edge_${index}`,
      source: edge.source,
      target: edge.target,
      label: typeof edge.label === 'string' ? edge.label : undefined,
      condition,
    }
  })
}

function getWorkflowOrigin(workflow: WorkflowDefinition): WorkflowOrigin {
  return workflow.is_template && workflow.project_id === null ? 'global_template' : 'project'
}

function buildWorkflowDisplayName(workflow: WorkflowDefinition, mode: WorkflowOrigin): string {
  return mode === 'global_template' ? `${workflow.name}（模板副本）` : workflow.name
}

function buildWorkflowPayload(
  nodes: Node<VisualNodeData>[],
  edges: Edge[],
  workflowName: string,
  selectedWorkflow: WorkflowDefinition | null,
  currentProjectId: string,
) {
  const workflowNodes = buildWorkflowNodesFromCanvas(nodes)
  const workflowEdges = buildWorkflowEdgesFromCanvas(edges)
  const isStandardTemplate = workflowName === standardAllNodesDefinition.name

  return {
    workflowNodes,
    workflowEdges,
    createPayload: {
      project_id: currentProjectId,
      name: workflowName,
      description: selectedWorkflow?.description || (isStandardTemplate ? standardAllNodesDefinition.description : undefined),
      nodes: workflowNodes,
      edges: workflowEdges,
      variables: selectedWorkflow?.variables || (isStandardTemplate ? standardAllNodesDefinition.variables : {}),
    },
    updatePayload: {
      name: workflowName,
      description: selectedWorkflow?.description || (isStandardTemplate ? standardAllNodesDefinition.description : undefined),
      nodes: workflowNodes,
      edges: workflowEdges,
      variables: selectedWorkflow?.variables || (isStandardTemplate ? standardAllNodesDefinition.variables : {}),
    },
  }
}

export default function Visualizer() {
  const { theme } = useTheme()
  const isDark = theme === 'dark'
  const { currentProject } = useProject()

  const [activeTab, setActiveTab] = useState<TabType>('workflow')
  const [data, setData] = useState<any>(null)
  const [worlds, setWorlds] = useState<World[]>([])
  const [selectedWorldId, setSelectedWorldId] = useState('')
  const [regionsByWorldId, setRegionsByWorldId] = useState<Record<string, Region[]>>({})
  const [characters, setCharacters] = useState<Character[]>([])
  const [loadingSceneData, setLoadingSceneData] = useState(false)
  const [selectedRelationshipNodeId, setSelectedRelationshipNodeId] = useState('')
  const [nodeTypesData, setNodeTypesData] = useState<WorkflowNodeTypes>({
    agent_nodes: [],
    interaction_nodes: [],
    control_nodes: [],
    character_nodes: [],
  })
  const [loadingNodeTypes, setLoadingNodeTypes] = useState(true)
  const [workflows, setWorkflows] = useState<WorkflowDefinition[]>([])
  const [selectedWorkflow, setSelectedWorkflow] = useState<WorkflowDefinition | null>(null)
  const [workflowSelectionMode, setWorkflowSelectionMode] = useState<WorkflowOrigin>('project')
  const [nodes, setNodes] = useState<Node<VisualNodeData>[]>([])
  const [edges, setEdges] = useState<Edge[]>([])
  const [workflowName, setWorkflowName] = useState('新工作流')
  const [saving, setSaving] = useState(false)
  const [executing, setExecuting] = useState(false)
  const [startPrechecking, setStartPrechecking] = useState(false)
  const [startPrecheckError, setStartPrecheckError] = useState<string | null>(null)
  const [startPrecheckOutline, setStartPrecheckOutline] = useState<ChapterOutline | null>(null)
  const [startPrecheckReadiness, setStartPrecheckReadiness] = useState<ChapterResourceReadiness | null>(null)
  const [startPrecheckBlockingRequirements, setStartPrecheckBlockingRequirements] = useState<OutlineResourceRequirement[]>([])
  const [startPrecheckAdvisoryRequirements, setStartPrecheckAdvisoryRequirements] = useState<OutlineResourceRequirement[]>([])
  const [currentExecutionId, setCurrentExecutionId] = useState<string | null>(null)
  const [currentExecutionStatus, setCurrentExecutionStatus] = useState<string | null>(null)
  const [currentExecution, setCurrentExecution] = useState<WorkflowExecution | null>(null)
  const [executionOperationSummary, setExecutionOperationSummary] = useState<WorkflowOperationSummary | null>(null)
  const [executionOperationEvents, setExecutionOperationEvents] = useState<WorkflowOperationEvent[]>([])
  const [executionRestoreError, setExecutionRestoreError] = useState<string | null>(null)
  const [workflowSseState, setWorkflowSseState] = useState<WorkflowSseState>('closed')
  const [workflowSseMessage, setWorkflowSseMessage] = useState('')
  const [executionActionError, setExecutionActionError] = useState<string | null>(null)
  const [recoveringExecution, setRecoveringExecution] = useState(false)
  const [recoveryReason, setRecoveryReason] = useState('visualize_manual_recovery')
  const [failedNodeDiagnosis, setFailedNodeDiagnosis] = useState<WorkflowFailureDiagnosis | null>(null)
  const [failedNodeDiagnosisLoading, setFailedNodeDiagnosisLoading] = useState(false)
  const [failedNodeDiagnosisError, setFailedNodeDiagnosisError] = useState<string | null>(null)
  const [remediationAgentType, setRemediationAgentType] = useState('')
  const [remediationScenario, setRemediationScenario] = useState('')
  const [remediatingExecution, setRemediatingExecution] = useState(false)
  const [executionHistory, setExecutionHistory] = useState<WorkflowExecutionHistoryRow[]>([])
  const [executionHistoryLoading, setExecutionHistoryLoading] = useState(false)
  const [executionHistoryError, setExecutionHistoryError] = useState<string | null>(null)
  const [executionHistoryStatusFilter, setExecutionHistoryStatusFilter] = useState<WorkflowStatus | 'all'>('all')
  const [pendingUrlExecutionId, setPendingUrlExecutionId] = useState<string | null>(null)
  const [executionAuditPanelOpen, setExecutionAuditPanelOpen] = useState(false)
  const [operationEventFilter, setOperationEventFilter] = useState<'all' | 'lifecycle' | 'node' | 'failure' | 'recovery' | 'remediation' | 'stale'>('all')
  const [selectedOperationEventKey, setSelectedOperationEventKey] = useState<string | null>(null)
  const [staleInspection, setStaleInspection] = useState<WorkflowStaleInspection | null>(null)
  const [staleInspectionLoading, setStaleInspectionLoading] = useState(false)
  const [staleActionLoading, setStaleActionLoading] = useState(false)
  const [runtimeFixtureLoading, setRuntimeFixtureLoading] = useState(false)
  const [runtimeFixtureCleanupLoading, setRuntimeFixtureCleanupLoading] = useState(false)
  const [runtimeFixture, setRuntimeFixture] = useState<{ executionId: string; workflowId: string; cleanupToken: string } | null>(null)
  const [rightWorkflowPanel, setRightWorkflowPanel] = useState<'monitor' | 'trace'>('monitor')

  useEffect(() => {
    loadNodeTypes()
  }, [currentProject])

  const loadNodeTypes = async () => {
    setLoadingNodeTypes(true)
    try {
      const result = await getWorkflowNodeTypes(currentProject?.id)
      setNodeTypesData(result)
    } catch (error) {
      console.error('[Visualizer] Failed to load node types:', error)
    } finally {
      setLoadingNodeTypes(false)
    }
  }

  useEffect(() => {
    if (currentProject) {
      loadWorlds()
    } else {
      setWorlds([])
      setSelectedWorldId('')
      setData(null)
    }
  }, [currentProject])

  useEffect(() => {
    if (!selectedWorldId) {
      setData(null)
      return
    }
    loadData(selectedWorldId)
  }, [selectedWorldId])

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Delete' || e.key === 'Backspace') {
        const target = e.target as HTMLElement
        if (target.tagName === 'INPUT' || target.tagName === 'TEXTAREA') return
        setNodes((nds) => nds.filter((node) => !node.selected))
        setEdges((eds) => eds.filter((edge) => !edge.selected))
      }
    }
    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [setNodes, setEdges])

  useEffect(() => {
    if (!currentProject || (activeTab !== 'world3d' && activeTab !== 'relationships3d')) return
    void loadSceneData()
  }, [currentProject, worlds, activeTab])

  useEffect(() => {
    setSelectedRelationshipNodeId('')
  }, [selectedWorldId])

  const loadWorlds = async () => {
    if (!currentProject) return
    try {
      const result = await getWorlds(currentProject.id)
      setWorlds(result)
      setSelectedWorldId((current) => {
        if (current && result.some((world) => world.id === current)) {
          return current
        }
        return result[0]?.id || ''
      })
    } catch (error) {
      console.error('Failed to load worlds:', error)
    }
  }

  const loadWorkflows = useCallback(async (): Promise<WorkflowDefinition[]> => {
    if (!currentProject) return []
    try {
      const result = await getWorkflows(currentProject.id, true)
      setWorkflows(result)
      return result
    } catch (error) {
      console.error('Failed to load workflows:', error)
      return []
    }
  }, [currentProject])

  const loadSceneData = async () => {
    if (!currentProject) return
    setLoadingSceneData(true)
    try {
      const [characterResult, regionEntries] = await Promise.all([
        getCharacters(currentProject.id),
        Promise.all(
          worlds
            .filter((world) => world.id)
            .map(async (world) => {
              try {
                return [world.id as string, await getRegions(world.id as string)] as const
              } catch (error) {
                console.warn('Failed to load regions for world:', world.id, error)
                return [world.id as string, []] as const
              }
            }),
        ),
      ])
      setCharacters(characterResult)
      setRegionsByWorldId(Object.fromEntries(regionEntries))
    } catch (error) {
      console.error('Failed to load 3D scene data:', error)
    } finally {
      setLoadingSceneData(false)
    }
  }

  const loadData = async (worldId: string) => {
    try {
      const result = await getVisualizationData(worldId)
      setData(result)
    } catch (error) {
      console.error('Failed to load visualization data:', error)
    }
  }

  const onNodesChange: OnNodesChange = useCallback((changes) => {
    setNodes((nds) => applyNodeChanges(changes, nds))
  }, [])

  const onEdgesChange: OnEdgesChange = useCallback((changes) => {
    setEdges((eds) => applyEdgeChanges(changes, eds))
  }, [])

  const onConnect = useCallback((connection: Connection) => {
    setEdges((eds) => addEdge({ ...connection, animated: true }, eds))
  }, [])

  const clearExecutionProjection = useCallback(() => {
    setNodes((currentNodes) => currentNodes.map((node) => ({
      ...node,
      data: {
        ...node.data,
        status: undefined,
        error: undefined,
        duration_ms: undefined,
      },
    })))
  }, [])

  const resetExecutionState = useCallback(() => {
    setCurrentExecution(null)
    setCurrentExecutionId(null)
    setCurrentExecutionStatus(null)
    setExecutionActionError(null)
    setFailedNodeDiagnosis(null)
    setFailedNodeDiagnosisError(null)
    setRemediationAgentType('')
    setRemediationScenario('')
    setWorkflowSseState('closed')
    setWorkflowSseMessage('')
    setExecutionOperationEvents([])
    setSelectedOperationEventKey(null)
    setStaleInspection(null)
    clearExecutionProjection()
  }, [clearExecutionProjection])

  const projectWorkflowFromDefinition = useCallback((workflow: WorkflowDefinition) => {
    const origin = getWorkflowOrigin(workflow)
    setSelectedWorkflow(origin === 'global_template' ? null : workflow)
    setWorkflowSelectionMode(origin)
    setWorkflowName(buildWorkflowDisplayName(workflow, origin))
    setNodes(workflowToCanvasNodes(workflow))
    setEdges(workflowToCanvasEdges(workflow))
  }, [])

  const handleSelectWorkflow = (workflow: WorkflowDefinition) => {
    projectWorkflowFromDefinition(workflow)
    resetExecutionState()
  }

  const handleNewWorkflow = () => {
    setSelectedWorkflow(null)
    setWorkflowSelectionMode('project')
    setWorkflowName('新工作流')
    setNodes([
      { id: 'start', type: 'start', position: { x: 250, y: 50 }, data: { label: '开始' } },
      { id: 'end', type: 'end', position: { x: 250, y: 400 }, data: { label: '结束' } },
    ])
    setEdges([])
    resetExecutionState()
  }

  const handleLoadStandardWorkflow = () => {
    if (!currentProject) return
    const workflow = buildStandardTemplateWorkflow(currentProject.id)
    setSelectedWorkflow(null)
    setWorkflowSelectionMode('project')
    setWorkflowName(workflow.name)
    setNodes(workflowToCanvasNodes(workflow))
    setEdges(workflowToCanvasEdges(workflow))
    resetExecutionState()
  }

  const handleAddNode = (nodeInfo: NodeTypeInfo) => {
    const nodeType = nodeInfo.type as WfNode['node_type']
    const newNode: Node<VisualNodeData> = {
      id: generateId(),
      type: nodeType,
      position: { x: 100 + Math.random() * 300, y: 150 + nodes.length * 80 },
      data: {
        label: nodeInfo.label,
        agent_type: nodeInfo.agent_type,
        description: nodeInfo.description,
        config: {},
        inputs: [],
        outputs: [],
      },
    }
    setNodes((nds) => [...nds, newNode])
  }

  const persistCurrentWorkflow = useCallback(async (): Promise<WorkflowDefinition | null> => {
    if (!currentProject) return null

    const baseWorkflow = workflowSelectionMode === 'global_template' ? null : selectedWorkflow
    const { createPayload, updatePayload } = buildWorkflowPayload(
      nodes,
      edges,
      workflowName,
      baseWorkflow,
      currentProject.id,
    )

    if (baseWorkflow) {
      const result = await updateWorkflow(baseWorkflow.id, updatePayload)
      setSelectedWorkflow(result.workflow)
      setWorkflowSelectionMode('project')
      return result.workflow
    }

    const result = await createWorkflow(createPayload)
    setSelectedWorkflow(result.workflow)
    setWorkflowSelectionMode('project')
    return result.workflow
  }, [currentProject, nodes, edges, workflowName, selectedWorkflow, workflowSelectionMode])

  const applyExecutionState = useCallback((execution: WorkflowExecution | null) => {
    setCurrentExecution(execution)
    setCurrentExecutionId(execution?.id || null)
    setCurrentExecutionStatus(execution?.status || null)
    setExecutionOperationSummary(execution?.operation_summary || null)
    if (execution?.status !== 'failed') setExecutionActionError(null)
    setNodes((currentNodes) => currentNodes.map((node) => {
      const state = execution?.node_states?.[node.id]
      return {
        ...node,
        data: {
          ...node.data,
          status: state?.status,
          error: state?.error,
          duration_ms: state?.duration_ms,
        },
      }
    }))
  }, [])

  const updateCurrentExecutionStatus = useCallback((status: WorkflowStatus) => {
    setCurrentExecutionStatus(status)
    setCurrentExecution((current) => current ? { ...current, status } : current)
    setExecutionOperationSummary(null)
  }, [])

  const loadOperationEvents = useCallback(async (executionId?: string | null) => {
    if (!executionId) {
      setExecutionOperationEvents([])
      setSelectedOperationEventKey(null)
      return
    }
    try {
      const events = await getExecutionOperationEvents(executionId, 80)
      setExecutionOperationEvents(events)
      setSelectedOperationEventKey((current) => {
        if (current && events.some((event, index) => operationEventKey(event, index) === current)) return current
        const newest = [...events].reverse()[0]
        return newest ? operationEventKey(newest, 0) : null
      })
    } catch (error) {
      console.warn('Failed to load operation events:', error)
      setExecutionOperationEvents([])
      setSelectedOperationEventKey(null)
    }
  }, [])

  const loadExecutionHistory = useCallback(async () => {
    if (!currentProject) return
    setExecutionHistoryLoading(true)
    setExecutionHistoryError(null)
    try {
      const rows = await getExecutions(
        currentProject.id,
        executionHistoryStatusFilter === 'all' ? undefined : executionHistoryStatusFilter,
        25,
        0,
        selectedWorkflow?.id,
      )
      setExecutionHistory(rows)
    } catch (error) {
      console.warn('Failed to load execution history:', error)
      setExecutionHistoryError(formatApiErrorMessage(error, '加载执行历史失败'))
    } finally {
      setExecutionHistoryLoading(false)
    }
  }, [currentProject, selectedWorkflow?.id, executionHistoryStatusFilter])

  const reconcileExecution = useCallback(async (
    executionId: string,
    options?: { openTrace?: boolean; updateUrl?: boolean; requireProject?: boolean; source?: string; availableWorkflows?: WorkflowDefinition[] },
  ) => {
    if (!currentProject) return null
    setExecutionActionError(null)
    setExecutionRestoreError(null)
    try {
      const execution = await getExecution(executionId)
      if (options?.requireProject !== false && execution.project_id !== currentProject.id) {
        throw new Error(`执行 ${execution.id} 属于项目 ${execution.project_id}，不属于当前项目 ${currentProject.id}`)
      }
      const workflowSource = options?.availableWorkflows?.length ? options.availableWorkflows : workflows
      const workflow = workflowSource.find((item) => item.id === execution.workflow_id)
      if (!workflow) {
        const message = `执行 ${execution.id} 仍可读取，但对应的工作流定义 ${execution.workflow_id} 不在当前项目工作流列表中；监控将继续以执行快照为准。`
        console.warn(message)
        setExecutionRestoreError(message)
      } else if (workflow.id !== selectedWorkflow?.id) {
        projectWorkflowFromDefinition(workflow)
      }
      applyExecutionState(execution)
      if (execution.status === 'failed') {
        setRightWorkflowPanel('trace')
        setExecutionAuditPanelOpen(true)
      } else if (isActiveExecutionStatus(execution.status)) {
        setRightWorkflowPanel('monitor')
      }
      localStorage.setItem(executionStorageKey(currentProject.id, execution.workflow_id), execution.id)
      if (options?.updateUrl !== false) {
        const params = new URLSearchParams(window.location.search)
        params.set('project_id', currentProject.id)
        params.set('execution_id', execution.id)
        window.history.replaceState({}, '', `${window.location.pathname}?${params.toString()}`)
      }
      if (options?.openTrace) setRightWorkflowPanel('trace')
      void loadOperationEvents(execution.id)
      setStaleInspection(execution.operation_summary?.stale_inspection || null)
      return execution
    } catch (error) {
      console.error('Failed to reconcile execution:', error)
      const message = formatApiErrorMessage(error, '加载执行失败')
      setExecutionActionError(message)
      setExecutionRestoreError(message)
      setExecutionOperationEvents([])
      return null
    }
  }, [applyExecutionState, currentProject, loadOperationEvents, projectWorkflowFromDefinition, selectedWorkflow?.id, workflows])

  const inspectExecution = useCallback(async (executionId: string, options?: { openTrace?: boolean }) => {
    await reconcileExecution(executionId, { ...options, updateUrl: true, source: 'history' })
  }, [reconcileExecution])

  useEffect(() => {
    if (activeTab !== 'workflow') return
    void loadExecutionHistory()
  }, [activeTab, loadExecutionHistory])

  useEffect(() => {
    if (activeTab !== 'workflow' || !currentExecutionId) return
    const handle = window.setTimeout(() => {
      void loadExecutionHistory()
    }, 800)
    return () => window.clearTimeout(handle)
  }, [activeTab, currentExecutionId, currentExecutionStatus, loadExecutionHistory])

  useEffect(() => {
    const failedEntry = currentExecution
      ? Object.entries(currentExecution.node_states).find(([, state]) => state.status === 'failed')
      : null
    const failedNodeId = failedEntry?.[0]

    if (activeTab !== 'workflow' || currentExecutionStatus !== 'failed' || !currentExecutionId || !failedNodeId) {
      setFailedNodeDiagnosis(null)
      setFailedNodeDiagnosisError(null)
      setRemediationAgentType('')
      setRemediationScenario('')
      return
    }

    let cancelled = false
    setFailedNodeDiagnosisLoading(true)
    setFailedNodeDiagnosisError(null)
    void getFailedNodeDiagnosis(currentExecutionId, failedNodeId)
      .then((diagnosis) => {
        if (cancelled) return
        setFailedNodeDiagnosis(diagnosis)
        setRemediationAgentType(diagnosis.current_agent_type || '')
        setRemediationScenario(diagnosis.current_scenario || '')
      })
      .catch((error) => {
        if (cancelled) return
        console.warn('Failed to load failed-node diagnosis:', error)
        setFailedNodeDiagnosis(null)
        setFailedNodeDiagnosisError(formatApiErrorMessage(error, '加载失败节点诊断失败'))
      })
      .finally(() => {
        if (!cancelled) setFailedNodeDiagnosisLoading(false)
      })

    return () => {
      cancelled = true
    }
  }, [activeTab, currentExecution, currentExecutionId, currentExecutionStatus])

  const hasPendingDiscussionConfirmation = currentExecutionStatus === 'paused'
    && Boolean(currentExecution?.context?.waiting_confirmation)

  const isInputPause = currentExecutionStatus === 'paused'
    && currentExecution?.current_node === 'input'
    && !currentExecution?.context?.waiting_confirmation

  const handleSaveWorkflow = async () => {
    if (!currentProject) return
    setSaving(true)
    try {
      const workflow = await persistCurrentWorkflow()
      if (!workflow) {
        alert('保存失败')
        return
      }
      await loadWorkflows()
      alert(
        workflowSelectionMode === 'global_template'
          ? '模板已复制到当前项目并保存成功！'
          : selectedWorkflow
            ? '工作流更新成功！'
            : '工作流创建成功！',
      )
    } catch (error) {
      console.error('Failed to save workflow:', error)
      alert('保存失败')
    } finally {
      setSaving(false)
    }
  }

  useEffect(() => {
    void loadWorkflows()
  }, [loadWorkflows])

  useEffect(() => {
    if (!currentProject) return
    const params = new URLSearchParams(window.location.search)
    const urlExecutionId = params.get('execution_id')
    setPendingUrlExecutionId(urlExecutionId)
    if (urlExecutionId) setActiveTab('workflow')
  }, [currentProject])

  useEffect(() => {
    if (!currentProject || !pendingUrlExecutionId || currentExecutionId === pendingUrlExecutionId) return
    let cancelled = false
    const restoreUrlExecution = async () => {
      const workflowSource = workflows.length ? workflows : await loadWorkflows()
      if (cancelled) return
      const execution = await reconcileExecution(pendingUrlExecutionId, {
        updateUrl: true,
        requireProject: true,
        source: 'url',
        availableWorkflows: workflowSource,
      })
      if (!cancelled && execution) setPendingUrlExecutionId(null)
    }
    void restoreUrlExecution()
    return () => {
      cancelled = true
    }
  }, [currentExecutionId, currentProject, loadWorkflows, pendingUrlExecutionId, reconcileExecution, workflows])

  useEffect(() => {
    if (!currentProject || !selectedWorkflow) return
    const params = new URLSearchParams(window.location.search)
    if (params.get('execution_id')) return

    const restoreExecution = async () => {
      const storedExecutionId = localStorage.getItem(executionStorageKey(currentProject.id, selectedWorkflow.id))

      try {
        if (storedExecutionId) {
          const execution = await getExecution(storedExecutionId)
          if (execution.workflow_id === selectedWorkflow.id && isActiveExecutionStatus(execution.status)) {
            applyExecutionState(execution)
            localStorage.setItem(executionStorageKey(currentProject.id, selectedWorkflow.id), execution.id)
            void loadOperationEvents(execution.id)
            return
          }
          localStorage.removeItem(executionStorageKey(currentProject.id, selectedWorkflow.id))
        }

        const active = await getActiveWorkflowExecution(currentProject.id, selectedWorkflow.id)
        if (active.execution && isActiveExecutionStatus(active.execution.status)) {
          applyExecutionState(active.execution)
          localStorage.setItem(executionStorageKey(currentProject.id, selectedWorkflow.id), active.execution.id)
          void loadOperationEvents(active.execution.id)
        }
      } catch (error) {
        console.warn('Failed to restore workflow execution:', error)
        setExecutionRestoreError(formatApiErrorMessage(error, '恢复执行状态失败'))
      }
    }

    void restoreExecution()
  }, [applyExecutionState, currentProject, loadOperationEvents, selectedWorkflow])
  const loadStartReadinessPrecheck = useCallback(async () => {
    if (!currentProject) return null

    setStartPrechecking(true)
    setStartPrecheckError(null)
    setStartPrecheckOutline(null)
    setStartPrecheckReadiness(null)
    setStartPrecheckBlockingRequirements([])
    setStartPrecheckAdvisoryRequirements([])

    try {
      const [outlinesResult, chaptersResult] = await Promise.all([
        getOutlines(currentProject.id),
        getChapters(currentProject.id),
      ])
      const completedChapters = (chaptersResult || []).filter(chapter => chapter.status === 'completed')
      const completedOutlineIds = new Set(
        completedChapters
          .map(chapter => String(chapter.chapter_outline_id || '').trim())
          .filter(Boolean),
      )
      const completedChapterNumbers = new Set(
        completedChapters
          .filter(chapter => !chapter.chapter_outline_id)
          .map(chapter => {
            const match = String(chapter.title || '').match(/第\s*(\d+)\s*章/)
            return match ? Number(match[1]) : null
          })
          .filter((value): value is number => Number.isFinite(value as number)),
      )
      const targetOutline = [...(outlinesResult.outlines || [])]
        .filter(outline => outline.status === 'approved' && !outline.next_outline_id)
        .sort((a, b) => a.chapter_number - b.chapter_number)
        .find(outline => (
          !completedOutlineIds.has(outline.id)
          && !completedChapterNumbers.has(outline.chapter_number)
        )) || null

      if (!targetOutline) {
        setStartPrecheckError('当前项目没有可启动的当前已审批大纲（所有当前已审批章节都已完成，或尚未审批）。请先在大纲页准备下一章的已审批大纲。')
        return null
      }

      setStartPrecheckOutline(targetOutline)
      const [requirementsResult, readinessResult] = await Promise.all([
        getOutlineResourceRequirements(currentProject.id, {
          outline_id: targetOutline.id,
          chapter_num: targetOutline.chapter_number,
        }),
        getChapterResourceReadiness(currentProject.id, {
          outline_id: targetOutline.id,
          chapter_num: targetOutline.chapter_number,
          refresh: true,
        }),
      ])

      const unresolvedStatuses = new Set(['pending', 'in_progress'])
      const blocking = requirementsResult.requirements.filter(requirement => (
        requirement.severity === 'blocking' && unresolvedStatuses.has(requirement.status)
      ))
      const advisory = requirementsResult.requirements.filter(requirement => (
        requirement.severity === 'advisory' && unresolvedStatuses.has(requirement.status)
      ))
      setStartPrecheckBlockingRequirements(blocking)
      setStartPrecheckAdvisoryRequirements(advisory)
      const readiness = readinessResult.readiness[0] || null
      setStartPrecheckReadiness(readiness)

      if (blocking.length > 0 || isReadinessBlockedStatus(readiness?.readiness_status)) {
        setStartPrecheckError(`第 ${targetOutline.chapter_number} 章存在 unresolved blocking 资源需求：${formatRequirementList(blocking) || '请到大纲页刷新资源需求。'}`)
        return null
      }

      return targetOutline
    } catch (error: any) {
      const gateDetail = extractChapterReadinessGateDetail(error)
      setStartPrecheckError(
        gateDetail
          ? formatChapterReadinessGateMessage(gateDetail, requirements => formatRequirementList(requirements as OutlineResourceRequirement[]))
          : formatApiErrorMessage(error, '启动前资源预检失败'),
      )
      return null
    } finally {
      setStartPrechecking(false)
    }
  }, [currentProject])

  const handleExecuteWorkflow = async (forceNew = false) => {
    if (!currentProject) return

    if (currentExecutionId && isActiveExecutionStatus(currentExecutionStatus || undefined) && !forceNew) {
      setExecutionActionError(`当前已有运行中的执行：${currentExecutionId}`)
      return
    }

    setExecutionActionError(null)
    setExecuting(true)
    try {
      const workflow = await persistCurrentWorkflow()
      if (!workflow) {
        setExecutionActionError('请先保存工作流')
        return
      }

      if (!selectedWorkflow) {
        await loadWorkflows()
      }

      const targetOutline = await loadStartReadinessPrecheck()
      if (!targetOutline) {
        setExecutionActionError(startPrecheckError || '启动前预检失败，请先修复阻塞项后再执行。')
        return
      }

      const requestId = `workflow_${workflow.id}_${Date.now()}_${Math.random().toString(36).slice(2, 9)}`
      const result = await executeWorkflow(
        workflow.id,
        currentProject.id,
        {
          chapter_num: targetOutline.chapter_number,
          chapter_outline_id: targetOutline.id,
          chapter_outline: targetOutline,
          ...(selectedWorldId ? { world_id: selectedWorldId } : {}),
        },
        { requestId, forceNew },
      )
      applyExecutionState({
        id: result.execution_id,
        workflow_id: workflow.id,
        project_id: currentProject.id,
        status: result.status || 'running',
        node_states: {},
        context: {},
        intervention_ids: [],
        started_at: new Date().toISOString(),
        trace_id: result.trace_id,
      })
      localStorage.setItem(executionStorageKey(currentProject.id, workflow.id), result.execution_id)
      const params = new URLSearchParams(window.location.search)
      params.set('execution_id', result.execution_id)
      window.history.replaceState(null, '', `${window.location.pathname}?${params.toString()}`)
    } catch (error: any) {
      const gateDetail = extractChapterReadinessGateDetail(error)
      setExecutionActionError(
        gateDetail
          ? formatChapterReadinessGateMessage(gateDetail, formatRequirementList)
          : formatApiErrorMessage(error, '执行失败'),
      )
      console.error('Failed to execute workflow:', error)
    } finally {
      setExecuting(false)
      void loadExecutionHistory()
    }
  }

  useEffect(() => {
    if (currentProject && activeTab === 'workflow') {
      void loadStartReadinessPrecheck()
    }
  }, [activeTab, currentProject, loadStartReadinessPrecheck])

  const handlePauseExecution = async () => {
    if (!currentExecutionId) return
    setExecutionActionError(null)
    try {
      const result = await pauseExecution(currentExecutionId)
      if (result.execution) {
        applyExecutionState(result.execution)
      } else {
        updateCurrentExecutionStatus('paused')
      }
      void loadExecutionHistory()
      void loadOperationEvents(currentExecutionId)
    } catch (error) {
      console.error('Failed to pause execution:', error)
      setExecutionActionError(formatApiErrorMessage(error, '暂停失败'))
    }
  }

  const handleResumeExecution = async () => {
    if (!currentExecutionId) return
    setExecutionActionError(null)
    try {
      const result = await resumeExecution(currentExecutionId)
      if (result.execution) {
        applyExecutionState(result.execution)
      } else {
        updateCurrentExecutionStatus('running')
      }
      void loadExecutionHistory()
      void loadOperationEvents(currentExecutionId)
    } catch (error) {
      console.error('Failed to resume execution:', error)
      setExecutionActionError(formatApiErrorMessage(error, '恢复失败'))
    }
  }

  const handleCancelExecution = async () => {
    if (!currentExecutionId) return
    if (!confirm('确定要取消当前工作流执行吗？')) return
    setExecutionActionError(null)
    try {
      const result = await cancelExecution(currentExecutionId)
      if (result.execution) {
        applyExecutionState(result.execution)
      } else {
        updateCurrentExecutionStatus('cancelled')
      }
      if (currentProject && selectedWorkflow) {
        localStorage.removeItem(executionStorageKey(currentProject.id, selectedWorkflow.id))
      }
      void loadExecutionHistory()
      void loadOperationEvents(currentExecutionId)
    } catch (error) {
      console.error('Failed to cancel execution:', error)
      setExecutionActionError(formatApiErrorMessage(error, '取消失败'))
    }
  }

  const reconcileRecoveredExecution = useCallback((executionId: string) => {
    void getExecution(executionId)
      .then((execution) => {
        applyExecutionState(execution)
        void loadOperationEvents(executionId)
      })
      .catch((error) => console.warn('Failed to reconcile recovered execution:', error))
    for (const delay of [1200, 3000, 7000]) {
      window.setTimeout(() => {
        void getExecution(executionId)
          .then((execution) => {
            applyExecutionState(execution)
            void loadOperationEvents(executionId)
          })
          .catch((error) => console.warn('Failed to reconcile recovered execution:', error))
      }, delay)
    }
  }, [applyExecutionState, loadOperationEvents])

  const handleRecoverExecution = async () => {
    if (!currentExecutionId || !selectedWorkflow || !failedNodeState) return
    const normalizedReason = recoveryReason.trim() || 'visualize_manual_recovery'

    setRecoveryReason(normalizedReason)
    setExecutionActionError(null)
    setRecoveringExecution(true)
    try {
      const result = await recoverExecution(currentExecutionId, {
        mode: 'retry_failed',
        reason: normalizedReason,
        reset_downstream: true,
      })
      updateCurrentExecutionStatus(result.status || 'running')
      reconcileRecoveredExecution(currentExecutionId)
      if (currentProject && selectedWorkflow) {
        localStorage.setItem(executionStorageKey(currentProject.id, selectedWorkflow.id), currentExecutionId)
      }
      void loadExecutionHistory()
      void loadOperationEvents(currentExecutionId)
    } catch (error) {
      console.error('Failed to recover execution:', error)
      setExecutionActionError(formatApiErrorMessage(error, '恢复失败'))
    } finally {
      setRecoveringExecution(false)
    }
  }

  const handleRemediateAndRecoverExecution = async () => {
    if (!currentExecutionId || !selectedWorkflow || !failedNodeState || !failedNodeDiagnosis) return
    const normalizedReason = recoveryReason.trim() || 'visualize_remediation_recovery'
    const patch: { agent_type?: string; scenario?: string } = {}
    const agentType = remediationAgentType.trim()
    const scenario = remediationScenario.trim()

    if (agentType && agentType !== (failedNodeDiagnosis.current_agent_type || '')) {
      patch.agent_type = agentType
    }
    if (scenario && scenario !== (failedNodeDiagnosis.current_scenario || '')) {
      patch.scenario = scenario
    }

    if (!patch.agent_type && !patch.scenario) {
      setExecutionActionError('请至少修改 Agent 类型或场景后再保存修复。')
      return
    }

    setRecoveryReason(normalizedReason)
    setExecutionActionError(null)
    setRemediatingExecution(true)
    try {
      const result = await remediateAndRecoverExecution(currentExecutionId, {
        node_id: failedNodeDiagnosis.failed_node_id || failedNodeState.node_id,
        reason: normalizedReason,
        patch,
        reset_downstream: true,
      })
      updateCurrentExecutionStatus(result.recovery.status || 'running')
      setFailedNodeDiagnosis(result.diagnosis)
      reconcileRecoveredExecution(currentExecutionId)
      if (currentProject && selectedWorkflow) {
        localStorage.setItem(executionStorageKey(currentProject.id, selectedWorkflow.id), currentExecutionId)
      }
      void loadExecutionHistory()
      void loadOperationEvents(currentExecutionId)
    } catch (error) {
      console.error('Failed to remediate and recover execution:', error)
      setExecutionActionError(formatApiErrorMessage(error, '保存修复并恢复失败'))
    } finally {
      setRemediatingExecution(false)
    }
  }

  const handleConfirmDiscussion = async (approved: boolean) => {
    if (!currentExecutionId) return
    const feedback = approved ? undefined : window.prompt('请输入返工反馈')
    if (!approved && !feedback) return

    setExecutionActionError(null)
    try {
      await confirmDiscussion(currentExecutionId, approved, feedback || undefined)
      updateCurrentExecutionStatus('running')
      setCurrentExecution((current) => current ? {
        ...current,
        context: {
          ...current.context,
          waiting_confirmation: undefined,
        },
      } : current)
    } catch (error) {
      console.error('Failed to confirm discussion:', error)
      setExecutionActionError(formatApiErrorMessage(error, '讨论确认失败'))
    }
  }

  const handleInspectStaleExecution = async () => {
    if (!currentExecutionId) return
    setStaleInspectionLoading(true)
    setExecutionActionError(null)
    try {
      const inspection = await inspectExecutionStaleness(currentExecutionId)
      setStaleInspection(inspection)
    } catch (error) {
      setExecutionActionError(formatApiErrorMessage(error, '陈旧状态检查失败'))
    } finally {
      setStaleInspectionLoading(false)
    }
  }

  const handleMarkExecutionStaleFailed = async () => {
    if (!currentExecutionId) return
    if (!confirm('确认将该执行标记为陈旧失败？该操作会写入审计历史，之后可从失败节点恢复。')) return
    setStaleActionLoading(true)
    setExecutionActionError(null)
    try {
      const result = await resolveStaleExecution(currentExecutionId, 'mark_failed', 'visualize_manual_stale_resolution')
      setStaleInspection(result.inspection)
      if (result.execution) applyExecutionState(result.execution)
      void loadOperationEvents(currentExecutionId)
      void loadExecutionHistory()
    } catch (error) {
      setExecutionActionError(formatApiErrorMessage(error, '陈旧执行治理失败'))
    } finally {
      setStaleActionLoading(false)
    }
  }

  const handleCreateStaleRuntimeFixture = async () => {
    if (!currentProject) return
    setRuntimeFixtureLoading(true)
    setExecutionActionError(null)
    try {
      const fixture = await createRuntimeFixture(currentProject.id, 'stale_running', `Visualizer stale fixture ${Date.now()}`)
      const workflow = fixture.workflow
      setRuntimeFixture({ executionId: fixture.execution.id, workflowId: workflow.id, cleanupToken: fixture.cleanup_token })
      setWorkflows((items) => [workflow, ...items.filter((item) => item.id !== workflow.id)])
      projectWorkflowFromDefinition(workflow)
      applyExecutionState(fixture.execution)
      setStaleInspection(fixture.inspection || null)
      setRightWorkflowPanel('monitor')
      const params = new URLSearchParams(window.location.search)
      params.set('project_id', currentProject.id)
      params.set('execution_id', fixture.execution.id)
      window.history.replaceState({}, '', `${window.location.pathname}?${params.toString()}`)
      void loadOperationEvents(fixture.execution.id)
      void loadExecutionHistory()
    } catch (error) {
      setExecutionActionError(formatApiErrorMessage(error, '创建运行时夹具失败。请确认后端处于 DEBUG 模式。'))
    } finally {
      setRuntimeFixtureLoading(false)
    }
  }

  const handleCleanupRuntimeFixture = async () => {
    if (!runtimeFixture) return
    if (!confirm('确认清理本次 DEBUG 运行时夹具？仅带有匹配 cleanup token 的夹具记录会被删除。')) return
    setRuntimeFixtureCleanupLoading(true)
    setExecutionActionError(null)
    try {
      await cleanupRuntimeFixture(runtimeFixture.executionId, runtimeFixture.workflowId, runtimeFixture.cleanupToken)
      setRuntimeFixture(null)
      resetExecutionState()
      await loadWorkflows()
      const params = new URLSearchParams(window.location.search)
      params.delete('execution_id')
      window.history.replaceState({}, '', `${window.location.pathname}?${params.toString()}`)
    } catch (error) {
      setExecutionActionError(formatApiErrorMessage(error, '清理运行时夹具失败'))
    } finally {
      setRuntimeFixtureCleanupLoading(false)
    }
  }

  const handleForceNewExecution = async () => {
    if (!confirm('当前可能已有执行在运行。确定要强制启动一个新执行吗？')) return
    await handleExecuteWorkflow(true)
  }

  const handleDeleteWorkflow = async (workflow: WorkflowDefinition, e: React.MouseEvent) => {
    e.stopPropagation()
    if (getWorkflowOrigin(workflow) === 'global_template') {
      alert('全局模板不能直接删除，请复制到项目后编辑。')
      return
    }

    if (!confirm(`确定要删除工作流 "${workflow.name}" 吗？`)) return
    try {
      await deleteWorkflow(workflow.id)
      if (selectedWorkflow?.id === workflow.id) {
        setSelectedWorkflow(null)
        setWorkflowSelectionMode('project')
        setNodes([])
        setEdges([])
        setWorkflowName('新工作流')
        resetExecutionState()
      }
      await loadWorkflows()
    } catch (error) {
      console.error('Failed to delete workflow:', error)
      alert('删除失败')
    }
  }

  const handleDeleteSelectedNodes = useCallback(() => {
    setNodes((nds) => nds.filter((node) => !node.selected))
    setEdges((eds) => eds.filter((edge) => !edge.selected))
  }, [])

  const currentWorld = useMemo(
    () => worlds.find((world) => world.id === selectedWorldId) || null,
    [worlds, selectedWorldId],
  )

  const plotNodes = (data?.plot_tree?.nodes || []).map((node: any, index: number) => ({
    id: node.id,
    position: { x: 160 + index * 180, y: 180 + (index % 2) * 120 },
    data: { label: node.label },
    style: { padding: 10, borderRadius: 10, background: '#fef3c7', border: '1px solid #f59e0b' },
  }))
  const plotEdges = (data?.plot_tree?.edges || []).map((edge: any, index: number) => ({
    id: `plot-${index}`,
    source: edge.source,
    target: edge.target,
  }))

  const snapshotNodes = (data?.snapshot_tree?.nodes || []).map((node: any, index: number) => ({
    id: node.id,
    position: { x: 160 + index * 180, y: 180 + (index % 3) * 100 },
    data: { label: node.label },
    style: {
      padding: 10,
      borderRadius: 10,
      background: node.is_branch ? '#f5d0fe' : '#ede9fe',
      border: '1px solid #a78bfa',
    },
  }))
  const snapshotEdges = (data?.snapshot_tree?.edges || []).map((edge: any, index: number) => ({
    id: `snap-${index}`,
    source: edge.source,
    target: edge.target,
  }))

  const tabs = [
    { key: 'workflow', label: '工作流', icon: <Network size={18} /> },
    { key: 'plots', label: '剧情树', icon: <Users size={18} /> },
    { key: 'snapshots', label: '版本树', icon: <GitBranch size={18} /> },
    { key: 'world3d', label: '3D地图', icon: <Map size={18} /> },
    { key: 'relationships3d', label: '3D关系', icon: <Orbit size={18} /> },
  ]

  const failedNodeEntry = currentExecution
    ? Object.entries(currentExecution.node_states).find(([, state]) => state.status === 'failed')
    : null
  const failedNodeState = failedNodeEntry?.[1]
  const operationSummary = executionOperationSummary || currentExecution?.operation_summary || null
  const operationCapabilities = operationSummary?.capabilities
  const currentStaleInspection = staleInspection || operationSummary?.stale_inspection || null
  const operationEventsNewestFirst = [...executionOperationEvents].reverse()
  const filteredOperationEvents = operationEventsNewestFirst.filter((event) => operationEventMatchesFilter(event, operationEventFilter))
  const selectedOperationEvent = filteredOperationEvents.find((event, index) => operationEventKey(event, index) === selectedOperationEventKey) || filteredOperationEvents[0] || null
  const selectedOperationEventPayload = selectedOperationEvent ? Object.entries(selectedOperationEvent.data || {}) : []
  const canPauseExecution = operationCapabilities?.pause?.allowed ?? currentExecutionStatus === 'running'
  const canResumeExecution = operationCapabilities?.resume?.allowed ?? currentExecutionStatus === 'paused'
  const canCancelExecution = operationCapabilities?.cancel?.allowed ?? isActiveExecutionStatus(currentExecutionStatus || undefined)
  const canRecoverExecution = operationCapabilities?.recover?.allowed ?? currentExecutionStatus === 'failed'
  const canRemediateExecution = operationCapabilities?.remediate?.allowed ?? currentExecutionStatus === 'failed'
  const agentTypeOptions = getAgentTypeOptions(nodeTypesData)
  const remediationPatchChanged = Boolean(
    failedNodeDiagnosis && (
      (remediationAgentType.trim() && remediationAgentType.trim() !== (failedNodeDiagnosis.current_agent_type || '')) ||
      (remediationScenario.trim() && remediationScenario.trim() !== (failedNodeDiagnosis.current_scenario || ''))
    ),
  )
  const remediationHistory = Array.isArray(currentExecution?.context?.remediation_history)
    ? currentExecution.context.remediation_history.filter((entry: unknown): entry is Record<string, any> => Boolean(entry && typeof entry === 'object'))
    : []
  const remediationHistoryNewestFirst = [...remediationHistory].reverse()
  const recoveryHistory: WorkflowRecoveryHistoryEntry[] = Array.isArray(currentExecution?.context?.recovery_history)
    ? currentExecution.context.recovery_history.filter((entry: unknown): entry is WorkflowRecoveryHistoryEntry => Boolean(entry && typeof entry === 'object'))
    : []
  const recoveryHistoryNewestFirst = [...recoveryHistory].reverse()
  const latestRecovery = recoveryHistory.length > 0 ? recoveryHistory[recoveryHistory.length - 1] : null
  const recoveryCursor = currentExecution?.resume_cursor || null
  const getRecoveryOutcome = (entry: WorkflowRecoveryHistoryEntry, indexFromNewest: number) => {
    if (indexFromNewest > 0) return '已被后续恢复覆盖'
    if (currentExecutionStatus === 'running' || currentExecutionStatus === 'pending') return '恢复执行中'
    if (currentExecutionStatus === 'completed') return '恢复后完成'
    if (currentExecutionStatus === 'failed') return '恢复后再次失败'
    return entry.attempt === latestRecovery?.attempt ? '状态未知' : '已被后续恢复覆盖'
  }
  const executionStatusTone = currentExecutionStatus === 'failed'
    ? 'border-red-200 bg-red-50 text-red-800'
    : currentExecutionStatus === 'completed'
      ? 'border-emerald-200 bg-emerald-50 text-emerald-800'
      : currentExecutionStatus === 'cancelled'
        ? 'border-gray-200 bg-gray-50 text-gray-700'
        : workflowSseState === 'degraded'
          ? 'border-amber-200 bg-amber-50 text-amber-800'
          : 'border-blue-200 bg-blue-50 text-blue-800'

  return (
    <PageLayout
      title="可视化工作台"
      description="可视化展示工作流、剧情树、版本树、多位面地图和角色关系网"
      tabs={tabs}
      activeTab={activeTab}
      onTabChange={(key) => setActiveTab(key as TabType)}
      actions={
        <div className="flex items-center gap-4">
          {activeTab === 'workflow' && (
            <>
              <input
                type="text"
                value={workflowName}
                onChange={(e) => setWorkflowName(e.target.value)}
                className={`px-3 py-1.5 rounded border text-sm ${
                  isDark ? 'bg-gray-800 border-gray-600 text-white' : 'bg-white border-gray-300'
                }`}
                placeholder="工作流名称"
              />
              <button
                onClick={handleSaveWorkflow}
                disabled={saving || !currentProject}
                className="flex items-center gap-1 px-3 py-1.5 bg-blue-500 text-white rounded text-sm hover:bg-blue-600 disabled:opacity-50"
              >
                <Save size={14} />
                {saving ? '保存中...' : '保存'}
              </button>
              <WorkflowHelp />
            </>
          )}
          <div className="w-48">
            <label className={`block text-sm font-medium mb-1 ${isDark ? 'text-gray-300' : 'text-gray-700'}`}>
              世界
            </label>
            <select
              className={`w-full px-3 py-2 border rounded-lg ${
                isDark ? 'bg-gray-800 border-gray-600 text-white' : 'bg-white border-gray-300'
              }`}
              value={selectedWorldId}
              onChange={(e) => setSelectedWorldId(e.target.value)}
            >
              <option value="">选择世界...</option>
              {worlds.map((world) => (
                <option key={world.id} value={world.id}>
                  {world.name || world.id}
                </option>
              ))}
            </select>
          </div>
        </div>
      }
    >
      {activeTab === 'workflow' ? (
        <>
          <div className="w-80 flex flex-col gap-3">
            <Card className="p-3">
              <div className="flex items-center justify-between mb-2">
                <h3 className={`text-sm font-semibold ${isDark ? 'text-gray-200' : 'text-gray-700'}`}>
                  工作流
                </h3>
                <div className="flex gap-2">
                  <button
                    onClick={handleNewWorkflow}
                    className="flex items-center gap-1 px-2 py-1 bg-green-500 text-white rounded text-xs hover:bg-green-600"
                  >
                    <Plus size={12} /> 新建
                  </button>
                  <button
                    onClick={handleLoadStandardWorkflow}
                    disabled={!currentProject}
                    className="px-2 py-1 bg-indigo-500 text-white rounded text-xs hover:bg-indigo-600 disabled:opacity-50"
                  >
                    标准全节点
                  </button>
                </div>
              </div>
              <div className="space-y-1 max-h-32 overflow-y-auto">
                {workflows.length === 0 ? (
                  <p className={`text-xs ${isDark ? 'text-gray-500' : 'text-gray-400'}`}>暂无</p>
                ) : (
                  workflows.map((wf) => (
                    <div
                      key={wf.id}
                      onClick={() => handleSelectWorkflow(wf)}
                      className={`p-1.5 rounded cursor-pointer text-xs flex justify-between items-center gap-2 ${
                        selectedWorkflow?.id === wf.id
                          ? 'bg-blue-100 text-blue-700'
                          : isDark
                            ? 'bg-gray-700 hover:bg-gray-600 text-gray-300'
                            : 'bg-gray-50 hover:bg-gray-100 text-gray-700'
                      }`}
                    >
                      <div className="min-w-0 flex-1 flex items-center gap-1.5">
                        <span className="truncate flex-1">{wf.name}</span>
                        {getWorkflowOrigin(wf) === 'global_template' && (
                          <span
                            className={`shrink-0 rounded px-1 py-0.5 text-[10px] ${
                              isDark ? 'bg-indigo-900 text-indigo-200' : 'bg-indigo-100 text-indigo-700'
                            }`}
                          >
                            模板
                          </span>
                        )}
                      </div>
                      {getWorkflowOrigin(wf) === 'project' ? (
                        <button
                          onClick={(e) => handleDeleteWorkflow(wf, e)}
                          className="text-red-500 hover:text-red-700 ml-2"
                          title="删除"
                        >
                          <Trash2 size={10} />
                        </button>
                      ) : (
                        <span className={`ml-2 text-[10px] ${isDark ? 'text-gray-400' : 'text-gray-500'}`}>
                          只读
                        </span>
                      )}
                    </div>
                  ))
                )}
              </div>
            </Card>

            <Card className="p-3">
              <div className="mb-2 flex items-center justify-between gap-2">
                <h3 className={`text-sm font-semibold ${isDark ? 'text-gray-200' : 'text-gray-700'}`}>
                  执行历史
                </h3>
                <button
                  onClick={() => void loadExecutionHistory()}
                  disabled={executionHistoryLoading || !currentProject}
                  className="text-xs text-blue-500 hover:text-blue-600 disabled:opacity-50"
                >
                  刷新
                </button>
              </div>
              <div className="mb-2 flex gap-1 text-[11px]">
                {[
                  { key: 'all', label: '全部' },
                  { key: 'running', label: '运行中' },
                  { key: 'failed', label: '失败' },
                  { key: 'completed', label: '完成' },
                ].map((item) => (
                  <button
                    key={item.key}
                    onClick={() => setExecutionHistoryStatusFilter(item.key as WorkflowStatus | 'all')}
                    className={`rounded px-2 py-1 ${
                      executionHistoryStatusFilter === item.key
                        ? 'bg-blue-600 text-white'
                        : isDark
                          ? 'bg-gray-700 text-gray-300 hover:bg-gray-600'
                          : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
                    }`}
                  >
                    {item.label}
                  </button>
                ))}
              </div>
              {executionHistoryError && (
                <div className="mb-2 rounded border border-red-200 bg-red-50 p-2 text-[11px] text-red-700">
                  {executionHistoryError}
                </div>
              )}
              <div className="max-h-52 space-y-1 overflow-y-auto">
                {executionHistoryLoading ? (
                  <div className="flex items-center gap-2 py-3 text-xs text-blue-500">
                    <Loader2 size={14} className="animate-spin" /> 加载执行历史...
                  </div>
                ) : executionHistory.length === 0 ? (
                  <div className={`py-3 text-xs ${isDark ? 'text-gray-500' : 'text-gray-400'}`}>
                    {selectedWorkflow ? '暂无执行历史' : '选择工作流后查看执行历史'}
                  </div>
                ) : executionHistory.map((row) => (
                  <div
                    key={row.id}
                    className={`rounded border p-2 text-xs ${
                      currentExecutionId === row.id
                        ? 'border-blue-400 bg-blue-50 text-blue-900'
                        : isDark
                          ? 'border-gray-700 bg-gray-800 text-gray-300 hover:bg-gray-700'
                          : 'border-gray-200 bg-white text-gray-700 hover:bg-gray-50'
                    }`}
                  >
                    <div
                      role="button"
                      tabIndex={0}
                      onClick={() => void inspectExecution(row.id)}
                      onKeyDown={(event) => {
                        if (event.key === 'Enter' || event.key === ' ') void inspectExecution(row.id)
                      }}
                      className="w-full cursor-pointer text-left"
                    >
                      <div className="mb-1 flex items-center justify-between gap-2">
                        <span className="font-mono text-[11px]">{shortExecutionId(row.id)}</span>
                        <span className={`rounded px-1.5 py-0.5 text-[10px] ${
                          row.status === 'failed'
                            ? 'bg-red-100 text-red-700'
                            : row.status === 'completed'
                              ? 'bg-emerald-100 text-emerald-700'
                              : isActiveExecutionStatus(row.status)
                                ? 'bg-blue-100 text-blue-700'
                                : 'bg-gray-100 text-gray-600'
                        }`}>{row.status}</span>
                      </div>
                      <div className="flex items-center justify-between text-[11px] opacity-75">
                        <span>{formatExecutionDate(row.started_at)}</span>
                        <span>{formatExecutionDuration(row.total_duration_ms)}</span>
                      </div>
                      <div className="mt-1 flex flex-wrap gap-1 text-[10px]">
                        {row.node_count != null && (
                          <span className="rounded bg-slate-100 px-1.5 py-0.5 text-slate-600">
                            {row.completed_node_count || 0}/{row.node_count} 节点
                          </span>
                        )}
                        {row.failed_node_id && (
                          <span className="rounded bg-red-100 px-1.5 py-0.5 text-red-700">
                            失败：{row.failed_node_id}
                          </span>
                        )}
                        {(row.recovery_count || 0) > 0 && (
                          <span className="rounded bg-amber-100 px-1.5 py-0.5 text-amber-700">
                            恢复 {row.recovery_count} 次
                          </span>
                        )}
                        {row.trace_id && (
                          <button
                            onClick={(event) => {
                              event.stopPropagation()
                              void inspectExecution(row.id, { openTrace: true })
                            }}
                            className="rounded bg-indigo-100 px-1.5 py-0.5 text-indigo-700 hover:bg-indigo-200"
                          >
                            Trace
                          </button>
                        )}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </Card>

            <Card className="p-3 flex-1 overflow-y-auto">
              {loadingNodeTypes ? (
                <div className="flex items-center justify-center h-32">
                  <Loader2 size={24} className="animate-spin text-blue-500" />
                </div>
              ) : (
                <>
                  <h3 className={`text-sm font-semibold mb-2 ${isDark ? 'text-gray-200' : 'text-gray-700'}`}>
                    可用节点
                  </h3>

                  <div className="mb-3">
                    <p className={`text-xs font-medium mb-2 ${isDark ? 'text-gray-400' : 'text-gray-500'}`}>
                      系统 Agent
                    </p>
                    <div className="grid grid-cols-2 gap-1">
                      {nodeTypesData.agent_nodes.map((node) => (
                        <button
                          key={node.agent_type || node.type}
                          onClick={() => handleAddNode(node)}
                          className={`text-left px-2 py-1.5 rounded text-xs transition-colors truncate ${
                            isDark
                              ? 'bg-gray-700 hover:bg-gray-600 text-gray-300'
                              : 'bg-gray-50 hover:bg-gray-100 text-gray-700'
                          }`}
                          title={node.label}
                        >
                          {node.label}
                        </button>
                      ))}
                    </div>
                  </div>

                  <div className="mb-3">
                    <p className={`text-xs font-medium mb-2 ${isDark ? 'text-gray-400' : 'text-gray-500'}`}>
                      交互节点
                    </p>
                    <div className="grid grid-cols-2 gap-1">
                      {nodeTypesData.interaction_nodes.map((node) => (
                        <button
                          key={node.type}
                          onClick={() => handleAddNode(node)}
                          className={`text-left px-2 py-1.5 rounded text-xs transition-colors truncate ${
                            isDark
                              ? 'bg-rose-900/50 hover:bg-rose-800/50 text-rose-300'
                              : 'bg-rose-50 hover:bg-rose-100 text-rose-700'
                          }`}
                          title={node.label}
                        >
                          {node.label}
                        </button>
                      ))}
                    </div>
                  </div>

                  <div>
                    <p className={`text-xs font-medium mb-2 ${isDark ? 'text-gray-400' : 'text-gray-500'}`}>
                      控制节点
                    </p>
                    <div className="grid grid-cols-2 gap-1">
                      {nodeTypesData.control_nodes
                        .filter((n) => n.type !== 'start' && n.type !== 'end')
                        .map((node) => (
                          <button
                            key={node.type}
                            onClick={() => handleAddNode(node)}
                            className={`text-left px-2 py-1.5 rounded text-xs transition-colors truncate ${
                              node.type === 'condition'
                                ? isDark
                                  ? 'bg-orange-900/50 hover:bg-orange-800/50 text-orange-300'
                                  : 'bg-orange-50 hover:bg-orange-100 text-orange-700'
                                : node.type === 'parallel'
                                  ? isDark
                                    ? 'bg-purple-900/50 hover:bg-purple-800/50 text-purple-300'
                                    : 'bg-purple-50 hover:bg-purple-100 text-purple-700'
                                  : isDark
                                    ? 'bg-gray-700 hover:bg-gray-600 text-gray-300'
                                    : 'bg-gray-50 hover:bg-gray-100 text-gray-700'
                            }`}
                            title={node.label}
                          >
                            {node.label}
                          </button>
                        ))}
                    </div>
                  </div>
                </>
              )}
            </Card>

            <Card className="p-3">
              <button
                onClick={() => handleExecuteWorkflow()}
                disabled={executing || startPrechecking || !selectedWorkflow || Boolean(currentExecutionId && isActiveExecutionStatus(currentExecutionStatus || undefined)) || !!startPrecheckError || !startPrecheckOutline}
                className="w-full flex items-center justify-center gap-2 px-3 py-2 bg-green-500 text-white rounded text-sm hover:bg-green-600 disabled:opacity-50"
                title={startPrecheckError || (!startPrecheckOutline ? '等待启动前预检完成' : '')}
              >
                <Play size={14} />
                {executing ? '执行中...' : startPrechecking ? '预检中...' : currentExecutionId && isActiveExecutionStatus(currentExecutionStatus || undefined) ? '已有执行运行中' : '执行'}
              </button>
              <div className="mt-2 flex items-center gap-2">
                <button
                  onClick={() => { void loadStartReadinessPrecheck() }}
                  disabled={startPrechecking}
                  className="flex-1 px-3 py-2 rounded bg-gray-100 text-gray-700 text-sm hover:bg-gray-200 disabled:opacity-50"
                >
                  刷新预检
                </button>
                {startPrecheckOutline && (
                  <div className="flex-1 text-xs text-gray-500 text-right truncate" title={`第 ${startPrecheckOutline.chapter_number} 章《${startPrecheckOutline.title}》`}>
                    启动目标：第 {startPrecheckOutline.chapter_number} 章
                  </div>
                )}
              </div>
              <div className={`mt-2 rounded-xl border p-3 text-xs ${
                startPrecheckError
                  ? 'border-red-200 bg-red-50 text-red-800'
                  : startPrecheckAdvisoryRequirements.length > 0
                    ? 'border-amber-200 bg-amber-50 text-amber-800'
                    : 'border-emerald-200 bg-emerald-50 text-emerald-800'
              }`}>
                {startPrechecking ? (
                  <div className="flex items-center gap-2"><span className="h-2 w-2 animate-pulse rounded-full bg-current" />正在检查已审批大纲和章节资源 readiness...</div>
                ) : startPrecheckOutline ? (
                  <div className="space-y-2">
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="font-semibold">第 {startPrecheckOutline.chapter_number} 章</span>
                      <span className={`rounded-full px-2 py-0.5 text-[11px] font-semibold uppercase tracking-wide ${startPrecheckError ? 'bg-red-600 text-white' : startPrecheckAdvisoryRequirements.length > 0 ? 'bg-amber-500 text-white' : 'bg-emerald-600 text-white'}`}>
                        {getReadinessStatusLabel(startPrecheckReadiness?.readiness_status || (startPrecheckError ? 'blocked' : 'ready'))}
                      </span>
                      <span>blocking {startPrecheckBlockingRequirements.length}</span>
                      <span>advisory {startPrecheckAdvisoryRequirements.length}</span>
                    </div>
                    {startPrecheckError && <div className="font-medium">{startPrecheckError}</div>}
                    {[...startPrecheckBlockingRequirements, ...startPrecheckAdvisoryRequirements].slice(0, 4).map(requirement => (
                      <a
                        key={requirement.id}
                        href={getRequirementRecoveryPath(requirement)}
                        className="block rounded-lg border border-white/70 bg-white/70 px-3 py-2 hover:bg-white"
                      >
                        <div className="font-medium">{formatRequirementSummary(requirement)}</div>
                        <div className="mt-1 opacity-80">{getRequirementRecoveryActionLabel(requirement)}</div>
                      </a>
                    ))}
                  </div>
                ) : startPrecheckError ? (
                  <div>{startPrecheckError}</div>
                ) : (
                  <div>等待启动前预检...</div>
                )}
              </div>
              {currentExecutionId && (
                <div className="mt-2 space-y-2 text-xs">
                  <div className="truncate text-gray-500" title={currentExecutionId}>执行ID: {currentExecutionId}</div>
                  <div className={`rounded-xl border p-3 ${executionStatusTone}`}>
                    <div className="mb-2 flex items-center justify-between gap-2">
                      <span className="font-semibold">执行状态：{currentExecutionStatus || 'unknown'}</span>
                      <span className="rounded-full bg-white/70 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide">
                        {workflowSseState === 'connected' ? '实时' : workflowSseState === 'degraded' ? '轮询降级' : workflowSseState === 'connecting' ? '连接中' : '已断开'}
                      </span>
                    </div>
                    <div className="space-y-1">
                      {currentExecution?.current_node && <div>当前节点：{currentExecution.current_node}</div>}
                      {currentExecution?.trace_id && <div className="truncate" title={currentExecution.trace_id}>Trace：{currentExecution.trace_id}</div>}
                      {workflowSseMessage && <div>{workflowSseMessage}</div>}
                      {currentExecution?.error && <div className="font-medium">工作流错误：{currentExecution.error}</div>}
                      {failedNodeState && (
                        <div className="rounded-lg bg-white/70 p-2">
                          <div className="font-semibold">失败节点：{failedNodeState.node_id}</div>
                          {failedNodeState.error && <div className="mt-1 whitespace-pre-wrap">{failedNodeState.error}</div>}
                        </div>
                      )}
                      {currentExecutionStatus === 'failed' && failedNodeState && (
                        <div className="rounded-lg border border-red-200 bg-white/80 p-2 text-red-800">
                          <div className="mb-2 flex items-center justify-between gap-2">
                            <span className="font-semibold">失败诊断与恢复</span>
                            {failedNodeDiagnosis && (
                              <span className="rounded-full bg-red-100 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide">
                                {failedNodeDiagnosis.category}
                              </span>
                            )}
                          </div>
                          <div className="mb-2 text-[11px] leading-relaxed opacity-80">
                            先判断失败是否可直接重试；若是确定性配置错误，可保存安全修复并继续使用当前执行 ID 恢复。
                          </div>
                          {failedNodeDiagnosisLoading ? (
                            <div className="mb-2 rounded bg-red-50 p-2 text-[11px]">正在加载失败节点诊断...</div>
                          ) : failedNodeDiagnosisError ? (
                            <div className="mb-2 rounded bg-red-50 p-2 text-[11px] font-medium whitespace-pre-wrap">{failedNodeDiagnosisError}</div>
                          ) : failedNodeDiagnosis ? (
                            <div className="mb-2 space-y-2 text-[11px]">
                              <div className="rounded border border-red-100 bg-red-50 p-2">
                                <div className="font-semibold">{failedNodeDiagnosis.summary}</div>
                                <div className="mt-1">失败节点：{failedNodeDiagnosis.failed_node_label || failedNodeDiagnosis.failed_node_id}</div>
                                <div className="mt-1">当前 Agent：{failedNodeDiagnosis.current_agent_type || '-'}</div>
                                {failedNodeDiagnosis.current_scenario && <div className="mt-1">当前场景：{failedNodeDiagnosis.current_scenario}</div>}
                                {failedNodeDiagnosis.retry_without_fix_likely_to_fail && (
                                  <div className="mt-2 rounded bg-white px-2 py-1 font-medium text-red-700">
                                    诊断认为直接重试大概率会再次失败，建议先修复配置。
                                  </div>
                                )}
                                {failedNodeDiagnosis.evidence.length > 0 && (
                                  <div className="mt-2 max-h-16 overflow-y-auto whitespace-pre-wrap rounded bg-white p-1 text-red-700">
                                    证据：{failedNodeDiagnosis.evidence.join('\n')}
                                  </div>
                                )}
                              </div>
                              {failedNodeDiagnosis.remediable && (
                                <div className="rounded border border-amber-200 bg-amber-50 p-2 text-amber-900">
                                  <div className="mb-2 font-semibold">安全修复补丁</div>
                                  <label className="mb-1 block font-medium">替换 Agent 类型</label>
                                  <select
                                    value={remediationAgentType}
                                    onChange={(event) => setRemediationAgentType(event.target.value)}
                                    className="mb-2 w-full rounded border border-amber-200 bg-white px-2 py-1 text-[11px] outline-none focus:border-amber-400"
                                  >
                                    <option value="">选择 Agent 类型</option>
                                    {agentTypeOptions.map((option) => (
                                      <option key={option.value} value={option.value}>{option.label} · {option.value}</option>
                                    ))}
                                  </select>
                                  <label className="mb-1 block font-medium">场景（可选）</label>
                                  <input
                                    value={remediationScenario}
                                    onChange={(event) => setRemediationScenario(event.target.value)}
                                    maxLength={80}
                                    className="mb-2 w-full rounded border border-amber-200 bg-white px-2 py-1 text-[11px] outline-none focus:border-amber-400"
                                    placeholder="保留为空或输入新 scenario"
                                  />
                                  <div className="mb-2 rounded bg-white p-2 text-[10px]">
                                    <div className="font-semibold">补丁预览</div>
                                    <div>Agent：{failedNodeDiagnosis.current_agent_type || '-'} → {remediationAgentType.trim() || '-'}</div>
                                    <div>场景：{failedNodeDiagnosis.current_scenario || '-'} → {remediationScenario.trim() || '-'}</div>
                                  </div>
                                  <button
                                    onClick={handleRemediateAndRecoverExecution}
                                    disabled={remediatingExecution || executing || !remediationPatchChanged || !canRemediateExecution}
                                    className="w-full rounded bg-amber-600 px-2 py-1 text-white hover:bg-amber-700 disabled:opacity-50"
                                    title={operationCapabilities?.remediate?.reason || ''}
                                  >
                                    {remediatingExecution ? '修复恢复中...' : '保存修复并从失败节点恢复'}
                                  </button>
                                </div>
                              )}
                            </div>
                          ) : null}
                          <label className="mb-1 block text-[11px] font-medium">恢复/修复原因</label>
                          <input
                            value={recoveryReason}
                            onChange={(event) => setRecoveryReason(event.target.value)}
                            maxLength={120}
                            className="mb-2 w-full rounded border border-red-200 bg-white px-2 py-1 text-[11px] text-red-900 outline-none focus:border-red-400"
                            placeholder="visualize_manual_recovery"
                          />
                          <button
                            onClick={handleRecoverExecution}
                            disabled={recoveringExecution || remediatingExecution || executing || !canRecoverExecution}
                            className="w-full rounded bg-red-600 px-2 py-1 text-white hover:bg-red-700 disabled:opacity-50"
                            title={operationCapabilities?.recover?.reason || ''}
                          >
                            {recoveringExecution ? '恢复中...' : '从失败节点重试'}
                          </button>
                        </div>
                      )}
                      {remediationHistory.length > 0 && (
                        <div className="rounded-lg border border-orange-200 bg-white/80 p-2 text-orange-900">
                          <div className="mb-2 flex items-center justify-between gap-2">
                            <span className="font-semibold">修复审计</span>
                            <span className="rounded bg-orange-100 px-1.5 py-0.5 text-[10px]">{remediationHistory.length} 次</span>
                          </div>
                          <div className="space-y-2">
                            {remediationHistoryNewestFirst.slice(0, 3).map((entry, index) => {
                              const diff = entry.diff || {}
                              const before = diff.before || {}
                              const after = diff.after || {}
                              return (
                                <div key={`${entry.node_id || index}-${entry.applied_at || index}`} className="rounded border border-orange-100 bg-white p-2 text-[11px]">
                                  <div className="mb-1 flex items-center justify-between gap-2">
                                    <span className="font-semibold">{entry.node_id || '-'}</span>
                                    <span className="rounded bg-orange-100 px-1.5 py-0.5 text-[10px]">{entry.diagnosis_category || 'unknown'}</span>
                                  </div>
                                  <div>原因：{entry.reason || '-'}</div>
                                  <div>时间：{formatExecutionDate(entry.applied_at || entry.started_at)}</div>
                                  {before.agent_type !== undefined || after.agent_type !== undefined ? (
                                    <div>Agent：{before.agent_type || '-'} → {after.agent_type || '-'}</div>
                                  ) : null}
                                  {before.scenario !== undefined || after.scenario !== undefined ? (
                                    <div>场景：{before.scenario || '-'} → {after.scenario || '-'}</div>
                                  ) : null}
                                </div>
                              )
                            })}
                          </div>
                        </div>
                      )}
                      {recoveryHistory.length > 0 && (
                        <div className="rounded-lg border border-amber-200 bg-white/80 p-2 text-amber-900">
                          <div className="mb-2 flex items-center justify-between gap-2">
                            <span className="font-semibold">恢复审计</span>
                            <span className="rounded bg-amber-100 px-1.5 py-0.5 text-[10px]">{recoveryHistory.length} 次</span>
                          </div>
                          {recoveryCursor && (
                            <div className="mb-2 rounded bg-amber-50 p-2 text-[11px]">
                              <div>游标：#{recoveryCursor.recovery_attempt || '-'} · {recoveryCursor.recovered_node_id || '-'}</div>
                              {Array.isArray(recoveryCursor.reset_node_ids) && (
                                <div className="mt-1 truncate" title={recoveryCursor.reset_node_ids.join(', ')}>
                                  重置：{recoveryCursor.reset_node_ids.join(', ')}
                                </div>
                              )}
                            </div>
                          )}
                          <div className="space-y-2">
                            {recoveryHistoryNewestFirst.slice(0, 4).map((entry, index) => (
                              <div key={`${entry.attempt || index}-${entry.started_at || index}`} className="rounded border border-amber-100 bg-white p-2 text-[11px]">
                                <div className="mb-1 flex items-center justify-between gap-2">
                                  <span className="font-semibold">Attempt #{entry.attempt || '?'}</span>
                                  <span className="rounded bg-amber-100 px-1.5 py-0.5 text-[10px]">{getRecoveryOutcome(entry, index)}</span>
                                </div>
                                <div>目标：{entry.target_node_id || '-'}</div>
                                <div>模式：{entry.mode || '-'}</div>
                                <div>原因：{entry.reason || '-'}</div>
                                <div>时间：{formatExecutionDate(entry.started_at)}</div>
                                {Array.isArray(entry.reset_node_ids) && entry.reset_node_ids.length > 0 && (
                                  <div className="truncate" title={entry.reset_node_ids.join(', ')}>
                                    重置 {entry.reset_node_ids.length} 个：{entry.reset_node_ids.join(', ')}
                                  </div>
                                )}
                                {entry.previous_error && (
                                  <div className="mt-1 max-h-12 overflow-y-auto whitespace-pre-wrap rounded bg-red-50 p-1 text-red-700">
                                    上次错误：{entry.previous_error}
                                  </div>
                                )}
                              </div>
                            ))}
                          </div>
                        </div>
                      )}
                      {executionRestoreError && (
                        <div className="rounded-lg border border-red-200 bg-red-50 p-2 text-red-800">
                          <div className="font-semibold">执行恢复失败</div>
                          <div className="mt-1 whitespace-pre-wrap">{executionRestoreError}</div>
                        </div>
                      )}
                      {operationSummary && (
                        <div className="rounded-lg border border-slate-200 bg-white/80 p-2 text-slate-800">
                          <div className="mb-2 flex items-center justify-between gap-2">
                            <span className="font-semibold">运行操作台</span>
                            <span className="rounded bg-slate-100 px-1.5 py-0.5 text-[10px]">
                              {operationSummary.active_task ? '任务活跃' : operationSummary.terminal ? '终态' : '可操作'}
                            </span>
                          </div>
                          <div className="grid grid-cols-2 gap-1 text-[11px]">
                            <div>节点：{operationSummary.node_summary.total}</div>
                            <div>失败：{operationSummary.node_summary.counts.failed || 0}</div>
                            <div>恢复：{operationSummary.recovery.count} 次</div>
                            <div>修复：{operationSummary.remediation.count} 次</div>
                            <div>陈旧：{operationSummary.stale.count} 次</div>
                            <div>租约：{operationSummary.lease.expired ? '已过期' : operationSummary.lease.seconds_remaining !== null && operationSummary.lease.seconds_remaining !== undefined ? `${operationSummary.lease.seconds_remaining}s` : '-'}</div>
                          </div>
                          {operationSummary.attention.length > 0 && (
                            <div className="mt-2 space-y-1">
                              {operationSummary.attention.slice(0, 3).map((item) => (
                                <div key={`${item.type}-${item.message}`} className="rounded bg-slate-50 px-2 py-1 text-[11px]">
                                  {item.message}
                                </div>
                              ))}
                            </div>
                          )}
                          <div className="mt-2 rounded-lg border border-slate-200 bg-slate-50 p-2 text-[11px]">
                            <div className="mb-1 flex items-center justify-between gap-2">
                              <span className="font-semibold">陈旧执行治理</span>
                              <span className={`rounded px-1.5 py-0.5 text-[10px] ${currentStaleInspection?.suspected_stale ? 'bg-red-100 text-red-700' : 'bg-slate-200 text-slate-700'}`}>
                                {currentStaleInspection?.suspected_stale ? '疑似陈旧' : '状态正常'}
                              </span>
                            </div>
                            <div className="mb-2 rounded border border-amber-200 bg-amber-50 px-2 py-1 text-[10px] text-amber-800">
                              工作流界面只负责结构完整性、诊断与治理验证；实际生成运行请在 Director 发起，章节编辑/版本对比在 Novel/Diff 界面处理。
                            </div>
                            <div className="space-y-0.5 opacity-80">
                              <div>活跃任务：{currentStaleInspection?.active_task ? '存在' : '无'}</div>
                              <div>建议：{currentStaleInspection?.recommendation || '点击检查获取治理建议。'}</div>
                            </div>
                            <div className="mt-2 flex gap-1">
                              <button
                                type="button"
                                onClick={handleInspectStaleExecution}
                                disabled={!currentExecutionId || staleInspectionLoading}
                                className="rounded bg-white px-2 py-1 text-[10px] text-slate-700 shadow-sm hover:bg-slate-100 disabled:opacity-50"
                              >
                                {staleInspectionLoading ? '检查中...' : '检查'}
                              </button>
                              <button
                                type="button"
                                onClick={handleMarkExecutionStaleFailed}
                                disabled={!currentExecutionId || staleActionLoading || !currentStaleInspection?.suspected_stale}
                                className="rounded bg-red-600 px-2 py-1 text-[10px] text-white shadow-sm hover:bg-red-700 disabled:opacity-50"
                                title={currentStaleInspection?.suspected_stale ? '' : '仅租约过期且无活跃任务时可标记'}
                              >
                                {staleActionLoading ? '处理中...' : '标记失败'}
                              </button>
                              <button
                                type="button"
                                onClick={handleCreateStaleRuntimeFixture}
                                disabled={!currentProject || runtimeFixtureLoading}
                                className="rounded bg-amber-100 px-2 py-1 text-[10px] text-amber-800 shadow-sm hover:bg-amber-200 disabled:opacity-50"
                                title="DEBUG-only：创建隔离 stale-running 夹具用于验证治理链路"
                              >
                                {runtimeFixtureLoading ? '创建中...' : '创建陈旧夹具'}
                              </button>
                              {runtimeFixture && (
                                <button
                                  type="button"
                                  onClick={handleCleanupRuntimeFixture}
                                  disabled={runtimeFixtureCleanupLoading}
                                  className="rounded bg-slate-200 px-2 py-1 text-[10px] text-slate-700 shadow-sm hover:bg-slate-300 disabled:opacity-50"
                                >
                                  {runtimeFixtureCleanupLoading ? '清理中...' : '清理夹具'}
                                </button>
                              )}
                            </div>
                            {runtimeFixture && (
                              <div className="mt-1 text-[10px] text-slate-500">
                                当前夹具：{shortExecutionId(runtimeFixture.executionId)} · token 已绑定，仅允许清理本次创建的数据。
                              </div>
                            )}
                          </div>
                        </div>
                      )}
                      {executionOperationEvents.length > 0 && (
                        <div className="rounded-lg border border-indigo-200 bg-white/80 p-2 text-indigo-900">
                          <div className="mb-2 flex items-center justify-between gap-2">
                            <span className="font-semibold">操作事件时间线</span>
                            <button
                              type="button"
                              onClick={() => setExecutionAuditPanelOpen(true)}
                              className="rounded bg-indigo-100 px-1.5 py-0.5 text-[10px] hover:bg-indigo-200"
                            >
                              审计 {executionOperationEvents.length} 条
                            </button>
                          </div>
                          <div className="max-h-44 space-y-2 overflow-y-auto">
                            {operationEventsNewestFirst.slice(0, 8).map((event, index) => (
                              <button
                                type="button"
                                key={operationEventKey(event, index)}
                                onClick={() => {
                                  setSelectedOperationEventKey(operationEventKey(event, index))
                                  setExecutionAuditPanelOpen(true)
                                }}
                                className="w-full rounded border border-indigo-100 bg-white p-2 text-left text-[11px] transition hover:-translate-y-0.5 hover:border-indigo-300 hover:shadow-sm"
                              >
                                <div className="mb-1 flex items-center justify-between gap-2">
                                  <span className="font-semibold">{event.summary}</span>
                                  <span className={`rounded px-1.5 py-0.5 text-[10px] ${event.severity === 'error' ? 'bg-red-100 text-red-700' : 'bg-indigo-100 text-indigo-700'}`}>
                                    {event.event_type}
                                  </span>
                                </div>
                                <div className="flex items-center justify-between gap-2 opacity-75">
                                  <span>{formatExecutionDate(event.created_at)}</span>
                                  {event.node_id && <span className="truncate" title={event.node_id}>节点：{event.node_id}</span>}
                                </div>
                              </button>
                            ))}
                          </div>
                        </div>
                      )}
                      {executionActionError && <div className="font-medium whitespace-pre-wrap">{executionActionError}</div>}
                      {(currentExecution?.error || failedNodeState || executionActionError) && (
                        <div className="opacity-80">可切换右侧 Trace 面板查看调用链和产物详情。</div>
                      )}
                    </div>
                  </div>
                  <div className="grid grid-cols-3 gap-1">
                    <button
                      onClick={handlePauseExecution}
                      disabled={!canPauseExecution}
                      title={operationCapabilities?.pause?.reason || ''}
                      className="flex items-center justify-center gap-1 px-2 py-1 rounded bg-yellow-100 text-yellow-700 disabled:opacity-50"
                    >
                      <Pause size={12} /> 暂停
                    </button>
                    <button
                      onClick={handleResumeExecution}
                      disabled={!canResumeExecution}
                      title={operationCapabilities?.resume?.reason || ''}
                      className="flex items-center justify-center gap-1 px-2 py-1 rounded bg-blue-100 text-blue-700 disabled:opacity-50"
                    >
                      <RotateCcw size={12} /> 恢复
                    </button>
                    <button
                      onClick={handleCancelExecution}
                      disabled={!canCancelExecution}
                      title={operationCapabilities?.cancel?.reason || ''}
                      className="flex items-center justify-center gap-1 px-2 py-1 rounded bg-red-100 text-red-700 disabled:opacity-50"
                    >
                      <Square size={12} /> 取消
                    </button>
                  </div>
                  {hasPendingDiscussionConfirmation && (
                    <div className="rounded border border-indigo-200 bg-indigo-50 p-2 text-indigo-700">
                      <div className="mb-2 font-medium">集体讨论已完成，请确认讨论结果后继续流程。</div>
                      <div className="grid grid-cols-2 gap-1">
                        <button
                          onClick={() => handleConfirmDiscussion(true)}
                          className="px-2 py-1 rounded bg-indigo-600 text-white hover:bg-indigo-700"
                        >
                          同意讨论
                        </button>
                        <button
                          onClick={() => handleConfirmDiscussion(false)}
                          className="px-2 py-1 rounded bg-white text-indigo-700 border border-indigo-200 hover:bg-indigo-100"
                        >
                          返工讨论
                        </button>
                      </div>
                    </div>
                  )}
                  {isInputPause && (
                    <div className="rounded border border-blue-200 bg-blue-50 p-2 text-blue-700">
                      当前暂停在用户输入节点；点击“恢复”继续后续节点。
                    </div>
                  )}
                  <button
                    onClick={handleForceNewExecution}
                    disabled={executing || startPrechecking || !selectedWorkflow}
                    className="w-full px-2 py-1 rounded border border-gray-300 text-gray-600 hover:bg-gray-50 disabled:opacity-50"
                  >
                    强制新执行
                  </button>
                </div>
              )}
            </Card>
          </div>

          <div className="flex-1 flex gap-4 min-w-0">
            <div
              className="flex-1 border-2 border-dashed border-gray-300 rounded-xl overflow-hidden"
              style={{ height: 'calc(100vh - 280px)', minHeight: '500px' }}
            >
              {nodes.length === 0 ? (
                <div className="h-full flex flex-col items-center justify-center text-gray-400">
                  <Network size={48} className="mb-4 opacity-50" />
                  <p className="text-lg mb-2">点击“新建工作流”开始创建</p>
                  <p className="text-sm">或使用“标准全节点”直接加载一个可执行工作流</p>
                </div>
              ) : (
                <ReactFlow
                  nodes={nodes}
                  edges={edges}
                  onNodesChange={onNodesChange}
                  onEdgesChange={onEdgesChange}
                  onConnect={onConnect}
                  nodeTypes={nodeTypes}
                  fitView
                  selectNodesOnDrag={false}
                  panOnScroll
                  selectionOnDrag
                  proOptions={{ hideAttribution: true }}
                >
                  <MiniMap />
                  <Controls />
                  <Background color={isDark ? '#374151' : '#e5e7eb'} gap={16} />
                  <Panel position="top-right">
                    <div className="flex gap-2">
                      <button
                        onClick={handleDeleteSelectedNodes}
                        className={`px-3 py-1.5 rounded text-sm ${
                          isDark
                            ? 'bg-red-900 text-red-200 hover:bg-red-800'
                            : 'bg-red-100 text-red-700 hover:bg-red-200'
                        }`}
                        title="删除选中节点 (Delete)"
                      >
                        <Trash2 size={14} className="inline mr-1" /> 删除选中
                      </button>
                      <button
                        onClick={() => {
                          setNodes((nds) => nds.filter((node) => node.id === 'start' || node.id === 'end'))
                          setEdges([])
                        }}
                        className={`px-3 py-1.5 rounded text-sm ${
                          isDark
                            ? 'bg-gray-800 text-gray-300 hover:bg-gray-700'
                            : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
                        }`}
                        title="清空所有节点（保留开始和结束）"
                      >
                        清空
                      </button>
                    </div>
                  </Panel>
                </ReactFlow>
              )}
            </div>

            <div
              className="w-[360px] border rounded-xl overflow-hidden flex flex-col"
              style={{ height: 'calc(100vh - 280px)', minHeight: '500px' }}
            >
              <div className={`flex border-b ${isDark ? 'border-gray-700 bg-gray-900' : 'border-gray-200 bg-white'}`}>
                <button
                  onClick={() => setRightWorkflowPanel('monitor')}
                  className={`flex-1 px-3 py-2 text-sm ${
                    rightWorkflowPanel === 'monitor'
                      ? 'border-b-2 border-blue-500 text-blue-600'
                      : isDark
                        ? 'text-gray-400 hover:text-gray-200'
                        : 'text-gray-500 hover:text-gray-700'
                  }`}
                >
                  监控
                </button>
                <button
                  onClick={() => setRightWorkflowPanel('trace')}
                  className={`flex-1 px-3 py-2 text-sm ${
                    rightWorkflowPanel === 'trace'
                      ? 'border-b-2 border-blue-500 text-blue-600'
                      : isDark
                        ? 'text-gray-400 hover:text-gray-200'
                        : 'text-gray-500 hover:text-gray-700'
                  }`}
                >
                  Trace
                </button>
              </div>
              <div className="flex-1 overflow-hidden">
                {rightWorkflowPanel === 'monitor' ? (
                  <WorkflowMonitor
                    executionId={currentExecutionId}
                    onExecutionChange={applyExecutionState}
                    onConnectionStateChange={(state, message) => {
                      setWorkflowSseState(state)
                      setWorkflowSseMessage(message || '')
                    }}
                  />
                ) : (
                  <WorkflowTrace executionId={currentExecutionId} />
                )}
              </div>
            </div>
          </div>
          {executionAuditPanelOpen && activeTab === 'workflow' && (
            <div className="fixed inset-0 z-50 flex justify-end bg-slate-950/35 backdrop-blur-[2px]" onClick={() => setExecutionAuditPanelOpen(false)}>
              <div
                className={`h-full w-full max-w-4xl overflow-hidden border-l shadow-2xl ${
                  isDark ? 'border-slate-700 bg-slate-950 text-slate-100' : 'border-slate-200 bg-[#f8f6ef] text-slate-950'
                }`}
                onClick={(event) => event.stopPropagation()}
              >
                <div className={`border-b px-5 py-4 ${isDark ? 'border-slate-800 bg-slate-900' : 'border-stone-300 bg-stone-100'}`}>
                  <div className="flex items-start justify-between gap-4">
                    <div>
                      <div className="flex items-center gap-2 text-xs uppercase tracking-[0.28em] text-indigo-500">
                        <FileClock size={15} /> Operation Ledger
                      </div>
                      <h2 className="mt-1 text-2xl font-semibold tracking-tight">执行审计事件</h2>
                      <p className={`mt-1 text-sm ${isDark ? 'text-slate-400' : 'text-slate-600'}`}>
                        {currentExecutionId ? `Execution ${currentExecutionId}` : '未选择执行'} · 已脱敏展示运行、失败、修复、恢复和租约事件
                      </p>
                    </div>
                    <button
                      type="button"
                      onClick={() => setExecutionAuditPanelOpen(false)}
                      className={`rounded-full px-3 py-1 text-sm ${isDark ? 'bg-slate-800 hover:bg-slate-700' : 'bg-white hover:bg-stone-200'}`}
                    >
                      关闭
                    </button>
                  </div>
                  <div className="mt-4 flex flex-wrap gap-2 text-xs">
                    {[
                      ['all', '全部'],
                      ['lifecycle', '生命周期'],
                      ['node', '节点'],
                      ['failure', '失败'],
                      ['recovery', '恢复'],
                      ['remediation', '修复'],
                      ['stale', '陈旧'],
                    ].map(([key, label]) => (
                      <button
                        type="button"
                        key={key}
                        onClick={() => {
                          setOperationEventFilter(key as typeof operationEventFilter)
                          setSelectedOperationEventKey(null)
                        }}
                        className={`rounded-full border px-3 py-1 transition ${
                          operationEventFilter === key
                            ? 'border-indigo-500 bg-indigo-600 text-white shadow-sm'
                            : isDark
                              ? 'border-slate-700 bg-slate-900 text-slate-300 hover:border-indigo-500'
                              : 'border-stone-300 bg-white text-slate-700 hover:border-indigo-400'
                        }`}
                      >
                        {label}
                      </button>
                    ))}
                  </div>
                </div>
                <div className="grid h-[calc(100%-132px)] grid-cols-[310px_1fr]">
                  <div className={`overflow-y-auto border-r p-3 ${isDark ? 'border-slate-800' : 'border-stone-300'}`}>
                    {filteredOperationEvents.length === 0 ? (
                      <div className={`rounded-xl border border-dashed p-4 text-sm ${isDark ? 'border-slate-700 text-slate-400' : 'border-stone-300 text-slate-500'}`}>
                        当前过滤条件下暂无事件。
                      </div>
                    ) : filteredOperationEvents.map((event, index) => {
                      const key = operationEventKey(event, index)
                      const selected = selectedOperationEventKey ? selectedOperationEventKey === key : index === 0
                      return (
                        <button
                          type="button"
                          key={key}
                          onClick={() => setSelectedOperationEventKey(key)}
                          className={`mb-2 w-full rounded-xl border p-3 text-left transition ${
                            selected
                              ? 'border-indigo-500 bg-indigo-600 text-white shadow-lg shadow-indigo-900/20'
                              : isDark
                                ? 'border-slate-800 bg-slate-900 text-slate-200 hover:border-slate-600'
                                : 'border-stone-300 bg-white text-slate-800 hover:border-indigo-300'
                          }`}
                        >
                          <div className="mb-1 flex items-center justify-between gap-2">
                            <span className="truncate text-sm font-semibold">{event.summary}</span>
                            <span className={`rounded px-1.5 py-0.5 text-[10px] ${event.severity === 'error' ? 'bg-red-100 text-red-700' : selected ? 'bg-white/20 text-white' : 'bg-indigo-100 text-indigo-700'}`}>
                              {operationEventCategory(event)}
                            </span>
                          </div>
                          <div className={`text-[11px] ${selected ? 'text-white/75' : isDark ? 'text-slate-400' : 'text-slate-500'}`}>
                            #{event.sequence_no ?? '-'} · {event.event_type}
                          </div>
                          <div className={`mt-1 text-[11px] ${selected ? 'text-white/75' : isDark ? 'text-slate-500' : 'text-slate-500'}`}>
                            {formatExecutionDate(event.created_at)}
                          </div>
                        </button>
                      )
                    })}
                  </div>
                  <div className="overflow-y-auto p-5">
                    {selectedOperationEvent ? (
                      <div className="space-y-4">
                        <div className={`rounded-2xl border p-4 ${isDark ? 'border-slate-800 bg-slate-900' : 'border-stone-300 bg-white'}`}>
                          <div className="flex items-start justify-between gap-4">
                            <div>
                              <div className="text-xs uppercase tracking-[0.22em] text-indigo-500">{selectedOperationEvent.event_type}</div>
                              <h3 className="mt-1 text-xl font-semibold">{selectedOperationEvent.summary}</h3>
                            </div>
                            <span className={`rounded-full px-2 py-1 text-xs ${selectedOperationEvent.severity === 'error' ? 'bg-red-100 text-red-700' : 'bg-indigo-100 text-indigo-700'}`}>
                              {selectedOperationEvent.severity}
                            </span>
                          </div>
                          <div className="mt-4 grid grid-cols-2 gap-3 text-sm">
                            <div><span className="opacity-60">Sequence</span><div className="font-mono">{selectedOperationEvent.sequence_no ?? '-'}</div></div>
                            <div><span className="opacity-60">时间</span><div>{formatExecutionDate(selectedOperationEvent.created_at)}</div></div>
                            <div><span className="opacity-60">节点</span><div className="font-mono">{selectedOperationEvent.node_id || '-'}</div></div>
                            <div><span className="opacity-60">状态</span><div>{selectedOperationEvent.status || '-'}</div></div>
                          </div>
                          <div className="mt-4 flex flex-wrap gap-2">
                            {selectedOperationEvent.node_id && (
                              <button
                                type="button"
                                onClick={() => {
                                  setNodes((current) => current.map((node) => ({ ...node, selected: node.id === selectedOperationEvent.node_id })))
                                  setExecutionAuditPanelOpen(false)
                                }}
                                className="rounded bg-indigo-600 px-3 py-1.5 text-xs text-white hover:bg-indigo-700"
                              >
                                定位节点
                              </button>
                            )}
                            {(selectedOperationEvent.data?.trace_id || currentExecution?.trace_id) && (
                              <button
                                type="button"
                                onClick={() => {
                                  setRightWorkflowPanel('trace')
                                  setExecutionAuditPanelOpen(false)
                                }}
                                className={`rounded px-3 py-1.5 text-xs ${isDark ? 'bg-slate-800 hover:bg-slate-700' : 'bg-stone-100 hover:bg-stone-200'}`}
                              >
                                打开 Trace
                              </button>
                            )}
                          </div>
                        </div>
                        <div className={`rounded-2xl border p-4 ${isDark ? 'border-slate-800 bg-slate-900' : 'border-stone-300 bg-white'}`}>
                          <div className="mb-3 flex items-center gap-2 text-sm font-semibold">
                            <ShieldAlert size={15} /> 脱敏事件载荷
                          </div>
                          {selectedOperationEventPayload.length === 0 ? (
                            <div className={`text-sm ${isDark ? 'text-slate-400' : 'text-slate-500'}`}>无可展示载荷。</div>
                          ) : (
                            <div className="space-y-2">
                              {selectedOperationEventPayload.map(([key, value]) => (
                                <div key={key} className={`rounded-lg border p-2 ${isDark ? 'border-slate-800 bg-slate-950' : 'border-stone-200 bg-stone-50'}`}>
                                  <div className="mb-1 font-mono text-[11px] text-indigo-500">{key}</div>
                                  <pre className="max-h-44 overflow-auto whitespace-pre-wrap break-words text-xs leading-relaxed">{formatEventPayloadValue(value)}</pre>
                                </div>
                              ))}
                            </div>
                          )}
                        </div>
                      </div>
                    ) : (
                      <div className={`rounded-2xl border border-dashed p-8 text-center ${isDark ? 'border-slate-700 text-slate-400' : 'border-stone-300 text-slate-500'}`}>
                        选择左侧事件查看审计详情。
                      </div>
                    )}
                  </div>
                </div>
              </div>
            </div>
          )}
        </>
      ) : activeTab === 'world3d' ? (
        <Card className="min-h-[650px] overflow-hidden p-0">
          {loadingSceneData ? (
            <div className={`h-[650px] flex items-center justify-center gap-2 ${isDark ? 'text-gray-400' : 'text-gray-500'}`}>
              <Loader2 size={22} className="animate-spin text-blue-500" />
              正在加载多位面地图数据...
            </div>
          ) : selectedWorldId && currentWorld ? (
            <WorldMap3D
              worlds={worlds}
              regionsByWorldId={regionsByWorldId}
              characters={characters}
              selectedWorldId={selectedWorldId}
              onWorldSelect={setSelectedWorldId}
              isDark={isDark}
            />
          ) : (
            <div className={`h-[650px] flex items-center justify-center ${isDark ? 'text-gray-400' : 'text-gray-500'}`}>
              暂无世界数据，请先创建世界
            </div>
          )}
        </Card>
      ) : activeTab === 'relationships3d' ? (
        <Card className="min-h-[650px] overflow-hidden p-0">
          {loadingSceneData ? (
            <div className={`h-[650px] flex items-center justify-center gap-2 ${isDark ? 'text-gray-400' : 'text-gray-500'}`}>
              <Loader2 size={22} className="animate-spin text-blue-500" />
              正在加载角色关系数据...
            </div>
          ) : selectedWorldId && currentWorld ? (
            <CharacterRelationshipGraph3D
              worldId={selectedWorldId}
              characters={characters}
              selectedCharacterId={selectedRelationshipNodeId}
              onCharacterSelect={setSelectedRelationshipNodeId}
              isDark={isDark}
            />
          ) : (
            <div className={`h-[650px] flex items-center justify-center ${isDark ? 'text-gray-400' : 'text-gray-500'}`}>
              暂无世界数据，请先创建世界
            </div>
          )}
        </Card>
      ) : (
        <Card className="min-h-[600px]">
          {selectedWorldId && currentWorld ? (
            <ReactFlow
              nodes={activeTab === 'plots' ? plotNodes : snapshotNodes}
              edges={activeTab === 'plots' ? plotEdges : snapshotEdges}
              fitView
            >
              <MiniMap zoomable pannable />
              <Controls />
              <Background />
            </ReactFlow>
          ) : (
            <div className={`h-[600px] flex items-center justify-center ${isDark ? 'text-gray-400' : 'text-gray-500'}`}>
              暂无世界数据，请先创建世界
            </div>
          )}
        </Card>
      )}
    </PageLayout>
  )
}
