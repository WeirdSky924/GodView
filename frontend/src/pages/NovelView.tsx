import { useState, useEffect, useCallback } from 'react'
import { Card, Button, Input, Modal } from '@/components/ui'
import PageLayout from '@/components/PageLayout'
import {
  FileText, Download, ChevronLeft, ChevronRight, Save, Plus,
  Edit3, Eye, Trash2, RefreshCw, FileDown, FolderOpen
} from 'lucide-react'
import { getChapters, createChapter, updateChapter, deleteChapter } from '@/api/chapters'
import type { Chapter } from '@/api/chapters'
import { useProject } from '@/contexts/ProjectContext'
import { useTheme } from '@/contexts/ThemeContext'


export default function NovelView() {
  const { currentProject } = useProject()
  const { theme } = useTheme()
  const isDark = theme === 'dark'

  const [chapters, setChapters] = useState<Chapter[]>([])
  const [currentChapterIndex, setCurrentChapterIndex] = useState(-1)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [editMode, setEditMode] = useState(false)
  const [showCreateModal, setShowCreateModal] = useState(false)
  const [newChapterTitle, setNewChapterTitle] = useState('')
  const [saveStatus, setSaveStatus] = useState<'idle' | 'saved' | 'saving'>('idle')

  const currentChapter = currentChapterIndex >= 0 ? chapters[currentChapterIndex] : null

  // 加载章节列表
  const loadChapters = useCallback(async () => {
    if (!currentProject) {
      setChapters([])
      setLoading(false)
      return
    }
    setLoading(true)
    try {
      const data = await getChapters(currentProject.id)
      setChapters(data)
      if (data.length > 0 && currentChapterIndex === -1) {
        setCurrentChapterIndex(0)
      }
    } catch (error) {
      console.error('Failed to load chapters:', error)
    } finally {
      setLoading(false)
    }
  }, [currentProject, currentChapterIndex])

  useEffect(() => {
    loadChapters()
  }, [loadChapters])

  // 创建章节
  const handleCreateChapter = async () => {
    if (!newChapterTitle.trim()) return
    try {
      const result = await createChapter({
        title: newChapterTitle,
        content: '',
        status: 'draft',
      })
      await loadChapters()
      const newIndex = chapters.findIndex((c) => c.id === result.id)
      if (newIndex >= 0) setCurrentChapterIndex(newIndex)
      setShowCreateModal(false)
      setNewChapterTitle('')
      setEditMode(true)
    } catch (error) {
      console.error('Failed to create chapter:', error)
    }
  }

  // 删除章节
  const handleDeleteChapter = async (id: string | undefined) => {
    if (!id || !confirm('确定要删除这个章节吗？此操作不可撤销。')) return
    try {
      await deleteChapter(id)
      const newIndex = Math.max(0, currentChapterIndex - 1)
      await loadChapters()
      setCurrentChapterIndex(newIndex)
    } catch (error) {
      console.error('Failed to delete chapter:', error)
    }
  }

  // 更新章节内容
  const handleSave = async () => {
    if (!currentChapter?.id) return
    setSaving(true)
    setSaveStatus('saving')
    try {
      await updateChapter(currentChapter.id, {
        title: currentChapter.title,
        content: currentChapter.content,
        status: currentChapter.status,
      })
      setSaveStatus('saved')
      setTimeout(() => setSaveStatus('idle'), 2000)
    } catch (error) {
      console.error('Failed to save chapter:', error)
      alert('保存失败，请重试')
    } finally {
      setSaving(false)
    }
  }

  // 切换编辑/预览模式
  const toggleEditMode = () => {
    setEditMode(!editMode)
  }

  // 更新当前章节内容
  const updateCurrentChapter = (updates: Partial<Chapter>) => {
    if (!currentChapter) return
    setChapters((prev) =>
      prev.map((c, i) =>
        i === currentChapterIndex ? { ...c, ...updates } : c
      )
    )
  }

  // 导出为 TXT
  const exportToTxt = () => {
    let content = `${currentChapter?.title || '未命名小说'}\n\n`
    chapters.forEach((chapter, index) => {
      content += `${chapter.title}\n`
      content += '='.repeat(40) + '\n\n'
      content += (chapter.content || '') + '\n\n'
      if (index < chapters.length - 1) {
        content += '\n' + '-'.repeat(60) + '\n\n'
      }
    })

    const blob = new Blob([content], { type: 'text/plain;charset=utf-8' })
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = `${currentChapter?.title || '小说'}.txt`
    link.click()
    URL.revokeObjectURL(url)
  }

  // 导出当前章节
  const exportCurrentChapter = () => {
    if (!currentChapter) return
    const content = `${currentChapter.title}\n\n${currentChapter.content || ''}`
    const blob = new Blob([content], { type: 'text/plain;charset=utf-8' })
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = `${currentChapter.title}.txt`
    link.click()
    URL.revokeObjectURL(url)
  }

  // 导出 Markdown
  const exportToMarkdown = () => {
    let content = `# ${currentChapter?.title || '未命名小说'}\n\n`
    chapters.forEach((chapter) => {
      content += `## ${chapter.title}\n\n`
      content += (chapter.content || '') + '\n\n---\n\n'
    })

    const blob = new Blob([content], { type: 'text/markdown;charset=utf-8' })
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = `${currentChapter?.title || '小说'}.md`
    link.click()
    URL.revokeObjectURL(url)
  }

  const getStatusLabel = (status: string) => {
    switch (status) {
      case 'draft': return '草稿'
      case 'published': return '已发布'
      case 'archived': return '已归档'
      default: return status
    }
  }

  const getStatusClass = (status: string) => {
    switch (status) {
      case 'draft': return isDark ? 'bg-yellow-900/50 text-yellow-400' : 'bg-yellow-100 text-yellow-700'
      case 'published': return isDark ? 'bg-green-900/50 text-green-400' : 'bg-green-100 text-green-700'
      case 'archived': return isDark ? 'bg-gray-700 text-gray-300' : 'bg-gray-100 text-gray-700'
      default: return isDark ? 'bg-gray-700 text-gray-300' : 'bg-gray-100'
    }
  }

  const wordCount = (text: string) => {
    const chinese = (text.match(/[\u4e00-\u9fa5]/g) || []).length
    const words = (text.match(/[a-zA-Z]+/g) || []).length
    return chinese + words
  }

  // Action buttons for PageLayout header
  const headerActions = (
    <div className="flex items-center gap-3">
      {saveStatus === 'saved' && (
        <span className="text-sm text-green-600 flex items-center gap-1">
          已保存
        </span>
      )}
      <div className="relative group">
        <Button variant="secondary" disabled={!currentProject}>
          <Download size={18} className="mr-2" />
          导出
        </Button>
        <div className={`absolute right-0 top-full mt-1 rounded-lg shadow-lg border py-1 hidden group-hover:block z-10 min-w-[160px] ${
          isDark ? 'bg-gray-800 border-gray-700' : 'bg-white border-gray-200'
        }`}>
          <button
            onClick={exportToTxt}
            className={`w-full text-left px-4 py-2 text-sm flex items-center gap-2 ${
              isDark ? 'hover:bg-gray-700 text-gray-200' : 'hover:bg-gray-50 text-gray-700'
            }`}
          >
            <FileText size={16} /> 导出全文 TXT
          </button>
          <button
            onClick={exportCurrentChapter}
            className={`w-full text-left px-4 py-2 text-sm flex items-center gap-2 ${
              isDark ? 'hover:bg-gray-700 text-gray-200' : 'hover:bg-gray-50 text-gray-700'
            }`}
          >
            <FileText size={16} /> 导出当前章节
          </button>
          <button
            onClick={exportToMarkdown}
            className={`w-full text-left px-4 py-2 text-sm flex items-center gap-2 ${
              isDark ? 'hover:bg-gray-700 text-gray-200' : 'hover:bg-gray-50 text-gray-700'
            }`}
          >
            <FileDown size={16} /> 导出 Markdown
          </button>
        </div>
      </div>
      <Button onClick={() => setShowCreateModal(true)} disabled={!currentProject}>
        <Plus size={18} className="mr-2" />
        新建章节
      </Button>
    </div>
  )

  return (
    <PageLayout
      title="小说编辑器"
      description="编辑和管理小说章节"
      actions={headerActions}
    >
      {!currentProject ? (
        <div className={`text-center py-20 ${isDark ? 'text-gray-400' : 'text-gray-500'}`}>
          <FolderOpen size={48} className="mx-auto mb-4 opacity-50" />
          <p>请先在侧边栏选择一个项目</p>
        </div>
      ) : loading ? (
        <div className="flex items-center justify-center py-20">
          <RefreshCw size={24} className="animate-spin mr-3" />
          <span className={isDark ? 'text-gray-400' : 'text-gray-500'}>加载章节...</span>
        </div>
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
          {/* 目录 */}
          <Card className="lg:col-span-1 h-[calc(100vh-200px)] flex flex-col">
            <div className={`px-6 py-4 border-b flex items-center justify-between ${isDark ? 'border-gray-700' : 'border-gray-200'}`}>
              <h2 className={`font-semibold flex items-center gap-2 ${isDark ? 'text-white' : 'text-gray-800'}`}>
                <FileText size={20} />
                目录 ({chapters.length})
              </h2>
            </div>
            <div className="flex-1 overflow-y-auto p-4 space-y-2">
              {chapters.length === 0 ? (
                <div className="text-center py-8">
                  <p className={`text-sm mb-3 ${isDark ? 'text-gray-400' : 'text-gray-500'}`}>暂无章节</p>
                  <Button size="sm" onClick={() => setShowCreateModal(true)}>
                    <Plus size={16} className="mr-1" /> 创建第一章
                  </Button>
                </div>
              ) : (
                chapters.map((chapter, index) => (
                  <div
                    key={chapter.id || index}
                    onClick={() => setCurrentChapterIndex(index)}
                    className={`p-3 rounded-lg cursor-pointer transition-colors group ${
                      index === currentChapterIndex
                        ? isDark ? 'bg-blue-900/30 border-l-4 border-blue-500' : 'bg-blue-50 border-l-4 border-blue-500'
                        : isDark ? 'hover:bg-gray-700 border-l-4 border-transparent' : 'hover:bg-gray-50 border-l-4 border-transparent'
                    }`}
                  >
                    <div className="flex items-start justify-between">
                      <p className={`font-medium text-sm truncate ${isDark ? 'text-gray-200' : 'text-gray-700'}`}>{chapter.title}</p>
                      <button
                        onClick={(e) => {
                          e.stopPropagation()
                          handleDeleteChapter(chapter.id)
                        }}
                        className={`opacity-0 group-hover:opacity-100 transition-opacity p-1 ${
                          isDark ? 'text-red-400 hover:text-red-300' : 'text-red-400 hover:text-red-600'
                        }`}
                      >
                        <Trash2 size={14} />
                      </button>
                    </div>
                    <div className="flex items-center gap-2 mt-1">
                      <span className={`text-xs px-1.5 py-0.5 rounded ${getStatusClass(chapter.status || 'draft')}`}>
                        {getStatusLabel(chapter.status || 'draft')}
                      </span>
                      <span className={`text-xs ${isDark ? 'text-gray-500' : 'text-gray-400'}`}>
                        {wordCount(chapter.content || '')} 字
                      </span>
                    </div>
                  </div>
                ))
              )}
            </div>
          </Card>

          {/* 编辑/预览区 */}
          <Card className="lg:col-span-3 h-[calc(100vh-200px)] flex flex-col">
            {!currentChapter ? (
              <div className={`flex-1 flex flex-col items-center justify-center ${isDark ? 'text-gray-500' : 'text-gray-400'}`}>
                <FileText size={48} className="mb-4" />
                <p className="text-lg">选择或创建一个章节开始编辑</p>
              </div>
            ) : (
              <>
                {/* 章节头部 */}
                <div className={`px-6 py-4 border-b flex items-center justify-between ${isDark ? 'border-gray-700' : 'border-gray-200'}`}>
                  <div className="flex-1">
                    {editMode ? (
                      <input
                        type="text"
                        value={currentChapter.title}
                        onChange={(e) => updateCurrentChapter({ title: e.target.value })}
                        className={`text-xl font-semibold bg-transparent border-none focus:outline-none w-full ${
                          isDark ? 'text-white' : 'text-gray-800'
                        }`}
                        placeholder="章节标题"
                      />
                    ) : (
                      <h2 className={`text-xl font-semibold ${isDark ? 'text-white' : 'text-gray-800'}`}>{currentChapter.title}</h2>
                    )}
                    <div className="flex items-center gap-3 mt-1">
                      <span className={`text-xs px-2 py-0.5 rounded ${getStatusClass(currentChapter.status || 'draft')}`}>
                        {getStatusLabel(currentChapter.status || 'draft')}
                      </span>
                      <span className={`text-xs ${isDark ? 'text-gray-500' : 'text-gray-400'}`}>
                        {wordCount(currentChapter.content || '')} 字
                      </span>
                      {currentChapter.updated_at && (
                        <span className={`text-xs ${isDark ? 'text-gray-500' : 'text-gray-400'}`}>
                          最后修改: {new Date(currentChapter.updated_at).toLocaleString('zh-CN')}
                        </span>
                      )}
                    </div>
                  </div>
                  <div className="flex items-center gap-2 ml-4">
                    <Button
                      variant="secondary"
                      size="sm"
                      onClick={toggleEditMode}
                    >
                      {editMode ? <Eye size={16} className="mr-1" /> : <Edit3 size={16} className="mr-1" />}
                      {editMode ? '预览' : '编辑'}
                    </Button>
                    {editMode && (
                      <Button
                        size="sm"
                        onClick={handleSave}
                        loading={saving}
                      >
                        <Save size={16} className="mr-1" />
                        保存
                      </Button>
                    )}
                  </div>
                </div>

                {/* 内容区 */}
                <div className="flex-1 overflow-y-auto">
                  {editMode ? (
                    <textarea
                      value={currentChapter.content || ''}
                      onChange={(e) => updateCurrentChapter({ content: e.target.value })}
                      className={`w-full h-full p-6 resize-none border-none focus:outline-none leading-relaxed font-mono text-sm ${
                        isDark ? 'bg-gray-800 text-gray-200' : 'text-gray-700'
                      }`}
                      placeholder="开始写作..."
                      style={{ minHeight: '400px' }}
                    />
                  ) : (
                    <div className="p-6 prose max-w-none">
                      <pre className={`whitespace-pre-wrap leading-relaxed font-sans text-base ${
                        isDark ? 'text-gray-200' : 'text-gray-700'
                      }`}>
                        {currentChapter.content || '暂无内容，点击"编辑"开始创作'}
                      </pre>
                    </div>
                  )}
                </div>

                {/* 底部导航 */}
                <div className={`px-6 py-3 border-t flex items-center justify-between ${isDark ? 'bg-gray-800 border-gray-700' : 'bg-gray-50 border-gray-200'}`}>
                  <Button
                    variant="secondary"
                    size="sm"
                    onClick={() => setCurrentChapterIndex(Math.max(0, currentChapterIndex - 1))}
                    disabled={currentChapterIndex === 0}
                  >
                    <ChevronLeft size={18} className="mr-1" />
                    上一章
                  </Button>
                  <span className={`text-sm ${isDark ? 'text-gray-400' : 'text-gray-500'}`}>
                    {currentChapterIndex + 1} / {chapters.length}
                  </span>
                  <Button
                    variant="secondary"
                    size="sm"
                    onClick={() => setCurrentChapterIndex(Math.min(chapters.length - 1, currentChapterIndex + 1))}
                    disabled={currentChapterIndex === chapters.length - 1}
                  >
                    下一章
                    <ChevronRight size={18} className="ml-1" />
                  </Button>
                </div>
              </>
            )}
          </Card>
        </div>
      )}

      {/* 创建章节模态框 */}
      <Modal
        isOpen={showCreateModal}
        onClose={() => {
          setShowCreateModal(false)
          setNewChapterTitle('')
        }}
        title="新建章节"
      >
        <div className="space-y-4">
          <Input
            label="章节标题 *"
            value={newChapterTitle}
            onChange={(e) => setNewChapterTitle(e.target.value)}
            placeholder="如：第一章 相遇"
            autoFocus
          />
          <div className="flex justify-end gap-3 pt-4">
            <Button
              variant="secondary"
              onClick={() => {
                setShowCreateModal(false)
                setNewChapterTitle('')
              }}
            >
              取消
            </Button>
            <Button onClick={handleCreateChapter} disabled={!newChapterTitle.trim()}>
              创建
            </Button>
          </div>
        </div>
      </Modal>
    </PageLayout>
  )
}
