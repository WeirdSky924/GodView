import { useState, useEffect, useCallback, useRef } from 'react'
import { Card, Button, Input, TextArea, Modal } from '@/components/ui'
import PageLayout from '@/components/PageLayout'
import { getHooks, createHook, updateHook, updateHookStatus, deleteHook as deleteHookApi } from '@/api/chapters'
import { Plus, Flag, CheckCircle, Clock, XCircle, Trash2, Edit, FolderOpen } from 'lucide-react'
import { useProject } from '@/contexts/ProjectContext'
import { useTheme } from '@/contexts/ThemeContext'
import { useProjectWorlds } from '@/hooks/useProjectWorlds'

interface Hook {
  id?: string
  title: string
  description?: string
  hook_type?: string
  status: 'planted' | 'triggered' | 'resolved' | 'dropped'
  world_id?: string | null
  scope_type?: 'project' | 'world' | 'character' | 'arc' | string
  visibility?: string
  related_characters?: string[]
  related_locations?: string[]
  related_objects?: string[]
  plant_context?: string
  plant_chapter?: string
  resolution_hint?: string
  resolution_chapter?: string
  priority?: number
  created_at?: string
  resolved_at?: string
}

interface CreateHookDTO {
  title: string
  description?: string
  hook_type?: string
  related_characters?: string[]
  priority?: number
  project_id?: string
  world_id?: string
  scope_type?: string
}

export default function Hooks() {
  const { currentProject } = useProject()
  const { theme } = useTheme()
  const isDark = theme === 'dark'
  const {
    worlds,
    selectedWorldId,
    setSelectedWorldId,
    formatWorldLabel,
  } = useProjectWorlds(currentProject?.id, currentProject?.world_id)

  const [hooks, setHooks] = useState<Hook[]>([])
  const [showModal, setShowModal] = useState(false)
  const [editingHook, setEditingHook] = useState<Hook | null>(null)
  const [loading, setLoading] = useState(true)
  const [filterStatus, setFilterStatus] = useState<string>('all')
  const [scopeFilter, setScopeFilter] = useState<'all' | 'project' | 'world'>('all')
  const [includeInherited, setIncludeInherited] = useState(true)
  const [openDropdownId, setOpenDropdownId] = useState<string | null>(null)

  const [formData, setFormData] = useState<CreateHookDTO>({
    title: '',
    description: '',
    hook_type: 'custom',
    priority: 1,
  })

  const loadHooks = useCallback(async () => {
    if (!currentProject) {
      setHooks([])
      setLoading(false)
      return
    }
    setLoading(true)
    try {
      const data = await getHooks(
        currentProject.id,
        filterStatus === 'all' ? undefined : filterStatus,
        {
          worldId: scopeFilter === 'world' ? selectedWorldId : undefined,
          includeInherited: scopeFilter === 'world' ? includeInherited : undefined,
          scopeType: scopeFilter === 'project' ? 'project' : undefined,
        },
      )
      setHooks(data)
    } catch (error) {
      console.error('Failed to load hooks:', error)
    } finally {
      setLoading(false)
    }
  }, [currentProject, filterStatus, scopeFilter, selectedWorldId, includeInherited])

  useEffect(() => {
    loadHooks()
  }, [loadHooks])

  // 点击外部关闭下拉菜单
  useEffect(() => {
    const handleClickOutside = () => setOpenDropdownId(null)
    if (openDropdownId) {
      document.addEventListener('click', handleClickOutside)
      return () => document.removeEventListener('click', handleClickOutside)
    }
  }, [openDropdownId])

  const openCreateModal = () => {
    setEditingHook(null)
    const defaultWorldId = selectedWorldId || worlds.find(world => world.is_default)?.id || worlds[0]?.id || ''
    setFormData({
      title: '',
      description: '',
      hook_type: 'custom',
      priority: 1,
      scope_type: defaultWorldId ? 'world' : 'project',
      world_id: defaultWorldId || undefined,
    })
    setShowModal(true)
  }

  const openEditModal = (hook: Hook) => {
    setEditingHook(hook)
    setFormData({
      title: hook.title,
      description: hook.description || '',
      priority: hook.priority || 1,
      hook_type: hook.hook_type || 'custom',
      world_id: hook.world_id || undefined,
      scope_type: hook.scope_type || (hook.world_id ? 'world' : 'project'),
    })
    setShowModal(true)
  }

  const saveHook = async () => {
    if (!formData.title || !currentProject) return

    const payload = {
      ...formData,
      project_id: currentProject.id,
      scope_type: formData.scope_type || (formData.world_id ? 'world' : 'project'),
      world_id: formData.scope_type === 'project' ? null : formData.world_id,
    }

    try {
      if (editingHook?.id) {
        // 编辑模式：更新现有伏笔
        await updateHook(editingHook.id, {
          ...payload,
          status: editingHook.status,
        })
      } else {
        // 新建模式：创建伏笔
        await createHook(payload)
      }
      await loadHooks()
      setShowModal(false)
    } catch (error) {
      console.error('Failed to save hook:', error)
      alert('保存失败，请重试')
    }
  }

  const updateStatus = async (hookId: string | undefined, newStatus: string) => {
    if (!hookId) return
    try {
      await updateHookStatus(hookId, newStatus)
      await loadHooks()
    } catch (error) {
      console.error('Failed to update hook status:', error)
      alert('更新失败，请重试')
    }
  }

  const deleteHookHandler = async (hookId: string | undefined) => {
    if (!hookId || !confirm('确定要删除这个伏笔吗？')) return
    try {
      await deleteHookApi(hookId)
      await loadHooks()
    } catch (error) {
      console.error('Failed to delete hook:', error)
      alert('删除失败，请重试')
    }
  }

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'planted': return <Clock size={16} className="text-blue-500" />
      case 'triggered': return <Flag size={16} className="text-yellow-500" />
      case 'resolved': return <CheckCircle size={16} className="text-green-500" />
      case 'dropped': return <XCircle size={16} className="text-gray-400" />
      default: return <Clock size={16} />
    }
  }

  const getStatusLabel = (status: string) => {
    switch (status) {
      case 'planted': return '已埋设'
      case 'triggered': return '已触发'
      case 'resolved': return '已回收'
      case 'dropped': return '已废弃'
      default: return status
    }
  }

  const getStatusClass = (status: string) => {
    if (isDark) {
      switch (status) {
        case 'planted': return 'bg-blue-900 text-blue-300'
        case 'triggered': return 'bg-yellow-900 text-yellow-300'
        case 'resolved': return 'bg-green-900 text-green-300'
        case 'dropped': return 'bg-gray-700 text-gray-400'
        default: return 'bg-gray-700'
      }
    }
    switch (status) {
      case 'planted': return 'bg-blue-100 text-blue-700'
      case 'triggered': return 'bg-yellow-100 text-yellow-700'
      case 'resolved': return 'bg-green-100 text-green-700'
      case 'dropped': return 'bg-gray-100 text-gray-500'
      default: return 'bg-gray-100'
    }
  }

  const getTypeLabel = (type?: string) => {
    const types: Record<string, string> = {
      mystery: '谜团',
      character: '角色相关',
      event: '事件',
      object: '物品',
      location: '地点',
      relationship: '关系',
      custom: '自定义',
    }
    return type ? types[type] || type : '自定义'
  }

  const filteredHooks = filterStatus === 'all'
    ? hooks
    : hooks.filter(h => h.status === filterStatus)

  const statusCounts = {
    all: hooks.length,
    planted: hooks.filter(h => h.status === 'planted').length,
    triggered: hooks.filter(h => h.status === 'triggered').length,
    resolved: hooks.filter(h => h.status === 'resolved').length,
    dropped: hooks.filter(h => h.status === 'dropped').length,
  }

  return (
    <PageLayout
      title="伏笔管理"
      description="管理小说中的伏笔埋设与回收"
      actions={
        <Button onClick={openCreateModal} disabled={!currentProject}>
          <Plus size={20} className="mr-2" />
          新建伏笔
        </Button>
      }
    >
      {!currentProject ? (
        <div className={`text-center py-20 ${isDark ? 'text-gray-400' : 'text-gray-500'}`}>
          <FolderOpen size={48} className="mx-auto mb-4 opacity-50" />
          <p>请先在侧边栏选择一个项目</p>
        </div>
      ) : (
        <>
        <div className="flex flex-col h-[calc(100vh-200px)]">
          {/* 状态筛选 - 固定在顶部 */}
          <div className="flex gap-2 flex-wrap flex-shrink-0 mb-4">
            {[
              { key: 'all', label: '全部' },
              { key: 'planted', label: '已埋设' },
              { key: 'triggered', label: '已触发' },
              { key: 'resolved', label: '已回收' },
              { key: 'dropped', label: '已废弃' },
            ].map((s) => (
              <button
                key={s.key}
                onClick={() => setFilterStatus(s.key)}
                className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
                  filterStatus === s.key
                    ? 'bg-blue-500 text-white'
                    : isDark
                      ? 'bg-gray-800 text-gray-300 hover:bg-gray-700'
                      : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
                }`}
              >
                {s.label} ({statusCounts[s.key as keyof typeof statusCounts]})
              </button>
            ))}
          </div>

          <div className={`flex flex-wrap items-center gap-3 flex-shrink-0 mb-4 rounded-lg p-3 ${isDark ? 'bg-gray-800' : 'bg-gray-50'}`}>
            <select
              value={scopeFilter}
              onChange={(e) => setScopeFilter(e.target.value as typeof scopeFilter)}
              className={`px-3 py-2 border rounded-lg text-sm ${isDark ? 'bg-gray-900 border-gray-700 text-white' : 'bg-white border-gray-300'}`}
            >
              <option value="all">全部项目伏笔</option>
              <option value="project">仅项目级</option>
              <option value="world">当前世界</option>
            </select>
            <select
              value={selectedWorldId}
              onChange={(e) => setSelectedWorldId(e.target.value)}
              disabled={worlds.length === 0 || scopeFilter !== 'world'}
              className={`px-3 py-2 border rounded-lg text-sm disabled:opacity-60 ${isDark ? 'bg-gray-900 border-gray-700 text-white' : 'bg-white border-gray-300'}`}
            >
              {worlds.map(world => (
                <option key={world.id} value={world.id}>{formatWorldLabel(world)}</option>
              ))}
            </select>
            <label className={`flex items-center gap-2 text-sm ${isDark ? 'text-gray-300' : 'text-gray-600'}`}>
              <input
                type="checkbox"
                checked={includeInherited}
                disabled={scopeFilter !== 'world'}
                onChange={(e) => setIncludeInherited(e.target.checked)}
              />
              包含项目级/父世界继承
            </label>
          </div>

          {/* 列表区域 - 填满剩余空间 */}
          {loading ? (
            <div className="flex items-center justify-center py-20 flex-shrink-0">
              <Flag size={24} className="animate-spin mr-3" />
              <span className={isDark ? 'text-gray-400' : 'text-gray-500'}>加载伏笔...</span>
            </div>
          ) : (
            <div className="flex-1 overflow-y-auto min-h-0">
              <div className="grid grid-cols-1 gap-4">
                {filteredHooks.length === 0 ? (
                  <Card>
                  <div className={`text-center py-12 ${isDark ? 'text-gray-400' : 'text-gray-500'}`}>
                    <Flag size={48} className="mx-auto mb-4 opacity-50" />
                    <p>暂无伏笔记录</p>
                    <p className="text-sm mt-2">点击"新建伏笔"开始创建</p>
                  </div>
                </Card>
              ) : (
                filteredHooks.map((hook) => (
                  <Card key={hook.id} className="hover:shadow-md transition-shadow overflow-visible">
                    <div className="flex items-start justify-between">
                      <div className="flex items-start gap-4 flex-1">
                        <div className="mt-1">{getStatusIcon(hook.status)}</div>
                        <div className="flex-1">
                          <div className="flex items-center gap-3 flex-wrap">
                            <h3 className={`font-semibold text-lg ${isDark ? 'text-white' : 'text-gray-800'}`}>{hook.title}</h3>
                            <span className={`text-xs px-2 py-0.5 rounded ${getStatusClass(hook.status)}`}>
                              {getStatusLabel(hook.status)}
                            </span>
                            <span className={`text-xs px-2 py-0.5 rounded ${isDark ? 'bg-purple-900 text-purple-300' : 'bg-purple-100 text-purple-700'}`}>
                              {getTypeLabel(hook.hook_type)}
                            </span>
                            {hook.priority && hook.priority >= 3 && (
                              <span className={`text-xs px-2 py-0.5 rounded ${isDark ? 'bg-red-900 text-red-300' : 'bg-red-100 text-red-700'}`}>
                                高优先级
                              </span>
                            )}
                            <span className={`text-xs px-2 py-0.5 rounded ${isDark ? 'bg-gray-700 text-gray-300' : 'bg-gray-100 text-gray-600'}`}>
                              {hook.scope_type === 'project' || !hook.world_id
                                ? '项目级'
                                : `世界：${worlds.find(world => world.id === hook.world_id)?.name || hook.world_id}`}
                            </span>
                          </div>
                          <p className={`text-sm mt-2 ${isDark ? 'text-gray-400' : 'text-gray-600'}`}>{hook.description}</p>
                          <div className={`flex items-center gap-4 mt-3 text-xs ${isDark ? 'text-gray-500' : 'text-gray-500'}`}>
                            {hook.plant_chapter && (
                              <span>埋设章节：{hook.plant_chapter}</span>
                            )}
                            {hook.resolution_chapter && (
                              <span>回收章节：{hook.resolution_chapter}</span>
                            )}
                            {hook.created_at && (
                              <span>创建时间：{new Date(hook.created_at).toLocaleDateString('zh-CN')}</span>
                            )}
                          </div>
                        </div>
                      </div>
                      <div className="flex items-center gap-2">
                        <div className="relative">
                          <Button
                            variant="secondary"
                            size="sm"
                            onClick={(e) => { e.stopPropagation(); setOpenDropdownId(openDropdownId === hook.id ? null : hook.id!) }}
                          >
                            变更状态
                          </Button>
                          {openDropdownId === hook.id && (
                            <div
                              className={`absolute right-0 top-full mt-1 rounded-lg shadow-lg border py-1 z-50 min-w-[120px] ${isDark ? 'bg-gray-800 border-gray-700' : 'bg-white border-gray-200'}`}
                              onClick={(e) => e.stopPropagation()}
                            >
                              <button
                                onClick={() => { updateStatus(hook.id, 'planted'); setOpenDropdownId(null); }}
                                className={`w-full text-left px-4 py-2 text-sm hover:bg-gray-50 flex items-center gap-2 ${isDark ? 'hover:bg-gray-700 text-gray-300' : ''}`}
                              >
                                <Clock size={14} /> 已埋设
                              </button>
                              <button
                                onClick={() => { updateStatus(hook.id, 'triggered'); setOpenDropdownId(null); }}
                                className={`w-full text-left px-4 py-2 text-sm hover:bg-gray-50 flex items-center gap-2 ${isDark ? 'hover:bg-gray-700 text-gray-300' : ''}`}
                              >
                                <Flag size={14} /> 已触发
                              </button>
                              <button
                                onClick={() => { updateStatus(hook.id, 'resolved'); setOpenDropdownId(null); }}
                                className={`w-full text-left px-4 py-2 text-sm hover:bg-gray-50 flex items-center gap-2 ${isDark ? 'hover:bg-gray-700 text-gray-300' : ''}`}
                              >
                                <CheckCircle size={14} /> 已回收
                              </button>
                              <button
                                onClick={() => { updateStatus(hook.id, 'dropped'); setOpenDropdownId(null); }}
                                className={`w-full text-left px-4 py-2 text-sm hover:bg-gray-50 flex items-center gap-2 ${isDark ? 'hover:bg-gray-700 text-gray-300' : ''}`}
                              >
                                <XCircle size={14} /> 已废弃
                              </button>
                            </div>
                          )}
                        </div>
                        <Button variant="secondary" size="sm" onClick={() => openEditModal(hook)}>
                          <Edit size={16} />
                        </Button>
                        <Button variant="danger" size="sm" onClick={() => deleteHookHandler(hook.id)}>
                          <Trash2 size={16} />
                        </Button>
                      </div>
                    </div>
                  </Card>
                ))
              )}
              </div>
            </div>
          )}
        </div>

        {/* 创建/编辑模态框 */}
          <Modal
            isOpen={showModal}
            onClose={() => setShowModal(false)}
            title={editingHook ? '编辑伏笔' : '新建伏笔'}
            size="lg"
          >
            <div className="space-y-4">
              <Input
                label="伏笔标题 *"
                value={formData.title}
                onChange={(e) => setFormData({ ...formData, title: e.target.value })}
                placeholder="如：神秘的黑衣人身份"
                autoFocus
              />
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className={`block text-sm font-medium mb-1 ${isDark ? 'text-gray-300' : 'text-gray-700'}`}>作用域</label>
                  <select
                    className={`w-full px-3 py-2 border rounded-lg ${isDark ? 'bg-gray-800 border-gray-600 text-white' : 'border-gray-300'}`}
                    value={formData.scope_type || 'project'}
                    onChange={(e) => setFormData({
                      ...formData,
                      scope_type: e.target.value,
                      world_id: e.target.value === 'project' ? undefined : (formData.world_id || selectedWorldId || worlds[0]?.id),
                    })}
                  >
                    <option value="project">项目级/全局</option>
                    <option value="world">世界级</option>
                    <option value="character">角色级</option>
                    <option value="arc">篇章级</option>
                  </select>
                </div>
                <div>
                  <label className={`block text-sm font-medium mb-1 ${isDark ? 'text-gray-300' : 'text-gray-700'}`}>所属世界</label>
                  <select
                    className={`w-full px-3 py-2 border rounded-lg disabled:opacity-60 ${isDark ? 'bg-gray-800 border-gray-600 text-white' : 'border-gray-300'}`}
                    value={formData.world_id || ''}
                    disabled={!formData.scope_type || formData.scope_type === 'project'}
                    onChange={(e) => setFormData({ ...formData, world_id: e.target.value })}
                  >
                    <option value="">不绑定世界</option>
                    {worlds.map(world => (
                      <option key={world.id} value={world.id}>{formatWorldLabel(world)}</option>
                    ))}
                  </select>
                </div>
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className={`block text-sm font-medium mb-1 ${isDark ? 'text-gray-300' : 'text-gray-700'}`}>伏笔类型</label>
                  <select
                    className={`w-full px-3 py-2 border rounded-lg ${isDark ? 'bg-gray-800 border-gray-600 text-white' : 'border-gray-300'}`}
                    value={formData.hook_type}
                    onChange={(e) => setFormData({ ...formData, hook_type: e.target.value })}
                  >
                    <option value="mystery">谜团</option>
                    <option value="character">角色相关</option>
                    <option value="event">事件</option>
                    <option value="object">物品</option>
                    <option value="location">地点</option>
                    <option value="relationship">关系</option>
                    <option value="custom">自定义</option>
                  </select>
                </div>
                <div>
                  <label className={`block text-sm font-medium mb-1 ${isDark ? 'text-gray-300' : 'text-gray-700'}`}>优先级</label>
                  <select
                    className={`w-full px-3 py-2 border rounded-lg ${isDark ? 'bg-gray-800 border-gray-600 text-white' : 'border-gray-300'}`}
                    value={formData.priority}
                    onChange={(e) => setFormData({ ...formData, priority: parseInt(e.target.value) })}
                  >
                    <option value={1}>普通</option>
                    <option value={2}>重要</option>
                    <option value={3}>高优先级</option>
                  </select>
                </div>
              </div>
              <TextArea
                label="伏笔描述"
                value={formData.description}
                onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                placeholder="描述这个伏笔的内容、作用..."
                rows={4}
              />
              <div className="flex justify-end gap-3 pt-4">
                <Button variant="secondary" onClick={() => setShowModal(false)}>取消</Button>
                <Button onClick={saveHook}>{editingHook ? '保存修改' : '创建'}</Button>
              </div>
            </div>
          </Modal>
        </>
      )}
    </PageLayout>
  )
}
