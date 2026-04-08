import { useEffect, useMemo, useState } from 'react'
import { Card } from '@/components/ui'
import PageLayout from '@/components/PageLayout'
import ReactFlow, { Background, Controls, MiniMap } from 'reactflow'
import 'reactflow/dist/style.css'
import { getVisualizationData } from '@/api/visualization'
import { getWorlds, type World } from '@/api/worlds'
import { Network, Users, GitBranch } from 'lucide-react'
import { useTheme } from '@/contexts/ThemeContext'

type TabType = 'workflow' | 'plots' | 'snapshots'

export default function Visualizer() {
  const { theme } = useTheme()
  const isDark = theme === 'dark'

  const [activeTab, setActiveTab] = useState<TabType>('workflow')
  const [data, setData] = useState<any>(null)
  const [worlds, setWorlds] = useState<World[]>([])
  const [selectedWorldId, setSelectedWorldId] = useState('')

  useEffect(() => {
    loadWorlds()
  }, [])

  useEffect(() => {
    if (!selectedWorldId) return
    loadData(selectedWorldId)
  }, [selectedWorldId])

  const loadWorlds = async () => {
    try {
      const result = await getWorlds()
      setWorlds(result)
      setSelectedWorldId((current) => current || result[0]?.id || '')
    } catch (error) {
      console.error('Failed to load worlds:', error)
    }
  }

  const loadData = async (worldId: string) => {
    try {
      const result = await getVisualizationData(worldId)
      setData(result)
    } catch (error) {
      console.error('Failed to load visualization data:', error)
    }
  }

  const currentWorld = useMemo(
    () => worlds.find((world) => world.id === selectedWorldId) || null,
    [worlds, selectedWorldId],
  )

  const workflowNodes = (data?.workflow?.nodes || []).map((node: any, index: number) => ({
    id: node.id,
    position: { x: 120 + index * 180, y: 180 },
    data: { label: node.label },
    style: { padding: 10, borderRadius: 10, background: '#e0f2fe', border: '1px solid #7dd3fc' },
  }))
  const workflowEdges = (data?.workflow?.edges || []).map((edge: any, index: number) => ({
    id: `wf-${index}`,
    source: edge.source,
    target: edge.target,
    animated: true,
  }))

  const plotNodes = (data?.plot_tree?.nodes || []).map((node: any, index: number) => ({
    id: node.id,
    position: { x: 160 + index * 180, y: 180 + (index % 2) * 120 },
    data: { label: node.label },
    style: { padding: 10, borderRadius: 10, background: '#fef3c7', border: '1px solid #f59e0b' },
  }))
  const plotEdges = (data?.plot_tree?.edges || []).map((edge: any, index: number) => ({
    id: `plot-${index}`,
    source: edge.source,
    target: edge.target,
  }))

  const snapshotNodes = (data?.snapshot_tree?.nodes || []).map((node: any, index: number) => ({
    id: node.id,
    position: { x: 160 + index * 180, y: 180 + (index % 3) * 100 },
    data: { label: node.label },
    style: {
      padding: 10,
      borderRadius: 10,
      background: node.is_branch ? '#f5d0fe' : '#ede9fe',
      border: '1px solid #a78bfa',
    },
  }))
  const snapshotEdges = (data?.snapshot_tree?.edges || []).map((edge: any, index: number) => ({
    id: `snap-${index}`,
    source: edge.source,
    target: edge.target,
  }))

  const tabs = [
    { key: 'workflow', label: '工作流', icon: <Network size={18} /> },
    { key: 'plots', label: '剧情树', icon: <Users size={18} /> },
    { key: 'snapshots', label: '版本树', icon: <GitBranch size={18} /> },
  ]

  const currentNodes = activeTab === 'workflow' ? workflowNodes : activeTab === 'plots' ? plotNodes : snapshotNodes
  const currentEdges = activeTab === 'workflow' ? workflowEdges : activeTab === 'plots' ? plotEdges : snapshotEdges

  return (
    <PageLayout
      title="可视化工作台"
      description="可视化展示工作流、剧情树和版本树"
      actions={
        <div className="w-72">
          <label className={`block text-sm font-medium mb-1 ${isDark ? 'text-gray-300' : 'text-gray-700'}`}>世界</label>
          <select
            className={`w-full px-3 py-2 border rounded-lg ${isDark ? 'bg-gray-800 border-gray-600 text-white' : 'bg-white border-gray-300'}`}
            value={selectedWorldId}
            onChange={(e) => setSelectedWorldId(e.target.value)}
          >
            <option value="">选择世界...</option>
            {worlds.map((world) => (
              <option key={world.id} value={world.id}>{world.name || world.id}</option>
            ))}
          </select>
        </div>
      }
    >
      {currentWorld && (
        <div className={`mb-4 text-sm ${isDark ? 'text-gray-400' : 'text-gray-500'}`}>
          当前世界：{currentWorld.name || currentWorld.id}
        </div>
      )}

      <div className="mb-6 flex gap-4">
        {tabs.map((tab) => (
          <button
            key={tab.key}
            onClick={() => setActiveTab(tab.key as TabType)}
            className={`px-4 py-2 rounded-lg font-medium transition-colors ${
              activeTab === tab.key
                ? 'bg-blue-500 text-white'
                : isDark
                  ? 'bg-gray-800 text-gray-300 hover:bg-gray-700'
                  : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
            }`}
          >
            <span className="inline mr-2">{tab.icon}</span>
            {tab.label}
          </button>
        ))}
      </div>

      <Card className="min-h-[600px]">
        {selectedWorldId ? (
          <ReactFlow nodes={currentNodes} edges={currentEdges} fitView>
            <MiniMap zoomable pannable />
            <Controls />
            <Background />
          </ReactFlow>
        ) : (
          <div className={`h-[600px] flex items-center justify-center ${isDark ? 'text-gray-400' : 'text-gray-500'}`}>
            暂无世界数据，请先创建世界
          </div>
        )}
      </Card>
    </PageLayout>
  )
}
