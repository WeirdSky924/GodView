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
  ChevronDown,
  ChevronRight,
  Wand2,
  Settings,
  MapPin,
  Clock,
  Cpu,
  Tags,
  BookOpen,
} from 'lucide-react'
import { useProject } from '@/contexts/ProjectContext'
import { useTheme } from '@/contexts/ThemeContext'

type WorldTagField = 'world_type' | 'tone' | 'content_styles' | 'protagonist_types' | 'power_types' | 'character_archetypes'

// 模块定义
interface ModuleConfig {
  key: string
  title: string
  icon: React.ReactNode
  description: string
  fields: string[]
}

const MODULES: ModuleConfig[] = [
  {
    key: 'basic',
    title: '基本信息',
    icon: <Globe size={18} />,
    description: '世界名称与核心描述',
    fields: ['name', 'description'],
  },
  {
    key: 'tags',
    title: '风格标签',
    icon: <Tags size={18} />,
    description: '世界类型、内容风格、主角类型等',
    fields: ['tags'],
  },
  {
    key: 'power',
    title: '力量体系',
    icon: <Wand2 size={18} />,
    description: '修炼体系、魔法系统、异能设定',
    fields: ['power_system'],
  },
  {
    key: 'tech',
    title: '科技水平',
    icon: <Cpu size={18} />,
    description: '科技发展程度、技术水平',
    fields: ['technology_level'],
  },
  {
    key: 'history',
    title: '世界历史',
    icon: <Clock size={18} />,
    description: '重要历史事件、时代划分',
    fields: ['history'],
  },
  {
    key: 'geography',
    title: '地理环境',
    icon: <MapPin size={18} />,
    description: '地理分布、重要地点',
    fields: ['geography'],
  },
]

// 表单数据类型
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
}

export default function Worlds() {
  const { currentProject } = useProject()
  const { theme } = useTheme()
  const isDark = theme === 'dark'

  const [worldId, setWorldId] = useState<string | null>(null)
  const [formData, setFormData] = useState<WorldFormData>(defaultFormData)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [analyzing, setAnalyzing] = useState(false)
  const [expandedModules, setExpandedModules] = useState<Set<string>>(
    new Set(['basic', 'tags'])
  )

  // 加载世界观设定
  const loadWorld = useCallback(async () => {
    if (!currentProject?.id) {
      setLoading(false)
      return
    }

    setLoading(true)
    try {
      const worlds = await getWorlds(currentProject.id)
      if (worlds && worlds.length > 0) {
        const world = worlds[0]
        setWorldId(world.id || null)

        // 辅助函数：确保返回数组
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

        setFormData({
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
        })
      } else {
        setWorldId(null)
        setFormData({ ...defaultFormData })
      }
    } catch (error) {
      console.error('Failed to load world:', error)
    } finally {
      setLoading(false)
    }
  }, [currentProject?.id])

  useEffect(() => {
    loadWorld()
  }, [loadWorld])

  // 保存
  const handleSave = async () => {
    if (!currentProject?.id || !formData.name) {
      alert('请填写世界名称')
      return
    }

    setSaving(true)
    try {
      const data = { ...formData, project_id: currentProject.id }
      console.log('[Worlds] 保存数据:', data)
      console.log('[Worlds] worldId:', worldId)

      if (worldId) {
        console.log('[Worlds] 调用 updateWorld')
        const result = await updateWorld(worldId, data as UpdateWorldDTO)
        console.log('[Worlds] updateWorld 结果:', result)
      } else {
        console.log('[Worlds] 调用 createWorld')
        const newWorld = await createWorld(data as CreateWorldDTO)
        console.log('[Worlds] createWorld 结果:', newWorld)
        setWorldId(newWorld.id || null)
      }
      alert('保存成功')
    } catch (error) {
      console.error('Failed to save world:', error)
      alert('保存失败')
    } finally {
      setSaving(false)
    }
  }

  // AI 分析
  const handleAnalyze = async () => {
    if (!currentProject?.id || !formData.description) {
      alert('请先填写世界观描述')
      return
    }

    setAnalyzing(true)
    try {
      const { structured_data: result } = await analyzeWorldDescription(
        currentProject.id,
        formData.description,
      )
      setFormData(prev => ({
        ...prev,
        power_system: result.power_system || prev.power_system,
        technology_level: result.technology_level || prev.technology_level,
        history: result.history || prev.history,
        geography: result.geography || prev.geography,
      }))

      // 展开所有模块让用户看到结果
      setExpandedModules(new Set(MODULES.map(m => m.key)))
      alert('AI 分析完成')
    } catch (error) {
      console.error('Failed to analyze:', error)
      alert('分析失败')
    } finally {
      setAnalyzing(false)
    }
  }

  // 切换模块展开
  const toggleModule = (key: string) => {
    const newExpanded = new Set(expandedModules)
    if (newExpanded.has(key)) {
      newExpanded.delete(key)
    } else {
      newExpanded.add(key)
    }
    setExpandedModules(newExpanded)
  }

  // 标签变化
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

  // 确保 selectedTags 中所有字段都是有效数组
  const selectedTags: Record<string, string[]> = {
    world_type: (() => {
      const val = formData.world_type
      if (!val) return []
      if (Array.isArray(val)) return val
      return [val]
    })(),
    tone: (() => {
      const val = formData.tone
      if (!val) return []
      if (Array.isArray(val)) return val
      return [val]
    })(),
    content_styles: Array.isArray(formData.content_styles) ? formData.content_styles : [],
    protagonist_types: Array.isArray(formData.protagonist_types) ? formData.protagonist_types : [],
    power_types: Array.isArray(formData.power_types) ? formData.power_types : [],
    character_archetypes: Array.isArray(formData.character_archetypes) ? formData.character_archetypes : [],
  }

  // 渲染模块内容
  const renderModuleContent = (module: ModuleConfig) => {
    switch (module.key) {
      case 'basic':
        return (
          <div className="space-y-4">
            <Input
              label="世界名称"
              value={formData.name}
              onChange={(e) => setFormData({ ...formData, name: e.target.value })}
              placeholder="如：九州大陆、星际联邦..."
            />
            <div>
              <div className="flex items-center justify-between mb-1">
                <label className={`text-sm font-medium ${isDark ? 'text-gray-300' : 'text-gray-700'}`}>
                  世界观描述
                </label>
                <Button
                  variant="secondary"
                  size="sm"
                  onClick={handleAnalyze}
                  disabled={analyzing || !formData.description}
                >
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
        )
      case 'tags':
        return <TagSelector selectedTags={selectedTags} onTagsChange={handleTagsChange} />
      case 'power':
        return (
          <TextArea
            value={formData.power_system}
            onChange={(e) => setFormData({ ...formData, power_system: e.target.value })}
            placeholder="修仙境界、魔法等级、异能分类..."
            rows={4}
          />
        )
      case 'tech':
        return (
          <TextArea
            value={formData.technology_level}
            onChange={(e) => setFormData({ ...formData, technology_level: e.target.value })}
            placeholder="科技发展水平描述..."
            rows={3}
          />
        )
      case 'history':
        return (
          <TextArea
            value={formData.history}
            onChange={(e) => setFormData({ ...formData, history: e.target.value })}
            placeholder="重要历史事件、时代划分..."
            rows={4}
          />
        )
      case 'geography':
        return (
          <TextArea
            value={formData.geography}
            onChange={(e) => setFormData({ ...formData, geography: e.target.value })}
            placeholder="地理分布、重要地点..."
            rows={4}
          />
        )
      default:
        return null
    }
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
      description="构建小说世界的核心设定"
      actions={
        <Button onClick={handleSave} disabled={saving || !formData.name}>
          {saving ? <Loader2 size={16} className="mr-2 animate-spin" /> : <Save size={16} className="mr-2" />}
          保存
        </Button>
      }
    >
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* 左栏：基本信息 + 标签 */}
        <div className="space-y-4">
          {/* 基本信息 */}
          <div className={`rounded-lg p-4 ${isDark ? 'bg-gray-800' : 'bg-white'} shadow`}>
            <div className="flex items-center gap-2 mb-3">
              <Globe size={18} className={isDark ? 'text-gray-400' : 'text-gray-500'} />
              <h3 className={`font-medium ${isDark ? 'text-white' : 'text-gray-800'}`}>基本信息</h3>
            </div>
            <div className="space-y-3">
              <Input
                label="世界名称"
                value={formData.name}
                onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                placeholder="如：九州大陆、星际联邦..."
              />
              <div>
                <div className="flex items-center justify-between mb-1">
                  <label className={`text-sm font-medium ${isDark ? 'text-gray-300' : 'text-gray-700'}`}>
                    世界观描述
                  </label>
                  <Button
                    variant="secondary"
                    size="sm"
                    onClick={handleAnalyze}
                    disabled={analyzing || !formData.description}
                  >
                    {analyzing ? <Loader2 size={14} className="mr-1 animate-spin" /> : <Sparkles size={14} className="mr-1" />}
                    AI 提取
                  </Button>
                </div>
                <textarea
                  value={formData.description}
                  onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                  placeholder="描述世界观背景、规则...AI可自动提取"
                  rows={6}
                  className={`w-full px-3 py-2 border rounded-lg text-sm ${isDark ? 'bg-gray-700 border-gray-600 text-white' : 'border-gray-300'}`}
                />
              </div>
            </div>
          </div>

          {/* 风格标签 */}
          <div className={`rounded-lg p-4 ${isDark ? 'bg-gray-800' : 'bg-white'} shadow`}>
            <div className="flex items-center gap-2 mb-3">
              <Tags size={18} className={isDark ? 'text-gray-400' : 'text-gray-500'} />
              <h3 className={`font-medium ${isDark ? 'text-white' : 'text-gray-800'}`}>风格标签</h3>
            </div>
            <TagSelector selectedTags={selectedTags} onTagsChange={handleTagsChange} />
          </div>
        </div>

        {/* 右栏：力量体系 + 其他设定 */}
        <div className="space-y-4">
          {/* 力量体系 */}
          <div className={`rounded-lg p-4 ${isDark ? 'bg-gray-800' : 'bg-white'} shadow`}>
            <div className="flex items-center gap-2 mb-3">
              <Wand2 size={18} className={isDark ? 'text-gray-400' : 'text-gray-500'} />
              <h3 className={`font-medium ${isDark ? 'text-white' : 'text-gray-800'}`}>力量体系</h3>
            </div>
            <textarea
              value={formData.power_system}
              onChange={(e) => setFormData({ ...formData, power_system: e.target.value })}
              placeholder="修仙境界、魔法等级、异能分类..."
              rows={4}
              className={`w-full px-3 py-2 border rounded-lg text-sm ${isDark ? 'bg-gray-700 border-gray-600 text-white' : 'border-gray-300'}`}
            />
          </div>

          {/* 科技水平 + 历史 */}
          <div className="grid grid-cols-2 gap-4">
            <div className={`rounded-lg p-4 ${isDark ? 'bg-gray-800' : 'bg-white'} shadow`}>
              <div className="flex items-center gap-2 mb-3">
                <Cpu size={16} className={isDark ? 'text-gray-400' : 'text-gray-500'} />
                <h3 className={`text-sm font-medium ${isDark ? 'text-white' : 'text-gray-800'}`}>科技水平</h3>
              </div>
              <textarea
                value={formData.technology_level}
                onChange={(e) => setFormData({ ...formData, technology_level: e.target.value })}
                placeholder="科技发展程度..."
                rows={3}
                className={`w-full px-3 py-2 border rounded-lg text-sm ${isDark ? 'bg-gray-700 border-gray-600 text-white' : 'border-gray-300'}`}
              />
            </div>
            <div className={`rounded-lg p-4 ${isDark ? 'bg-gray-800' : 'bg-white'} shadow`}>
              <div className="flex items-center gap-2 mb-3">
                <MapPin size={16} className={isDark ? 'text-gray-400' : 'text-gray-500'} />
                <h3 className={`text-sm font-medium ${isDark ? 'text-white' : 'text-gray-800'}`}>地理环境</h3>
              </div>
              <textarea
                value={formData.geography}
                onChange={(e) => setFormData({ ...formData, geography: e.target.value })}
                placeholder="地理分布..."
                rows={3}
                className={`w-full px-3 py-2 border rounded-lg text-sm ${isDark ? 'bg-gray-700 border-gray-600 text-white' : 'border-gray-300'}`}
              />
            </div>
          </div>

          {/* 世界历史 */}
          <div className={`rounded-lg p-4 ${isDark ? 'bg-gray-800' : 'bg-white'} shadow`}>
            <div className="flex items-center gap-2 mb-3">
              <Clock size={18} className={isDark ? 'text-gray-400' : 'text-gray-500'} />
              <h3 className={`font-medium ${isDark ? 'text-white' : 'text-gray-800'}`}>世界历史</h3>
            </div>
            <textarea
              value={formData.history}
              onChange={(e) => setFormData({ ...formData, history: e.target.value })}
              placeholder="重要历史事件、时代划分..."
              rows={4}
              className={`w-full px-3 py-2 border rounded-lg text-sm ${isDark ? 'bg-gray-700 border-gray-600 text-white' : 'border-gray-300'}`}
            />
          </div>
        </div>
      </div>

      {/* 状态栏 */}
      <div className={`mt-4 p-3 rounded-lg flex items-center justify-between ${isDark ? 'bg-gray-800/50' : 'bg-gray-50'}`}>
        <div className="flex items-center gap-2 text-sm">
          <BookOpen size={16} className={isDark ? 'text-gray-400' : 'text-gray-500'} />
          <span className={isDark ? 'text-gray-400' : 'text-gray-500'}>
            世界观设定将作为 AI 创作的核心参考
          </span>
        </div>
        <span className={`text-sm ${isDark ? 'text-gray-500' : 'text-gray-400'}`}>
          {Object.values(selectedTags).flat().length} 个标签
        </span>
      </div>
    </PageLayout>
  )
}
