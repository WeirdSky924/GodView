/**
 * Workflow Agents Hook
 * 根据工作流节点动态生成 Agent 状态列表
 */

import { useState, useEffect, useCallback, useMemo } from 'react'
import { type WorkflowDefinition, type WorkflowNode } from '@/api/workflows'
import {
  type WorkflowNodeTypes,
  getWorkflowNodeTypes,
  getAgentTypeOptions,
  FALLBACK_AGENT_TYPE_OPTIONS,
} from '@/api/nodeTypes'

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
const AGENT_DEFAULTS: Record<string, { icon: string; color: string }> = {
  'summarizer': { icon: '📝', color: 'blue' },
  'master_plotter': { icon: '🎬', color: 'purple' },
  'hook_manager': { icon: '🎯', color: 'orange' },
  'writer': { icon: '✍️', color: 'green' },
  'evaluator': { icon: '🔍', color: 'red' },
  'character': { icon: '🎭', color: 'pink' },
  'setting': { icon: '⚙️', color: 'indigo' },
  'event_generator': { icon: '🎲', color: 'pink' },
  'world_map_manager': { icon: '🗺️', color: 'teal' },
  'scene_coordinator': { icon: '🎭', color: 'rose' },
  'proc_gen': { icon: '🎰', color: 'amber' },
  'dungeon_generator': { icon: '🏰', color: 'violet' },
  'plotter': { icon: '🪄', color: 'violet' },
  'plot_outline': { icon: '📑', color: 'rose' },
}

const NODE_TYPE_TO_NAME: Record<string, string> = {
  'scene_performance': '场景演绎',
  'group_discussion': '集体讨论',
  'condition': '条件分支',
  'parallel': '并行执行',
  'input': '用户输入',
  'start': '开始',
  'end': '结束',
}

const FALLBACK_AGENT_LABELS = new Map(FALLBACK_AGENT_TYPE_OPTIONS.map((option) => [option.value, option.label]))

function buildAgentLabelMap(nodeTypes?: WorkflowNodeTypes | null): Map<string, string> {
  const options = getAgentTypeOptions(nodeTypes)
  return new Map(options.map((option) => [option.value, option.label]))
}

function getAgentLabel(agentType: string | undefined, label: string | undefined, agentLabelMap: Map<string, string>): string {
  if (!agentType) {
    return label || 'Agent'
  }

  if (agentType === 'character') {
    return label || agentLabelMap.get(agentType) || '角色 Agent'
  }

  return agentLabelMap.get(agentType) || label || FALLBACK_AGENT_LABELS.get(agentType) || agentType
}

function getAgentDescription(agentType: string | undefined, label: string | undefined, agentLabelMap: Map<string, string>): string {
  return getAgentLabel(agentType, label, agentLabelMap)
}

/**
 * 从工作流节点提取唯一的 Agent 类型
 */
function getWorkflowAgentKey(node: WorkflowNode, duplicateAgentTypes: Set<string>): string {
  if (node.agent_type === 'character') {
    return `character:${node.label || node.id}`
  }
  if (node.agent_type && duplicateAgentTypes.has(node.agent_type)) {
    return `agent_node:${node.id}`
  }
  return node.agent_type || node.id
}

function extractAgentsFromWorkflow(workflow: WorkflowDefinition, agentLabelMap: Map<string, string>): AgentStatus[] {
  const agentMap = new Map<string, AgentStatus>()
  const agentTypeCounts = new Map<string, number>()

  for (const node of workflow.nodes) {
    if (node.node_type === 'agent' && node.agent_type) {
      agentTypeCounts.set(node.agent_type, (agentTypeCounts.get(node.agent_type) || 0) + 1)
    }
  }
  const duplicateAgentTypes = new Set(
    Array.from(agentTypeCounts.entries())
      .filter(([, count]) => count > 1)
      .map(([agentType]) => agentType),
  )

  for (const node of workflow.nodes) {
    // Agent 节点
    if (node.node_type === 'agent' && node.agent_type) {
      const agentType = node.agent_type
      const agentKey = getWorkflowAgentKey(node, duplicateAgentTypes)

      if (!agentMap.has(agentKey)) {
        const defaults = AGENT_DEFAULTS[agentType] || { icon: '🤖', color: 'gray' }
        const baseName = getAgentLabel(agentType, node.label, agentLabelMap)
        const name = duplicateAgentTypes.has(agentType) && node.label ? node.label : baseName
        const description = getAgentDescription(agentType, node.label, agentLabelMap)

        agentMap.set(agentKey, {
          id: agentKey,
          name,
          status: 'idle',
          message: description,
          agent_type: agentType,
          icon: defaults.icon,
          color: defaults.color,
          description,
        })
      }
    }

    // 场景演绎节点（使用 SceneCoordinatorAgent）
    if (node.node_type === 'scene_performance') {
      const key = `scene_performance:${node.id}`
      if (!agentMap.has(key)) {
        agentMap.set(key, {
          id: key,
          name: node.label || NODE_TYPE_TO_NAME.scene_performance,
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
  }

  return Array.from(agentMap.values())
}

/**
 * Hook: 根据工作流动态生成 Agent 列表
 */
export function useWorkflowAgents(selectedWorkflowId: string, workflows: WorkflowDefinition[], projectId?: string) {
  // 当前活跃的 Agent 列表
  const [agents, setAgents] = useState<AgentStatus[]>([])
  const [nodeTypes, setNodeTypes] = useState<WorkflowNodeTypes | null>(null)

  // Agent 状态更新
  const [agentStates, setAgentStates] = useState<Record<string, AgentStatus['status']>>({})

  // Agent 输出
  const [agentOutputs, setAgentOutputsState] = useState<Record<string, string>>({})

  // Agent 流式输出
  const [agentStreaming, setAgentStreamingState] = useState<Record<string, string>>({})

  useEffect(() => {
    let cancelled = false

    getWorkflowNodeTypes(projectId)
      .then((data) => {
        if (!cancelled) {
          setNodeTypes(data)
        }
      })
      .catch((err) => {
        console.error('[useWorkflowAgents] Failed to load node types:', err)
      })

    return () => {
      cancelled = true
    }
  }, [projectId])

  const agentLabelMap = useMemo(() => buildAgentLabelMap(nodeTypes), [nodeTypes])

  // 当工作流变化时，重新生成 Agent 列表
  useEffect(() => {
    if (selectedWorkflowId) {
      const workflow = workflows.find(w => w.id === selectedWorkflowId)
      if (workflow) {
        const extractedAgents = extractAgentsFromWorkflow(workflow, agentLabelMap)
        setAgents(extractedAgents)
        // 重置状态
        setAgentStates({})
        setAgentOutputsState({})
        setAgentStreamingState({})
      }
    } else {
      // 没有选择工作流时，使用默认 Agent 列表
      const defaultAgents: AgentStatus[] = getAgentTypeOptions(nodeTypes).map((option) => {
        const defaults = AGENT_DEFAULTS[option.value] || { icon: '🤖', color: 'gray' }
        return {
          id: option.value,
          name: option.label,
          status: 'idle',
          message: option.label,
          agent_type: option.value,
          icon: defaults.icon,
          color: defaults.color,
          description: option.label,
        }
      })
      setAgents(defaultAgents)
    }
  }, [selectedWorkflowId, workflows, agentLabelMap, nodeTypes])

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
  if (data.agent_type) {
    return getAgentLabel(data.agent_type, data.label, FALLBACK_AGENT_LABELS)
  }

  if (data.node_type && NODE_TYPE_TO_NAME[data.node_type]) {
    return NODE_TYPE_TO_NAME[data.node_type]
  }

  if (data.label) {
    return data.label
  }

  return null
}
