import { useEffect, useState } from 'react'
import { Card, Button } from '@/components/ui'
import { evaluateChapter, getChapters } from '@/api/chapters'
import type { Chapter, ChapterEvaluationResult } from '@/api/chapters'
import { CheckCircle2, Gauge, Sparkles, BookOpen, AlertCircle } from 'lucide-react'

export default function ChapterEvaluator() {
  const [chapters, setChapters] = useState<Chapter[]>([])
  const [selectedChapterId, setSelectedChapterId] = useState('')
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState<ChapterEvaluationResult | null>(null)

  useEffect(() => {
    loadChapters()
  }, [])

  const loadChapters = async () => {
    try {
      const data = await getChapters()
      setChapters(data)
      if (data.length > 0) {
        setSelectedChapterId(data[0].id || '')
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
    <div>
      <div className="flex items-center justify-between mb-8">
        <h1 className="text-3xl font-bold text-gray-800">✅ 章节结束判定器</h1>
        <Button onClick={runEvaluation} loading={loading} disabled={!selectedChapterId}>
          <CheckCircle2 size={18} className="mr-2" />开始评估
        </Button>
      </div>

      <Card className="mb-6">
        <div className="flex items-center gap-4">
          <label className="text-sm font-medium text-gray-700">选择章节：</label>
          <select
            className="px-3 py-2 border border-gray-300 rounded-lg flex-1 max-w-md"
            value={selectedChapterId}
            onChange={(e) => setSelectedChapterId(e.target.value)}
          >
            <option value="">请选择章节...</option>
            {chapters.map((chapter) => (
              <option key={chapter.id} value={chapter.id}>
                {chapter.title}
              </option>
            ))}
          </select>
          {selectedChapter && (
            <span className="text-sm text-gray-500">{(selectedChapter.content || '').length} 字符</span>
          )}
        </div>
      </Card>

      {!result ? (
        <Card>
          <div className="text-center py-12 text-gray-500">
            <CheckCircle2 size={64} className="mx-auto mb-4 opacity-50" />
            <p className="text-lg">选择一个章节并点击“开始评估”</p>
            <p className="text-sm mt-2">系统会从信息增量、悬念、节奏与完整度四个维度给出建议</p>
          </div>
        </Card>
      ) : (
        <>
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-6">
            <Card className="p-5">
              <div className="flex items-center gap-3 mb-2">
                <Sparkles size={22} className="text-blue-500" />
                <span className="text-sm text-gray-500">信息增量</span>
              </div>
              <div className={`text-2xl font-bold ${scoreText(result.scores.info_gain)}`}>
                {(result.scores.info_gain * 100).toFixed(0)}%
              </div>
            </Card>
            <Card className="p-5">
              <div className="flex items-center gap-3 mb-2">
                <AlertCircle size={22} className="text-purple-500" />
                <span className="text-sm text-gray-500">悬念埋设</span>
              </div>
              <div className={`text-2xl font-bold ${scoreText(result.scores.suspense)}`}>
                {(result.scores.suspense * 100).toFixed(0)}%
              </div>
            </Card>
            <Card className="p-5">
              <div className="flex items-center gap-3 mb-2">
                <Gauge size={22} className="text-yellow-500" />
                <span className="text-sm text-gray-500">节奏控制</span>
              </div>
              <div className={`text-2xl font-bold ${scoreText(result.scores.pacing)}`}>
                {(result.scores.pacing * 100).toFixed(0)}%
              </div>
            </Card>
            <Card className="p-5">
              <div className="flex items-center gap-3 mb-2">
                <BookOpen size={22} className="text-green-500" />
                <span className="text-sm text-gray-500">完整度</span>
              </div>
              <div className={`text-2xl font-bold ${scoreText(result.scores.completeness)}`}>
                {(result.scores.completeness * 100).toFixed(0)}%
              </div>
            </Card>
          </div>

          <Card className="mb-6">
            <h2 className="text-lg font-semibold text-gray-800 mb-4">维度详情</h2>
            <div className="space-y-4">
              {[
                { key: 'info_gain', label: '信息增量', value: result.scores.info_gain },
                { key: 'suspense', label: '悬念埋设', value: result.scores.suspense },
                { key: 'pacing', label: '节奏控制', value: result.scores.pacing },
                { key: 'completeness', label: '完整度', value: result.scores.completeness },
              ].map((item) => (
                <div key={item.key}>
                  <div className="flex justify-between text-sm mb-1">
                    <span className="text-gray-600">{item.label}</span>
                    <span className={scoreText(item.value)}>{(item.value * 100).toFixed(0)}%</span>
                  </div>
                  <div className="w-full bg-gray-200 rounded-full h-3 overflow-hidden">
                    <div className={`h-full ${scoreColor(item.value)}`} style={{ width: `${item.value * 100}%` }} />
                  </div>
                </div>
              ))}
            </div>
          </Card>

          <Card>
            <h2 className="text-lg font-semibold text-gray-800 mb-4">判定结果</h2>
            <div className={`p-4 rounded-lg ${result.should_end ? 'bg-green-50 border border-green-200' : 'bg-yellow-50 border border-yellow-200'}`}>
              <div className="flex items-center gap-2 mb-2">
                <CheckCircle2 className={result.should_end ? 'text-green-600' : 'text-yellow-600'} size={20} />
                <span className={`font-semibold ${result.should_end ? 'text-green-700' : 'text-yellow-700'}`}>
                  {result.should_end ? '建议可以收尾' : '建议暂不收尾'}
                </span>
              </div>
              <p className="text-sm text-gray-700 leading-relaxed">{result.reason}</p>
              {result.suggested_continuation && (
                <p className="text-sm text-gray-600 mt-3">后续建议：{result.suggested_continuation}</p>
              )}
            </div>
          </Card>
        </>
      )}
    </div>
  )
}
