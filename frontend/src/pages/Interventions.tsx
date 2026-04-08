import { useState, useEffect } from 'react'
import { Card, Button, Modal, TextArea } from '@/components/ui'
import PageLayout from '@/components/PageLayout'
import { GitCompare, Flag, Users, Edit3, Save, AlertCircle, FolderOpen } from 'lucide-react'
import {
  createIntervention,
  getInterventions,
  getSnapshots,
  updateInterventionEvaluation,
} from '@/api/interventions'
import type { Intervention, SnapshotOption } from '@/api/interventions'
import { useProject } from '@/contexts/ProjectContext'
import { useTheme } from '@/contexts/ThemeContext'

export default function Interventions() {
  const { currentProject } = useProject()
  const { theme } = useTheme()
  const isDark = theme === 'dark'

  const [interventions, setInterventions] = useState<Intervention[]>([])
  const [showModal, setShowModal] = useState(false)
  const [showImpactModal, setShowImpactModal] = useState(false)
  const [selectedIntervention, setSelectedIntervention] = useState<Intervention | null>(null)
  const [snapshots, setSnapshots] = useState<SnapshotOption[]>([])
  const [selectedSnapshotId, setSelectedSnapshotId] = useState('')
  const [savingEvaluation, setSavingEvaluation] = useState(false)

  const [formData, setFormData] = useState({
    intervention_type: 'character_edit' as Intervention['intervention_type'],
    description: '',
    affected_characters: [] as string[],
    affected_hooks: [] as string[],
    affected_relationships: [] as string[],
  })

  useEffect(() => {
    if (currentProject) {
      loadInterventions()
      loadSnapshots()
    }
  }, [currentProject])

  const loadInterventions = async () => {
    try {
      const data = await getInterventions()
      setInterventions(data)
    } catch (error) {
      console.error('Failed to load interventions:', error)
    }
  }

  const loadSnapshots = async () => {
    try {
      const data = await getSnapshots()
      setSnapshots(data)
      setSelectedSnapshotId((current) => current || data[0]?.id || '')
    } catch (error) {
      console.error('Failed to load snapshots:', error)
    }
  }

  const saveIntervention = async () => {
    if (!formData.description || !selectedSnapshotId) return

    try {
      await createIntervention({
        snapshot_id: selectedSnapshotId,
        intervention_type: formData.intervention_type,
        description: formData.description,
        details: {},
        affected_hooks: formData.affected_hooks,
        affected_relationships: formData.affected_relationships,
        affected_characters: formData.affected_characters,
      })
      await loadInterventions()
      setShowModal(false)
      setFormData({
        intervention_type: 'character_edit',
        description: '',
        affected_characters: [],
        affected_hooks: [],
        affected_relationships: [],
      })
    } catch (error) {
      console.error('Failed to save intervention:', error)
      alert('保存失败，请重试')
    }
  }

  const saveEvaluation = async () => {
    if (!selectedIntervention?.id) return

    setSavingEvaluation(true)
    try {
      const result = await updateInterventionEvaluation(selectedIntervention.id, {
        outcome_rating: selectedIntervention.outcome_rating,
        outcome_notes: selectedIntervention.outcome_notes,
      })
      setSelectedIntervention(result.data)
      await loadInterventions()
      setShowImpactModal(false)
    } catch (error) {
      console.error('Failed to save intervention evaluation:', error)
      alert('效果评估保存失败')
    } finally {
      setSavingEvaluation(false)
    }
  }

  const getTypeIcon = (type: string) => {
    switch (type) {
      case 'character_edit': return <Users size={16} />
      case 'plot_change': return <Edit3 size={16} />
      case 'hook_modification': return <Flag size={16} />
      case 'relationship_change': return <GitCompare size={16} />
      case 'world_edit': return <AlertCircle size={16} />
      default: return <Edit3 size={16} />
    }
  }

  const getTypeLabel = (type: string) => {
    const labels: Record<string, string> = {
      character_edit: '角色修改',
      plot_change: '剧情变更',
      hook_modification: '伏笔调整',
      relationship_change: '关系变更',
      world_edit: '世界设定修改',
    }
    return labels[type] || type
  }

  const viewImpact = (intervention: Intervention) => {
    setSelectedIntervention(intervention)
    setShowImpactModal(true)
  }

  const getAffectedCount = (intervention: Intervention) => {
    const chars = intervention.affected_characters?.length || 0
    const hooks = intervention.affected_hooks?.length || 0
    const rels = intervention.affected_relationships?.length || 0
    return chars + hooks + rels
  }

  return (
    <PageLayout
      title="干预日志"
      description="记录和追踪对剧情的干预行为"
      actions={
        <Button onClick={() => setShowModal(true)} disabled={!currentProject}>
          <Save size={18} className="mr-2" />
          记录干预
        </Button>
      }
    >
      {!currentProject ? (
        <div className={`text-center py-20 ${isDark ? 'text-gray-400' : 'text-gray-500'}`}>
          <FolderOpen size={48} className="mx-auto mb-4 opacity-50" />
          <p>请先在侧边栏选择一个项目</p>
        </div>
      ) : (
        <>
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-6">
            <Card className="p-4">
              <div className="text-2xl font-bold text-blue-600">{interventions.length}</div>
              <div className={`text-sm ${isDark ? 'text-gray-400' : 'text-gray-500'}`}>总干预次数</div>
            </Card>
            <Card className="p-4">
              <div className="text-2xl font-bold text-green-600">
                {interventions.filter(i => i.outcome_rating && i.outcome_rating >= 4).length}
              </div>
              <div className={`text-sm ${isDark ? 'text-gray-400' : 'text-gray-500'}`}>正面效果</div>
            </Card>
            <Card className="p-4">
              <div className="text-2xl font-bold text-yellow-600">
                {interventions.filter(i => i.outcome_rating && i.outcome_rating === 3).length}
              </div>
              <div className={`text-sm ${isDark ? 'text-gray-400' : 'text-gray-500'}`}>中性效果</div>
            </Card>
            <Card className="p-4">
              <div className="text-2xl font-bold text-red-600">
                {interventions.filter(i => i.outcome_rating && i.outcome_rating < 3).length}
              </div>
              <div className={`text-sm ${isDark ? 'text-gray-400' : 'text-gray-500'}`}>负面效果</div>
            </Card>
          </div>

          <Card>
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead className={`border-b ${isDark ? 'bg-gray-800' : 'bg-gray-50'}`}>
                  <tr>
                    <th className={`px-4 py-3 text-left text-sm font-medium ${isDark ? 'text-gray-300' : 'text-gray-600'}`}>类型</th>
                    <th className={`px-4 py-3 text-left text-sm font-medium ${isDark ? 'text-gray-300' : 'text-gray-600'}`}>描述</th>
                    <th className={`px-4 py-3 text-left text-sm font-medium ${isDark ? 'text-gray-300' : 'text-gray-600'}`}>影响范围</th>
                    <th className={`px-4 py-3 text-left text-sm font-medium ${isDark ? 'text-gray-300' : 'text-gray-600'}`}>时间</th>
                    <th className={`px-4 py-3 text-left text-sm font-medium ${isDark ? 'text-gray-300' : 'text-gray-600'}`}>效果评估</th>
                    <th className={`px-4 py-3 text-left text-sm font-medium ${isDark ? 'text-gray-300' : 'text-gray-600'}`}>操作</th>
                  </tr>
                </thead>
                <tbody>
                  {interventions.length === 0 ? (
                    <tr>
                      <td colSpan={6} className={`px-4 py-8 text-center ${isDark ? 'text-gray-400' : 'text-gray-500'}`}>
                        暂无干预记录，点击"记录干预"开始创建
                      </td>
                    </tr>
                  ) : (
                    interventions.map((item) => (
                      <tr key={item.id} className={`border-b ${isDark ? 'hover:bg-gray-800 border-gray-700' : 'hover:bg-gray-50'}`}>
                        <td className="px-4 py-3">
                          <div className="flex items-center gap-2">
                            {getTypeIcon(item.intervention_type)}
                            <span className={`text-sm ${isDark ? 'text-gray-300' : 'text-gray-700'}`}>{getTypeLabel(item.intervention_type)}</span>
                          </div>
                        </td>
                        <td className={`px-4 py-3 text-sm max-w-xs truncate ${isDark ? 'text-gray-300' : 'text-gray-700'}`}>{item.description}</td>
                        <td className="px-4 py-3">
                          <span className={`text-sm ${isDark ? 'text-gray-400' : 'text-gray-500'}`}>
                            {getAffectedCount(item)} 个项目受影响
                          </span>
                        </td>
                        <td className={`px-4 py-3 text-sm ${isDark ? 'text-gray-400' : 'text-gray-500'}`}>
                          {item.created_at ? new Date(item.created_at).toLocaleString('zh-CN') : '-'}
                        </td>
                        <td className="px-4 py-3">
                          {item.outcome_rating ? (
                            <div className="flex gap-1">
                              {[1, 2, 3, 4, 5].map((star) => (
                                <span
                                  key={star}
                                  className={`text-lg ${
                                    star <= (item.outcome_rating || 0) ? 'text-yellow-400' : isDark ? 'text-gray-600' : 'text-gray-300'
                                  }`}
                                >
                                  ★
                                </span>
                              ))}
                            </div>
                          ) : (
                            <span className={`text-sm ${isDark ? 'text-gray-500' : 'text-gray-400'}`}>未评估</span>
                          )}
                        </td>
                        <td className="px-4 py-3">
                          <Button variant="secondary" size="sm" onClick={() => viewImpact(item)}>
                            查看影响
                          </Button>
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
          </Card>

          <Modal
            isOpen={showModal}
            onClose={() => setShowModal(false)}
            title="记录干预"
            size="lg"
          >
            <div className="space-y-4">
              <div>
                <label className={`block text-sm font-medium mb-1 ${isDark ? 'text-gray-300' : 'text-gray-700'}`}>干预类型</label>
                <select
                  className={`w-full px-3 py-2 border rounded-lg ${isDark ? 'bg-gray-800 border-gray-600 text-white' : 'border-gray-300'}`}
                  value={formData.intervention_type}
                  onChange={(e) => setFormData({ ...formData, intervention_type: e.target.value as Intervention['intervention_type'] })}
                >
                  <option value="character_edit">角色修改</option>
                  <option value="plot_change">剧情变更</option>
                  <option value="hook_modification">伏笔调整</option>
                  <option value="relationship_change">关系变更</option>
                  <option value="world_edit">世界设定修改</option>
                </select>
              </div>
              <div>
                <label className={`block text-sm font-medium mb-1 ${isDark ? 'text-gray-300' : 'text-gray-700'}`}>关联快照</label>
                <select
                  className={`w-full px-3 py-2 border rounded-lg ${isDark ? 'bg-gray-800 border-gray-600 text-white' : 'border-gray-300'}`}
                  value={selectedSnapshotId}
                  onChange={(e) => setSelectedSnapshotId(e.target.value)}
                >
                  <option value="">选择快照...</option>
                  {snapshots.map((s) => (
                    <option key={s.id} value={s.id}>{s.name || s.id}</option>
                  ))}
                </select>
              </div>
              <TextArea
                label="干预描述 *"
                value={formData.description}
                onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                placeholder="详细描述你做了什么干预，为什么这么做..."
                rows={4}
              />
              <div className="flex justify-end gap-3 pt-4">
                <Button variant="secondary" onClick={() => setShowModal(false)}>取消</Button>
                <Button onClick={saveIntervention} disabled={!formData.description || !selectedSnapshotId}>保存</Button>
              </div>
            </div>
          </Modal>

          <Modal
            isOpen={showImpactModal}
            onClose={() => setShowImpactModal(false)}
            title="影响范围分析"
          >
            {selectedIntervention && (
              <div className="space-y-4">
                <div className={`p-4 rounded-lg ${isDark ? 'bg-gray-800' : 'bg-gray-50'}`}>
                  <p className={`text-sm ${isDark ? 'text-gray-400' : 'text-gray-500'}`}>干预描述</p>
                  <p className={isDark ? 'text-gray-200' : 'text-gray-800'}>{selectedIntervention.description}</p>
                </div>
                <div className="grid grid-cols-3 gap-4">
                  <div className={`p-4 border rounded-lg ${isDark ? 'border-gray-700' : 'border-gray-200'}`}>
                    <div className="flex items-center gap-2 text-blue-600 mb-2">
                      <Users size={18} />
                      <span className="font-medium">影响角色</span>
                    </div>
                    <div className={`text-2xl font-bold ${isDark ? 'text-white' : 'text-gray-800'}`}>
                      {selectedIntervention.affected_characters?.length || 0}
                    </div>
                  </div>
                  <div className={`p-4 border rounded-lg ${isDark ? 'border-gray-700' : 'border-gray-200'}`}>
                    <div className="flex items-center gap-2 text-green-600 mb-2">
                      <Flag size={18} />
                      <span className="font-medium">影响伏笔</span>
                    </div>
                    <div className={`text-2xl font-bold ${isDark ? 'text-white' : 'text-gray-800'}`}>
                      {selectedIntervention.affected_hooks?.length || 0}
                    </div>
                  </div>
                  <div className={`p-4 border rounded-lg ${isDark ? 'border-gray-700' : 'border-gray-200'}`}>
                    <div className="flex items-center gap-2 text-purple-600 mb-2">
                      <GitCompare size={18} />
                      <span className="font-medium">影响关系</span>
                    </div>
                    <div className={`text-2xl font-bold ${isDark ? 'text-white' : 'text-gray-800'}`}>
                      {selectedIntervention.affected_relationships?.length || 0}
                    </div>
                  </div>
                </div>
                <div>
                  <label className={`block text-sm font-medium mb-1 ${isDark ? 'text-gray-300' : 'text-gray-700'}`}>效果评估</label>
                  <div className="flex gap-2">
                    {[1, 2, 3, 4, 5].map((rating) => (
                      <button
                        key={rating}
                        onClick={() => setSelectedIntervention((prev) => prev ? { ...prev, outcome_rating: rating } : prev)}
                        className={`text-2xl ${
                          rating <= (selectedIntervention.outcome_rating || 0)
                            ? 'text-yellow-400'
                            : isDark ? 'text-gray-600' : 'text-gray-300'
                        } hover:scale-110 transition-transform`}
                      >
                        ★
                      </button>
                    ))}
                  </div>
                </div>
                <TextArea
                  label="效果备注"
                  value={selectedIntervention.outcome_notes || ''}
                  onChange={(e) => setSelectedIntervention((prev) => prev ? { ...prev, outcome_notes: e.target.value } : prev)}
                  placeholder="记录这次干预的效果..."
                  rows={3}
                />
                <div className="flex justify-end gap-3 pt-2">
                  <Button variant="secondary" onClick={() => setShowImpactModal(false)}>取消</Button>
                  <Button onClick={saveEvaluation} loading={savingEvaluation}>保存评估</Button>
                </div>
              </div>
            )}
          </Modal>
        </>
      )}
    </PageLayout>
  )
}
