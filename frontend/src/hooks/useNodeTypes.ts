/**
 * Node Types Hook
 * 动态加载工作流节点类型的 Hook
 */

import { useState, useEffect, useCallback } from 'react'
import { getWorkflowNodeTypes, type NodeTypeInfo, type WorkflowNodeTypes } from '@/api/nodeTypes'

/**
 * 获取工作流节点类型的 Hook
 *
 * 每次都从 API 获取最新数据，不使用全局缓存
 */
export function useNodeTypes(projectId?: string) {
  const [nodeTypes, setNodeTypes] = useState<WorkflowNodeTypes>({
    agent_nodes: [],
    interaction_nodes: [],
    control_nodes: [],
    character_nodes: [],
  })
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<Error | null>(null)

  useEffect(() => {
    // 每次都重新获取数据
    setLoading(true)
    getWorkflowNodeTypes(projectId)
      .then((data) => {
        console.log('[useNodeTypes] Loaded node types:', data.agent_nodes?.length, 'agent nodes, version:', data.version)
        setNodeTypes(data)
        setError(null)
      })
      .catch((err) => {
        console.error('[useNodeTypes] Failed to load node types:', err)
        setError(err)
      })
      .finally(() => {
        setLoading(false)
      })
  }, [projectId])

  /**
   * 获取所有 Agent 节点（系统 + 角色）
   */
  const getAllAgentNodes = useCallback((): NodeTypeInfo[] => {
    return [...nodeTypes.agent_nodes, ...nodeTypes.character_nodes]
  }, [nodeTypes])

  /**
   * 根据 agent_type 获取节点信息
   */
  const getNodeByAgentType = useCallback(
    (agentType: string): NodeTypeInfo | undefined => {
      return getAllAgentNodes().find((n) => n.agent_type === agentType)
    },
    [nodeTypes]
  )

  /**
   * 根据节点类型获取信息
   */
  const getNodeByType = useCallback(
    (type: string): NodeTypeInfo | undefined => {
      const allNodes = [
        ...nodeTypes.agent_nodes,
        ...nodeTypes.interaction_nodes,
        ...nodeTypes.control_nodes,
        ...nodeTypes.character_nodes,
      ]
      return allNodes.find((n) => n.type === type)
    },
    [nodeTypes]
  )

  /**
   * 获取节点标签
   */
  const getLabel = useCallback(
    (typeOrAgentType: string): string => {
      const node = getNodeByType(typeOrAgentType) || getNodeByAgentType(typeOrAgentType)
      return node?.label || typeOrAgentType
    },
    [nodeTypes]
  )

  /**
   * 获取节点图标
   */
  const getIcon = useCallback(
    (typeOrAgentType: string): string => {
      const node = getNodeByType(typeOrAgentType) || getNodeByAgentType(typeOrAgentType)
      return node?.icon || 'Bot'
    },
    [nodeTypes]
  )

  return {
    nodeTypes,
    loading,
    error,
    getAllAgentNodes,
    getNodeByAgentType,
    getNodeByType,
    getLabel,
    getIcon,
  }
}

/**
 * 清除缓存（用于测试或强制刷新）
 * @deprecated 不再使用全局缓存
 */
export function clearNodeTypesCache() {
  // 不再需要，保留空函数以保持向后兼容
}
