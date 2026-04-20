/**
 * 项目 Agent 配置组件
 * 用于在项目详情页面中配置 Agent
 */

import { useEffect, useMemo, useState } from 'react'
import { Card, Button, Input, Modal } from '@/components/ui'
import {
  getAgentConfigs,
  getAgentConfig,
  updateAgentConfig,
  previewAgentConfig,
  resetAgentConfigs,
  AgentConfig,
  ModelConfig,
  SlotOverride,
} from '@/api/agentConfigs'
import { getAgentTemplates, AgentTemplate, AgentType } from '@/api/agentTemplates'
import { getPrompts, PromptTemplate } from '@/api/prompts'
import { useAgentTypes } from '@/hooks/useAgentTypes'
import { Eye, RefreshCw, Settings, ChevronDown, ChevronUp, Layers, CheckCircle2 } from 'lucide-react'
import { useTheme } from '@/contexts/ThemeContext'

interface AgentConfigPanelProps {
  projectId: string
  refreshKey?: number
  agentTypeFilter?: string | null
  onChanged?: () => void
}

interface AgentConfigRow {
  key: string
  agentType: string
  label: string
  template?: AgentTemplate
  config?: AgentConfig
  isUsingProjectConfig: boolean
  effectiveActive: boolean
}

export default function AgentConfigPanel({
  projectId,
  refreshKey = 0,
  agentTypeFilter,
  onChanged,
}: AgentConfigPanelProps) {
  const { theme } = useTheme()
  const isDark = theme === 'dark'

  const { labels: AGENT_TYPE_LABELS, metadata } = useAgentTypes()

  const [configs, setConfigs] = useState<AgentConfig[]>([])
  const [templates, setTemplates] = useState<AgentTemplate[]>([])
  const [prompts, setPrompts] = useState<PromptTemplate[]>([])
  const [loading, setLoading] = useState(true)

  const [editingConfig, setEditingConfig] = useState<AgentConfig | null>(null)
  const [showEditModal, setShowEditModal] = useState(false)
  const [showPreviewModal, setShowPreviewModal] = useState(false)
  const [previewContent, setPreviewContent] = useState('')
  const [previewTitle, setPreviewTitle] = useState('')

  const [formData, setFormData] = useState<{
    name: string
    description: string
    llm_config: ModelConfig
    slot_overrides: SlotOverride[]
  }>({
    name: '',
    description: '',
    llm_config: {
      model_name: 'gpt-4o-mini',
      temperature: 0.7,
      max_tokens: 4096,
    },
    slot_overrides: [],
  })

  const [expandedConfigs, setExpandedConfigs] = useState<Set<string>>(new Set())

  useEffect(() => {
    loadData()
  }, [projectId, refreshKey, agentTypeFilter])

  const loadData = async () => {
    setLoading(true)
    try {
      const filter = agentTypeFilter || undefined
      const [configsData, templatesData, promptsData] = await Promise.all([
        getAgentConfigs(projectId, filter || undefined, undefined, 200),
        getAgentTemplates(filter as AgentType | undefined, undefined, undefined, 200),
        getPrompts({ limit: 100 }),
      ])
      setConfigs(configsData)
      setTemplates(templatesData)
      setPrompts(promptsData)
    } catch (error) {
      console.error('Failed to load agent config panel data:', error)
      setConfigs([])
      setTemplates([])
      setPrompts([])
    } finally {
      setLoading(false)
    }
  }

  const getTemplateForConfig = (config?: AgentConfig | null) => {
    if (!config) return null
    if (config.template_id) {
      const matchedById = templates.find((template) => template.id === config.template_id)
      if (matchedById) return matchedById
    }
    return templates.find((template) => template.agent_type === config.agent_type) || null
  }

  const rows = useMemo<AgentConfigRow[]>(() => {
    const configMap = new Map(configs.map((config) => [config.agent_type, config]))
    const visibleTemplates = agentTypeFilter
      ? templates.filter((template) => template.agent_type === agentTypeFilter)
      : templates

    const templateRows: AgentConfigRow[] = visibleTemplates.map((template) => {
      const config = configMap.get(template.agent_type)
      return {
        key: template.agent_type,
        agentType: template.agent_type,
        label: AGENT_TYPE_LABELS[template.agent_type] || template.agent_type,
        template,
        config,
        isUsingProjectConfig: Boolean(config),
        effectiveActive: config?.is_active ?? template.is_enabled,
      }
    })

    const extraConfigRows: AgentConfigRow[] = configs
      .filter((config) => !visibleTemplates.some((template) => template.agent_type === config.agent_type))
      .filter((config) => !agentTypeFilter || config.agent_type === agentTypeFilter)
      .map((config) => ({
        key: config.agent_type,
        agentType: config.agent_type,
        label: AGENT_TYPE_LABELS[config.agent_type] || config.agent_type,
        template: undefined,
        config,
        isUsingProjectConfig: true,
        effectiveActive: config.is_active,
      }))

    const typeOrder = new Map<string, number>(metadata.map((item, index) => [item.type, index]))

    return [...templateRows, ...extraConfigRows].sort((a, b) => {
      const orderA = typeOrder.get(a.agentType) ?? Number.MAX_SAFE_INTEGER
      const orderB = typeOrder.get(b.agentType) ?? Number.MAX_SAFE_INTEGER
      if (orderA !== orderB) return orderA - orderB
      return a.label.localeCompare(b.label, 'zh-CN')
    })
  }, [configs, templates, agentTypeFilter, AGENT_TYPE_LABELS, metadata])

  const existingConfigCount = configs.length

  const handleEdit = async (row: AgentConfigRow) => {
    try {
      const resolvedConfig = row.config || await getAgentConfig(projectId, row.agentType)
      const wasLazyCreated = !row.config

      setEditingConfig(resolvedConfig)
      setFormData({
        name: resolvedConfig.name,
        description: resolvedConfig.description,
        llm_config: {
          model_name: resolvedConfig.llm_config.model_name,
          temperature: resolvedConfig.llm_config.temperature,
          max_tokens: resolvedConfig.llm_config.max_tokens,
          top_p: resolvedConfig.llm_config.top_p,
          frequency_penalty: resolvedConfig.llm_config.frequency_penalty,
          presence_penalty: resolvedConfig.llm_config.presence_penalty,
        },
        slot_overrides: resolvedConfig.slot_overrides,
      })
      setShowEditModal(true)

      if (wasLazyCreated) {
        await loadData()
        onChanged?.()
      }
    } catch (error) {
      console.error('Failed to load config for edit:', error)
    }
  }

  const handleSave = async () => {
    if (!editingConfig) return
    try {
      await updateAgentConfig(projectId, editingConfig.agent_type, formData)
      setShowEditModal(false)
      await loadData()
      onChanged?.()
    } catch (error) {
      console.error('Failed to save config:', error)
    }
  }

  const handlePreview = async (row: AgentConfigRow) => {
    setPreviewTitle(row.label)
    setPreviewContent('')
    setShowPreviewModal(true)

    try {
      const result = await previewAgentConfig(projectId, row.agentType)
      setPreviewContent(result.final_prompt)

      if (!row.config) {
        await loadData()
        onChanged?.()
      }
    } catch (error) {
      console.error('Failed to preview config:', error)
      setPreviewContent('预览失败')
    }
  }

  const handleReset = async (agentType?: string) => {
    if (!confirm('确定要重置配置为模板默认值吗？')) return
    try {
      await resetAgentConfigs(projectId, agentType)
      await loadData()
      onChanged?.()
    } catch (error) {
      console.error('Failed to reset config:', error)
    }
  }

  const toggleExpand = (agentType: string) => {
    const newExpanded = new Set(expandedConfigs)
    if (newExpanded.has(agentType)) {
      newExpanded.delete(agentType)
    } else {
      newExpanded.add(agentType)
    }
    setExpandedConfigs(newExpanded)
  }

  if (loading) {
    return <div className={`text-center py-8 ${isDark ? 'text-gray-400' : 'text-gray-500'}`}>加载中...</div>
  }

  return (
    <div className="space-y-4">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h2 className={`text-xl font-bold ${isDark ? 'text-white' : 'text-gray-800'}`}>项目级 Agent 配置</h2>
          <p className={`mt-1 text-sm ${isDark ? 'text-gray-400' : 'text-gray-500'}`}>
            当前项目对 Agent 模板的覆盖层。未创建配置时会继续使用模板默认值，并在首次配置或预览时懒创建。
          </p>
        </div>
        <Button
          variant="secondary"
          size="sm"
          onClick={() => handleReset()}
          disabled={existingConfigCount === 0}
          title={existingConfigCount === 0 ? '当前还没有可重置的项目配置' : '重置所有项目级配置'}
        >
          <RefreshCw className="w-4 h-4 mr-1" />
          重置全部
        </Button>
      </div>

      <Card className={`p-4 ${isDark ? 'bg-gray-900 border-gray-800' : 'bg-gray-50 border-gray-200'}`}>
        <div className="grid gap-3 md:grid-cols-3 text-sm">
          <div>
            <div className={isDark ? 'text-gray-500' : 'text-gray-500'}>模板类型数</div>
            <div className={`mt-1 text-lg font-semibold ${isDark ? 'text-white' : 'text-gray-800'}`}>{rows.length}</div>
          </div>
          <div>
            <div className={isDark ? 'text-gray-500' : 'text-gray-500'}>已创建项目覆盖</div>
            <div className={`mt-1 text-lg font-semibold ${isDark ? 'text-white' : 'text-gray-800'}`}>{existingConfigCount}</div>
          </div>
          <div>
            <div className={isDark ? 'text-gray-500' : 'text-gray-500'}>当前状态</div>
            <div className={`mt-1 ${isDark ? 'text-gray-300' : 'text-gray-700'}`}>
              {existingConfigCount > 0 ? '项目覆盖与模板默认值并存' : '当前全部使用模板默认值'}
            </div>
          </div>
        </div>
      </Card>

      {rows.length === 0 ? (
        <div className={`text-center py-8 ${isDark ? 'text-gray-400' : 'text-gray-500'}`}>暂无可展示的 Agent 类型</div>
      ) : (
        <div className="space-y-3">
          {rows.map((row) => {
            const config = row.config
            const template = row.template || getTemplateForConfig(config)
            const isExpanded = expandedConfigs.has(row.agentType)

            return (
              <Card key={row.key} className="p-4">
                <div
                  className="flex items-center justify-between gap-4 cursor-pointer"
                  onClick={() => toggleExpand(row.agentType)}
                >
                  <div className="flex items-center gap-3 min-w-0">
                    {isExpanded ? <ChevronUp className="w-5 h-5 flex-shrink-0" /> : <ChevronDown className="w-5 h-5 flex-shrink-0" />}
                    <div className="min-w-0">
                      <div className="flex items-center gap-2 flex-wrap">
                        <span className={`font-semibold ${isDark ? 'text-white' : 'text-gray-800'}`}>
                          {config?.name || row.label}
                        </span>
                        <span className={`px-2 py-0.5 text-xs rounded ${isDark ? 'bg-gray-700 text-gray-200' : 'bg-gray-200 text-gray-700'}`}>
                          {row.label}
                        </span>
                        <span className={`px-2 py-0.5 text-xs rounded ${row.effectiveActive ? 'bg-green-900 text-green-300' : 'bg-gray-700 text-gray-300'}`}>
                          {row.effectiveActive ? '项目启用' : '项目禁用'}
                        </span>
                        {row.isUsingProjectConfig ? (
                          <span className="px-2 py-0.5 text-xs bg-purple-900 text-purple-300 rounded">项目覆盖</span>
                        ) : (
                          <span className="px-2 py-0.5 text-xs bg-blue-900 text-blue-300 rounded">模板默认值</span>
                        )}
                      </div>
                      <div className={`mt-1 text-xs ${isDark ? 'text-gray-400' : 'text-gray-500'}`}>
                        {row.isUsingProjectConfig
                          ? `来源模板：${template?.name || '未关联模板'}`
                          : `当前未创建项目配置，使用 ${template?.name || '系统模板'} 的默认值`}
                      </div>
                    </div>
                  </div>

                  <div className="flex gap-2 flex-shrink-0" onClick={(e) => e.stopPropagation()}>
                    <Button size="sm" variant="secondary" onClick={() => handlePreview(row)}>
                      <Eye className="w-4 h-4 mr-1" />
                      预览
                    </Button>
                    <Button size="sm" variant="secondary" onClick={() => handleEdit(row)}>
                      <Settings className="w-4 h-4 mr-1" />
                      配置
                    </Button>
                    <Button
                      size="sm"
                      variant="secondary"
                      onClick={() => handleReset(row.agentType)}
                      disabled={!config}
                      title={!config ? '该类型还没有项目级配置，无需重置' : '重置该 Agent 的项目配置'}
                    >
                      <RefreshCw className="w-4 h-4" />
                    </Button>
                  </div>
                </div>

                {isExpanded && (
                  <div className={`mt-4 pt-4 border-t space-y-3 ${isDark ? 'border-gray-700' : 'border-gray-200'}`}>
                    <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4 text-sm">
                      <div>
                        <div className={isDark ? 'text-gray-500' : 'text-gray-500'}>配置层级</div>
                        <div className={`mt-1 ${isDark ? 'text-gray-200' : 'text-gray-700'}`}>
                          {row.isUsingProjectConfig ? '项目覆盖已生效' : '使用模板默认值'}
                        </div>
                      </div>
                      <div>
                        <div className={isDark ? 'text-gray-500' : 'text-gray-500'}>模型</div>
                        <div className={`mt-1 ${isDark ? 'text-gray-200' : 'text-gray-700'}`}>
                          {config?.llm_config.model_name || '模板默认'}
                        </div>
                      </div>
                      <div>
                        <div className={isDark ? 'text-gray-500' : 'text-gray-500'}>温度</div>
                        <div className={`mt-1 ${isDark ? 'text-gray-200' : 'text-gray-700'}`}>
                          {config ? config.llm_config.temperature : '模板默认'}
                        </div>
                      </div>
                      <div>
                        <div className={isDark ? 'text-gray-500' : 'text-gray-500'}>插槽覆盖</div>
                        <div className={`mt-1 ${isDark ? 'text-gray-200' : 'text-gray-700'}`}>
                          {config ? `${config.slot_overrides.length} 项` : '尚未创建'}
                        </div>
                      </div>
                    </div>

                    {!config ? (
                      <div className={`rounded-lg p-3 text-sm ${isDark ? 'bg-gray-800 text-gray-300' : 'bg-blue-50 text-gray-700'}`}>
                        <div className="flex items-center gap-2 mb-1">
                          <CheckCircle2 className="w-4 h-4" />
                          <span className="font-medium">当前仍在使用模板默认配置</span>
                        </div>
                        <div>
                          点击“配置”会创建当前项目的覆盖记录，点击“预览”会基于运行时配置生成最终 prompt。
                        </div>
                      </div>
                    ) : (
                      <>
                        {config.slot_overrides.length > 0 && (
                          <div>
                            <h4 className={`text-sm mb-2 ${isDark ? 'text-gray-400' : 'text-gray-600'}`}>插槽覆盖</h4>
                            <div className="space-y-2">
                              {config.slot_overrides.map((override, index) => (
                                <div key={`${override.slot_name}-${index}`} className={`p-2 rounded text-sm ${isDark ? 'bg-gray-800' : 'bg-gray-50'}`}>
                                  <div className="flex items-center gap-2 flex-wrap">
                                    <span className="font-medium">{override.slot_name}</span>
                                    <span className={`px-1.5 py-0.5 text-xs rounded ${isDark ? 'bg-gray-700 text-gray-300' : 'bg-gray-200 text-gray-700'}`}>
                                      {override.override_type}
                                    </span>
                                  </div>
                                  {override.prompt_template_id && (
                                    <div className={`text-xs mt-1 ${isDark ? 'text-gray-500' : 'text-gray-500'}`}>
                                      替换为：{prompts.find((prompt) => prompt.id === override.prompt_template_id)?.name || override.prompt_template_id}
                                    </div>
                                  )}
                                </div>
                              ))}
                            </div>
                          </div>
                        )}

                        <div className={`text-xs ${isDark ? 'text-gray-500' : 'text-gray-500'}`}>
                          使用次数：{config.usage_count} ｜ 最后使用：{config.last_used_at ? new Date(config.last_used_at).toLocaleString() : '从未'}
                        </div>
                      </>
                    )}

                    {template && (
                      <div className={`rounded-lg p-3 text-sm ${isDark ? 'bg-gray-800/60 text-gray-300' : 'bg-gray-50 text-gray-700'}`}>
                        <div className="flex items-center gap-2 mb-2 font-medium">
                          <Layers className="w-4 h-4" />
                          模板基础信息
                        </div>
                        <div className="grid gap-2 md:grid-cols-3">
                          <div>模板名称：{template.name}</div>
                          <div>Prompt 插槽：{template.prompt_slots.length}</div>
                          <div>Skill 插槽：{template.skill_slots.length}</div>
                        </div>
                      </div>
                    )}
                  </div>
                )}
              </Card>
            )
          })}
        </div>
      )}

      <Modal
        isOpen={showEditModal}
        onClose={() => setShowEditModal(false)}
        title={`配置 ${editingConfig ? (AGENT_TYPE_LABELS[editingConfig.agent_type] || editingConfig.agent_type) : ''}`}
        className="max-w-3xl"
      >
        <div className="space-y-4">
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className={`block text-sm mb-1 ${isDark ? 'text-gray-400' : 'text-gray-600'}`}>名称</label>
              <Input
                value={formData.name}
                onChange={(e) => setFormData({ ...formData, name: e.target.value })}
              />
            </div>
            <div>
              <label className={`block text-sm mb-1 ${isDark ? 'text-gray-400' : 'text-gray-600'}`}>描述</label>
              <Input
                value={formData.description}
                onChange={(e) => setFormData({ ...formData, description: e.target.value })}
              />
            </div>
          </div>

          <div>
            <h4 className={`text-sm mb-2 ${isDark ? 'text-gray-400' : 'text-gray-600'}`}>模型配置</h4>
            <div className="grid grid-cols-3 gap-4">
              <div>
                <label className={`block text-xs mb-1 ${isDark ? 'text-gray-500' : 'text-gray-500'}`}>模型名称</label>
                <Input
                  value={formData.llm_config.model_name}
                  onChange={(e) =>
                    setFormData({
                      ...formData,
                      llm_config: { ...formData.llm_config, model_name: e.target.value },
                    })
                  }
                />
              </div>
              <div>
                <label className={`block text-xs mb-1 ${isDark ? 'text-gray-500' : 'text-gray-500'}`}>温度</label>
                <Input
                  type="number"
                  value={formData.llm_config.temperature}
                  onChange={(e) =>
                    setFormData({
                      ...formData,
                      llm_config: {
                        ...formData.llm_config,
                        temperature: parseFloat(e.target.value) || 0.7,
                      },
                    })
                  }
                  min={0}
                  max={2}
                  step={0.1}
                />
              </div>
              <div>
                <label className={`block text-xs mb-1 ${isDark ? 'text-gray-500' : 'text-gray-500'}`}>最大 Token</label>
                <Input
                  type="number"
                  value={formData.llm_config.max_tokens || ''}
                  onChange={(e) =>
                    setFormData({
                      ...formData,
                      llm_config: {
                        ...formData.llm_config,
                        max_tokens: parseInt(e.target.value) || undefined,
                      },
                    })
                  }
                />
              </div>
            </div>
          </div>

          <div>
            <h4 className={`text-sm mb-2 ${isDark ? 'text-gray-400' : 'text-gray-600'}`}>Prompt 插槽覆盖</h4>
            {(getTemplateForConfig(editingConfig)?.prompt_slots.length || 0) === 0 ? (
              <div className={`rounded p-3 text-sm ${isDark ? 'bg-gray-800 text-gray-400' : 'bg-gray-50 text-gray-500'}`}>
                当前模板没有可覆盖的 Prompt 插槽。
              </div>
            ) : (
              getTemplateForConfig(editingConfig)?.prompt_slots.map((slot) => {
                const existingOverride = formData.slot_overrides.find((override) => override.slot_name === slot.slot_name)
                return (
                  <div key={slot.slot_name} className={`p-3 rounded mb-2 ${isDark ? 'bg-gray-800' : 'bg-gray-50'}`}>
                    <div className="flex items-center justify-between mb-2 gap-3">
                      <span className={`font-medium ${isDark ? 'text-gray-200' : 'text-gray-700'}`}>{slot.slot_name}</span>
                      <span className={`text-xs ${isDark ? 'text-gray-500' : 'text-gray-500'}`}>{slot.description}</span>
                    </div>
                    <select
                      className={`w-full border rounded px-3 py-2 text-sm ${isDark ? 'bg-gray-700 border-gray-600 text-white' : 'bg-white border-gray-300 text-gray-800'}`}
                      value={existingOverride?.prompt_template_id || ''}
                      onChange={(e) => {
                        const newOverrides = [...formData.slot_overrides]
                        const index = newOverrides.findIndex((override) => override.slot_name === slot.slot_name)
                        if (e.target.value) {
                          const newOverride: SlotOverride = {
                            slot_name: slot.slot_name,
                            override_type: 'prompt_replace',
                            prompt_template_id: e.target.value,
                          }
                          if (index >= 0) {
                            newOverrides[index] = newOverride
                          } else {
                            newOverrides.push(newOverride)
                          }
                        } else if (index >= 0) {
                          newOverrides.splice(index, 1)
                        }
                        setFormData({ ...formData, slot_overrides: newOverrides })
                      }}
                    >
                      <option value="">使用模板默认</option>
                      {prompts.map((prompt) => (
                        <option key={prompt.id} value={prompt.id}>
                          {prompt.name}
                        </option>
                      ))}
                    </select>
                  </div>
                )
              })
            )}
          </div>

          <div className="flex justify-end gap-2 pt-4">
            <Button variant="secondary" onClick={() => setShowEditModal(false)}>取消</Button>
            <Button onClick={handleSave}>保存</Button>
          </div>
        </div>
      </Modal>

      <Modal
        isOpen={showPreviewModal}
        onClose={() => setShowPreviewModal(false)}
        title={`${previewTitle || 'Agent'} 最终 Prompt 预览`}
        className="max-w-4xl"
      >
        <pre className={`p-4 rounded text-sm overflow-auto max-h-[500px] whitespace-pre-wrap ${isDark ? 'bg-gray-900 text-gray-100' : 'bg-gray-50 text-gray-800'}`}>
          {previewContent || '加载中...'}
        </pre>
      </Modal>
    </div>
  )
}
