import { useState, useRef, useEffect } from 'react'
import { MessageCircle, Send, AlertTriangle, CheckCircle, X, Loader2, Save, Trash2 } from 'lucide-react'
import { Button, Card } from '@/components/ui'
import {
  chatWithSettingAgent,
  negotiateConflict,
  savePendingLores,
  savePendingCharacters,
  SettingConflict,
  PendingLore,
  PendingCharacter,
} from '@/api/settingAgent'

interface Message {
  id: string
  role: 'user' | 'assistant'
  content: string
  timestamp: Date
  conflict?: SettingConflict
}

interface SettingAgentChatProps {
  projectId: string
  onConflictResolved?: () => void
  onLoreChange?: () => void
}

const severityColors = {
  low: 'bg-gray-100 text-gray-700 border-gray-200',
  medium: 'bg-yellow-100 text-yellow-700 border-yellow-200',
  high: 'bg-orange-100 text-orange-700 border-orange-200',
  critical: 'bg-red-100 text-red-700 border-red-200',
}

const severityLabels = {
  low: '轻微',
  medium: '中等',
  high: '严重',
  critical: '致命',
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
  const [showConfirmModal, setShowConfirmModal] = useState(false)
  const [showCharacterModal, setShowCharacterModal] = useState(false)
  const messagesEndRef = useRef<HTMLDivElement>(null)

  // 初始欢迎消息
  useEffect(() => {
    setMessages([
      {
        id: 'welcome',
        role: 'assistant',
        content: '你好！我是设定管理者 Agent。我可以帮助你维护世界观设定的一致性，检测和处理设定冲突。请问有什么需要我帮助的吗？',
        timestamp: new Date(),
      },
    ])
  }, [])

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
      const response = await chatWithSettingAgent(projectId, input.trim())

      const assistantMessage: Message = {
        id: `assistant_${Date.now()}`,
        role: 'assistant',
        content: response.response,
        timestamp: new Date(),
      }

      setMessages((prev) => [...prev, assistantMessage])

      // 检查是否有待确认的设定
      if (response.pending_lores && response.pending_lores.length > 0) {
        setPendingLores(response.pending_lores)
        setShowConfirmModal(true)
        // 添加提示消息
        setMessages((prev) => [
          ...prev,
          {
            id: `pending_${Date.now()}`,
            role: 'assistant',
            content: `我检测到您确认了以下新设定，请确认是否保存到设定库：\n\n${response.pending_lores.map((l, i) => `${i + 1}. ${l.title} (${l.category})`).join('\n')}`,
            timestamp: new Date(),
          },
        ])
      }

      // 检查是否有待确认的角色
      if (response.pending_characters && response.pending_characters.length > 0) {
        setPendingCharacters(response.pending_characters)
        setShowCharacterModal(true)
        // 添加提示消息
        setMessages((prev) => [
          ...prev,
          {
            id: `pending_char_${Date.now()}`,
            role: 'assistant',
            content: `我检测到您确认了以下新角色，请确认是否保存到角色库：\n\n${response.pending_characters.map((c, i) => `${i + 1}. ${c.name} (${c.importance_tier})`).join('\n')}`,
            timestamp: new Date(),
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
    if (pendingLores.length === 0) return

    setLoading(true)
    try {
      const result = await savePendingLores(projectId, pendingLores)
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
    setShowConfirmModal(false)
  }

  // 保存用户确认的角色
  const handleConfirmSaveCharacters = async () => {
    if (pendingCharacters.length === 0) return

    setLoading(true)
    try {
      const result = await savePendingCharacters(projectId, pendingCharacters)
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
    setShowCharacterModal(false)
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
      } else if (result.response) {
        setMessages((prev) => [
          ...prev,
          {
            id: `negotiate_${Date.now()}`,
            role: 'assistant',
            content: result.response!,
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
                      severityColors[msg.conflict.severity]
                    }`}
                  >
                    {severityLabels[msg.conflict.severity]}冲突
                  </div>
                  <div className="space-y-2">
                    <p className="text-xs text-gray-600">解决方案：</p>
                    {msg.conflict.resolution_suggestions.map((suggestion, idx) => (
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
                  严重程度：{severityLabels[currentConflict.severity]}
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
              {pendingLores.map((lore, idx) => (
                <div key={idx} className="border rounded-lg p-3 bg-gray-50">
                  <div className="flex items-center justify-between mb-2">
                    <span className="font-medium text-gray-800">{lore.title}</span>
                    <span className="text-xs px-2 py-0.5 bg-blue-100 text-blue-700 rounded">
                      {lore.category}
                    </span>
                  </div>
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
                </div>
              ))}
            </div>
            <div className="p-4 border-t bg-gray-50 flex justify-end gap-3">
              <Button
                variant="secondary"
                onClick={handleRejectSave}
                disabled={loading}
              >
                <Trash2 size={16} className="mr-1" />
                取消
              </Button>
              <Button
                onClick={handleConfirmSave}
                disabled={loading}
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
              {pendingCharacters.map((char, idx) => (
                <div key={idx} className="border rounded-lg p-3 bg-gray-50">
                  <div className="flex items-center justify-between mb-2">
                    <span className="font-medium text-gray-800">{char.name}</span>
                    <span className="text-xs px-2 py-0.5 bg-green-100 text-green-700 rounded">
                      {char.importance_tier}
                    </span>
                  </div>
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
                </div>
              ))}
            </div>
            <div className="p-4 border-t bg-gray-50 flex justify-end gap-3">
              <Button
                variant="secondary"
                onClick={handleRejectSaveCharacters}
                disabled={loading}
              >
                <Trash2 size={16} className="mr-1" />
                取消
              </Button>
              <Button
                onClick={handleConfirmSaveCharacters}
                disabled={loading}
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
