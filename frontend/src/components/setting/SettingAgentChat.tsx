import { useState, useRef, useEffect } from 'react'
import { MessageCircle, Send, AlertTriangle, CheckCircle, X, Loader2 } from 'lucide-react'
import { Button, Card } from '@/components/ui'
import {
  chatWithSettingAgent,
  negotiateConflict,
  SettingConflict,
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

      // 如果保存了新设定，刷新设定列表
      if (response.lore_saved) {
        onLoreChange?.()
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
