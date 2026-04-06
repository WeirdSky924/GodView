import { useState, useEffect } from 'react'
import { Card, Button } from '@/components/ui'
import { getChapters, simulateReader } from '@/api/chapters'
import { Eye, TrendingUp, AlertTriangle, Heart, Zap, Clock } from 'lucide-react'
import type { Chapter, ReaderSimulationResult } from '@/api/chapters'

interface ReaderMetrics {
  engagement_score: number
  emotional_arc: Array<{ chapter: string; value: number; emotion: string }>
  suspense_level: number
  pacing_score: number
  character_development: number
  plot_cohesion: number
  predicted_retention: number
  highlighted_moments: Array<{ chapter: string; timestamp: string; description: string }>
  reader_feedback: Array<{ aspect: string; score: number; comments: string }>
}

function mapReaderMetrics(chapter: Chapter | undefined, result: ReaderSimulationResult): ReaderMetrics {
  const scores = result.scores || {
    opening: 0,
    pacing: 0,
    suspense: 0,
    character: 0,
    emotion: 0,
    flow: 0,
  }

  return {
    engagement_score: Number((((scores.opening + scores.flow + scores.emotion) / 3) / 2).toFixed(1)),
    emotional_arc: [
      { chapter: chapter?.title || '当前章节', value: Math.round((scores.emotion / 10) * 100), emotion: '情绪波动' },
      { chapter: '沉浸', value: Math.round((scores.opening / 10) * 100), emotion: '投入' },
      { chapter: '悬念', value: Math.round((scores.suspense / 10) * 100), emotion: '紧张' },
    ],
    suspense_level: (scores.suspense / 10) * 100,
    pacing_score: Number((scores.pacing / 2).toFixed(1)),
    character_development: Number((scores.character / 2).toFixed(1)),
    plot_cohesion: Number((scores.flow / 2).toFixed(1)),
    predicted_retention: Math.round((result.overall / 10) * 100),
    highlighted_moments: (result.suggestions || []).slice(0, 3).map((item, index) => ({
      chapter: chapter?.title || '当前章节',
      timestamp: `0${index + 1}:00`,
      description: item,
    })),
    reader_feedback: [
      { aspect: '开篇吸引力', score: Number((scores.opening / 2).toFixed(1)), comments: result.comments },
      { aspect: '节奏把控', score: Number((scores.pacing / 2).toFixed(1)), comments: result.comments },
      { aspect: '悬念设置', score: Number((scores.suspense / 2).toFixed(1)), comments: result.comments },
    ],
  }
}

export default function ReaderSimulator() {
  const [chapters, setChapters] = useState<Chapter[]>([])
  const [selectedChapter, setSelectedChapter] = useState<string>('')
  const [metrics, setMetrics] = useState<ReaderMetrics | null>(null)
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    loadChapters()
  }, [])

  const loadChapters = async () => {
    try {
      const data = await getChapters()
      setChapters(data)
      if (data.length > 0) {
        setSelectedChapter(data[0].id || '')
      }
    } catch (error) {
      console.error('Failed to load chapters:', error)
    }
  }

  const simulateReading = async () => {
    if (!selectedChapter) return
    setLoading(true)

    try {
      const chapter = chapters.find((item) => item.id === selectedChapter)
      const result = await simulateReader(selectedChapter)
      setMetrics(mapReaderMetrics(chapter, result))
    } catch (error) {
      console.error('Failed to simulate reading:', error)
    } finally {
      setLoading(false)
    }
  }

  const selectedChapterData = chapters.find(c => c.id === selectedChapter)

  const getScoreColor = (score: number) => {
    if (score >= 4) return 'text-green-600'
    if (score >= 3) return 'text-yellow-600'
    return 'text-red-600'
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-8">
        <h1 className="text-3xl font-bold text-gray-800">👁️ 读者体验模拟器</h1>
        <Button onClick={simulateReading} disabled={!selectedChapter || loading}>
          <Eye size={18} className="mr-2" />
          {loading ? '模拟中...' : '开始阅读模拟'}
        </Button>
      </div>

      <Card className="mb-6">
        <div className="flex items-center gap-4">
          <label className="text-sm font-medium text-gray-700">选择章节：</label>
          <select
            className="px-3 py-2 border border-gray-300 rounded-lg flex-1 max-w-md"
            value={selectedChapter}
            onChange={(e) => setSelectedChapter(e.target.value)}
          >
            <option value="">请选择章节...</option>
            {chapters.map((chapter) => (
              <option key={chapter.id} value={chapter.id}>
                {chapter.title}
              </option>
            ))}
          </select>
          {selectedChapterData && (
            <span className="text-sm text-gray-500">
              {selectedChapterData.content ? `${wordCount(selectedChapterData.content)} 字` : '无内容'}
            </span>
          )}
        </div>
      </Card>

      {!metrics ? (
        <Card>
          <div className="text-center py-12 text-gray-500">
            <Eye size={64} className="mx-auto mb-4 opacity-50" />
            <p className="text-lg">选择一个章节并点击"开始阅读模拟"</p>
            <p className="text-sm mt-2">系统会分析章节内容并预测读者反应</p>
          </div>
        </Card>
      ) : (
        <>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
            <Card className="p-6">
              <div className="flex items-center gap-3 mb-2">
                <Heart size={24} className="text-pink-500" />
                <span className="text-sm text-gray-500">沉浸度评分</span>
              </div>
              <div className={`text-3xl font-bold ${getScoreColor(metrics.engagement_score)}`}>
                {metrics.engagement_score.toFixed(1)}
                <span className="text-lg text-gray-400 ml-1">/5</span>
              </div>
            </Card>
            <Card className="p-6">
              <div className="flex items-center gap-3 mb-2">
                <Zap size={24} className="text-yellow-500" />
                <span className="text-sm text-gray-500">悬念指数</span>
              </div>
              <div className="text-3xl font-bold text-purple-600">
                {metrics.suspense_level.toFixed(0)}
                <span className="text-lg text-gray-400 ml-1">%</span>
              </div>
            </Card>
            <Card className="p-6">
              <div className="flex items-center gap-3 mb-2">
                <Clock size={24} className="text-blue-500" />
                <span className="text-sm text-gray-500">预计留存率</span>
              </div>
              <div className="text-3xl font-bold text-green-600">
                {metrics.predicted_retention.toFixed(0)}
                <span className="text-lg text-gray-400 ml-1">%</span>
              </div>
            </Card>
          </div>

          <Card className="mb-6">
            <h2 className="text-lg font-semibold text-gray-800 mb-4 flex items-center gap-2">
              <TrendingUp size={20} />
              情感弧线
            </h2>
            <div className="h-48 flex items-end justify-around px-4">
              {metrics.emotional_arc.map((item, index) => (
                <div key={index} className="flex flex-col items-center">
                  <div className="relative w-12 bg-gradient-to-t from-blue-500 to-purple-500 rounded-t" style={{ height: `${item.value}%` }}>
                    <span className="absolute -top-6 left-1/2 transform -translate-x-1/2 text-xs text-gray-600">{item.value}</span>
                  </div>
                  <span className="text-xs text-gray-500 mt-2 whitespace-nowrap">{item.chapter}</span>
                  <span className="text-xs text-purple-600 font-medium">{item.emotion}</span>
                </div>
              ))}
            </div>
          </Card>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-6">
            <Card>
              <h2 className="text-lg font-semibold text-gray-800 mb-4">维度评分</h2>
              <div className="space-y-4">
                <div>
                  <div className="flex justify-between text-sm mb-1">
                    <span className="text-gray-600">故事节奏</span>
                    <span className={getScoreColor(metrics.pacing_score)}>{metrics.pacing_score.toFixed(1)}/5</span>
                  </div>
                  <div className="w-full bg-gray-200 rounded-full h-2">
                    <div className="bg-blue-500 h-2 rounded-full" style={{ width: `${(metrics.pacing_score / 5) * 100}%` }}></div>
                  </div>
                </div>
                <div>
                  <div className="flex justify-between text-sm mb-1">
                    <span className="text-gray-600">角色塑造</span>
                    <span className={getScoreColor(metrics.character_development)}>{metrics.character_development.toFixed(1)}/5</span>
                  </div>
                  <div className="w-full bg-gray-200 rounded-full h-2">
                    <div className="bg-green-500 h-2 rounded-full" style={{ width: `${(metrics.character_development / 5) * 100}%` }}></div>
                  </div>
                </div>
                <div>
                  <div className="flex justify-between text-sm mb-1">
                    <span className="text-gray-600">剧情连贯性</span>
                    <span className={getScoreColor(metrics.plot_cohesion)}>{metrics.plot_cohesion.toFixed(1)}/5</span>
                  </div>
                  <div className="w-full bg-gray-200 rounded-full h-2">
                    <div className="bg-purple-500 h-2 rounded-full" style={{ width: `${(metrics.plot_cohesion / 5) * 100}%` }}></div>
                  </div>
                </div>
              </div>
            </Card>

            <Card>
              <h2 className="text-lg font-semibold text-gray-800 mb-4">高亮时刻</h2>
              <div className="space-y-3">
                {metrics.highlighted_moments.map((moment, index) => (
                  <div key={index} className="flex items-start gap-3 p-3 bg-yellow-50 rounded-lg">
                    <AlertTriangle size={18} className="text-yellow-600 mt-0.5" />
                    <div>
                      <div className="text-sm font-medium text-gray-800">{moment.chapter} - {moment.timestamp}</div>
                      <div className="text-sm text-gray-600">{moment.description}</div>
                    </div>
                  </div>
                ))}
              </div>
            </Card>
          </div>

          <Card>
            <h2 className="text-lg font-semibold text-gray-800 mb-4">读者反馈预测</h2>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              {metrics.reader_feedback.map((feedback, index) => (
                <div key={index} className="p-4 border rounded-lg">
                  <div className="flex items-center justify-between mb-2">
                    <span className="font-medium text-gray-800">{feedback.aspect}</span>
                    <div className="flex gap-0.5">
                      {[1, 2, 3, 4, 5].map((star) => (
                        <span
                          key={star}
                          className={`text-sm ${
                            star <= Math.round(feedback.score) ? 'text-yellow-400' : 'text-gray-300'
                          }`}
                        >
                          ★
                        </span>
                      ))}
                    </div>
                  </div>
                  <p className="text-sm text-gray-600">{feedback.comments}</p>
                </div>
              ))}
            </div>
          </Card>
        </>
      )}
    </div>
  )
}

function wordCount(text: string): number {
  const chinese = (text.match(/[\u4e00-\u9fa5]/g) || []).length
  const words = (text.match(/[a-zA-Z]+/g) || []).length
  return chinese + words
}
