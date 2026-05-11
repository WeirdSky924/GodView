import { useEffect, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { Card, Button } from '@/components/ui'
import PageLayout from '@/components/PageLayout'
import { evaluateChapter, getChapters } from '@/api/chapters'
import type { Chapter, ChapterEvaluationResult } from '@/api/chapters'
import { CheckCircle2, Gauge, Sparkles, BookOpen, AlertCircle } from 'lucide-react'
import { useTheme } from '@/contexts/ThemeContext'
import { useProject } from '@/contexts/ProjectContext'

export default function ChapterEvaluator() {
  const { theme } = useTheme()
  const { currentProject } = useProject()
  const [searchParams] = useSearchParams()
  const isDark = theme === 'dark'
  const queryChapterId = searchParams.get('chapter_id')

  const [chapters, setChapters] = useState<Chapter[]>([])
  const [selectedChapterId, setSelectedChapterId] = useState('')
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState<ChapterEvaluationResult | null>(null)
  const [missingChapterId, setMissingChapterId] = useState<string | null>(null)

  useEffect(() => {
    loadChapters()
  }, [currentProject, queryChapterId])

  const loadChapters = async () => {
    try {
      const data = await getChapters(currentProject?.id)
      setChapters(data)
      const requestedChapter = queryChapterId ? data.find(chapter => chapter.id === queryChapterId) : null
      if (requestedChapter?.id) {
        setMissingChapterId(null)
        setSelectedChapterId(requestedChapter.id)
      } else if (queryChapterId) {
        setMissingChapterId(queryChapterId)
        setSelectedChapterId('')
      } else if (data.length > 0) {
        setMissingChapterId(null)
        setSelectedChapterId(data[0].id || '')
      } else {
        setMissingChapterId(null)
        setSelectedChapterId('')
      }
    } catch (error) {
      console.error('Failed to load chapters:', error)
    }
  }

  const runEvaluation = async () => {
    if (!selectedChapterId) return

    setLoading(true)
    try {
      const evaluation = await evaluateChapter(selectedChapterId)
      setResult(evaluation)
    } catch (error) {
      console.error('Failed to evaluate chapter:', error)
    } finally {
      setLoading(false)
    }
  }

  const selectedChapter = chapters.find((c) => c.id === selectedChapterId)

  const scoreColor = (value: number) => {
    if (value >= 0.75) return 'bg-green-500'
    if (value >= 0.5) return 'bg-yellow-500'
    return 'bg-red-500'
  }

  const scoreText = (value: number) => {
    if (value >= 0.75) return 'text-green-600'
    if (value >= 0.5) return 'text-yellow-600'
    return 'text-red-600'
  }

  return (
    <PageLayout
      title="章节结束判定器"
      description="评估章节是否适合收尾"
      actions={
        <Button onClick={runEvaluation} loading={loading} disabled={!selectedChapterId}>
          <CheckCircle2 size={18} className="mr-2" />开始评估
        </Button>
      }
    >
      <div className="flex flex-col h-[calc(100vh-200px)]">
        {missingChapterId && (
          <Card className="mb-4 flex-shrink-0">
            <div className={`text-sm ${isDark ? 'text-yellow-300' : 'text-yellow-700'}`}>
              <div className="font-medium mb-1">章节交接链接未命中</div>
              <div>章节不存在或不属于当前项目：<span className="font-mono break-all">{missingChapterId}</span></div>
              <div className={`mt-1 ${isDark ? 'text-gray-400' : 'text-gray-500'}`}>请选择下方可用章节后再手动开始评估。</div>
            </div>
          </Card>
        )}

        <Card className="mb-4 flex-shrink-0">
          <div className="flex items-center gap-4">
            <label className={`text-sm font-medium ${isDark ? 'text-gray-300' : 'text-gray-700'}`}>选择章节：</label>
            <select
              className={`px-3 py-2 border rounded-lg flex-1 max-w-md ${isDark ? 'bg-gray-800 border-gray-600 text-white' : 'border-gray-300'}`}
              value={selectedChapterId}
              onChange={(e) => {
                setMissingChapterId(null)
                setSelectedChapterId(e.target.value)
              }}
            >
              <option value="">请选择章节...</option>
              {chapters.map((chapter) => (
                <option key={chapter.id} value={chapter.id}>
                  {chapter.title}
                </option>
              ))}
            </select>
            {selectedChapter && (
              <span className={`text-sm ${isDark ? 'text-gray-400' : 'text-gray-500'}`}>{(selectedChapter.content || '').length} 字符</span>
            )}
          </div>
        </Card>

        {!result ? (
          <Card className="flex-1 min-h-0">
            <div className={`text-center py-12 h-full flex flex-col items-center justify-center ${isDark ? 'text-gray-400' : 'text-gray-500'}`}>
              <CheckCircle2 size={64} className="mb-4 opacity-50" />
              <p className="text-lg">选择一个章节并点击"开始评估"</p>
              <p className="text-sm mt-2">系统会从信息增量、悬念、节奏与完整度四个维度给出建议</p>
            </div>
          </Card>
      ) : (
        <div className="flex-1 min-h-0 overflow-y-auto space-y-4">
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
            <Card className="p-5">
              <div className="flex items-center gap-3 mb-2">
                <Sparkles size={22} className="text-blue-500" />
                <span className={`text-sm ${isDark ? 'text-gray-400' : 'text-gray-500'}`}>信息增量</span>
              </div>
              <div className={`text-2xl font-bold ${scoreText(result.scores.info_gain)}`}>
                {(result.scores.info_gain * 100).toFixed(0)}%
              </div>
            </Card>
            <Card className="p-5">
              <div className="flex items-center gap-3 mb-2">
                <AlertCircle size={22} className="text-purple-500" />
                <span className={`text-sm ${isDark ? 'text-gray-400' : 'text-gray-500'}`}>悬念埋设</span>
              </div>
              <div className={`text-2xl font-bold ${scoreText(result.scores.suspense)}`}>
                {(result.scores.suspense * 100).toFixed(0)}%
              </div>
            </Card>
            <Card className="p-5">
              <div className="flex items-center gap-3 mb-2">
                <Gauge size={22} className="text-yellow-500" />
                <span className={`text-sm ${isDark ? 'text-gray-400' : 'text-gray-500'}`}>节奏控制</span>
              </div>
              <div className={`text-2xl font-bold ${scoreText(result.scores.pacing)}`}>
                {(result.scores.pacing * 100).toFixed(0)}%
              </div>
            </Card>
            <Card className="p-5">
              <div className="flex items-center gap-3 mb-2">
                <BookOpen size={22} className="text-green-500" />
                <span className={`text-sm ${isDark ? 'text-gray-400' : 'text-gray-500'}`}>完整度</span>
              </div>
              <div className={`text-2xl font-bold ${scoreText(result.scores.completeness)}`}>
                {(result.scores.completeness * 100).toFixed(0)}%
              </div>
            </Card>
          </div>

          <Card className="mb-6">
            <h2 className={`text-lg font-semibold mb-4 ${isDark ? 'text-white' : 'text-gray-800'}`}>维度详情</h2>
            <div className="space-y-4">
              {[
                { key: 'info_gain', label: '信息增量', value: result.scores.info_gain },
                { key: 'suspense', label: '悬念埋设', value: result.scores.suspense },
                { key: 'pacing', label: '节奏控制', value: result.scores.pacing },
                { key: 'completeness', label: '完整度', value: result.scores.completeness },
              ].map((item) => (
                <div key={item.key}>
                  <div className="flex justify-between text-sm mb-1">
                    <span className={isDark ? 'text-gray-400' : 'text-gray-600'}>{item.label}</span>
                    <span className={scoreText(item.value)}>{(item.value * 100).toFixed(0)}%</span>
                  </div>
                  <div className={`w-full rounded-full h-3 overflow-hidden ${isDark ? 'bg-gray-700' : 'bg-gray-200'}`}>
                    <div className={`h-full ${scoreColor(item.value)}`} style={{ width: `${item.value * 100}%` }} />
                  </div>
                </div>
              ))}
            </div>
          </Card>

          <Card>
            <h2 className={`text-lg font-semibold mb-4 ${isDark ? 'text-white' : 'text-gray-800'}`}>判定结果</h2>
            <div className={`p-4 rounded-lg ${result.should_end ? (isDark ? 'bg-green-900/30 border border-green-700' : 'bg-green-50 border border-green-200') : (isDark ? 'bg-yellow-900/30 border border-yellow-700' : 'bg-yellow-50 border border-yellow-200')}`}>
              <div className="flex items-center gap-2 mb-2">
                <CheckCircle2 className={result.should_end ? 'text-green-600' : 'text-yellow-600'} size={20} />
                <span className={`font-semibold ${result.should_end ? (isDark ? 'text-green-400' : 'text-green-700') : (isDark ? 'text-yellow-400' : 'text-yellow-700')}`}>
                  {result.should_end ? '建议可以收尾' : '建议暂不收尾'}
                </span>
              </div>
              <p className={`text-sm leading-relaxed ${isDark ? 'text-gray-300' : 'text-gray-700'}`}>{result.reason}</p>
              {result.suggested_continuation && (
                <p className={`text-sm mt-3 ${isDark ? 'text-gray-400' : 'text-gray-600'}`}>后续建议：{result.suggested_continuation}</p>
              )}
            </div>
          </Card>
        </div>
      )}
      </div>
    </PageLayout>
  )
}
