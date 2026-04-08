/**
 * 项目初始化页面
 * v7 美化版：渐变背景、卡片动画、玻璃态效果
 */

import React, { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { Plus, FolderOpen, Globe, Loader, ArrowRight, Trash2, Sparkles } from 'lucide-react'
import { getProjects, createProject, deleteProject, type Project } from '@/api/projects'
import { AnimatedCard, AnimatedList, AnimatedListItem, FadeIn, GradientBackground } from '@/components/animations'

export default function ProjectSetup() {
  const navigate = useNavigate()

  const [projects, setProjects] = useState<Project[]>([])
  const [loading, setLoading] = useState(true)
  const [creating, setCreating] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const [newProjectName, setNewProjectName] = useState('')
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
        description: newProjectDescription
      })

      setProjects([...projects, project])
      setNewProjectName('')
      setNewProjectDescription('')

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

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center relative overflow-hidden">
        <GradientBackground colors={['#1e293b', '#0f172a', '#1e1b4b']} className="absolute inset-0" />
        <div className="relative z-10 text-center">
          <Loader className="w-12 h-12 text-blue-500 animate-spin mx-auto mb-4" />
          <p className="text-gray-400">加载中...</p>
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-screen relative overflow-hidden">
      {/* 背景渐变 */}
      <GradientBackground colors={['#0f172a', '#1e1b4b', '#0f172a']} className="fixed inset-0" animated />

      {/* 装饰元素 */}
      <div className="fixed top-20 left-20 w-64 h-64 bg-blue-500/10 rounded-full blur-3xl" />
      <div className="fixed bottom-20 right-20 w-96 h-96 bg-purple-500/10 rounded-full blur-3xl" />

      <div className="relative z-10 p-8">
        <div className="max-w-6xl mx-auto">
          {/* 页面标题 */}
          <FadeIn className="text-center mb-12">
            <div className="inline-flex items-center justify-center w-20 h-20 rounded-2xl bg-gradient-to-br from-blue-500 to-purple-600 mb-6 glow-primary">
              <Globe className="w-10 h-10 text-white" />
            </div>
            <h1 className="text-4xl font-bold gradient-text mb-3">项目初始化</h1>
            <p className="text-gray-400 text-lg">创建或选择一个项目，开始你的创作之旅</p>
          </FadeIn>

          {error && (
            <FadeIn className="mb-6">
              <div className="p-4 bg-red-900/30 border border-red-700 text-red-300 rounded-xl backdrop-blur-sm">
                {error}
              </div>
            </FadeIn>
          )}

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
            {/* 创建新项目 */}
            <AnimatedCard delay={0.2} className="glass-card">
              <div className="p-6">
                <div className="flex items-center gap-3 mb-6">
                  <div className="p-2 rounded-xl bg-green-500/20 glow-success">
                    <Plus className="w-6 h-6 text-green-400" />
                  </div>
                  <h2 className="text-xl font-bold text-white">创建新项目</h2>
                </div>

                <div className="space-y-4">
                  <div>
                    <label className="block text-sm font-medium text-gray-300 mb-2">
                      项目名称 <span className="text-red-400">*</span>
                    </label>
                    <input
                      type="text"
                      value={newProjectName}
                      onChange={(e) => setNewProjectName(e.target.value)}
                      className="w-full px-4 py-3 bg-gray-800/50 border border-gray-700 rounded-xl text-white placeholder-gray-500 focus:border-green-500 transition-all"
                      placeholder="例如：星辰之誓"
                    />
                  </div>

                  <div>
                    <label className="block text-sm font-medium text-gray-300 mb-2">
                      项目描述
                    </label>
                    <textarea
                      value={newProjectDescription}
                      onChange={(e) => setNewProjectDescription(e.target.value)}
                      className="w-full px-4 py-3 bg-gray-800/50 border border-gray-700 rounded-xl text-white placeholder-gray-500 focus:border-green-500 transition-all resize-none"
                      rows={3}
                      placeholder="简单描述你的小说设定..."
                    />
                  </div>

                  <button
                    onClick={handleCreateProject}
                    disabled={creating || !newProjectName.trim()}
                    className="w-full py-3 bg-gradient-to-r from-green-500 to-emerald-600 text-white font-medium rounded-xl hover:from-green-600 hover:to-emerald-700 disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2 transition-all hover:shadow-lg hover:shadow-green-500/25"
                  >
                    {creating ? (
                      <>
                        <Loader className="w-5 h-5 animate-spin" />
                        创建中...
                      </>
                    ) : (
                      <>
                        <Sparkles className="w-5 h-5" />
                        创建项目并开始设定
                      </>
                    )}
                  </button>
                </div>
              </div>
            </AnimatedCard>

            {/* 现有项目 */}
            <AnimatedCard delay={0.3} className="glass-card">
              <div className="p-6">
                <div className="flex items-center gap-3 mb-6">
                  <div className="p-2 rounded-xl bg-blue-500/20 glow-primary">
                    <FolderOpen className="w-6 h-6 text-blue-400" />
                  </div>
                  <h2 className="text-xl font-bold text-white">现有项目</h2>
                  <span className="ml-auto px-3 py-1 text-sm bg-gray-800 text-gray-300 rounded-full">
                    {projects.length} 个项目
                  </span>
                </div>

                {projects.length === 0 ? (
                  <div className="text-center py-16">
                    <FolderOpen className="w-16 h-16 text-gray-600 mx-auto mb-4" />
                    <p className="text-gray-400 text-lg">暂无项目</p>
                    <p className="text-sm text-gray-500 mt-2">创建一个新项目开始</p>
                  </div>
                ) : (
                  <AnimatedList className="space-y-3 max-h-[500px] overflow-y-auto pr-2">
                    {projects.map((project, index) => (
                      <AnimatedListItem key={project.id}>
                        <div
                          className="border border-gray-700 rounded-xl p-4 hover:border-blue-500 hover:bg-gray-800/50 transition-all cursor-pointer group backdrop-blur-sm"
                          onClick={() => handleSelectProject(project)}
                          style={{ transitionDelay: `${index * 0.05}s` }}
                        >
                          <div className="flex items-start justify-between">
                            <div className="flex-1">
                              <div className="font-medium text-white text-lg">{project.name}</div>
                              <div className="text-sm text-gray-400 mt-1">
                                {project.description || '无描述'}
                              </div>
                              <div className="flex items-center gap-3 mt-3 text-xs text-gray-500">
                                <span>创建于 {new Date(project.created_at).toLocaleDateString('zh-CN')}</span>
                              </div>
                            </div>
                            <div className="flex items-center gap-2">
                              <div className="p-2 rounded-lg bg-blue-500/20 text-blue-400 opacity-0 group-hover:opacity-100 transition-opacity">
                                <ArrowRight className="w-5 h-5" />
                              </div>
                              <button
                                onClick={(e) => {
                                  e.stopPropagation()
                                  handleDeleteProject(project.id)
                                }}
                                className="p-2 text-gray-500 hover:text-red-400 hover:bg-red-500/10 rounded-lg opacity-0 group-hover:opacity-100 transition-all"
                              >
                                <Trash2 className="w-5 h-5" />
                              </button>
                            </div>
                          </div>
                        </div>
                      </AnimatedListItem>
                    ))}
                  </AnimatedList>
                )}
              </div>
            </AnimatedCard>
          </div>
        </div>
      </div>
    </div>
  )
}
