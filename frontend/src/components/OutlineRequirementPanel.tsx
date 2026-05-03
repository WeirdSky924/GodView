import { useCallback, useEffect, useMemo, useState } from 'react'
import { AlertTriangle, Check, Loader2, X } from 'lucide-react'

import { Button, Card } from '@/components/ui'
import {
  getOutlineResourceRequirements,
  updateOutlineResourceRequirementStatus,
  type OutlineResourceRequirement,
  type ResourceRequirementStatus,
} from '@/api/outlines'
import { useTheme } from '@/contexts/ThemeContext'
import {
  formatRequirementTypeFlow,
  getRequirementOriginalType,
  getRequirementTargetType,
  getRequirementTypeLabel,
  normalizeRequirementType,
} from '@/utils/resourceRequirementDisplay'

type BindableRequirementResource = {
  id: string
  label: string
  type: string
  description?: string
}

interface OutlineRequirementPanelProps {
  projectId?: string
  requirementTypes: string[]
  title: string
  description?: string
  emptyText?: string
  maxItems?: number
  refreshKey?: number
  onCreate?: (requirement: OutlineResourceRequirement) => void
  bindableResources?: BindableRequirementResource[]
  onBound?: () => void
}

const severityLabels: Record<string, string> = {
  blocking: '阻塞',
  advisory: '建议',
  optional: '可选',
}

const severityClasses: Record<string, { light: string; dark: string }> = {
  blocking: {
    light: 'bg-red-50 text-red-700 border-red-200',
    dark: 'bg-red-900/30 text-red-300 border-red-800',
  },
  advisory: {
    light: 'bg-amber-50 text-amber-700 border-amber-200',
    dark: 'bg-amber-900/30 text-amber-300 border-amber-800',
  },
  optional: {
    light: 'bg-gray-50 text-gray-700 border-gray-200',
    dark: 'bg-gray-800 text-gray-300 border-gray-700',
  },
}

const statusLabels: Record<ResourceRequirementStatus, string> = {
  pending: '待处理',
  in_progress: '处理中',
  resolved: '已解决',
  ignored: '已忽略',
  superseded: '已过期',
}

function uniqueRequirements(requirements: OutlineResourceRequirement[]) {
  const seen = new Set<string>()
  return requirements.filter(requirement => {
    if (seen.has(requirement.id)) return false
    seen.add(requirement.id)
    return true
  })
}

export default function OutlineRequirementPanel({
  projectId,
  requirementTypes,
  title,
  description,
  emptyText = '暂无来自大纲的待补需求。',
  maxItems = 5,
  refreshKey = 0,
  onCreate,
  bindableResources = [],
  onBound,
}: OutlineRequirementPanelProps) {
  const { theme } = useTheme()
  const isDark = theme === 'dark'
  const [requirements, setRequirements] = useState<OutlineResourceRequirement[]>([])
  const [loading, setLoading] = useState(false)
  const [updatingId, setUpdatingId] = useState<string | null>(null)
  const [selectedBindingByRequirementId, setSelectedBindingByRequirementId] = useState<Record<string, string>>({})

  const requirementTypeKey = requirementTypes.join('|')
  const queryTypes = useMemo(
    () => requirementTypeKey.split('|').filter(Boolean),
    [requirementTypeKey],
  )
  const normalizedTypes = useMemo(
    () => queryTypes.map(normalizeRequirementType),
    [queryTypes],
  )

  const loadRequirements = useCallback(async () => {
    if (!projectId) {
      setRequirements([])
      return
    }

    setLoading(true)
    try {
      const responses = await Promise.all(
        queryTypes.flatMap(requirementType => ([
          getOutlineResourceRequirements(projectId, { requirement_type: requirementType, status: 'pending' }),
          getOutlineResourceRequirements(projectId, { requirement_type: requirementType, status: 'in_progress' }),
        ])),
      )
      const loaded = uniqueRequirements(responses.flatMap(response => response.requirements))
        .filter(requirement => normalizedTypes.includes(normalizeRequirementType(requirement.requirement_type)))
        .sort((a, b) => {
          const severityRank = { blocking: 0, advisory: 1, optional: 2 }
          const severityDiff = severityRank[a.severity] - severityRank[b.severity]
          if (severityDiff !== 0) return severityDiff
          return (a.chapter_num || 0) - (b.chapter_num || 0)
        })
      setRequirements(loaded)
    } catch (error) {
      console.error('Failed to load outline resource requirements:', error)
      setRequirements([])
    } finally {
      setLoading(false)
    }
  }, [projectId, queryTypes, normalizedTypes])

  useEffect(() => {
    loadRequirements()
  }, [loadRequirements, refreshKey])

  const handleStatusUpdate = async (requirementId: string, status: ResourceRequirementStatus) => {
    setUpdatingId(requirementId)
    try {
      await updateOutlineResourceRequirementStatus(requirementId, {
        status,
        ...(status === 'resolved' ? { resolution_method: 'manual_resolved' as const } : {}),
        ...(status === 'ignored' ? { resolution_method: 'ignored' as const } : {}),
      })
      await loadRequirements()
    } catch (error) {
      console.error('Failed to update outline resource requirement:', error)
      alert('更新资源需求状态失败')
    } finally {
      setUpdatingId(null)
    }
  }

  const handleBindResource = async (requirement: OutlineResourceRequirement) => {
    const resourceId = selectedBindingByRequirementId[requirement.id]
    const resource = bindableResources.find(item => item.id === resourceId)
    if (!resource) {
      alert('请先选择要绑定的资源')
      return
    }

    setUpdatingId(requirement.id)
    try {
      await updateOutlineResourceRequirementStatus(requirement.id, {
        status: 'resolved',
        matched_resource_id: resource.id,
        matched_resource_type: resource.type,
        resolution_method: 'bind_existing',
      })
      setSelectedBindingByRequirementId(current => {
        const next = { ...current }
        delete next[requirement.id]
        return next
      })
      await loadRequirements()
      onBound?.()
    } catch (error) {
      console.error('Failed to bind outline resource requirement:', error)
      alert('绑定资源需求失败')
    } finally {
      setUpdatingId(null)
    }
  }

  const displayedRequirements = requirements.slice(0, maxItems)
  const hiddenCount = Math.max(requirements.length - displayedRequirements.length, 0)
  const pendingCount = requirements.filter(requirement => requirement.status === 'pending').length
  const inProgressCount = requirements.filter(requirement => requirement.status === 'in_progress').length

  return (
    <Card className="overflow-hidden" noPadding>
      <div className={`px-4 py-3 border-b ${isDark ? 'border-gray-700 bg-gray-900/60' : 'border-gray-100 bg-white'}`}>
        <div className="flex items-start justify-between gap-3">
          <div>
            <h3 className={`font-medium flex items-center gap-2 ${isDark ? 'text-white' : 'text-gray-900'}`}>
              <AlertTriangle className="w-4 h-4 text-amber-500" />
              {title}
            </h3>
            {description && <p className={`text-xs mt-1 ${isDark ? 'text-gray-400' : 'text-gray-500'}`}>{description}</p>}
          </div>
          <div className="flex gap-1 text-xs whitespace-nowrap">
            <span className={`px-2 py-1 rounded-full ${isDark ? 'bg-amber-900/30 text-amber-300' : 'bg-amber-50 text-amber-700'}`}>待 {pendingCount}</span>
            <span className={`px-2 py-1 rounded-full ${isDark ? 'bg-blue-900/30 text-blue-300' : 'bg-blue-50 text-blue-700'}`}>中 {inProgressCount}</span>
          </div>
        </div>
      </div>

      <div className="p-4 space-y-3">
        {loading ? (
          <div className={`text-sm flex items-center gap-2 ${isDark ? 'text-gray-400' : 'text-gray-500'}`}>
            <Loader2 className="w-4 h-4 animate-spin" />
            加载资源需求...
          </div>
        ) : displayedRequirements.length === 0 ? (
          <p className={`text-sm ${isDark ? 'text-gray-400' : 'text-gray-500'}`}>{emptyText}</p>
        ) : (
          displayedRequirements.map(requirement => {
            const severityClass = severityClasses[requirement.severity]
            const targetType = getRequirementTargetType(requirement)
            const selectedBindingId = selectedBindingByRequirementId[requirement.id] || ''
            const typeFlow = formatRequirementTypeFlow(requirement)
            const bindableOptions = bindableResources.filter(resource => normalizeRequirementType(resource.type) === targetType)
            return (
              <div key={requirement.id} className={`rounded-lg border p-3 ${isDark ? 'border-gray-700 bg-gray-800/60' : 'border-gray-100 bg-gray-50'}`}>
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <div className="flex items-center gap-2 flex-wrap">
                      <span className={`text-sm font-medium ${isDark ? 'text-gray-100' : 'text-gray-900'}`}>{requirement.resource_name}</span>
                      <span className={`text-xs px-2 py-0.5 rounded border ${isDark ? severityClass.dark : severityClass.light}`}>
                        {severityLabels[requirement.severity] || requirement.severity}
                      </span>
                      <span className={`text-xs ${isDark ? 'text-gray-400' : 'text-gray-500'}`}>
                        {statusLabels[requirement.status] || requirement.status}
                        {requirement.chapter_num ? ` · 第 ${requirement.chapter_num} 章` : ''}
                      </span>
                    </div>
                    <div className={`text-xs mt-1 flex flex-wrap gap-x-3 gap-y-1 ${isDark ? 'text-gray-400' : 'text-gray-500'}`}>
                      <span>需求类型：{getRequirementTypeLabel(getRequirementOriginalType(requirement))}</span>
                      <span>处理入口：{getRequirementTypeLabel(targetType)}</span>
                      <span>流向：{typeFlow}</span>
                    </div>
                    {requirement.reason && (
                      <p className={`text-xs mt-1 ${isDark ? 'text-gray-400' : 'text-gray-600'}`}>{requirement.reason}</p>
                    )}
                  </div>
                </div>
                {bindableOptions.length > 0 && requirement.status !== 'resolved' && requirement.status !== 'ignored' && (
                  <div className="flex flex-wrap gap-2 mt-3">
                    <select
                      value={selectedBindingId}
                      onChange={event => setSelectedBindingByRequirementId(current => ({
                        ...current,
                        [requirement.id]: event.target.value,
                      }))}
                      className={`min-w-[180px] flex-1 px-3 py-1.5 text-sm border rounded-lg ${isDark ? 'bg-gray-900 border-gray-700 text-gray-100' : 'bg-white border-gray-300 text-gray-900'}`}
                    >
                      <option value="">选择已有{getRequirementTypeLabel(targetType)}</option>
                      {bindableOptions.map(resource => (
                        <option key={resource.id} value={resource.id}>
                          {resource.label}{resource.description ? ` · ${resource.description}` : ''}
                        </option>
                      ))}
                    </select>
                    <Button
                      size="sm"
                      variant="secondary"
                      loading={updatingId === requirement.id}
                      onClick={() => handleBindResource(requirement)}
                    >
                      绑定已有
                    </Button>
                  </div>
                )}
                <div className="flex flex-wrap gap-2 mt-3">
                  {onCreate && requirement.status === 'pending' && (
                    <Button size="sm" onClick={() => onCreate(requirement)}>创建</Button>
                  )}
                  {requirement.status === 'pending' && (
                    <Button
                      size="sm"
                      variant="secondary"
                      loading={updatingId === requirement.id}
                      onClick={() => handleStatusUpdate(requirement.id, 'in_progress')}
                    >
                      设为处理中
                    </Button>
                  )}
                  <Button
                    size="sm"
                    variant="secondary"
                    loading={updatingId === requirement.id}
                    onClick={() => handleStatusUpdate(requirement.id, 'resolved')}
                  >
                    <Check className="w-3 h-3 mr-1" />
                    人工标记解决
                  </Button>
                  <Button
                    size="sm"
                    variant="ghost"
                    loading={updatingId === requirement.id}
                    onClick={() => handleStatusUpdate(requirement.id, 'ignored')}
                  >
                    <X className="w-3 h-3 mr-1" />
                    忽略此需求
                  </Button>
                </div>
              </div>
            )
          })
        )}
        {hiddenCount > 0 && (
          <p className={`text-xs ${isDark ? 'text-gray-400' : 'text-gray-500'}`}>还有 {hiddenCount} 条需求未显示，可到大纲页查看完整列表。</p>
        )}
      </div>
    </Card>
  )
}
