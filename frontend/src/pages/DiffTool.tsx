import { useEffect, useState } from 'react'
import { Card, Button, Modal, TextArea } from '@/components/ui'
import PageLayout from '@/components/PageLayout'
import { getChapters } from '@/api/chapters'
import { getWorlds } from '@/api/worlds'
import { compareSnapshots } from '@/api/visualization'
import { FileText, GitCompare, Copy, GitBranch } from 'lucide-react'
import type { Chapter } from '@/api/chapters'
import type { World } from '@/api/worlds'
import { useTheme } from '@/contexts/ThemeContext'
import { useProject } from '@/contexts/ProjectContext'

interface DiffResult {
  added: string[]
  removed: string[]
  unchanged: string[]
}

function computeTextDiff(oldText: string, newText: string): DiffResult {
  const oldLines = oldText.split('\n')
  const newLines = newText.split('\n')

  const added: string[] = []
  const removed: string[] = []
  const unchanged: string[] = []

  const maxLen = Math.max(oldLines.length, newLines.length)

  for (let i = 0; i < maxLen; i++) {
    const oldLine = oldLines[i]
    const newLine = newLines[i]

    if (oldLine === undefined) {
      added.push(newLine || '')
    } else if (newLine === undefined) {
      removed.push(oldLine)
    } else if (oldLine === newLine) {
      unchanged.push(oldLine)
    } else {
      removed.push(oldLine)
      added.push(newLine)
    }
  }

  return { added, removed, unchanged }
}

export default function DiffTool() {
  const { theme } = useTheme()
  const isDark = theme === 'dark'
  const { currentProject } = useProject()

  const [chapters, setChapters] = useState<Chapter[]>([])
  const [worlds, setWorlds] = useState<World[]>([])
  const [snapshots, setSnapshots] = useState<any[]>([])
  const [compareType, setCompareType] = useState<'chapter' | 'world' | 'snapshot'>('chapter')
  const [leftVersion, setLeftVersion] = useState<string>('')
  const [rightVersion, setRightVersion] = useState<string>('')
  const [leftContent, setLeftContent] = useState<string>('')
  const [rightContent, setRightContent] = useState<string>('')
  const [diffResult, setDiffResult] = useState<DiffResult | null>(null)
  const [showCustomModal, setShowCustomModal] = useState(false)
  const [customLeft, setCustomLeft] = useState('')
  const [customRight, setCustomRight] = useState('')

  useEffect(() => {
    loadChapters()
    loadWorlds()
  }, [currentProject?.id])

  const loadChapters = async () => {
    try {
      const data = await getChapters(currentProject?.id)
      setChapters(data)
    } catch (error) {
      console.error('Failed to load chapters:', error)
    }
  }

  const loadWorlds = async () => {
    try {
      const data = await getWorlds(currentProject?.id)
      setWorlds(data)
      // 快照暂时置空，需要有效的 world_id 才能加载
      setSnapshots([])
    } catch (error) {
      console.error('Failed to load worlds:', error)
    }
  }

  const handleCompare = async () => {
    if (!leftVersion || !rightVersion) return

    if (compareType === 'snapshot') {
      try {
        const result = await compareSnapshots(leftVersion, rightVersion)
        const added = result.lines.filter((line) => line.type === 'added').map((line) => line.content)
        const removed = result.lines.filter((line) => line.type === 'removed').map((line) => line.content)
        const unchanged = result.lines.filter((line) => line.type === 'unchanged').map((line) => line.content)
        setDiffResult({ added, removed, unchanged })
        return
      } catch (error) {
        console.error('Failed to compare snapshots:', error)
      }
    }

    if (!leftContent || !rightContent) return
    const diff = computeTextDiff(leftContent, rightContent)
    setDiffResult(diff)
  }

  const handleCustomCompare = () => {
    const diff = computeTextDiff(customLeft, customRight)
    setDiffResult(diff)
    setShowCustomModal(false)
  }

  const wordCount = (text: string) => {
    const chinese = (text.match(/[\u4e00-\u9fa5]/g) || []).length
    const words = (text.match(/[a-zA-Z]+/g) || []).length
    return chinese + words
  }

  const getCollection = () => {
    if (compareType === 'chapter') return chapters
    if (compareType === 'world') return worlds
    return snapshots
  }

  const resolveContent = (id: string) => {
    if (compareType === 'chapter') {
      return chapters.find((c) => c.id === id)?.content || ''
    }
    if (compareType === 'world') {
      return worlds.find((w) => w.id === id)?.description || ''
    }
    return snapshots.find((s) => s.id === id)?.name || ''
  }

  const stats = diffResult
    ? {
        added: diffResult.added.length,
        removed: diffResult.removed.length,
        unchanged: diffResult.unchanged.length,
      }
    : null

  return (
    <PageLayout
      title="版本对比工具"
      description="对比不同版本的内容差异"
      actions={
        <Button variant="secondary" onClick={() => setShowCustomModal(true)}>
          <Copy size={18} className="mr-2" />
          自定义文本对比
        </Button>
      }
    >
      <div className="mb-6 flex gap-4 flex-wrap">
        <button onClick={() => setCompareType('chapter')} className={`px-4 py-2 rounded-lg font-medium ${compareType === 'chapter' ? 'bg-blue-500 text-white' : isDark ? 'bg-gray-800 text-gray-300' : 'bg-gray-100 text-gray-600'}`}>
          <FileText size={18} className="inline mr-2" />章节对比
        </button>
        <button onClick={() => setCompareType('world')} className={`px-4 py-2 rounded-lg font-medium ${compareType === 'world' ? 'bg-blue-500 text-white' : isDark ? 'bg-gray-800 text-gray-300' : 'bg-gray-100 text-gray-600'}`}>
          <GitCompare size={18} className="inline mr-2" />世界对比
        </button>
        <button onClick={() => setCompareType('snapshot')} className={`px-4 py-2 rounded-lg font-medium ${compareType === 'snapshot' ? 'bg-blue-500 text-white' : isDark ? 'bg-gray-800 text-gray-300' : 'bg-gray-100 text-gray-600'}`}>
          <GitBranch size={18} className="inline mr-2" />快照对比
        </button>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {[{ side: 'left', value: leftVersion, setValue: setLeftVersion, setContent: setLeftContent }, { side: 'right', value: rightVersion, setValue: setRightVersion, setContent: setRightContent }].map((panel) => (
          <Card key={panel.side} title={`${panel.side === 'left' ? '左侧' : '右侧'}版本`}>
            <div className="space-y-4">
              <select
                className={`w-full px-3 py-2 border rounded-lg ${isDark ? 'bg-gray-800 border-gray-600 text-white' : 'border-gray-300'}`}
                value={panel.value}
                onChange={(e) => {
                  panel.setValue(e.target.value)
                  panel.setContent(resolveContent(e.target.value))
                }}
              >
                <option value="">选择版本...</option>
                {getCollection().map((item: any) => (
                  <option key={item.id} value={item.id}>
                    {item.title || item.name || item.id}
                  </option>
                ))}
              </select>
              {((panel.side === 'left' ? leftContent : rightContent) || compareType === 'snapshot') && (
                <div className={`p-4 rounded-lg ${isDark ? 'bg-gray-800' : 'bg-gray-50'}`}>
                  <p className={`text-sm mb-2 ${isDark ? 'text-gray-400' : 'text-gray-500'}`}>内容预览：</p>
                  <p className={`text-sm line-clamp-4 ${isDark ? 'text-gray-300' : 'text-gray-700'}`}>{panel.side === 'left' ? leftContent : rightContent}</p>
                  {compareType !== 'snapshot' && <p className={`text-xs mt-2 ${isDark ? 'text-gray-500' : 'text-gray-400'}`}>{wordCount(panel.side === 'left' ? leftContent : rightContent)} 字</p>}
                </div>
              )}
            </div>
          </Card>
        ))}
      </div>

      <div className="mt-6 flex justify-center">
        <Button onClick={handleCompare} disabled={!leftVersion || !rightVersion}>
          <GitCompare size={18} className="mr-2" />开始对比
        </Button>
      </div>

      {diffResult && stats && (
        <Card title="对比结果" className="mt-6">
          <div className="mb-4 flex items-center gap-6">
            <span className="text-sm"><span className={`inline-block w-3 h-3 mr-2 ${isDark ? 'bg-green-900 border-green-600' : 'bg-green-100 border-green-500'} border`}></span>新增：{stats.added} 行</span>
            <span className="text-sm"><span className={`inline-block w-3 h-3 mr-2 ${isDark ? 'bg-red-900 border-red-600' : 'bg-red-100 border-red-500'} border`}></span>删除：{stats.removed} 行</span>
            <span className="text-sm"><span className={`inline-block w-3 h-3 mr-2 ${isDark ? 'bg-gray-700 border-gray-500' : 'bg-gray-50 border-gray-300'} border`}></span>不变：{stats.unchanged} 行</span>
          </div>
          <div className={`space-y-1 font-mono text-sm max-h-[600px] overflow-y-auto border rounded-lg p-4 ${isDark ? 'bg-gray-900 border-gray-700' : 'bg-gray-50 border-gray-200'}`}>
            {diffResult.unchanged.map((line, i) => <div key={`u-${i}`} className={`${isDark ? 'bg-gray-800 text-gray-400' : 'bg-gray-50 text-gray-600'} px-2`}>{line}</div>)}
            {diffResult.removed.map((line, i) => <div key={`r-${i}`} className={`${isDark ? 'bg-red-900/50 text-red-300' : 'bg-red-50 text-red-700'} px-2 border-l-4 border-red-500`}>-{line}</div>)}
            {diffResult.added.map((line, i) => <div key={`a-${i}`} className={`${isDark ? 'bg-green-900/50 text-green-300' : 'bg-green-50 text-green-700'} px-2 border-l-4 border-green-500`}>+{line}</div>)}
          </div>
        </Card>
      )}

      <Modal isOpen={showCustomModal} onClose={() => setShowCustomModal(false)} title="自定义文本对比" size="lg">
        <div className="space-y-4">
          <div className="grid grid-cols-2 gap-4">
            <TextArea label="左侧文本" value={customLeft} onChange={(e) => setCustomLeft(e.target.value)} rows={8} />
            <TextArea label="右侧文本" value={customRight} onChange={(e) => setCustomRight(e.target.value)} rows={8} />
          </div>
          <div className="flex justify-end gap-3 pt-4">
            <Button variant="secondary" onClick={() => setShowCustomModal(false)}>取消</Button>
            <Button onClick={handleCustomCompare}><GitCompare size={18} className="mr-2" />对比</Button>
          </div>
        </div>
      </Modal>
    </PageLayout>
  )
}
