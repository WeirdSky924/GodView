import { useEffect, useState } from 'react'
import { Card, Button, Modal, TextArea } from '@/components/ui'
import { getChapters } from '@/api/chapters'
import { getWorlds } from '@/api/worlds'
import { getSnapshotTree } from '@/api/director'
import { compareSnapshots } from '@/api/visualization'
import { FileText, GitCompare, Copy, GitBranch } from 'lucide-react'
import type { Chapter } from '@/api/chapters'
import type { World } from '@/api/worlds'

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
    loadSnapshots()
  }, [])

  const flattenSnapshots = (nodes: any[]): any[] => {
    return nodes.flatMap((node) => [node, ...(node.children ? flattenSnapshots(node.children) : [])])
  }

  const loadChapters = async () => {
    try {
      const data = await getChapters()
      setChapters(data)
    } catch (error) {
      console.error('Failed to load chapters:', error)
    }
  }

  const loadWorlds = async () => {
    try {
      const data = await getWorlds()
      setWorlds(data)
    } catch (error) {
      console.error('Failed to load worlds:', error)
    }
  }

  const loadSnapshots = async () => {
    try {
      const result = await getSnapshotTree('default-world')
      setSnapshots(flattenSnapshots(result.data || []))
    } catch (error) {
      console.error('Failed to load snapshots:', error)
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
    <div>
      <div className="flex items-center justify-between mb-8">
        <h1 className="text-3xl font-bold text-gray-800">🔍 版本对比工具</h1>
        <div className="flex gap-3">
          <Button variant="secondary" onClick={() => setShowCustomModal(true)}>
            <Copy size={18} className="mr-2" />
            自定义文本对比
          </Button>
        </div>
      </div>

      <div className="mb-6 flex gap-4 flex-wrap">
        <button onClick={() => setCompareType('chapter')} className={`px-4 py-2 rounded-lg font-medium ${compareType === 'chapter' ? 'bg-blue-500 text-white' : 'bg-gray-100 text-gray-600'}`}>
          <FileText size={18} className="inline mr-2" />章节对比
        </button>
        <button onClick={() => setCompareType('world')} className={`px-4 py-2 rounded-lg font-medium ${compareType === 'world' ? 'bg-blue-500 text-white' : 'bg-gray-100 text-gray-600'}`}>
          <GitCompare size={18} className="inline mr-2" />世界对比
        </button>
        <button onClick={() => setCompareType('snapshot')} className={`px-4 py-2 rounded-lg font-medium ${compareType === 'snapshot' ? 'bg-blue-500 text-white' : 'bg-gray-100 text-gray-600'}`}>
          <GitBranch size={18} className="inline mr-2" />快照对比
        </button>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {[{ side: 'left', value: leftVersion, setValue: setLeftVersion, setContent: setLeftContent }, { side: 'right', value: rightVersion, setValue: setRightVersion, setContent: setRightContent }].map((panel) => (
          <Card key={panel.side} title={`${panel.side === 'left' ? '左侧' : '右侧'}版本`}>
            <div className="space-y-4">
              <select
                className="w-full px-3 py-2 border border-gray-300 rounded-lg"
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
                <div className="p-4 bg-gray-50 rounded-lg">
                  <p className="text-sm text-gray-500 mb-2">内容预览：</p>
                  <p className="text-sm text-gray-700 line-clamp-4">{panel.side === 'left' ? leftContent : rightContent}</p>
                  {compareType !== 'snapshot' && <p className="text-xs text-gray-400 mt-2">{wordCount(panel.side === 'left' ? leftContent : rightContent)} 字</p>}
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
            <span className="text-sm"><span className="inline-block w-3 h-3 bg-green-100 border border-green-500 mr-2"></span>新增：{stats.added} 行</span>
            <span className="text-sm"><span className="inline-block w-3 h-3 bg-red-100 border border-red-500 mr-2"></span>删除：{stats.removed} 行</span>
            <span className="text-sm"><span className="inline-block w-3 h-3 bg-gray-50 border border-gray-300 mr-2"></span>不变：{stats.unchanged} 行</span>
          </div>
          <div className="space-y-1 font-mono text-sm max-h-[600px] overflow-y-auto border rounded-lg p-4">
            {diffResult.unchanged.map((line, i) => <div key={`u-${i}`} className="bg-gray-50 text-gray-600 px-2">{line}</div>)}
            {diffResult.removed.map((line, i) => <div key={`r-${i}`} className="bg-red-50 text-red-700 px-2 border-l-4 border-red-500">-{line}</div>)}
            {diffResult.added.map((line, i) => <div key={`a-${i}`} className="bg-green-50 text-green-700 px-2 border-l-4 border-green-500">+{line}</div>)}
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
    </div>
  )
}
