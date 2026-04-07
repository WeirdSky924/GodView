/**
 * 项目初始化页面
 * v4 功能：创建新项目或选择现有项目
 */

import React, { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { Plus, FolderOpen, Globe, Loader, ArrowRight, Trash2 } from 'lucide-react'
import { getProjects, createProject, deleteProject, type Project } from '@/api/projects'

export default function ProjectSetup() {
  const navigate = useNavigate()

  const [projects, setProjects] = useState<Project[]>([])
  const [loading, setLoading] = useState(true)
  const [creating, setCreating] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const [newProjectName, setNewProjectName] = useState('')
  const [newProjectType, setNewProjectType] = useState('fantasy')
  const [newProjectTone, setNewProjectTone] = useState('serious')
  const [newProjectDescription, setNewProjectDescription] = useState('')

  useEffect(() => {
    loadProjects()
  }, [])

  const loadProjects = async () => {
    setLoading(true)
    try {
      const result = await getProjects()
      setProjects(result)
    } catch (err) {
      console.error('Failed to load projects:', err)
      setError('加载项目列表失败')
    } finally {
      setLoading(false)
    }
  }

  const handleCreateProject = async () => {
    if (!newProjectName.trim()) {
      setError('请输入项目名称')
      return
    }

    setCreating(true)
    try {
      const project = await createProject({
        name: newProjectName,
        description: newProjectDescription,
        world_type: newProjectType,
        tone: newProjectTone
      })

      setProjects([...projects, project])
      setNewProjectName('')
      setNewProjectDescription('')

      // 创建后跳转到 Bootstrap 页面
      navigate(`/bootstrap?projectId=${project.id}`)
    } catch (err) {
      console.error('Failed to create project:', err)
      setError('创建项目失败')
    } finally {
      setCreating(false)
    }
  }

  const handleDeleteProject = async (projectId: string) => {
    if (!confirm('确定要删除这个项目吗？此操作不可撤销。')) {
      return
    }

    try {
      await deleteProject(projectId)
      setProjects(projects.filter(p => p.id !== projectId))
    } catch (err) {
      console.error('Failed to delete project:', err)
      setError('删除项目失败')
    }
  }

  const handleSelectProject = (project: Project) => {
    navigate(`/bootstrap?projectId=${project.id}`)
  }

  const getWorldTypeLabel = (type?: string): string => {
    const labels: Record<string, string> = {
      fantasy: '奇幻',
      scifi: '科幻',
      modern: '现代',
      historical: '历史',
      wuxia: '武侠',
    }
    return labels[type || 'fantasy'] || type || '奇幻'
  }

  const getToneLabel = (tone?: string): string => {
    const labels: Record<string, string> = {
      serious: '严肃',
      lighthearted: '轻松',
      dark: '暗黑',
      comedic: '喜剧',
      adventurous: '冒险',
    }
    return labels[tone || 'serious'] || tone || '严肃'
  }

  if (loading) {
    return (
      <div className="h-screen flex items-center justify-center">
        <Loader className="w-8 h-8 text-blue-600 animate-spin" />
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-gray-50 p-8">
      <div className="max-w-6xl mx-auto">
        {/* 页面标题 */}
        <div className="text-center mb-10">
          <Globe className="w-16 h-16 text-blue-600 mx-auto mb-4" />
          <h1 className="text-3xl font-bold text-gray-800">项目初始化</h1>
          <p className="text-gray-600 mt-2">创建或选择一个项目开始你的创作之旅</p>
        </div>

        {error && (
          <div className="mb-6 p-4 bg-red-50 border border-red-200 text-red-700 rounded-lg">
            {error}
          </div>
        )}

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
          {/* 创建新项目 */}
          <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
            <div className="flex items-center gap-3 mb-6">
              <Plus className="w-6 h-6 text-green-600" />
              <h2 className="text-xl font-bold text-gray-800">创建新项目</h2>
            </div>

            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  项目名称 *
                </label>
                <input
                  type="text"
                  value={newProjectName}
                  onChange={(e) => setNewProjectName(e.target.value)}
                  className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                  placeholder="例如：星辰之誓"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  项目描述
                </label>
                <textarea
                  value={newProjectDescription}
                  onChange={(e) => setNewProjectDescription(e.target.value)}
                  className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 resize-none"
                  rows={3}
                  placeholder="简单描述你的小说设定..."
                />
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    世界类型
                  </label>
                  <select
                    value={newProjectType}
                    onChange={(e) => setNewProjectType(e.target.value)}
                    className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                  >
                    <option value="fantasy">奇幻</option>
                    <option value="scifi">科幻</option>
                    <option value="modern">现代</option>
                    <option value="historical">历史</option>
                    <option value="wuxia">武侠</option>
                  </select>
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    叙事基调
                  </label>
                  <select
                    value={newProjectTone}
                    onChange={(e) => setNewProjectTone(e.target.value)}
                    className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                  >
                    <option value="serious">严肃</option>
                    <option value="lighthearted">轻松</option>
                    <option value="dark">暗黑</option>
                    <option value="comedic">喜剧</option>
                    <option value="adventurous">冒险</option>
                  </select>
                </div>
              </div>

              <button
                onClick={handleCreateProject}
                disabled={creating || !newProjectName.trim()}
                className="w-full py-3 bg-green-600 text-white font-medium rounded-lg hover:bg-green-700 disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
              >
                {creating ? (
                  <>
                    <Loader className="w-5 h-5 animate-spin" />
                    创建中...
                  </>
                ) : (
                  <>
                    <Plus className="w-5 h-5" />
                    创建项目并开始设定
                  </>
                )}
              </button>
            </div>
          </div>

          {/* 现有项目 */}
          <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
            <div className="flex items-center gap-3 mb-6">
              <FolderOpen className="w-6 h-6 text-blue-600" />
              <h2 className="text-xl font-bold text-gray-800">现有项目</h2>
              <span className="ml-auto text-sm text-gray-500">
                {projects.length} 个项目
              </span>
            </div>

            {projects.length === 0 ? (
              <div className="text-center py-12">
                <FolderOpen className="w-12 h-12 text-gray-300 mx-auto mb-3" />
                <p className="text-gray-500">暂无项目</p>
                <p className="text-sm text-gray-400 mt-1">创建一个新项目开始</p>
              </div>
            ) : (
              <div className="space-y-3 max-h-[500px] overflow-y-auto">
                {projects.map((project) => (
                  <div
                    key={project.id}
                    className="border border-gray-200 rounded-lg p-4 hover:border-blue-300 hover:bg-blue-50 transition-colors cursor-pointer group"
                    onClick={() => handleSelectProject(project)}
                  >
                    <div className="flex items-start justify-between">
                      <div className="flex-1">
                        <div className="font-medium text-gray-800">{project.name}</div>
                        <div className="text-sm text-gray-600 mt-1">
                          {project.description || '无描述'}
                        </div>
                        <div className="flex items-center gap-3 mt-2 text-xs text-gray-500">
                          <span>{getWorldTypeLabel(project.world_type)}</span>
                          <span>·</span>
                          <span>{getToneLabel(project.tone)}</span>
                          <span>·</span>
                          <span>{new Date(project.created_at).toLocaleDateString('zh-CN')}</span>
                        </div>
                      </div>
                      <div className="flex items-center gap-2">
                        <ArrowRight className="w-5 h-5 text-blue-600 opacity-0 group-hover:opacity-100 transition-opacity" />
                        <button
                          onClick={(e) => {
                            e.stopPropagation()
                            handleDeleteProject(project.id)
                          }}
                          className="p-1 text-gray-400 hover:text-red-600 opacity-0 group-hover:opacity-100 transition-opacity"
                        >
                          <Trash2 className="w-4 h-4" />
                        </button>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}