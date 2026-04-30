/**
 * 章节大纲管理页面
 * 与 Plot Outline Agent 协作管理章节大纲
 */

import { useEffect, useState } from 'react'
import { Card, Button, Input } from '@/components/ui'
import PageLayout from '@/components/PageLayout'
import { useProject } from '@/contexts/ProjectContext'
import { useTheme } from '@/contexts/ThemeContext'
import {
  getOutlines,
  getOutline,
  updateOutline,
  approveOutline,
  chatWithAgent,
  deleteOutline,
  type ChapterOutline,
  type SceneOutline,
  type EmotionPoint,
  type OutlineStatus,
} from '@/api/outlines'
import {
  BookOpen, Plus, Edit2, Check, MessageSquare, Send, RefreshCw,
  ChevronLeft, ChevronRight, Play, Sparkles, Target, Users,
  MapPin, Clock, Zap, CheckCircle, X, Loader2, Trash2
} from 'lucide-react'

// 情绪类型映射
const EMOTION_LABELS: Record<string, { label: string; color: string }> = {
  joy: { label: '喜悦', color: 'text-yellow-500' },
  anger: { label: '愤怒', color: 'text-red-500' },
  sadness: { label: '悲伤', color: 'text-blue-500' },
  fear: { label: '恐惧', color: 'text-purple-500' },
  surprise: { label: '惊讶', color: 'text-orange-500' },
  disgust: { label: '厌恶', color: 'text-green-500' },
  anticipation: { label: '期待', color: 'text-cyan-500' },
  trust: { label: '信任', color: 'text-teal-500' },
  tension: { label: '紧张', color: 'text-amber-500' },
  relief: { label: '释然', color: 'text-lime-500' },
  neutral: { label: '中性', color: 'text-gray-500' },
}

// 场景类型映射
const SCENE_TYPE_LABELS: Record<string, string> = {
  dialogue: '对话',
  action: '动作',
  description: '描写',
  transition: '过渡',
  climax: '高潮',
  resolution: '结局',
  flashback: '回忆',
  foreshadow: '伏笔',
}

// 状态映射
const STATUS_CONFIG: Record<OutlineStatus, { label: string; color: string }> = {
  draft: { label: '草稿', color: 'bg-gray-100 text-gray-700' },
  approved: { label: '已审批', color: 'bg-green-100 text-green-700' },
  in_writing: { label: '写作中', color: 'bg-blue-100 text-blue-700' },
  completed: { label: '已完成', color: 'bg-purple-100 text-purple-700' },
  revision: { label: '需修改', color: 'bg-orange-100 text-orange-700' },
}

export default function Outlines() {
  const { theme } = useTheme()
  const isDark = theme === 'dark'
  const { currentProject } = useProject()

  // 状态
  const [outlines, setOutlines] = useState<ChapterOutline[]>([])
  const [selectedChapter, setSelectedChapter] = useState<number | null>(null)
  const [currentOutline, setCurrentOutline] = useState<ChapterOutline | null>(null)
  const [loading, setLoading] = useState(false)

  // 聊天状态
  const [showChat, setShowChat] = useState(false)
  const [chatMessages, setChatMessages] = useState<Array<{ role: 'user' | 'assistant'; content: string }>>([])
  const [chatInput, setChatInput] = useState('')
  const [sendingMessage, setSendingMessage] = useState(false)

  // 编辑状态
  const [editingScene, setEditingScene] = useState<SceneOutline | null>(null)
  const [showSceneEditor, setShowSceneEditor] = useState(false)

  const mergeOutlines = (current: ChapterOutline[], incoming: ChapterOutline[]) => {
    const outlineMap = new Map(current.map(outline => [outline.chapter_number, outline]))

    for (const outline of incoming) {
      outlineMap.set(outline.chapter_number, outline)
    }

    return Array.from(outlineMap.values()).sort((a, b) => a.chapter_number - b.chapter_number)
  }

  const upsertOutline = (outline: ChapterOutline) => {
    setOutlines(prev => mergeOutlines(prev, [outline]))
  }

  const upsertOutlines = (incoming: ChapterOutline[]) => {
    setOutlines(prev => mergeOutlines(prev, incoming))
  }

  const removeOutlineFromState = (chapterNumber: number) => {
    const remaining = outlines.filter(outline => outline.chapter_number !== chapterNumber)
    const fallbackOutline = remaining[0] ?? null

    setOutlines(remaining)
    setSelectedChapter(fallbackOutline?.chapter_number ?? null)
    setCurrentOutline(fallbackOutline)
  }

  // 加载大纲列表
  useEffect(() => {
    if (currentProject?.id) {
      loadOutlines()
    }
  }, [currentProject?.id])

  const loadOutlines = async () => {
    if (!currentProject?.id) return
    setLoading(true)
    try {
      const result = await getOutlines(currentProject.id)
      setOutlines(result.outlines)
      // 默认选择第一章或最新的章节
      if (result.outlines.length > 0 && !selectedChapter) {
        selectChapter(result.outlines[0].chapter_number)
      }
    } catch (error) {
      console.error('Failed to load outlines:', error)
    } finally {
      setLoading(false)
    }
  }

  const selectChapter = async (chapterNumber: number) => {
    if (!currentProject?.id) return
    setSelectedChapter(chapterNumber)
    setLoading(true)
    try {
      const outline = await getOutline(currentProject.id, chapterNumber)
      setCurrentOutline(outline)
    } catch (error) {
      console.error('Failed to load outline:', error)
      setCurrentOutline(null)
    } finally {
      setLoading(false)
    }
  }

  const handleApprove = async () => {
    if (!currentProject?.id || !selectedChapter) return
    try {
      const updated = await approveOutline(currentProject.id, selectedChapter, 'user')
      setCurrentOutline(updated)
      upsertOutline(updated)
    } catch (error) {
      console.error('Failed to approve outline:', error)
    }
  }

  const handleDelete = async () => {
    if (!currentProject?.id || !selectedChapter) return
    const keepContent = confirm(
      `删除第${selectedChapter}章大纲时，默认保留已经生成的小说正文。\n\n点击“确定”：仅删除大纲，保留正文。\n点击“取消”：继续选择是否同时软删除正文。`
    )
    let softDeleteGeneratedChapters = false

    if (!keepContent) {
      softDeleteGeneratedChapters = confirm(
        `是否同时软删除第${selectedChapter}章大纲关联生成的小说正文？\n\n正文会被标记为已删除，默认列表不再显示，但不是物理删除。`
      )
      if (!softDeleteGeneratedChapters) return
    }

    try {
      const result = await deleteOutline(currentProject.id, selectedChapter, { softDeleteGeneratedChapters })
      removeOutlineFromState(selectedChapter)
      alert(result.message)
    } catch (error) {
      console.error('Failed to delete outline:', error)
      alert('删除失败，请稍后再试')
    }
  }

  const handleStartFirstChapterChat = () => {
    // 设置为第一章
    setSelectedChapter(1)
    // 打开聊天面板
    setShowChat(true)
    // 设置初始消息
    const initialMessage = '请帮我生成第一章大纲'
    setChatInput(initialMessage)
    // 自动发送消息
    sendChatMessage(initialMessage)
  }

  const sendChatMessage = async (message: string) => {
    if (!currentProject?.id) return

    const chapterNumber = selectedChapter || 1
    setSendingMessage(true)

    // 添加用户消息
    setChatMessages(prev => [...prev, { role: 'user' as const, content: message }])

    try {
      const response = await chatWithAgent(currentProject.id, chapterNumber, message)
      setChatMessages(prev => [...prev, { role: 'assistant' as const, content: response.message }])

      // 处理多章大纲保存
      const savedOutlines = response.saved_outlines
      if (savedOutlines && savedOutlines.length > 0) {
        setChatMessages(prev => [...prev, {
          role: 'assistant' as const,
          content: `✅ 已保存 ${savedOutlines.length} 章大纲草稿：${savedOutlines.map(o => `第${o.chapter_number}章`).join('、')}`
        }])
        upsertOutlines(savedOutlines)
        const firstSaved = savedOutlines[0]
        setCurrentOutline(firstSaved)
        setSelectedChapter(firstSaved.chapter_number)
      } else if (response.saved_outline) {
        setCurrentOutline(response.saved_outline)
        setSelectedChapter(response.saved_outline.chapter_number)
        upsertOutline(response.saved_outline)
      } else if (response.outline_updates) {
        setCurrentOutline(prev => prev ? { ...prev, ...response.outline_updates } : prev)
      }
    } catch (error) {
      console.error('Chat error:', error)
      setChatMessages(prev => [
        ...prev,
        { role: 'assistant' as const, content: '抱歉，发生了错误。请稍后再试。' }
      ])
    } finally {
      setSendingMessage(false)
    }
  }

  const handleSendMessage = async () => {
    if (!currentProject?.id || !selectedChapter || !chatInput.trim()) return
    const message = chatInput.trim()
    setChatInput('')
    await sendChatMessage(message)
  }

  const handleQuickCommand = (command: string) => {
    setChatInput(command)
  }

  // 情绪曲线可视化
  const renderEmotionCurve = () => {
    if (!currentOutline?.emotion_curve?.points) return null

    const points = currentOutline.emotion_curve.points
    const height = 100
    const width = 300

    return (
      <div className="mt-4">
        <h4 className={`text-sm font-medium mb-2 ${isDark ? 'text-gray-300' : 'text-gray-700'}`}>
          情绪曲线
        </h4>
        <svg width={width} height={height} className="w-full">
          {/* 背景网格 */}
          <line x1="0" y1={height / 2} x2={width} y2={height / 2} stroke={isDark ? '#374151' : '#e5e7eb'} strokeWidth="1" />

          {/* 情绪曲线 */}
          <polyline
            fill="none"
            stroke={isDark ? '#60a5fa' : '#3b82f6'}
            strokeWidth="2"
            points={points.map((p, i) => {
              const x = (p.position * width)
              const y = height - (p.intensity * height * 0.8) - 10
              return `${x},${y}`
            }).join(' ')}
          />

          {/* 数据点 */}
          {points.map((p, i) => {
            const x = (p.position * width)
            const y = height - (p.intensity * height * 0.8) - 10
            const emotionInfo = EMOTION_LABELS[p.emotion] || EMOTION_LABELS.neutral
            return (
              <g key={i}>
                <circle cx={x} cy={y} r="4" className={isDark ? 'fill-blue-400' : 'fill-blue-500'} />
                <text
                  x={x}
                  y={y - 8}
                  textAnchor="middle"
                  className={`text-xs ${emotionInfo.color}`}
                >
                  {emotionInfo.label}
                </text>
              </g>
            )
          })}
        </svg>
      </div>
    )
  }

  return (
    <PageLayout
      title="章节大纲"
      description="与 Plot Outline Agent 协作管理章节大纲"
    >
      <div className="h-full flex">
        {/* 左侧：章节列表 */}
        <div className={`w-64 border-r flex-shrink-0 ${isDark ? 'border-gray-700 bg-gray-800' : 'border-gray-200 bg-white'}`}>
          <div className={`p-4 border-b ${isDark ? 'border-gray-700' : 'border-gray-200'}`}>
            <div className="flex items-center justify-between mb-2">
              <h2 className={`text-lg font-semibold ${isDark ? 'text-white' : 'text-gray-800'}`}>
                章节大纲
              </h2>
              <Button size="sm" onClick={() => {
                const newChapter = outlines.length > 0 ? Math.max(...outlines.map(o => o.chapter_number)) + 1 : 1
                setSelectedChapter(newChapter)
                setCurrentOutline(null)
              }}>
                <Plus className="w-4 h-4" />
              </Button>
            </div>
            <p className={`text-sm ${isDark ? 'text-gray-400' : 'text-gray-500'}`}>
              {currentProject?.name || '未选择项目'}
            </p>
          </div>

          <div className="overflow-y-auto h-[calc(100vh-200px)]">
            {loading && outlines.length === 0 ? (
              <div className={`p-4 text-center ${isDark ? 'text-gray-400' : 'text-gray-500'}`}>
                加载中...
              </div>
            ) : outlines.length === 0 ? (
              <div className={`p-4 text-center ${isDark ? 'text-gray-400' : 'text-gray-500'}`}>
                <BookOpen className="w-12 h-12 mx-auto mb-2 opacity-50" />
                <p className="text-sm">暂无大纲</p>
                <Button size="sm" className="mt-2" onClick={handleStartFirstChapterChat}>
                  生成第一章
                </Button>
              </div>
            ) : (
              <div className="p-2 space-y-1">
                {outlines.map((outline) => {
                  const status = STATUS_CONFIG[outline.status]
                  const isSelected = selectedChapter === outline.chapter_number
                  return (
                    <button
                      key={outline.id}
                      onClick={() => selectChapter(outline.chapter_number)}
                      className={`w-full text-left p-3 rounded-lg transition-colors ${
                        isSelected
                          ? isDark ? 'bg-blue-900 text-blue-100' : 'bg-blue-50 text-blue-900'
                          : isDark ? 'hover:bg-gray-700 text-gray-200' : 'hover:bg-gray-50 text-gray-700'
                      }`}
                    >
                      <div className="flex items-center justify-between">
                        <span className="font-medium text-sm">
                          第{outline.chapter_number}章
                        </span>
                        <span className={`px-2 py-0.5 text-xs rounded ${status.color}`}>
                          {status.label}
                        </span>
                      </div>
                      <p className={`text-xs mt-1 truncate ${isDark ? 'text-gray-400' : 'text-gray-500'}`}>
                        {outline.title}
                      </p>
                      <div className={`flex items-center gap-2 mt-1 text-xs ${isDark ? 'text-gray-500' : 'text-gray-400'}`}>
                        <span>{outline.scenes.length} 场景</span>
                        <span>·</span>
                        <span>{outline.target_word_count} 字</span>
                      </div>
                    </button>
                  )
                })}
              </div>
            )}
          </div>
        </div>

        {/* 中间：大纲详情 */}
        <div className="flex-1 overflow-y-auto">
          {selectedChapter ? (
            currentOutline ? (
              <div className="p-6">
                {/* 头部信息 */}
                <div className="mb-6">
                  <div className="flex items-center justify-between mb-2">
                    <h2 className={`text-2xl font-bold ${isDark ? 'text-white' : 'text-gray-800'}`}>
                      第{currentOutline.chapter_number}章：{currentOutline.title}
                    </h2>
                    <div className="flex items-center gap-2">
                      <span className={`px-3 py-1 text-sm rounded-full ${STATUS_CONFIG[currentOutline.status].color}`}>
                        {STATUS_CONFIG[currentOutline.status].label}
                      </span>
                      {currentOutline.status === 'draft' && (
                        <Button size="sm" onClick={handleApprove}>
                          <Check className="w-4 h-4 mr-1" />
                          审批
                        </Button>
                      )}
                      <Button size="sm" variant="secondary" onClick={handleDelete}>
                        <Trash2 className="w-4 h-4 mr-1" />
                        删除
                      </Button>
                    </div>
                  </div>
                  <p className={`text-sm ${isDark ? 'text-gray-400' : 'text-gray-600'}`}>
                    {currentOutline.summary}
                  </p>
                </div>

                {/* 章节目标 */}
                {currentOutline.chapter_goals.length > 0 && (
                  <Card className="p-4 mb-6">
                    <h3 className={`text-sm font-medium mb-2 ${isDark ? 'text-gray-300' : 'text-gray-700'}`}>
                      <Target className="w-4 h-4 inline mr-1" />
                      章节目标
                    </h3>
                    <div className="flex flex-wrap gap-2">
                      {currentOutline.chapter_goals.map((goal, i) => (
                        <span
                          key={i}
                          className={`px-3 py-1 text-sm rounded-full ${
                            isDark ? 'bg-gray-700 text-gray-200' : 'bg-gray-100 text-gray-700'
                          }`}
                        >
                          {goal}
                        </span>
                      ))}
                    </div>
                  </Card>
                )}

                {/* 场景列表 */}
                <Card className="p-4 mb-6">
                  <div className="flex items-center justify-between mb-4">
                    <h3 className={`text-sm font-medium ${isDark ? 'text-gray-300' : 'text-gray-700'}`}>
                      <Play className="w-4 h-4 inline mr-1" />
                      场景规划 ({currentOutline.scenes.length} 场景)
                    </h3>
                    <Button size="sm" variant="secondary" onClick={() => setShowSceneEditor(true)}>
                      <Edit2 className="w-4 h-4 mr-1" />
                      编辑场景
                    </Button>
                  </div>

                  {currentOutline.scenes.length === 0 ? (
                    <div className={`text-center py-8 ${isDark ? 'text-gray-400' : 'text-gray-500'}`}>
                      <p>暂无场景规划</p>
                      <Button size="sm" className="mt-2" onClick={() => setShowChat(true)}>
                        与 Agent 讨论
                      </Button>
                    </div>
                  ) : (
                    <div className="space-y-3">
                      {currentOutline.scenes.map((scene, index) => (
                        <div
                          key={scene.id}
                          className={`p-4 rounded-lg border ${
                            isDark ? 'bg-gray-800 border-gray-700' : 'bg-gray-50 border-gray-200'
                          }`}
                        >
                          <div className="flex items-center justify-between mb-2">
                            <div className="flex items-center gap-2">
                              <span className={`text-xs px-2 py-0.5 rounded ${
                                isDark ? 'bg-blue-900 text-blue-300' : 'bg-blue-100 text-blue-700'
                              }`}>
                                场景 {scene.scene_number}
                              </span>
                              <span className={`font-medium ${isDark ? 'text-gray-200' : 'text-gray-800'}`}>
                                {scene.title}
                              </span>
                            </div>
                            <span className={`text-xs px-2 py-0.5 rounded ${
                              isDark ? 'bg-gray-700 text-gray-300' : 'bg-gray-200 text-gray-600'
                            }`}>
                              {SCENE_TYPE_LABELS[scene.scene_type] || scene.scene_type}
                            </span>
                          </div>

                          <p className={`text-sm mb-2 ${isDark ? 'text-gray-400' : 'text-gray-600'}`}>
                            {scene.summary}
                          </p>

                          <div className="flex items-center gap-4 text-xs">
                            {scene.location && (
                              <span className={`flex items-center gap-1 ${isDark ? 'text-gray-400' : 'text-gray-500'}`}>
                                <MapPin className="w-3 h-3" />
                                {scene.location}
                              </span>
                            )}
                            {scene.time_of_day && (
                              <span className={`flex items-center gap-1 ${isDark ? 'text-gray-400' : 'text-gray-500'}`}>
                                <Clock className="w-3 h-3" />
                                {scene.time_of_day}
                              </span>
                            )}
                            {scene.participating_characters.length > 0 && (
                              <span className={`flex items-center gap-1 ${isDark ? 'text-gray-400' : 'text-gray-500'}`}>
                                <Users className="w-3 h-3" />
                                {scene.participating_characters.length} 角色
                              </span>
                            )}
                            <span className={`flex items-center gap-1 ${isDark ? 'text-gray-400' : 'text-gray-500'}`}>
                              约 {scene.estimated_words} 字
                            </span>
                          </div>

                          {/* 情绪变化 */}
                          <div className="mt-2 flex items-center gap-2">
                            <span className="text-xs">情绪：</span>
                            <span className={`text-xs ${EMOTION_LABELS[scene.emotion_start]?.color || ''}`}>
                              {EMOTION_LABELS[scene.emotion_start]?.label || scene.emotion_start}
                            </span>
                            <span className="text-xs">→</span>
                            <span className={`text-xs ${EMOTION_LABELS[scene.emotion_end]?.color || ''}`}>
                              {EMOTION_LABELS[scene.emotion_end]?.label || scene.emotion_end}
                            </span>
                          </div>

                          {/* 关键事件 */}
                          {scene.key_events.length > 0 && (
                            <div className="mt-2">
                              <p className={`text-xs mb-1 ${isDark ? 'text-gray-500' : 'text-gray-400'}`}>关键事件：</p>
                              <div className="flex flex-wrap gap-1">
                                {scene.key_events.map((event, i) => (
                                  <span
                                    key={i}
                                    className={`text-xs px-2 py-0.5 rounded ${
                                      isDark ? 'bg-gray-700 text-gray-300' : 'bg-gray-200 text-gray-600'
                                    }`}
                                  >
                                    {event}
                                  </span>
                                ))}
                              </div>
                            </div>
                          )}
                        </div>
                      ))}
                    </div>
                  )}
                </Card>

                {/* 情绪曲线 */}
                {currentOutline.emotion_curve && (
                  <Card className="p-4 mb-6">
                    <h3 className={`text-sm font-medium mb-2 ${isDark ? 'text-gray-300' : 'text-gray-700'}`}>
                      <Zap className="w-4 h-4 inline mr-1" />
                      情绪曲线
                    </h3>
                    {renderEmotionCurve()}
                    {currentOutline.emotion_curve.reader_experience_goal && (
                      <p className={`text-sm mt-2 ${isDark ? 'text-gray-400' : 'text-gray-600'}`}>
                        读者体验目标：{currentOutline.emotion_curve.reader_experience_goal}
                      </p>
                    )}
                  </Card>
                )}

                {/* 伏笔管理 */}
                {(currentOutline.hooks_planted.length > 0 || currentOutline.hooks_resolved.length > 0) && (
                  <Card className="p-4 mb-6">
                    <h3 className={`text-sm font-medium mb-2 ${isDark ? 'text-gray-300' : 'text-gray-700'}`}>
                      伏笔管理
                    </h3>
                    <div className="grid grid-cols-2 gap-4">
                      <div>
                        <p className={`text-xs mb-1 ${isDark ? 'text-gray-400' : 'text-gray-500'}`}>埋设伏笔</p>
                        {currentOutline.hooks_planted.length > 0 ? (
                          <ul className={`text-sm ${isDark ? 'text-gray-300' : 'text-gray-700'}`}>
                            {currentOutline.hooks_planted.map((hook, i) => (
                              <li key={i} className="flex items-center gap-1">
                                <span className="w-1.5 h-1.5 rounded-full bg-blue-500" />
                                {hook}
                              </li>
                            ))}
                          </ul>
                        ) : (
                          <p className={`text-sm ${isDark ? 'text-gray-500' : 'text-gray-400'}`}>无</p>
                        )}
                      </div>
                      <div>
                        <p className={`text-xs mb-1 ${isDark ? 'text-gray-400' : 'text-gray-500'}`}>回收伏笔</p>
                        {currentOutline.hooks_resolved.length > 0 ? (
                          <ul className={`text-sm ${isDark ? 'text-gray-300' : 'text-gray-700'}`}>
                            {currentOutline.hooks_resolved.map((hook, i) => (
                              <li key={i} className="flex items-center gap-1">
                                <CheckCircle className="w-3 h-3 text-green-500" />
                                {hook}
                              </li>
                            ))}
                          </ul>
                        ) : (
                          <p className={`text-sm ${isDark ? 'text-gray-500' : 'text-gray-400'}`}>无</p>
                        )}
                      </div>
                    </div>
                  </Card>
                )}

                {/* 底部操作栏 */}
                <div className={`sticky bottom-0 p-4 border-t ${isDark ? 'bg-gray-900 border-gray-700' : 'bg-white border-gray-200'}`}>
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <Button
                        variant="secondary"
                        onClick={() => selectedChapter > 1 && selectChapter(selectedChapter - 1)}
                        disabled={selectedChapter <= 1}
                      >
                        <ChevronLeft className="w-4 h-4" />
                        上一章
                      </Button>
                      <Button
                        variant="secondary"
                        onClick={() => selectChapter(selectedChapter + 1)}
                        disabled={!outlines.find(o => o.chapter_number === selectedChapter + 1)}
                      >
                        下一章
                        <ChevronRight className="w-4 h-4" />
                      </Button>
                    </div>
                    <div className="flex items-center gap-2">
                      <Button variant="secondary" onClick={() => setShowChat(true)}>
                        <MessageSquare className="w-4 h-4 mr-1" />
                        与 Agent 讨论
                      </Button>
                      <Button variant="secondary" onClick={() => {
                        setShowChat(true)
                        setChatInput('请帮我重新生成这一章的大纲')
                      }}>
                        <RefreshCw className="w-4 h-4 mr-1" />
                        重新生成
                      </Button>
                    </div>
                  </div>
                </div>
              </div>
            ) : (
              // 空状态：章节未创建大纲
              <div className="h-full flex items-center justify-center">
                <div className={`text-center max-w-md ${isDark ? 'text-gray-400' : 'text-gray-500'}`}>
                  <BookOpen className="w-16 h-16 mx-auto mb-4 opacity-50" />
                  <h3 className={`text-lg font-medium mb-2 ${isDark ? 'text-gray-200' : 'text-gray-700'}`}>
                    第{selectedChapter}章大纲
                  </h3>
                  <p className="mb-4">该章节尚未生成大纲</p>
                  <div className="flex justify-center gap-2">
                    <Button variant="secondary" onClick={() => setShowChat(true)}>
                      <MessageSquare className="w-4 h-4 mr-1" />
                      与 Agent 讨论
                    </Button>
                    <Button onClick={() => {
                      setShowChat(true)
                      setChatInput(`请帮我生成第${selectedChapter}章的大纲`)
                    }}>
                      <Sparkles className="w-4 h-4 mr-1" />
                      生成大纲
                    </Button>
                  </div>
                </div>
              </div>
            )
          ) : (
            // 未选择章节
            <div className="h-full flex items-center justify-center">
              <div className={`text-center ${isDark ? 'text-gray-400' : 'text-gray-500'}`}>
                <BookOpen className="w-16 h-16 mx-auto mb-4 opacity-50" />
                <p>请选择一个章节查看或创建大纲</p>
              </div>
            </div>
          )}
        </div>

        {/* 右侧：Agent 聊天面板 */}
        {showChat && (
          <div className={`w-96 border-l flex-shrink-0 flex flex-col ${isDark ? 'bg-gray-800 border-gray-700' : 'bg-white border-gray-200'}`}>
            <div className={`p-4 border-b flex items-center justify-between ${isDark ? 'border-gray-700' : 'border-gray-200'}`}>
              <div className="flex items-center gap-2">
                <div className="w-8 h-8 rounded-full bg-gradient-to-r from-purple-500 to-pink-500 flex items-center justify-center">
                  <Sparkles className="w-4 h-4 text-white" />
                </div>
                <div>
                  <h3 className={`font-medium ${isDark ? 'text-white' : 'text-gray-800'}`}>Plot Outline Agent</h3>
                  <p className={`text-xs ${isDark ? 'text-gray-400' : 'text-gray-500'}`}>
                    第{selectedChapter || '?'}章大纲规划
                  </p>
                </div>
              </div>
              <Button variant="ghost" size="sm" onClick={() => setShowChat(false)}>
                <X className="w-4 h-4" />
              </Button>
            </div>

            {/* 快捷命令 */}
            <div className={`p-3 border-b ${isDark ? 'border-gray-700' : 'border-gray-200'}`}>
              <p className={`text-xs mb-2 ${isDark ? 'text-gray-400' : 'text-gray-500'}`}>快捷命令</p>
              <div className="flex flex-wrap gap-1">
                {[
                  '生成3个场景',
                  '添加一个高潮场景',
                  '调整情绪曲线',
                  '检查伏笔一致性',
                  '优化场景顺序',
                ].map((cmd) => (
                  <button
                    key={cmd}
                    onClick={() => handleQuickCommand(cmd)}
                    className={`px-2 py-1 text-xs rounded ${
                      isDark ? 'bg-gray-700 text-gray-300 hover:bg-gray-600' : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
                    }`}
                  >
                    {cmd}
                  </button>
                ))}
              </div>
            </div>

            {/* 聊天消息 */}
            <div className="flex-1 overflow-y-auto p-4 space-y-4">
              {chatMessages.length === 0 ? (
                <div className={`text-center py-8 ${isDark ? 'text-gray-400' : 'text-gray-500'}`}>
                  <MessageSquare className="w-8 h-8 mx-auto mb-2 opacity-50" />
                  <p className="text-sm">开始与 Agent 讨论{selectedChapter ? `第${selectedChapter}章` : ''}大纲</p>
                </div>
              ) : (
                chatMessages.map((msg, i) => (
                  <div
                    key={i}
                    className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}
                  >
                    <div
                      className={`max-w-[85%] p-3 rounded-lg ${
                        msg.role === 'user'
                          ? 'bg-blue-500 text-white'
                          : isDark ? 'bg-gray-700 text-gray-200' : 'bg-gray-100 text-gray-800'
                      }`}
                    >
                      <p className="text-sm whitespace-pre-wrap">{msg.content}</p>
                    </div>
                  </div>
                ))
              )}
              {sendingMessage && (
                <div className="flex justify-start">
                  <div className={`p-3 rounded-lg ${isDark ? 'bg-gray-700' : 'bg-gray-100'}`}>
                    <Loader2 className="w-4 h-4 animate-spin" />
                  </div>
                </div>
              )}
            </div>

            {/* 输入框 */}
            <div className={`p-4 border-t ${isDark ? 'border-gray-700' : 'border-gray-200'}`}>
              <div className="flex gap-2">
                <Input
                  value={chatInput}
                  onChange={(e) => setChatInput(e.target.value)}
                  placeholder="描述你想要的大纲..."
                  onKeyDown={(e) => e.key === 'Enter' && !e.shiftKey && handleSendMessage()}
                  className="flex-1"
                />
                <Button onClick={handleSendMessage} disabled={!chatInput.trim() || sendingMessage}>
                  <Send className="w-4 h-4" />
                </Button>
              </div>
            </div>
          </div>
        )}
      </div>
    </PageLayout>
  )
}
