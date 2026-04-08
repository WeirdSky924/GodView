import { useEffect, useMemo, useState } from 'react'
import { Card, Button, Input, TextArea, Modal } from '@/components/ui'
import PageLayout from '@/components/PageLayout'
import { useDynamicWebSocket } from '@/hooks/useWebSocket'
import { getDirectorState, getSnapshotTree, getWorkflowGraph } from '@/api/director'
import { getCharacters } from '@/api/characters'
import { Play, Pause, RotateCcw, Zap, Target, BookOpen, MessageSquare, Map, GitBranch, RefreshCcw, Workflow, Mic, PenLine, FolderOpen, UserPlus, UserMinus, Users } from 'lucide-react'
import { useProject } from '@/contexts/ProjectContext'
import { useTheme } from '@/contexts/ThemeContext'

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
  { name: 'Summarizer', status: 'idle', message: '剧情总结员 - 待命', progress: 0 },
  { name: 'Master Plotter', status: 'idle', message: '总编剧 - 待命', progress: 0 },
  { name: 'Hook Manager', status: 'idle', message: '伏笔管理员 - 待命', progress: 0 },
  { name: 'Writer', status: 'idle', message: '内容执行官 - 待命', progress: 0 },
  { name: 'Evaluator', status: 'idle', message: '剧情评估员 - 待命', progress: 0 },
  { name: 'Character Agent', status: 'idle', message: '角色演绎 - 待命', progress: 0 },
  { name: 'ProcGen', status: 'idle', message: '世界生成 - 待命', progress: 0 },
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

  const addLog = (message: string) => {
    const timestamp = new Date().toLocaleTimeString()
    setLogs((prev) => [`[${timestamp}] ${message}`, ...prev.slice(0, 199)])
  }

  // 使用相对路径，WebSocket 基础 URL 从配置获取
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

  // 加载项目角色列表
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
          addLog(`对话生成完成: ${data.data?.dialogue || ''}`)
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
          // 刷新角色列表
          if (currentProject) {
            getCharacters(currentProject.id).then((chars: any[]) => {
              setAvailableCharacters(chars.map((c) => ({ id: c.id, name: c.name })))
            })
          }
          break
        case 'character_removed':
          addLog(`角色已移除: ${data.data?.character_id}`)
          // 刷新角色列表
          if (currentProject) {
            getCharacters(currentProject.id).then((chars: any[]) => {
              setAvailableCharacters(chars.map((c) => ({ id: c.id, name: c.name })))
            })
          }
          break
        case 'characters_list':
          addLog(`角色列表: ${data.data?.count || 0} 个角色`)
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
    addLog(`启动会话: 项目 ${currentProject.name}, 世界 ${worldId}, 角色 ${characterIds.length} 个`)
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

    // 重置表单并关闭 Modal
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

  const quickActions = [
    { icon: <Zap size={18} />, label: '推进剧情', command: 'advance_plot' },
    { icon: <Target size={18} />, label: '管理伏笔', command: 'manage_hooks' },
    { icon: <BookOpen size={18} />, label: '检查章节结束', command: 'chapter_end_check' },
  ]

  const getAgentColor = (status: AgentStatus['status']) => {
    switch (status) {
      case 'idle':
        return 'bg-gray-400'
      case 'working':
        return 'bg-blue-500 animate-pulse'
      case 'completed':
        return 'bg-green-500'
      case 'error':
        return 'bg-red-500'
      default:
        return 'bg-gray-400'
    }
  }

  const renderSnapshotTree = (nodes: SnapshotNode[], depth = 0): React.ReactNode => {
    return nodes.map((node) => (
      <div key={node.id} className="space-y-2">
        <div className={`rounded-lg border p-3 ${isDark ? 'border-gray-700' : 'border-gray-200'}`} style={{ marginLeft: `${depth * 16}px` }}>
          <div className="flex items-center justify-between gap-3">
            <div>
              <p className={`text-sm font-medium ${isDark ? 'text-white' : 'text-gray-800'}`}>{node.name || node.id}</p>
              <p className={`text-xs ${isDark ? 'text-gray-400' : 'text-gray-500'}`}>{node.snapshot_type} {node.is_branch ? '· 分支' : ''}</p>
              {node.branch_reason && <p className="text-xs text-purple-600 mt-1">{node.branch_reason}</p>}
            </div>
            <Button
              variant="secondary"
              onClick={() => setRollbackSnapshotId(node.id)}
              disabled={!isGenerating || wsStatus !== 'connected'}
            >
              选择回档
            </Button>
          </div>
        </div>
        {node.children && node.children.length > 0 ? renderSnapshotTree(node.children, depth + 1) : null}
      </div>
    ))
  }

  const headerActions = (
    <div className="flex items-center gap-4">
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
      title="导演模式"
      description={currentProject ? `项目: ${currentProject.name}` : undefined}
      actions={headerActions}
    >
      {!currentProject ? (
        <div className={`text-center py-20 ${isDark ? 'text-gray-400' : 'text-gray-500'}`}>
          <FolderOpen size={48} className="mx-auto mb-4 opacity-50" />
          <p>请先在侧边栏选择一个项目</p>
        </div>
      ) : (
        <>
          <Card title="会话控制" className="mb-6">
            <div className="flex gap-4 flex-wrap">
              <Input placeholder="输入会话 ID" value={sessionId} onChange={(e) => setSessionId(e.target.value)} />
              {!isGenerating ? (
                <Button onClick={startSession} disabled={!currentProject}>
                  <Play size={18} className="mr-2" />开始生成
                </Button>
              ) : (
                <Button variant="danger" onClick={stopSession}>
                  <Pause size={18} className="mr-2" />停止生成
                </Button>
              )}
              <Button variant="secondary" onClick={resetAll}>
                <RotateCcw size={18} className="mr-2" />重置
          </Button>
          <Button variant="secondary" onClick={loadRuntimePanels}>
            <RefreshCcw size={18} className="mr-2" />刷新状态
          </Button>
          <Button onClick={() => setShowCommandModal(true)}>手动指令</Button>
        </div>
      </Card>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 mb-6">
        <div className="lg:col-span-2">
          <Card title="Agent 状态" className="mb-6">
            <div className="space-y-3">
              {agents.map((agent) => (
                <div key={agent.name} className={`flex items-center gap-3 p-3 rounded-lg ${isDark ? 'bg-gray-800' : 'bg-gray-50'}`}>
                  <div className={`w-3 h-3 rounded-full ${getAgentColor(agent.status)}`} />
                  <div className="flex-1">
                    <p className={`font-medium ${isDark ? 'text-white' : 'text-gray-800'}`}>{agent.name}</p>
                    <p className={`text-sm ${isDark ? 'text-gray-400' : 'text-gray-500'}`}>{agent.message}</p>
                  </div>
                  {agent.progress !== undefined && (
                    <div className="w-32">
                      <div className={`h-2 rounded-full overflow-hidden ${isDark ? 'bg-gray-700' : 'bg-gray-200'}`}>
                        <div className="h-full bg-blue-500 transition-all" style={{ width: `${agent.progress}%` }} />
                      </div>
                    </div>
                  )}
                </div>
              ))}
            </div>
          </Card>

          <Card title="对话 / 工作流输入" className="mb-6">
            <div className="space-y-4">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <Input
                  label="speaker_id"
                  value={dialogueForm.speakerId}
                  onChange={(e) => setDialogueForm((prev) => ({ ...prev, speakerId: e.target.value }))}
                  placeholder="如：narrator / char_001"
                />
                <Input
                  label="present_characters"
                  value={dialogueForm.presentCharacters}
                  onChange={(e) => setDialogueForm((prev) => ({ ...prev, presentCharacters: e.target.value }))}
                  placeholder="逗号分隔，如：char_001,char_002"
                />
              </div>
              <TextArea
                label="context"
                value={dialogueForm.context}
                onChange={(e) => setDialogueForm((prev) => ({ ...prev, context: e.target.value }))}
                placeholder="当前场景上下文"
              />
              <TextArea
                label="intents"
                value={dialogueForm.intents}
                onChange={(e) => setDialogueForm((prev) => ({ ...prev, intents: e.target.value }))}
                placeholder="逗号或换行分隔，如：推进剧情，制造冲突"
              />
              <TextArea
                label="environment"
                value={dialogueForm.environment}
                onChange={(e) => setDialogueForm((prev) => ({ ...prev, environment: e.target.value }))}
                placeholder="环境描写，如：夜雨、空旷仓库、压抑气氛"
              />
              <TextArea
                label="character_moods"
                value={dialogueForm.characterMoods}
                onChange={(e) => setDialogueForm((prev) => ({ ...prev, characterMoods: e.target.value }))}
                placeholder={"每行一条，格式：角色ID:情绪\nchar_001:愤怒\nchar_002:警惕"}
              />
              <div className="flex gap-3 flex-wrap">
                <Button onClick={triggerDialogue} disabled={!isGenerating || wsStatus !== 'connected'}>
                  <MessageSquare size={18} className="mr-2" />生成对话
                </Button>
                <Button variant="secondary" onClick={triggerNarrative} disabled={!isGenerating || wsStatus !== 'connected'}>
                  <PenLine size={18} className="mr-2" />生成叙事
                </Button>
                <Button variant="secondary" onClick={triggerWorkflowCycle} disabled={!isGenerating || wsStatus !== 'connected'}>
                  <Workflow size={18} className="mr-2" />执行工作流
                </Button>
              </div>
            </div>
          </Card>

          <Card title="快速操作" className="mb-6">
            <div className="grid grid-cols-2 gap-3">
              {quickActions.map((action) => (
                <Button
                  key={action.label}
                  variant="secondary"
                  onClick={() => send({ type: action.command })}
                  disabled={!isGenerating || wsStatus !== 'connected'}
                  className="justify-start"
                >
                  {action.icon}
                  <span className="ml-2">{action.label}</span>
                </Button>
              ))}
            </div>
          </Card>

          <Card title="角色管理" className="mb-6">
            <div className="space-y-4">
              <div className="flex items-center justify-between">
                <div className={`flex items-center gap-2 ${isDark ? 'text-gray-400' : 'text-gray-600'}`}>
                  <Users size={18} />
                  <span>当前角色 ({availableCharacters.length})</span>
                </div>
                <Button
                  size="sm"
                  onClick={() => setShowAddCharacterModal(true)}
                  disabled={!isGenerating || wsStatus !== 'connected'}
                >
                  <UserPlus size={16} className="mr-1" /> 添加角色
                </Button>
              </div>

              {availableCharacters.length === 0 ? (
                <p className={`text-sm text-center py-4 ${isDark ? 'text-gray-400' : 'text-gray-500'}`}>暂无角色，请先在项目中创建角色</p>
              ) : (
                <div className="space-y-2 max-h-48 overflow-y-auto">
                  {availableCharacters.map((char) => (
                    <div
                      key={char.id}
                      className={`flex items-center justify-between p-3 rounded-lg ${isDark ? 'bg-gray-800' : 'bg-gray-50'}`}
                    >
                      <div>
                        <span className={`font-medium ${isDark ? 'text-white' : 'text-gray-800'}`}>{char.name}</span>
                        <span className={`text-xs ml-2 ${isDark ? 'text-gray-400' : 'text-gray-500'}`}>{char.id}</span>
                      </div>
                      <Button
                        variant="secondary"
                        size="sm"
                        onClick={() => handleRemoveCharacter(char.id)}
                        disabled={!isGenerating || wsStatus !== 'connected'}
                      >
                        <UserMinus size={14} />
                      </Button>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </Card>

          <Card title="声音审查面板" className="mb-6">
            {!dialoguePanel ? (
              <p className={`text-sm ${isDark ? 'text-gray-400' : 'text-gray-500'}`}>暂无对话结果。执行"生成对话"或工作流后会显示声音审查数据。</p>
            ) : (
              <div className="space-y-4 text-sm">
                <div className={`rounded-lg p-4 ${isDark ? 'bg-gray-800' : 'bg-gray-50'}`}>
                  <div className={`flex items-center gap-2 mb-2 font-medium ${isDark ? 'text-white' : 'text-gray-800'}`}>
                    <Mic size={16} /> 最新对话
                  </div>
                  <p><span className="font-medium">角色：</span>{dialoguePanel.speaker_id || '-'}</p>
                  <p className={`mt-2 whitespace-pre-wrap ${isDark ? 'text-gray-300' : 'text-gray-700'}`}>{dialoguePanel.dialogue || '-'}</p>
                  {dialoguePanel.action ? <p className={`mt-2 ${isDark ? 'text-gray-400' : 'text-gray-500'}`}>动作：{dialoguePanel.action}</p> : null}
                  {dialoguePanel.emotion ? <p className={isDark ? 'text-gray-400' : 'text-gray-500'}>情绪：{dialoguePanel.emotion}</p> : null}
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div className={`rounded-lg border p-4 ${isDark ? 'border-gray-700' : 'border-gray-200'}`}>
                    <h3 className={`font-medium mb-2 ${isDark ? 'text-white' : 'text-gray-800'}`}>声音上下文</h3>
                    <p className={isDark ? 'text-gray-300' : 'text-gray-700'}>向量检索：{dialoguePanel.voice_context?.used_qdrant ? '已启用' : '未启用'}</p>
                    <p className={isDark ? 'text-gray-300' : 'text-gray-700'}>命中样本数：{dialoguePanel.voice_context?.retrieved_count || 0}</p>
                    <div className="mt-2 space-y-2">
                      {(dialoguePanel.voice_context?.retrieved_samples || []).length === 0 ? (
                        <p className={isDark ? 'text-gray-400' : 'text-gray-500'}>暂无参考样本</p>
                      ) : (
                        dialoguePanel.voice_context?.retrieved_samples?.map((sample, index) => (
                          <div key={`${sample}-${index}`} className={`rounded p-2 ${isDark ? 'bg-gray-700 text-gray-300' : 'bg-gray-50 text-gray-700'}`}>
                            {sample}
                          </div>
                        ))
                      )}
                    </div>
                  </div>

                  <div className={`rounded-lg border p-4 ${isDark ? 'border-gray-700' : 'border-gray-200'}`}>
                    <h3 className={`font-medium mb-2 ${isDark ? 'text-white' : 'text-gray-800'}`}>OOC 审查</h3>
                    <p className={isDark ? 'text-gray-300' : 'text-gray-700'}>已审查：{dialoguePanel.voice_review?.checked ? '是' : '否'}</p>
                    <p className={isDark ? 'text-gray-300' : 'text-gray-700'}>结果：{dialoguePanel.voice_review?.is_ooc ? '检测到 OOC' : '通过'}</p>
                    <p className={isDark ? 'text-gray-300' : 'text-gray-700'}>置信度：{typeof dialoguePanel.voice_review?.confidence === 'number' ? dialoguePanel.voice_review.confidence.toFixed(3) : '-'}</p>
                    {dialoguePanel.voice_review?.suggestion ? (
                      <p className="mt-2 text-amber-700">建议：{dialoguePanel.voice_review.suggestion}</p>
                    ) : null}
                    <div className="mt-2 space-y-2">
                      {(dialoguePanel.voice_review?.issues || []).length === 0 ? (
                        <p className={isDark ? 'text-gray-400' : 'text-gray-500'}>无明显问题</p>
                      ) : (
                        dialoguePanel.voice_review?.issues?.map((issue, index) => (
                          <div key={`${issue}-${index}`} className={`rounded p-2 ${isDark ? 'bg-red-900 text-red-300' : 'bg-red-50 text-red-700'}`}>
                            {issue}
                          </div>
                        ))
                      )}
                    </div>
                  </div>
                </div>

                <div className={`rounded-lg border p-4 ${isDark ? 'border-gray-700' : 'border-gray-200'}`}>
                  <h3 className={`font-medium mb-2 ${isDark ? 'text-white' : 'text-gray-800'}`}>自动重写结果</h3>
                  <p className={isDark ? 'text-gray-300' : 'text-gray-700'}>是否重写：{dialoguePanel.rewrite_result?.applied ? '已重写' : '未触发'}</p>
                  {dialoguePanel.rewrite_result?.original_dialogue ? (
                    <div className="mt-3 rounded bg-amber-50 p-3">
                      <p className="text-xs font-medium text-amber-800 mb-1">重写前</p>
                      <p className="text-sm text-amber-900 whitespace-pre-wrap">{dialoguePanel.rewrite_result.original_dialogue}</p>
                    </div>
                  ) : null}
                  {(dialoguePanel.rewrite_result?.changes_made || []).length > 0 ? (
                    <div className="mt-3 space-y-2">
                      {dialoguePanel.rewrite_result?.changes_made?.map((change, index) => (
                        <div key={`${change}-${index}`} className={`rounded p-2 ${isDark ? 'bg-green-900 text-green-300' : 'bg-green-50 text-green-700'}`}>
                          {change}
                        </div>
                      ))}
                    </div>
                  ) : null}
                </div>
              </div>
            )}
          </Card>

          <Card title="叙事闭环面板" className="mb-6">
            {!narrativePanel ? (
              <p className={`text-sm ${isDark ? 'text-gray-400' : 'text-gray-500'}`}>暂无叙事结果。执行"生成叙事"或工作流后会显示叙事闭环数据。</p>
            ) : (
              <div className="space-y-4 text-sm">
                <div className={`rounded-lg p-4 ${isDark ? 'bg-gray-800' : 'bg-gray-50'}`}>
                  <div className={`flex items-center gap-2 mb-2 font-medium ${isDark ? 'text-white' : 'text-gray-800'}`}>
                    <PenLine size={16} /> 最新叙事
                  </div>
                  <p className={`text-xs ${isDark ? 'text-gray-400' : 'text-gray-500'}`}>字数：{narrativePanel.word_count || 0}</p>
                  <p className={`mt-2 whitespace-pre-wrap ${isDark ? 'text-gray-300' : 'text-gray-700'}`}>{narrativePanel.content || '-'}</p>
                </div>

                <div className={`rounded-lg border p-4 ${isDark ? 'border-gray-700' : 'border-gray-200'}`}>
                  <h3 className={`font-medium mb-2 ${isDark ? 'text-white' : 'text-gray-800'}`}>叙事声音审查</h3>
                  <p className={isDark ? 'text-gray-300' : 'text-gray-700'}>已审查：{narrativePanel.voice_review?.checked ? '是' : '否'}</p>
                  <p className={isDark ? 'text-gray-300' : 'text-gray-700'}>是否存在 OOC：{narrativePanel.voice_review?.has_ooc ? '是' : '否'}</p>
                  {narrativePanel.voice_review?.reason ? (
                    <p className={`mt-1 ${isDark ? 'text-gray-400' : 'text-gray-500'}`}>原因：{narrativePanel.voice_review.reason}</p>
                  ) : null}
                  <div className="mt-3 space-y-3">
                    {(narrativePanel.voice_review?.results || []).length === 0 ? (
                      <p className={isDark ? 'text-gray-400' : 'text-gray-500'}>暂无角色级审查结果</p>
                    ) : (
                      narrativePanel.voice_review?.results?.map((entry, index) => (
                        <div key={`${entry.character_id || 'entry'}-${index}`} className={`rounded border p-3 ${isDark ? 'bg-gray-800 border-gray-700' : 'bg-gray-50 border-gray-200'}`}>
                          <p className={`font-medium ${isDark ? 'text-white' : 'text-gray-800'}`}>{entry.character_name || entry.character_id || '未知角色'}</p>
                          <p className={`text-xs mt-1 ${isDark ? 'text-gray-400' : 'text-gray-500'}`}>Qdrant：{entry.voice_context?.used_qdrant ? '已启用' : '未启用'} / 命中样本：{entry.voice_context?.retrieved_count || 0}</p>
                          <p className={`mt-2 ${isDark ? 'text-gray-300' : 'text-gray-700'}`}>结果：{entry.voice_review?.is_ooc ? '检测到 OOC' : '通过'}</p>
                          {entry.voice_review?.suggestion ? <p className="text-amber-700 mt-1">建议：{entry.voice_review.suggestion}</p> : null}
                          {(entry.voice_review?.issues || []).length > 0 ? (
                            <div className="mt-2 space-y-1">
                              {entry.voice_review?.issues?.map((issue, issueIndex) => (
                                <div key={`${issue}-${issueIndex}`} className={`rounded p-2 ${isDark ? 'bg-red-900 text-red-300' : 'bg-red-50 text-red-700'}`}>
                                  {issue}
                                </div>
                              ))}
                            </div>
                          ) : null}
                        </div>
                      ))
                    )}
                  </div>
                </div>

                <div className={`rounded-lg border p-4 ${isDark ? 'border-gray-700' : 'border-gray-200'}`}>
                  <h3 className={`font-medium mb-2 ${isDark ? 'text-white' : 'text-gray-800'}`}>叙事自动重写</h3>
                  <p className={isDark ? 'text-gray-300' : 'text-gray-700'}>是否重写：{narrativePanel.rewrite_result?.applied ? '已重写' : '未触发'}</p>
                  {narrativePanel.rewrite_result?.target_character_name ? (
                    <p className={`mt-1 ${isDark ? 'text-gray-400' : 'text-gray-600'}`}>目标角色：{narrativePanel.rewrite_result.target_character_name}</p>
                  ) : null}
                  {narrativePanel.rewrite_result?.original_content ? (
                    <div className="mt-3 rounded bg-amber-50 p-3">
                      <p className="text-xs font-medium text-amber-800 mb-1">重写前</p>
                      <p className="text-sm text-amber-900 whitespace-pre-wrap">{narrativePanel.rewrite_result.original_content}</p>
                    </div>
                  ) : null}
                  {(narrativePanel.rewrite_result?.changes_made || []).length > 0 ? (
                    <div className="mt-3 space-y-2">
                      {narrativePanel.rewrite_result?.changes_made?.map((change, index) => (
                        <div key={`${change}-${index}`} className={`rounded p-2 ${isDark ? 'bg-green-900 text-green-300' : 'bg-green-50 text-green-700'}`}>
                          {change}
                        </div>
                      ))}
                    </div>
                  ) : null}
                </div>
              </div>
            )}
          </Card>

          <Card title="第三阶段控制台">
            <div className="space-y-4">
              <div>
                <label className={`block text-sm font-medium mb-2 ${isDark ? 'text-gray-300' : 'text-gray-700'}`}>区域生成提示</label>
                <TextArea value={regionPrompt} onChange={(e) => setRegionPrompt(e.target.value)} />
              </div>
              <div className="flex gap-3 flex-wrap">
                <Button
                  variant="secondary"
                  onClick={() => send({ type: 'generate_region', exploration_direction: regionPrompt })}
                  disabled={!isGenerating || wsStatus !== 'connected'}
                >
                  <Map size={18} className="mr-2" />生成区域
                </Button>
                <Button
                  variant="secondary"
                  onClick={() => send({ type: 'create_snapshot', snapshot_type: 'manual', is_branch: true, branch_reason: 'manual branch' })}
                  disabled={!isGenerating || wsStatus !== 'connected'}
                >
                  <GitBranch size={18} className="mr-2" />创建分支快照
                </Button>
                <Button
                  variant="secondary"
                  onClick={() => rollbackSnapshotId && send({ type: 'rollback_snapshot', snapshot_id: rollbackSnapshotId })}
                  disabled={!rollbackSnapshotId || !isGenerating || wsStatus !== 'connected'}
                >
                  <RotateCcw size={18} className="mr-2" />回档到所选快照
                </Button>
              </div>
            </div>
          </Card>
        </div>

        <div>
          <Card title="实时日志" className="h-[600px] flex flex-col mb-6">
            <div className="flex-1 overflow-y-auto space-y-2 font-mono text-sm bg-gray-900 text-green-400 p-4 rounded-lg">
              {logs.length === 0 ? <p className="text-gray-500">暂无日志...</p> : logs.map((log, i) => <p key={i}>{log}</p>)}
            </div>
          </Card>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <Card title="运行时状态">
          <div className={`space-y-2 text-sm ${isDark ? 'text-gray-300' : 'text-gray-700'}`}>
            <p>阶段：{runtimeState?.state_machine?.phase || '-'}</p>
            <p>当前快照：{runtimeState?.current_snapshot_id || '-'}</p>
            <p>主线进度：{typeof runtimeState?.main_plot_progress === 'number' ? `${Math.round(runtimeState.main_plot_progress * 100)}%` : '-'}</p>
            <p>区域数：{runtimeState?.regions?.length || 0}</p>
            <p>已埋设伏笔：{runtimeState?.hooks_planted?.length || 0}</p>
            <p>已回收伏笔：{runtimeState?.hooks_resolved?.length || 0}</p>
          </div>
        </Card>

        <Card title="工作流图">
          <div className={`space-y-2 text-sm ${isDark ? 'text-gray-300' : 'text-gray-700'}`}>
            <div className={`flex items-center gap-2 mb-2 font-medium ${isDark ? 'text-white' : 'text-gray-800'}`}>
              <Workflow size={16} />工作流节点
            </div>
            {workflowGraph?.nodes?.map((node) => (
              <div key={node.id} className={`rounded px-3 py-2 border ${isDark ? 'bg-gray-800 border-gray-700' : 'bg-gray-50 border-gray-200'}`}>
                {node.label}
              </div>
            )) || <p className={isDark ? 'text-gray-400' : 'text-gray-500'}>暂无工作流数据</p>}
          </div>
        </Card>

        <Card title="版本树 / 快照树">
          <div className="space-y-3 max-h-[360px] overflow-y-auto">
            {snapshotTree.length > 0 ? renderSnapshotTree(snapshotTree) : <p className={`text-sm ${isDark ? 'text-gray-400' : 'text-gray-500'}`}>暂无快照树数据</p>}
            <div className={`pt-2 border-t ${isDark ? 'border-gray-700' : 'border-gray-100'}`}>
              <p className={`text-xs mb-2 ${isDark ? 'text-gray-400' : 'text-gray-500'}`}>当前选择回档快照</p>
              <Input value={rollbackSnapshotId} onChange={(e) => setRollbackSnapshotId(e.target.value)} placeholder="snapshot_id" />
            </div>
          </div>
        </Card>
      </div>

      <Modal isOpen={showCommandModal} onClose={() => setShowCommandModal(false)} title="手动 Agent 指令">
        <div className="space-y-4">
          <div>
            <label className={`block text-sm font-medium mb-2 ${isDark ? 'text-gray-300' : 'text-gray-700'}`}>选择 Agent</label>
            <select
              className={`w-full px-3 py-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 ${isDark ? 'bg-gray-800 border-gray-600 text-white' : 'border-gray-300'}`}
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
            placeholder='例如：{"action": "plant_hook", "description": "..."}'
            value={agentCommand}
            onChange={(e) => setAgentCommand(e.target.value)}
          />
          <div className="flex justify-end gap-3">
            <Button variant="secondary" onClick={() => setShowCommandModal(false)}>取消</Button>
            <Button onClick={executeAgentCommand}>发送指令</Button>
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
              className={`w-full px-3 py-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 ${isDark ? 'bg-gray-800 border-gray-600 text-white' : 'border-gray-300'}`}
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
            placeholder="描述角色的外貌、性格等"
            rows={3}
          />
          <TextArea
            label="背景故事"
            value={newCharacterForm.background_story}
            onChange={(e) => setNewCharacterForm({ ...newCharacterForm, background_story: e.target.value })}
            placeholder="角色的背景故事"
            rows={3}
          />
          <Input
            label="说话风格"
            value={newCharacterForm.speech_pattern}
            onChange={(e) => setNewCharacterForm({ ...newCharacterForm, speech_pattern: e.target.value })}
            placeholder="例如：说话带古风，喜欢用成语"
          />
          <div className="flex justify-end gap-3">
            <Button variant="secondary" onClick={() => setShowAddCharacterModal(false)}>取消</Button>
            <Button onClick={handleAddCharacter} disabled={!newCharacterForm.name.trim()}>
              添加角色
            </Button>
          </div>
        </div>
      </Modal>
        </>
      )}
    </PageLayout>
  )
}
