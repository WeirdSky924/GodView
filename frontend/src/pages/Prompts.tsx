/**
 * Prompt 库管理页面
 * v7 核心功能：Prompt 模板的 CRUD、分类筛选、变量预览
 */

import { useEffect, useState } from 'react'
import { Card, Button, Input, TextArea, Modal } from '@/components/ui'
import PageLayout from '@/components/PageLayout'
import {
  getPrompts,
  createPrompt,
  updatePrompt,
  deletePrompt,
  searchPrompts,
  getCategories,
  renderPrompt,
  PromptTemplate,
  PromptCategory,
  PromptVariable,
  CreatePromptDTO,
  UpdatePromptDTO,
} from '@/api/prompts'
import { Search, Plus, Edit2, Trash2, Eye, X } from 'lucide-react'
import { useTheme } from '@/contexts/ThemeContext'

// 与后端 PromptCategory 枚举保持一致
const CATEGORY_LABELS: Record<PromptCategory, string> = {
  base: '基础定义',
  role: '角色定义',
  function: '功能规范',
  value: '价值观/风格',
  output: '输出格式',
  constraint: '约束条件',
}

export default function Prompts() {
  const { theme } = useTheme()
  const isDark = theme === 'dark'

  const [prompts, setPrompts] = useState<PromptTemplate[]>([])
  const [categories, setCategories] = useState<Record<string, number>>({})
  const [loading, setLoading] = useState(true)
  const [searchQuery, setSearchQuery] = useState('')
  const [selectedCategory, setSelectedCategory] = useState<PromptCategory | null>(null)
  const [selectedTags, setSelectedTags] = useState<string[]>([])
  const [showSystemOnly, setShowSystemOnly] = useState<boolean | undefined>(undefined)

  // Modal 状态
  const [showEditModal, setShowEditModal] = useState(false)
  const [showPreviewModal, setShowPreviewModal] = useState(false)
  const [editingPrompt, setEditingPrompt] = useState<PromptTemplate | null>(null)
  const [previewContent, setPreviewContent] = useState('')
  const [previewVariables, setPreviewVariables] = useState<Record<string, any>>({})

  // 表单状态
  const [formData, setFormData] = useState<CreatePromptDTO>({
    name: '',
    description: '',
    category: 'function',
    tags: [],
    content: '',
    variables: [],
    priority: 50,
  })
  const [tagInput, setTagInput] = useState('')

  useEffect(() => {
    loadPrompts()
    loadCategories()
  }, [selectedCategory, selectedTags, showSystemOnly])

  const loadPrompts = async () => {
    setLoading(true)
    try {
      const data = await getPrompts({
        category: selectedCategory || undefined,
        tags: selectedTags.length > 0 ? selectedTags : undefined,
        is_system: showSystemOnly,
        search: searchQuery || undefined,
      })
      setPrompts(data)
    } catch (error) {
      console.error('Failed to load prompts:', error)
    } finally {
      setLoading(false)
    }
  }

  const loadCategories = async () => {
    try {
      const data = await getCategories()
      setCategories(data)
    } catch (error) {
      console.error('Failed to load categories:', error)
    }
  }

  const handleSearch = async () => {
    if (!searchQuery.trim()) {
      loadPrompts()
      return
    }
    setLoading(true)
    try {
      const data = await searchPrompts(searchQuery, selectedCategory || undefined)
      setPrompts(data)
    } catch (error) {
      console.error('Failed to search prompts:', error)
    } finally {
      setLoading(false)
    }
  }

  const handleCreate = () => {
    setEditingPrompt(null)
    setFormData({
      name: '',
      description: '',
      category: 'function',
      tags: [],
      content: '',
      variables: [],
      priority: 50,
    })
    setShowEditModal(true)
  }

  const handleEdit = (prompt: PromptTemplate) => {
    setEditingPrompt(prompt)
    setFormData({
      name: prompt.name,
      description: prompt.description,
      category: prompt.category,
      tags: prompt.tags || [],
      content: prompt.content,
      variables: prompt.variables || [],
      priority: prompt.priority,
    })
    setShowEditModal(true)
  }

  const handleDelete = async (promptId: string) => {
    if (!confirm('确定要删除此 Prompt 模板吗？')) return
    try {
      await deletePrompt(promptId)
      loadPrompts()
    } catch (error) {
      console.error('Failed to delete prompt:', error)
    }
  }

  const handlePreview = async (prompt: PromptTemplate) => {
    // 初始化变量默认值
    const defaultVars: Record<string, any> = {}
    prompt.variables.forEach(v => {
      if (v.default !== undefined) {
        defaultVars[v.name] = v.default
      }
    })
    setPreviewVariables(defaultVars)
    setEditingPrompt(prompt)
    setShowPreviewModal(true)
    await doRenderPreview(prompt.id, defaultVars)
  }

  const doRenderPreview = async (promptId: string, vars: Record<string, any>) => {
    try {
      const result = await renderPrompt(promptId, vars)
      setPreviewContent(result.rendered_content)
    } catch (error) {
      console.error('Failed to render preview:', error)
      setPreviewContent('渲染失败')
    }
  }

  const handleSave = async () => {
    try {
      if (editingPrompt) {
        await updatePrompt(editingPrompt.id, formData as UpdatePromptDTO)
      } else {
        await createPrompt(formData)
      }
      setShowEditModal(false)
      loadPrompts()
    } catch (error) {
      console.error('Failed to save prompt:', error)
    }
  }

  const handleAddTag = () => {
    const currentTags = formData.tags || []
    if (tagInput.trim() && !currentTags.includes(tagInput.trim())) {
      setFormData({ ...formData, tags: [...currentTags, tagInput.trim()] })
      setTagInput('')
    }
  }

  const handleRemoveTag = (tag: string) => {
    const currentTags = formData.tags || []
    setFormData({ ...formData, tags: currentTags.filter(t => t !== tag) })
  }

  const handleAddVariable = () => {
    const currentVars = formData.variables || []
    setFormData({
      ...formData,
      variables: [
        ...currentVars,
        { name: '', type: 'string', description: '', required: false },
      ],
    })
  }

  const handleUpdateVariable = (index: number, field: keyof PromptVariable, value: any) => {
    const currentVars = formData.variables || []
    const newVars = [...currentVars]
    newVars[index] = { ...newVars[index], [field]: value }
    setFormData({ ...formData, variables: newVars })
  }

  const handleRemoveVariable = (index: number) => {
    const currentVars = formData.variables || []
    setFormData({
      ...formData,
      variables: currentVars.filter((_, i) => i !== index),
    })
  }

  // 获取所有标签
  const allTags = Array.from(new Set((prompts || []).flatMap(p => p.tags || [])))

  // 获取所有标签
  return (
    <PageLayout
      title="Prompt 库"
      description="管理可复用的 Prompt 模板"
      actions={
        <Button onClick={handleCreate}>
          <Plus className="w-4 h-4 mr-2" />
          新建 Prompt
        </Button>
      }
      filters={
        <div className="space-y-3">
          <div className="flex gap-4 flex-wrap">
            <div className="flex-1 min-w-[200px]">
              <div className="relative">
                <Input
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  placeholder="搜索 Prompt..."
                  onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
                />
                <Button
                  variant="secondary"
                  size="sm"
                  className="absolute right-1 top-1"
                  onClick={handleSearch}
                >
                  <Search className="w-4 h-4" />
                </Button>
              </div>
            </div>

            <select
              className={`border rounded px-3 py-2 text-sm ${isDark ? 'bg-gray-800 border-gray-600 text-white' : 'bg-white border-gray-300 text-gray-800'}`}
              value={selectedCategory || ''}
              onChange={(e) => setSelectedCategory(e.target.value as PromptCategory || null)}
            >
              <option value="">全部分类</option>
              {Object.entries(CATEGORY_LABELS).map(([key, label]) => (
                <option key={key} value={key}>
                  {label} ({categories[key] || 0})
                </option>
              ))}
            </select>

            <select
              className={`border rounded px-3 py-2 text-sm ${isDark ? 'bg-gray-800 border-gray-600 text-white' : 'bg-white border-gray-300 text-gray-800'}`}
              value={showSystemOnly === undefined ? '' : showSystemOnly ? 'system' : 'custom'}
              onChange={(e) => {
                const val = e.target.value
                setShowSystemOnly(val === '' ? undefined : val === 'system')
              }}
            >
              <option value="">全部来源</option>
              <option value="system">系统内置</option>
              <option value="custom">用户自定义</option>
            </select>
          </div>

          {allTags.length > 0 && (
            <div className="flex gap-2 flex-wrap">
              <span className={isDark ? 'text-gray-400' : 'text-gray-500'}>标签：</span>
              {allTags.map((tag) => (
                <button
                  key={tag}
                  onClick={() => {
                    setSelectedTags(
                      selectedTags.includes(tag)
                        ? selectedTags.filter((t) => t !== tag)
                        : [...selectedTags, tag]
                    )
                  }}
                  className={`px-2 py-1 text-xs rounded ${
                    selectedTags.includes(tag)
                      ? 'bg-blue-600 text-white'
                      : isDark
                        ? 'bg-gray-700 text-gray-300 hover:bg-gray-600'
                        : 'bg-gray-200 text-gray-600 hover:bg-gray-300'
                  }`}
                >
                  {tag}
                </button>
              ))}
            </div>
          )}
        </div>
      }
    >
      {loading ? (
        <div className={`text-center py-8 ${isDark ? 'text-gray-400' : 'text-gray-500'}`}>加载中...</div>
      ) : (!prompts || prompts.length === 0) ? (
        <div className={`text-center py-8 ${isDark ? 'text-gray-400' : 'text-gray-500'}`}>暂无数据</div>
      ) : (
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
            {prompts.map((prompt) => (
              <Card key={prompt.id} className="p-4">
                <div className="flex items-start justify-between mb-2">
                  <div className="flex-1">
                    <h3 className={`font-semibold text-lg ${isDark ? 'text-white' : 'text-gray-800'}`}>{prompt.name}</h3>
                    <p className={`text-sm ${isDark ? 'text-gray-400' : 'text-gray-500'}`}>{prompt.description}</p>
                  </div>
                  {prompt.is_system && (
                    <span className="px-2 py-1 text-xs bg-blue-900 text-blue-300 rounded">系统</span>
                  )}
                </div>

                <div className="flex items-center gap-2 mb-3">
                  <span className={`px-2 py-1 text-xs rounded ${isDark ? 'bg-gray-700' : 'bg-gray-100'}`}>
                    {CATEGORY_LABELS[prompt.category]}
                  </span>
                  {prompt.variables.length > 0 && (
                    <span className="px-2 py-1 text-xs bg-purple-900 text-purple-300 rounded">
                      {prompt.variables.length} 变量
                    </span>
                  )}
                </div>

                {prompt.tags.length > 0 && (
                  <div className="flex gap-1 mb-3 flex-wrap">
                    {prompt.tags.slice(0, 3).map((tag) => (
                      <span key={tag} className={`px-1.5 py-0.5 text-xs rounded ${isDark ? 'bg-gray-800' : 'bg-gray-100'}`}>
                        {tag}
                      </span>
                    ))}
                    {prompt.tags.length > 3 && (
                      <span className={`text-xs ${isDark ? 'text-gray-500' : 'text-gray-400'}`}>+{prompt.tags.length - 3}</span>
                    )}
                  </div>
                )}

                <div className={`text-sm mb-3 line-clamp-2 ${isDark ? 'text-gray-500' : 'text-gray-600'}`}>
                  {prompt.content.substring(0, 100)}...
                </div>

                <div className="flex gap-2">
                  <Button size="sm" variant="secondary" onClick={() => handlePreview(prompt)}>
                    <Eye className="w-4 h-4 mr-1" />
                    预览
                  </Button>
                  {!prompt.is_system && (
                    <>
                      <Button size="sm" variant="secondary" onClick={() => handleEdit(prompt)}>
                        <Edit2 className="w-4 h-4 mr-1" />
                        编辑
                      </Button>
                      <Button size="sm" variant="danger" onClick={() => handleDelete(prompt.id)}>
                        <Trash2 className="w-4 h-4" />
                      </Button>
                    </>
                  )}
                </div>
              </Card>
            ))}
          </div>
        )}

      {/* 编辑/创建 Modal */}
      <Modal isOpen={showEditModal} onClose={() => setShowEditModal(false)} title={editingPrompt ? '编辑 Prompt' : '新建 Prompt'} size="xl">
        <div className="space-y-4">
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className={`block text-sm mb-1 ${isDark ? 'text-gray-400' : 'text-gray-600'}`}>名称</label>
              <Input
                value={formData.name}
                onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                placeholder="Prompt 名称"
              />
            </div>
            <div>
              <label className={`block text-sm mb-1 ${isDark ? 'text-gray-400' : 'text-gray-600'}`}>分类</label>
              <select
                className={`w-full border rounded px-3 py-2 ${isDark ? 'bg-gray-800 border-gray-600 text-white' : 'bg-white border-gray-300 text-gray-800'}`}
                value={formData.category}
                onChange={(e) => setFormData({ ...formData, category: e.target.value as PromptCategory })}
              >
                {Object.entries(CATEGORY_LABELS).map(([key, label]) => (
                  <option key={key} value={key}>{label}</option>
                ))}
              </select>
            </div>
          </div>

          <div>
            <label className={`block text-sm mb-1 ${isDark ? 'text-gray-400' : 'text-gray-600'}`}>描述</label>
            <Input
              value={formData.description}
              onChange={(e) => setFormData({ ...formData, description: e.target.value })}
              placeholder="简要描述此 Prompt 的用途"
            />
          </div>

          <div>
            <label className={`block text-sm mb-1 ${isDark ? 'text-gray-400' : 'text-gray-600'}`}>内容</label>
            <TextArea
              value={formData.content}
              onChange={(e) => setFormData({ ...formData, content: e.target.value })}
              placeholder="Prompt 内容，可使用 {{变量名}} 插入变量"
              rows={8}
            />
          </div>

          {/* 标签 */}
          <div>
            <label className={`block text-sm mb-1 ${isDark ? 'text-gray-400' : 'text-gray-600'}`}>标签</label>
            <div className="flex gap-2 mb-2">
              <Input
                value={tagInput}
                onChange={(e) => setTagInput(e.target.value)}
                placeholder="输入标签"
                onKeyDown={(e) => e.key === 'Enter' && (e.preventDefault(), handleAddTag())}
                className="flex-1"
              />
              <Button variant="secondary" onClick={handleAddTag}>添加</Button>
            </div>
            <div className="flex gap-1 flex-wrap">
              {(formData.tags || []).map((tag) => (
                <span key={tag} className={`px-2 py-1 rounded flex items-center gap-1 ${isDark ? 'bg-gray-700' : 'bg-gray-200'}`}>
                  <span className={isDark ? 'text-white' : 'text-gray-800'}>{tag}</span>
                  <button onClick={() => handleRemoveTag(tag)} className={isDark ? 'text-gray-400 hover:text-white' : 'text-gray-500 hover:text-gray-700'}>
                    <X className="w-3 h-3" />
                  </button>
                </span>
              ))}
            </div>
          </div>

          {/* 变量定义 */}
          <div>
            <div className="flex items-center justify-between mb-2">
              <label className={`block text-sm font-medium ${isDark ? 'text-gray-300' : 'text-gray-700'}`}>变量定义</label>
              <Button size="sm" variant="secondary" onClick={handleAddVariable}>
                <Plus className="w-4 h-4 mr-1" />
                添加变量
              </Button>
            </div>
            {(formData.variables?.length ?? 0) > 0 && (
              <div className="space-y-2">
                {(formData.variables || []).map((variable, index) => (
                  <div key={index} className={`flex gap-2 items-start p-3 rounded-lg border ${isDark ? 'bg-gray-800 border-gray-700' : 'bg-gray-50 border-gray-200'}`}>
                    <div className="flex-1">
                      <label className={`block text-xs mb-1 ${isDark ? 'text-gray-500' : 'text-gray-500'}`}>变量名</label>
                      <Input
                        value={variable.name}
                        onChange={(e) => handleUpdateVariable(index, 'name', e.target.value)}
                        placeholder="如：character_name"
                      />
                    </div>
                    <div className="w-28">
                      <label className={`block text-xs mb-1 ${isDark ? 'text-gray-500' : 'text-gray-500'}`}>类型</label>
                      <select
                        className={`w-full border rounded px-2 py-2 text-sm ${isDark ? 'bg-gray-700 border-gray-600 text-white' : 'bg-white border-gray-300 text-gray-800'}`}
                        value={variable.type}
                        onChange={(e) => handleUpdateVariable(index, 'type', e.target.value)}
                      >
                        <option value="string">字符串</option>
                        <option value="number">数字</option>
                        <option value="boolean">布尔</option>
                        <option value="array">数组</option>
                        <option value="object">对象</option>
                      </select>
                    </div>
                    <div className="flex-1">
                      <label className={`block text-xs mb-1 ${isDark ? 'text-gray-500' : 'text-gray-500'}`}>描述</label>
                      <Input
                        value={variable.description}
                        onChange={(e) => handleUpdateVariable(index, 'description', e.target.value)}
                        placeholder="变量描述"
                      />
                    </div>
                    <div className="flex items-end gap-2 pb-1">
                      <label className={`flex items-center gap-1 text-sm ${isDark ? 'text-gray-300' : 'text-gray-600'}`}>
                        <input
                          type="checkbox"
                          checked={variable.required}
                          onChange={(e) => handleUpdateVariable(index, 'required', e.target.checked)}
                          className="w-4 h-4"
                        />
                        必填
                      </label>
                      <Button size="sm" variant="danger" onClick={() => handleRemoveVariable(index)}>
                        <Trash2 className="w-4 h-4" />
                      </Button>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className={`block text-sm mb-1 ${isDark ? 'text-gray-400' : 'text-gray-600'}`}>优先级 (1-100)</label>
              <Input
                type="number"
                value={formData.priority}
                onChange={(e) => setFormData({ ...formData, priority: parseInt(e.target.value) || 50 })}
                min={1}
                max={100}
              />
            </div>
          </div>

          <div className="flex justify-end gap-2 pt-4">
            <Button variant="secondary" onClick={() => setShowEditModal(false)} className="whitespace-nowrap">取消</Button>
            <Button onClick={handleSave} className="whitespace-nowrap">{editingPrompt ? '保存' : '创建'}</Button>
          </div>
        </div>
      </Modal>

      {/* 预览 Modal */}
      <Modal isOpen={showPreviewModal} onClose={() => setShowPreviewModal(false)} title="Prompt 预览" size="xl">
        <div className="space-y-4">
          {editingPrompt && editingPrompt.variables.length > 0 && (
            <div>
              <h4 className={`text-sm mb-2 ${isDark ? 'text-gray-400' : 'text-gray-600'}`}>变量值</h4>
              <div className="grid gap-2 grid-cols-2">
                {editingPrompt.variables.map((v) => (
                  <div key={v.name}>
                    <label className={`block text-xs mb-1 ${isDark ? 'text-gray-500' : 'text-gray-400'}`}>{v.name}</label>
                    <Input
                      value={previewVariables[v.name] || ''}
                      onChange={(e) => {
                        const newVars = { ...previewVariables, [v.name]: e.target.value }
                        setPreviewVariables(newVars)
                        doRenderPreview(editingPrompt.id, newVars)
                      }}
                      placeholder={v.description}
                    />
                  </div>
                ))}
              </div>
            </div>
          )}

          <div>
            <h4 className={`text-sm mb-2 ${isDark ? 'text-gray-400' : 'text-gray-600'}`}>渲染结果</h4>
            <pre className={`p-4 rounded text-sm overflow-auto max-h-[400px] whitespace-pre-wrap ${isDark ? 'bg-gray-900' : 'bg-gray-100'}`}>
              {previewContent || '加载中...'}
            </pre>
          </div>
        </div>
      </Modal>
    </PageLayout>
  )
}
