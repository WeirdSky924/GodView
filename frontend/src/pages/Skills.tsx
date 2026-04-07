import { useState, useEffect, useCallback } from 'react'
import { Card, Button, Input, TextArea, Modal } from '@/components/ui'
import {
  getSkills,
  getSkill,
  createSkill,
  updateSkill,
  deleteSkill,
  testSkill,
  getSkillsStats,
  type Skill,
  type SkillType,
  type SkillStatus,
  type CreateSkillDTO,
  type SkillTestResult,
} from '@/api/skills'
import {
  Plus, Edit, Trash2, Search, Play, Code, FileText, Workflow, BookOpen,
  Layers, ChevronDown, ChevronRight, Copy, CheckCircle, XCircle,
} from 'lucide-react'

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

const statusColors: Record<SkillStatus, string> = {
  draft: 'bg-gray-100 text-gray-700 border-gray-200',
  active: 'bg-green-100 text-green-700 border-green-200',
  deprecated: 'bg-red-100 text-red-700 border-red-200',
}

const statusLabels: Record<SkillStatus, string> = {
  draft: '草稿',
  active: '激活',
  deprecated: '已废弃',
}

export default function Skills() {
  const [skills, setSkills] = useState<Skill[]>([])
  const [loading, setLoading] = useState(true)
  const [selectedSkill, setSelectedSkill] = useState<Skill | null>(null)
  const [showModal, setShowModal] = useState(false)
  const [editingSkill, setEditingSkill] = useState<Skill | null>(null)
  const [searchQuery, setSearchQuery] = useState('')
  const [filterType, setFilterType] = useState<SkillType | ''>('')
  const [filterStatus, setFilterStatus] = useState<SkillStatus | ''>('')
  const [stats, setStats] = useState<{ total_skills: number; total_usage: number } | null>(null)
  const [showTestModal, setShowTestModal] = useState(false)
  const [testParams, setTestParams] = useState('{}')
  const [testResult, setTestResult] = useState<SkillTestResult | null>(null)
  const [testing, setTesting] = useState(false)

  const [formData, setFormData] = useState<CreateSkillDTO>({
    name: '',
    description: '',
    skill_type: 'prompt',
    prompt_template: '',
    parameters: [],
    tags: [],
  })
  const [tagsInput, setTagsInput] = useState('')

  const loadSkills = useCallback(async () => {
    setLoading(true)
    try {
      const data = await getSkills(
        filterType || undefined,
        filterStatus || undefined,
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
  }, [filterType, filterStatus, searchQuery])

  useEffect(() => {
    loadSkills()
  }, [loadSkills])

  const openCreateModal = () => {
    setEditingSkill(null)
    setFormData({
      name: '',
      description: '',
      skill_type: 'prompt',
      prompt_template: '',
      parameters: [],
      tags: [],
    })
    setTagsInput('')
    setShowModal(true)
  }

  const openEditModal = (skill: Skill) => {
    setEditingSkill(skill)
    setFormData({
      name: skill.name,
      description: skill.description,
      skill_type: skill.skill_type,
      prompt_template: skill.prompt_template || '',
      function_code: skill.function_code || '',
      workflow_steps: skill.workflow_steps || [],
      knowledge_content: skill.knowledge_content || '',
      parameters: skill.parameters,
      tags: skill.tags,
    })
    setTagsInput(skill.tags.join(', '))
    setShowModal(true)
  }

  const saveSkill = async () => {
    if (!formData.name) return

    const data = {
      ...formData,
      tags: tagsInput.split(',').map(t => t.trim()).filter(Boolean),
    }

    try {
      if (editingSkill) {
        await updateSkill(editingSkill.id, data)
      } else {
        await createSkill(data)
      }
      await loadSkills()
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
      await loadSkills()
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
      if (testParams.trim()) {
        params = JSON.parse(testParams)
      }

      const result = await testSkill(selectedSkill.id, params)
      setTestResult(result)
    } catch (error: any) {
      setTestResult({
        success: false,
        error: error.message || '解析参数失败',
      })
    } finally {
      setTesting(false)
    }
  }

  const copyToClipboard = (text: string) => {
    navigator.clipboard.writeText(text)
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-3xl font-bold text-gray-800">🧩 Agent Skills</h1>
          {stats && (
            <p className="text-gray-500 mt-1">
              共 {stats.total_skills} 个 Skill，累计使用 {stats.total_usage} 次
            </p>
          )}
        </div>
        <Button onClick={openCreateModal}>
          <Plus size={20} className="mr-2" />
          创建 Skill
        </Button>
      </div>

      {loading ? (
        <div className="flex items-center justify-center py-20">
          <Layers size={24} className="animate-spin mr-3" />
          <span className="text-gray-500">加载 Skills...</span>
        </div>
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
          {/* 左侧：筛选器和列表 */}
          <div className="lg:col-span-1 space-y-4">
            {/* 搜索 */}
            <Card className="p-4">
              <div className="relative">
                <Search size={18} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
                <input
                  type="text"
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  placeholder="搜索 Skill..."
                  className="w-full pl-10 pr-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              </div>
            </Card>

            {/* 类型筛选 */}
            <Card className="p-4">
              <h3 className="font-medium text-gray-800 mb-3">类型</h3>
              <div className="space-y-2">
                <button
                  onClick={() => setFilterType('')}
                  className={`w-full text-left px-3 py-2 rounded-lg text-sm ${
                    filterType === '' ? 'bg-blue-50 text-blue-700' : 'hover:bg-gray-50'
                  }`}
                >
                  全部
                </button>
                {Object.entries(skillTypeLabels).map(([type, label]) => (
                  <button
                    key={type}
                    onClick={() => setFilterType(type as SkillType)}
                    className={`w-full text-left px-3 py-2 rounded-lg text-sm flex items-center gap-2 ${
                      filterType === type ? 'bg-blue-50 text-blue-700' : 'hover:bg-gray-50'
                    }`}
                  >
                    {skillTypeIcons[type as SkillType]}
                    {label}
                  </button>
                ))}
              </div>
            </Card>

            {/* 状态筛选 */}
            <Card className="p-4">
              <h3 className="font-medium text-gray-800 mb-3">状态</h3>
              <div className="space-y-2">
                <button
                  onClick={() => setFilterStatus('')}
                  className={`w-full text-left px-3 py-2 rounded-lg text-sm ${
                    filterStatus === '' ? 'bg-blue-50 text-blue-700' : 'hover:bg-gray-50'
                  }`}
                >
                  全部
                </button>
                {Object.entries(statusLabels).map(([status, label]) => (
                  <button
                    key={status}
                    onClick={() => setFilterStatus(status as SkillStatus)}
                    className={`w-full text-left px-3 py-2 rounded-lg text-sm ${
                      filterStatus === status ? 'bg-blue-50 text-blue-700' : 'hover:bg-gray-50'
                    }`}
                  >
                    {label}
                  </button>
                ))}
              </div>
            </Card>
          </div>

          {/* 中间：Skill 列表 */}
          <div className="lg:col-span-1">
            <Card className="h-[calc(100vh-200px)] overflow-y-auto">
              <div className="p-4 border-b sticky top-0 bg-white">
                <h3 className="font-medium text-gray-800">
                  Skill 列表 ({skills.length})
                </h3>
              </div>
              <div className="divide-y">
                {skills.length === 0 ? (
                  <div className="p-8 text-center text-gray-500">暂无 Skill</div>
                ) : (
                  skills.map(skill => (
                    <div
                      key={skill.id}
                      onClick={() => setSelectedSkill(skill)}
                      className={`p-4 cursor-pointer transition-colors ${
                        selectedSkill?.id === skill.id ? 'bg-blue-50' : 'hover:bg-gray-50'
                      }`}
                    >
                      <div className="flex items-start gap-3">
                        <div className="mt-1 text-gray-500">
                          {skillTypeIcons[skill.skill_type]}
                        </div>
                        <div className="flex-1 min-w-0">
                          <h4 className="font-medium text-gray-800 truncate">{skill.name}</h4>
                          <p className="text-sm text-gray-500 mt-1 line-clamp-2">
                            {skill.description}
                          </p>
                          <div className="flex items-center gap-2 mt-2">
                            <span className={`text-xs px-2 py-0.5 rounded border ${statusColors[skill.status]}`}>
                              {statusLabels[skill.status]}
                            </span>
                            <span className="text-xs text-gray-400">
                              使用 {skill.usage_count} 次
                            </span>
                          </div>
                        </div>
                      </div>
                    </div>
                  ))
                )}
              </div>
            </Card>
          </div>

          {/* 右侧：Skill 详情 */}
          <div className="lg:col-span-2">
            {!selectedSkill ? (
              <Card className="h-[calc(100vh-200px)] flex items-center justify-center text-gray-500">
                <div className="text-center">
                  <Layers size={48} className="mx-auto mb-4 opacity-50" />
                  <p>选择一个 Skill 查看详情</p>
                </div>
              </Card>
            ) : (
              <Card className="h-[calc(100vh-200px)] overflow-y-auto">
                <div className="p-6">
                  {/* 头部 */}
                  <div className="flex items-start justify-between mb-6">
                    <div>
                      <div className="flex items-center gap-3 mb-2">
                        {skillTypeIcons[selectedSkill.skill_type]}
                        <span className={`text-xs px-2 py-0.5 rounded border ${statusColors[selectedSkill.status]}`}>
                          {statusLabels[selectedSkill.status]}
                        </span>
                      </div>
                      <h2 className="text-2xl font-bold text-gray-800">{selectedSkill.name}</h2>
                      <p className="text-gray-600 mt-2">{selectedSkill.description}</p>
                    </div>
                    <div className="flex gap-2">
                      <Button variant="secondary" size="sm" onClick={() => setShowTestModal(true)}>
                        <Play size={16} className="mr-1" /> 测试
                      </Button>
                      <Button variant="secondary" size="sm" onClick={() => openEditModal(selectedSkill)}>
                        <Edit size={16} className="mr-1" /> 编辑
                      </Button>
                      <Button variant="danger" size="sm" onClick={() => handleDelete(selectedSkill.id)}>
                        <Trash2 size={16} className="mr-1" /> 删除
                      </Button>
                    </div>
                  </div>

                  {/* 内容 */}
                  <div className="space-y-6">
                    {/* Prompt 模板 */}
                    {selectedSkill.prompt_template && (
                      <div>
                        <div className="flex items-center justify-between mb-2">
                          <h3 className="font-medium text-gray-800">提示词模板</h3>
                          <button
                            onClick={() => copyToClipboard(selectedSkill.prompt_template!)}
                            className="text-sm text-blue-600 hover:text-blue-700"
                          >
                            <Copy size={14} className="inline mr-1" /> 复制
                          </button>
                        </div>
                        <pre className="bg-gray-50 p-4 rounded-lg text-sm overflow-x-auto whitespace-pre-wrap">
                          {selectedSkill.prompt_template}
                        </pre>
                      </div>
                    )}

                    {/* Function 代码 */}
                    {selectedSkill.function_code && (
                      <div>
                        <div className="flex items-center justify-between mb-2">
                          <h3 className="font-medium text-gray-800">Python 代码</h3>
                          <button
                            onClick={() => copyToClipboard(selectedSkill.function_code!)}
                            className="text-sm text-blue-600 hover:text-blue-700"
                          >
                            <Copy size={14} className="inline mr-1" /> 复制
                          </button>
                        </div>
                        <pre className="bg-gray-900 text-green-400 p-4 rounded-lg text-sm overflow-x-auto">
                          {selectedSkill.function_code}
                        </pre>
                      </div>
                    )}

                    {/* Workflow 步骤 */}
                    {selectedSkill.workflow_steps && selectedSkill.workflow_steps.length > 0 && (
                      <div>
                        <h3 className="font-medium text-gray-800 mb-2">工作流步骤</h3>
                        <div className="space-y-2">
                          {selectedSkill.workflow_steps.map((step, idx) => (
                            <div key={idx} className="bg-gray-50 p-3 rounded-lg">
                              <span className="font-medium text-gray-700">{step.name || `步骤 ${idx + 1}`}</span>
                              <p className="text-sm text-gray-600 mt-1">{step.action}</p>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}

                    {/* Knowledge 内容 */}
                    {selectedSkill.knowledge_content && (
                      <div>
                        <h3 className="font-medium text-gray-800 mb-2">知识内容</h3>
                        <div className="bg-gray-50 p-4 rounded-lg text-sm whitespace-pre-wrap">
                          {selectedSkill.knowledge_content}
                        </div>
                      </div>
                    )}

                    {/* 参数 */}
                    {selectedSkill.parameters.length > 0 && (
                      <div>
                        <h3 className="font-medium text-gray-800 mb-2">参数定义</h3>
                        <div className="space-y-2">
                          {selectedSkill.parameters.map((param, idx) => (
                            <div key={idx} className="bg-gray-50 p-3 rounded-lg">
                              <div className="flex items-center gap-2">
                                <span className="font-medium text-gray-700">{param.name}</span>
                                <span className="text-xs text-gray-500">({param.type})</span>
                                {param.required && (
                                  <span className="text-xs text-red-600">*必填</span>
                                )}
                              </div>
                              <p className="text-sm text-gray-600 mt-1">{param.description}</p>
                              {param.default !== undefined && (
                                <p className="text-xs text-gray-500 mt-1">默认值: {JSON.stringify(param.default)}</p>
                              )}
                            </div>
                          ))}
                        </div>
                      </div>
                    )}

                    {/* 标签 */}
                    {selectedSkill.tags.length > 0 && (
                      <div>
                        <h3 className="font-medium text-gray-800 mb-2">标签</h3>
                        <div className="flex flex-wrap gap-2">
                          {selectedSkill.tags.map((tag, i) => (
                            <span key={i} className="px-3 py-1 bg-gray-100 rounded-full text-sm text-gray-700">
                              {tag}
                            </span>
                          ))}
                        </div>
                      </div>
                    )}

                    {/* 元信息 */}
                    <div className="grid grid-cols-2 gap-4 text-sm">
                      <div className="p-4 bg-gray-50 rounded-lg">
                        <div className="text-gray-500 mb-1">版本</div>
                        <div className="font-medium">{selectedSkill.version}</div>
                      </div>
                      <div className="p-4 bg-gray-50 rounded-lg">
                        <div className="text-gray-500 mb-1">使用次数</div>
                        <div className="font-medium">{selectedSkill.usage_count}</div>
                      </div>
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
          <Input
            label="名称 *"
            value={formData.name}
            onChange={(e) => setFormData({ ...formData, name: e.target.value })}
            placeholder="Skill 名称"
          />

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">类型</label>
              <select
                className="w-full px-3 py-2 border border-gray-300 rounded-lg"
                value={formData.skill_type}
                onChange={(e) => setFormData({ ...formData, skill_type: e.target.value as SkillType })}
              >
                {Object.entries(skillTypeLabels).map(([type, label]) => (
                  <option key={type} value={type}>{label}</option>
                ))}
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">版本</label>
              <input
                type="text"
                className="w-full px-3 py-2 border border-gray-300 rounded-lg"
                value={editingSkill?.version || '1.0.0'}
                disabled
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
          <TextArea
            label="输入参数 (JSON 格式)"
            value={testParams}
            onChange={(e) => setTestParams(e.target.value)}
            placeholder='{"param1": "value1", "param2": "value2"}'
            rows={4}
          />

          <Button onClick={handleTest} disabled={testing}>
            {testing ? '执行中...' : '执行测试'}
          </Button>

          {testResult && (
            <div className={`p-4 rounded-lg ${testResult.success ? 'bg-green-50' : 'bg-red-50'}`}>
              <div className="flex items-center gap-2 mb-2">
                {testResult.success ? (
                  <CheckCircle size={18} className="text-green-600" />
                ) : (
                  <XCircle size={18} className="text-red-600" />
                )}
                <span className={`font-medium ${testResult.success ? 'text-green-700' : 'text-red-700'}`}>
                  {testResult.success ? '执行成功' : '执行失败'}
                </span>
                {testResult.execution_time_ms && (
                  <span className="text-xs text-gray-500">
                    ({testResult.execution_time_ms}ms)
                  </span>
                )}
              </div>

              {testResult.output && (
                <pre className="bg-white p-3 rounded text-sm overflow-x-auto whitespace-pre-wrap">
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
    </div>
  )
}
