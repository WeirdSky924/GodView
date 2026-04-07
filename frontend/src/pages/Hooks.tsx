import { useState, useEffect, useCallback } from 'react'
import { Card, Button, Input, TextArea, Modal } from '@/components/ui'
import { getHooks, createHook, updateHookStatus } from '@/api/chapters'
import { Plus, Flag, CheckCircle, Clock, XCircle, Trash2, Edit, FolderOpen } from 'lucide-react'
import { useProject } from '@/contexts/ProjectContext'

interface Hook {
  id?: string
  title: string
  description?: string
  hook_type?: string
  status: 'planted' | 'triggered' | 'resolved' | 'dropped'
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
}

export default function Hooks() {
  const { currentProject } = useProject()
  const [hooks, setHooks] = useState<Hook[]>([])
  const [showModal, setShowModal] = useState(false)
  const [editingHook, setEditingHook] = useState<Hook | null>(null)
  const [loading, setLoading] = useState(true)
  const [filterStatus, setFilterStatus] = useState<string>('all')

  const [formData, setFormData] = useState<CreateHookDTO>({
    title: '',
    description: '',
    hook_type: 'foreshadowing',
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
      const data = await getHooks(currentProject.id, filterStatus === 'all' ? undefined : filterStatus)
      setHooks(data)
    } catch (error) {
      console.error('Failed to load hooks:', error)
    } finally {
      setLoading(false)
    }
  }, [currentProject, filterStatus])

  useEffect(() => {
    loadHooks()
  }, [loadHooks])

  const openCreateModal = () => {
    setEditingHook(null)
    setFormData({ title: '', description: '', hook_type: 'foreshadowing', priority: 1 })
    setShowModal(true)
  }

  const openEditModal = (hook: Hook) => {
    setEditingHook(hook)
    setFormData({
      title: hook.title,
      description: hook.description || '',
      hook_type: hook.hook_type || 'foreshadowing',
      priority: hook.priority || 1,
    })
    setShowModal(true)
  }

  const saveHook = async () => {
    if (!formData.title) return

    try {
      await createHook(formData)
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

  const deleteHook = async (hookId: string | undefined) => {
    if (!hookId || !confirm('确定要删除这个伏笔吗？')) return
    // TODO: add deleteHook API
    alert('删除功能待实现')
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
      foreshadowing: '伏笔',
      character: '角色线索',
      plot: '剧情线索',
      object: '物品线索',
      location: '地点线索',
    }
    return type ? types[type] || type : '伏笔'
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
    <div>
      <div className="flex items-center justify-between mb-8">
        <h1 className="text-3xl font-bold text-gray-800">🎯 伏笔管理</h1>
        <Button onClick={openCreateModal} disabled={!currentProject}>
          <Plus size={20} className="mr-2" />
          新建伏笔
        </Button>
      </div>

      {!currentProject ? (
        <div className="text-center py-20 text-gray-500">
          <FolderOpen size={48} className="mx-auto mb-4 opacity-50" />
          <p>请先在侧边栏选择一个项目</p>
        </div>
      ) : (
        <>
          {/* 状态筛选 */}
          <div className="mb-6 flex gap-2 flex-wrap">
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
                    : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
                }`}
              >
                {s.label} ({statusCounts[s.key as keyof typeof statusCounts]})
              </button>
            ))}
          </div>

          {loading ? (
        <div className="flex items-center justify-center py-20">
          <Flag size={24} className="animate-spin mr-3" />
          <span className="text-gray-500">加载伏笔...</span>
        </div>
      ) : (
        <div className="grid grid-cols-1 gap-4">
          {filteredHooks.length === 0 ? (
            <Card>
              <div className="text-center py-12 text-gray-500">
                <Flag size={48} className="mx-auto mb-4 opacity-50" />
                <p>暂无伏笔记录</p>
                <p className="text-sm mt-2">点击"新建伏笔"开始创建</p>
              </div>
            </Card>
          ) : (
            filteredHooks.map((hook) => (
              <Card key={hook.id} className="hover:shadow-md transition-shadow">
                <div className="flex items-start justify-between">
                  <div className="flex items-start gap-4 flex-1">
                    <div className="mt-1">{getStatusIcon(hook.status)}</div>
                    <div className="flex-1">
                      <div className="flex items-center gap-3">
                        <h3 className="font-semibold text-lg text-gray-800">{hook.title}</h3>
                        <span className={`text-xs px-2 py-0.5 rounded ${getStatusClass(hook.status)}`}>
                          {getStatusLabel(hook.status)}
                        </span>
                        <span className="text-xs px-2 py-0.5 rounded bg-purple-100 text-purple-700">
                          {getTypeLabel(hook.hook_type)}
                        </span>
                        {hook.priority && hook.priority >= 3 && (
                          <span className="text-xs px-2 py-0.5 rounded bg-red-100 text-red-700">
                            高优先级
                          </span>
                        )}
                      </div>
                      <p className="text-sm text-gray-600 mt-2">{hook.description}</p>
                      <div className="flex items-center gap-4 mt-3 text-xs text-gray-500">
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
                    <div className="relative group">
                      <Button variant="secondary" size="sm">
                        变更状态
                      </Button>
                      <div className="absolute right-0 top-full mt-1 bg-white rounded-lg shadow-lg border border-gray-200 py-1 hidden group-hover:block z-10 min-w-[120px]">
                        <button
                          onClick={() => updateStatus(hook.id, 'planted')}
                          className="w-full text-left px-4 py-2 text-sm hover:bg-gray-50 flex items-center gap-2"
                        >
                          <Clock size={14} /> 已埋设
                        </button>
                        <button
                          onClick={() => updateStatus(hook.id, 'triggered')}
                          className="w-full text-left px-4 py-2 text-sm hover:bg-gray-50 flex items-center gap-2"
                        >
                          <Flag size={14} /> 已触发
                        </button>
                        <button
                          onClick={() => updateStatus(hook.id, 'resolved')}
                          className="w-full text-left px-4 py-2 text-sm hover:bg-gray-50 flex items-center gap-2"
                        >
                          <CheckCircle size={14} /> 已回收
                        </button>
                        <button
                          onClick={() => updateStatus(hook.id, 'dropped')}
                          className="w-full text-left px-4 py-2 text-sm hover:bg-gray-50 flex items-center gap-2"
                        >
                          <XCircle size={14} /> 已废弃
                        </button>
                      </div>
                    </div>
                    <Button variant="secondary" size="sm" onClick={() => openEditModal(hook)}>
                      <Edit size={16} />
                    </Button>
                    <Button variant="danger" size="sm" onClick={() => deleteHook(hook.id)}>
                      <Trash2 size={16} />
                    </Button>
                  </div>
                </div>
              </Card>
            ))
          )}
        </div>
      )}

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
              <label className="block text-sm font-medium text-gray-700 mb-1">伏笔类型</label>
              <select
                className="w-full px-3 py-2 border border-gray-300 rounded-lg"
                value={formData.hook_type}
                onChange={(e) => setFormData({ ...formData, hook_type: e.target.value })}
              >
                <option value="foreshadowing">伏笔</option>
                <option value="character">角色线索</option>
                <option value="plot">剧情线索</option>
                <option value="object">物品线索</option>
                <option value="location">地点线索</option>
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">优先级</label>
              <select
                className="w-full px-3 py-2 border border-gray-300 rounded-lg"
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
    </div>
  )
}
