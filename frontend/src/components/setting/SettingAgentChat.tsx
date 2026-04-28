import { useState, useRef, useEffect } from 'react'
import { MessageCircle, Send, AlertTriangle, CheckCircle, X, Loader2, Save, Trash2, Lightbulb, Wrench } from 'lucide-react'
import { Button, Card } from '@/components/ui'
import {
  chatWithSettingAgent,
  negotiateConflict,
  savePendingLores,
  savePendingCharacters,
  savePendingHooks,
  executeLoreModification,
  SettingConflict,
  PendingLore,
  PendingCharacter,
  PendingHook,
  ImprovementSuggestion,
  createOrGetSession,
  getChatHistory,
} from '@/api/settingAgent'

interface Message {
  id: string
  role: 'user' | 'assistant'
  content: string
  timestamp: Date
  conflict?: SettingConflict
  suggestions?: ImprovementSuggestion[]
}

interface SettingAgentChatProps {
  projectId: string
  onConflictResolved?: () => void
  onLoreChange?: () => void
}

const severityColors: Record<string, string> = {
  low: 'bg-gray-100 text-gray-700 border-gray-200',
  medium: 'bg-yellow-100 text-yellow-700 border-yellow-200',
  high: 'bg-orange-100 text-orange-700 border-orange-200',
  critical: 'bg-red-100 text-red-700 border-red-200',
}

const severityLabels: Record<string, string> = {
  low: '轻微',
  medium: '中等',
  high: '严重',
  critical: '致命',
}

// 获取 severity 标签，带默认值
const getSeverityLabel = (severity: string): string => {
  return severityLabels[severity] || '未知'
}

// 获取 severity 颜色，带默认值
const getSeverityColor = (severity: string): string => {
  return severityColors[severity] || 'bg-gray-100 text-gray-700 border-gray-200'
}

export default function SettingAgentChat({
  projectId,
  onConflictResolved,
  onLoreChange,
}: SettingAgentChatProps) {
  const [messages, setMessages] = useState<Message[]>([])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [currentConflict, setCurrentConflict] = useState<SettingConflict | null>(null)
  const [pendingLores, setPendingLores] = useState<PendingLore[]>([])
  const [pendingCharacters, setPendingCharacters] = useState<PendingCharacter[]>([])
  const [pendingHooks, setPendingHooks] = useState<PendingHook[]>([])
  const [showConfirmModal, setShowConfirmModal] = useState(false)
  const [showCharacterModal, setShowCharacterModal] = useState(false)
  const [showHookModal, setShowHookModal] = useState(false)
  const [removedLoreIndices, setRemovedLoreIndices] = useState<Set<number>>(new Set())
  const [removedCharacterIndices, setRemovedCharacterIndices] = useState<Set<number>>(new Set())
  const [removedHookIndices, setRemovedHookIndices] = useState<Set<number>>(new Set())
  const [improvementSuggestions, setImprovementSuggestions] = useState<ImprovementSuggestion[]>([])
  const [showImprovementModal, setShowImprovementModal] = useState(false)
  const [executingSuggestion, setExecutingSuggestion] = useState<string | null>(null)
  const [sessionId, setSessionId] = useState<string | null>(null)
  const messagesEndRef = useRef<HTMLDivElement>(null)

  // 初始化或恢复持久化会话
  useEffect(() => {
    const hydrateSession = async () => {
      const storageKey = `settingAgentSession:${projectId}:management`
      const storedSessionId = localStorage.getItem(storageKey) || undefined
      try {
        const session = await createOrGetSession(projectId, 'management', storedSessionId)
        setSessionId(session.session_id)
        localStorage.setItem(storageKey, session.session_id)
        const history = await getChatHistory(projectId, session.session_id)
        const historyMessages: Array<{
          role: 'user' | 'assistant'
          content: string
          timestamp?: string
          created_at?: string
        }> = history.messages || history.history || []
        const restored: Message[] = historyMessages
          .filter((msg) => msg.role === 'user' || msg.role === 'assistant')
          .map((msg, index) => {
            const timestamp = msg.created_at || msg.timestamp
            return {
              id: `restored_${index}_${timestamp || Date.now()}`,
              role: msg.role,
              content: msg.content,
              timestamp: new Date(timestamp || Date.now()),
            }
          })
        if (restored.length > 0) {
          setMessages(restored)
        } else {
          setMessages([
            {
              id: 'welcome',
              role: 'assistant',
              content: '你好！我是设定管理者 Agent。我可以帮助你维护世界观设定的一致性，检测和处理设定冲突。请问有什么需要我帮助的吗？',
              timestamp: new Date(),
            },
          ])
        }
        setPendingLores(history.pending_lores || session.pending_lores || [])
        setPendingCharacters(history.pending_characters || session.pending_characters || [])
        setPendingHooks(history.pending_hooks || session.pending_hooks || [])
      } catch (error) {
        console.error('Failed to hydrate setting agent session:', error)
      }
    }
    void hydrateSession()
  }, [projectId])

  // 自动滚动到底部
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const sendMessage = async () => {
    if (!input.trim() || loading) return

    const userMessage: Message = {
      id: `user_${Date.now()}`,
      role: 'user',
      content: input.trim(),
      timestamp: new Date(),
    }

    setMessages((prev) => [...prev, userMessage])
    setInput('')
    setLoading(true)

    try {
      const requestId = `setting_chat_${Date.now()}_${Math.random().toString(36).slice(2, 9)}`
      const response = await chatWithSettingAgent(projectId, input.trim(), undefined, {
        sessionId: sessionId || undefined,
        requestId,
      })
      if (response.session_id && response.session_id !== sessionId) {
        setSessionId(response.session_id)
        localStorage.setItem(`settingAgentSession:${projectId}:management`, response.session_id)
      }

      const assistantMessage: Message = {
        id: `assistant_${Date.now()}`,
        role: 'assistant',
        content: response.message,
        timestamp: new Date(),
      }

      setMessages((prev) => [...prev, assistantMessage])

      // 检查是否有待确认的设定
      if (response.pending_lores && response.pending_lores.length > 0) {
        const lores = response.pending_lores
        setPendingLores(lores)
        setRemovedLoreIndices(new Set()) // 重置已删除列表
        setShowConfirmModal(true)
        // 添加提示消息
        setMessages((prev) => [
          ...prev,
          {
            id: `pending_${Date.now()}`,
            role: 'assistant',
            content: `我检测到您确认了以下新设定，请确认是否保存到设定库：\n\n${lores.map((l, i) => `${i + 1}. ${l.title} (${l.category})`).join('\n')}`,
            timestamp: new Date(),
          },
        ])
      }

      // 检查是否有待确认的角色
      if (response.pending_characters && response.pending_characters.length > 0) {
        const characters = response.pending_characters
        setPendingCharacters(characters)
        setRemovedCharacterIndices(new Set())
        setShowCharacterModal(true)
        setMessages((prev) => [
          ...prev,
          {
            id: `pending_character_${Date.now()}`,
            role: 'assistant',
            content: `我检测到以下可保存的角色，请确认是否保存到角色库：\n\n${characters.map((c, i) => `${i + 1}. ${c.name} (${c.importance_tier})`).join('\n')}`,
            timestamp: new Date(),
          },
        ])
      }

      // 检查是否有待确认的伏笔
      if (response.pending_hooks && response.pending_hooks.length > 0) {
        const hooks = response.pending_hooks
        setPendingHooks(hooks)
        setRemovedHookIndices(new Set())
        setShowHookModal(true)
        setMessages((prev) => [
          ...prev,
          {
            id: `pending_hook_${Date.now()}`,
            role: 'assistant',
            content: `我检测到以下可单独管理的伏笔，请确认是否保存到伏笔库：\n\n${hooks.map((h, i) => `${i + 1}. ${h.title} (${h.hook_type})`).join('\n')}`,
            timestamp: new Date(),
          },
        ])
      }

      if (response.improvement_suggestions && response.improvement_suggestions.length > 0) {
        const suggestions = response.improvement_suggestions
        setImprovementSuggestions(suggestions)
        setShowImprovementModal(true)
        // 添加提示消息
        setMessages((prev) => [
          ...prev,
          {
            id: `improvement_${Date.now()}`,
            role: 'assistant',
            content: `💡 我分析了现有设定，发现 ${suggestions.length} 个可能的改进点。点击查看详情。`,
            timestamp: new Date(),
            suggestions: suggestions,
          },
        ])
      }
    } catch (error) {
      console.error('Chat error:', error)
      setMessages((prev) => [
        ...prev,
        {
          id: `error_${Date.now()}`,
          role: 'assistant',
          content: '抱歉，我遇到了一些问题。请稍后再试。',
          timestamp: new Date(),
        },
      ])
    } finally {
      setLoading(false)
    }
  }

  // 保存用户确认的设定
  const handleConfirmSave = async () => {
    // 过滤掉已删除的设定
    const loresToSave = pendingLores.filter((_, idx) => !removedLoreIndices.has(idx))
    if (loresToSave.length === 0) {
      setMessages((prev) => [
        ...prev,
        {
          id: `no_lores_${Date.now()}`,
          role: 'assistant',
          content: '没有需要保存的设定。',
          timestamp: new Date(),
        },
      ])
      setPendingLores([])
      setRemovedLoreIndices(new Set())
      setShowConfirmModal(false)
      return
    }

    setLoading(true)
    try {
      const result = await savePendingLores(projectId, loresToSave, {
        sessionId: sessionId || undefined,
        requestId: `save_lores_${Date.now()}_${Math.random().toString(36).slice(2, 9)}`,
      })
      if (result.success) {
        setMessages((prev) => [
          ...prev,
          {
            id: `saved_${Date.now()}`,
            role: 'assistant',
            content: result.message,
            timestamp: new Date(),
          },
        ])
        onLoreChange?.()
      }
    } catch (error) {
      console.error('Save error:', error)
    } finally {
      setPendingLores([])
      setRemovedLoreIndices(new Set())
      setShowConfirmModal(false)
      setLoading(false)
    }
  }

  // 拒绝保存设定
  const handleRejectSave = () => {
    setMessages((prev) => [
      ...prev,
      {
        id: `rejected_${Date.now()}`,
        role: 'assistant',
        content: '已取消保存设定。',
        timestamp: new Date(),
      },
    ])
    setPendingLores([])
    setRemovedLoreIndices(new Set())
    setShowConfirmModal(false)
  }

  // 切换设定项的删除状态
  const toggleLoreRemoval = (index: number) => {
    setRemovedLoreIndices((prev) => {
      const newSet = new Set(prev)
      if (newSet.has(index)) {
        newSet.delete(index)
      } else {
        newSet.add(index)
      }
      return newSet
    })
  }

  // 保存用户确认的角色
  const handleConfirmSaveCharacters = async () => {
    // 过滤掉已删除的角色
    const charactersToSave = pendingCharacters.filter((_, idx) => !removedCharacterIndices.has(idx))
    if (charactersToSave.length === 0) {
      setMessages((prev) => [
        ...prev,
        {
          id: `no_chars_${Date.now()}`,
          role: 'assistant',
          content: '没有需要保存的角色。',
          timestamp: new Date(),
        },
      ])
      setPendingCharacters([])
      setRemovedCharacterIndices(new Set())
      setShowCharacterModal(false)
      return
    }

    setLoading(true)
    try {
      const result = await savePendingCharacters(projectId, charactersToSave, {
        sessionId: sessionId || undefined,
        requestId: `save_characters_${Date.now()}_${Math.random().toString(36).slice(2, 9)}`,
      })
      if (result.success) {
        setMessages((prev) => [
          ...prev,
          {
            id: `saved_char_${Date.now()}`,
            role: 'assistant',
            content: result.message,
            timestamp: new Date(),
          },
        ])
        onLoreChange?.()
      }
    } catch (error) {
      console.error('Save characters error:', error)
    } finally {
      setPendingCharacters([])
      setRemovedCharacterIndices(new Set())
      setShowCharacterModal(false)
      setLoading(false)
    }
  }

  // 拒绝保存角色
  const handleRejectSaveCharacters = () => {
    setMessages((prev) => [
      ...prev,
      {
        id: `rejected_char_${Date.now()}`,
        role: 'assistant',
        content: '已取消保存角色。',
        timestamp: new Date(),
      },
    ])
    setPendingCharacters([])
    setRemovedCharacterIndices(new Set())
    setShowCharacterModal(false)
  }

  // 切换角色项的删除状态
  const toggleCharacterRemoval = (index: number) => {
    setRemovedCharacterIndices((prev) => {
      const newSet = new Set(prev)
      if (newSet.has(index)) {
        newSet.delete(index)
      } else {
        newSet.add(index)
      }
      return newSet
    })
  }

  // 保存用户确认的伏笔
  const handleConfirmSaveHooks = async () => {
    const hooksToSave = pendingHooks.filter((_, idx) => !removedHookIndices.has(idx))
    if (hooksToSave.length === 0) {
      setMessages((prev) => [
        ...prev,
        {
          id: `no_hooks_${Date.now()}`,
          role: 'assistant',
          content: '没有需要保存的伏笔。',
          timestamp: new Date(),
        },
      ])
      setPendingHooks([])
      setRemovedHookIndices(new Set())
      setShowHookModal(false)
      return
    }

    setLoading(true)
    try {
      const result = await savePendingHooks(projectId, hooksToSave, {
        sessionId: sessionId || undefined,
        requestId: `save_hooks_${Date.now()}_${Math.random().toString(36).slice(2, 9)}`,
      })
      if (result.success) {
        setMessages((prev) => [
          ...prev,
          {
            id: `saved_hook_${Date.now()}`,
            role: 'assistant',
            content: result.message,
            timestamp: new Date(),
          },
        ])
        onLoreChange?.()
      }
    } catch (error) {
      console.error('Save hooks error:', error)
    } finally {
      setPendingHooks([])
      setRemovedHookIndices(new Set())
      setShowHookModal(false)
      setLoading(false)
    }
  }

  // 拒绝保存伏笔
  const handleRejectSaveHooks = () => {
    setMessages((prev) => [
      ...prev,
      {
        id: `rejected_hook_${Date.now()}`,
        role: 'assistant',
        content: '已取消保存伏笔。',
        timestamp: new Date(),
      },
    ])
    setPendingHooks([])
    setRemovedHookIndices(new Set())
    setShowHookModal(false)
  }

  // 切换伏笔项的删除状态
  const toggleHookRemoval = (index: number) => {
    setRemovedHookIndices((prev) => {
      const newSet = new Set(prev)
      if (newSet.has(index)) {
        newSet.delete(index)
      } else {
        newSet.add(index)
      }
      return newSet
    })
  }

  // 执行设定改进建议
  const handleExecuteImprovement = async (suggestion: ImprovementSuggestion) => {
    setExecutingSuggestion(suggestion.id)
    try {
      const result = await executeLoreModification(projectId, suggestion)
      if (result.success) {
        setMessages((prev) => [
          ...prev,
          {
            id: `executed_${Date.now()}`,
            role: 'assistant',
            content: `✅ ${result.message || '修改已执行'}`,
            timestamp: new Date(),
          },
        ])
        // 从列表中移除已执行的建议
        setImprovementSuggestions((prev) => prev.filter((s) => s.id !== suggestion.id))
        onLoreChange?.()
      } else {
        setMessages((prev) => [
          ...prev,
          {
            id: `error_${Date.now()}`,
            role: 'assistant',
            content: `❌ 执行失败: ${result.error || '未知错误'}`,
            timestamp: new Date(),
          },
        ])
      }
    } catch (error) {
      console.error('Execute improvement error:', error)
      setMessages((prev) => [
        ...prev,
        {
          id: `error_${Date.now()}`,
          role: 'assistant',
          content: '执行修改时发生错误，请重试。',
          timestamp: new Date(),
        },
      ])
    } finally {
      setExecutingSuggestion(null)
      // 如果没有更多建议，关闭弹窗
      if (improvementSuggestions.length <= 1) {
        setShowImprovementModal(false)
      }
    }
  }

  // 忽略改进建议
  const handleIgnoreImprovement = (suggestionId: string) => {
    setImprovementSuggestions((prev) => prev.filter((s) => s.id !== suggestionId))
    if (improvementSuggestions.length <= 1) {
      setShowImprovementModal(false)
      setMessages((prev) => [
        ...prev,
        {
          id: `ignored_${Date.now()}`,
          role: 'assistant',
          content: '已忽略所有改进建议。',
          timestamp: new Date(),
        },
      ])
    }
  }

  // 关闭改进建议弹窗
  const handleCloseImprovementModal = () => {
    setShowImprovementModal(false)
  }

  const handleSuggestionClick = async (suggestion: string, conflictId: string) => {
    setLoading(true)
    try {
      const result = await negotiateConflict(projectId, conflictId, `接受建议：${suggestion}`)

      if (result.status === 'resolved') {
        setCurrentConflict(null)
        setMessages((prev) => [
          ...prev,
          {
            id: `resolved_${Date.now()}`,
            role: 'assistant',
            content: '冲突已解决！你可以继续进行其他操作。',
            timestamp: new Date(),
          },
        ])
        onConflictResolved?.()
      } else if (result.message) {
        setMessages((prev) => [
          ...prev,
          {
            id: `negotiate_${Date.now()}`,
            role: 'assistant',
            content: result.message!,
            timestamp: new Date(),
            conflict: result.conflict,
          },
        ])
      }
    } catch (error) {
      console.error('Negotiate error:', error)
    } finally {
      setLoading(false)
    }
  }

  const handleOverride = async (conflictId: string) => {
    setLoading(true)
    try {
      await negotiateConflict(projectId, conflictId, '强制覆盖')
      setCurrentConflict(null)
      setMessages((prev) => [
        ...prev,
        {
          id: `override_${Date.now()}`,
          role: 'assistant',
          content: '已强制覆盖冲突设定。请注意这可能影响世界观的一致性。',
          timestamp: new Date(),
        },
      ])
      onConflictResolved?.()
    } catch (error) {
      console.error('Override error:', error)
    } finally {
      setLoading(false)
    }
  }

  const handleCancel = async (conflictId: string) => {
    setLoading(true)
    try {
      await negotiateConflict(projectId, conflictId, '取消变更')
      setCurrentConflict(null)
      setMessages((prev) => [
        ...prev,
        {
          id: `cancel_${Date.now()}`,
          role: 'assistant',
          content: '已取消变更请求。',
          timestamp: new Date(),
        },
      ])
    } catch (error) {
      console.error('Cancel error:', error)
    } finally {
      setLoading(false)
    }
  }

  const showConflictDialog = (conflict: SettingConflict) => {
    setCurrentConflict(conflict)
    setMessages((prev) => [
      ...prev,
      {
        id: `conflict_${conflict.id}`,
        role: 'assistant',
        content: `检测到设定冲突：${conflict.description}`,
        timestamp: new Date(),
        conflict,
      },
    ])
  }

  return (
    <div className="flex flex-col h-full">
      {/* 消息列表 - 可滚动区域 */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4 min-h-0">
        {messages.map((msg) => (
          <div
            key={msg.id}
            className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}
          >
            <div
              className={`max-w-[80%] rounded-lg px-4 py-2 ${
                msg.role === 'user'
                  ? 'bg-blue-600 text-white'
                  : 'bg-gray-100 text-gray-800'
              }`}
            >
              <p className="text-sm whitespace-pre-wrap">{msg.content}</p>
              <p
                className={`text-xs mt-1 ${
                  msg.role === 'user' ? 'text-blue-200' : 'text-gray-500'
                }`}
              >
                {msg.timestamp.toLocaleTimeString()}
              </p>

              {/* 冲突解决按钮 */}
              {msg.conflict && (
                <div className="mt-3 pt-3 border-t border-gray-200">
                  <div
                    className={`text-xs px-2 py-1 rounded inline-block mb-2 ${
                      getSeverityColor(msg.conflict.severity || 'medium')
                    }`}
                  >
                    {getSeverityLabel(msg.conflict.severity || 'medium')}冲突
                  </div>
                  <div className="space-y-2">
                    <p className="text-xs text-gray-600">解决方案：</p>
                    {(msg.conflict.resolution_suggestions || []).map((suggestion, idx) => (
                      <button
                        key={idx}
                        onClick={() => handleSuggestionClick(suggestion, msg.conflict!.id)}
                        className="block w-full text-left text-xs bg-white hover:bg-blue-50 border border-gray-200 rounded px-3 py-2 transition-colors"
                        disabled={loading}
                      >
                        {idx + 1}. {suggestion}
                      </button>
                    ))}
                    <div className="flex gap-2 mt-3">
                      <button
                        onClick={() => handleOverride(msg.conflict!.id)}
                        className="text-xs text-orange-600 hover:text-orange-700"
                        disabled={loading}
                      >
                        强制覆盖
                      </button>
                      <button
                        onClick={() => handleCancel(msg.conflict!.id)}
                        className="text-xs text-gray-600 hover:text-gray-700"
                        disabled={loading}
                      >
                        取消变更
                      </button>
                    </div>
                  </div>
                </div>
              )}
            </div>
          </div>
        ))}

        {/* 冲突提示对话框 */}
        {currentConflict && !messages.some((m) => m.conflict?.id === currentConflict.id) && (
          <div className="bg-orange-50 border border-orange-200 rounded-lg p-4">
            <div className="flex items-start gap-2">
              <AlertTriangle className="text-orange-500 flex-shrink-0 mt-0.5" size={16} />
              <div className="flex-1">
                <p className="text-sm font-medium text-orange-800">
                  {currentConflict.description}
                </p>
                <p className="text-xs text-orange-600 mt-1">
                  严重程度：{getSeverityLabel(currentConflict.severity || 'medium')}
                </p>
              </div>
            </div>
          </div>
        )}

        {loading && (
          <div className="flex justify-start">
            <div className="bg-gray-100 rounded-lg px-4 py-2">
              <Loader2 size={16} className="animate-spin text-gray-500" />
            </div>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* 设定确认弹窗 */}
      {showConfirmModal && pendingLores.length > 0 && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg shadow-xl max-w-lg w-full mx-4 max-h-[80vh] overflow-hidden">
            <div className="p-4 border-b bg-blue-50 flex items-center justify-between">
              <h3 className="font-semibold text-lg text-gray-800 flex items-center gap-2">
                <CheckCircle className="text-blue-600" size={20} />
                确认保存设定
              </h3>
              <button onClick={handleRejectSave} className="text-gray-400 hover:text-gray-600">
                <X size={20} />
              </button>
            </div>
            <div className="p-4 max-h-96 overflow-y-auto space-y-4">
              {pendingLores.map((lore, idx) => {
                const isRemoved = removedLoreIndices.has(idx)
                return (
                  <div
                    key={idx}
                    className={`border rounded-lg p-3 transition-all ${
                      isRemoved
                        ? 'bg-red-50 border-red-200 opacity-60'
                        : 'bg-gray-50'
                    }`}
                  >
                    <div className="flex items-center justify-between mb-2">
                      <span className={`font-medium ${isRemoved ? 'text-gray-400 line-through' : 'text-gray-800'}`}>
                        {lore.title}
                      </span>
                      <div className="flex items-center gap-2">
                        <span className={`text-xs px-2 py-0.5 rounded ${
                          isRemoved
                            ? 'bg-gray-100 text-gray-400'
                            : 'bg-blue-100 text-blue-700'
                        }`}>
                          {lore.category}
                        </span>
                        <button
                          onClick={() => toggleLoreRemoval(idx)}
                          className={`p-1 rounded transition-colors ${
                            isRemoved
                              ? 'text-green-600 hover:bg-green-100'
                              : 'text-red-500 hover:bg-red-100'
                          }`}
                          title={isRemoved ? '恢复' : '移除'}
                        >
                          {isRemoved ? (
                            <CheckCircle size={16} />
                          ) : (
                            <Trash2 size={16} />
                          )}
                        </button>
                      </div>
                    </div>
                    {!isRemoved && (
                      <>
                        {lore.summary && (
                          <p className="text-sm text-gray-600 mb-2">{lore.summary}</p>
                        )}
                        <p className="text-xs text-gray-500 line-clamp-3">{lore.content}</p>
                        {lore.keywords.length > 0 && (
                          <div className="flex flex-wrap gap-1 mt-2">
                            {lore.keywords.map((kw, i) => (
                              <span key={i} className="text-xs px-2 py-0.5 bg-gray-200 text-gray-600 rounded">
                                {kw}
                              </span>
                            ))}
                          </div>
                        )}
                      </>
                    )}
                    {isRemoved && (
                      <p className="text-xs text-red-500 italic">已标记移除，将不会保存</p>
                    )}
                  </div>
                )
              })}
            </div>
            <div className="p-4 border-t bg-gray-50 flex justify-between items-center">
              <span className="text-sm text-gray-500">
                将保存 {pendingLores.length - removedLoreIndices.size} 个设定
              </span>
              <div className="flex gap-3">
                <Button
                  variant="secondary"
                  onClick={handleRejectSave}
                  disabled={loading}
                >
                  全部取消
                </Button>
                <Button
                  onClick={handleConfirmSave}
                  disabled={loading || removedLoreIndices.size === pendingLores.length}
                >
                  {loading ? (
                    <Loader2 size={16} className="animate-spin mr-1" />
                  ) : (
                    <Save size={16} className="mr-1" />
                  )}
                  确认保存
                </Button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* 角色确认弹窗 */}
      {showCharacterModal && pendingCharacters.length > 0 && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg shadow-xl max-w-lg w-full mx-4 max-h-[80vh] overflow-hidden">
            <div className="p-4 border-b bg-green-50 flex items-center justify-between">
              <h3 className="font-semibold text-lg text-gray-800 flex items-center gap-2">
                <CheckCircle className="text-green-600" size={20} />
                确认保存角色
              </h3>
              <button onClick={handleRejectSaveCharacters} className="text-gray-400 hover:text-gray-600">
                <X size={20} />
              </button>
            </div>
            <div className="p-4 max-h-96 overflow-y-auto space-y-4">
              {pendingCharacters.map((char, idx) => {
                const isRemoved = removedCharacterIndices.has(idx)
                return (
                  <div
                    key={idx}
                    className={`border rounded-lg p-3 transition-all ${
                      isRemoved
                        ? 'bg-red-50 border-red-200 opacity-60'
                        : 'bg-gray-50'
                    }`}
                  >
                    <div className="flex items-center justify-between mb-2">
                      <span className={`font-medium ${isRemoved ? 'text-gray-400 line-through' : 'text-gray-800'}`}>
                        {char.name}
                      </span>
                      <div className="flex items-center gap-2">
                        <span className={`text-xs px-2 py-0.5 rounded ${
                          isRemoved
                            ? 'bg-gray-100 text-gray-400'
                            : 'bg-green-100 text-green-700'
                        }`}>
                          {char.importance_tier}
                        </span>
                        <button
                          onClick={() => toggleCharacterRemoval(idx)}
                          className={`p-1 rounded transition-colors ${
                            isRemoved
                              ? 'text-green-600 hover:bg-green-100'
                              : 'text-red-500 hover:bg-red-100'
                          }`}
                          title={isRemoved ? '恢复' : '移除'}
                        >
                          {isRemoved ? (
                            <CheckCircle size={16} />
                          ) : (
                            <Trash2 size={16} />
                          )}
                        </button>
                      </div>
                    </div>
                    {!isRemoved && (
                      <>
                        {char.description && (
                          <p className="text-sm text-gray-600 mb-2">{char.description}</p>
                        )}
                        {char.appearance && (
                          <p className="text-xs text-gray-500">外貌：{char.appearance}</p>
                        )}
                        {char.personality && (
                          <p className="text-xs text-gray-500">性格：{char.personality}</p>
                        )}
                        {char.goals && char.goals.length > 0 && (
                          <div className="flex flex-wrap gap-1 mt-2">
                            {char.goals.map((goal, i) => (
                              <span key={i} className="text-xs px-2 py-0.5 bg-gray-200 text-gray-600 rounded">
                                {goal}
                              </span>
                            ))}
                          </div>
                        )}
                      </>
                    )}
                    {isRemoved && (
                      <p className="text-xs text-red-500 italic">已标记移除，将不会保存</p>
                    )}
                  </div>
                )
              })}
            </div>
            <div className="p-4 border-t bg-gray-50 flex justify-between items-center">
              <span className="text-sm text-gray-500">
                将保存 {pendingCharacters.length - removedCharacterIndices.size} 个角色
              </span>
              <div className="flex gap-3">
                <Button
                  variant="secondary"
                  onClick={handleRejectSaveCharacters}
                  disabled={loading}
                >
                  全部取消
                </Button>
                <Button
                  onClick={handleConfirmSaveCharacters}
                  disabled={loading || removedCharacterIndices.size === pendingCharacters.length}
                >
                  {loading ? (
                    <Loader2 size={16} className="animate-spin mr-1" />
                  ) : (
                    <Save size={16} className="mr-1" />
                  )}
                  确认保存
                </Button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* 伏笔确认弹窗 */}
      {showHookModal && pendingHooks.length > 0 && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg shadow-xl max-w-lg w-full mx-4 max-h-[80vh] overflow-hidden">
            <div className="p-4 border-b bg-purple-50 flex items-center justify-between">
              <h3 className="font-semibold text-lg text-gray-800 flex items-center gap-2">
                <CheckCircle className="text-purple-600" size={20} />
                确认保存伏笔
              </h3>
              <button onClick={handleRejectSaveHooks} className="text-gray-400 hover:text-gray-600">
                <X size={20} />
              </button>
            </div>
            <div className="p-4 max-h-96 overflow-y-auto space-y-4">
              {pendingHooks.map((hook, idx) => {
                const isRemoved = removedHookIndices.has(idx)
                return (
                  <div
                    key={idx}
                    className={`border rounded-lg p-3 transition-all ${
                      isRemoved
                        ? 'bg-red-50 border-red-200 opacity-60'
                        : 'bg-gray-50'
                    }`}
                  >
                    <div className="flex items-center justify-between mb-2 gap-2">
                      <span className={`font-medium ${isRemoved ? 'text-gray-400 line-through' : 'text-gray-800'}`}>
                        {hook.title}
                      </span>
                      <div className="flex items-center gap-2">
                        <span className={`text-xs px-2 py-0.5 rounded ${
                          isRemoved
                            ? 'bg-gray-100 text-gray-400'
                            : 'bg-purple-100 text-purple-700'
                        }`}>
                          {hook.hook_type}
                        </span>
                        <button
                          onClick={() => toggleHookRemoval(idx)}
                          className={`p-1 rounded transition-colors ${
                            isRemoved
                              ? 'text-green-600 hover:bg-green-100'
                              : 'text-red-500 hover:bg-red-100'
                          }`}
                          title={isRemoved ? '恢复' : '移除'}
                        >
                          {isRemoved ? (
                            <CheckCircle size={16} />
                          ) : (
                            <Trash2 size={16} />
                          )}
                        </button>
                      </div>
                    </div>
                    {!isRemoved && (
                      <>
                        {hook.description && (
                          <p className="text-sm text-gray-600 mb-2">{hook.description}</p>
                        )}
                        {hook.plant_context && (
                          <p className="text-xs text-gray-500 mb-1">埋设情境：{hook.plant_context}</p>
                        )}
                        {hook.resolution_hint && (
                          <p className="text-xs text-gray-500 mb-1">回收提示：{hook.resolution_hint}</p>
                        )}
                        <div className="flex flex-wrap gap-1 mt-2">
                          <span className="text-xs px-2 py-0.5 bg-gray-200 text-gray-600 rounded">
                            状态：{hook.status}
                          </span>
                          <span className="text-xs px-2 py-0.5 bg-gray-200 text-gray-600 rounded">
                            优先级：{hook.priority}
                          </span>
                          {hook.related_characters.map((item: string, i: number) => (
                            <span key={`char-${i}`} className="text-xs px-2 py-0.5 bg-blue-100 text-blue-700 rounded">
                              角色：{item}
                            </span>
                          ))}
                          {hook.related_locations.map((item: string, i: number) => (
                            <span key={`loc-${i}`} className="text-xs px-2 py-0.5 bg-green-100 text-green-700 rounded">
                              地点：{item}
                            </span>
                          ))}
                          {hook.related_objects.map((item: string, i: number) => (
                            <span key={`obj-${i}`} className="text-xs px-2 py-0.5 bg-amber-100 text-amber-700 rounded">
                              物件：{item}
                            </span>
                          ))}
                        </div>
                      </>
                    )}
                    {isRemoved && (
                      <p className="text-xs text-red-500 italic">已标记移除，将不会保存</p>
                    )}
                  </div>
                )
              })}
            </div>
            <div className="p-4 border-t bg-gray-50 flex justify-between items-center">
              <span className="text-sm text-gray-500">
                将保存 {pendingHooks.length - removedHookIndices.size} 个伏笔
              </span>
              <div className="flex gap-3">
                <Button
                  variant="secondary"
                  onClick={handleRejectSaveHooks}
                  disabled={loading}
                >
                  全部取消
                </Button>
                <Button
                  onClick={handleConfirmSaveHooks}
                  disabled={loading || removedHookIndices.size === pendingHooks.length}
                >
                  {loading ? (
                    <Loader2 size={16} className="animate-spin mr-1" />
                  ) : (
                    <Save size={16} className="mr-1" />
                  )}
                  确认保存
                </Button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* 设定改进建议弹窗 */}
      {showImprovementModal && improvementSuggestions.length > 0 && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg shadow-xl max-w-2xl w-full mx-4 max-h-[80vh] overflow-hidden">
            <div className="p-4 border-b bg-amber-50 flex items-center justify-between">
              <h3 className="font-semibold text-lg text-gray-800 flex items-center gap-2">
                <Lightbulb className="text-amber-600" size={20} />
                设定改进建议
              </h3>
              <button onClick={handleCloseImprovementModal} className="text-gray-400 hover:text-gray-600">
                <X size={20} />
              </button>
            </div>
            <div className="p-4 max-h-96 overflow-y-auto space-y-4">
              {improvementSuggestions.map((suggestion) => {
                const typeLabels: Record<string, string> = {
                  conflict: '冲突检测',
                  missing: '缺失补充',
                  priority: '优先级调整',
                  optimize: '内容优化',
                  relation: '关联增强',
                }
                const typeColors: Record<string, string> = {
                  conflict: 'bg-red-100 text-red-700',
                  missing: 'bg-blue-100 text-blue-700',
                  priority: 'bg-purple-100 text-purple-700',
                  optimize: 'bg-green-100 text-green-700',
                  relation: 'bg-orange-100 text-orange-700',
                }
                const priorityColors: Record<string, string> = {
                  low: 'text-gray-500',
                  medium: 'text-amber-600',
                  high: 'text-red-600',
                }

                return (
                  <div key={suggestion.id} className="border rounded-lg p-4 bg-gray-50">
                    <div className="flex items-start justify-between mb-3">
                      <div className="flex items-center gap-2">
                        <span className={`text-xs px-2 py-1 rounded ${typeColors[suggestion.type] || 'bg-gray-100'}`}>
                          {typeLabels[suggestion.type] || suggestion.type}
                        </span>
                        {suggestion.target_lore_title && (
                          <span className="text-sm text-gray-600">→ {suggestion.target_lore_title}</span>
                        )}
                      </div>
                      <span className={`text-xs font-medium ${priorityColors[suggestion.priority]}`}>
                        {suggestion.priority === 'high' ? '重要' : suggestion.priority === 'medium' ? '中等' : '建议'}
                      </span>
                    </div>

                    <div className="space-y-2">
                      <div>
                        <span className="text-xs font-medium text-gray-500">问题：</span>
                        <p className="text-sm text-gray-700">{suggestion.issue}</p>
                      </div>
                      <div>
                        <span className="text-xs font-medium text-gray-500">建议：</span>
                        <p className="text-sm text-gray-800">{suggestion.suggestion}</p>
                      </div>
                      {suggestion.suggested_content && (
                        <div className="bg-white border rounded p-2">
                          <span className="text-xs font-medium text-gray-500">建议内容：</span>
                          <p className="text-sm text-gray-600 mt-1 whitespace-pre-wrap">
                            {suggestion.suggested_content.length > 200
                              ? suggestion.suggested_content.slice(0, 200) + '...'
                              : suggestion.suggested_content}
                          </p>
                        </div>
                      )}
                      {suggestion.reason && (
                        <p className="text-xs text-gray-500 italic">原因：{suggestion.reason}</p>
                      )}
                    </div>

                    <div className="flex gap-2 mt-3 pt-3 border-t">
                      <Button
                        size="sm"
                        onClick={() => handleExecuteImprovement(suggestion)}
                        disabled={executingSuggestion === suggestion.id}
                      >
                        {executingSuggestion === suggestion.id ? (
                          <Loader2 size={14} className="animate-spin mr-1" />
                        ) : (
                          <Wrench size={14} className="mr-1" />
                        )}
                        执行修改
                      </Button>
                      <Button
                        size="sm"
                        variant="secondary"
                        onClick={() => handleIgnoreImprovement(suggestion.id)}
                        disabled={executingSuggestion === suggestion.id}
                      >
                        忽略
                      </Button>
                    </div>
                  </div>
                )
              })}
            </div>
            <div className="p-4 border-t bg-gray-50 flex justify-between items-center">
              <span className="text-sm text-gray-500">
                还有 {improvementSuggestions.length} 个建议待处理
              </span>
              <Button variant="secondary" onClick={handleCloseImprovementModal}>
                稍后处理
              </Button>
            </div>
          </div>
        </div>
      )}

      {/* 输入框 */}
      <div className="p-4 border-t flex-shrink-0">
        <div className="flex gap-2">
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && !e.shiftKey && sendMessage()}
            placeholder="输入消息..."
            className="flex-1 px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
            disabled={loading}
          />
          <Button onClick={sendMessage} disabled={!input.trim() || loading}>
            <Send size={18} />
          </Button>
        </div>
      </div>
    </div>
  )
}
