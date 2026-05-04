/**
 * Agent 模板配置页面
 * v7 核心功能：Agent 模板管理、Prompt 插槽配置、预览渲染
 */

import { useEffect, useState } from 'react'
import { Card, Button, Input, TextArea, Modal } from '@/components/ui'
import AgentConfigPanel from '@/components/AgentConfigPanel'
import {
  getAgentTemplates,
  createAgentTemplate,
  updateAgentTemplate,
  deleteAgentTemplate,
  previewAgentTemplate,
  toggleAgentTemplate,
  AgentTemplate,
  AgentType,
  PromptSlot,
  SkillSlot,
  CreateAgentTemplateDTO,
  UpdateAgentTemplateDTO,
  PreviewRenderTrace,
} from '@/api/agentTemplates'
import { getAgentConfigs } from '@/api/agentConfigs'
import { getPrompts, PromptTemplate } from '@/api/prompts'
import { getAgentTypeSkills, getSkills, type Skill } from '@/api/skills'
import { useAgentTypes } from '@/hooks/useAgentTypes'
import { Plus, Edit2, Trash2, Eye, GripVertical, ChevronDown, ChevronUp, Lock, ToggleLeft, ToggleRight, AlertTriangle, Layers, BookOpen } from 'lucide-react'
import { useProject } from '@/contexts/ProjectContext'
import { useTheme } from '@/contexts/ThemeContext'

export default function AgentTemplates() {
  const { theme } = useTheme()
  const { currentProject } = useProject()
  const isDark = theme === 'dark'

  // 动态加载 Agent 类型元数据
  const { labels: AGENT_TYPE_LABELS, isCoreType } = useAgentTypes()

  const [templates, setTemplates] = useState<AgentTemplate[]>([])
  const [prompts, setPrompts] = useState<PromptTemplate[]>([])
  const [loading, setLoading] = useState(true)
  const [searchQuery, setSearchQuery] = useState('')
  const [selectedType, setSelectedType] = useState<AgentType | null>(null)
  const [configRefreshKey, setConfigRefreshKey] = useState(0)

  // Modal 状态
  const [showEditModal, setShowEditModal] = useState(false)
  const [showPreviewModal, setShowPreviewModal] = useState(false)
  const [editingTemplate, setEditingTemplate] = useState<AgentTemplate | null>(null)
  const [previewResult, setPreviewResult] = useState<{
    rendered_prompts: Array<{ slot_name: string; description: string; content: string }>
    final_prompt: string
    render_trace?: PreviewRenderTrace
  } | null>(null)

  // Skills 状态
  const [availableSkills, setAvailableSkills] = useState<Skill[]>([])
  const [allSkills, setAllSkills] = useState<Skill[]>([])
  const [loadingSkills, setLoadingSkills] = useState(false)

  // 表单状态
  const [formData, setFormData] = useState<CreateAgentTemplateDTO>({
    name: '',
    description: '',
    agent_type: 'character',
    prompt_slots: [],
    skill_slots: [],
    default_prompt_order: [],
    default_skill_order: [],
    default_model: '',
    default_temperature: 0.7,
    tags: [],
    scenario: 'default',
    is_optional: false,
    is_enabled: true,
  })

  useEffect(() => {
    loadTemplates()
    loadPrompts()
    loadAllSkills()
  }, [selectedType, currentProject?.id])

  const loadTemplates = async () => {
    setLoading(true)
    try {
      const data = await getAgentTemplates(selectedType || undefined)
      const projectConfigs = currentProject?.id
        ? await getAgentConfigs(currentProject.id, undefined, undefined, 200)
        : []
      const projectConfigMap = new Map(projectConfigs.map((config) => [`${config.agent_type}:${config.scenario || 'default'}`, config]))

      // 确保返回的是数组
      if (Array.isArray(data)) {
        const mergedTemplates = data.map((template) => {
          const projectConfig = currentProject?.id ? projectConfigMap.get(`${template.agent_type}:${template.scenario || 'default'}`) : undefined
          if (!template.is_optional || !projectConfig) {
            return template
          }

          return {
            ...template,
            is_enabled: projectConfig.is_active,
          }
        })

        // 前端搜索过滤
        if (searchQuery) {
          const query = searchQuery.toLowerCase()
          const filtered = mergedTemplates.filter(
            (t) =>
              t.name.toLowerCase().includes(query) ||
              t.description.toLowerCase().includes(query) ||
              t.tags.some((tag) => tag.toLowerCase().includes(query))
          )
          setTemplates(filtered)
        } else {
          setTemplates(mergedTemplates)
        }
      } else {
        setTemplates([])
      }
    } catch (error) {
      console.error('Failed to load templates:', error)
      setTemplates([])
    } finally {
      setLoading(false)
    }
  }

  const bumpConfigRefreshKey = () => {
    setConfigRefreshKey((value) => value + 1)
  }

  const loadPrompts = async () => {
    try {
      const data = await getPrompts({ limit: 200 })
      if (Array.isArray(data)) {
        setPrompts(data)
      } else {
        setPrompts([])
      }
    } catch (error) {
      console.error('Failed to load prompts:', error)
      setPrompts([])
    }
  }

  const loadAllSkills = async () => {
    try {
      const data = await getSkills(undefined, undefined, undefined, undefined, undefined, undefined, 200)
      if (Array.isArray(data)) {
        setAllSkills(data)
      } else {
        setAllSkills([])
      }
    } catch (error) {
      console.error('Failed to load all skills:', error)
      setAllSkills([])
    }
  }

  const getPromptById = (promptId?: string | null) => {
    if (!promptId) return undefined
    return prompts.find((prompt) => prompt.id === promptId)
  }

  const getSkillById = (skillId?: string | null) => {
    if (!skillId) return undefined
    return allSkills.find((skill) => skill.id === skillId) || availableSkills.find((skill) => skill.id === skillId)
  }

  const formatSlotBinding = (slot: PromptSlot) => {
    if (slot.slot_name === 'writing_rules' && !slot.prompt_template_id) {
      return '动态 Writing Rules'
    }
    const prompt = getPromptById(slot.prompt_template_id)
    return prompt ? `${prompt.name} (${prompt.id})` : slot.prompt_template_id || '未绑定'
  }

  const enabledPromptSlots = (template: AgentTemplate) => (template.prompt_slots || []).filter((slot) => slot.is_enabled)
  const enabledSkillSlots = (template: AgentTemplate) => (template.skill_slots || []).filter((slot) => slot.is_enabled)

  const handleCreate = async () => {
    setEditingTemplate(null)
    setFormData({
      name: '',
      description: '',
      agent_type: 'character',
      prompt_slots: [],
      skill_slots: [],
      default_prompt_order: [],
      default_skill_order: [],
      default_model: '',
      default_temperature: 0.7,
      tags: [],
      scenario: 'default',
      is_optional: false,
      is_enabled: true,
    })
    setAvailableSkills([])
    setShowEditModal(true)
  }

  const handleEdit = async (template: AgentTemplate) => {
    setEditingTemplate(template)
    setFormData({
      name: template.name,
      description: template.description,
      agent_type: template.agent_type,
      prompt_slots: template.prompt_slots || [],
      skill_slots: template.skill_slots || [],
      default_prompt_order: template.default_prompt_order || [],
      default_skill_order: template.default_skill_order || [],
      default_model: template.default_model || '',
      default_temperature: template.default_temperature ?? 0.7,
      tags: template.tags || [],
      scenario: template.scenario || 'default',
      is_system: template.is_system,
      is_optional: template.is_optional,
      is_enabled: template.is_enabled,
    })
    setShowEditModal(true)

    // 加载该 Agent 类型可用的 Skills
    await loadSkillsForAgentType(template.agent_type, template.scenario || 'default')
  }

  const loadSkillsForAgentType = async (agentType: AgentType, scenario?: string) => {
    setLoadingSkills(true)
    try {
      const skills = await getAgentTypeSkills(agentType, scenario || formData.scenario || 'default')
      setAvailableSkills(skills)
    } catch (error) {
      console.error('Failed to load skills:', error)
      setAvailableSkills([])
    } finally {
      setLoadingSkills(false)
    }
  }

  const handleDelete = async (templateId: string) => {
    if (!confirm('确定要删除此 Agent 模板吗？')) return
    try {
      await deleteAgentTemplate(templateId)
      await loadTemplates()
      bumpConfigRefreshKey()
    } catch (error) {
      console.error('Failed to delete template:', error)
    }
  }

  const handlePreview = async (template: AgentTemplate) => {
    setEditingTemplate(template)
    setShowPreviewModal(true)
    try {
      const result = await previewAgentTemplate(template.id, currentProject?.id)
      setPreviewResult(result)
    } catch (error) {
      console.error('Failed to preview template:', error)
    }
  }

  const handleToggle = async (template: AgentTemplate) => {
    try {
      await toggleAgentTemplate(template.id, !template.is_enabled, currentProject?.id)
      await loadTemplates()
      bumpConfigRefreshKey()
    } catch (error) {
      console.error('Failed to toggle template:', error)
    }
  }

  const handleConfigChanged = async () => {
    await loadTemplates()
    bumpConfigRefreshKey()
  }

  const handleSave = async () => {
    try {
      const payload = {
        ...formData,
        default_model: formData.default_model?.trim() || null,
        default_temperature: Number(formData.default_temperature ?? 0.7),
        default_prompt_order: (formData.prompt_slots || [])
          .filter((slot) => slot.is_enabled)
          .map((slot) => slot.slot_name)
          .filter(Boolean),
        default_skill_order: (formData.skill_slots || [])
          .filter((slot) => slot.is_enabled)
          .map((slot) => slot.slot_name)
          .filter(Boolean),
      }

      if (editingTemplate) {
        await updateAgentTemplate(editingTemplate.id, payload as UpdateAgentTemplateDTO)
      } else {
        await createAgentTemplate(payload)
      }
      setShowEditModal(false)
      await loadTemplates()
      bumpConfigRefreshKey()
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

  // Skill 插槽操作
  const handleAddSkillSlot = () => {
    const currentSlots = formData.skill_slots || []
    const newSlot: SkillSlot = {
      slot_name: '',
      description: '',
      skill_id: '',
      is_enabled: true,
      is_required: false,
      priority: currentSlots.length * 10,
      variable_overrides: {},
    }
    setFormData({
      ...formData,
      skill_slots: [...currentSlots, newSlot],
    })
  }

  const handleSelectSkill = (skill: Skill) => {
    const currentSlots = formData.skill_slots || []
    const newSlot: SkillSlot = {
      slot_name: skill.name,
      description: skill.description,
      skill_id: skill.id,
      is_enabled: true,
      is_required: false,
      priority: skill.priority,
      variable_overrides: {},
    }
    setFormData({
      ...formData,
      skill_slots: [...currentSlots, newSlot],
    })
  }

  const handleUpdateSkillSlot = (index: number, field: keyof SkillSlot, value: any) => {
    const currentSlots = formData.skill_slots || []
    const newSlots = [...currentSlots]
    newSlots[index] = { ...newSlots[index], [field]: value }
    setFormData({ ...formData, skill_slots: newSlots })
  }

  const handleRemoveSkillSlot = (index: number) => {
    const currentSlots = formData.skill_slots || []
    setFormData({
      ...formData,
      skill_slots: currentSlots.filter((_, i) => i !== index),
    })
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

      <div className="flex-1 overflow-auto p-4 space-y-6">
        {currentProject?.id ? (
          <AgentConfigPanel
            projectId={currentProject.id}
            refreshKey={configRefreshKey}
            agentTypeFilter={selectedType}
            onChanged={handleConfigChanged}
          />
        ) : (
          <Card className={`p-4 ${isDark ? 'bg-gray-900 border-gray-800' : 'bg-blue-50 border-blue-200'}`}>
            <div className={`text-sm ${isDark ? 'text-gray-300' : 'text-gray-700'}`}>
              选择项目后，可在这里查看、预览、编辑和重置该项目的 Agent 覆盖配置。
            </div>
          </Card>
        )}

        <div>
          <div className="flex items-center justify-between mb-3">
            <div>
              <h2 className={`text-xl font-bold ${isDark ? 'text-white' : 'text-gray-800'}`}>Agent 模板列表</h2>
              <p className={`mt-1 text-sm ${isDark ? 'text-gray-400' : 'text-gray-500'}`}>
                模板定义全局默认结构；上方的项目级配置用于覆盖当前项目的运行时行为。
              </p>
            </div>
          </div>

          {loading ? (
            <div className={`text-center py-8 ${isDark ? 'text-gray-400' : 'text-gray-500'}`}>加载中...</div>
          ) : (!templates || templates.length === 0) ? (
            <div className={`text-center py-8 ${isDark ? 'text-gray-400' : 'text-gray-500'}`}>暂无数据</div>
          ) : (
            <div className="space-y-4">
              {templates.map((template) => (
                <Card key={template.id} className={`p-4 ${!template.is_enabled && template.is_optional ? 'opacity-60' : ''}`}>
                  <div className="flex items-start justify-between">
                    <div className="flex-1">
                      <div className="flex items-center gap-2 mb-1">
                        <h3 className={`font-semibold text-lg ${isDark ? 'text-white' : 'text-gray-800'}`}>{template.name}</h3>
                        {template.is_system && (
                          <span className="px-2 py-1 text-xs bg-blue-900 text-blue-300 rounded">系统</span>
                        )}
                        {template.is_optional && (
                          <span className="px-2 py-1 text-xs bg-purple-900 text-purple-300 rounded">可选</span>
                        )}
                        {!isCoreType(template.agent_type) && template.is_optional && (
                          <span className={`px-2 py-1 text-xs rounded ${template.is_enabled ? 'bg-green-900 text-green-300' : 'bg-gray-700 text-gray-400'}`}>
                            {currentProject?.id
                              ? (template.is_enabled ? '项目已启用' : '项目已禁用')
                              : (template.is_enabled ? '已启用' : '已禁用')}
                          </span>
                        )}
                        <span className={`px-2 py-1 text-xs rounded ${isDark ? 'bg-gray-700' : 'bg-gray-200'}`}>
                          {AGENT_TYPE_LABELS[template.agent_type]}
                        </span>
                        <span className={`px-2 py-1 text-xs rounded ${isDark ? 'bg-gray-700 text-gray-300' : 'bg-gray-200 text-gray-600'}`}>
                          {template.scenario || 'default'}
                        </span>
                      </div>
                      <p className={`text-sm mb-2 ${isDark ? 'text-gray-400' : 'text-gray-500'}`}>{template.description}</p>

                      <div className="space-y-3 mb-2">
                        <div>
                          <div className="flex items-center gap-2 mb-2">
                            <span className={`text-sm ${isDark ? 'text-gray-500' : 'text-gray-400'}`}>Prompt / Rule 绑定：</span>
                            <span className={`text-xs ${isDark ? 'text-gray-600' : 'text-gray-400'}`}>
                              按 default_prompt_order / 插槽顺序加载
                            </span>
                          </div>
                          <div className="flex gap-2 flex-wrap">
                            {enabledPromptSlots(template).length ? enabledPromptSlots(template).map((slot, idx) => {
                              const prompt = getPromptById(slot.prompt_template_id)
                              const isWritingRules = slot.slot_name === 'writing_rules' && !slot.prompt_template_id
                              return (
                                <span
                                  key={`${template.id}-prompt-${slot.slot_name}-${idx}`}
                                  title={formatSlotBinding(slot)}
                                  className={`px-2 py-1 text-xs rounded border ${
                                    isWritingRules
                                      ? 'bg-amber-900/40 text-amber-300 border-amber-700'
                                      : prompt
                                        ? 'bg-green-900/40 text-green-300 border-green-700'
                                        : isDark
                                          ? 'bg-gray-800 text-gray-400 border-gray-700'
                                          : 'bg-gray-100 text-gray-500 border-gray-200'
                                  }`}
                                >
                                  <span className="font-medium">{idx + 1}. {slot.slot_name}</span>
                                  <span className="opacity-75"> → {isWritingRules ? '动态规则' : prompt?.name || slot.prompt_template_id || '未绑定'}</span>
                                </span>
                              )
                            }) : (
                              <span className={`text-xs ${isDark ? 'text-gray-500' : 'text-gray-400'}`}>无启用插槽</span>
                            )}
                          </div>
                        </div>

                        <div>
                          <div className="flex items-center gap-2 mb-2">
                            <span className={`text-sm ${isDark ? 'text-gray-500' : 'text-gray-400'}`}>Skill / md 绑定：</span>
                            <span className={`text-xs ${isDark ? 'text-gray-600' : 'text-gray-400'}`}>
                              由模板 skill_slots 显式加载
                            </span>
                          </div>
                          <div className="flex gap-2 flex-wrap">
                            {enabledSkillSlots(template).length ? enabledSkillSlots(template).map((slot, idx) => {
                              const skill = getSkillById(slot.skill_id)
                              return (
                                <span
                                  key={`${template.id}-skill-${slot.slot_name}-${idx}`}
                                  title={skill ? `${skill.name} (${skill.id})` : slot.skill_id || '未绑定'}
                                  className={`px-2 py-1 text-xs rounded border ${
                                    skill || slot.skill_id
                                      ? 'bg-purple-900/40 text-purple-300 border-purple-700'
                                      : isDark
                                        ? 'bg-gray-800 text-gray-400 border-gray-700'
                                        : 'bg-gray-100 text-gray-500 border-gray-200'
                                  }`}
                                >
                                  <span className="font-medium">{idx + 1}. {slot.slot_name}</span>
                                  <span className="opacity-75"> → {skill?.name || slot.skill_id || '未绑定'}</span>
                                </span>
                              )
                            }) : (
                              <span className={`text-xs ${isDark ? 'text-gray-500' : 'text-gray-400'}`}>无启用 Skill</span>
                            )}
                          </div>
                        </div>
                      </div>

                    </div>

                    <div className="flex gap-2 items-center">
                      {template.is_optional && (
                        <Button
                          size="sm"
                          variant={template.is_enabled ? 'primary' : 'secondary'}
                          onClick={() => handleToggle(template)}
                          title={template.is_enabled ? '点击禁用' : '点击启用'}
                        >
                          {template.is_enabled ? (
                            <ToggleRight className="w-4 h-4 mr-1" />
                          ) : (
                            <ToggleLeft className="w-4 h-4 mr-1" />
                          )}
                          {template.is_enabled ? '启用' : '禁用'}
                        </Button>
                      )}

                      {!template.is_optional && isCoreType(template.agent_type) && (
                        <span className={`flex items-center gap-1 text-xs ${isDark ? 'text-gray-500' : 'text-gray-400'}`}>
                          <Lock className="w-3 h-3" />
                          核心
                        </span>
                      )}

                      <Button size="sm" variant="secondary" onClick={() => handlePreview(template)}>
                        <Eye className="w-4 h-4 mr-1" />
                        预览
                      </Button>
                      <Button size="sm" variant="secondary" onClick={() => handleEdit(template)}>
                        <Edit2 className="w-4 h-4 mr-1" />
                        编辑
                      </Button>
                      {!template.is_system && (
                        <Button size="sm" variant="danger" onClick={() => handleDelete(template.id)}>
                          <Trash2 className="w-4 h-4" />
                        </Button>
                      )}
                    </div>
                  </div>
                </Card>
              ))}
            </div>
          )}
        </div>
      </div>
      <Modal
        isOpen={showEditModal}
        onClose={() => setShowEditModal(false)}
        title={editingTemplate ? '编辑模板' : '新建模板'}
        size="2xl"
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
                onChange={(e) => {
                  const newType = e.target.value as AgentType
                  setFormData({ ...formData, agent_type: newType })
                  loadSkillsForAgentType(newType, formData.scenario || 'default')
                }}
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
            <label className={`block text-sm mb-1 ${isDark ? 'text-gray-400' : 'text-gray-600'}`}>场景</label>
            <Input
              value={formData.scenario || 'default'}
              onChange={(e) => {
                const scenario = e.target.value || 'default'
                setFormData({ ...formData, scenario })
                loadSkillsForAgentType(formData.agent_type, scenario)
              }}
              placeholder="如：workflow_chapter_generation"
            />
            <p className={`mt-1 text-xs ${isDark ? 'text-gray-500' : 'text-gray-400'}`}>同一 Agent 类型可通过不同场景加载不同模板。</p>
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

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className={`block text-sm mb-1 ${isDark ? 'text-gray-400' : 'text-gray-600'}`}>默认模型</label>
              <Input
                value={formData.default_model || ''}
                onChange={(e) => setFormData({ ...formData, default_model: e.target.value })}
                placeholder="留空则使用项目/全局模型配置"
              />
            </div>
            <div>
              <label className={`block text-sm mb-1 ${isDark ? 'text-gray-400' : 'text-gray-600'}`}>默认温度</label>
              <Input
                type="number"
                min="0"
                max="2"
                step="0.1"
                value={formData.default_temperature ?? 0.7}
                onChange={(e) => setFormData({ ...formData, default_temperature: Number(e.target.value) })}
              />
            </div>
          </div>

          <div className="grid grid-cols-3 gap-4">
            <label className={`flex items-center gap-2 text-sm ${isDark ? 'text-gray-300' : 'text-gray-600'}`}>
              <input
                type="checkbox"
                checked={!!formData.is_optional}
                onChange={(e) => setFormData({ ...formData, is_optional: e.target.checked })}
              />
              可选 Agent
            </label>
            <label className={`flex items-center gap-2 text-sm ${isDark ? 'text-gray-300' : 'text-gray-600'}`}>
              <input
                type="checkbox"
                checked={formData.is_enabled ?? true}
                onChange={(e) => setFormData({ ...formData, is_enabled: e.target.checked })}
              />
              启用模板
            </label>
            <label className={`flex items-center gap-2 text-sm ${isDark ? 'text-gray-300' : 'text-gray-600'}`}>
              <input
                type="checkbox"
                checked={!!formData.is_system}
                onChange={(e) => setFormData({ ...formData, is_system: e.target.checked })}
              />
              系统种子
            </label>
          </div>

          <div>
            <label className={`block text-sm mb-1 ${isDark ? 'text-gray-400' : 'text-gray-600'}`}>标签</label>
            <Input
              value={(formData.tags || []).join(', ')}
              onChange={(e) => setFormData({
                ...formData,
                tags: e.target.value.split(',').map((tag) => tag.trim()).filter(Boolean),
              })}
              placeholder="例如：director, writer, workflow"
            />
            <p className={`mt-1 text-xs ${isDark ? 'text-gray-500' : 'text-gray-400'}`}>多个标签用英文逗号分隔。</p>
          </div>

          {/* Prompt 插槽 */}
          <div>
            <div className="flex items-center justify-between mb-2">
              <label className={`block text-sm font-medium ${isDark ? 'text-gray-300' : 'text-gray-700'}`}>Prompt 插槽</label>
              <Button size="sm" variant="secondary" onClick={handleAddSlot}>
                <Plus className="w-4 h-4 mr-1" />
                添加插槽
              </Button>
            </div>

            {(formData.prompt_slots?.length ?? 0) > 0 && (
              <div className="space-y-3">
                {(formData.prompt_slots || []).map((slot, index) => (
                  <div key={index} className={`p-4 rounded-lg border ${isDark ? 'bg-gray-800 border-gray-700' : 'bg-gray-50 border-gray-200'}`}>
                    {/* 插槽第一行：名称和操作按钮 */}
                    <div className="flex items-center gap-3 mb-3">
                      <GripVertical className={`w-4 h-4 cursor-move flex-shrink-0 ${isDark ? 'text-gray-500' : 'text-gray-400'}`} />
                      <div className="flex-1">
                        <label className={`block text-xs mb-1 ${isDark ? 'text-gray-500' : 'text-gray-500'}`}>插槽名称</label>
                        <Input
                          value={slot.slot_name}
                          onChange={(e) => handleUpdateSlot(index, 'slot_name', e.target.value)}
                          placeholder="如：role_definition"
                        />
                      </div>
                      <div className="flex gap-1 flex-shrink-0">
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
                      <label className={`flex items-center gap-1 text-sm flex-shrink-0 ${isDark ? 'text-gray-300' : 'text-gray-600'}`}>
                        <input
                          type="checkbox"
                          checked={slot.is_enabled}
                          onChange={(e) => handleUpdateSlot(index, 'is_enabled', e.target.checked)}
                          className="w-4 h-4"
                        />
                        启用
                      </label>
                      <Button size="sm" variant="danger" onClick={() => handleRemoveSlot(index)} className="flex-shrink-0">
                        <Trash2 className="w-4 h-4" />
                      </Button>
                    </div>

                    {/* 插槽第二行：描述和 Prompt 模板选择 */}
                    <div className="grid grid-cols-2 gap-3">
                      <div>
                        <label className={`block text-xs mb-1 ${isDark ? 'text-gray-500' : 'text-gray-500'}`}>插槽描述</label>
                        <Input
                          value={slot.description}
                          onChange={(e) => handleUpdateSlot(index, 'description', e.target.value)}
                          placeholder="描述这个插槽的用途"
                        />
                      </div>
                      <div>
                        <label className={`block text-xs mb-1 ${isDark ? 'text-gray-500' : 'text-gray-500'}`}>关联 Prompt 模板 / 动态规则</label>
                        <select
                          className={`w-full border rounded px-3 py-2 text-sm ${isDark ? 'bg-gray-700 border-gray-600 text-white' : 'bg-white border-gray-300 text-gray-800'}`}
                          value={slot.prompt_template_id || ''}
                          onChange={(e) =>
                            handleUpdateSlot(index, 'prompt_template_id', e.target.value || null)
                          }
                        >
                          <option value="">{slot.slot_name === 'writing_rules' ? '动态加载 Writing Rules' : '选择 Prompt 模板'}</option>
                          {prompts.map((p) => (
                            <option key={p.id} value={p.id}>
                              {p.name} · {p.category} · {p.id}
                            </option>
                          ))}
                        </select>
                        <p className={`mt-1 text-xs ${isDark ? 'text-gray-500' : 'text-gray-400'}`}>
                          {slot.slot_name === 'writing_rules' && !slot.prompt_template_id
                            ? '此插槽不绑定单个 md prompt，运行时按项目、Agent 类型和场景动态注入 Writing Rules。'
                            : `当前绑定：${formatSlotBinding(slot)}`}
                        </p>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Skill 插槽 */}
          <div>
            <div className="flex items-center justify-between mb-2">
              <label className={`block text-sm font-medium ${isDark ? 'text-gray-300' : 'text-gray-700'}`}>
                <Layers className="w-4 h-4 inline mr-1" />
                Skill 插槽
              </label>
              <Button size="sm" variant="secondary" onClick={handleAddSkillSlot}>
                <Plus className="w-4 h-4 mr-1" />
                添加 Skill
              </Button>
            </div>

            {/* 显示已绑定的 Skills */}
            {(formData.skill_slots?.length ?? 0) > 0 && (
              <div className="space-y-2 mb-3">
                {(formData.skill_slots || []).map((skillSlot, index) => (
                  <div key={index} className={`p-3 rounded-lg border ${isDark ? 'bg-gray-800 border-gray-700' : 'bg-gray-50 border-gray-200'}`}>
                    <div className="flex items-center justify-between gap-3">
                      <div className="flex items-center gap-3 min-w-0">
                        <BookOpen className={`w-4 h-4 flex-shrink-0 ${isDark ? 'text-gray-400' : 'text-gray-500'}`} />
                        <div className="min-w-0">
                          <span className={`font-medium ${isDark ? 'text-gray-200' : 'text-gray-700'}`}>
                            {skillSlot.slot_name}
                          </span>
                          <span className={`text-xs ml-2 ${isDark ? 'text-gray-500' : 'text-gray-400'}`}>
                            → {getSkillById(skillSlot.skill_id)?.name || skillSlot.skill_id || '未绑定'}
                          </span>
                        </div>
                        <label className={`flex items-center gap-1 text-sm flex-shrink-0 ${isDark ? 'text-gray-300' : 'text-gray-600'}`}>
                          <input
                            type="checkbox"
                            checked={skillSlot.is_enabled}
                            onChange={(e) => handleUpdateSkillSlot(index, 'is_enabled', e.target.checked)}
                            className="w-3 h-3"
                          />
                          启用
                        </label>
                      </div>
                      <Button size="sm" variant="danger" onClick={() => handleRemoveSkillSlot(index)}>
                        <Trash2 className="w-3 h-3" />
                      </Button>
                    </div>
                    <div className={`mt-2 text-xs ${isDark ? 'text-gray-500' : 'text-gray-400'}`}>
                      <span>ID：{skillSlot.skill_id || '未绑定'}</span>
                      {getSkillById(skillSlot.skill_id)?.category && <span className="ml-3">分类：{getSkillById(skillSlot.skill_id)?.category}</span>}
                      {getSkillById(skillSlot.skill_id)?.skill_type && <span className="ml-3">类型：{getSkillById(skillSlot.skill_id)?.skill_type}</span>}
                    </div>
                  </div>
                ))}
              </div>
            )}

            {/* 可用 Skills 列表 */}
            {loadingSkills ? (
              <div className={`text-center py-4 text-sm ${isDark ? 'text-gray-400' : 'text-gray-500'}`}>
                加载 Skills...
              </div>
            ) : availableSkills.length > 0 ? (
              <div className={`p-3 rounded-lg border max-h-48 overflow-y-auto ${isDark ? 'bg-gray-800 border-gray-700' : 'bg-white border-gray-200'}`}>
                <p className={`text-xs mb-2 ${isDark ? 'text-gray-400' : 'text-gray-500'}`}>
                  可用 Skills（点击添加）
                </p>
                <div className="space-y-1">
                  {availableSkills.map((skill) => {
                    const isAlreadyAdded = (formData.skill_slots || []).some(s => s.skill_id === skill.id)
                    return (
                      <div
                        key={skill.id}
                        onClick={() => !isAlreadyAdded && handleSelectSkill(skill)}
                        className={`p-2 rounded text-sm cursor-pointer flex items-center justify-between ${
                          isAlreadyAdded
                            ? 'opacity-50 cursor-not-allowed'
                            : isDark ? 'hover:bg-gray-700' : 'hover:bg-gray-50'
                        }`}
                      >
                        <div>
                          <span className={isDark ? 'text-gray-200' : 'text-gray-700'}>{skill.name}</span>
                          <span className={`text-xs ml-2 ${isDark ? 'text-gray-500' : 'text-gray-400'}`}>
                            {skill.skill_type === 'knowledge' ? '知识' : skill.skill_type === 'prompt' ? '提示词' : skill.skill_type}
                          </span>
                        </div>
                        <span className={`text-xs ${isDark ? 'text-gray-500' : 'text-gray-400'}`}>
                          优先级: {skill.priority}
                        </span>
                      </div>
                    )
                  })}
                </div>
              </div>
            ) : (
              <div className={`text-center py-4 text-sm ${isDark ? 'text-gray-400' : 'text-gray-500'}`}>
                该 Agent 类型暂无可用 Skills
              </div>
            )}
          </div>

          {/* 系统种子模板提示 */}
          {editingTemplate?.is_system && (
            <div className={`p-3 rounded-lg flex items-center gap-2 ${isDark ? 'bg-blue-900/30 text-blue-300' : 'bg-blue-50 text-blue-700'}`}>
              <AlertTriangle className="w-4 h-4 flex-shrink-0" />
              <span className="text-sm">这是系统种子模板。Prompt / Skill / 场景关系会保存到数据库并作为运行时配置生效；系统种子不可删除，但可以在此编辑。</span>
            </div>
          )}

          <div className="flex justify-end gap-2 pt-4">
            <Button variant="secondary" onClick={() => setShowEditModal(false)} className="whitespace-nowrap">
              取消
            </Button>
            <Button onClick={handleSave} className="whitespace-nowrap">{editingTemplate ? '保存' : '创建'}</Button>
          </div>
        </div>
      </Modal>

      {/* 预览 Modal */}
      <Modal isOpen={showPreviewModal} onClose={() => setShowPreviewModal(false)} title="模板预览" size="xl">
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

            {previewResult.render_trace && (
              <div>
                <h4 className={`text-sm mb-2 ${isDark ? 'text-gray-400' : 'text-gray-600'}`}>Render Trace</h4>
                <div className={`p-3 rounded text-sm space-y-2 ${isDark ? 'bg-gray-800 text-gray-300' : 'bg-gray-100 text-gray-700'}`}>
                  <div>Agent：{previewResult.render_trace.agent_type}</div>
                  <div>Template：{previewResult.render_trace.template_id || '无'}</div>
                  {previewResult.render_trace.scenario && <div>Scenario：{previewResult.render_trace.scenario}</div>}
                  <div>Template Scenario：{previewResult.render_trace.template_scenario || 'default'}</div>
                  <div>Config：{previewResult.render_trace.config_id || '无'}</div>
                  <div>Prompt IDs：{previewResult.render_trace.prompt_ids.length ? previewResult.render_trace.prompt_ids.join(', ') : '无'}</div>
                  <div>Skill IDs：{previewResult.render_trace.skill_ids.length ? previewResult.render_trace.skill_ids.join(', ') : '无'}</div>
                  <div>Writing Rule IDs：{previewResult.render_trace.writing_rule_ids.length ? previewResult.render_trace.writing_rule_ids.join(', ') : '无'}</div>
                  {previewResult.render_trace.writing_rules?.always_rule_ids?.length ? (
                    <div>Always Rules：{previewResult.render_trace.writing_rules.always_rule_ids.join(', ')}</div>
                  ) : null}
                  {previewResult.render_trace.writing_rules?.query ? (
                    <div>Rule Query：{previewResult.render_trace.writing_rules.query}</div>
                  ) : null}
                  {previewResult.render_trace.writing_rules?.resolved_scope ? (
                    <div>Rule Scope：{JSON.stringify(previewResult.render_trace.writing_rules.resolved_scope)}</div>
                  ) : null}
                  {previewResult.render_trace.writing_rules?.retrieved_rules?.length ? (
                    <div>
                      <div className="mb-1">命中规则：</div>
                      <ul className="list-disc pl-5 space-y-1">
                        {previewResult.render_trace.writing_rules.retrieved_rules.map((rule) => (
                          <li key={rule.id || rule.name}>
                            <span className="font-medium">{rule.name || rule.id}</span>
                            <span className="opacity-75"> [{rule.severity || 'unknown'} / {rule.reason || 'unknown'}]</span>
                            {typeof rule.score === 'number' && <span className="opacity-60"> score={rule.score.toFixed(3)}</span>}
                          </li>
                        ))}
                      </ul>
                    </div>
                  ) : null}
                  {previewResult.render_trace.fallbacks_used.length ? (
                    <div>Fallbacks：{previewResult.render_trace.fallbacks_used.join(', ')}</div>
                  ) : null}
                  {previewResult.render_trace.deprecated_sources_used.length ? (
                    <div>Deprecated：{previewResult.render_trace.deprecated_sources_used.join(', ')}</div>
                  ) : null}
                </div>
              </div>
            )}

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
