/**
 * Bootstrap 流程页面
 * v4 核心功能：小说设定 Agent、文本大纲输入、自动项目初始化
 */

import React, { useState, useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { Bot, FileText, Upload, CheckCircle, AlertCircle, Loader, MessageSquare, Globe } from 'lucide-react'
import { startBootstrap, getBootstrapSession, sendBootstrapMessage, uploadOutline, confirmSeed, runBootstrap, getBootstrapStatus, type BootstrapSession, type SeedData } from '@/api/bootstrap'
import { getProjects, createProject, type Project } from '@/api/projects'
import SeedConfirmDialog from '@/components/bootstrap/SeedConfirmDialog'

type BootstrapStage = 'project_select' | 'setting_agent' | 'outline_input' | 'seed_confirmation' | 'running' | 'completed'

export default function BootstrapPage() {
  const { sessionId } = useParams<{ sessionId?: string }>()
  const navigate = useNavigate()

  const [projects, setProjects] = useState<Project[]>([])
  const [selectedProjectId, setSelectedProjectId] = useState('')
  const [newProjectName, setNewProjectName] = useState('')
  const [creatingProject, setCreatingProject] = useState(false)

  const [session, setSession] = useState<BootstrapSession | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const [stage, setStage] = useState<BootstrapStage>('project_select')
  const [userMessage, setUserMessage] = useState('')
  const [outlineContent, setOutlineContent] = useState('')
  const [outlineFile, setOutlineFile] = useState<File | null>(null)
  const [outlineSourceType, setOutlineSourceType] = useState<'pasted_text' | 'file_txt' | 'file_md'>('pasted_text')

  const [showSeedConfirm, setShowSeedConfirm] = useState(false)
  const [seedData, setSeedData] = useState<SeedData | null>(null)

  // 加载项目列表
  useEffect(() => {
    loadProjects()
  }, [])

  // 如果有 sessionId，加载会话
  useEffect(() => {
    if (sessionId) {
      loadSession(sessionId)
    }
  }, [sessionId])

  const loadProjects = async () => {
    try {
      const result = await getProjects()
      setProjects(result)
    } catch (err) {
      console.error('Failed to load projects:', err)
      setError('加载项目列表失败')
    }
  }

  const loadSession = async (id: string) => {
    setLoading(true)
    try {
      const sessionData = await getBootstrapSession(id)
      setSession(sessionData)
      updateStageFromSession(sessionData)
    } catch (err) {
      console.error('Failed to load session:', err)
      setError('加载会话失败')
    } finally {
      setLoading(false)
    }
  }

  const updateStageFromSession = (sessionData: BootstrapSession) => {
    const status = sessionData.status
    const currentStage = sessionData.current_stage

    if (status === 'completed') {
      setStage('completed')
    } else if (status === 'running') {
      setStage('running')
    } else if (currentStage === 'seed_confirmation') {
      setStage('seed_confirmation')
      setSeedData(sessionData.extracted_seed as SeedData)
    } else if (currentStage === 'outline_input') {
      setStage('outline_input')
    } else {
      setStage('setting_agent')
    }
  }

  const handleCreateProject = async () => {
    if (!newProjectName.trim()) {
      setError('请输入项目名称')
      return
    }

    setCreatingProject(true)
    try {
      const project = await createProject({
        name: newProjectName,
        description: '',
        world_type: 'fantasy',
        tone: 'serious'
      })
      setProjects([...projects, project])
      setSelectedProjectId(project.id)
      setNewProjectName('')
    } catch (err) {
      console.error('Failed to create project:', err)
      setError('创建项目失败')
    } finally {
      setCreatingProject(false)
    }
  }

  const handleStartBootstrap = async () => {
    if (!selectedProjectId) {
      setError('请选择或创建一个项目')
      return
    }

    setLoading(true)
    try {
      const result = await startBootstrap(selectedProjectId)
      const newSession = result.session
      setSession(newSession)
      setStage('setting_agent')
      navigate(`/bootstrap/${newSession.id}`)
    } catch (err) {
      console.error('Failed to start bootstrap:', err)
      setError('启动引导流程失败')
    } finally {
      setLoading(false)
    }
  }

  const handleSendMessage = async () => {
    if (!session || !userMessage.trim()) return

    setLoading(true)
    try {
      await sendBootstrapMessage(session.id, userMessage)
      const updatedSession = await getBootstrapSession(session.id)
      setSession(updatedSession)
      setUserMessage('')
    } catch (err) {
      console.error('Failed to send message:', err)
      setError('发送消息失败')
    } finally {
      setLoading(false)
    }
  }

  const handleUploadOutline = async () => {
    if (!session) return

    let content = outlineContent
    let sourceType = outlineSourceType

    // 处理文件上传
    if (outlineFile) {
      try {
        content = await readFileAsText(outlineFile)
        sourceType = outlineFile.name.endsWith('.md') ? 'file_md' : 'file_txt'
      } catch (err) {
        setError('读取文件失败')
        return
      }
    }

    if (!content.trim()) {
      setError('请输入大纲内容或选择文件')
      return
    }

    setLoading(true)
    try {
      await uploadOutline(session.id, content, sourceType)
      const updatedSession = await getBootstrapSession(session.id)
      setSession(updatedSession)
      setOutlineContent('')
      setOutlineFile(null)
    } catch (err) {
      console.error('Failed to upload outline:', err)
      setError('上传大纲失败')
    } finally {
      setLoading(false)
    }
  }

  const readFileAsText = (file: File): Promise<string> => {
    return new Promise((resolve, reject) => {
      const reader = new FileReader()
      reader.onload = (e) => resolve(e.target?.result as string)
      reader.onerror = (e) => reject(e)
      reader.readAsText(file)
    })
  }

  const handleConfirmSeed = async (confirmedSeed: SeedData) => {
    if (!session) return

    setLoading(true)
    try {
      await confirmSeed(session.id, confirmedSeed)
      const updatedSession = await getBootstrapSession(session.id)
      setSession(updatedSession)
      setShowSeedConfirm(false)
      setStage('running')

      // 自动运行 bootstrap
      await runBootstrap(session.id)
    } catch (err) {
      console.error('Failed to confirm seed:', err)
      setError('确认种子数据失败')
    } finally {
      setLoading(false)
    }
  }

  const handleRunBootstrap = async () => {
    if (!session) return

    setLoading(true)
    try {
      await runBootstrap(session.id)
      setStage('running')
    } catch (err) {
      console.error('Failed to run bootstrap:', err)
      setError('运行引导失败')
    } finally {
      setLoading(false)
    }
  }

  const renderProjectSelect = () => (
    <div className="max-w-4xl mx-auto">
      <div className="text-center mb-10">
        <Globe className="w-16 h-16 text-blue-600 mx-auto mb-4" />
        <h1 className="text-3xl font-bold text-gray-800">项目初始化</h1>
        <p className="text-gray-600 mt-2">选择现有项目或创建新项目开始引导流程</p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
        {/* 选择现有项目 */}
        <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
          <h2 className="text-xl font-bold text-gray-800 mb-4">选择现有项目</h2>
          {projects.length === 0 ? (
            <div className="text-center py-8 text-gray-500">
              <FileText className="w-12 h-12 mx-auto mb-3 text-gray-300" />
              <p>暂无项目</p>
            </div>
          ) : (
            <div className="space-y-3">
              {projects.map((project) => (
                <div
                  key={project.id}
                  className={`p-4 border rounded-lg cursor-pointer transition-all ${
                    selectedProjectId === project.id
                      ? 'border-blue-500 bg-blue-50'
                      : 'border-gray-200 hover:border-gray-300'
                  }`}
                  onClick={() => setSelectedProjectId(project.id)}
                >
                  <div className="font-medium text-gray-800">{project.name}</div>
                  <div className="text-sm text-gray-600 mt-1">{project.description || '无描述'}</div>
                  <div className="text-xs text-gray-500 mt-2">
                    {new Date(project.created_at).toLocaleDateString('zh-CN')}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* 创建新项目 */}
        <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
          <h2 className="text-xl font-bold text-gray-800 mb-4">创建新项目</h2>
          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                项目名称
              </label>
              <input
                type="text"
                value={newProjectName}
                onChange={(e) => setNewProjectName(e.target.value)}
                className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                placeholder="例如：星辰之誓"
              />
            </div>
            <button
              onClick={handleCreateProject}
              disabled={creatingProject || !newProjectName.trim()}
              className="w-full py-3 bg-blue-600 text-white font-medium rounded-lg hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {creatingProject ? '创建中...' : '创建项目'}
            </button>
          </div>
        </div>
      </div>

      <div className="mt-8 text-center">
        <button
          onClick={handleStartBootstrap}
          disabled={!selectedProjectId || loading}
          className="px-8 py-3 bg-green-600 text-white font-medium rounded-lg hover:bg-green-700 disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {loading ? '启动中...' : '开始引导流程'}
        </button>
      </div>
    </div>
  )

  const renderSettingAgent = () => (
    <div className="max-w-4xl mx-auto">
      <div className="flex items-center gap-3 mb-6">
        <Bot className="w-8 h-8 text-blue-600" />
        <h1 className="text-2xl font-bold text-gray-800">小说设定 Agent</h1>
      </div>

      <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6 mb-6">
        <div className="flex items-center gap-3 mb-4">
          <MessageSquare className="w-5 h-5 text-gray-500" />
          <h2 className="font-medium text-gray-800">与设定 Agent 对话</h2>
        </div>

        <div className="mb-6 p-4 bg-gray-50 rounded-lg border border-gray-200">
          <div className="text-sm text-gray-600 mb-2">Agent 提示：</div>
          <div className="text-gray-800">
            请描述你的小说设定：世界观、主要角色、故事主线、风格基调等。
            我会通过多轮对话帮助你完善设定，并提取结构化的项目种子。
          </div>
        </div>

        {/* 对话历史 */}
        {session?.setting_agent_history && session.setting_agent_history.length > 0 && (
          <div className="mb-6 space-y-4">
            {session.setting_agent_history.map((msg, idx) => (
              <div
                key={idx}
                className={`p-4 rounded-lg ${
                  msg.role === 'user'
                    ? 'bg-blue-50 border border-blue-100 ml-8'
                    : 'bg-gray-50 border border-gray-200 mr-8'
                }`}
              >
                <div className="font-medium text-sm text-gray-500 mb-1">
                  {msg.role === 'user' ? '你' : '设定 Agent'}
                </div>
                <div className="text-gray-800">{msg.content}</div>
              </div>
            ))}
          </div>
        )}

        {/* 输入框 */}
        <div className="flex gap-3">
          <textarea
            value={userMessage}
            onChange={(e) => setUserMessage(e.target.value)}
            placeholder="输入你的设定描述..."
            className="flex-1 px-4 py-3 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 resize-none"
            rows={3}
          />
          <button
            onClick={handleSendMessage}
            disabled={!userMessage.trim() || loading}
            className="self-end px-6 py-3 bg-blue-600 text-white font-medium rounded-lg hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            发送
          </button>
        </div>
      </div>

      <div className="text-center">
        <button
          onClick={() => setStage('outline_input')}
          className="px-6 py-3 border border-gray-300 text-gray-700 font-medium rounded-lg hover:bg-gray-50"
        >
          跳过，直接上传大纲 →
        </button>
      </div>
    </div>
  )

  const renderOutlineInput = () => (
    <div className="max-w-4xl mx-auto">
      <div className="flex items-center gap-3 mb-6">
        <FileText className="w-8 h-8 text-blue-600" />
        <h1 className="text-2xl font-bold text-gray-800">文本大纲输入</h1>
      </div>

      <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6 mb-6">
        <div className="mb-6">
          <div className="flex gap-4 mb-4">
            <button
              onClick={() => setOutlineSourceType('pasted_text')}
              className={`px-4 py-2 rounded-lg border ${
                outlineSourceType === 'pasted_text'
                  ? 'border-blue-500 bg-blue-50 text-blue-700'
                  : 'border-gray-300 text-gray-700 hover:bg-gray-50'
              }`}
            >
              粘贴文本
            </button>
            <button
              onClick={() => setOutlineSourceType('file_txt')}
              className={`px-4 py-2 rounded-lg border ${
                outlineSourceType === 'file_txt'
                  ? 'border-blue-500 bg-blue-50 text-blue-700'
                  : 'border-gray-300 text-gray-700 hover:bg-gray-50'
              }`}
            >
              上传 TXT 文件
            </button>
            <button
              onClick={() => setOutlineSourceType('file_md')}
              className={`px-4 py-2 rounded-lg border ${
                outlineSourceType === 'file_md'
                  ? 'border-blue-500 bg-blue-50 text-blue-700'
                  : 'border-gray-300 text-gray-700 hover:bg-gray-50'
              }`}
            >
              上传 MD 文件
            </button>
          </div>

          {outlineSourceType === 'pasted_text' ? (
            <textarea
              value={outlineContent}
              onChange={(e) => setOutlineContent(e.target.value)}
              placeholder="粘贴你的小说大纲文本..."
              className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 resize-none"
              rows={10}
            />
          ) : (
            <div className="border-2 border-dashed border-gray-300 rounded-lg p-8 text-center">
              <Upload className="w-12 h-12 text-gray-400 mx-auto mb-3" />
              <div className="text-gray-600 mb-4">
                上传 {outlineSourceType === 'file_txt' ? 'TXT' : 'MD'} 文件
              </div>
              <input
                type="file"
                accept={outlineSourceType === 'file_txt' ? '.txt' : '.md'}
                onChange={(e) => setOutlineFile(e.target.files?.[0] || null)}
                className="block mx-auto"
              />
              {outlineFile && (
                <div className="mt-4 text-sm text-gray-700">
                  已选择：{outlineFile.name} ({Math.round(outlineFile.size / 1024)} KB)
                </div>
              )}
            </div>
          )}
        </div>

        <div className="flex justify-between">
          <button
            onClick={() => setStage('setting_agent')}
            className="px-6 py-3 border border-gray-300 text-gray-700 font-medium rounded-lg hover:bg-gray-50"
          >
            ← 返回设定对话
          </button>
          <button
            onClick={handleUploadOutline}
            disabled={(!outlineContent.trim() && !outlineFile) || loading}
            className="px-8 py-3 bg-blue-600 text-white font-medium rounded-lg hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {loading ? '处理中...' : '上传大纲并继续'}
          </button>
        </div>
      </div>
    </div>
  )

  const renderSeedConfirmation = () => (
    <div className="max-w-4xl mx-auto">
      <div className="flex items-center gap-3 mb-6">
        <CheckCircle className="w-8 h-8 text-green-600" />
        <h1 className="text-2xl font-bold text-gray-800">结构化种子确认</h1>
      </div>

      <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6 mb-6">
        <div className="mb-6">
          <div className="text-gray-600 mb-4">
            系统已从你的设定和大纲中提取出以下结构化种子数据。
            请检查并确认，如有需要可以修改。
          </div>

          {seedData && (
            <div className="p-4 bg-gray-50 rounded-lg border border-gray-200">
              <pre className="text-sm whitespace-pre-wrap font-mono">
                {JSON.stringify(seedData, null, 2)}
              </pre>
            </div>
          )}
        </div>

        <div className="flex justify-center gap-4">
          <button
            onClick={() => setShowSeedConfirm(true)}
            className="px-8 py-3 bg-green-600 text-white font-medium rounded-lg hover:bg-green-700"
          >
            确认种子数据
          </button>
          <button
            onClick={() => setStage('outline_input')}
            className="px-6 py-3 border border-gray-300 text-gray-700 font-medium rounded-lg hover:bg-gray-50"
          >
            重新上传大纲
          </button>
        </div>
      </div>
    </div>
  )

  const renderRunning = () => (
    <div className="max-w-2xl mx-auto text-center py-12">
      <Loader className="w-16 h-16 text-blue-600 mx-auto mb-6 animate-spin" />
      <h1 className="text-2xl font-bold text-gray-800 mb-4">项目初始化进行中</h1>
      <p className="text-gray-600 mb-8">
        系统正在根据种子数据创建世界、角色、Agent 等基础组件。
        这个过程可能需要几分钟时间。
      </p>
      <div className="inline-block px-6 py-3 bg-blue-100 text-blue-800 rounded-lg font-medium">
        进度：{session?.progress || 0}%
      </div>
    </div>
  )

  const renderCompleted = () => (
    <div className="max-w-2xl mx-auto text-center py-12">
      <CheckCircle className="w-16 h-16 text-green-600 mx-auto mb-6" />
      <h1 className="text-2xl font-bold text-gray-800 mb-4">项目初始化完成！</h1>
      <p className="text-gray-600 mb-8">
        你的项目已经成功初始化。现在可以进入 Director 模式开始创作，
        或进入世界观测页面查看模拟状态。
      </p>
      <div className="flex justify-center gap-4">
        <button
          onClick={() => navigate('/director')}
          className="px-8 py-3 bg-blue-600 text-white font-medium rounded-lg hover:bg-blue-700"
        >
          进入 Director 模式
        </button>
        <button
          onClick={() => navigate('/world-view')}
          className="px-8 py-3 border border-gray-300 text-gray-700 font-medium rounded-lg hover:bg-gray-50"
        >
          进入世界观测
        </button>
      </div>
    </div>
  )

  if (loading && !session) {
    return (
      <div className="h-screen flex items-center justify-center">
        <Loader className="w-8 h-8 text-blue-600 animate-spin" />
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-gray-50 p-6">
      {error && (
        <div className="max-w-4xl mx-auto mb-6">
          <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg flex items-center gap-2">
            <AlertCircle className="w-5 h-5" />
            {error}
          </div>
        </div>
      )}

      {stage === 'project_select' && renderProjectSelect()}
      {stage === 'setting_agent' && renderSettingAgent()}
      {stage === 'outline_input' && renderOutlineInput()}
      {stage === 'seed_confirmation' && renderSeedConfirmation()}
      {stage === 'running' && renderRunning()}
      {stage === 'completed' && renderCompleted()}

      {showSeedConfirm && seedData && (
        <SeedConfirmDialog
          seedData={seedData}
          onConfirm={handleConfirmSeed}
          onCancel={() => setShowSeedConfirm(false)}
        />
      )}
    </div>
  )
}