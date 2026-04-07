import { useState, useEffect, useCallback } from 'react'
import { Card, Button, Input, TextArea, Modal } from '@/components/ui'
import { getWorlds, createWorld, updateWorld, deleteWorld } from '@/api/worlds'
import type { World, CreateWorldDTO, UpdateWorldDTO } from '@/api/worlds'
import { Plus, Edit, Trash2, Globe, FolderOpen } from 'lucide-react'
import { useProject } from '@/contexts/ProjectContext'

export default function Worlds() {
  const { currentProject } = useProject()
  const [worlds, setWorlds] = useState<World[]>([])
  const [showModal, setShowModal] = useState(false)
  const [editingWorld, setEditingWorld] = useState<World | null>(null)
  const [loading, setLoading] = useState(true)

  const [formData, setFormData] = useState<CreateWorldDTO>({
    name: '',
    description: '',
    world_type: 'fantasy',
    tone: 'serious',
  })

  // 加载世界列表
  const loadWorlds = useCallback(async () => {
    setLoading(true)
    try {
      const data = await getWorlds(currentProject?.id)
      setWorlds(data)
    } catch (error) {
      console.error('Failed to load worlds:', error)
    } finally {
      setLoading(false)
    }
  }, [currentProject?.id])

  useEffect(() => {
    loadWorlds()
  }, [loadWorlds])

  const openCreateModal = () => {
    setEditingWorld(null)
    setFormData({ name: '', description: '', world_type: 'fantasy', tone: 'serious' })
    setShowModal(true)
  }

  const openEditModal = (world: World) => {
    setEditingWorld(world)
    setFormData({
      name: world.name,
      description: world.description,
      world_type: world.world_type || 'fantasy',
      tone: world.tone || 'serious',
    })
    setShowModal(true)
  }

  const saveWorld = async () => {
    if (!formData.name || !formData.description) return

    try {
      if (editingWorld?.id) {
        await updateWorld(editingWorld.id, formData as UpdateWorldDTO)
      } else {
        await createWorld(formData)
      }
      await loadWorlds()
      setShowModal(false)
    } catch (error) {
      console.error('Failed to save world:', error)
      alert('保存失败，请重试')
    }
  }

  const deleteWorldItem = async (id: string | undefined) => {
    if (!id || !confirm('确定要删除这个世界吗？')) return
    try {
      await deleteWorld(id)
      await loadWorlds()
    } catch (error) {
      console.error('Failed to delete world:', error)
      alert('删除失败，请重试')
    }
  }

  const worldTypes = [
    { value: 'fantasy', label: '奇幻' },
    { value: 'scifi', label: '科幻' },
    { value: 'historical', label: '历史' },
    { value: 'modern', label: '现代' },
    { value: 'other', label: '其他' },
  ]

  const toneOptions = [
    { value: 'serious', label: '严肃' },
    { value: 'light', label: '轻松' },
    { value: 'dark', label: '黑暗' },
    { value: 'humorous', label: '幽默' },
    { value: 'epic', label: '史诗' },
  ]

  return (
    <div>
      <div className="flex items-center justify-between mb-8">
        <h1 className="text-3xl font-bold text-gray-800">🌍 世界管理</h1>
        <Button onClick={openCreateModal} disabled={!currentProject}>
          <Plus size={20} className="mr-2" />
          新建世界
        </Button>
      </div>

      {!currentProject ? (
        <div className="text-center py-20 text-gray-500">
          <FolderOpen size={48} className="mx-auto mb-4 opacity-50" />
          <p>请先在侧边栏选择一个项目</p>
        </div>
      ) : loading ? (
        <div className="flex items-center justify-center py-20">
          <Globe size={24} className="animate-spin mr-3" />
          <span className="text-gray-500">加载世界...</span>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          {worlds.length === 0 ? (
            <div className="col-span-full text-center text-gray-500 py-12">
              暂无世界设定，点击"新建世界"开始创建
            </div>
          ) : (
            worlds.map((world) => (
              <Card key={world.id} className="hover:shadow-md transition-shadow">
                <div className="flex items-start gap-4">
                  <div className="w-16 h-16 bg-gradient-to-br from-green-400 to-blue-500 rounded-lg flex items-center justify-center text-white text-2xl">
                    <Globe size={24} />
                  </div>
                  <div className="flex-1 min-w-0">
                    <h3 className="font-semibold text-lg text-gray-800">{world.name}</h3>
                    <div className="flex items-center gap-2 mt-1">
                      <span className="text-xs px-2 py-0.5 rounded bg-blue-100 text-blue-700">
                        {worldTypes.find((t) => t.value === world.world_type)?.label || '自定义'}
                      </span>
                      <span className="text-xs px-2 py-0.5 rounded bg-purple-100 text-purple-700">
                        {toneOptions.find((t) => t.value === world.tone)?.label || '自定义'}
                      </span>
                    </div>
                    <p className="text-sm text-gray-600 mt-2 line-clamp-3">{world.description}</p>
                  </div>
                </div>
                <div className="flex gap-2 mt-4 pt-4 border-t">
                  <Button variant="secondary" size="sm" onClick={() => openEditModal(world)}>
                    <Edit size={16} className="mr-1" /> 编辑
                  </Button>
                  <Button variant="danger" size="sm" onClick={() => deleteWorldItem(world.id)}>
                    <Trash2 size={16} className="mr-1" /> 删除
                  </Button>
                </div>
              </Card>
            ))
          )}
        </div>
      )}

      <Modal isOpen={showModal} onClose={() => setShowModal(false)} title={editingWorld ? '编辑世界' : '新建世界'}>
        <div className="space-y-4">
          <Input
            label="世界名称 *"
            value={formData.name}
            onChange={(e) => setFormData({ ...formData, name: e.target.value })}
            placeholder="如：九州大陆、星际联邦..."
          />
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">世界类型</label>
              <select
                className="w-full px-3 py-2 border border-gray-300 rounded-lg"
                value={formData.world_type}
                onChange={(e) => setFormData({ ...formData, world_type: e.target.value })}
              >
                {worldTypes.map((t) => (
                  <option key={t.value} value={t.value}>{t.label}</option>
                ))}
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">故事基调</label>
              <select
                className="w-full px-3 py-2 border border-gray-300 rounded-lg"
                value={formData.tone}
                onChange={(e) => setFormData({ ...formData, tone: e.target.value })}
              >
                {toneOptions.map((t) => (
                  <option key={t.value} value={t.value}>{t.label}</option>
                ))}
              </select>
            </div>
          </div>
          <TextArea
            label="世界观描述 *"
            value={formData.description}
            onChange={(e) => setFormData({ ...formData, description: e.target.value })}
            placeholder="描述这个世界的背景、规则、特色..."
            rows={6}
          />
          <div className="flex justify-end gap-3 pt-4">
            <Button variant="secondary" onClick={() => setShowModal(false)}>取消</Button>
            <Button onClick={saveWorld}>保存</Button>
          </div>
        </div>
      </Modal>
    </div>
  )
}
