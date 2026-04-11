/**
 * 项目 Agent 配置组件
 * 用于在项目详情页面中配置 Agent
 */

import { useEffect, useState } from 'react'
import { Card, Button, Input, Modal } from '@/components/ui'
import {
  getAgentConfigs,
  getAgentConfig,
  updateAgentConfig,
  previewAgentConfig,
  resetAgentConfigs,
  AgentConfig,
  UpdateAgentConfigDTO,
  ModelConfig,
  SlotOverride,
} from '@/api/agentConfigs'
import { getAgentTemplates, AgentTemplate } from '@/api/agentTemplates'
import { getPrompts, PromptTemplate } from '@/api/prompts'
import { useAgentTypes } from '@/hooks/useAgentTypes'
import { Eye, RefreshCw, Settings, ChevronDown, ChevronUp, Check } from 'lucide-react'

interface AgentConfigPanelProps {
  projectId: string
}

export default function AgentConfigPanel({ projectId }: AgentConfigPanelProps) {
  // 动态加载 Agent 类型元数据
  const { labels: AGENT_TYPE_LABELS } = useAgentTypes()

  const [configs, setConfigs] = useState<AgentConfig[]>([])
  const [templates, setTemplates] = useState<AgentTemplate[]>([])
  const [prompts, setPrompts] = useState<PromptTemplate[]>([])
  const [loading, setLoading] = useState(true)

  // 编辑状态
  const [editingConfig, setEditingConfig] = useState<AgentConfig | null>(null)
  const [showEditModal, setShowEditModal] = useState(false)
  const [showPreviewModal, setShowPreviewModal] = useState(false)
  const [previewContent, setPreviewContent] = useState('')

  // 表单状态
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

  // 展开状态
  const [expandedConfigs, setExpandedConfigs] = useState<Set<string>>(new Set())

  useEffect(() => {
    loadData()
  }, [projectId])

  const loadData = async () => {
    setLoading(true)
    try {
      const [configsData, templatesData, promptsData] = await Promise.all([
        getAgentConfigs(projectId),
        getAgentTemplates(),
        getPrompts({ limit: 100 }),
      ])
      setConfigs(configsData)
      setTemplates(templatesData)
      setPrompts(promptsData)
    } catch (error) {
      console.error('Failed to load data:', error)
    } finally {
      setLoading(false)
    }
  }

  const handleEdit = async (config: AgentConfig) => {
    setEditingConfig(config)
    setFormData({
      name: config.name,
      description: config.description,
      llm_config: config.llm_config,
      slot_overrides: config.slot_overrides,
    })
    setShowEditModal(true)
  }

  const handleSave = async () => {
    if (!editingConfig) return
    try {
      await updateAgentConfig(projectId, editingConfig.agent_type, formData)
      setShowEditModal(false)
      loadData()
    } catch (error) {
      console.error('Failed to save config:', error)
    }
  }

  const handlePreview = async (config: AgentConfig) => {
    setEditingConfig(config)
    setShowPreviewModal(true)
    try {
      const result = await previewAgentConfig(projectId, config.agent_type)
      setPreviewContent(result.final_prompt)
    } catch (error) {
      console.error('Failed to preview:', error)
      setPreviewContent('预览失败')
    }
  }

  const handleReset = async (agentType?: string) => {
    if (!confirm('确定要重置配置为模板默认值吗？')) return
    try {
      await resetAgentConfigs(projectId, agentType)
      loadData()
    } catch (error) {
      console.error('Failed to reset config:', error)
    }
  }

  const toggleExpand = (configId: string) => {
    const newExpanded = new Set(expandedConfigs)
    if (newExpanded.has(configId)) {
      newExpanded.delete(configId)
    } else {
      newExpanded.add(configId)
    }
    setExpandedConfigs(newExpanded)
  }

  // 获取关联的模板信息
  const getTemplate = (templateId?: string) => {
    if (!templateId) return null
    return templates.find(t => t.id === templateId)
  }

  if (loading) {
    return <div className="text-center text-gray-400 py-8">加载中...</div>
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-xl font-bold">Agent 配置</h2>
        <Button variant="secondary" size="sm" onClick={() => handleReset()}>
          <RefreshCw className="w-4 h-4 mr-1" />
          重置全部
        </Button>
      </div>

      {configs.length === 0 ? (
        <div className="text-center text-gray-400 py-8">暂无 Agent 配置</div>
      ) : (
        <div className="space-y-3">
          {configs.map((config) => {
            const template = getTemplate(config.template_id)
            const isExpanded = expandedConfigs.has(config.id)

            return (
              <Card key={config.id} className="p-4">
                <div
                  className="flex items-center justify-between cursor-pointer"
                  onClick={() => toggleExpand(config.id)}
                >
                  <div className="flex items-center gap-3">
                    {isExpanded ? <ChevronUp className="w-5 h-5" /> : <ChevronDown className="w-5 h-5" />}
                    <div>
                      <div className="flex items-center gap-2">
                        <span className="font-semibold">{config.name}</span>
                        <span className="px-2 py-0.5 text-xs bg-gray-700 rounded">
                          {AGENT_TYPE_LABELS[config.agent_type] || config.agent_type}
                        </span>
                        {config.is_custom && (
                          <span className="px-2 py-0.5 text-xs bg-purple-900 text-purple-300 rounded">自定义</span>
                        )}
                      </div>
                      {template && (
                        <div className="text-xs text-gray-500 mt-0.5">
                          模板: {template.name}
                        </div>
                      )}
                    </div>
                  </div>

                  <div className="flex gap-2" onClick={(e) => e.stopPropagation()}>
                    <Button size="sm" variant="secondary" onClick={() => handlePreview(config)}>
                      <Eye className="w-4 h-4 mr-1" />
                      预览
                    </Button>
                    <Button size="sm" variant="secondary" onClick={() => handleEdit(config)}>
                      <Settings className="w-4 h-4 mr-1" />
                      配置
                    </Button>
                    <Button size="sm" variant="secondary" onClick={() => handleReset(config.agent_type)}>
                      <RefreshCw className="w-4 h-4" />
                    </Button>
                  </div>
                </div>

                {isExpanded && (
                  <div className="mt-4 pt-4 border-t border-gray-700 space-y-3">
                    {/* 模型配置 */}
                    <div>
                      <h4 className="text-sm text-gray-400 mb-2">模型配置</h4>
                      <div className="grid grid-cols-3 gap-4 text-sm">
                        <div>
                          <span className="text-gray-500">模型:</span>
                          <span className="ml-2">{config.llm_config.model_name}</span>
                        </div>
                        <div>
                          <span className="text-gray-500">温度:</span>
                          <span className="ml-2">{config.llm_config.temperature}</span>
                        </div>
                        <div>
                          <span className="text-gray-500">最大Token:</span>
                          <span className="ml-2">{config.llm_config.max_tokens || '默认'}</span>
                        </div>
                      </div>
                    </div>

                    {/* 插槽覆盖 */}
                    {config.slot_overrides.length > 0 && (
                      <div>
                        <h4 className="text-sm text-gray-400 mb-2">插槽覆盖</h4>
                        <div className="space-y-2">
                          {config.slot_overrides.map((override, i) => (
                            <div key={i} className="bg-gray-800 p-2 rounded text-sm">
                              <div className="flex items-center gap-2">
                                <span className="font-medium">{override.slot_name}</span>
                                <span className="px-1.5 py-0.5 text-xs bg-gray-700 rounded">
                                  {override.override_type}
                                </span>
                              </div>
                              {override.prompt_template_id && (
                                <div className="text-xs text-gray-500 mt-1">
                                  替换为: {prompts.find(p => p.id === override.prompt_template_id)?.name || override.prompt_template_id}
                                </div>
                              )}
                            </div>
                          ))}
                        </div>
                      </div>
                    )}

                    {/* 使用统计 */}
                    <div className="text-xs text-gray-500">
                      使用次数: {config.usage_count} |
                      最后使用: {config.last_used_at ? new Date(config.last_used_at).toLocaleString() : '从未'}
                    </div>
                  </div>
                )}
              </Card>
            )
          })}
        </div>
      )}

      {/* 编辑 Modal */}
      <Modal
        isOpen={showEditModal}
        onClose={() => setShowEditModal(false)}
        title={`配置 ${editingConfig?.name || ''}`}
        className="max-w-3xl"
      >
        <div className="space-y-4">
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm text-gray-400 mb-1">名称</label>
              <Input
                value={formData.name}
                onChange={(e) => setFormData({ ...formData, name: e.target.value })}
              />
            </div>
            <div>
              <label className="block text-sm text-gray-400 mb-1">描述</label>
              <Input
                value={formData.description}
                onChange={(e) => setFormData({ ...formData, description: e.target.value })}
              />
            </div>
          </div>

          {/* 模型配置 */}
          <div>
            <h4 className="text-sm text-gray-400 mb-2">模型配置</h4>
            <div className="grid grid-cols-3 gap-4">
              <div>
                <label className="block text-xs text-gray-500 mb-1">模型名称</label>
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
                <label className="block text-xs text-gray-500 mb-1">温度</label>
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
                <label className="block text-xs text-gray-500 mb-1">最大 Token</label>
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

          {/* 插槽覆盖 */}
          <div>
            <h4 className="text-sm text-gray-400 mb-2">Prompt 插槽覆盖</h4>
            {editingConfig && getTemplate(editingConfig.template_id)?.prompt_slots.map((slot) => {
              const existingOverride = formData.slot_overrides.find(o => o.slot_name === slot.slot_name)
              return (
                <div key={slot.slot_name} className="bg-gray-800 p-3 rounded mb-2">
                  <div className="flex items-center justify-between mb-2">
                    <span className="font-medium">{slot.slot_name}</span>
                    <span className="text-xs text-gray-500">{slot.description}</span>
                  </div>
                  <select
                    className="w-full bg-gray-700 border border-gray-600 rounded px-3 py-2 text-sm"
                    value={existingOverride?.prompt_template_id || ''}
                    onChange={(e) => {
                      const newOverrides = [...formData.slot_overrides]
                      const idx = newOverrides.findIndex(o => o.slot_name === slot.slot_name)
                      if (e.target.value) {
                        const newOverride: SlotOverride = {
                          slot_name: slot.slot_name,
                          override_type: 'prompt_replace',
                          prompt_template_id: e.target.value,
                        }
                        if (idx >= 0) {
                          newOverrides[idx] = newOverride
                        } else {
                          newOverrides.push(newOverride)
                        }
                      } else if (idx >= 0) {
                        newOverrides.splice(idx, 1)
                      }
                      setFormData({ ...formData, slot_overrides: newOverrides })
                    }}
                  >
                    <option value="">使用模板默认</option>
                    {prompts.map((p) => (
                      <option key={p.id} value={p.id}>
                        {p.name}
                      </option>
                    ))}
                  </select>
                </div>
              )
            })}
          </div>

          <div className="flex justify-end gap-2 pt-4">
            <Button variant="secondary" onClick={() => setShowEditModal(false)}>取消</Button>
            <Button onClick={handleSave}>保存</Button>
          </div>
        </div>
      </Modal>

      {/* 预览 Modal */}
      <Modal isOpen={showPreviewModal} onClose={() => setShowPreviewModal(false)} title="最终 Prompt 预览" className="max-w-4xl">
        <pre className="bg-gray-900 p-4 rounded text-sm overflow-auto max-h-[500px] whitespace-pre-wrap">
          {previewContent || '加载中...'}
        </pre>
      </Modal>
    </div>
  )
}
