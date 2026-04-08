/**
 * Agent 模板配置页面
 * v7 核心功能：Agent 模板管理、Prompt 插槽配置、预览渲染
 */

import { useEffect, useState } from 'react'
import { Card, Button, Input, TextArea, Modal } from '@/components/ui'
import {
  getAgentTemplates,
  getAgentTemplateByType,
  createAgentTemplate,
  updateAgentTemplate,
  deleteAgentTemplate,
  previewAgentTemplate,
  AgentTemplate,
  AgentType,
  PromptSlot,
  CreateAgentTemplateDTO,
  UpdateAgentTemplateDTO,
} from '@/api/agentTemplates'
import { getPrompts, PromptTemplate } from '@/api/prompts'
import { Search, Plus, Edit2, Trash2, Eye, GripVertical, ChevronDown, ChevronUp, Settings } from 'lucide-react'
import { useTheme } from '@/contexts/ThemeContext'

const AGENT_TYPE_LABELS: Record<AgentType, string> = {
  character: '角色 Agent',
  setting: '设定 Agent',
  summarizer: '摘要 Agent',
  master_plotter: '总编剧 Agent',
  hook_manager: '伏笔管理 Agent',
  writer: '作家 Agent',
  evaluator: '评估 Agent',
  proc_gen: '过程生成 Agent',
}

export default function AgentTemplates() {
  const { theme } = useTheme()
  const isDark = theme === 'dark'

  const [templates, setTemplates] = useState<AgentTemplate[]>([])
  const [prompts, setPrompts] = useState<PromptTemplate[]>([])
  const [loading, setLoading] = useState(true)
  const [searchQuery, setSearchQuery] = useState('')
  const [selectedType, setSelectedType] = useState<AgentType | null>(null)

  // Modal 状态
  const [showEditModal, setShowEditModal] = useState(false)
  const [showPreviewModal, setShowPreviewModal] = useState(false)
  const [editingTemplate, setEditingTemplate] = useState<AgentTemplate | null>(null)
  const [previewResult, setPreviewResult] = useState<{
    rendered_prompts: Array<{ slot_name: string; description: string; content: string }>
    final_prompt: string
  } | null>(null)

  // 表单状态
  const [formData, setFormData] = useState<CreateAgentTemplateDTO>({
    name: '',
    description: '',
    agent_type: 'character',
    prompt_slots: [],
    default_prompt_order: [],
    default_model: 'gpt-4o-mini',
    default_temperature: 0.7,
    default_max_tokens: 4096,
    tags: [],
  })

  useEffect(() => {
    loadTemplates()
    loadPrompts()
  }, [selectedType])

  const loadTemplates = async () => {
    setLoading(true)
    try {
      const data = await getAgentTemplates(selectedType || undefined)
      // 前端搜索过滤
      if (searchQuery) {
        const query = searchQuery.toLowerCase()
        const filtered = data.filter(
          (t) =>
            t.name.toLowerCase().includes(query) ||
            t.description.toLowerCase().includes(query) ||
            t.tags.some((tag) => tag.toLowerCase().includes(query))
        )
        setTemplates(filtered)
      } else {
        setTemplates(data)
      }
    } catch (error) {
      console.error('Failed to load templates:', error)
    } finally {
      setLoading(false)
    }
  }

  const loadPrompts = async () => {
    try {
      const data = await getPrompts({ limit: 200 })
      setPrompts(data)
    } catch (error) {
      console.error('Failed to load prompts:', error)
    }
  }

  const handleCreate = () => {
    setEditingTemplate(null)
    setFormData({
      name: '',
      description: '',
      agent_type: 'character',
      prompt_slots: [],
      default_prompt_order: [],
      default_model: 'gpt-4o-mini',
      default_temperature: 0.7,
      default_max_tokens: 4096,
      tags: [],
    })
    setShowEditModal(true)
  }

  const handleEdit = (template: AgentTemplate) => {
    setEditingTemplate(template)
    setFormData({
      name: template.name,
      description: template.description,
      agent_type: template.agent_type,
      prompt_slots: template.prompt_slots || [],
      default_prompt_order: template.default_prompt_order || [],
      default_model: template.default_model,
      default_temperature: template.default_temperature,
      default_max_tokens: template.default_max_tokens,
      tags: template.tags || [],
    })
    setShowEditModal(true)
  }

  const handleDelete = async (templateId: string) => {
    if (!confirm('确定要删除此 Agent 模板吗？')) return
    try {
      await deleteAgentTemplate(templateId)
      loadTemplates()
    } catch (error) {
      console.error('Failed to delete template:', error)
    }
  }

  const handlePreview = async (template: AgentTemplate) => {
    setEditingTemplate(template)
    setShowPreviewModal(true)
    try {
      const result = await previewAgentTemplate(template.id)
      setPreviewResult(result)
    } catch (error) {
      console.error('Failed to preview template:', error)
    }
  }

  const handleSave = async () => {
    try {
      if (editingTemplate) {
        await updateAgentTemplate(editingTemplate.id, formData as UpdateAgentTemplateDTO)
      } else {
        await createAgentTemplate(formData)
      }
      setShowEditModal(false)
      loadTemplates()
    } catch (error) {
      console.error('Failed to save template:', error)
    }
  }

  const handleAddSlot = () => {
    const currentSlots = formData.prompt_slots || []
    const newSlot: PromptSlot = {
      slot_name: '',
      description: '',
      prompt_template_id: '',
      required: false,
      is_enabled: true,
      priority: currentSlots.length,
      variable_overrides: {},
    }
    setFormData({
      ...formData,
      prompt_slots: [...currentSlots, newSlot],
    })
  }

  const handleUpdateSlot = (index: number, field: keyof PromptSlot, value: any) => {
    const currentSlots = formData.prompt_slots || []
    const newSlots = [...currentSlots]
    newSlots[index] = { ...newSlots[index], [field]: value }
    setFormData({ ...formData, prompt_slots: newSlots })
  }

  const handleRemoveSlot = (index: number) => {
    const currentSlots = formData.prompt_slots || []
    setFormData({
      ...formData,
      prompt_slots: currentSlots.filter((_, i) => i !== index),
    })
  }

  const moveSlot = (index: number, direction: 'up' | 'down') => {
    const currentSlots = formData.prompt_slots || []
    const newSlots = [...currentSlots]
    if (direction === 'up' && index > 0) {
      [newSlots[index - 1], newSlots[index]] = [newSlots[index], newSlots[index - 1]]
    } else if (direction === 'down' && index < newSlots.length - 1) {
      [newSlots[index], newSlots[index + 1]] = [newSlots[index + 1], newSlots[index]]
    }
    // 更新优先级
    newSlots.forEach((slot, i) => {
      slot.priority = i
    })
    setFormData({ ...formData, prompt_slots: newSlots })
  }

  return (
    <div className="h-full flex flex-col">
      {/* 头部 */}
      <div className={`p-4 border-b ${isDark ? 'border-gray-700' : 'border-gray-200'}`}>
        <div className="flex items-center justify-between mb-4">
          <h1 className={`text-2xl font-bold ${isDark ? 'text-white' : 'text-gray-800'}`}>Agent 模板</h1>
          <Button onClick={handleCreate}>
            <Plus className="w-4 h-4 mr-2" />
            新建模板
          </Button>
        </div>

        {/* 搜索和筛选 */}
        <div className="flex gap-4">
          <div className="flex-1">
            <Input
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="搜索模板..."
              onKeyDown={(e) => e.key === 'Enter' && loadTemplates()}
            />
          </div>
          <select
            className={`border rounded px-3 py-2 text-sm ${isDark ? 'bg-gray-800 border-gray-600 text-white' : 'bg-white border-gray-300 text-gray-800'}`}
            value={selectedType || ''}
            onChange={(e) => setSelectedType(e.target.value as AgentType || null)}
          >
            <option value="">全部类型</option>
            {Object.entries(AGENT_TYPE_LABELS).map(([key, label]) => (
              <option key={key} value={key}>
                {label}
              </option>
            ))}
          </select>
        </div>
      </div>

      {/* 列表 */}
      <div className="flex-1 overflow-auto p-4">
        {loading ? (
          <div className={`text-center py-8 ${isDark ? 'text-gray-400' : 'text-gray-500'}`}>加载中...</div>
        ) : templates.length === 0 ? (
          <div className={`text-center py-8 ${isDark ? 'text-gray-400' : 'text-gray-500'}`}>暂无数据</div>
        ) : (
          <div className="space-y-4">
            {templates.map((template) => (
              <Card key={template.id} className="p-4">
                <div className="flex items-start justify-between">
                  <div className="flex-1">
                    <div className="flex items-center gap-2 mb-1">
                      <h3 className={`font-semibold text-lg ${isDark ? 'text-white' : 'text-gray-800'}`}>{template.name}</h3>
                      {template.is_system && (
                        <span className="px-2 py-1 text-xs bg-blue-900 text-blue-300 rounded">系统</span>
                      )}
                      <span className={`px-2 py-1 text-xs rounded ${isDark ? 'bg-gray-700' : 'bg-gray-200'}`}>
                        {AGENT_TYPE_LABELS[template.agent_type]}
                      </span>
                    </div>
                    <p className={`text-sm mb-2 ${isDark ? 'text-gray-400' : 'text-gray-500'}`}>{template.description}</p>

                    {/* Prompt 插槽预览 */}
                    <div className="flex items-center gap-2 mb-2">
                      <span className={`text-sm ${isDark ? 'text-gray-500' : 'text-gray-400'}`}>Prompt 插槽：</span>
                      <div className="flex gap-1 flex-wrap">
                        {template.prompt_slots
                          .filter((s) => s.is_enabled)
                          .slice(0, 5)
                          .map((slot) => (
                            <span
                              key={slot.slot_name}
                              className={`px-2 py-0.5 text-xs rounded ${
                                slot.prompt_template_id ? 'bg-green-900 text-green-300' : isDark ? 'bg-gray-700 text-gray-400' : 'bg-gray-200 text-gray-500'
                              }`}
                            >
                              {slot.slot_name}
                            </span>
                          ))}
                        {template.prompt_slots.filter((s) => s.is_enabled).length > 5 && (
                          <span className={`text-xs ${isDark ? 'text-gray-500' : 'text-gray-400'}`}>
                            +{template.prompt_slots.filter((s) => s.is_enabled).length - 5}
                          </span>
                        )}
                      </div>
                    </div>

                    {/* 模型配置 */}
                    <div className={`text-xs ${isDark ? 'text-gray-500' : 'text-gray-400'}`}>
                      模型：{template.default_model} | 温度：{template.default_temperature} | 最大 Token：{template.default_max_tokens}
                    </div>
                  </div>

                  <div className="flex gap-2">
                    <Button size="sm" variant="secondary" onClick={() => handlePreview(template)}>
                      <Eye className="w-4 h-4 mr-1" />
                      预览
                    </Button>
                    {!template.is_system && (
                      <>
                        <Button size="sm" variant="secondary" onClick={() => handleEdit(template)}>
                          <Edit2 className="w-4 h-4 mr-1" />
                          编辑
                        </Button>
                        <Button size="sm" variant="danger" onClick={() => handleDelete(template.id)}>
                          <Trash2 className="w-4 h-4" />
                        </Button>
                      </>
                    )}
                  </div>
                </div>
              </Card>
            ))}
          </div>
        )}
      </div>

      {/* 编辑/创建 Modal */}
      <Modal
        isOpen={showEditModal}
        onClose={() => setShowEditModal(false)}
        title={editingTemplate ? '编辑模板' : '新建模板'}
        className="max-w-4xl"
      >
        <div className="space-y-4">
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className={`block text-sm mb-1 ${isDark ? 'text-gray-400' : 'text-gray-600'}`}>名称</label>
              <Input
                value={formData.name}
                onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                placeholder="模板名称"
              />
            </div>
            <div>
              <label className={`block text-sm mb-1 ${isDark ? 'text-gray-400' : 'text-gray-600'}`}>Agent 类型</label>
              <select
                className={`w-full border rounded px-3 py-2 ${isDark ? 'bg-gray-800 border-gray-600 text-white' : 'bg-white border-gray-300 text-gray-800'}`}
                value={formData.agent_type}
                onChange={(e) => setFormData({ ...formData, agent_type: e.target.value as AgentType })}
              >
                {Object.entries(AGENT_TYPE_LABELS).map(([key, label]) => (
                  <option key={key} value={key}>
                    {label}
                  </option>
                ))}
              </select>
            </div>
          </div>

          <div>
            <label className={`block text-sm mb-1 ${isDark ? 'text-gray-400' : 'text-gray-600'}`}>描述</label>
            <TextArea
              value={formData.description}
              onChange={(e) => setFormData({ ...formData, description: e.target.value })}
              placeholder="模板描述"
              rows={2}
            />
          </div>

          {/* 模型配置 */}
          <div className="grid grid-cols-3 gap-4">
            <div>
              <label className={`block text-sm mb-1 ${isDark ? 'text-gray-400' : 'text-gray-600'}`}>默认模型</label>
              <Input
                value={formData.default_model}
                onChange={(e) => setFormData({ ...formData, default_model: e.target.value })}
                placeholder="gpt-4o-mini"
              />
            </div>
            <div>
              <label className={`block text-sm mb-1 ${isDark ? 'text-gray-400' : 'text-gray-600'}`}>温度</label>
              <Input
                type="number"
                value={formData.default_temperature}
                onChange={(e) =>
                  setFormData({ ...formData, default_temperature: parseFloat(e.target.value) || 0.7 })
                }
                min={0}
                max={2}
                step={0.1}
              />
            </div>
            <div>
              <label className={`block text-sm mb-1 ${isDark ? 'text-gray-400' : 'text-gray-600'}`}>最大 Token</label>
              <Input
                type="number"
                value={formData.default_max_tokens}
                onChange={(e) =>
                  setFormData({ ...formData, default_max_tokens: parseInt(e.target.value) || 4096 })
                }
              />
            </div>
          </div>

          {/* Prompt 插槽 */}
          <div>
            <div className="flex items-center justify-between mb-2">
              <label className={`block text-sm ${isDark ? 'text-gray-400' : 'text-gray-600'}`}>Prompt 插槽</label>
              <Button size="sm" variant="secondary" onClick={handleAddSlot}>
                <Plus className="w-4 h-4 mr-1" />
                添加插槽
              </Button>
            </div>

            {(formData.prompt_slots?.length ?? 0) > 0 && (
              <div className="space-y-2">
                {(formData.prompt_slots || []).map((slot, index) => (
                  <div key={index} className={`p-3 rounded ${isDark ? 'bg-gray-800' : 'bg-gray-100'}`}>
                    <div className="flex items-center gap-2 mb-2">
                      <GripVertical className={`w-4 h-4 cursor-move ${isDark ? 'text-gray-500' : 'text-gray-400'}`} />
                      <Input
                        value={slot.slot_name}
                        onChange={(e) => handleUpdateSlot(index, 'slot_name', e.target.value)}
                        placeholder="插槽名称"
                        className="flex-1"
                      />
                      <div className="flex gap-1">
                        <Button
                          size="sm"
                          variant="secondary"
                          onClick={() => moveSlot(index, 'up')}
                          disabled={index === 0}
                        >
                          <ChevronUp className="w-4 h-4" />
                        </Button>
                        <Button
                          size="sm"
                          variant="secondary"
                          onClick={() => moveSlot(index, 'down')}
                          disabled={index === (formData.prompt_slots?.length ?? 0) - 1}
                        >
                          <ChevronDown className="w-4 h-4" />
                        </Button>
                      </div>
                      <label className={`flex items-center gap-1 text-sm ${isDark ? 'text-gray-300' : 'text-gray-600'}`}>
                        <input
                          type="checkbox"
                          checked={slot.is_enabled}
                          onChange={(e) => handleUpdateSlot(index, 'is_enabled', e.target.checked)}
                        />
                        启用
                      </label>
                      <Button size="sm" variant="danger" onClick={() => handleRemoveSlot(index)}>
                        <Trash2 className="w-4 h-4" />
                      </Button>
                    </div>

                    <div className="grid grid-cols-2 gap-2">
                      <div>
                        <Input
                          value={slot.description}
                          onChange={(e) => handleUpdateSlot(index, 'description', e.target.value)}
                          placeholder="插槽描述"
                        />
                      </div>
                      <div>
                        <select
                          className={`w-full border rounded px-2 py-1 text-sm ${isDark ? 'bg-gray-700 border-gray-600 text-white' : 'bg-white border-gray-300 text-gray-800'}`}
                          value={slot.prompt_template_id || ''}
                          onChange={(e) =>
                            handleUpdateSlot(index, 'prompt_template_id', e.target.value || null)
                          }
                        >
                          <option value="">选择 Prompt 模板</option>
                          {prompts.map((p) => (
                            <option key={p.id} value={p.id}>
                              {p.name}
                            </option>
                          ))}
                        </select>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>

          <div className="flex justify-end gap-2 pt-4">
            <Button variant="secondary" onClick={() => setShowEditModal(false)}>
              取消
            </Button>
            <Button onClick={handleSave}>{editingTemplate ? '保存' : '创建'}</Button>
          </div>
        </div>
      </Modal>

      {/* 预览 Modal */}
      <Modal isOpen={showPreviewModal} onClose={() => setShowPreviewModal(false)} title="模板预览" className="max-w-4xl">
        {previewResult ? (
          <div className="space-y-4">
            <div>
              <h4 className={`text-sm mb-2 ${isDark ? 'text-gray-400' : 'text-gray-600'}`}>渲染后的 Prompt 片段</h4>
              <div className="space-y-3">
                {previewResult.rendered_prompts.map((p, i) => (
                  <div key={i} className={`p-3 rounded ${isDark ? 'bg-gray-800' : 'bg-gray-100'}`}>
                    <div className="flex items-center justify-between mb-2">
                      <span className={`font-medium ${isDark ? 'text-white' : 'text-gray-800'}`}>{p.slot_name}</span>
                      <span className={`text-xs ${isDark ? 'text-gray-500' : 'text-gray-400'}`}>{p.description}</span>
                    </div>
                    <pre className={`text-sm whitespace-pre-wrap ${isDark ? 'text-gray-300' : 'text-gray-700'}`}>{p.content || '(空)'}</pre>
                  </div>
                ))}
              </div>
            </div>

            <div>
              <h4 className={`text-sm mb-2 ${isDark ? 'text-gray-400' : 'text-gray-600'}`}>最终拼接结果</h4>
              <pre className={`p-4 rounded text-sm overflow-auto max-h-[300px] whitespace-pre-wrap ${isDark ? 'bg-gray-900' : 'bg-gray-100'}`}>
                {previewResult.final_prompt}
              </pre>
            </div>
          </div>
        ) : (
          <div className={`text-center py-8 ${isDark ? 'text-gray-400' : 'text-gray-500'}`}>加载中...</div>
        )}
      </Modal>
    </div>
  )
}
