/**
 * Workflow Agents Hook
 * 根据工作流节点动态生成 Agent 状态列表
 */

import { useState, useEffect, useCallback, useMemo } from 'react'
import { type WorkflowDefinition } from '@/api/workflows'
import { type NodeTypeInfo, getWorkflowNodeTypes } from '@/api/nodeTypes'

// Agent 状态
export interface AgentStatus {
  id: string
  name: string
  status: 'idle' | 'working' | 'completed' | 'error'
  message: string
  agent_type: string
  icon: string
  color: string
  description: string
  isInteractionNode?: boolean
  nodeType?: string
}

// Agent 默认配置
const AGENT_DEFAULTS: Record<string, { icon: string; color: string; description: string }> = {
  'summarizer': { icon: '📝', color: 'blue', description: '剧情总结员' },
  'master_plotter': { icon: '🎬', color: 'purple', description: '总编剧' },
  'hook_manager': { icon: '🎯', color: 'orange', description: '伏笔管理员' },
  'writer': { icon: '✍️', color: 'green', description: '内容执行官' },
  'evaluator': { icon: '🔍', color: 'red', description: '剧情评估员' },
  'character': { icon: '🎭', color: 'pink', description: '角色演绎' },
  'setting': { icon: '⚙️', color: 'indigo', description: '设定 Agent' },
  'event_generator': { icon: '🎲', color: 'pink', description: '事件生成' },
  'world_map_manager': { icon: '🗺️', color: 'teal', description: '地图管理' },
  'scene_coordinator': { icon: '🎭', color: 'rose', description: '场景协调' },
  'proc_gen': { icon: '🎰', color: 'amber', description: '过程生成' },
  'dungeon_generator': { icon: '🏰', color: 'violet', description: '副本生成' },
}

// Agent 类型到显示名称的映射
const AGENT_TYPE_TO_NAME: Record<string, string> = {
  'summarizer': 'Summarizer',
  'master_plotter': 'Master Plotter',
  'plotter': 'Master Plotter',
  'hook_manager': 'Hook Manager',
  'writer': 'Writer',
  'evaluator': 'Evaluator',
  'character': 'Character Agent',
  'setting': 'Setting',
  'event_generator': 'Event Generator',
  'world_map_manager': 'World Map',
  'scene_coordinator': 'Scene Coordinator',
  'proc_gen': 'ProcGen',
  'dungeon_generator': 'Dungeon Generator',
}

// 节点类型到显示名称的映射（非 Agent 节点）
const NODE_TYPE_TO_NAME: Record<string, string> = {
  'scene_performance': '场景演绎',
  'group_discussion': '集体讨论',
  'condition': '条件判断',
  'parallel': '并行执行',
  'input': '用户输入',
}

/**
 * 从工作流节点提取唯一的 Agent 类型
 */
function extractAgentsFromWorkflow(workflow: WorkflowDefinition): AgentStatus[] {
  const agentMap = new Map<string, AgentStatus>()

  for (const node of workflow.nodes) {
    // Agent 节点
    if (node.node_type === 'agent' && node.agent_type) {
      const agentType = node.agent_type
      const agentKey = agentType.startsWith('character:') ? `character:${node.label}` : agentType

      if (!agentMap.has(agentKey)) {
        const defaults = AGENT_DEFAULTS[agentType] || { icon: '🤖', color: 'gray', description: node.label }
        const name = agentType.startsWith('character:')
          ? node.label
          : AGENT_TYPE_TO_NAME[agentType] || node.label

        agentMap.set(agentKey, {
          id: agentKey,
          name,
          status: 'idle',
          message: defaults.description,
          agent_type: agentType,
          icon: defaults.icon,
          color: defaults.color,
          description: defaults.description,
        })
      }
    }

    // 场景演绎节点（使用 SceneCoordinatorAgent）
    if (node.node_type === 'scene_performance') {
      const key = `scene_performance:${node.id}`
      if (!agentMap.has(key)) {
        agentMap.set(key, {
          id: key,
          name: node.label || '场景演绎',
          status: 'idle',
          message: '多角色同台演绎',
          agent_type: 'scene_coordinator',
          icon: '🎭',
          color: 'rose',
          description: '多角色场景协调',
          isInteractionNode: true,
          nodeType: 'scene_performance',
        })
      }
    }

    // 集体讨论节点 - 已有专用卡片，不在此生成
    // if (node.node_type === 'group_discussion') { ... }
  }

  return Array.from(agentMap.values())
}

/**
 * Hook: 根据工作流动态生成 Agent 列表
 */
export function useWorkflowAgents(selectedWorkflowId: string, workflows: WorkflowDefinition[]) {
  // 当前活跃的 Agent 列表
  const [agents, setAgents] = useState<AgentStatus[]>([])

  // Agent 状态更新
  const [agentStates, setAgentStates] = useState<Record<string, AgentStatus['status']>>({})

  // Agent 输出
  const [agentOutputs, setAgentOutputsState] = useState<Record<string, string>>({})

  // Agent 流式输出
  const [agentStreaming, setAgentStreamingState] = useState<Record<string, string>>({})

  // 当工作流变化时，重新生成 Agent 列表
  useEffect(() => {
    if (selectedWorkflowId) {
      const workflow = workflows.find(w => w.id === selectedWorkflowId)
      if (workflow) {
        const extractedAgents = extractAgentsFromWorkflow(workflow)
        setAgents(extractedAgents)
        // 重置状态
        setAgentStates({})
        setAgentOutputsState({})
        setAgentStreamingState({})
      }
    } else {
      // 没有选择工作流时，使用默认 Agent 列表
      const defaultAgents: AgentStatus[] = [
        { id: 'summarizer', name: 'Summarizer', status: 'idle', message: '剧情总结员', agent_type: 'summarizer', icon: '📝', color: 'blue', description: '剧情总结员' },
        { id: 'master_plotter', name: 'Master Plotter', status: 'idle', message: '总编剧', agent_type: 'master_plotter', icon: '🎬', color: 'purple', description: '总编剧' },
        { id: 'hook_manager', name: 'Hook Manager', status: 'idle', message: '伏笔管理员', agent_type: 'hook_manager', icon: '🎯', color: 'orange', description: '伏笔管理员' },
        { id: 'writer', name: 'Writer', status: 'idle', message: '内容执行官', agent_type: 'writer', icon: '✍️', color: 'green', description: '内容执行官' },
        { id: 'evaluator', name: 'Evaluator', status: 'idle', message: '剧情评估员', agent_type: 'evaluator', icon: '🔍', color: 'red', description: '剧情评估员' },
        { id: 'character', name: 'Character Agent', status: 'idle', message: '角色演绎', agent_type: 'character', icon: '🎭', color: 'pink', description: '角色演绎' },
        { id: 'setting', name: 'Setting', status: 'idle', message: '设定 Agent', agent_type: 'setting', icon: '⚙️', color: 'indigo', description: '设定 Agent' },
        { id: 'event_generator', name: 'Event Generator', status: 'idle', message: '事件生成', agent_type: 'event_generator', icon: '🎲', color: 'pink', description: '事件生成' },
        { id: 'world_map_manager', name: 'World Map', status: 'idle', message: '地图管理', agent_type: 'world_map_manager', icon: '🗺️', color: 'teal', description: '地图管理' },
      ]
      setAgents(defaultAgents)
    }
  }, [selectedWorkflowId, workflows])

  // 更新 Agent 状态
  const updateAgentStatus = useCallback((agentId: string, status: AgentStatus['status'], message?: string) => {
    setAgentStates(prev => ({ ...prev, [agentId]: status }))
    setAgents(prev => prev.map(a =>
      a.id === agentId || a.agent_type === agentId || a.name === agentId
        ? { ...a, status, message: message || a.message }
        : a
    ))
  }, [])

  // 更新 Agent 输出
  const setAgentOutput = useCallback((agentId: string, output: string) => {
    setAgentOutputsState(prev => ({ ...prev, [agentId]: output }))
  }, [])

  // 追加 Agent 流式输出
  const appendAgentStreaming = useCallback((agentId: string, chunk: string) => {
    setAgentStreamingState(prev => ({
      ...prev,
      [agentId]: (prev[agentId] || '') + chunk
    }))
    // 同时更新输出
    setAgentOutputsState(prev => ({
      ...prev,
      [agentId]: (prev[agentId] || '') + chunk
    }))
  }, [])

  // 清除流式输出
  const clearAgentStreaming = useCallback((agentId: string) => {
    setAgentStreamingState(prev => {
      const next = { ...prev }
      delete next[agentId]
      return next
    })
  }, [])

  // 批量设置 Agent 输出（用于 WebSocket 消息处理）
  const setAgentOutputs = useCallback((updater: (prev: Record<string, string>) => Record<string, string>) => {
    setAgentOutputsState(updater)
  }, [])

  // 批量设置 Agent 流式输出（用于 WebSocket 消息处理）
  const updateAgentStreaming = useCallback((updater: (prev: Record<string, string>) => Record<string, string>) => {
    setAgentStreamingState(updater)
  }, [])

  // 重置所有状态
  const resetAll = useCallback(() => {
    setAgentStates({})
    setAgentOutputsState({})
    setAgentStreamingState({})
    setAgents(prev => prev.map(a => ({ ...a, status: 'idle' as const })))
  }, [])

  // 获取带状态的 Agent 列表
  const agentsWithStatus = useMemo(() => {
    return agents.map(agent => ({
      ...agent,
      status: agentStates[agent.id] || agentStates[agent.agent_type] || agentStates[agent.name] || agent.status,
    }))
  }, [agents, agentStates])

  return {
    agents: agentsWithStatus,
    agentOutputs,
    agentStreaming,
    updateAgentStatus,
    setAgentOutput,
    setAgentOutputs,
    appendAgentStreaming,
    clearAgentStreaming,
    updateAgentStreaming,
    resetAll,
  }
}

/**
 * 根据 agent_type 或节点信息获取 Agent 显示名称
 */
export function getAgentDisplayName(data: {
  agent_type?: string
  label?: string
  node_type?: string
  node_id?: string
}): string | null {
  // 优先使用 agent_type 映射
  if (data.agent_type) {
    // 角色类型
    if (data.agent_type.startsWith('character:')) {
      return data.label || '角色 Agent'
    }
    // 系统 Agent
    if (AGENT_TYPE_TO_NAME[data.agent_type]) {
      return AGENT_TYPE_TO_NAME[data.agent_type]
    }
  }

  // 使用节点类型
  if (data.node_type && NODE_TYPE_TO_NAME[data.node_type]) {
    return NODE_TYPE_TO_NAME[data.node_type]
  }

  // 使用标签
  if (data.label) {
    return data.label
  }

  return null
}
