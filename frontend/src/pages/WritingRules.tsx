/**
 * 写作规则管理页面
 * v7 核心功能：写作规则的CRUD、规则集管理、项目写作配置
 */

import { useEffect, useState } from 'react'
import { Card, Button, Input, TextArea, Modal } from '@/components/ui'
import {
  getWritingRules,
  createWritingRule,
  updateWritingRule,
  deleteWritingRule,
  getWritingRuleSets,
  getWritingRuleSet,
  createWritingRuleSet,
  updateWritingRuleSet,
  deleteWritingRuleSet,
  getProjectWritingConfig,
  updateProjectWritingConfig,
  previewWritingPrompt,
  WritingRule,
  WritingRuleSet,
  WritingRuleCategory,
  RuleSeverity,
  CreateWritingRuleDTO,
  UpdateWritingRuleDTO,
  ProjectWritingConfig,
} from '@/api/writingRules'
import { useProject } from '@/contexts/ProjectContext'
import { useTheme } from '@/contexts/ThemeContext'
import { Search, Plus, Edit2, Trash2, Eye, Check, BookOpen, Layers, Settings } from 'lucide-react'

const CATEGORY_LABELS: Record<WritingRuleCategory, string> = {
  dialogue: '对话类',
  structure: '结构类',
  style: '风格类',
  pacing: '节奏类',
  character: '角色塑造类',
  plot: '剧情类',
  format: '格式类',
  grammar: '语法类',
}

const SEVERITY_LABELS: Record<RuleSeverity, { label: string; color: string }> = {
  required: { label: '必须', color: 'bg-red-900 text-red-300' },
  strong: { label: '强烈', color: 'bg-orange-900 text-orange-300' },
  recommended: { label: '推荐', color: 'bg-yellow-900 text-yellow-300' },
  optional: { label: '可选', color: 'bg-gray-700 text-gray-300' },
  info: { label: '信息', color: 'bg-blue-900 text-blue-300' },
}

type TabType = 'rules' | 'sets' | 'config'

export default function WritingRules() {
  const { currentProject } = useProject()
  const { theme } = useTheme()
  const isDark = theme === 'dark'

  const [activeTab, setActiveTab] = useState<TabType>('rules')

  // 规则列表状态
  const [rules, setRules] = useState<WritingRule[]>([])
  const [ruleSets, setRuleSets] = useState<WritingRuleSet[]>([])
  const [projectConfig, setProjectConfig] = useState<ProjectWritingConfig | null>(null)
  const [loading, setLoading] = useState(true)

  // 筛选状态
  const [searchQuery, setSearchQuery] = useState('')
  const [selectedCategory, setSelectedCategory] = useState<WritingRuleCategory | null>(null)
  const [selectedSeverity, setSelectedSeverity] = useState<RuleSeverity | null>(null)

  // Modal 状态
  const [showEditModal, setShowEditModal] = useState(false)
  const [showPreviewModal, setShowPreviewModal] = useState(false)
  const [editingRule, setEditingRule] = useState<WritingRule | null>(null)
  const [previewContent, setPreviewContent] = useState('')

  // 表单状态
  const [formData, setFormData] = useState<CreateWritingRuleDTO>({
    name: '',
    description: '',
    category: 'dialogue',
    severity: 'recommended',
    content: '',
    examples: [],
    anti_patterns: [],
    tags: [],
  })
  const [exampleInput, setExampleInput] = useState('')
  const [antiPatternInput, setAntiPatternInput] = useState('')
  const [tagInput, setTagInput] = useState('')

  // 规则集表单
  const [showRuleSetModal, setShowRuleSetModal] = useState(false)
  const [editingRuleSet, setEditingRuleSet] = useState<WritingRuleSet | null>(null)
  const [viewingRuleSet, setViewingRuleSet] = useState<WritingRuleSet | null>(null)
  const [ruleSetForm, setRuleSetForm] = useState({
    name: '',
    description: '',
    rule_ids: [] as string[],
    target_genre: '',
    tags: [] as string[],
  })

  useEffect(() => {
    loadData()
  }, [activeTab, currentProject])

  // 筛选状态变化时重新加载规则列表
  useEffect(() => {
    if (activeTab === 'rules') {
      const loadFilteredRules = async () => {
        setLoading(true)
        try {
          const data = await getWritingRules(
            selectedCategory || undefined,
            selectedSeverity || undefined
          )
          setRules(data)
        } catch (error) {
          console.error('Failed to load filtered rules:', error)
        } finally {
          setLoading(false)
        }
      }
      loadFilteredRules()
    }
  }, [selectedCategory, selectedSeverity, activeTab])

  const loadData = async () => {
    setLoading(true)
    try {
      if (activeTab === 'rules') {
        const data = await getWritingRules(selectedCategory || undefined, selectedSeverity || undefined)
        setRules(data)
      } else if (activeTab === 'sets') {
        // 同时加载规则集和规则列表（用于显示规则名称）
        const [setsData, rulesData] = await Promise.all([
          getWritingRuleSets(),
          getWritingRules()
        ])
        setRuleSets(setsData)
        setRules(rulesData)
      } else if (activeTab === 'config' && currentProject) {
        const config = await getProjectWritingConfig(currentProject.id)
        setProjectConfig(config)
        // 同时加载规则列表用于选择
        const allRules = await getWritingRules()
        setRules(allRules)
        const allSets = await getWritingRuleSets()
        setRuleSets(allSets)
      }
    } catch (error) {
      console.error('Failed to load data:', error)
    } finally {
      setLoading(false)
    }
  }

  const handleCreateRule = () => {
    setEditingRule(null)
    setFormData({
      name: '',
      description: '',
      category: 'dialogue',
      severity: 'recommended',
      content: '',
      examples: [],
      anti_patterns: [],
      tags: [],
    })
    setShowEditModal(true)
  }

  const handleEditRule = (rule: WritingRule) => {
    setEditingRule(rule)
    setFormData({
      name: rule.name,
      description: rule.description,
      category: rule.category,
      severity: rule.severity,
      content: rule.content,
      examples: rule.examples || [],
      anti_patterns: rule.anti_patterns || [],
      tags: rule.tags || [],
    })
    setShowEditModal(true)
  }

  const handleDeleteRule = async (ruleId: string) => {
    if (!confirm('确定要删除此规则吗？')) return
    try {
      await deleteWritingRule(ruleId)
      loadData()
    } catch (error) {
      console.error('Failed to delete rule:', error)
    }
  }

  const handleSaveRule = async () => {
    try {
      if (editingRule) {
        await updateWritingRule(editingRule.id, formData as UpdateWritingRuleDTO)
      } else {
        await createWritingRule(formData)
      }
      setShowEditModal(false)
      loadData()
    } catch (error) {
      console.error('Failed to save rule:', error)
    }
  }

  const handlePreview = async () => {
    if (!currentProject) return
    setShowPreviewModal(true)
    try {
      const result = await previewWritingPrompt(currentProject.id)
      setPreviewContent(result.prompt)
    } catch (error) {
      console.error('Failed to preview:', error)
      setPreviewContent('预览失败')
    }
  }

  const handleToggleRule = async (ruleId: string) => {
    if (!projectConfig || !currentProject) return
    const enabledIds = projectConfig.enabled_rule_ids.includes(ruleId)
      ? projectConfig.enabled_rule_ids.filter(id => id !== ruleId)
      : [...projectConfig.enabled_rule_ids, ruleId]

    try {
      await updateProjectWritingConfig(currentProject.id, { enabled_rule_ids: enabledIds })
      setProjectConfig({ ...projectConfig, enabled_rule_ids: enabledIds })
    } catch (error) {
      console.error('Failed to update config:', error)
    }
  }

  const handleToggleRuleSet = async (ruleSetId: string) => {
    if (!projectConfig || !currentProject) return
    const enabledIds = projectConfig.enabled_rule_set_ids.includes(ruleSetId)
      ? projectConfig.enabled_rule_set_ids.filter(id => id !== ruleSetId)
      : [...projectConfig.enabled_rule_set_ids, ruleSetId]

    try {
      await updateProjectWritingConfig(currentProject.id, { enabled_rule_set_ids: enabledIds })
      setProjectConfig({ ...projectConfig, enabled_rule_set_ids: enabledIds })
    } catch (error) {
      console.error('Failed to update config:', error)
    }
  }

  // 规则集操作
  const handleViewRuleSet = (ruleSet: WritingRuleSet) => {
    setViewingRuleSet(ruleSet)
  }

  const handleEditRuleSet = (ruleSet: WritingRuleSet) => {
    setEditingRuleSet(ruleSet)
    setRuleSetForm({
      name: ruleSet.name,
      description: ruleSet.description,
      rule_ids: ruleSet.rule_ids,
      target_genre: ruleSet.target_genre || '',
      tags: ruleSet.tags,
    })
    setShowRuleSetModal(true)
  }

  const handleCreateRuleSet = () => {
    setEditingRuleSet(null)
    setRuleSetForm({
      name: '',
      description: '',
      rule_ids: [],
      target_genre: '',
      tags: [],
    })
    setShowRuleSetModal(true)
  }

  const handleSaveRuleSet = async () => {
    try {
      if (editingRuleSet) {
        // 更新规则集
        await updateWritingRuleSet(editingRuleSet.id, ruleSetForm)
      } else {
        // 创建规则集
        await createWritingRuleSet(ruleSetForm)
      }
      setShowRuleSetModal(false)
      loadData()
    } catch (error) {
      console.error('Failed to save rule set:', error)
    }
  }

  const handleToggleRuleInSet = (ruleId: string) => {
    const currentIds = ruleSetForm.rule_ids
    if (currentIds.includes(ruleId)) {
      setRuleSetForm({ ...ruleSetForm, rule_ids: currentIds.filter(id => id !== ruleId) })
    } else {
      setRuleSetForm({ ...ruleSetForm, rule_ids: [...currentIds, ruleId] })
    }
  }

  const addExample = () => {
    if (exampleInput.trim()) {
      const currentExamples = formData.examples || []
      setFormData({ ...formData, examples: [...currentExamples, exampleInput.trim()] })
      setExampleInput('')
    }
  }

  const addAntiPattern = () => {
    if (antiPatternInput.trim()) {
      const currentAntiPatterns = formData.anti_patterns || []
      setFormData({ ...formData, anti_patterns: [...currentAntiPatterns, antiPatternInput.trim()] })
      setAntiPatternInput('')
    }
  }

  const addTag = () => {
    const currentTags = formData.tags || []
    if (tagInput.trim() && !currentTags.includes(tagInput.trim())) {
      setFormData({ ...formData, tags: [...currentTags, tagInput.trim()] })
      setTagInput('')
    }
  }

  // 过滤规则
  const filteredRules = searchQuery
    ? (rules || []).filter(r =>
        r.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
        r.description.toLowerCase().includes(searchQuery.toLowerCase())
      )
    : (rules || [])

  // 计算启用的规则集中包含的所有规则ID（去重）
  const getRuleIdsFromEnabledSets = () => {
    const ruleIds = new Set<string>()
    if (projectConfig) {
      for (const setId of projectConfig.enabled_rule_set_ids) {
        const ruleSet = ruleSets.find(s => s.id === setId)
        if (ruleSet) {
          for (const ruleId of ruleSet.rule_ids) {
            ruleIds.add(ruleId)
          }
        }
      }
    }
    return ruleIds
  }

  // 判断规则是否被规则集包含
  const isRuleFromEnabledSet = (ruleId: string) => {
    return getRuleIdsFromEnabledSets().has(ruleId)
  }

  return (
    <div className="h-[calc(100vh-4rem)] flex flex-col">
      {/* 头部 - 固定在顶部 */}
      <div className={`sticky top-0 z-10 p-4 border-b ${isDark ? 'bg-gray-900 border-gray-700' : 'bg-white border-gray-200'}`}>
        <div className="flex items-center justify-between mb-4">
          <h1 className={`text-2xl font-bold ${isDark ? 'text-white' : 'text-gray-800'}`}>写作规则</h1>
          {activeTab === 'rules' && (
            <Button onClick={handleCreateRule}>
              <Plus className="w-4 h-4 mr-2" />
              新建规则
            </Button>
          )}
          {activeTab === 'sets' && (
            <Button onClick={handleCreateRuleSet}>
              <Plus className="w-4 h-4 mr-2" />
              新建规则集
            </Button>
          )}
          {activeTab === 'config' && (
            <Button onClick={handlePreview}>
              <Eye className="w-4 h-4 mr-2" />
              预览 Prompt
            </Button>
          )}
        </div>

        {/* Tab 切换 */}
        <div className="flex gap-2 mb-4">
          {[
            { key: 'rules', label: '规则列表', icon: <BookOpen className="w-4 h-4" /> },
            { key: 'sets', label: '规则集', icon: <Layers className="w-4 h-4" /> },
            { key: 'config', label: '项目配置', icon: <Settings className="w-4 h-4" /> },
          ].map(tab => (
            <button
              key={tab.key}
              onClick={() => setActiveTab(tab.key as TabType)}
              className={`flex items-center gap-2 px-4 py-2 rounded transition-colors ${
                activeTab === tab.key
                  ? 'bg-blue-600 text-white'
                  : isDark
                    ? 'bg-gray-700 hover:bg-gray-600 text-gray-300'
                    : 'bg-gray-200 hover:bg-gray-300 text-gray-700'
              }`}
            >
              {tab.icon}
              {tab.label}
            </button>
          ))}
        </div>

        {/* 筛选器 */}
        {activeTab === 'rules' && (
          <div className="flex gap-4">
            <Input
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="搜索规则..."
              className="flex-1"
            />
            <select
              className={`border rounded px-3 py-2 text-sm ${isDark ? 'bg-gray-800 border-gray-600 text-white' : 'bg-white border-gray-300 text-gray-800'}`}
              value={selectedCategory || ''}
              onChange={(e) => setSelectedCategory(e.target.value as WritingRuleCategory || null)}
            >
              <option value="">全部分类</option>
              {Object.entries(CATEGORY_LABELS).map(([key, label]) => (
                <option key={key} value={key}>{label}</option>
              ))}
            </select>
            <select
              className={`border rounded px-3 py-2 text-sm ${isDark ? 'bg-gray-800 border-gray-600 text-white' : 'bg-white border-gray-300 text-gray-800'}`}
              value={selectedSeverity || ''}
              onChange={(e) => setSelectedSeverity(e.target.value as RuleSeverity || null)}
            >
              <option value="">全部级别</option>
              {Object.entries(SEVERITY_LABELS).map(([key, { label }]) => (
                <option key={key} value={key}>{label}</option>
              ))}
            </select>
          </div>
        )}
      </div>

      {/* 内容区域 */}
      <div className="flex-1 overflow-auto p-4">
        {loading ? (
          <div className={`text-center py-8 ${isDark ? 'text-gray-400' : 'text-gray-500'}`}>加载中...</div>
        ) : activeTab === 'rules' ? (
          // 规则列表
          <div className="grid gap-4 md:grid-cols-2">
            {filteredRules.map((rule) => (
              <Card key={rule.id} className="p-4">
                <div className="flex items-start justify-between mb-2">
                  <div>
                    <h3 className={`font-semibold text-lg ${isDark ? 'text-white' : 'text-gray-800'}`}>{rule.name}</h3>
                    <p className={`text-sm ${isDark ? 'text-gray-400' : 'text-gray-500'}`}>{rule.description}</p>
                  </div>
                  <div className="flex gap-1">
                    <span className={`px-2 py-1 text-xs rounded ${SEVERITY_LABELS[rule.severity].color}`}>
                      {SEVERITY_LABELS[rule.severity].label}
                    </span>
                    {rule.is_system && (
                      <span className="px-2 py-1 text-xs bg-blue-900 text-blue-300 rounded">系统</span>
                    )}
                  </div>
                </div>

                <div className="flex items-center gap-2 mb-2">
                  <span className={`px-2 py-1 text-xs rounded ${isDark ? 'bg-gray-700' : 'bg-gray-200'}`}>
                    {CATEGORY_LABELS[rule.category]}
                  </span>
                </div>

                <p className={`text-sm mb-3 line-clamp-3 ${isDark ? 'text-gray-500' : 'text-gray-600'}`}>{rule.content.substring(0, 150)}...</p>

                <div className="flex gap-2">
                  <Button size="sm" variant="secondary" onClick={() => handleEditRule(rule)}>
                    <Edit2 className="w-4 h-4 mr-1" />
                    编辑
                  </Button>
                  {!rule.is_system && (
                    <Button size="sm" variant="danger" onClick={() => handleDeleteRule(rule.id)}>
                      <Trash2 className="w-4 h-4" />
                    </Button>
                  )}
                </div>
              </Card>
            ))}
          </div>
        ) : activeTab === 'sets' ? (
          // 规则集列表
          <div className="space-y-4">
            {ruleSets.map((set) => (
              <Card key={set.id} className="p-4">
                <div className="flex items-start justify-between">
                  <div className="flex-1">
                    <div className="flex items-center gap-2">
                      <h3 className={`font-semibold text-lg ${isDark ? 'text-white' : 'text-gray-800'}`}>{set.name}</h3>
                      {set.is_system && (
                        <span className="px-2 py-1 text-xs bg-blue-900 text-blue-300 rounded">系统</span>
                      )}
                    </div>
                    <p className={`text-sm ${isDark ? 'text-gray-400' : 'text-gray-500'}`}>{set.description}</p>
                    <p className={`text-xs mt-1 ${isDark ? 'text-gray-500' : 'text-gray-400'}`}>包含 {set.rule_ids.length} 条规则</p>
                  </div>
                  <div className="flex gap-2">
                    <Button size="sm" variant="secondary" onClick={() => handleViewRuleSet(set)}>
                      <Eye className="w-4 h-4 mr-1" />
                      查看
                    </Button>
                    <Button size="sm" variant="secondary" onClick={() => handleEditRuleSet(set)}>
                      <Edit2 className="w-4 h-4 mr-1" />
                      编辑
                    </Button>
                    {!set.is_system && (
                      <Button size="sm" variant="danger" onClick={async () => {
                        if (!confirm('确定要删除此规则集吗？')) return
                        try {
                          await deleteWritingRuleSet(set.id)
                          loadData()
                        } catch (error) {
                          console.error('Failed to delete rule set:', error)
                        }
                      }}>
                        <Trash2 className="w-4 h-4" />
                      </Button>
                    )}
                  </div>
                </div>
              </Card>
            ))}
          </div>
        ) : (
          // 项目配置
          !currentProject ? (
            <div className={`text-center py-8 ${isDark ? 'text-gray-400' : 'text-gray-500'}`}>请先选择项目</div>
          ) : !projectConfig ? (
            <div className={`text-center py-8 ${isDark ? 'text-gray-400' : 'text-gray-500'}`}>加载配置中...</div>
          ) : (
            <div className="space-y-6">
              {/* 规则集选择 */}
              <Card className="p-4">
                <h3 className={`font-semibold mb-3 ${isDark ? 'text-white' : 'text-gray-800'}`}>启用规则集</h3>
                <div className="grid gap-2 md:grid-cols-2">
                  {ruleSets.map((set) => (
                    <label
                      key={set.id}
                      className={`flex items-center gap-3 p-3 rounded cursor-pointer transition-colors ${
                        projectConfig.enabled_rule_set_ids.includes(set.id)
                          ? 'bg-blue-900/30 border border-blue-500'
                          : isDark
                            ? 'bg-gray-800 hover:bg-gray-700'
                            : 'bg-gray-100 hover:bg-gray-200'
                      }`}
                    >
                      <input
                        type="checkbox"
                        checked={projectConfig.enabled_rule_set_ids.includes(set.id)}
                        onChange={() => handleToggleRuleSet(set.id)}
                        className="w-4 h-4"
                      />
                      <div>
                        <div className={`font-medium ${isDark ? 'text-white' : 'text-gray-800'}`}>{set.name}</div>
                        <div className={`text-xs ${isDark ? 'text-gray-400' : 'text-gray-500'}`}>{set.description}</div>
                      </div>
                    </label>
                  ))}
                </div>
              </Card>

              {/* 单独规则选择 */}
              <Card className="p-4">
                <div className="flex items-center justify-between mb-3">
                  <h3 className={`font-semibold ${isDark ? 'text-white' : 'text-gray-800'}`}>单独启用规则</h3>
                  <p className={`text-xs ${isDark ? 'text-gray-500' : 'text-gray-400'}`}>
                    蓝色边框 = 已被规则集包含
                  </p>
                </div>
                <div className="grid gap-2 md:grid-cols-2 lg:grid-cols-3">
                  {rules.map((rule) => {
                    const isEnabled = projectConfig.enabled_rule_ids.includes(rule.id)
                    const isFromSet = isRuleFromEnabledSet(rule.id)
                    const isChecked = isEnabled || isFromSet

                    return (
                      <label
                        key={rule.id}
                        className={`flex items-center gap-2 p-2 rounded cursor-pointer transition-colors ${
                          isFromSet
                            ? 'bg-blue-900/20 border border-blue-500'
                            : isEnabled
                              ? 'bg-green-900/30 border border-green-500'
                              : isDark
                                ? 'bg-gray-800 hover:bg-gray-700'
                                : 'bg-gray-100 hover:bg-gray-200'
                        }`}
                      >
                        <input
                          type="checkbox"
                          checked={isChecked}
                          onChange={() => handleToggleRule(rule.id)}
                          className="w-4 h-4"
                        />
                        <div className="flex-1 min-w-0">
                          <div className={`text-sm font-medium truncate ${isDark ? 'text-white' : 'text-gray-800'}`}>
                            {rule.name}
                            {isFromSet && (
                              <span className="ml-1 text-xs text-blue-400">(规则集)</span>
                            )}
                          </div>
                          <div className={`text-xs ${isDark ? 'text-gray-500' : 'text-gray-400'}`}>{CATEGORY_LABELS[rule.category]}</div>
                        </div>
                      </label>
                    )
                  })}
                </div>
              </Card>
            </div>
          )
        )}
      </div>

      {/* 编辑规则 Modal */}
      <Modal isOpen={showEditModal} onClose={() => setShowEditModal(false)} title={editingRule ? '编辑规则' : '新建规则'} size="xl">
        <div className="space-y-4">
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className={`block text-sm mb-1 ${isDark ? 'text-gray-400' : 'text-gray-600'}`}>名称</label>
              <Input
                value={formData.name}
                onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                placeholder="规则名称"
              />
            </div>
            <div className="grid grid-cols-2 gap-2">
              <div>
                <label className={`block text-sm mb-1 ${isDark ? 'text-gray-400' : 'text-gray-600'}`}>分类</label>
                <select
                  className={`w-full border rounded px-3 py-2 ${isDark ? 'bg-gray-800 border-gray-600 text-white' : 'bg-white border-gray-300 text-gray-800'}`}
                  value={formData.category}
                  onChange={(e) => setFormData({ ...formData, category: e.target.value as WritingRuleCategory })}
                >
                  {Object.entries(CATEGORY_LABELS).map(([key, label]) => (
                    <option key={key} value={key}>{label}</option>
                  ))}
                </select>
              </div>
              <div>
                <label className={`block text-sm mb-1 ${isDark ? 'text-gray-400' : 'text-gray-600'}`}>级别</label>
                <select
                  className={`w-full border rounded px-3 py-2 ${isDark ? 'bg-gray-800 border-gray-600 text-white' : 'bg-white border-gray-300 text-gray-800'}`}
                  value={formData.severity}
                  onChange={(e) => setFormData({ ...formData, severity: e.target.value as RuleSeverity })}
                >
                  {Object.entries(SEVERITY_LABELS).map(([key, { label }]) => (
                    <option key={key} value={key}>{label}</option>
                  ))}
                </select>
              </div>
            </div>
          </div>

          <div>
            <label className={`block text-sm mb-1 ${isDark ? 'text-gray-400' : 'text-gray-600'}`}>描述</label>
            <Input
              value={formData.description}
              onChange={(e) => setFormData({ ...formData, description: e.target.value })}
              placeholder="简要描述规则内容"
            />
          </div>

          <div>
            <label className={`block text-sm mb-1 ${isDark ? 'text-gray-400' : 'text-gray-600'}`}>规则内容</label>
            <TextArea
              value={formData.content}
              onChange={(e) => setFormData({ ...formData, content: e.target.value })}
              placeholder="详细的规则说明..."
              rows={6}
            />
          </div>

          {/* 示例 */}
          <div>
            <label className={`block text-sm mb-1 ${isDark ? 'text-gray-400' : 'text-gray-600'}`}>示例</label>
            <div className="flex gap-2 mb-2">
              <Input
                value={exampleInput}
                onChange={(e) => setExampleInput(e.target.value)}
                placeholder="添加示例"
                className="flex-1"
              />
              <Button variant="secondary" onClick={addExample} className="whitespace-nowrap">添加</Button>
            </div>
            {(formData.examples?.length ?? 0) > 0 && (
              <ul className={`text-sm space-y-1 ${isDark ? 'text-gray-300' : 'text-gray-700'}`}>
                {(formData.examples || []).map((ex, i) => (
                  <li key={i} className="flex items-start gap-2">
                    <span className="text-green-400">•</span>
                    {ex}
                  </li>
                ))}
              </ul>
            )}
          </div>

          {/* 反例 */}
          <div>
            <label className={`block text-sm mb-1 ${isDark ? 'text-gray-400' : 'text-gray-600'}`}>反例</label>
            <div className="flex gap-2 mb-2">
              <Input
                value={antiPatternInput}
                onChange={(e) => setAntiPatternInput(e.target.value)}
                placeholder="添加反例"
                className="flex-1"
              />
              <Button variant="secondary" onClick={addAntiPattern} className="whitespace-nowrap">添加</Button>
            </div>
            {(formData.anti_patterns?.length ?? 0) > 0 && (
              <ul className={`text-sm space-y-1 ${isDark ? 'text-gray-300' : 'text-gray-700'}`}>
                {(formData.anti_patterns || []).map((ap, i) => (
                  <li key={i} className="flex items-start gap-2">
                    <span className="text-red-400">•</span>
                    {ap}
                  </li>
                ))}
              </ul>
            )}
          </div>

          {/* 标签 */}
          <div>
            <label className={`block text-sm mb-1 ${isDark ? 'text-gray-400' : 'text-gray-600'}`}>标签</label>
            <div className="flex gap-2 mb-2">
              <Input
                value={tagInput}
                onChange={(e) => setTagInput(e.target.value)}
                placeholder="添加标签"
                className="flex-1"
              />
              <Button variant="secondary" onClick={addTag} className="whitespace-nowrap">添加</Button>
            </div>
            <div className="flex gap-1 flex-wrap">
              {(formData.tags || []).map((tag) => (
                <span key={tag} className={`px-2 py-1 rounded text-sm ${isDark ? 'bg-gray-700 text-gray-300' : 'bg-gray-200 text-gray-700'}`}>{tag}</span>
              ))}
            </div>
          </div>

          <div className="flex justify-end gap-2 pt-4">
            <Button variant="secondary" onClick={() => setShowEditModal(false)} className="whitespace-nowrap">取消</Button>
            <Button onClick={handleSaveRule} className="whitespace-nowrap">{editingRule ? '保存' : '创建'}</Button>
          </div>
        </div>
      </Modal>

      {/* 预览 Modal */}
      <Modal isOpen={showPreviewModal} onClose={() => setShowPreviewModal(false)} title="写作规则 Prompt 预览" size="xl">
        <pre className={`p-4 rounded text-sm overflow-auto max-h-[500px] whitespace-pre-wrap ${isDark ? 'bg-gray-900' : 'bg-gray-100'}`}>
          {previewContent || '加载中...'}
        </pre>
      </Modal>

      {/* 规则集详情 Modal */}
      <Modal isOpen={!!viewingRuleSet} onClose={() => setViewingRuleSet(null)} title={viewingRuleSet?.name || '规则集详情'} size="xl">
        {viewingRuleSet && (
          <div className="space-y-4">
            <div>
              <h4 className={`font-medium mb-2 ${isDark ? 'text-white' : 'text-gray-800'}`}>描述</h4>
              <p className={`text-sm ${isDark ? 'text-gray-400' : 'text-gray-600'}`}>{viewingRuleSet.description}</p>
            </div>

            {viewingRuleSet.target_genre && (
              <div>
                <h4 className={`font-medium mb-2 ${isDark ? 'text-white' : 'text-gray-800'}`}>目标体裁</h4>
                <p className={`text-sm ${isDark ? 'text-gray-400' : 'text-gray-600'}`}>{viewingRuleSet.target_genre}</p>
              </div>
            )}

            <div>
              <h4 className={`font-medium mb-2 ${isDark ? 'text-white' : 'text-gray-800'}`}>
                包含规则 ({viewingRuleSet.rule_ids.length} 条)
              </h4>
              <div className="space-y-2 max-h-[300px] overflow-auto">
                {viewingRuleSet.rule_ids.map((ruleId) => {
                  const rule = rules.find(r => r.id === ruleId)
                  return rule ? (
                    <div key={ruleId} className={`p-2 rounded ${isDark ? 'bg-gray-800' : 'bg-gray-100'}`}>
                      <div className="flex items-center gap-2">
                        <span className={`font-medium ${isDark ? 'text-white' : 'text-gray-800'}`}>{rule.name}</span>
                        <span className={`px-2 py-0.5 text-xs rounded ${SEVERITY_LABELS[rule.severity].color}`}>
                          {SEVERITY_LABELS[rule.severity].label}
                        </span>
                        <span className={`px-2 py-0.5 text-xs rounded ${isDark ? 'bg-gray-700' : 'bg-gray-200'}`}>
                          {CATEGORY_LABELS[rule.category]}
                        </span>
                      </div>
                      <p className={`text-xs mt-1 ${isDark ? 'text-gray-500' : 'text-gray-400'}`}>
                        {rule.description}
                      </p>
                    </div>
                  ) : (
                    <div key={ruleId} className={`p-2 rounded ${isDark ? 'bg-gray-800 text-gray-500' : 'bg-gray-100 text-gray-400'}`}>
                      {ruleId} (未找到)
                    </div>
                  )
                })}
              </div>
            </div>

            {viewingRuleSet.tags && viewingRuleSet.tags.length > 0 && (
              <div>
                <h4 className={`font-medium mb-2 ${isDark ? 'text-white' : 'text-gray-800'}`}>标签</h4>
                <div className="flex gap-1 flex-wrap">
                  {viewingRuleSet.tags.map((tag) => (
                    <span key={tag} className={`px-2 py-1 rounded text-sm ${isDark ? 'bg-gray-700 text-gray-300' : 'bg-gray-200 text-gray-700'}`}>
                      {tag}
                    </span>
                  ))}
                </div>
              </div>
            )}

            <div className="flex justify-end gap-2 pt-4">
              <Button variant="secondary" onClick={() => setViewingRuleSet(null)}>关闭</Button>
              <Button onClick={() => {
                setViewingRuleSet(null)
                handleEditRuleSet(viewingRuleSet)
              }}>编辑</Button>
            </div>
          </div>
        )}
      </Modal>

      {/* 规则集编辑 Modal */}
      <Modal isOpen={showRuleSetModal} onClose={() => setShowRuleSetModal(false)} title={editingRuleSet ? '编辑规则集' : '新建规则集'} size="xl">
        <div className="space-y-4">
          <div>
            <label className={`block text-sm mb-1 ${isDark ? 'text-gray-400' : 'text-gray-600'}`}>名称</label>
            <Input
              value={ruleSetForm.name}
              onChange={(e) => setRuleSetForm({ ...ruleSetForm, name: e.target.value })}
              placeholder="规则集名称"
            />
          </div>

          <div>
            <label className={`block text-sm mb-1 ${isDark ? 'text-gray-400' : 'text-gray-600'}`}>描述</label>
            <Input
              value={ruleSetForm.description}
              onChange={(e) => setRuleSetForm({ ...ruleSetForm, description: e.target.value })}
              placeholder="规则集描述"
            />
          </div>

          <div>
            <label className={`block text-sm mb-1 ${isDark ? 'text-gray-400' : 'text-gray-600'}`}>目标体裁</label>
            <Input
              value={ruleSetForm.target_genre}
              onChange={(e) => setRuleSetForm({ ...ruleSetForm, target_genre: e.target.value })}
              placeholder="如：玄幻、都市、仙侠等"
            />
          </div>

          <div>
            <label className={`block text-sm mb-1 ${isDark ? 'text-gray-400' : 'text-gray-600'}`}>
              选择规则 ({ruleSetForm.rule_ids.length} 条已选)
            </label>
            <div className={`border rounded p-2 max-h-[300px] overflow-auto ${isDark ? 'border-gray-600' : 'border-gray-300'}`}>
              {rules.length === 0 ? (
                <p className={`text-center py-4 ${isDark ? 'text-gray-500' : 'text-gray-400'}`}>加载规则中...</p>
              ) : (
                <div className="space-y-1">
                  {rules.map((rule) => (
                    <label
                      key={rule.id}
                      className={`flex items-center gap-2 p-2 rounded cursor-pointer transition-colors ${
                        ruleSetForm.rule_ids.includes(rule.id)
                          ? 'bg-blue-900/30'
                          : isDark
                            ? 'hover:bg-gray-700'
                            : 'hover:bg-gray-100'
                      }`}
                    >
                      <input
                        type="checkbox"
                        checked={ruleSetForm.rule_ids.includes(rule.id)}
                        onChange={() => handleToggleRuleInSet(rule.id)}
                        className="w-4 h-4"
                      />
                      <div className="flex-1">
                        <span className={`${isDark ? 'text-white' : 'text-gray-800'}`}>{rule.name}</span>
                        <span className={`ml-2 text-xs ${isDark ? 'text-gray-500' : 'text-gray-400'}`}>
                          {CATEGORY_LABELS[rule.category]}
                        </span>
                      </div>
                    </label>
                  ))}
                </div>
              )}
            </div>
          </div>

          <div className="flex justify-end gap-2 pt-4">
            <Button variant="secondary" onClick={() => setShowRuleSetModal(false)} className="whitespace-nowrap">取消</Button>
            <Button onClick={handleSaveRuleSet} className="whitespace-nowrap">{editingRuleSet ? '保存' : '创建'}</Button>
          </div>
        </div>
      </Modal>
    </div>
  )
}
