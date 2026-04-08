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
  createWritingRuleSet,
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
}

const SEVERITY_LABELS: Record<RuleSeverity, { label: string; color: string }> = {
  required: { label: '必须', color: 'bg-red-900 text-red-300' },
  recommended: { label: '推荐', color: 'bg-yellow-900 text-yellow-300' },
  optional: { label: '可选', color: 'bg-gray-700 text-gray-300' },
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

  const loadData = async () => {
    setLoading(true)
    try {
      if (activeTab === 'rules') {
        const data = await getWritingRules(selectedCategory || undefined, selectedSeverity || undefined)
        setRules(data)
      } else if (activeTab === 'sets') {
        const data = await getWritingRuleSets()
        setRuleSets(data)
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
    ? rules.filter(r =>
        r.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
        r.description.toLowerCase().includes(searchQuery.toLowerCase())
      )
    : rules

  return (
    <div className="h-full flex flex-col">
      {/* 头部 */}
      <div className={`p-4 border-b ${isDark ? 'border-gray-700' : 'border-gray-200'}`}>
        <div className="flex items-center justify-between mb-4">
          <h1 className={`text-2xl font-bold ${isDark ? 'text-white' : 'text-gray-800'}`}>写作规则</h1>
          {activeTab === 'rules' && (
            <Button onClick={handleCreateRule}>
              <Plus className="w-4 h-4 mr-2" />
              新建规则
            </Button>
          )}
          {activeTab === 'sets' && (
            <Button onClick={() => setShowRuleSetModal(true)}>
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
                  <div>
                    <h3 className={`font-semibold text-lg ${isDark ? 'text-white' : 'text-gray-800'}`}>{set.name}</h3>
                    <p className={`text-sm ${isDark ? 'text-gray-400' : 'text-gray-500'}`}>{set.description}</p>
                    <p className={`text-xs mt-1 ${isDark ? 'text-gray-500' : 'text-gray-400'}`}>包含 {set.rule_ids.length} 条规则</p>
                  </div>
                  {set.is_system && (
                    <span className="px-2 py-1 text-xs bg-blue-900 text-blue-300 rounded">系统</span>
                  )}
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
                <h3 className={`font-semibold mb-3 ${isDark ? 'text-white' : 'text-gray-800'}`}>单独启用规则</h3>
                <div className="grid gap-2 md:grid-cols-2 lg:grid-cols-3">
                  {rules.map((rule) => (
                    <label
                      key={rule.id}
                      className={`flex items-center gap-2 p-2 rounded cursor-pointer transition-colors ${
                        projectConfig.enabled_rule_ids.includes(rule.id)
                          ? 'bg-green-900/30 border border-green-500'
                          : isDark
                            ? 'bg-gray-800 hover:bg-gray-700'
                            : 'bg-gray-100 hover:bg-gray-200'
                      }`}
                    >
                      <input
                        type="checkbox"
                        checked={projectConfig.enabled_rule_ids.includes(rule.id)}
                        onChange={() => handleToggleRule(rule.id)}
                        className="w-4 h-4"
                      />
                      <div className="flex-1 min-w-0">
                        <div className={`text-sm font-medium truncate ${isDark ? 'text-white' : 'text-gray-800'}`}>{rule.name}</div>
                        <div className={`text-xs ${isDark ? 'text-gray-500' : 'text-gray-400'}`}>{CATEGORY_LABELS[rule.category]}</div>
                      </div>
                    </label>
                  ))}
                </div>
              </Card>
            </div>
          )
        )}
      </div>

      {/* 编辑规则 Modal */}
      <Modal isOpen={showEditModal} onClose={() => setShowEditModal(false)} title={editingRule ? '编辑规则' : '新建规则'} className="max-w-3xl">
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
              />
              <Button variant="secondary" onClick={addExample}>添加</Button>
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
              />
              <Button variant="secondary" onClick={addAntiPattern}>添加</Button>
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
              />
              <Button variant="secondary" onClick={addTag}>添加</Button>
            </div>
            <div className="flex gap-1 flex-wrap">
              {(formData.tags || []).map((tag) => (
                <span key={tag} className={`px-2 py-1 rounded text-sm ${isDark ? 'bg-gray-700 text-gray-300' : 'bg-gray-200 text-gray-700'}`}>{tag}</span>
              ))}
            </div>
          </div>

          <div className="flex justify-end gap-2 pt-4">
            <Button variant="secondary" onClick={() => setShowEditModal(false)}>取消</Button>
            <Button onClick={handleSaveRule}>{editingRule ? '保存' : '创建'}</Button>
          </div>
        </div>
      </Modal>

      {/* 预览 Modal */}
      <Modal isOpen={showPreviewModal} onClose={() => setShowPreviewModal(false)} title="写作规则 Prompt 预览" className="max-w-4xl">
        <pre className={`p-4 rounded text-sm overflow-auto max-h-[500px] whitespace-pre-wrap ${isDark ? 'bg-gray-900' : 'bg-gray-100'}`}>
          {previewContent || '加载中...'}
        </pre>
      </Modal>
    </div>
  )
}
