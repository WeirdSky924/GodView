import { useState, useRef, useEffect } from 'react'
import { useTheme } from '@/contexts/ThemeContext'
import { sendV8Intervention, getMessageHistory } from '@/api/interventions'
import { getAgentTypeOptions, getWorkflowNodeTypes, type WorkflowNodeTypes } from '@/api/nodeTypes'
import {
  MessageSquare,
  Send,
  Bot,
  User,
  Loader2,
  AlertCircle,
} from 'lucide-react'

interface Message {
  id: string
  role: 'user' | 'agent'
  content: string
  agent_type?: string
  timestamp: Date
  response_time_ms?: number
}

interface AgentChatProps {
  executionId: string | null
  projectId: string
  onInterventionSent?: () => void
}

export default function AgentChat({
  executionId,
  projectId,
  onInterventionSent,
}: AgentChatProps) {
  const { theme } = useTheme()
  const isDark = theme === 'dark'

  const [selectedAgent, setSelectedAgent] = useState('')
  const [message, setMessage] = useState('')
  const [messages, setMessages] = useState<Message[]>([])
  const [sending, setSending] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [nodeTypes, setNodeTypes] = useState<WorkflowNodeTypes | null>(null)

  const messagesEndRef = useRef<HTMLDivElement>(null)
  const agentOptions = getAgentTypeOptions(nodeTypes)

  useEffect(() => {
    let cancelled = false

    getWorkflowNodeTypes(projectId)
      .then((data) => {
        if (!cancelled) {
          setNodeTypes(data)
        }
      })
      .catch((err) => {
        console.error('Failed to load workflow node types:', err)
      })

    return () => {
      cancelled = true
    }
  }, [projectId])

  // 加载消息历史
  useEffect(() => {
    if (!executionId) {
      setMessages([])
      return
    }

    const loadHistory = async () => {
      try {
        const history = await getMessageHistory(executionId)
        const formatted: Message[] = history.map((h) => [
          {
            id: `${h.id}-user`,
            role: 'user' as const,
            content: h.message,
            agent_type: h.agent_type,
            timestamp: new Date(h.timestamp),
          },
          h.response
            ? {
                id: `${h.id}-agent`,
                role: 'agent' as const,
                content: h.response,
                agent_type: h.agent_type,
                timestamp: new Date(h.timestamp),
              }
            : null,
        ]).flat().filter(Boolean) as Message[]

        setMessages(formatted)
      } catch (err) {
        console.error('Failed to load message history:', err)
      }
    }

    loadHistory()
  }, [executionId])

  // 滚动到底部
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const handleSend = async () => {
    if (!message.trim() || !selectedAgent || !executionId) return

    setError(null)
    setSending(true)

    // 添加用户消息
    const userMessage: Message = {
      id: `temp-${Date.now()}`,
      role: 'user',
      content: message,
      agent_type: selectedAgent,
      timestamp: new Date(),
    }
    setMessages((prev) => [...prev, userMessage])
    setMessage('')

    try {
      const result = await sendV8Intervention({
        project_id: projectId,
        workflow_execution_id: executionId,
        agent_type: selectedAgent,
        message: userMessage.content,
      })

      if (result.success) {
        // 添加 Agent 响应
        const agentMessage: Message = {
          id: result.intervention_id || `response-${Date.now()}`,
          role: 'agent',
          content: result.agent_response || '已收到消息',
          agent_type: selectedAgent,
          timestamp: new Date(),
          response_time_ms: result.response_time_ms,
        }
        setMessages((prev) => [...prev, agentMessage])
        onInterventionSent?.()
      } else {
        setError(result.message || '发送失败')
      }
    } catch (err) {
      setError('发送消息失败')
      console.error(err)
    } finally {
      setSending(false)
    }
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  if (!executionId) {
    return (
      <div
        className={`
          h-full flex items-center justify-center p-4
          ${isDark ? 'bg-gray-900' : 'bg-white'}
        `}
      >
        <p className={`text-sm ${isDark ? 'text-gray-500' : 'text-gray-400'}`}>
          启动工作流后可与 Agent 私聊
        </p>
      </div>
    )
  }

  return (
    <div className={`h-full flex flex-col ${isDark ? 'bg-gray-900' : 'bg-white'}`}>
      {/* 标题 */}
      <div
        className={`
          flex items-center gap-2 p-4 border-b
          ${isDark ? 'border-gray-700' : 'border-gray-200'}
        `}
      >
        <MessageSquare size={16} />
        <h3 className={`text-sm font-semibold ${isDark ? 'text-gray-200' : 'text-gray-700'}`}>
          Agent 私聊
        </h3>
      </div>

      {/* Agent 选择 */}
      <div className={`p-4 border-b ${isDark ? 'border-gray-700' : 'border-gray-200'}`}>
        <select
          value={selectedAgent}
          onChange={(e) => setSelectedAgent(e.target.value)}
          className={`
            w-full px-3 py-2 rounded-lg border text-sm
            ${isDark
              ? 'bg-gray-800 border-gray-600 text-white'
              : 'bg-white border-gray-300'
            }
          `}
        >
          <option value="">选择 Agent...</option>
          {agentOptions.map((opt) => (
            <option key={opt.value} value={opt.value}>
              {opt.label}
            </option>
          ))}
        </select>
      </div>

      {/* 消息列表 */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {messages.length === 0 ? (
          <div
            className={`text-center text-sm ${
              isDark ? 'text-gray-500' : 'text-gray-400'
            }`}
          >
            选择一个 Agent 开始对话
          </div>
        ) : (
          messages.map((msg) => (
            <div
              key={msg.id}
              className={`flex gap-3 ${msg.role === 'user' ? 'flex-row-reverse' : ''}`}
            >
              <div
                className={`
                  w-8 h-8 rounded-full flex items-center justify-center flex-shrink-0
                  ${msg.role === 'user'
                    ? 'bg-blue-100 text-blue-600'
                    : 'bg-green-100 text-green-600'
                  }
                `}
              >
                {msg.role === 'user' ? <User size={16} /> : <Bot size={16} />}
              </div>
              <div
                className={`
                  max-w-[80%] rounded-lg px-3 py-2 text-sm
                  ${msg.role === 'user'
                    ? 'bg-blue-500 text-white'
                    : isDark
                      ? 'bg-gray-800 text-gray-200'
                      : 'bg-gray-100 text-gray-700'
                  }
                `}
              >
                <div className="whitespace-pre-wrap">{msg.content}</div>
                {msg.response_time_ms && (
                  <div
                    className={`
                      text-xs mt-1 ${
                        msg.role === 'user' ? 'text-blue-100' : 'text-gray-400'
                      }
                    `}
                  >
                    响应时间: {msg.response_time_ms}ms
                  </div>
                )}
              </div>
            </div>
          ))
        )}
        <div ref={messagesEndRef} />
      </div>

      {/* 错误提示 */}
      {error && (
        <div className="px-4 py-2 bg-red-50 border-t border-red-100">
          <div className="flex items-center gap-2 text-sm text-red-600">
            <AlertCircle size={14} />
            {error}
          </div>
        </div>
      )}

      {/* 输入框 */}
      <div className={`p-4 border-t ${isDark ? 'border-gray-700' : 'border-gray-200'}`}>
        <div className="flex gap-2">
          <textarea
            value={message}
            onChange={(e) => setMessage(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder={selectedAgent ? '输入消息...' : '请先选择 Agent'}
            disabled={!selectedAgent || sending}
            rows={2}
            className={`
              flex-1 px-3 py-2 rounded-lg border text-sm resize-none
              ${isDark
                ? 'bg-gray-800 border-gray-600 text-white'
                : 'bg-white border-gray-300'
              }
              disabled:opacity-50
            `}
          />
          <button
            onClick={handleSend}
            disabled={!message.trim() || !selectedAgent || sending}
            className={`
              px-4 rounded-lg transition-colors
              ${sending || !message.trim() || !selectedAgent
                ? 'bg-gray-300 text-gray-500'
                : 'bg-blue-500 text-white hover:bg-blue-600'
              }
            `}
          >
            {sending ? (
              <Loader2 size={18} className="animate-spin" />
            ) : (
              <Send size={18} />
            )}
          </button>
        </div>
        <div
          className={`text-xs mt-2 ${isDark ? 'text-gray-500' : 'text-gray-400'}`}
        >
          按 Enter 发送，Shift+Enter 换行
        </div>
      </div>
    </div>
  )
}
