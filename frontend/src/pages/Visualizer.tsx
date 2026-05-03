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
  getActiveWorkflowExecution,
  getExecution,
  pauseExecution,
  resumeExecution,
  cancelExecution,
  confirmDiscussion,
  type WorkflowDefinition,
  type WorkflowExecution,
  type WorkflowNode as WfNode,
  type WorkflowEdge as WfEdge,
  type NodeInputConfig,
  type NodeOutputConfig,
} from '@/api/workflows'
import { getWorkflowNodeTypes, type NodeTypeInfo, type WorkflowNodeTypes } from '@/api/nodeTypes'
import WorkflowMonitor from '@/components/workflow/WorkflowMonitor'
import WorkflowTrace from '@/components/workflow/WorkflowTrace'
import { Network, Users, GitBranch, Play, Save, Trash2, Plus, Loader2, Pause, Square, RotateCcw, Orbit, Map } from 'lucide-react'
import { useTheme } from '@/contexts/ThemeContext'
import { formatRequirementList } from '@/utils/resourceRequirementDisplay'
import { useProject } from '@/contexts/ProjectContext'
import WorkflowHelp from '@/components/workflow/WorkflowHelp'
import WorldMap3D from '@/components/visualizer/WorldMap3D'
import CharacterRelationshipGraph3D from '@/components/visualizer/CharacterRelationshipGraph3D'

function AgentNode({ data }: { data: any }) {
  const { theme } = useTheme()
  const isDark = theme === 'dark'
  const status = data.status || 'pending'

  const statusColors: Record<string, string> = {
    pending: isDark ? 'bg-gray-700 border-gray-600' : 'bg-gray-100 border-gray-300',
    running: 'bg-blue-100 border-blue-400 animate-pulse',
    completed: 'bg-green-100 border-green-400',
    failed: 'bg-red-100 border-red-400',
  }

  return (
    <div className={`px-4 py-3 rounded-lg border-2 min-w-[120px] ${statusColors[status]}`}>
      <Handle type="target" position={Position.Top} className="!bg-gray-400 !w-3 !h-3" />
      <div className="font-medium text-sm">{data.label}</div>
      {data.agent_type && <div className="text-xs opacity-70">{data.agent_type}</div>}
      <Handle type="source" position={Position.Bottom} className="!bg-gray-400 !w-3 !h-3" />
    </div>
  )
}

function ConditionNode({ data }: { data: any }) {
  return (
    <div className="px-4 py-3 rounded-lg border-2 border-orange-400 bg-orange-50 min-w-[150px]">
      <Handle type="target" position={Position.Top} className="!bg-orange-400 !w-3 !h-3" />
      <div className="font-medium text-sm">条件分支</div>
      <div className="text-xs opacity-70">{data.label || '评估结果'}</div>
      <div className="flex justify-between text-xs mt-1 px-1">
        <span className="text-green-600">通过</span>
        <span className="text-red-600">重试</span>
      </div>
      <Handle type="source" position={Position.Left} id="pass" className="!bg-green-500 !w-3 !h-3" />
      <Handle type="source" position={Position.Right} id="retry" className="!bg-red-500 !w-3 !h-3" />
    </div>
  )
}

function ParallelNode({ data }: { data: any }) {
  return (
    <div className="px-4 py-3 rounded-lg border-2 border-purple-400 bg-purple-50 min-w-[120px]">
      <Handle type="target" position={Position.Top} className="!bg-purple-400 !w-3 !h-3" />
      <div className="font-medium text-sm">并行执行</div>
      <div className="text-xs opacity-70">{data.label || '同时执行多个分支'}</div>
      <Handle type="source" position={Position.Bottom} className="!bg-purple-400 !w-3 !h-3" />
    </div>
  )
}

function ScenePerformanceNode({ data }: { data: any }) {
  return (
    <div className="px-4 py-3 rounded-lg border-2 border-rose-400 bg-rose-50 min-w-[150px]">
      <Handle type="target" position={Position.Top} className="!bg-rose-400 !w-3 !h-3" />
      <div className="font-medium text-sm">场景演绎</div>
      <div className="text-xs opacity-70">{data.label || '多角色同台表演'}</div>
      <div className="text-xs text-rose-600 mt-1">自动协调角色 Agent</div>
      <Handle type="source" position={Position.Bottom} className="!bg-rose-400 !w-3 !h-3" />
    </div>
  )
}

function GroupDiscussionNode({ data }: { data: any }) {
  return (
    <div className="px-4 py-3 rounded-lg border-2 border-indigo-400 bg-indigo-50 min-w-[150px]">
      <Handle type="target" position={Position.Top} className="!bg-indigo-400 !w-3 !h-3" />
      <div className="font-medium text-sm">集体讨论</div>
      <div className="text-xs opacity-70">{data.label || '多 Agent 讨论'}</div>
      <Handle type="source" position={Position.Bottom} className="!bg-indigo-400 !w-3 !h-3" />
    </div>
  )
}

function StartNode({ data }: { data: any }) {
  return (
    <div className="px-4 py-3 rounded-lg border-2 border-green-500 bg-green-50 min-w-[100px]">
      <Handle type="target" position={Position.Top} id="loop" className="!bg-green-400 !w-3 !h-3" />
      <div className="font-medium text-sm text-center">{data.label || '开始'}</div>
      <Handle type="source" position={Position.Bottom} className="!bg-green-500 !w-3 !h-3" />
    </div>
  )
}

function EndNode({ data }: { data: any }) {
  return (
    <div className="px-4 py-3 rounded-lg border-2 border-red-500 bg-red-50 min-w-[100px]">
      <Handle type="target" position={Position.Top} className="!bg-red-400 !w-3 !h-3" />
      <div className="font-medium text-sm text-center">{data.label || '结束'}</div>
    </div>
  )
}

function InputNode({ data }: { data: any }) {
  return (
    <div className="px-4 py-3 rounded-lg border-2 border-blue-400 bg-blue-50 min-w-[120px]">
      <Handle type="target" position={Position.Top} className="!bg-blue-400 !w-3 !h-3" />
      <div className="font-medium text-sm">用户输入</div>
      <div className="text-xs opacity-70">{data.label || '等待用户输入'}</div>
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
}

type WorkflowOrigin = 'project' | 'global_template'

const generateId = () => `node_${Date.now()}_${Math.random().toString(36).slice(2, 9)}`
const isActiveExecutionStatus = (status?: string) => status === 'pending' || status === 'running' || status === 'paused'
const executionStorageKey = (projectId: string, workflowId: string) => `workflowExecution:${projectId}:${workflowId}`

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

  const loadWorkflows = async () => {
    if (!currentProject) return
    try {
      const result = await getWorkflows(currentProject.id, true)
      setWorkflows(result)
    } catch (error) {
      console.error('Failed to load workflows:', error)
    }
  }

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

  const handleSelectWorkflow = (workflow: WorkflowDefinition) => {
    const origin = getWorkflowOrigin(workflow)
    setSelectedWorkflow(origin === 'global_template' ? null : workflow)
    setWorkflowSelectionMode(origin)
    setWorkflowName(buildWorkflowDisplayName(workflow, origin))
    setNodes(workflowToCanvasNodes(workflow))
    setEdges(workflowToCanvasEdges(workflow))
    setCurrentExecution(null)
    setCurrentExecutionId(null)
    setCurrentExecutionStatus(null)
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
    setCurrentExecution(null)
    setCurrentExecutionId(null)
    setCurrentExecutionStatus(null)
  }

  const handleLoadStandardWorkflow = () => {
    if (!currentProject) return
    const workflow = buildStandardTemplateWorkflow(currentProject.id)
    setSelectedWorkflow(null)
    setWorkflowSelectionMode('project')
    setWorkflowName(workflow.name)
    setNodes(workflowToCanvasNodes(workflow))
    setEdges(workflowToCanvasEdges(workflow))
    setCurrentExecution(null)
    setCurrentExecutionId(null)
    setCurrentExecutionStatus(null)
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

  const applyExecutionState = (execution: WorkflowExecution) => {
    setCurrentExecution(execution)
    setCurrentExecutionId(execution.id)
    setCurrentExecutionStatus(execution.status)
  }

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
    loadWorkflows()
  }, [currentProject])

  useEffect(() => {
    if (!currentProject || !workflows.length) return

    const params = new URLSearchParams(window.location.search)
    const urlExecutionId = params.get('execution_id')
    if (!urlExecutionId || selectedWorkflow) return

    const restoreWorkflowFromUrl = async () => {
      try {
        const execution = await getExecution(urlExecutionId)
        const workflow = workflows.find((item) => item.id === execution.workflow_id)
        if (!workflow) return
        handleSelectWorkflow(workflow)
        applyExecutionState(execution)
        localStorage.setItem(executionStorageKey(currentProject.id, workflow.id), execution.id)
      } catch (error) {
        console.warn('Failed to restore workflow from URL execution:', error)
      }
    }

    void restoreWorkflowFromUrl()
  }, [currentProject, workflows, selectedWorkflow])

  useEffect(() => {
    if (!currentProject || !selectedWorkflow) return

    const restoreExecution = async () => {
      const params = new URLSearchParams(window.location.search)
      const urlExecutionId = params.get('execution_id')
      const storedExecutionId = localStorage.getItem(executionStorageKey(currentProject.id, selectedWorkflow.id))

      try {
        if (urlExecutionId) {
          const execution = await getExecution(urlExecutionId)
          applyExecutionState(execution)
          localStorage.setItem(executionStorageKey(currentProject.id, selectedWorkflow.id), execution.id)
          return
        }

        if (storedExecutionId) {
          const execution = await getExecution(storedExecutionId)
          if (isActiveExecutionStatus(execution.status)) {
            applyExecutionState(execution)
            localStorage.setItem(executionStorageKey(currentProject.id, selectedWorkflow.id), execution.id)
            return
          }
          localStorage.removeItem(executionStorageKey(currentProject.id, selectedWorkflow.id))
        }

        const active = await getActiveWorkflowExecution(currentProject.id, selectedWorkflow.id)
        if (active.execution && isActiveExecutionStatus(active.execution.status)) {
          applyExecutionState(active.execution)
          localStorage.setItem(executionStorageKey(currentProject.id, selectedWorkflow.id), active.execution.id)
        }
      } catch (error) {
        console.warn('Failed to restore workflow execution:', error)
      }
    }

    void restoreExecution()
  }, [currentProject, selectedWorkflow])
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
      const completedChapterNumbers = new Set(
        (chaptersResult || [])
          .filter(chapter => chapter.status === 'completed')
          .map(chapter => {
            const match = String(chapter.title || '').match(/第\s*(\d+)\s*章/)
            return match ? Number(match[1]) : null
          })
          .filter((value): value is number => Number.isFinite(value as number)),
      )
      const targetOutline = [...(outlinesResult.outlines || [])]
        .filter(outline => ['approved', 'completed'].includes(outline.status))
        .sort((a, b) => a.chapter_number - b.chapter_number)
        .find(outline => !completedChapterNumbers.has(outline.chapter_number)) || null

      if (!targetOutline) {
        setStartPrecheckError('当前项目没有可启动的已审批大纲（所有已审批章节都已完成，或尚未审批）。请先在大纲页准备下一章的已审批大纲。')
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
      setStartPrecheckReadiness(readinessResult.readiness[0] || null)

      if (blocking.length > 0) {
        setStartPrecheckError(`第 ${targetOutline.chapter_number} 章存在 unresolved blocking 资源需求：${formatRequirementList(blocking)}`)
        return null
      }

      return targetOutline
    } catch (error: any) {
      const detail = error?.response?.data?.detail
      setStartPrecheckError(
        detail?.message || (typeof detail === 'string' ? detail : error?.message) || '启动前资源预检失败',
      )
      return null
    } finally {
      setStartPrechecking(false)
    }
  }, [currentProject])

  const handleExecuteWorkflow = async (forceNew = false) => {
    if (!currentProject) return

    if (currentExecutionId && isActiveExecutionStatus(currentExecutionStatus || undefined) && !forceNew) {
      alert(`当前已有运行中的执行：${currentExecutionId}`)
      return
    }

    setExecuting(true)
    try {
      const workflow = await persistCurrentWorkflow()
      if (!workflow) {
        alert('请先保存工作流')
        return
      }

      if (!selectedWorkflow) {
        await loadWorkflows()
      }

      const targetOutline = await loadStartReadinessPrecheck()
      if (!targetOutline) {
        alert('启动前预检失败，请先修复阻塞项后再执行。')
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
      setCurrentExecution(null)
      setCurrentExecutionId(result.execution_id)
      setCurrentExecutionStatus(result.status || 'running')
      localStorage.setItem(executionStorageKey(currentProject.id, workflow.id), result.execution_id)
      const params = new URLSearchParams(window.location.search)
      params.set('execution_id', result.execution_id)
      window.history.replaceState(null, '', `${window.location.pathname}?${params.toString()}`)
      alert(`工作流已启动！执行ID: ${result.execution_id}`)
    } catch (error: any) {
      const gateDetail = extractChapterReadinessGateDetail(error)
      if (gateDetail) {
        alert(formatChapterReadinessGateMessage(gateDetail, formatRequirementList))
      } else {
        const detail = error?.response?.data?.detail
        const message = detail?.message || (typeof detail === 'string' ? detail : error?.message) || '执行失败'
        alert(message)
      }
      console.error('Failed to execute workflow:', error)
    } finally {
      setExecuting(false)
    }
  }

  useEffect(() => {
    if (currentProject && activeTab === 'workflow') {
      void loadStartReadinessPrecheck()
    }
  }, [activeTab, currentProject, loadStartReadinessPrecheck])

  const handlePauseExecution = async () => {
    if (!currentExecutionId) return
    try {
      await pauseExecution(currentExecutionId)
      setCurrentExecution(null)
      setCurrentExecutionStatus('paused')
    } catch (error) {
      console.error('Failed to pause execution:', error)
      alert('暂停失败')
    }
  }

  const handleResumeExecution = async () => {
    if (!currentExecutionId) return
    try {
      await resumeExecution(currentExecutionId)
      setCurrentExecution(null)
      setCurrentExecutionStatus('running')
    } catch (error) {
      console.error('Failed to resume execution:', error)
      alert('恢复失败')
    }
  }

  const handleCancelExecution = async () => {
    if (!currentExecutionId) return
    if (!confirm('确定要取消当前工作流执行吗？')) return
    try {
      await cancelExecution(currentExecutionId)
      setCurrentExecution(null)
      setCurrentExecutionStatus('cancelled')
      if (currentProject && selectedWorkflow) {
        localStorage.removeItem(executionStorageKey(currentProject.id, selectedWorkflow.id))
      }
    } catch (error) {
      console.error('Failed to cancel execution:', error)
      alert('取消失败')
    }
  }

  const handleConfirmDiscussion = async (approved: boolean) => {
    if (!currentExecutionId) return
    const feedback = approved ? undefined : window.prompt('请输入返工反馈')
    if (!approved && !feedback) return

    try {
      await confirmDiscussion(currentExecutionId, approved, feedback || undefined)
      setCurrentExecution(null)
      setCurrentExecutionStatus('running')
    } catch (error) {
      console.error('Failed to confirm discussion:', error)
      alert('讨论确认失败')
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
        setCurrentExecution(null)
        setCurrentExecutionId(null)
        setCurrentExecutionStatus(null)
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
        <div className="flex gap-4" style={{ height: 'calc(100vh - 280px)', minHeight: '500px' }}>
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
              <div className={`mt-2 rounded border p-2 text-xs ${
                startPrecheckError
                  ? 'border-red-200 bg-red-50 text-red-700'
                  : startPrecheckAdvisoryRequirements.length > 0
                    ? 'border-yellow-200 bg-yellow-50 text-yellow-700'
                    : 'border-gray-200 bg-gray-50 text-gray-600'
              }`}>
                {startPrechecking ? (
                  <div>正在检查已审批大纲和章节资源 readiness...</div>
                ) : startPrecheckError ? (
                  <div>{startPrecheckError}</div>
                ) : startPrecheckOutline ? (
                  <div className="space-y-1">
                    <div>
                      readiness: {startPrecheckReadiness?.readiness_status || 'ready'}；blocking: {startPrecheckBlockingRequirements.length}；advisory: {startPrecheckAdvisoryRequirements.length}
                    </div>
                    {startPrecheckBlockingRequirements.length > 0 && (
                      <div>阻塞资源：{formatRequirementList(startPrecheckBlockingRequirements)}</div>
                    )}
                    {startPrecheckAdvisoryRequirements.length > 0 && (
                      <div>建议补齐：{formatRequirementList(startPrecheckAdvisoryRequirements)}</div>
                    )}
                  </div>
                ) : (
                  <div>等待启动前预检...</div>
                )}
              </div>
              {currentExecutionId && (
                <div className="mt-2 space-y-2 text-xs">
                  <div className="truncate text-gray-500" title={currentExecutionId}>执行ID: {currentExecutionId}</div>
                  <div className="grid grid-cols-3 gap-1">
                    <button
                      onClick={handlePauseExecution}
                      disabled={currentExecutionStatus !== 'running'}
                      className="flex items-center justify-center gap-1 px-2 py-1 rounded bg-yellow-100 text-yellow-700 disabled:opacity-50"
                    >
                      <Pause size={12} /> 暂停
                    </button>
                    <button
                      onClick={handleResumeExecution}
                      disabled={currentExecutionStatus !== 'paused'}
                      className="flex items-center justify-center gap-1 px-2 py-1 rounded bg-blue-100 text-blue-700 disabled:opacity-50"
                    >
                      <RotateCcw size={12} /> 恢复
                    </button>
                    <button
                      onClick={handleCancelExecution}
                      disabled={!isActiveExecutionStatus(currentExecutionStatus || undefined)}
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
                  <WorkflowMonitor executionId={currentExecutionId} />
                ) : (
                  <WorkflowTrace executionId={currentExecutionId} />
                )}
              </div>
            </div>
          </div>
        </div>
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
