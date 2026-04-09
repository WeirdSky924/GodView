import { useEffect, useMemo, useState } from 'react'
import { Card, Button, Input, TextArea, Modal } from '@/components/ui'
import PageLayout from '@/components/PageLayout'
import { useDynamicWebSocket } from '@/hooks/useWebSocket'
import { getDirectorState, getSnapshotTree, getWorkflowGraph } from '@/api/director'
import { getCharacters } from '@/api/characters'
import { Play, Pause, RotateCcw, Zap, Target, BookOpen, MessageSquare, Map, GitBranch, RefreshCcw, Workflow, Mic, PenLine, FolderOpen, UserPlus, UserMinus, Users, ChevronDown, ChevronUp, Settings, Sparkles, FileText } from 'lucide-react'
import { useProject } from '@/contexts/ProjectContext'
import { useTheme } from '@/contexts/ThemeContext'
import { motion, AnimatePresence } from 'framer-motion'

interface AgentStatus {
  name: string
  status: 'idle' | 'working' | 'completed' | 'error'
  progress?: number
  message?: string
}

interface SnapshotNode {
  id: string
  name?: string
  snapshot_type?: string
  parent_snapshot_id?: string | null
  is_branch?: boolean
  branch_reason?: string | null
  created_at?: string
  children?: SnapshotNode[]
}

interface VoiceContext {
  used_qdrant?: boolean
  retrieved_samples?: string[]
  retrieved_count?: number
}

interface VoiceReview {
  checked?: boolean
  is_ooc?: boolean
  confidence?: number
  issues?: string[]
  suggestion?: string
  reference_samples?: string[]
}

interface RewriteResult {
  applied?: boolean
  changes_made?: string[]
  original_dialogue?: string
  original_content?: string
  target_character_id?: string
  target_character_name?: string
}

interface DialoguePanelState {
  speaker_id?: string
  dialogue?: string
  action?: string
  emotion?: string
  voice_context?: VoiceContext
  voice_review?: VoiceReview
  rewrite_result?: RewriteResult
}

interface NarrativeVoiceReviewEntry {
  character_id?: string
  character_name?: string
  voice_context?: VoiceContext
  voice_review?: VoiceReview
}

interface NarrativeVoiceReview {
  checked?: boolean
  has_ooc?: boolean
  reason?: string
  results?: NarrativeVoiceReviewEntry[]
}

interface NarrativePanelState {
  content?: string
  word_count?: number
  voice_review?: NarrativeVoiceReview
  rewrite_result?: RewriteResult
}

const defaultAgents: AgentStatus[] = [
  { name: 'Summarizer', status: 'idle', message: '剧情总结员', progress: 0 },
  { name: 'Master Plotter', status: 'idle', message: '总编剧', progress: 0 },
  { name: 'Hook Manager', status: 'idle', message: '伏笔管理员', progress: 0 },
  { name: 'Writer', status: 'idle', message: '内容执行官', progress: 0 },
  { name: 'Evaluator', status: 'idle', message: '剧情评估员', progress: 0 },
  { name: 'Character Agent', status: 'idle', message: '角色演绎', progress: 0 },
  { name: 'ProcGen', status: 'idle', message: '世界生成', progress: 0 },
]

function splitMultiline(value: string) {
  return value
    .split(/[，,\n]/)
    .map((item) => item.trim())
    .filter(Boolean)
}

function parseCharacterMoods(value: string) {
  return value
    .split('\n')
    .map((line) => line.trim())
    .filter(Boolean)
    .reduce<Record<string, string>>((acc, line) => {
      const [name, ...rest] = line.split(':')
      const mood = rest.join(':').trim()
      if (name?.trim() && mood) {
        acc[name.trim()] = mood
      }
      return acc
    }, {})
}

export default function Director() {
  const { currentProject } = useProject()
  const { theme } = useTheme()
  const isDark = theme === 'dark'

  const [sessionId, setSessionId] = useState<string>('')
  const [isGenerating, setIsGenerating] = useState(false)
  const [selectedAgent, setSelectedAgent] = useState<string>('')
  const [agentCommand, setAgentCommand] = useState('')
  const [logs, setLogs] = useState<string[]>([])
  const [showCommandModal, setShowCommandModal] = useState(false)
  const [agents, setAgents] = useState<AgentStatus[]>(defaultAgents)
  const [runtimeState, setRuntimeState] = useState<Record<string, any> | null>(null)
  const [snapshotTree, setSnapshotTree] = useState<SnapshotNode[]>([])
  const [workflowGraph, setWorkflowGraph] = useState<{ nodes: Array<{ id: string; label: string }>; edges: Array<{ source: string; target: string }> } | null>(null)
  const [regionPrompt, setRegionPrompt] = useState('向未知区域探索')
  const [rollbackSnapshotId, setRollbackSnapshotId] = useState('')
  const [dialoguePanel, setDialoguePanel] = useState<DialoguePanelState | null>(null)
  const [narrativePanel, setNarrativePanel] = useState<NarrativePanelState | null>(null)
  const [availableCharacters, setAvailableCharacters] = useState<Array<{ id: string; name: string }>>([])
  const [dialogueForm, setDialogueForm] = useState({
    speakerId: 'narrator',
    context: '当前场景推进中',
    presentCharacters: '',
    intents: '推进剧情',
    environment: '',
    characterMoods: '',
  })
  const [showAddCharacterModal, setShowAddCharacterModal] = useState(false)
  const [newCharacterForm, setNewCharacterForm] = useState({
    name: '',
    description: '',
    role: 'supporting',
    background_story: '',
    speech_pattern: '',
  })
  const [showAutoWriteModal, setShowAutoWriteModal] = useState(false)
  const [autoWriteForm, setAutoWriteForm] = useState({
    chapter_title: '',
    chapter_goal: '',
    target_word_count: 2000,
    style_reference: '',
  })
  const [autoWriteResult, setAutoWriteResult] = useState<{
    chapter_id?: string
    title?: string
    content?: string
    word_count?: number
  } | null>(null)
  const [showAutoModeModal, setShowAutoModeModal] = useState(false)
  const [autoModeForm, setAutoModeForm] = useState({
    initial_plot: '',
    chapter_count: 3,
    words_per_chapter: 2000,
    style_reference: '',
  })
  const [autoModeRunning, setAutoModeRunning] = useState(false)
  const [autoModeChapters, setAutoModeChapters] = useState<Array<{
    chapter_num: number
    title: string
    word_count: number
    content: string
  }>>([])

  // 高级设置折叠状态
  const [showAdvancedControls, setShowAdvancedControls] = useState(false)
  const [showLogs, setShowLogs] = useState(true)

  const addLog = (message: string) => {
    const timestamp = new Date().toLocaleTimeString()
    setLogs((prev) => [`[${timestamp}] ${message}`, ...prev.slice(0, 199)])
  }

  const wsPath = useMemo(
    () => (sessionId.trim() ? `/api/ws/connect/${sessionId.trim()}` : ''),
    [sessionId]
  )

  const updateAgent = (name: string, patch: Partial<AgentStatus>) => {
    setAgents((prev) => prev.map((a) => (a.name === name ? { ...a, ...patch } : a)))
  }

  const loadRuntimePanels = async () => {
    if (!sessionId.trim()) return
    try {
      const [stateRes, workflowRes] = await Promise.all([
        getDirectorState(sessionId.trim()),
        getWorkflowGraph(sessionId.trim()),
      ])
      setRuntimeState(stateRes.data)
      setWorkflowGraph(workflowRes)
      if (stateRes.data?.world_id) {
        const treeRes = await getSnapshotTree(stateRes.data.world_id)
        setSnapshotTree(treeRes.data || [])
      } else {
        setSnapshotTree([])
      }
    } catch (error) {
      console.error('Failed to load runtime panels:', error)
    }
  }

  useEffect(() => {
    if (sessionId.trim()) {
      loadRuntimePanels()
    }
  }, [sessionId])

  useEffect(() => {
    const loadCharacters = async () => {
      if (!currentProject) {
        setAvailableCharacters([])
        return
      }
      try {
        const chars = await getCharacters(currentProject.id)
        setAvailableCharacters(chars.map((c: any) => ({ id: c.id, name: c.name })))
      } catch (error) {
        console.error('Failed to load characters:', error)
        setAvailableCharacters([])
      }
    }
    loadCharacters()
  }, [currentProject])

  const { status: wsStatus, send } = useDynamicWebSocket(wsPath, {
    onOpen: () => addLog('WebSocket 已连接'),
    onClose: () => addLog('WebSocket 已关闭'),
    onError: () => addLog('WebSocket 连接异常'),
    onMessage: (data) => {
      switch (data.type) {
        case 'log':
          addLog(data.message)
          break
        case 'agent_status':
          updateAgent(data.agent, {
            status: data.status,
            message: data.message,
            progress: data.progress,
          })
          break
        case 'session_started':
          addLog(`会话已启动: ${data.data?.session_id || sessionId}`)
          loadRuntimePanels()
          break
        case 'session_stopped':
          addLog('会话已停止')
          loadRuntimePanels()
          break
        case 'plot_advanced':
          addLog(`剧情推进: ${data.data?.reason || '已完成'}`)
          loadRuntimePanels()
          break
        case 'hooks_managed':
          addLog('伏笔管理完成')
          loadRuntimePanels()
          break
        case 'dialogue_generated':
          addLog(`对话生成完成`)
          setDialoguePanel(data.data || null)
          loadRuntimePanels()
          break
        case 'narrative_generated':
          addLog(`叙事生成完成: ${data.data?.word_count || 0} 字`)
          setNarrativePanel(data.data || null)
          loadRuntimePanels()
          break
        case 'workflow_cycle_result':
          addLog('工作流执行完成')
          if (data.data?.dialogue) {
            setDialoguePanel(data.data.dialogue)
          }
          if (data.data?.narrative) {
            setNarrativePanel(data.data.narrative)
          }
          loadRuntimePanels()
          break
        case 'chapter_end_result':
          addLog(`章节评估: ${data.data?.reason || '完成'}${data.snapshot_id ? ` / 快照: ${data.snapshot_id}` : ''}`)
          loadRuntimePanels()
          break
        case 'region_generated':
          addLog(`新区域已生成: ${data.data?.region_name || data.data?.name || ''}`)
          loadRuntimePanels()
          break
        case 'snapshot_created':
          addLog(`快照已创建: ${data.data?.id || ''}`)
          loadRuntimePanels()
          break
        case 'snapshot_rolled_back':
          addLog(`已回档到快照: ${data.data?.snapshot_id || data.data?.id || ''}`)
          loadRuntimePanels()
          break
        case 'agent_command_result':
          addLog(`${data.data?.agent}: ${data.data?.result}`)
          break
        case 'character_added':
          addLog(`角色已添加: ${data.data?.name || data.data?.character_id}`)
          if (currentProject) {
            getCharacters(currentProject.id).then((chars: any[]) => {
              setAvailableCharacters(chars.map((c) => ({ id: c.id, name: c.name })))
            })
          }
          break
        case 'character_removed':
          addLog(`角色已移除: ${data.data?.character_id}`)
          if (currentProject) {
            getCharacters(currentProject.id).then((chars: any[]) => {
              setAvailableCharacters(chars.map((c) => ({ id: c.id, name: c.name })))
            })
          }
          break
        case 'characters_list':
          addLog(`角色列表: ${data.data?.count || 0} 个角色`)
          break
        case 'auto_write_chapter_result':
          if (data.status === 'success') {
            addLog(`章节自动写作完成: ${data.data?.title} (${data.data?.word_count} 字)`)
            setAutoWriteResult(data.data)
          } else {
            addLog(`章节自动写作失败: ${data.error}`)
          }
          loadRuntimePanels()
          break
        case 'auto_mode_chapter_start':
          addLog(`📖 开始写作第 ${data.chapter_num} 章: ${data.title}`)
          break
        case 'auto_mode_chapter_completed':
          addLog(`✅ 第 ${data.chapter_num} 章完成: ${data.title} (${data.word_count} 字)`)
          setAutoModeChapters(prev => [...prev, {
            chapter_num: data.chapter_num,
            title: data.title,
            word_count: data.word_count,
            content: data.content,
          }])
          break
        case 'auto_mode_completed':
          setAutoModeRunning(false)
          addLog(`🎉 全自动创作完成！共 ${data.data?.total_chapters} 章，${data.data?.total_words} 字`)
          loadRuntimePanels()
          break
        case 'auto_mode_error':
          setAutoModeRunning(false)
          addLog(`❌ 自动模式错误: ${data.error}`)
          break
        case 'error':
          addLog(`错误: ${data.message}`)
          break
        default:
          addLog(`收到消息: ${JSON.stringify(data)}`)
      }
    },
  })

  const startSession = () => {
    if (!sessionId.trim()) {
      addLog('请输入会话 ID')
      return
    }
    if (!currentProject) {
      addLog('请先选择一个项目')
      return
    }
    setIsGenerating(true)
    const worldId = currentProject.world_id || `project-${currentProject.id}`
    const characterIds = availableCharacters.map((c) => c.id)
    addLog(`启动会话: 项目 ${currentProject.name}`)
    send({ type: 'start_session', world_id: worldId, character_ids: characterIds })
  }

  const stopSession = () => {
    setIsGenerating(false)
    send({ type: 'stop_session' })
  }

  const resetAll = () => {
    setAgents(defaultAgents)
    setLogs([])
    setRuntimeState(null)
    setSnapshotTree([])
    setWorkflowGraph(null)
    setDialoguePanel(null)
    setNarrativePanel(null)
    setAutoWriteResult(null)
    setAutoModeChapters([])
  }

  const executeAgentCommand = () => {
    if (!selectedAgent || !agentCommand.trim()) {
      addLog('请选择 Agent 并输入命令')
      return
    }
    send({
      type: 'agent_command',
      agent: selectedAgent,
      command: agentCommand,
    })
    setAgentCommand('')
    setShowCommandModal(false)
  }

  const buildDialoguePayload = () => ({
    speaker_id: dialogueForm.speakerId.trim() || 'narrator',
    context: dialogueForm.context.trim() || '当前场景推进中',
    present_characters: splitMultiline(dialogueForm.presentCharacters),
    intents: splitMultiline(dialogueForm.intents),
    environment: dialogueForm.environment.trim(),
    character_moods: parseCharacterMoods(dialogueForm.characterMoods),
  })

  const triggerDialogue = () => {
    send({
      type: 'generate_dialogue',
      ...buildDialoguePayload(),
    })
  }

  const triggerNarrative = () => {
    const payload = buildDialoguePayload()
    send({
      type: 'generate_narrative',
      intents: payload.intents,
      environment: payload.environment,
      character_moods: payload.character_moods,
    })
  }

  const triggerWorkflowCycle = () => {
    send({
      type: 'workflow_cycle',
      ...buildDialoguePayload(),
    })
  }

  const handleAddCharacter = () => {
    if (!newCharacterForm.name.trim()) {
      addLog('请输入角色名称')
      return
    }
    if (!currentProject) {
      addLog('请先选择项目')
      return
    }
    send({
      type: 'add_character',
      character_data: {
        name: newCharacterForm.name.trim(),
        description: newCharacterForm.description,
        role: newCharacterForm.role,
        background_story: newCharacterForm.background_story,
        speech_pattern: newCharacterForm.speech_pattern,
        project_id: currentProject.id,
      },
    })
    setNewCharacterForm({
      name: '',
      description: '',
      role: 'supporting',
      background_story: '',
      speech_pattern: '',
    })
    setShowAddCharacterModal(false)
  }

  const handleRemoveCharacter = (characterId: string) => {
    if (!confirm('确定要移除这个角色吗？')) return
    send({
      type: 'remove_character',
      character_id: characterId,
    })
  }

  const handleAutoWriteChapter = () => {
    if (!autoWriteForm.chapter_title.trim()) {
      addLog('请输入章节标题')
      return
    }
    if (!autoWriteForm.chapter_goal.trim()) {
      addLog('请输入章节目标/大纲')
      return
    }
    send({
      type: 'auto_write_chapter',
      chapter_title: autoWriteForm.chapter_title.trim(),
      chapter_goal: autoWriteForm.chapter_goal.trim(),
      target_word_count: autoWriteForm.target_word_count,
      style_reference: autoWriteForm.style_reference.trim(),
    })
    setShowAutoWriteModal(false)
  }

  const handleStartAutoMode = () => {
    if (!autoModeForm.initial_plot.trim()) {
      addLog('请输入初始剧情设定')
      return
    }
    setAutoModeRunning(true)
    setAutoModeChapters([])
    send({
      type: 'start_auto_mode',
      initial_plot: autoModeForm.initial_plot.trim(),
      chapter_count: autoModeForm.chapter_count,
      words_per_chapter: autoModeForm.words_per_chapter,
      style_reference: autoModeForm.style_reference.trim(),
    })
    setShowAutoModeModal(false)
  }

  const handleStopAutoMode = () => {
    send({ type: 'stop_auto_mode' })
    setAutoModeRunning(false)
  }

  const getAgentColor = (status: AgentStatus['status']) => {
    switch (status) {
      case 'idle':
        return isDark ? 'bg-gray-600' : 'bg-gray-300'
      case 'working':
        return 'bg-blue-500 animate-pulse'
      case 'completed':
        return 'bg-green-500'
      case 'error':
        return 'bg-red-500'
      default:
        return isDark ? 'bg-gray-600' : 'bg-gray-300'
    }
  }

  const getWorkingAgentName = () => agents.find(a => a.status === 'working')?.message || null

  const renderSnapshotTree = (nodes: SnapshotNode[], depth = 0): React.ReactNode => {
    return nodes.map((node) => (
      <div key={node.id} className="space-y-2">
        <div className={`rounded-lg border p-2 ${isDark ? 'border-gray-700' : 'border-gray-200'}`} style={{ marginLeft: `${depth * 12}px` }}>
          <div className="flex items-center justify-between gap-2">
            <div>
              <p className={`text-xs font-medium ${isDark ? 'text-white' : 'text-gray-800'}`}>{node.name || node.id}</p>
            </div>
            <Button
              variant="secondary"
              size="sm"
              onClick={() => setRollbackSnapshotId(node.id)}
              disabled={!isGenerating || wsStatus !== 'connected'}
              className="text-xs px-2 py-1"
            >
              回档
            </Button>
          </div>
        </div>
        {node.children && node.children.length > 0 ? renderSnapshotTree(node.children, depth + 1) : null}
      </div>
    ))
  }

  const headerActions = (
    <div className="flex items-center gap-3">
      {/* Agent状态指示器 */}
      <div className="flex items-center gap-1.5">
        {agents.map((agent) => (
          <div
            key={agent.name}
            className={`w-3 h-3 rounded-full ${getAgentColor(agent.status)} cursor-pointer transition-transform hover:scale-125`}
            title={`${agent.name}: ${agent.message}`}
          />
        ))}
      </div>
      <span
        className={`px-3 py-1 rounded-full text-sm ${
          wsStatus === 'connected'
            ? isDark ? 'bg-green-900 text-green-300' : 'bg-green-100 text-green-700'
            : wsStatus === 'connecting'
              ? isDark ? 'bg-yellow-900 text-yellow-300' : 'bg-yellow-100 text-yellow-700'
              : isDark ? 'bg-gray-700 text-gray-300' : 'bg-gray-100 text-gray-600'
        }`}
      >
        {wsStatus === 'connected' ? '● 已连接' : wsStatus === 'connecting' ? '◐ 连接中' : '○ 未连接'}
      </span>
    </div>
  )

  return (
    <PageLayout
      title="上帝模式"
      description={currentProject ? `项目: ${currentProject.name}` : undefined}
      actions={headerActions}
    >
      {!currentProject ? (
        <div className={`text-center py-20 ${isDark ? 'text-gray-400' : 'text-gray-500'}`}>
          <FolderOpen size={48} className="mx-auto mb-4 opacity-50" />
          <p>请先在侧边栏选择一个项目</p>
        </div>
      ) : (
        <div className="space-y-6">
          {/* 顶部控制栏 */}
          <Card className="p-4">
            <div className="flex items-center gap-4 flex-wrap">
              <Input
                placeholder="输入会话 ID"
                value={sessionId}
                onChange={(e) => setSessionId(e.target.value)}
                className="w-48"
              />
              {!isGenerating ? (
                <Button onClick={startSession} disabled={!currentProject}>
                  <Play size={18} className="mr-2" />启动会话
                </Button>
              ) : (
                <Button variant="danger" onClick={stopSession}>
                  <Pause size={18} className="mr-2" />停止会话
                </Button>
              )}
              <Button variant="secondary" onClick={resetAll}>
                <RotateCcw size={18} className="mr-2" />重置
              </Button>
              <div className="flex-1" />
              {/* 运行时状态摘要 */}
              {runtimeState && (
                <div className={`flex items-center gap-4 text-sm ${isDark ? 'text-gray-400' : 'text-gray-500'}`}>
                  <span>阶段: <strong className={isDark ? 'text-white' : 'text-gray-800'}>{runtimeState?.state_machine?.phase || '-'}</strong></span>
                  <span>进度: <strong className={isDark ? 'text-white' : 'text-gray-800'}>{typeof runtimeState?.main_plot_progress === 'number' ? `${Math.round(runtimeState.main_plot_progress * 100)}%` : '-'}</strong></span>
                  <span>伏笔: <strong className={isDark ? 'text-white' : 'text-gray-800'}>{runtimeState?.hooks_planted?.length || 0}/{(runtimeState?.hooks_planted?.length || 0) + (runtimeState?.hooks_resolved?.length || 0)}</strong></span>
                </div>
              )}
            </div>
            {/* 当前工作状态 */}
            {isGenerating && getWorkingAgentName() && (
              <motion.div
                initial={{ opacity: 0, y: -10 }}
                animate={{ opacity: 1, y: 0 }}
                className={`mt-3 flex items-center gap-2 text-sm ${isDark ? 'text-blue-400' : 'text-blue-600'}`}
              >
                <div className="w-2 h-2 rounded-full bg-blue-500 animate-pulse" />
                <span>{getWorkingAgentName()} 正在工作...</span>
              </motion.div>
            )}
          </Card>

          {/* 核心功能区 */}
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            {/* 左侧：全自动创作（核心功能） */}
            <div className="lg:col-span-2 space-y-6">
              {/* 全自动创作卡片 */}
              <Card className={`overflow-hidden ${autoModeRunning ? 'ring-2 ring-purple-500' : ''}`}>
                <div className="p-6">
                  <div className="flex items-center gap-3 mb-4">
                    <div className="w-12 h-12 rounded-xl bg-gradient-to-br from-purple-500 to-pink-500 flex items-center justify-center">
                      <Sparkles className="w-6 h-6 text-white" />
                    </div>
                    <div>
                      <h2 className={`text-xl font-bold ${isDark ? 'text-white' : 'text-gray-800'}`}>全自动创作</h2>
                      <p className={`text-sm ${isDark ? 'text-gray-400' : 'text-gray-500'}`}>一键生成完整章节，AI 自动协调所有 Agent</p>
                    </div>
                  </div>

                  {autoModeRunning ? (
                    <div className="space-y-4">
                      <div className={`p-4 rounded-lg ${isDark ? 'bg-purple-900/30' : 'bg-purple-50'}`}>
                        <div className="flex items-center justify-between">
                          <span className={`font-medium ${isDark ? 'text-purple-300' : 'text-purple-700'}`}>
                            正在自动创作中...
                          </span>
                          <Button variant="danger" size="sm" onClick={handleStopAutoMode}>
                            <Pause size={16} className="mr-1" /> 停止
                          </Button>
                        </div>
                        <div className="mt-2 text-sm">
                          已完成: {autoModeChapters.length} 章
                        </div>
                      </div>
                    </div>
                  ) : (
                    <Button
                      onClick={() => setShowAutoModeModal(true)}
                      disabled={!isGenerating || wsStatus !== 'connected'}
                      className="w-full justify-center py-3 text-lg"
                      size="lg"
                    >
                      <Play size={20} className="mr-2" />
                      开始全自动创作
                    </Button>
                  )}
                </div>
              </Card>

              {/* 快速操作 */}
              <Card title="快速操作">
                <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                  <Button
                    variant="secondary"
                    onClick={() => send({ type: 'advance_plot' })}
                    disabled={!isGenerating || wsStatus !== 'connected' || autoModeRunning}
                    className="justify-center"
                  >
                    <Zap size={16} className="mr-2" />推进剧情
                  </Button>
                  <Button
                    variant="secondary"
                    onClick={() => send({ type: 'manage_hooks' })}
                    disabled={!isGenerating || wsStatus !== 'connected' || autoModeRunning}
                    className="justify-center"
                  >
                    <Target size={16} className="mr-2" />管理伏笔
                  </Button>
                  <Button
                    variant="secondary"
                    onClick={() => setShowAutoWriteModal(true)}
                    disabled={!isGenerating || wsStatus !== 'connected' || autoModeRunning}
                    className="justify-center"
                  >
                    <FileText size={16} className="mr-2" />写作章节
                  </Button>
                  <Button
                    variant="secondary"
                    onClick={() => send({ type: 'chapter_end_check' })}
                    disabled={!isGenerating || wsStatus !== 'connected' || autoModeRunning}
                    className="justify-center"
                  >
                    <BookOpen size={16} className="mr-2" />章节判定
                  </Button>
                </div>
              </Card>

              {/* 自动创作结果 */}
              {autoModeChapters.length > 0 && (
                <Card title={`📚 已生成章节 (${autoModeChapters.length} 章)`}>
                  <div className="space-y-3 max-h-96 overflow-y-auto">
                    {autoModeChapters.map((chapter, index) => (
                      <details key={index} className={`rounded-lg border ${isDark ? 'border-gray-700' : 'border-gray-200'}`}>
                        <summary className={`flex items-center justify-between p-3 cursor-pointer ${isDark ? 'hover:bg-gray-800' : 'hover:bg-gray-50'}`}>
                          <div className="flex items-center gap-2">
                            <span className={`font-medium ${isDark ? 'text-white' : 'text-gray-800'}`}>
                              {chapter.title}
                            </span>
                            <span className={`text-xs ${isDark ? 'text-gray-400' : 'text-gray-500'}`}>
                              {chapter.word_count} 字
                            </span>
                          </div>
                          <Button
                            variant="secondary"
                            size="sm"
                            onClick={(e) => {
                              e.stopPropagation()
                              navigator.clipboard.writeText(chapter.content)
                              addLog(`已复制: ${chapter.title}`)
                            }}
                          >
                            复制
                          </Button>
                        </summary>
                        <div className={`p-3 border-t ${isDark ? 'border-gray-700' : 'border-gray-200'}`}>
                          <pre className={`text-sm whitespace-pre-wrap max-h-60 overflow-y-auto ${isDark ? 'text-gray-300' : 'text-gray-700'}`}>
                            {chapter.content}
                          </pre>
                        </div>
                      </details>
                    ))}
                  </div>
                </Card>
              )}

              {/* 自动写作结果 */}
              {autoWriteResult && (
                <Card title={`📝 ${autoWriteResult.title}`}>
                  <div className="space-y-3">
                    <div className="flex items-center justify-between">
                      <span className={`text-sm ${isDark ? 'text-gray-400' : 'text-gray-500'}`}>
                        {autoWriteResult.word_count} 字 | ID: {autoWriteResult.chapter_id}
                      </span>
                      <div className="flex gap-2">
                        <Button
                          variant="secondary"
                          size="sm"
                          onClick={() => {
                            navigator.clipboard.writeText(autoWriteResult.content || '')
                            addLog('内容已复制')
                          }}
                        >
                          复制
                        </Button>
                        <Button
                          variant="secondary"
                          size="sm"
                          onClick={() => setAutoWriteResult(null)}
                        >
                          关闭
                        </Button>
                      </div>
                    </div>
                    <div className={`max-h-80 overflow-y-auto p-4 rounded-lg ${isDark ? 'bg-gray-800' : 'bg-gray-50'}`}>
                      <pre className={`text-sm whitespace-pre-wrap ${isDark ? 'text-gray-200' : 'text-gray-700'}`}>
                        {autoWriteResult.content}
                      </pre>
                    </div>
                  </div>
                </Card>
              )}

              {/* 生成结果：声音审查 + 叙事 */}
              {(dialoguePanel || narrativePanel) && (
                <Card title="生成结果">
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    {/* 对话结果 */}
                    {dialoguePanel && (
                      <div className={`p-4 rounded-lg border ${isDark ? 'border-gray-700' : 'border-gray-200'}`}>
                        <div className="flex items-center gap-2 mb-2">
                          <MessageSquare size={16} />
                          <span className={`font-medium ${isDark ? 'text-white' : 'text-gray-800'}`}>对话</span>
                        </div>
                        <p className={`text-sm ${isDark ? 'text-gray-300' : 'text-gray-700'}`}>
                          <span className="font-medium">{dialoguePanel.speaker_id}:</span> {dialoguePanel.dialogue}
                        </p>
                        {dialoguePanel.voice_review?.is_ooc && (
                          <p className="text-xs text-red-500 mt-2">⚠️ 检测到 OOC</p>
                        )}
                      </div>
                    )}
                    {/* 叙事结果 */}
                    {narrativePanel && (
                      <div className={`p-4 rounded-lg border ${isDark ? 'border-gray-700' : 'border-gray-200'}`}>
                        <div className="flex items-center justify-between mb-2">
                          <div className="flex items-center gap-2">
                            <PenLine size={16} />
                            <span className={`font-medium ${isDark ? 'text-white' : 'text-gray-800'}`}>叙事</span>
                          </div>
                          <span className={`text-xs ${isDark ? 'text-gray-400' : 'text-gray-500'}`}>
                            {narrativePanel.word_count} 字
                          </span>
                        </div>
                        <p className={`text-sm line-clamp-3 ${isDark ? 'text-gray-300' : 'text-gray-700'}`}>
                          {narrativePanel.content}
                        </p>
                      </div>
                    )}
                  </div>
                </Card>
              )}

              {/* 高级控制（可折叠） */}
              <Card>
                <button
                  onClick={() => setShowAdvancedControls(!showAdvancedControls)}
                  className={`w-full flex items-center justify-between p-4 ${isDark ? 'hover:bg-gray-800' : 'hover:bg-gray-50'}`}
                >
                  <span className={`font-medium ${isDark ? 'text-white' : 'text-gray-800'}`}>高级控制</span>
                  {showAdvancedControls ? <ChevronUp size={18} /> : <ChevronDown size={18} />}
                </button>
                <AnimatePresence>
                  {showAdvancedControls && (
                    <motion.div
                      initial={{ height: 0, opacity: 0 }}
                      animate={{ height: 'auto', opacity: 1 }}
                      exit={{ height: 0, opacity: 0 }}
                      className="overflow-hidden"
                    >
                      <div className="p-4 pt-0 space-y-4">
                        {/* 角色管理 */}
                        <div className="flex items-center justify-between">
                          <div className="flex items-center gap-2">
                            <Users size={16} />
                            <span className={`text-sm ${isDark ? 'text-gray-300' : 'text-gray-700'}`}>
                              角色 ({availableCharacters.length})
                            </span>
                          </div>
                          <Button
                            size="sm"
                            variant="secondary"
                            onClick={() => setShowAddCharacterModal(true)}
                            disabled={!isGenerating || wsStatus !== 'connected'}
                          >
                            <UserPlus size={14} className="mr-1" /> 添加
                          </Button>
                        </div>
                        <div className="flex flex-wrap gap-2">
                          {availableCharacters.map((char) => (
                            <span
                              key={char.id}
                              className={`px-2 py-1 rounded text-sm flex items-center gap-1 ${isDark ? 'bg-gray-700 text-gray-300' : 'bg-gray-100 text-gray-700'}`}
                            >
                              {char.name}
                              <button
                                onClick={() => handleRemoveCharacter(char.id)}
                                className="hover:text-red-500"
                              >
                                <UserMinus size={12} />
                              </button>
                            </span>
                          ))}
                        </div>

                        {/* 对话/工作流输入 */}
                        <div className="grid grid-cols-2 gap-3">
                          <Input
                            placeholder="speaker_id"
                            value={dialogueForm.speakerId}
                            onChange={(e) => setDialogueForm(prev => ({ ...prev, speakerId: e.target.value }))}
                          />
                          <Input
                            placeholder="present_characters"
                            value={dialogueForm.presentCharacters}
                            onChange={(e) => setDialogueForm(prev => ({ ...prev, presentCharacters: e.target.value }))}
                          />
                        </div>
                        <TextArea
                          placeholder="context / intents"
                          value={dialogueForm.context}
                          onChange={(e) => setDialogueForm(prev => ({ ...prev, context: e.target.value }))}
                          rows={2}
                        />
                        <div className="flex gap-2">
                          <Button size="sm" variant="secondary" onClick={triggerDialogue} disabled={!isGenerating || wsStatus !== 'connected'}>
                            生成对话
                          </Button>
                          <Button size="sm" variant="secondary" onClick={triggerNarrative} disabled={!isGenerating || wsStatus !== 'connected'}>
                            生成叙事
                          </Button>
                          <Button size="sm" variant="secondary" onClick={triggerWorkflowCycle} disabled={!isGenerating || wsStatus !== 'connected'}>
                            执行工作流
                          </Button>
                        </div>

                        {/* 其他操作 */}
                        <div className="flex gap-2 flex-wrap">
                          <Button size="sm" variant="secondary" onClick={() => send({ type: 'create_snapshot', snapshot_type: 'manual', is_branch: true })} disabled={!isGenerating || wsStatus !== 'connected'}>
                            <GitBranch size={14} className="mr-1" />创建快照
                          </Button>
                          <Button size="sm" variant="secondary" onClick={() => setShowCommandModal(true)}>
                            <Settings size={14} className="mr-1" />手动指令
                          </Button>
                        </div>
                      </div>
                    </motion.div>
                  )}
                </AnimatePresence>
              </Card>
            </div>

            {/* 右侧：日志 + 快照 */}
            <div className="space-y-6">
              {/* 实时日志 */}
              <Card>
                <button
                  onClick={() => setShowLogs(!showLogs)}
                  className={`w-full flex items-center justify-between p-4 ${isDark ? 'hover:bg-gray-800' : 'hover:bg-gray-50'}`}
                >
                  <span className={`font-medium ${isDark ? 'text-white' : 'text-gray-800'}`}>实时日志</span>
                  <div className="flex items-center gap-2">
                    <span className={`text-xs px-2 py-0.5 rounded ${isDark ? 'bg-gray-700 text-gray-300' : 'bg-gray-100 text-gray-600'}`}>
                      {logs.length} 条
                    </span>
                    {showLogs ? <ChevronUp size={18} /> : <ChevronDown size={18} />}
                  </div>
                </button>
                <AnimatePresence>
                  {showLogs && (
                    <motion.div
                      initial={{ height: 0, opacity: 0 }}
                      animate={{ height: 'auto', opacity: 1 }}
                      exit={{ height: 0, opacity: 0 }}
                      className="overflow-hidden"
                    >
                      <div className="p-4 pt-0">
                        <div className={`h-80 overflow-y-auto space-y-1 font-mono text-xs p-3 rounded-lg ${isDark ? 'bg-gray-900 text-green-400' : 'bg-gray-900 text-green-400'}`}>
                          {logs.length === 0 ? (
                            <p className="text-gray-500">暂无日志...</p>
                          ) : (
                            logs.map((log, i) => <p key={i}>{log}</p>)
                          )}
                        </div>
                      </div>
                    </motion.div>
                  )}
                </AnimatePresence>
              </Card>

              {/* 版本树 */}
              <Card title="快照版本">
                <div className="space-y-2 max-h-60 overflow-y-auto">
                  {snapshotTree.length > 0 ? (
                    renderSnapshotTree(snapshotTree)
                  ) : (
                    <p className={`text-sm text-center py-4 ${isDark ? 'text-gray-400' : 'text-gray-500'}`}>
                      暂无快照
                    </p>
                  )}
                </div>
                {rollbackSnapshotId && (
                  <div className="mt-3 pt-3 border-t flex gap-2">
                    <Input
                      value={rollbackSnapshotId}
                      onChange={(e) => setRollbackSnapshotId(e.target.value)}
                      placeholder="snapshot_id"
                      className="flex-1 text-sm"
                    />
                    <Button
                      size="sm"
                      onClick={() => send({ type: 'rollback_snapshot', snapshot_id: rollbackSnapshotId })}
                      disabled={!isGenerating || wsStatus !== 'connected'}
                    >
                      回档
                    </Button>
                  </div>
                )}
              </Card>
            </div>
          </div>
        </div>
      )}

      {/* Modals */}
      <Modal isOpen={showCommandModal} onClose={() => setShowCommandModal(false)} title="手动 Agent 指令">
        <div className="space-y-4">
          <div>
            <label className={`block text-sm font-medium mb-2 ${isDark ? 'text-gray-300' : 'text-gray-700'}`}>选择 Agent</label>
            <select
              className={`w-full px-3 py-2 border rounded-lg ${isDark ? 'bg-gray-800 border-gray-600 text-white' : 'border-gray-300'}`}
              value={selectedAgent}
              onChange={(e) => setSelectedAgent(e.target.value)}
            >
              <option value="">请选择...</option>
              {agents.map((a) => (
                <option key={a.name} value={a.name}>{a.name}</option>
              ))}
            </select>
          </div>
          <TextArea
            label="指令内容"
            placeholder='{"action": "..."}'
            value={agentCommand}
            onChange={(e) => setAgentCommand(e.target.value)}
          />
          <div className="flex justify-end gap-3">
            <Button variant="secondary" onClick={() => setShowCommandModal(false)}>取消</Button>
            <Button onClick={executeAgentCommand}>发送</Button>
          </div>
        </div>
      </Modal>

      <Modal isOpen={showAddCharacterModal} onClose={() => setShowAddCharacterModal(false)} title="添加角色">
        <div className="space-y-4">
          <Input
            label="角色名称 *"
            value={newCharacterForm.name}
            onChange={(e) => setNewCharacterForm({ ...newCharacterForm, name: e.target.value })}
            placeholder="输入角色名称"
          />
          <div>
            <label className={`block text-sm font-medium mb-1 ${isDark ? 'text-gray-300' : 'text-gray-700'}`}>角色类型</label>
            <select
              className={`w-full px-3 py-2 border rounded-lg ${isDark ? 'bg-gray-800 border-gray-600 text-white' : 'border-gray-300'}`}
              value={newCharacterForm.role}
              onChange={(e) => setNewCharacterForm({ ...newCharacterForm, role: e.target.value })}
            >
              <option value="main">主角</option>
              <option value="supporting">配角</option>
              <option value="npc">NPC</option>
            </select>
          </div>
          <TextArea
            label="角色描述"
            value={newCharacterForm.description}
            onChange={(e) => setNewCharacterForm({ ...newCharacterForm, description: e.target.value })}
            rows={2}
          />
          <div className="flex justify-end gap-3">
            <Button variant="secondary" onClick={() => setShowAddCharacterModal(false)}>取消</Button>
            <Button onClick={handleAddCharacter} disabled={!newCharacterForm.name.trim()}>添加</Button>
          </div>
        </div>
      </Modal>

      <Modal isOpen={showAutoWriteModal} onClose={() => setShowAutoWriteModal(false)} title="自动写作章节">
        <div className="space-y-4">
          <Input
            label="章节标题 *"
            value={autoWriteForm.chapter_title}
            onChange={(e) => setAutoWriteForm({ ...autoWriteForm, chapter_title: e.target.value })}
            placeholder="如：第一章 相遇"
          />
          <TextArea
            label="章节目标/大纲 *"
            value={autoWriteForm.chapter_goal}
            onChange={(e) => setAutoWriteForm({ ...autoWriteForm, chapter_goal: e.target.value })}
            placeholder="描述本章的主要内容、情节走向..."
            rows={4}
          />
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className={`block text-sm font-medium mb-1 ${isDark ? 'text-gray-300' : 'text-gray-700'}`}>目标字数</label>
              <input
                type="number"
                value={autoWriteForm.target_word_count}
                onChange={(e) => setAutoWriteForm({ ...autoWriteForm, target_word_count: parseInt(e.target.value) || 2000 })}
                className={`w-full px-3 py-2 border rounded-lg ${isDark ? 'bg-gray-800 border-gray-600 text-white' : 'border-gray-300'}`}
                min={500}
                max={10000}
              />
            </div>
          </div>
          <div className="flex justify-end gap-3 pt-4">
            <Button variant="secondary" onClick={() => setShowAutoWriteModal(false)}>取消</Button>
            <Button onClick={handleAutoWriteChapter} disabled={!autoWriteForm.chapter_title.trim() || !autoWriteForm.chapter_goal.trim()}>
              开始写作
            </Button>
          </div>
        </div>
      </Modal>

      <Modal isOpen={showAutoModeModal} onClose={() => setShowAutoModeModal(false)} title="🚀 全自动创作模式" size="lg">
        <div className="space-y-4">
          <div className={`p-4 rounded-lg ${isDark ? 'bg-purple-900/30' : 'bg-purple-50'}`}>
            <p className={`text-sm ${isDark ? 'text-purple-300' : 'text-purple-700'}`}>
              全自动创作将自动规划剧情、逐章写作、管理伏笔。你只需要提供初始设定，剩下的交给 AI。
            </p>
          </div>
          <TextArea
            label="初始剧情设定/大纲 *"
            value={autoModeForm.initial_plot}
            onChange={(e) => setAutoModeForm({ ...autoModeForm, initial_plot: e.target.value })}
            placeholder="描述整体故事设定、主角、目标、世界观等...&#10;例如：少年林风偶然获得神秘玉佩，踏上修仙之路..."
            rows={5}
          />
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className={`block text-sm font-medium mb-1 ${isDark ? 'text-gray-300' : 'text-gray-700'}`}>章节数量</label>
              <input
                type="number"
                value={autoModeForm.chapter_count}
                onChange={(e) => setAutoModeForm({ ...autoModeForm, chapter_count: parseInt(e.target.value) || 3 })}
                className={`w-full px-3 py-2 border rounded-lg ${isDark ? 'bg-gray-800 border-gray-600 text-white' : 'border-gray-300'}`}
                min={1}
                max={20}
              />
            </div>
            <div>
              <label className={`block text-sm font-medium mb-1 ${isDark ? 'text-gray-300' : 'text-gray-700'}`}>每章字数</label>
              <input
                type="number"
                value={autoModeForm.words_per_chapter}
                onChange={(e) => setAutoModeForm({ ...autoModeForm, words_per_chapter: parseInt(e.target.value) || 2000 })}
                className={`w-full px-3 py-2 border rounded-lg ${isDark ? 'bg-gray-800 border-gray-600 text-white' : 'border-gray-300'}`}
                min={500}
                max={5000}
              />
            </div>
          </div>
          <TextArea
            label="风格参考（可选）"
            value={autoModeForm.style_reference}
            onChange={(e) => setAutoModeForm({ ...autoModeForm, style_reference: e.target.value })}
            placeholder="粘贴一段你希望模仿风格的文字..."
            rows={2}
          />
          <div className="flex justify-end gap-3 pt-4">
            <Button variant="secondary" onClick={() => setShowAutoModeModal(false)}>取消</Button>
            <Button onClick={handleStartAutoMode} disabled={!autoModeForm.initial_plot.trim()}>
              <Play size={16} className="mr-1" /> 开始自动创作
            </Button>
          </div>
        </div>
      </Modal>
    </PageLayout>
  )
}
