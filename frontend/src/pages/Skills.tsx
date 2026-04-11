import { useState, useEffect, useCallback } from 'react'
import { Card, Button, Input, TextArea, Modal } from '@/components/ui'
import PageLayout from '@/components/PageLayout'
import {
  getSkills,
  getSkill,
  createSkill,
  updateSkill,
  deleteSkill,
  testSkill,
  getSkillsStats,
  getAgentTypeSkills,
  initializeDefaultSkills,
  getSkillCategories,
  getSkillTypes,
  type Skill,
  type SkillType,
  type SkillStatus,
  type SkillCategory,
  type CreateSkillDTO,
  type SkillTestResult,
} from '@/api/skills'
import {
  Plus, Edit, Trash2, Search, Play, Code, FileText, Workflow, BookOpen,
  Layers, ChevronDown, ChevronRight, Copy, CheckCircle, XCircle,
  RefreshCw, Sparkles, Users, Filter, Grid, List, AlertCircle,
} from 'lucide-react'
import { useTheme } from '@/contexts/ThemeContext'

const skillTypeIcons: Record<SkillType, React.ReactNode> = {
  prompt: <FileText size={18} />,
  function: <Code size={18} />,
  workflow: <Workflow size={18} />,
  knowledge: <BookOpen size={18} />,
}

const skillTypeLabels: Record<SkillType, string> = {
  prompt: '提示词模板',
  function: 'Python 函数',
  workflow: '工作流',
  knowledge: '知识片段',
}

const skillCategoryLabels: Record<SkillCategory, string> = {
  writing: '写作',
  editing: '编辑',
  style: '风格',
  plotting: '剧情规划',
  pacing: '节奏控制',
  conflict: '冲突设计',
  character: '角色塑造',
  dialogue: '对话生成',
  ooc_check: 'OOC检查',
  foreshadowing: '伏笔管理',
  hook: '钩子/悬念',
  evaluation: '质量评估',
  reader_sim: '读者模拟',
  world_building: '世界观构建',
  setting: '设定管理',
  analysis: '内容分析',
  summary: '内容摘要',
  discussion: '集体讨论',
  performance: '角色演绎',
  general: '通用',
}

const statusLabels: Record<SkillStatus, string> = {
  draft: '草稿',
  active: '激活',
  deprecated: '已废弃',
}

// Agent 类型列表
const AGENT_TYPES = [
  { value: 'master_plotter', label: '总编剧 Agent' },
  { value: 'plotter', label: '编剧 Agent' },
  { value: 'writer', label: '作家 Agent' },
  { value: 'evaluator', label: '评估 Agent' },
  { value: 'character', label: '角色 Agent' },
  { value: 'hook_manager', label: '伏笔 Agent' },
  { value: 'summarizer', label: '摘要 Agent' },
  { value: 'setting', label: '设定 Agent' },
  { value: 'event_generator', label: '事件 Agent' },
  { value: 'world_map_manager', label: '地图 Agent' },
]

type ViewMode = 'all' | 'by_agent'

export default function Skills() {
  const { theme } = useTheme()
  const isDark = theme === 'dark'

  const [skills, setSkills] = useState<Skill[]>([])
  const [loading, setLoading] = useState(true)
  const [selectedSkill, setSelectedSkill] = useState<Skill | null>(null)
  const [showModal, setShowModal] = useState(false)
  const [editingSkill, setEditingSkill] = useState<Skill | null>(null)
  const [searchQuery, setSearchQuery] = useState('')
  const [filterType, setFilterType] = useState<SkillType | ''>('')
  const [filterStatus, setFilterStatus] = useState<SkillStatus | ''>('')
  const [filterCategory, setFilterCategory] = useState<SkillCategory | ''>('')
  const [stats, setStats] = useState<{ total_skills: number; total_usage: number; by_type?: Record<string, number>; by_status?: Record<string, number> } | null>(null)
  const [showTestModal, setShowTestModal] = useState(false)
  const [testParams, setTestParams] = useState('{}')
  const [testResult, setTestResult] = useState<SkillTestResult | null>(null)
  const [testing, setTesting] = useState(false)

  // 视图模式
  const [viewMode, setViewMode] = useState<ViewMode>('all')
  const [selectedAgentType, setSelectedAgentType] = useState<string>('')
  const [agentSkills, setAgentSkills] = useState<Skill[]>([])

  // 表单状态
  const [formData, setFormData] = useState<CreateSkillDTO>({
    name: '',
    description: '',
    skill_type: 'prompt',
    category: 'general',
    prompt_template: '',
    parameters: [],
    tags: [],
    applicable_agent_types: [],
  })
  const [tagsInput, setTagsInput] = useState('')
  const [agentTypesInput, setAgentTypesInput] = useState('')

  const getStatusColors = (status: SkillStatus): string => {
    if (isDark) {
      switch (status) {
        case 'draft': return 'bg-gray-800 text-gray-300 border-gray-600'
        case 'active': return 'bg-green-900 text-green-300 border-green-700'
        case 'deprecated': return 'bg-red-900 text-red-300 border-red-700'
        default: return 'bg-gray-800 text-gray-300 border-gray-600'
      }
    }
    switch (status) {
      case 'draft': return 'bg-gray-100 text-gray-700 border-gray-200'
      case 'active': return 'bg-green-100 text-green-700 border-green-200'
      case 'deprecated': return 'bg-red-100 text-red-700 border-red-200'
      default: return 'bg-gray-100 text-gray-700 border-gray-200'
    }
  }

  const loadSkills = useCallback(async () => {
    setLoading(true)
    try {
      const data = await getSkills(
        filterType || undefined,
        filterStatus || undefined,
        filterCategory || undefined,
        undefined,
        undefined,
        searchQuery || undefined
      )
      setSkills(data)

      // 加载统计
      const statsData = await getSkillsStats()
      setStats(statsData)
    } catch (error) {
      console.error('Failed to load skills:', error)
    } finally {
      setLoading(false)
    }
  }, [filterType, filterStatus, filterCategory, searchQuery])

  const loadAgentSkills = async (agentType: string) => {
    setLoading(true)
    try {
      const skills = await getAgentTypeSkills(agentType)
      setAgentSkills(skills)
    } catch (error) {
      console.error('Failed to load agent skills:', error)
      setAgentSkills([])
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    if (viewMode === 'all') {
      loadSkills()
    } else if (selectedAgentType) {
      loadAgentSkills(selectedAgentType)
    }
  }, [viewMode, selectedAgentType, loadSkills])

  const openCreateModal = () => {
    setEditingSkill(null)
    setFormData({
      name: '',
      description: '',
      skill_type: 'prompt',
      category: 'general',
      prompt_template: '',
      parameters: [],
      tags: [],
      applicable_agent_types: [],
    })
    setTagsInput('')
    setAgentTypesInput('')
    setShowModal(true)
  }

  const openEditModal = (skill: Skill) => {
    setEditingSkill(skill)
    setFormData({
      name: skill.name,
      description: skill.description,
      skill_type: skill.skill_type,
      category: skill.category,
      prompt_template: skill.prompt_template || '',
      function_code: skill.function_code || '',
      workflow_steps: skill.workflow_steps || [],
      knowledge_content: skill.knowledge_content || '',
      parameters: skill.parameters,
      tags: skill.tags,
      applicable_agent_types: skill.applicable_agent_types,
    })
    setTagsInput(skill.tags.join(', '))
    setAgentTypesInput(skill.applicable_agent_types.join(', '))
    setShowModal(true)
  }

  const saveSkill = async () => {
    if (!formData.name) return

    const data = {
      ...formData,
      tags: tagsInput.split(',').map(t => t.trim()).filter(Boolean),
      applicable_agent_types: agentTypesInput.split(',').map(t => t.trim()).filter(Boolean),
    }

    try {
      if (editingSkill) {
        await updateSkill(editingSkill.id, data)
      } else {
        await createSkill(data)
      }
      if (viewMode === 'all') {
        await loadSkills()
      } else if (selectedAgentType) {
        await loadAgentSkills(selectedAgentType)
      }
      setShowModal(false)
    } catch (error) {
      console.error('Failed to save skill:', error)
      alert('保存失败，请重试')
    }
  }

  const handleDelete = async (id: string) => {
    if (!confirm('确定要删除这个 Skill 吗？')) return
    try {
      await deleteSkill(id)
      if (viewMode === 'all') {
        await loadSkills()
      } else if (selectedAgentType) {
        await loadAgentSkills(selectedAgentType)
      }
      if (selectedSkill?.id === id) {
        setSelectedSkill(null)
      }
    } catch (error) {
      console.error('Failed to delete skill:', error)
    }
  }

  const handleTest = async () => {
    if (!selectedSkill) return

    setTesting(true)
    setTestResult(null)

    try {
      let params = {}

      // 处理用户输入
      const trimmedInput = testParams.trim()

      if (trimmedInput && trimmedInput !== '{}') {
        try {
          params = JSON.parse(trimmedInput)
        } catch (parseError: any) {
          // JSON 解析失败，给出友好提示
          setTestResult({
            success: false,
            error: `参数格式错误：请输入有效的 JSON 格式。\n正确格式示例：{"key": "value"}\n错误信息：${parseError.message}`,
          })
          setTesting(false)
          return
        }
      }

      const result = await testSkill(selectedSkill.id, params)
      setTestResult(result)
    } catch (error: any) {
      setTestResult({
        success: false,
        error: error.message || '执行失败',
      })
    } finally {
      setTesting(false)
    }
  }

  const handleInitialize = async () => {
    if (!confirm('确定要初始化默认 Skills 吗？这将创建系统预设的 Skills。')) return
    try {
      const result = await initializeDefaultSkills()
      alert(`初始化完成！创建 ${result.result.skills_created} 个 Skills，跳过 ${result.result.skills_skipped} 个`)
      await loadSkills()
    } catch (error) {
      console.error('Failed to initialize skills:', error)
      alert('初始化失败')
    }
  }

  const copyToClipboard = (text: string) => {
    navigator.clipboard.writeText(text)
  }

  // 当前显示的 Skills
  const displaySkills = viewMode === 'all' ? skills : agentSkills

  return (
    <PageLayout
      title="Agent Skills 管理"
      description={stats ? `共 ${stats.total_skills} 个 Skill，累计使用 ${stats.total_usage} 次` : undefined}
      actions={
        <div className="flex gap-2">
          <Button variant="secondary" onClick={handleInitialize}>
            <RefreshCw size={20} className="mr-2" />
            初始化默认
          </Button>
          <Button onClick={openCreateModal}>
            <Plus size={20} className="mr-2" />
            创建 Skill
          </Button>
        </div>
      }
    >
      {/* 视图切换和筛选 */}
      <div className="mb-6 space-y-4">
        {/* 视图模式切换 */}
        <div className="flex items-center gap-4">
          <div className={`flex rounded-lg p-1 ${isDark ? 'bg-gray-800' : 'bg-gray-100'}`}>
            <button
              onClick={() => setViewMode('all')}
              className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
                viewMode === 'all'
                  ? isDark ? 'bg-blue-600 text-white' : 'bg-white text-blue-600 shadow'
                  : isDark ? 'text-gray-400 hover:text-gray-200' : 'text-gray-600 hover:text-gray-800'
              }`}
            >
              <Grid size={16} />
              全部 Skills
            </button>
            <button
              onClick={() => setViewMode('by_agent')}
              className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
                viewMode === 'by_agent'
                  ? isDark ? 'bg-blue-600 text-white' : 'bg-white text-blue-600 shadow'
                  : isDark ? 'text-gray-400 hover:text-gray-200' : 'text-gray-600 hover:text-gray-800'
              }`}
            >
              <Users size={16} />
              按 Agent 查看
            </button>
          </div>
        </div>

        {/* 筛选条件 */}
        {viewMode === 'all' && (
          <div className="flex flex-wrap gap-4">
            {/* 搜索 */}
            <div className="relative flex-1 min-w-[200px]">
              <Search size={18} className={`absolute left-3 top-1/2 -translate-y-1/2 ${isDark ? 'text-gray-500' : 'text-gray-400'}`} />
              <input
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="搜索 Skill..."
                className={`w-full pl-10 pr-4 py-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 ${isDark ? 'bg-gray-800 border-gray-600 text-white' : 'border-gray-300'}`}
              />
            </div>

            {/* 类型筛选 */}
            <select
              value={filterType}
              onChange={(e) => setFilterType(e.target.value as SkillType | '')}
              className={`px-3 py-2 border rounded-lg ${isDark ? 'bg-gray-800 border-gray-600 text-white' : 'border-gray-300'}`}
            >
              <option value="">全部类型</option>
              {Object.entries(skillTypeLabels).map(([type, label]) => (
                <option key={type} value={type}>{label}</option>
              ))}
            </select>

            {/* 状态筛选 */}
            <select
              value={filterStatus}
              onChange={(e) => setFilterStatus(e.target.value as SkillStatus | '')}
              className={`px-3 py-2 border rounded-lg ${isDark ? 'bg-gray-800 border-gray-600 text-white' : 'border-gray-300'}`}
            >
              <option value="">全部状态</option>
              {Object.entries(statusLabels).map(([status, label]) => (
                <option key={status} value={status}>{label}</option>
              ))}
            </select>
          </div>
        )}

        {/* Agent 类型选择 */}
        {viewMode === 'by_agent' && (
          <div className="flex items-center gap-4">
            <span className={`text-sm ${isDark ? 'text-gray-400' : 'text-gray-500'}`}>选择 Agent 类型：</span>
            <select
              value={selectedAgentType}
              onChange={(e) => setSelectedAgentType(e.target.value)}
              className={`flex-1 max-w-xs px-3 py-2 border rounded-lg ${isDark ? 'bg-gray-800 border-gray-600 text-white' : 'border-gray-300'}`}
            >
              <option value="">请选择...</option>
              {AGENT_TYPES.map((agent) => (
                <option key={agent.value} value={agent.value}>{agent.label}</option>
              ))}
            </select>
          </div>
        )}
      </div>

      {loading ? (
        <div className="flex items-center justify-center py-20">
          <Layers size={24} className="animate-spin mr-3" />
          <span className={isDark ? 'text-gray-400' : 'text-gray-500'}>加载 Skills...</span>
        </div>
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* 左侧：Skill 列表 */}
          <div className="lg:col-span-2">
            {(!displaySkills || displaySkills.length === 0) ? (
              <Card className="p-12 text-center">
                <AlertCircle size={48} className={`mx-auto mb-4 ${isDark ? 'text-gray-600' : 'text-gray-300'}`} />
                <p className={`text-lg mb-2 ${isDark ? 'text-gray-400' : 'text-gray-500'}`}>
                  {viewMode === 'by_agent' && !selectedAgentType ? '请选择 Agent 类型查看 Skills' : '暂无 Skill'}
                </p>
                {viewMode === 'all' && (
                  <Button variant="secondary" onClick={handleInitialize} className="mt-4">
                    初始化默认 Skills
                  </Button>
                )}
              </Card>
            ) : (
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {displaySkills.map(skill => (
                  <Card
                    key={skill.id}
                    className={`p-4 cursor-pointer transition-all hover:shadow-lg ${
                      selectedSkill?.id === skill.id
                        ? isDark ? 'ring-2 ring-blue-500' : 'ring-2 ring-blue-400'
                        : ''
                    }`}
                    onClick={() => setSelectedSkill(skill)}
                  >
                    <div className="flex items-start justify-between mb-3">
                      <div className="flex items-center gap-3">
                        <div className={`p-2 rounded-lg ${isDark ? 'bg-gray-800' : 'bg-gray-100'}`}>
                          {skillTypeIcons[skill.skill_type]}
                        </div>
                        <div>
                          <h3 className={`font-semibold ${isDark ? 'text-white' : 'text-gray-800'}`}>
                            {skill.name}
                          </h3>
                          <div className="flex items-center gap-2 mt-1">
                            <span className={`text-xs px-2 py-0.5 rounded border ${getStatusColors(skill.status)}`}>
                              {statusLabels[skill.status]}
                            </span>
                            <span className={`text-xs ${isDark ? 'text-gray-500' : 'text-gray-400'}`}>
                              {skillCategoryLabels[skill.category] || skill.category}
                            </span>
                          </div>
                        </div>
                      </div>
                      {skill.is_system && (
                        <span className={`text-xs px-2 py-1 rounded ${isDark ? 'bg-purple-900 text-purple-300' : 'bg-purple-100 text-purple-700'}`}>
                          系统
                        </span>
                      )}
                    </div>

                    <p className={`text-sm line-clamp-2 ${isDark ? 'text-gray-400' : 'text-gray-500'}`}>
                      {skill.description}
                    </p>

                    <div className="flex items-center justify-between mt-3 pt-3 border-t border-dashed">
                      <div className="flex items-center gap-2">
                        {skill.applicable_agent_types.length === 0 ? (
                          <span className={`text-xs ${isDark ? 'text-gray-500' : 'text-gray-400'}`}>
                            全局通用
                          </span>
                        ) : (
                          <span className={`text-xs ${isDark ? 'text-gray-500' : 'text-gray-400'}`}>
                            {skill.applicable_agent_types.length} 个 Agent
                          </span>
                        )}
                      </div>
                      <div className="flex items-center gap-1 text-xs">
                        <span className={isDark ? 'text-gray-500' : 'text-gray-400'}>
                          优先级 {skill.priority}
                        </span>
                        <span className={isDark ? 'text-gray-600' : 'text-gray-300'}>|</span>
                        <span className={isDark ? 'text-gray-500' : 'text-gray-400'}>
                          使用 {skill.usage_count} 次
                        </span>
                      </div>
                    </div>
                  </Card>
                ))}
              </div>
            )}
          </div>

          {/* 右侧：Skill 详情 */}
          <div className="lg:col-span-1">
            {!selectedSkill ? (
              <Card className="p-8 text-center sticky top-4">
                <Layers size={48} className={`mx-auto mb-4 opacity-50 ${isDark ? 'text-gray-600' : 'text-gray-300'}`} />
                <p className={isDark ? 'text-gray-400' : 'text-gray-500'}>选择 Skill 查看详情</p>
              </Card>
            ) : (
              <Card className="sticky top-4">
                {/* 头部 */}
                <div className={`p-4 border-b ${isDark ? 'border-gray-700' : 'border-gray-200'}`}>
                  <div className="flex items-center gap-3 mb-2">
                    <div className={`p-2 rounded-lg ${isDark ? 'bg-gray-800' : 'bg-gray-100'}`}>
                      {skillTypeIcons[selectedSkill.skill_type]}
                    </div>
                    <div className="flex-1">
                      <h2 className={`font-bold text-lg ${isDark ? 'text-white' : 'text-gray-800'}`}>
                        {selectedSkill.name}
                      </h2>
                      <div className="flex items-center gap-2">
                        <span className={`text-xs px-2 py-0.5 rounded border ${getStatusColors(selectedSkill.status)}`}>
                          {statusLabels[selectedSkill.status]}
                        </span>
                        <span className={`text-xs ${isDark ? 'text-gray-500' : 'text-gray-400'}`}>
                          {skillTypeLabels[selectedSkill.skill_type]}
                        </span>
                      </div>
                    </div>
                  </div>
                  <p className={`text-sm ${isDark ? 'text-gray-400' : 'text-gray-600'}`}>
                    {selectedSkill.description}
                  </p>
                </div>

                {/* 操作按钮 */}
                <div className={`p-4 border-b flex gap-2 ${isDark ? 'border-gray-700' : 'border-gray-200'}`}>
                  <Button size="sm" variant="secondary" onClick={() => setShowTestModal(true)}>
                    <Play size={14} className="mr-1" /> 测试
                  </Button>
                  <Button size="sm" variant="secondary" onClick={() => openEditModal(selectedSkill)}>
                    <Edit size={14} className="mr-1" /> 编辑
                  </Button>
                  {!selectedSkill.is_system && (
                    <Button size="sm" variant="danger" onClick={() => handleDelete(selectedSkill.id)}>
                      <Trash2 size={14} className="mr-1" /> 删除
                    </Button>
                  )}
                </div>

                {/* 内容详情 */}
                <div className="p-4 space-y-4 max-h-[400px] overflow-y-auto">
                  {/* 适用 Agent */}
                  <div>
                    <h4 className={`text-sm font-medium mb-2 ${isDark ? 'text-gray-300' : 'text-gray-700'}`}>
                      适用 Agent
                    </h4>
                    {selectedSkill.applicable_agent_types.length === 0 ? (
                      <span className={`text-sm ${isDark ? 'text-gray-500' : 'text-gray-400'}`}>
                        全局通用（所有 Agent 都可用）
                      </span>
                    ) : (
                      <div className="flex flex-wrap gap-1">
                        {selectedSkill.applicable_agent_types.map((agent) => (
                          <span
                            key={agent}
                            className={`text-xs px-2 py-1 rounded ${isDark ? 'bg-gray-800 text-gray-300' : 'bg-gray-100 text-gray-600'}`}
                          >
                            {AGENT_TYPES.find(a => a.value === agent)?.label || agent}
                          </span>
                        ))}
                      </div>
                    )}
                  </div>

                  {/* Prompt 模板 */}
                  {selectedSkill.prompt_template && (
                    <div>
                      <div className="flex items-center justify-between mb-2">
                        <h4 className={`text-sm font-medium ${isDark ? 'text-gray-300' : 'text-gray-700'}`}>
                          提示词模板
                        </h4>
                        <button
                          onClick={() => copyToClipboard(selectedSkill.prompt_template!)}
                          className={`text-xs hover:underline ${isDark ? 'text-blue-400' : 'text-blue-600'}`}
                        >
                          <Copy size={12} className="inline mr-1" /> 复制
                        </button>
                      </div>
                      <pre className={`p-3 rounded-lg text-xs overflow-x-auto whitespace-pre-wrap max-h-48 ${isDark ? 'bg-gray-800' : 'bg-gray-50'}`}>
                        {selectedSkill.prompt_template}
                      </pre>
                    </div>
                  )}

                  {/* Knowledge 内容 */}
                  {selectedSkill.knowledge_content && (
                    <div>
                      <h4 className={`text-sm font-medium mb-2 ${isDark ? 'text-gray-300' : 'text-gray-700'}`}>
                        知识内容
                      </h4>
                      <div className={`p-3 rounded-lg text-xs whitespace-pre-wrap max-h-48 overflow-y-auto ${isDark ? 'bg-gray-800' : 'bg-gray-50'}`}>
                        {selectedSkill.knowledge_content}
                      </div>
                    </div>
                  )}

                  {/* 参数定义 */}
                  {selectedSkill.parameters.length > 0 && (
                    <div>
                      <h4 className={`text-sm font-medium mb-2 ${isDark ? 'text-gray-300' : 'text-gray-700'}`}>
                        参数定义
                      </h4>
                      <div className="space-y-2">
                        {selectedSkill.parameters.map((param, idx) => (
                          <div key={idx} className={`p-2 rounded-lg text-xs ${isDark ? 'bg-gray-800' : 'bg-gray-50'}`}>
                            <div className="flex items-center gap-2">
                              <span className={`font-medium ${isDark ? 'text-gray-200' : 'text-gray-700'}`}>
                                {param.name}
                              </span>
                              <span className={isDark ? 'text-gray-500' : 'text-gray-400'}>({param.type})</span>
                              {param.required && <span className="text-red-500 text-[10px]">*必填</span>}
                            </div>
                            {param.description && (
                              <p className={`mt-1 ${isDark ? 'text-gray-400' : 'text-gray-500'}`}>
                                {param.description}
                              </p>
                            )}
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* 标签 */}
                  {selectedSkill.tags.length > 0 && (
                    <div>
                      <h4 className={`text-sm font-medium mb-2 ${isDark ? 'text-gray-300' : 'text-gray-700'}`}>
                        标签
                      </h4>
                      <div className="flex flex-wrap gap-1">
                        {selectedSkill.tags.map((tag, i) => (
                          <span
                            key={i}
                            className={`text-xs px-2 py-1 rounded ${isDark ? 'bg-gray-800 text-gray-300' : 'bg-gray-100 text-gray-600'}`}
                          >
                            {tag}
                          </span>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* 元信息 */}
                  <div className="grid grid-cols-2 gap-2 text-xs pt-2 border-t border-dashed">
                    <div>
                      <span className={isDark ? 'text-gray-500' : 'text-gray-400'}>优先级:</span>
                      <span className={`ml-1 ${isDark ? 'text-gray-300' : 'text-gray-600'}`}>{selectedSkill.priority}</span>
                    </div>
                    <div>
                      <span className={isDark ? 'text-gray-500' : 'text-gray-400'}>版本:</span>
                      <span className={`ml-1 ${isDark ? 'text-gray-300' : 'text-gray-600'}`}>{selectedSkill.version}</span>
                    </div>
                    <div>
                      <span className={isDark ? 'text-gray-500' : 'text-gray-400'}>使用次数:</span>
                      <span className={`ml-1 ${isDark ? 'text-gray-300' : 'text-gray-600'}`}>{selectedSkill.usage_count}</span>
                    </div>
                    <div>
                      <span className={isDark ? 'text-gray-500' : 'text-gray-400'}>作者:</span>
                      <span className={`ml-1 ${isDark ? 'text-gray-300' : 'text-gray-600'}`}>{selectedSkill.author}</span>
                    </div>
                  </div>
                </div>
              </Card>
            )}
          </div>
        </div>
      )}

      {/* 创建/编辑模态框 */}
      <Modal
        isOpen={showModal}
        onClose={() => setShowModal(false)}
        title={editingSkill ? '编辑 Skill' : '创建 Skill'}
        size="lg"
      >
        <div className="space-y-4">
          <div className="grid grid-cols-2 gap-4">
            <Input
              label="名称 *"
              value={formData.name}
              onChange={(e) => setFormData({ ...formData, name: e.target.value })}
              placeholder="Skill 名称"
            />
            <div>
              <label className={`block text-sm font-medium mb-1 ${isDark ? 'text-gray-300' : 'text-gray-700'}`}>
                类型
              </label>
              <select
                className={`w-full px-3 py-2 border rounded-lg ${isDark ? 'bg-gray-800 border-gray-600 text-white' : 'border-gray-300'}`}
                value={formData.skill_type}
                onChange={(e) => setFormData({ ...formData, skill_type: e.target.value as SkillType })}
              >
                {Object.entries(skillTypeLabels).map(([type, label]) => (
                  <option key={type} value={type}>{label}</option>
                ))}
              </select>
            </div>
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className={`block text-sm font-medium mb-1 ${isDark ? 'text-gray-300' : 'text-gray-700'}`}>
                类别
              </label>
              <select
                className={`w-full px-3 py-2 border rounded-lg ${isDark ? 'bg-gray-800 border-gray-600 text-white' : 'border-gray-300'}`}
                value={formData.category}
                onChange={(e) => setFormData({ ...formData, category: e.target.value as SkillCategory })}
              >
                {Object.entries(skillCategoryLabels).map(([cat, label]) => (
                  <option key={cat} value={cat}>{label}</option>
                ))}
              </select>
            </div>
            <div>
              <label className={`block text-sm font-medium mb-1 ${isDark ? 'text-gray-300' : 'text-gray-700'}`}>
                优先级
              </label>
              <input
                type="number"
                className={`w-full px-3 py-2 border rounded-lg ${isDark ? 'bg-gray-800 border-gray-600 text-white' : 'border-gray-300'}`}
                value={formData.priority || 50}
                onChange={(e) => setFormData({ ...formData, priority: parseInt(e.target.value) || 50 })}
                min={1}
                max={100}
              />
            </div>
          </div>

          <TextArea
            label="描述"
            value={formData.description}
            onChange={(e) => setFormData({ ...formData, description: e.target.value })}
            placeholder="描述这个 Skill 的用途..."
            rows={2}
          />

          {formData.skill_type === 'prompt' && (
            <TextArea
              label="提示词模板"
              value={formData.prompt_template || ''}
              onChange={(e) => setFormData({ ...formData, prompt_template: e.target.value })}
              placeholder="使用 {param_name} 作为参数占位符..."
              rows={8}
            />
          )}

          {formData.skill_type === 'function' && (
            <TextArea
              label="Python 代码"
              value={formData.function_code || ''}
              onChange={(e) => setFormData({ ...formData, function_code: e.target.value })}
              placeholder="def execute(**params): ..."
              rows={8}
            />
          )}

          {formData.skill_type === 'knowledge' && (
            <TextArea
              label="知识内容"
              value={formData.knowledge_content || ''}
              onChange={(e) => setFormData({ ...formData, knowledge_content: e.target.value })}
              placeholder="知识内容..."
              rows={8}
            />
          )}

          <Input
            label="适用 Agent 类型（留空表示全局通用）"
            value={agentTypesInput}
            onChange={(e) => setAgentTypesInput(e.target.value)}
            placeholder="用逗号分隔，如：writer, evaluator, character"
          />
          <p className={`text-xs -mt-2 ${isDark ? 'text-gray-500' : 'text-gray-400'}`}>
            可选值: {AGENT_TYPES.map(a => a.value).join(', ')}
          </p>

          <Input
            label="标签"
            value={tagsInput}
            onChange={(e) => setTagsInput(e.target.value)}
            placeholder="用逗号分隔，如：对话, 情感, 描写"
          />

          <div className="flex justify-end gap-3 pt-4">
            <Button variant="secondary" onClick={() => setShowModal(false)}>取消</Button>
            <Button onClick={saveSkill} disabled={!formData.name}>
              {editingSkill ? '保存修改' : '创建'}
            </Button>
          </div>
        </div>
      </Modal>

      {/* 测试模态框 */}
      <Modal
        isOpen={showTestModal}
        onClose={() => {
          setShowTestModal(false)
          setTestResult(null)
          setTestParams('{}')
        }}
        title={`测试 Skill: ${selectedSkill?.name}`}
        size="lg"
      >
        <div className="space-y-4">
          {/* 显示 Skill 参数说明 */}
          {selectedSkill && selectedSkill.parameters && selectedSkill.parameters.length > 0 && (
            <div className={`p-3 rounded-lg ${isDark ? 'bg-gray-800' : 'bg-gray-50'}`}>
              <h4 className={`text-sm font-medium mb-2 ${isDark ? 'text-gray-300' : 'text-gray-700'}`}>
                参数说明
              </h4>
              <div className="space-y-1">
                {selectedSkill.parameters.map((param, index) => (
                  <div key={index} className="text-sm">
                    <span className={`font-mono ${isDark ? 'text-blue-400' : 'text-blue-600'}`}>
                      {param.name}
                    </span>
                    <span className={`mx-1 ${isDark ? 'text-gray-500' : 'text-gray-400'}`}>:</span>
                    <span className={isDark ? 'text-gray-400' : 'text-gray-600'}>
                      {param.description || param.type || '无描述'}
                    </span>
                    {param.default !== undefined && (
                      <span className={`ml-1 ${isDark ? 'text-gray-500' : 'text-gray-400'}`}>
                        (默认: {JSON.stringify(param.default)})
                      </span>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* 无参数提示 */}
          {selectedSkill && (!selectedSkill.parameters || selectedSkill.parameters.length === 0) && (
            <div className={`p-3 rounded-lg ${isDark ? 'bg-blue-900/30' : 'bg-blue-50'}`}>
              <p className={`text-sm ${isDark ? 'text-blue-300' : 'text-blue-700'}`}>
                该 Skill 无需参数，可直接点击「执行测试」按钮
              </p>
            </div>
          )}

          <TextArea
            label="输入参数 (JSON 格式)"
            value={testParams}
            onChange={(e) => setTestParams(e.target.value)}
            placeholder='{"param1": "value1", "param2": "value2"}'
            rows={4}
          />

          <div className="flex gap-2">
            <Button onClick={handleTest} disabled={testing}>
              {testing ? '执行中...' : '执行测试'}
            </Button>
            <Button
              variant="secondary"
              onClick={() => setTestParams('{}')}
            >
              重置参数
            </Button>
          </div>

          {testResult && (
            <div className={`p-4 rounded-lg ${testResult.success ? (isDark ? 'bg-green-900/30' : 'bg-green-50') : (isDark ? 'bg-red-900/30' : 'bg-red-50')}`}>
              <div className="flex items-center gap-2 mb-2">
                {testResult.success ? (
                  <CheckCircle size={18} className="text-green-600" />
                ) : (
                  <XCircle size={18} className="text-red-600" />
                )}
                <span className={`font-medium ${testResult.success ? (isDark ? 'text-green-400' : 'text-green-700') : (isDark ? 'text-red-400' : 'text-red-700')}`}>
                  {testResult.success ? '执行成功' : '执行失败'}
                </span>
                {testResult.execution_time_ms && (
                  <span className={`text-xs ${isDark ? 'text-gray-400' : 'text-gray-500'}`}>
                    ({testResult.execution_time_ms}ms)
                  </span>
                )}
              </div>

              {testResult.output && (
                <pre className={`p-3 rounded text-sm overflow-x-auto whitespace-pre-wrap ${isDark ? 'bg-gray-800' : 'bg-white'}`}>
                  {testResult.output}
                </pre>
              )}

              {testResult.error && (
                <p className="text-red-600 text-sm">{testResult.error}</p>
              )}
            </div>
          )}
        </div>
      </Modal>
    </PageLayout>
  )
}
