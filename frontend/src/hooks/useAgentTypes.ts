/**
 * Agent Types Hook
 * 动态加载 Agent 类型元数据的 Hook
 */

import { useState, useEffect, useCallback } from 'react'
import { getAgentTypesMetadata, AgentTypeMetadata } from '@/api/agentTemplates'

// 全局缓存
let cachedMetadata: AgentTypeMetadata[] | null = null
let cachePromise: Promise<AgentTypeMetadata[]> | null = null

/**
 * 获取 Agent 类型元数据的 Hook
 *
 * 自动缓存结果，避免重复请求
 */
export function useAgentTypes() {
  const [metadata, setMetadata] = useState<AgentTypeMetadata[]>(cachedMetadata || [])
  const [loading, setLoading] = useState(!cachedMetadata)
  const [error, setError] = useState<Error | null>(null)

  useEffect(() => {
    // 如果已有缓存，直接使用
    if (cachedMetadata) {
      setMetadata(cachedMetadata)
      setLoading(false)
      return
    }

    // 如果正在请求中，复用 Promise
    if (cachePromise) {
      cachePromise
        .then((data) => {
          setMetadata(data)
          setLoading(false)
        })
        .catch((err) => {
          setError(err)
          setLoading(false)
        })
      return
    }

    // 发起请求
    setLoading(true)
    cachePromise = getAgentTypesMetadata()

    cachePromise
      .then((data) => {
        cachedMetadata = data
        setMetadata(data)
        setError(null)
      })
      .catch((err) => {
        setError(err)
      })
      .finally(() => {
        setLoading(false)
        cachePromise = null
      })
  }, [])

  /**
   * 根据类型获取标签
   */
  const getLabel = useCallback(
    (type: string): string => {
      const item = metadata.find((m) => m.type === type)
      return item?.label || type
    },
    [metadata]
  )

  /**
   * 获取核心 Agent 类型
   */
  const getCoreTypes = useCallback((): AgentTypeMetadata[] => {
    return metadata.filter((m) => m.is_core)
  }, [metadata])

  /**
   * 获取可选 Agent 类型
   */
  const getOptionalTypes = useCallback((): AgentTypeMetadata[] => {
    return metadata.filter((m) => m.is_optional)
  }, [metadata])

  /**
   * 判断是否为核心类型
   */
  const isCoreType = useCallback(
    (type: string): boolean => {
      const item = metadata.find((m) => m.type === type)
      return item?.is_core ?? false
    },
    [metadata]
  )

  /**
   * 获取类型元数据
   */
  const getMetadata = useCallback(
    (type: string): AgentTypeMetadata | undefined => {
      return metadata.find((m) => m.type === type)
    },
    [metadata]
  )

  return {
    metadata,
    loading,
    error,
    getLabel,
    getCoreTypes,
    getOptionalTypes,
    isCoreType,
    getMetadata,
    // 向后兼容：提供 labels 对象
    labels: metadata.reduce(
      (acc, m) => {
        acc[m.type] = m.label
        return acc
      },
      {} as Record<string, string>
    ),
  }
}

/**
 * 清除缓存（用于测试或强制刷新）
 */
export function clearAgentTypesCache() {
  cachedMetadata = null
  cachePromise = null
}
