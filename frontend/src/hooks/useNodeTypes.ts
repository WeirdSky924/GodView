/**
 * Node Types Hook
 * 动态加载工作流节点类型的 Hook
 */

import { useState, useEffect, useCallback } from 'react'
import { getWorkflowNodeTypes, type NodeTypeInfo, type WorkflowNodeTypes } from '@/api/nodeTypes'

// 全局缓存
let cachedNodeTypes: WorkflowNodeTypes | null = null
let cachePromise: Promise<WorkflowNodeTypes> | null = null

/**
 * 获取工作流节点类型的 Hook
 *
 * 自动缓存结果，避免重复请求
 */
export function useNodeTypes(projectId?: string) {
  const [nodeTypes, setNodeTypes] = useState<WorkflowNodeTypes>(
    cachedNodeTypes || {
      agent_nodes: [],
      interaction_nodes: [],
      control_nodes: [],
      character_nodes: [],
    }
  )
  const [loading, setLoading] = useState(!cachedNodeTypes)
  const [error, setError] = useState<Error | null>(null)

  useEffect(() => {
    // 如果已有缓存且没有projectId，直接使用
    if (cachedNodeTypes && !projectId) {
      setNodeTypes(cachedNodeTypes)
      setLoading(false)
      return
    }

    // 发起请求
    setLoading(true)
    getWorkflowNodeTypes(projectId)
      .then((data) => {
        setNodeTypes(data)
        if (!projectId) {
          cachedNodeTypes = data
        }
        setError(null)
      })
      .catch((err) => {
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
 */
export function clearNodeTypesCache() {
  cachedNodeTypes = null
  cachePromise = null
}
