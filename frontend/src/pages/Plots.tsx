import { useState, useEffect, useCallback } from 'react'
import { Card, Button, Input, TextArea, Modal } from '@/components/ui'
import PageLayout from '@/components/PageLayout'
import { getChapters, createChapter, updateChapter, deleteChapter } from '@/api/chapters'
import type { Chapter, CreateChapterDTO } from '@/api/chapters'
import { Plus, Edit, Trash2, BookOpen, FolderOpen } from 'lucide-react'
import { useProject } from '@/contexts/ProjectContext'
import { useTheme } from '@/contexts/ThemeContext'

export default function Plots() {
  const { currentProject } = useProject()
  const { theme } = useTheme()
  const isDark = theme === 'dark'

  const [chapters, setChapters] = useState<Chapter[]>([])
  const [showModal, setShowModal] = useState(false)
  const [editingChapter, setEditingChapter] = useState<Chapter | null>(null)
  const [loading, setLoading] = useState(true)

  const [formData, setFormData] = useState<CreateChapterDTO>({
    title: '',
    content: '',
    status: 'draft',
  })

  // 加载章节列表
  const loadChapters = useCallback(async () => {
    setLoading(true)
    try {
      const data = await getChapters(currentProject?.id)
      setChapters(data)
    } catch (error) {
      console.error('Failed to load chapters:', error)
    } finally {
      setLoading(false)
    }
  }, [currentProject?.id])

  useEffect(() => {
    loadChapters()
  }, [loadChapters])

  const openCreateModal = () => {
    setEditingChapter(null)
    setFormData({ title: '', content: '', status: 'draft' })
    setShowModal(true)
  }

  const openEditModal = (chapter: Chapter) => {
    setEditingChapter(chapter)
    setFormData({
      title: chapter.title,
      content: chapter.content || '',
      status: chapter.status || 'draft',
    })
    setShowModal(true)
  }

  const saveChapter = async () => {
    if (!formData.title) return

    try {
      if (editingChapter?.id) {
        await updateChapter(editingChapter.id, formData)
      } else {
        await createChapter(formData)
      }
      await loadChapters()
      setShowModal(false)
    } catch (error) {
      console.error('Failed to save chapter:', error)
      alert('保存失败，请重试')
    }
  }

  const deleteChapterItem = async (id: string | undefined) => {
    if (!id || !confirm('确定删除此章节？')) return
    try {
      await deleteChapter(id)
      await loadChapters()
    } catch (error) {
      console.error('Failed to delete chapter:', error)
      alert('删除失败，请重试')
    }
  }

  const getStatusClass = (status: string) => {
    if (isDark) {
      switch (status) {
        case 'draft': return 'bg-yellow-900 text-yellow-300'
        case 'published': return 'bg-green-900 text-green-300'
        case 'archived': return 'bg-gray-700 text-gray-300'
        default: return 'bg-gray-700'
      }
    }
    switch (status) {
      case 'draft': return 'bg-yellow-100 text-yellow-700'
      case 'published': return 'bg-green-100 text-green-700'
      case 'archived': return 'bg-gray-100 text-gray-700'
      default: return 'bg-gray-100'
    }
  }

  const getStatusLabel = (status: string) => {
    switch (status) {
      case 'draft': return '草稿'
      case 'published': return '已发布'
      case 'archived': return '已归档'
      default: return status
    }
  }

  const wordCount = (text: string) => {
    const chinese = (text.match(/[\u4e00-\u9fa5]/g) || []).length
    const words = (text.match(/[a-zA-Z]+/g) || []).length
    return chinese + words
  }

  return (
    <PageLayout
      title="剧情管理"
      description="管理小说章节和剧情发展"
      actions={
        <Button onClick={openCreateModal} disabled={!currentProject}>
          <Plus size={20} className="mr-2" />
          新增章节
        </Button>
      }
    >
      {!currentProject ? (
        <div className={`text-center py-20 ${isDark ? 'text-gray-400' : 'text-gray-500'}`}>
          <FolderOpen size={48} className="mx-auto mb-4 opacity-50" />
          <p>请先在侧边栏选择一个项目</p>
        </div>
      ) : loading ? (
        <div className="flex items-center justify-center py-12">
          <BookOpen size={24} className="animate-spin mr-3" />
          <span className={isDark ? 'text-gray-400' : 'text-gray-500'}>加载章节...</span>
        </div>
      ) : (
        <Card>
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead className={`border-b ${isDark ? 'bg-gray-800' : 'bg-gray-50'}`}>
                <tr>
                  <th className={`px-4 py-3 text-left text-sm font-medium ${isDark ? 'text-gray-400' : 'text-gray-600'}`}>序号</th>
                  <th className={`px-4 py-3 text-left text-sm font-medium ${isDark ? 'text-gray-400' : 'text-gray-600'}`}>章节标题</th>
                  <th className={`px-4 py-3 text-left text-sm font-medium ${isDark ? 'text-gray-400' : 'text-gray-600'}`}>状态</th>
                  <th className={`px-4 py-3 text-left text-sm font-medium ${isDark ? 'text-gray-400' : 'text-gray-600'}`}>字数</th>
                  <th className={`px-4 py-3 text-left text-sm font-medium ${isDark ? 'text-gray-400' : 'text-gray-600'}`}>最后修改</th>
                  <th className={`px-4 py-3 text-left text-sm font-medium ${isDark ? 'text-gray-400' : 'text-gray-600'}`}>操作</th>
                </tr>
              </thead>
              <tbody>
                {chapters.length === 0 ? (
                  <tr>
                    <td colSpan={6} className={`px-4 py-8 text-center ${isDark ? 'text-gray-400' : 'text-gray-500'}`}>
                      暂无章节，点击"新增章节"开始创建
                    </td>
                  </tr>
                ) : (
                  chapters.map((chapter, index) => (
                    <tr key={chapter.id} className={`border-b ${isDark ? 'hover:bg-gray-800 border-gray-700' : 'hover:bg-gray-50'}`}>
                      <td className={`px-4 py-3 ${isDark ? 'text-gray-400' : 'text-gray-500'}`}>{index + 1}</td>
                      <td className={`px-4 py-3 font-medium ${isDark ? 'text-white' : 'text-gray-800'}`}>{chapter.title}</td>
                      <td className="px-4 py-3">
                        <span className={`px-2 py-1 text-xs rounded ${getStatusClass(chapter.status || 'draft')}`}>
                          {getStatusLabel(chapter.status || 'draft')}
                        </span>
                      </td>
                      <td className={`px-4 py-3 ${isDark ? 'text-gray-400' : 'text-gray-500'}`}>{wordCount(chapter.content || '')}</td>
                      <td className={`px-4 py-3 text-sm ${isDark ? 'text-gray-400' : 'text-gray-500'}`}>
                        {chapter.updated_at ? new Date(chapter.updated_at).toLocaleDateString('zh-CN') : '-'}
                      </td>
                      <td className="px-4 py-3">
                        <div className="flex gap-2">
                          <Button variant="secondary" size="sm" onClick={() => openEditModal(chapter)}>
                            <Edit size={16} className="mr-1" /> 编辑
                          </Button>
                          <Button variant="danger" size="sm" onClick={() => deleteChapterItem(chapter.id)}>
                            <Trash2 size={16} />
                          </Button>
                        </div>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </Card>
      )}

      <Modal isOpen={showModal} onClose={() => setShowModal(false)} title={editingChapter ? '编辑章节' : '新增章节'}>
        <div className="space-y-4">
          <Input
            label="章节标题 *"
            value={formData.title}
            onChange={(e) => setFormData({ ...formData, title: e.target.value })}
            placeholder="如：第一章 相遇"
            autoFocus
          />
          <div>
            <label className={`block text-sm font-medium mb-1 ${isDark ? 'text-gray-300' : 'text-gray-700'}`}>状态</label>
            <select
              className={`w-full px-3 py-2 border rounded-lg ${isDark ? 'bg-gray-800 border-gray-600 text-white' : 'border-gray-300'}`}
              value={formData.status}
              onChange={(e) => setFormData({ ...formData, status: e.target.value as string })}
            >
              <option value="draft">草稿</option>
              <option value="published">已发布</option>
              <option value="archived">已归档</option>
            </select>
          </div>
          <TextArea
            label="章节内容"
            value={formData.content || ''}
            onChange={(e) => setFormData({ ...formData, content: e.target.value })}
            placeholder="可以直接在这里编写章节内容，或者在小说编辑器中详细创作..."
            rows={8}
          />
          <div className="flex justify-end gap-3 pt-4">
            <Button variant="secondary" onClick={() => setShowModal(false)}>取消</Button>
            <Button onClick={saveChapter}>{editingChapter ? '保存修改' : '创建'}</Button>
          </div>
        </div>
      </Modal>
    </PageLayout>
  )
}
