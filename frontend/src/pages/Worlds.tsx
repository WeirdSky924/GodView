import { useState, useEffect, useCallback } from 'react'
import { Button, Input, TextArea } from '@/components/ui'
import PageLayout from '@/components/PageLayout'
import TagSelector from '@/components/world/TagSelector'
import { getWorlds, createWorld, updateWorld } from '@/api/worlds'
import { analyzeWorldDescription } from '@/api/settingAgent'
import type { World, CreateWorldDTO, UpdateWorldDTO } from '@/api/worlds'
import {
  Save,
  Globe,
  Loader2,
  Sparkles,
  Wand2,
  MapPin,
  Clock,
  Cpu,
  Tags,
  BookOpen,
  Plus,
} from 'lucide-react'
import { useProject } from '@/contexts/ProjectContext'
import { useTheme } from '@/contexts/ThemeContext'
import { formatWorldOptionLabel, getWorldDepth, sortWorldsForDisplay } from '@/hooks/useProjectWorlds'

type WorldTagField = 'world_type' | 'tone' | 'content_styles' | 'protagonist_types' | 'power_types' | 'character_archetypes'

interface WorldFormData {
  name: string
  description: string
  world_type: string
  tone: string
  content_styles: string[]
  protagonist_types: string[]
  character_archetypes: string[]
  power_types: string[]
  power_system: string
  technology_level: string
  history: string
  geography: string
  parent_world_id: string
  scope_type: string
  is_default: boolean
  inherit_rules: boolean
  order_index: number
}

const defaultFormData: WorldFormData = {
  name: '',
  description: '',
  world_type: 'fantasy',
  tone: 'serious',
  content_styles: [],
  protagonist_types: [],
  character_archetypes: [],
  power_types: [],
  power_system: '',
  technology_level: '',
  history: '',
  geography: '',
  parent_world_id: '',
  scope_type: 'root',
  is_default: false,
  inherit_rules: true,
  order_index: 0,
}

const ensureArray = (val: any): string[] => {
  if (!val) return []
  if (Array.isArray(val)) return val
  if (typeof val === 'string') {
    try {
      const parsed = JSON.parse(val)
      return Array.isArray(parsed) ? parsed : []
    } catch {
      return []
    }
  }
  return []
}

const worldToFormData = (world: World): WorldFormData => ({
  name: world.name || '',
  description: world.description || '',
  world_type: world.world_type || 'fantasy',
  tone: world.tone || 'serious',
  content_styles: ensureArray(world.content_styles),
  protagonist_types: ensureArray(world.protagonist_types),
  character_archetypes: ensureArray(world.character_archetypes),
  power_types: ensureArray(world.power_types),
  power_system: world.power_system || '',
  technology_level: world.technology_level || '',
  history: world.history || '',
  geography: world.geography || '',
  parent_world_id: world.parent_world_id || '',
  scope_type: world.scope_type || 'root',
  is_default: Boolean(world.is_default),
  inherit_rules: world.inherit_rules ?? true,
  order_index: world.order_index || 0,
})

export default function Worlds() {
  const { currentProject } = useProject()
  const { theme } = useTheme()
  const isDark = theme === 'dark'

  const [worlds, setWorlds] = useState<World[]>([])
  const [worldId, setWorldId] = useState<string | null>(null)
  const [draftingNewWorld, setDraftingNewWorld] = useState(false)
  const [formData, setFormData] = useState<WorldFormData>(defaultFormData)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [analyzing, setAnalyzing] = useState(false)

  const loadWorlds = useCallback(async () => {
    if (!currentProject?.id) {
      setWorlds([])
      setWorldId(null)
      setDraftingNewWorld(false)
      setFormData({ ...defaultFormData })
      setLoading(false)
      return
    }

    setLoading(true)
    try {
      const data = sortWorldsForDisplay(await getWorlds(currentProject.id))
      setWorlds(data)
      if (draftingNewWorld) {
        return
      }
      const selected = data.find(world => world.id === worldId) || data.find(world => world.id === currentProject.world_id) || data.find(world => world.is_default) || data[0]
      if (selected) {
        setWorldId(selected.id || null)
        setFormData(worldToFormData(selected))
      } else {
        setWorldId(null)
        setFormData({ ...defaultFormData, is_default: true })
      }
    } catch (error) {
      console.error('Failed to load worlds:', error)
    } finally {
      setLoading(false)
    }
  }, [currentProject?.id, currentProject?.world_id, worldId, draftingNewWorld])

  useEffect(() => {
    loadWorlds()
  }, [loadWorlds])

  const selectWorld = (world: World) => {
    setDraftingNewWorld(false)
    setWorldId(world.id || null)
    setFormData(worldToFormData(world))
  }

  const createBlankWorld = (parentWorldId?: string) => {
    setDraftingNewWorld(true)
    setWorldId(null)
    setFormData({
      ...defaultFormData,
      parent_world_id: parentWorldId || '',
      scope_type: parentWorldId ? 'plane' : 'root',
      is_default: worlds.length === 0,
      order_index: worlds.length,
    })
  }

  const handleSave = async () => {
    if (!currentProject?.id || !formData.name.trim()) {
      alert('请填写世界名称')
      return
    }

    setSaving(true)
    try {
      const data = {
        ...formData,
        name: formData.name.trim(),
        project_id: currentProject.id,
        parent_world_id: formData.parent_world_id || null,
      }

      if (worldId && !draftingNewWorld) {
        await updateWorld(worldId, data as UpdateWorldDTO)
      } else {
        const newWorld = await createWorld(data as CreateWorldDTO)
        setDraftingNewWorld(false)
        setWorldId(newWorld.id || null)
      }
      await loadWorlds()
      alert('保存成功')
    } catch (error) {
      console.error('Failed to save world:', error)
      alert('保存失败')
    } finally {
      setSaving(false)
    }
  }

  const handleAnalyze = async () => {
    if (!currentProject?.id || !formData.description) {
      alert('请先填写世界观描述')
      return
    }

    setAnalyzing(true)
    try {
      const { structured_data: result } = await analyzeWorldDescription(currentProject.id, formData.description)
      setFormData(prev => ({
        ...prev,
        power_system: result.power_system || prev.power_system,
        technology_level: result.technology_level || prev.technology_level,
        history: result.history || prev.history,
        geography: result.geography || prev.geography,
      }))
      alert('AI 分析完成')
    } catch (error) {
      console.error('Failed to analyze:', error)
      alert('分析失败')
    } finally {
      setAnalyzing(false)
    }
  }

  const handleTagsChange = (tags: Partial<Record<WorldTagField, string[]>>) => {
    setFormData(prev => {
      const newData = { ...prev }
      Object.entries(tags).forEach(([key, value]) => {
        if (!value) return
        const typedKey = key as WorldTagField
        if (typedKey === 'world_type' || typedKey === 'tone') {
          newData[typedKey] = value.length > 0 ? value[0] : ''
        } else {
          newData[typedKey] = value
        }
      })
      return newData
    })
  }

  const selectedTags: Record<string, string[]> = {
    world_type: formData.world_type ? [formData.world_type] : [],
    tone: formData.tone ? [formData.tone] : [],
    content_styles: Array.isArray(formData.content_styles) ? formData.content_styles : [],
    protagonist_types: Array.isArray(formData.protagonist_types) ? formData.protagonist_types : [],
    power_types: Array.isArray(formData.power_types) ? formData.power_types : [],
    character_archetypes: Array.isArray(formData.character_archetypes) ? formData.character_archetypes : [],
  }

  if (!currentProject) {
    return (
      <PageLayout title="世界观设定">
        <div className={`text-center py-20 ${isDark ? 'text-gray-400' : 'text-gray-500'}`}>
          <Globe size={48} className="mx-auto mb-4 opacity-50" />
          <p>请先选择一个项目</p>
        </div>
      </PageLayout>
    )
  }

  if (loading) {
    return (
      <PageLayout title="世界观设定">
        <div className="flex items-center justify-center py-20">
          <Loader2 size={24} className="animate-spin mr-3" />
          <span className={isDark ? 'text-gray-400' : 'text-gray-500'}>加载中...</span>
        </div>
      </PageLayout>
    )
  }

  return (
    <PageLayout
      title="世界观设定"
      description="构建小说世界的核心设定；多世界项目可在左侧维护根世界与子世界/位面"
      actions={
        <div className="flex gap-2">
          <Button variant="secondary" onClick={() => createBlankWorld()}>
            <Plus size={16} className="mr-2" />
            新建世界
          </Button>
          <Button onClick={handleSave} disabled={saving || !formData.name}>
            {saving ? <Loader2 size={16} className="mr-2 animate-spin" /> : <Save size={16} className="mr-2" />}
            保存
          </Button>
        </div>
      }
    >
      <div className="grid grid-cols-1 xl:grid-cols-[280px_minmax(0,1fr)] gap-4">
        <aside className={`rounded-lg border ${isDark ? 'bg-gray-800 border-gray-700' : 'bg-white border-gray-200'} overflow-hidden`}>
          <div className={`px-4 py-3 border-b flex items-center justify-between ${isDark ? 'border-gray-700' : 'border-gray-200'}`}>
            <div className={`font-medium ${isDark ? 'text-white' : 'text-gray-800'}`}>世界层级</div>
            <button onClick={() => createBlankWorld(worldId || undefined)} className={`text-xs ${isDark ? 'text-blue-300' : 'text-blue-600'}`}>新建子世界</button>
          </div>
          <div className="p-2 space-y-1 max-h-[calc(100vh-240px)] overflow-auto">
            {worlds.length === 0 ? (
              <div className={`p-3 text-sm ${isDark ? 'text-gray-400' : 'text-gray-500'}`}>暂无世界，请创建第一个世界。</div>
            ) : worlds.map(world => {
              const active = world.id === worldId
              const depth = getWorldDepth(world, worlds)
              return (
                <button
                  key={world.id}
                  onClick={() => selectWorld(world)}
                  className={`w-full text-left rounded-lg px-3 py-2 transition-colors ${active ? 'bg-blue-500 text-white' : isDark ? 'text-gray-300 hover:bg-gray-700' : 'text-gray-700 hover:bg-gray-100'}`}
                  style={{ paddingLeft: `${12 + depth * 18}px` }}
                >
                  <div className="font-medium truncate">{world.name || world.id}</div>
                  <div className={`text-xs mt-0.5 ${active ? 'text-blue-100' : isDark ? 'text-gray-500' : 'text-gray-400'}`}>
                    {world.is_default ? '默认 · ' : ''}{world.scope_type || 'root'}
                  </div>
                </button>
              )
            })}
          </div>
        </aside>

        <div className="space-y-4">
          <div className={`rounded-lg p-4 ${isDark ? 'bg-gray-800' : 'bg-white'} shadow`}>
            <div className="flex items-center gap-2 mb-3">
              <Globe size={18} className={isDark ? 'text-gray-400' : 'text-gray-500'} />
              <h3 className={`font-medium ${isDark ? 'text-white' : 'text-gray-800'}`}>基本信息</h3>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4">
              <Input
                label="世界名称"
                value={formData.name}
                onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                placeholder="如：九州大陆、星际联邦、末日副本..."
              />
              <div>
                <label className={`block text-sm font-medium mb-1 ${isDark ? 'text-gray-300' : 'text-gray-700'}`}>父级世界</label>
                <select
                  value={formData.parent_world_id}
                  onChange={(e) => setFormData({ ...formData, parent_world_id: e.target.value, scope_type: e.target.value ? formData.scope_type || 'plane' : 'root' })}
                  className={`w-full px-3 py-2 border rounded-lg ${isDark ? 'bg-gray-700 border-gray-600 text-white' : 'border-gray-300'}`}
                >
                  <option value="">无，作为根世界</option>
                  {worlds.filter(world => world.id !== worldId).map(world => (
                    <option key={world.id} value={world.id}>{formatWorldOptionLabel(world, worlds)}</option>
                  ))}
                </select>
              </div>
              <div>
                <label className={`block text-sm font-medium mb-1 ${isDark ? 'text-gray-300' : 'text-gray-700'}`}>世界作用域</label>
                <select
                  value={formData.scope_type}
                  onChange={(e) => setFormData({ ...formData, scope_type: e.target.value })}
                  className={`w-full px-3 py-2 border rounded-lg ${isDark ? 'bg-gray-700 border-gray-600 text-white' : 'border-gray-300'}`}
                >
                  <option value="root">总世界观/root</option>
                  <option value="plane">位面/子世界</option>
                  <option value="arc_world">篇章世界</option>
                  <option value="instance">副本/实例世界</option>
                  <option value="region_world">区域型世界</option>
                </select>
              </div>
              <Input
                label="排序"
                type="number"
                value={String(formData.order_index)}
                onChange={(e) => setFormData({ ...formData, order_index: Number(e.target.value) || 0 })}
              />
              <label className={`flex items-center gap-2 text-sm ${isDark ? 'text-gray-300' : 'text-gray-700'}`}>
                <input type="checkbox" checked={formData.is_default} onChange={(e) => setFormData({ ...formData, is_default: e.target.checked })} />
                设为项目默认世界
              </label>
              <label className={`flex items-center gap-2 text-sm ${isDark ? 'text-gray-300' : 'text-gray-700'}`}>
                <input type="checkbox" checked={formData.inherit_rules} onChange={(e) => setFormData({ ...formData, inherit_rules: e.target.checked })} />
                继承父级世界观规则
              </label>
            </div>
            <div>
              <div className="flex items-center justify-between mb-1">
                <label className={`text-sm font-medium ${isDark ? 'text-gray-300' : 'text-gray-700'}`}>世界观描述</label>
                <Button variant="secondary" size="sm" onClick={handleAnalyze} disabled={analyzing || !formData.description}>
                  {analyzing ? <Loader2 size={14} className="mr-1 animate-spin" /> : <Sparkles size={14} className="mr-1" />}
                  AI 提取
                </Button>
              </div>
              <textarea
                value={formData.description}
                onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                placeholder="描述世界观背景、规则、特色...AI 可自动提取到其他模块"
                rows={5}
                className={`w-full px-3 py-2 border rounded-lg text-sm ${isDark ? 'bg-gray-700 border-gray-600 text-white' : 'border-gray-300'}`}
              />
            </div>
          </div>

          <div className={`rounded-lg p-4 ${isDark ? 'bg-gray-800' : 'bg-white'} shadow`}>
            <div className="flex items-center gap-2 mb-3">
              <Tags size={18} className={isDark ? 'text-gray-400' : 'text-gray-500'} />
              <h3 className={`font-medium ${isDark ? 'text-white' : 'text-gray-800'}`}>风格标签</h3>
            </div>
            <TagSelector selectedTags={selectedTags} onTagsChange={handleTagsChange} />
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            <div className={`rounded-lg p-4 ${isDark ? 'bg-gray-800' : 'bg-white'} shadow`}>
              <div className="flex items-center gap-2 mb-3">
                <Wand2 size={18} className={isDark ? 'text-gray-400' : 'text-gray-500'} />
                <h3 className={`font-medium ${isDark ? 'text-white' : 'text-gray-800'}`}>力量体系</h3>
              </div>
              <TextArea value={formData.power_system} onChange={(e) => setFormData({ ...formData, power_system: e.target.value })} placeholder="修仙境界、魔法等级、异能分类..." rows={4} />
            </div>
            <div className={`rounded-lg p-4 ${isDark ? 'bg-gray-800' : 'bg-white'} shadow`}>
              <div className="flex items-center gap-2 mb-3">
                <Cpu size={18} className={isDark ? 'text-gray-400' : 'text-gray-500'} />
                <h3 className={`font-medium ${isDark ? 'text-white' : 'text-gray-800'}`}>科技水平</h3>
              </div>
              <TextArea value={formData.technology_level} onChange={(e) => setFormData({ ...formData, technology_level: e.target.value })} placeholder="科技发展水平描述..." rows={4} />
            </div>
            <div className={`rounded-lg p-4 ${isDark ? 'bg-gray-800' : 'bg-white'} shadow`}>
              <div className="flex items-center gap-2 mb-3">
                <Clock size={18} className={isDark ? 'text-gray-400' : 'text-gray-500'} />
                <h3 className={`font-medium ${isDark ? 'text-white' : 'text-gray-800'}`}>世界历史</h3>
              </div>
              <TextArea value={formData.history} onChange={(e) => setFormData({ ...formData, history: e.target.value })} placeholder="重要历史事件、时代划分..." rows={4} />
            </div>
            <div className={`rounded-lg p-4 ${isDark ? 'bg-gray-800' : 'bg-white'} shadow`}>
              <div className="flex items-center gap-2 mb-3">
                <MapPin size={18} className={isDark ? 'text-gray-400' : 'text-gray-500'} />
                <h3 className={`font-medium ${isDark ? 'text-white' : 'text-gray-800'}`}>地理环境</h3>
              </div>
              <TextArea value={formData.geography} onChange={(e) => setFormData({ ...formData, geography: e.target.value })} placeholder="地理分布、重要地点..." rows={4} />
            </div>
          </div>

          <div className={`p-3 rounded-lg flex items-center justify-between ${isDark ? 'bg-gray-800/50' : 'bg-gray-50'}`}>
            <div className="flex items-center gap-2 text-sm">
              <BookOpen size={16} className={isDark ? 'text-gray-400' : 'text-gray-500'} />
              <span className={isDark ? 'text-gray-400' : 'text-gray-500'}>世界观设定将作为 AI 创作、地图、伏笔和工作流的核心参考</span>
            </div>
            <span className={`text-sm ${isDark ? 'text-gray-500' : 'text-gray-400'}`}>{Object.values(selectedTags).flat().length} 个标签</span>
          </div>
        </div>
      </div>
    </PageLayout>
  )
}
