import { useState, useEffect, useCallback, useRef } from 'react'
import { useSearchParams } from 'react-router-dom'
import { Card, Button, Input, TextArea, Modal } from '@/components/ui'
import PageLayout from '@/components/PageLayout'
import {
  getLoreList,
  getLore,
  createLore,
  updateLore,
  deleteLore,
  searchLore,
  getLoreCategories,
  getLorePriorities,
  bindLoreCharacterReference,
} from '@/api/lore'
import type {
  BindLoreCharacterPayload,
  LoreEntry,
  LoreCategory,
  LorePriority,
  CreateLoreDTO,
  UpdateLoreDTO,
  LoreSearchResult,
} from '@/api/lore'
import { getCharacters, CharacterImportanceTier, TIER_DISPLAY_NAMES, type Character } from '@/api/characters'
import type { CharacterReferenceResolution, UnresolvedCharacterReference } from '@/api/settingAgent'
import {
  Plus, Edit, Trash2, Search, BookOpen, FolderOpen,
  Globe, Map, Clock, Users, Package, Zap, Shield, Star,
  List, TreeDeciduous, MessageCircle,
} from 'lucide-react'
import { LoreTree } from '@/components/lore'
import { SettingAgentChat } from '@/components/setting'
import { useProject } from '@/contexts/ProjectContext'
import { useTheme } from '@/contexts/ThemeContext'
import OutlineRequirementPanel from '@/components/OutlineRequirementPanel'
import {
  updateOutlineResourceRequirementStatus,
  type OutlineResourceRequirement,
} from '@/api/outlines'
import { formatApiErrorMessage } from '@/api/workflows'
import { formatRequirementSummary } from '@/utils/resourceRequirementDisplay'

const categoryIcons: Record<LoreCategory, React.ReactNode> = {
  world_rule: <Shield size={18} />,
  geography: <Map size={18} />,
  history: <Clock size={18} />,
  faction: <Users size={18} />,
  culture: <Globe size={18} />,
  race: <Users size={18} />,
  profession: <Package size={18} />,
  character_setting: <Users size={18} />,
  item: <Package size={18} />,
  skill: <Zap size={18} />,
  custom: <Star size={18} />,
}

const priorityLabels: Record<LorePriority, string> = {
  constitutional: '宪法级',
  core: '核心',
  standard: '标准',
  flexible: '灵活',
}

const loreCategories = new Set<LoreCategory>([
  'world_rule',
  'geography',
  'history',
  'faction',
  'culture',
  'race',
  'profession',
  'character_setting',
  'item',
  'skill',
  'custom',
])

const requirementTypeCategoryMap: Record<string, LoreCategory> = {
  setting: 'world_rule',
  '设定': 'world_rule',
  faction: 'faction',
  organization: 'faction',
  '势力': 'faction',
  '组织': 'faction',
  item: 'item',
  '道具': 'item',
  ability: 'skill',
  '能力': 'skill',
  relationship: 'character_setting',
  character_state: 'character_setting',
  continuity: 'world_rule',
  event_rule: 'world_rule',
  crisis_resolution: 'world_rule',
  crisis: 'world_rule',
  '关系': 'character_setting',
  '关系变化': 'character_setting',
  '角色状态': 'character_setting',
  '连续性': 'world_rule',
  '事件规则': 'world_rule',
  '危机解法': 'world_rule',
  '危机': 'world_rule',
}

const normalizeLoreCategory = (value: unknown, requirementType?: unknown): LoreCategory => {
  const category = String(value || '').trim().toLowerCase() as LoreCategory
  if (loreCategories.has(category)) return category
  const normalizedRequirementType = String(requirementType || '').trim().toLowerCase()
  return requirementTypeCategoryMap[normalizedRequirementType] || 'custom'
}

const normalizeStringArray = (value: unknown): string[] => {
  if (Array.isArray(value)) {
    return value.filter((item): item is string => typeof item === 'string')
  }

  if (typeof value === 'string') {
    try {
      const parsed = JSON.parse(value)
      return Array.isArray(parsed)
        ? parsed.filter((item): item is string => typeof item === 'string')
        : []
    } catch {
      return value
        .split(/[，,\n]/)
        .map(item => item.trim())
        .filter(Boolean)
    }
  }

  return []
}

const normalizeLorePriority = (value: unknown): LorePriority => {
  if (value === 'constitutional' || value === 'core' || value === 'standard' || value === 'flexible') {
    return value
  }

  if (value === 'low') return 'flexible'
  if (value === 'medium') return 'standard'
  if (value === 'high') return 'core'

  return 'standard'
}

export default function Lore() {
  const { currentProject } = useProject()
  const { theme } = useTheme()
  const isDark = theme === 'dark'
  const [searchParams, setSearchParams] = useSearchParams()

  const [loreList, setLoreList] = useState<LoreEntry[]>([])
  const [loading, setLoading] = useState(true)
  const [selectedLore, setSelectedLore] = useState<LoreEntry | null>(null)
  const [showModal, setShowModal] = useState(false)
  const [editingLore, setEditingLore] = useState<LoreEntry | null>(null)
  const [searchQuery, setSearchQuery] = useState('')
  const [filterCategory, setFilterCategory] = useState<LoreCategory | ''>('')
  const [filterPriority, setFilterPriority] = useState<LorePriority | ''>('')
  const [categories, setCategories] = useState<Array<{ value: string; label: string }>>([])
  const [priorities, setPriorities] = useState<Array<{ value: string; label: string }>>([])

  const [formData, setFormData] = useState<CreateLoreDTO>({
    id: '',
    project_id: '',
    title: '',
    category: 'custom',
    priority: 'standard',
    content: '',
    summary: '',
    keywords: [],
    tags: [],
    constraints: [],
    related_characters: [],
    related_locations: [],
    related_items: [],
    forbidden_actions: [],
    source: '',
  })
  const [keywordsInput, setKeywordsInput] = useState('')
  const [pendingRequirement, setPendingRequirement] = useState<OutlineResourceRequirement | null>(null)
  const [focusedRequirement, setFocusedRequirement] = useState<OutlineResourceRequirement | null>(null)
  const [requirementRefreshKey, setRequirementRefreshKey] = useState(0)
  const [viewMode, setViewMode] = useState<'list' | 'tree'>('list')
  const [showAgentChat, setShowAgentChat] = useState(false)
  const [bindingRef, setBindingRef] = useState<UnresolvedCharacterReference | null>(null)
  const [bindForm, setBindForm] = useState<BindLoreCharacterPayload>({ name: '', description: '', aliases: [], status: 'active', importance_tier: CharacterImportanceTier.NPC })
  const [bindAliasesInput, setBindAliasesInput] = useState('')
  const [bindingLoadingKey, setBindingLoadingKey] = useState<string | null>(null)
  const [referenceBindError, setReferenceBindError] = useState<string | null>(null)
  const [charactersForBinding, setCharactersForBinding] = useState<Character[]>([])
  const [loadingCharactersForBinding, setLoadingCharactersForBinding] = useState(false)
  const [selectedExistingCharacterId, setSelectedExistingCharacterId] = useState('')

  const getPriorityColors = (priority?: LorePriority): string => {
    const colors: Record<string, { light: string; dark: string }> = {
      constitutional: {
        light: 'bg-red-100 text-red-700 border-red-200',
        dark: 'bg-red-900/30 text-red-300 border-red-800'
      },
      core: {
        light: 'bg-orange-100 text-orange-700 border-orange-200',
        dark: 'bg-orange-900/30 text-orange-300 border-orange-800'
      },
      standard: {
        light: 'bg-blue-100 text-blue-700 border-blue-200',
        dark: 'bg-blue-900/30 text-blue-300 border-blue-800'
      },
      flexible: {
        light: 'bg-gray-100 text-gray-700 border-gray-200',
        dark: 'bg-gray-800 text-gray-300 border-gray-600'
      }
    }
    const validPriority = priority && colors[priority] ? priority : 'standard'
    return isDark ? colors[validPriority].dark : colors[validPriority].light
  }

  const loadLore = useCallback(async () => {
    if (!currentProject) {
      setLoreList([])
      setLoading(false)
      return
    }
    setLoading(true)
    try {
      const data = await getLoreList(
        currentProject.id,
        filterCategory || undefined,
        filterPriority || undefined,
        searchQuery || undefined,
      )
      setLoreList(data)
    } catch (error) {
      console.error('Failed to load lore:', error)
    } finally {
      setLoading(false)
    }
  }, [currentProject, filterCategory, filterPriority, searchQuery])

  useEffect(() => {
    loadLore()
  }, [loadLore])

  useEffect(() => {
    const loadOptions = async () => {
      try {
        const [cats, pris] = await Promise.all([
          getLoreCategories(),
          getLorePriorities(),
        ])
        setCategories(cats)
        setPriorities(pris)
      } catch (error) {
        console.error('Failed to load options:', error)
      }
    }
    loadOptions()
  }, [])

  const focusRequirementId = searchParams.get('requirement_id')
  const shouldAutoCreateFromRequirement = searchParams.get('action') === 'create'
  const autoOpenedRequirementIdRef = useRef<string | null>(null)

  const clearRequirementRecoveryParams = useCallback(() => {
    if (!searchParams.has('requirement_id') && !searchParams.has('action')) return
    const next = new URLSearchParams(searchParams)
    next.delete('requirement_id')
    next.delete('action')
    setSearchParams(next, { replace: true })
  }, [searchParams, setSearchParams])

  const openCreateModal = (requirement?: OutlineResourceRequirement) => {
    if (!currentProject) return
    const payload = requirement?.suggested_payload || {}
    const title = String(payload.title || payload.name || requirement?.resource_name || '')
    const content = String(payload.content || payload.description || payload.summary || requirement?.reason || '')
    const keywords = normalizeStringArray(payload.keywords)
    setEditingLore(null)
    setFormData({
      id: String(payload.id || `lore_${Date.now()}`),
      project_id: currentProject.id,
      title,
      category: normalizeLoreCategory(payload.category, requirement?.requirement_type),
      priority: normalizeLorePriority(payload.priority),
      content,
      summary: String(payload.summary || ''),
      keywords,
      tags: normalizeStringArray(payload.tags),
      constraints: normalizeStringArray(payload.constraints),
      related_characters: normalizeStringArray(payload.related_characters),
      related_locations: normalizeStringArray(payload.related_locations),
      related_items: normalizeStringArray(payload.related_items),
      forbidden_actions: normalizeStringArray(payload.forbidden_actions),
      source: requirement ? `outline_resource_requirement:${requirement.id}` : String(payload.source || ''),
    })
    setKeywordsInput(keywords.join('，'))
    setPendingRequirement(requirement || null)
    setShowModal(true)
  }

  useEffect(() => {
    if (!shouldAutoCreateFromRequirement || !focusedRequirement || showModal || pendingRequirement) return
    if (autoOpenedRequirementIdRef.current === focusedRequirement.id) return
    autoOpenedRequirementIdRef.current = focusedRequirement.id
    openCreateModal(focusedRequirement)
  }, [shouldAutoCreateFromRequirement, focusedRequirement, showModal, pendingRequirement])

  const openEditModal = (lore: LoreEntry) => {
    const keywords = normalizeStringArray(lore.keywords)

    setEditingLore(lore)
    setFormData({
      id: lore.id,
      project_id: lore.project_id,
      title: lore.title,
      category: lore.category,
      priority: normalizeLorePriority(lore.priority),
      content: lore.content,
      summary: lore.summary || '',
      keywords,
      tags: normalizeStringArray(lore.tags),
      constraints: normalizeStringArray(lore.constraints),
      related_characters: normalizeStringArray(lore.related_characters),
      related_locations: normalizeStringArray(lore.related_locations),
      related_items: normalizeStringArray(lore.related_items),
      forbidden_actions: normalizeStringArray(lore.forbidden_actions),
      source: lore.source || '',
    })
    setKeywordsInput(keywords.join('，'))
    setPendingRequirement(null)
    setShowModal(true)
  }

  const applyReferenceResolutionToLore = (lore: LoreEntry, resolution: CharacterReferenceResolution): LoreEntry => ({
    ...lore,
    related_characters: resolution.related_characters,
    related_character_refs: resolution.related_character_refs,
    unresolved_character_refs: resolution.unresolved_character_refs,
    updated_at: new Date().toISOString(),
  })

  const updateLoreReferenceState = (loreId: string, resolution: CharacterReferenceResolution) => {
    setLoreList(prev => prev.map(lore => lore.id === loreId ? applyReferenceResolutionToLore(lore, resolution) : lore))
    setSelectedLore(prev => prev && prev.id === loreId ? applyReferenceResolutionToLore(prev, resolution) : prev)
  }

  const loadCharactersForBinding = async () => {
    if (!currentProject || loadingCharactersForBinding) return
    setLoadingCharactersForBinding(true)
    try {
      const characters = await getCharacters(currentProject.id)
      setCharactersForBinding(characters)
    } catch (error) {
      console.error('Failed to load characters for binding:', error)
      setReferenceBindError(formatApiErrorMessage(error, '加载角色候选失败'))
    } finally {
      setLoadingCharactersForBinding(false)
    }
  }

  const openCreateBindModal = (ref: UnresolvedCharacterReference) => {
    setBindingRef(ref)
    setReferenceBindError(null)
    setBindAliasesInput('')
    setBindForm({
      name: ref.source_text,
      aliases: [],
      status: 'active',
      importance_tier: CharacterImportanceTier.NPC,
      description: selectedLore ? `由设定「${selectedLore.title}」中的未解析角色引用「${ref.source_text}」创建。` : '',
      has_agent: false,
      agent_enabled: true,
    })
  }

  const bindReference = async (ref: UnresolvedCharacterReference, characterId: string) => {
    if (!currentProject || !selectedLore || !characterId) return
    const loadingKey = `${ref.source_text}:existing:${characterId}`
    setBindingLoadingKey(loadingKey)
    setReferenceBindError(null)
    try {
      const result = await bindLoreCharacterReference(selectedLore.id, {
        project_id: currentProject.id,
        source_text: ref.source_text,
        action: 'bind_existing',
        character_id: characterId,
        provenance: {
          surface: 'lore_page',
          operation: 'bind_unresolved_reference_existing',
          lore_id: selectedLore.id,
          lore_title: selectedLore.title,
        },
      })
      updateLoreReferenceState(selectedLore.id, result.character_reference_resolution)
      await loadLore()
    } catch (error) {
      setReferenceBindError(formatApiErrorMessage(error, '绑定角色引用失败'))
    } finally {
      setBindingLoadingKey(null)
    }
  }

  const createAndBindReference = async () => {
    if (!currentProject || !selectedLore || !bindingRef || !bindForm.name?.trim()) return
    const loadingKey = `${bindingRef.source_text}:create`
    setBindingLoadingKey(loadingKey)
    setReferenceBindError(null)
    try {
      const result = await bindLoreCharacterReference(selectedLore.id, {
        project_id: currentProject.id,
        source_text: bindingRef.source_text,
        action: 'create_character',
        character: {
          ...bindForm,
          name: bindForm.name.trim(),
          aliases: bindAliasesInput.split(/[，,\n]/).map(item => item.trim()).filter(Boolean),
        },
        provenance: {
          surface: 'lore_page',
          operation: 'create_character_from_unresolved_reference',
          lore_id: selectedLore.id,
          lore_title: selectedLore.title,
        },
      })
      updateLoreReferenceState(selectedLore.id, result.character_reference_resolution)
      setBindingRef(null)
      await loadLore()
    } catch (error) {
      setReferenceBindError(formatApiErrorMessage(error, '创建并绑定角色失败'))
    } finally {
      setBindingLoadingKey(null)
    }
  }

  const saveLore = async () => {
    if (!formData.title || !formData.content) return

    const keywords = keywordsInput.split(/[，,\n]/).map(k => k.trim()).filter(Boolean)
    const tags = normalizeStringArray(formData.tags)
    const constraints = normalizeStringArray(formData.constraints)
    const relatedCharacters = normalizeStringArray(formData.related_characters)
    const relatedLocations = normalizeStringArray(formData.related_locations)
    const relatedItems = normalizeStringArray(formData.related_items)
    const forbiddenActions = normalizeStringArray(formData.forbidden_actions)

    try {
      if (editingLore) {
        const data: UpdateLoreDTO = {
          title: formData.title,
          category: formData.category,
          priority: normalizeLorePriority(formData.priority),
          content: formData.content,
          summary: formData.summary,
          keywords,
          tags,
          constraints,
          related_characters: relatedCharacters,
          related_locations: relatedLocations,
          related_items: relatedItems,
          forbidden_actions: forbiddenActions,
          source: formData.source,
        }
        await updateLore(editingLore.id, data)
        if (selectedLore?.id === editingLore.id) {
          setSelectedLore({
            ...selectedLore,
            ...data,
            priority: normalizeLorePriority(data.priority ?? selectedLore.priority),
            keywords,
            tags,
            constraints,
            related_characters: relatedCharacters,
            related_locations: relatedLocations,
            related_items: relatedItems,
            forbidden_actions: forbiddenActions,
          })
        }
      } else {
        const data: CreateLoreDTO = {
          ...formData,
          keywords,
          tags,
          constraints,
          related_characters: relatedCharacters,
          related_locations: relatedLocations,
          related_items: relatedItems,
          forbidden_actions: forbiddenActions,
        }
        const created = await createLore(data)
        if (pendingRequirement && created.id) {
          await updateOutlineResourceRequirementStatus(pendingRequirement.id, {
            status: 'resolved',
            matched_resource_id: created.id,
            matched_resource_type: 'lore',
            resolution_method: 'create_resource',
          })
          setFocusedRequirement(null)
          setRequirementRefreshKey(value => value + 1)
          clearRequirementRecoveryParams()
        }
      }
      await loadLore()
      setPendingRequirement(null)
      setShowModal(false)
    } catch (error: any) {
      const responseData = error?.response?.data
      const validationDetail = responseData?.detail
      const serializedResponseData = responseData ? JSON.stringify(responseData, null, 2) : null
      const serializedValidationDetail = validationDetail ? JSON.stringify(validationDetail, null, 2) : null

      console.error('Failed to save lore:', error)
      console.error('Lore save response data:', responseData)
      console.error('Lore save response data JSON:', serializedResponseData)
      console.error('Lore save validation detail:', validationDetail)
      console.error('Lore save validation detail JSON:', serializedValidationDetail)
      alert(serializedValidationDetail || formatApiErrorMessage(error, '保存失败，请重试'))
    }
  }

  const handleDelete = async (id: string) => {
    if (!confirm('确定要删除这个设定吗？')) return
    try {
      await deleteLore(id)
      await loadLore()
      if (selectedLore?.id === id) {
        setSelectedLore(null)
      }
    } catch (error) {
      console.error('Failed to delete lore:', error)
    }
  }

  const filteredLore = loreList.filter(lore => {
    if (filterCategory && lore.category !== filterCategory) return false
    if (filterPriority && lore.priority !== filterPriority) return false
    if (searchQuery) {
      const query = searchQuery.toLowerCase()
      return (
        lore.title.toLowerCase().includes(query) ||
        lore.content.toLowerCase().includes(query) ||
        lore.keywords.some(k => k.toLowerCase().includes(query))
      )
    }
    return true
  })

  return (
    <div className={showAgentChat ? 'pr-96' : ''}>
      <PageLayout
        title="设定库"
        description="管理世界观设定和规则"
        actions={
          <div className="flex gap-2">
            <Button
              variant={showAgentChat ? 'primary' : 'secondary'}
              onClick={() => setShowAgentChat(!showAgentChat)}
            >
              <MessageCircle size={20} className="mr-2" />
              设定助手
            </Button>
            <Button onClick={() => openCreateModal()} disabled={!currentProject}>
              <Plus size={20} className="mr-2" />
              新建设定
            </Button>
          </div>
        }
      >
        {!currentProject ? (
          <div className={`text-center py-20 ${isDark ? 'text-gray-400' : 'text-gray-500'}`}>
            <FolderOpen size={48} className="mx-auto mb-4 opacity-50" />
            <p>请先在侧边栏选择一个项目</p>
          </div>
        ) : loading ? (
          <div className="flex items-center justify-center py-20">
            <BookOpen size={24} className="animate-spin mr-3" />
            <span className={isDark ? 'text-gray-400' : 'text-gray-500'}>加载设定...</span>
          </div>
        ) : (
          <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
            {/* 左侧：筛选器和列表 */}
            <div className="lg:col-span-1 space-y-4">
              {focusedRequirement && (
                <div className={`rounded-xl border px-4 py-3 ${isDark ? 'border-blue-800 bg-blue-950/40 text-blue-100' : 'border-blue-200 bg-blue-50 text-blue-900'}`}>
                  <div className="text-sm font-semibold">正在补齐启动阻塞资源</div>
                  <div className="mt-1 text-sm opacity-90">{formatRequirementSummary(focusedRequirement)}</div>
                  <div className="mt-1 text-xs opacity-75">创建或绑定设定后，系统会自动把该资源需求标记为已解决并刷新章节 readiness。</div>
                </div>
              )}
              <OutlineRequirementPanel
                projectId={currentProject.id}
                focusRequirementId={focusRequirementId}
                onFocusedRequirementLoaded={setFocusedRequirement}
                requirementTypes={[
                  'lore', 'setting', '设定',
                  'faction', 'organization', '势力', '组织',
                  'item', 'ability', '道具', '能力',
                  'relationship', 'character_state', 'continuity', 'event_rule', 'crisis_resolution',
                  '关系', '关系变化', '角色状态', '连续性', '事件规则', '危机解法',
                ]}
                title="大纲待补设定"
                description="来自大纲的设定、势力、道具、能力、关系和危机解法等资源缺口，可预填新建设定、绑定已有设定或标记处理状态。创建/绑定后会标记需求为已解决。"
                onCreate={openCreateModal}
                bindableResources={loreList.map(lore => ({
                  id: lore.id,
                  label: lore.title,
                  type: 'lore',
                  description: lore.category,
                }))}
                onBound={async () => {
                  await loadLore()
                  setFocusedRequirement(null)
                  clearRequirementRecoveryParams()
                }}
                onRequirementChanged={(requirement, status) => {
                  setRequirementRefreshKey(value => value + 1)
                  if (requirement?.id === focusRequirementId && (status === 'resolved' || status === 'ignored' || status === 'superseded')) {
                    setFocusedRequirement(null)
                    clearRequirementRecoveryParams()
                  }
                }}
                refreshKey={requirementRefreshKey}
              />
              {/* 搜索 */}
              <Card className="p-4">
                <div className="relative">
                  <Search size={18} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
                  <input
                    type="text"
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                    placeholder="搜索设定..."
                    className={`w-full pl-10 pr-4 py-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 ${isDark ? 'bg-gray-800 border-gray-600 text-white' : 'border-gray-300'}`}
                  />
                </div>
              </Card>

              {/* 类别筛选 */}
              <Card className="p-4">
                <h3 className={`font-medium mb-3 ${isDark ? 'text-white' : 'text-gray-800'}`}>类别</h3>
                <div className="space-y-2">
                  <button
                    onClick={() => setFilterCategory('')}
                    className={`w-full text-left px-3 py-2 rounded-lg text-sm ${
                      filterCategory === '' ? (isDark ? 'bg-blue-900/30 text-blue-300' : 'bg-blue-50 text-blue-700') : (isDark ? 'hover:bg-gray-700' : 'hover:bg-gray-50')
                    }`}
                  >
                    全部
                  </button>
                  {categories.map(cat => (
                    <button
                      key={cat.value}
                      onClick={() => setFilterCategory(cat.value as LoreCategory)}
                      className={`w-full text-left px-3 py-2 rounded-lg text-sm flex items-center gap-2 ${
                        filterCategory === cat.value ? (isDark ? 'bg-blue-900/30 text-blue-300' : 'bg-blue-50 text-blue-700') : (isDark ? 'hover:bg-gray-700' : 'hover:bg-gray-50')
                      }`}
                    >
                      {categoryIcons[cat.value as LoreCategory]}
                      {cat.label}
                    </button>
                  ))}
                </div>
              </Card>

              {/* 优先级筛选 */}
              <Card className="p-4">
                <h3 className={`font-medium mb-3 ${isDark ? 'text-white' : 'text-gray-800'}`}>优先级</h3>
                <div className="space-y-2">
                  <button
                    onClick={() => setFilterPriority('')}
                    className={`w-full text-left px-3 py-2 rounded-lg text-sm ${
                      filterPriority === '' ? (isDark ? 'bg-blue-900/30 text-blue-300' : 'bg-blue-50 text-blue-700') : (isDark ? 'hover:bg-gray-700' : 'hover:bg-gray-50')
                    }`}
                  >
                    全部
                  </button>
                  {priorities.map(pri => (
                    <button
                      key={pri.value}
                      onClick={() => setFilterPriority(pri.value as LorePriority)}
                      className={`w-full text-left px-3 py-2 rounded-lg text-sm ${
                        filterPriority === pri.value ? (isDark ? 'bg-blue-900/30 text-blue-300' : 'bg-blue-50 text-blue-700') : (isDark ? 'hover:bg-gray-700' : 'hover:bg-gray-50')
                      }`}
                    >
                      {pri.label}
                    </button>
                  ))}
                </div>
              </Card>
            </div>

            {/* 中间：设定列表/树形视图 */}
            <div className="lg:col-span-1">
              <Card className="h-[calc(100vh-200px)] overflow-hidden flex flex-col" noPadding>
                <div className={`p-4 border-b flex items-center justify-between flex-shrink-0 ${isDark ? 'bg-gray-900 border-gray-700' : 'bg-white border-gray-200'}`}>
                  <h3 className={`font-medium ${isDark ? 'text-white' : 'text-gray-800'}`}>
                    {viewMode === 'list' ? `设定列表 (${filteredLore.length})` : '设定树'}
                  </h3>
                  <div className={`flex rounded-lg p-0.5 ${isDark ? 'bg-gray-800' : 'bg-gray-100'}`}>
                    <button
                      onClick={() => setViewMode('list')}
                      className={`p-1.5 rounded ${viewMode === 'list' ? (isDark ? 'bg-gray-700 shadow-sm' : 'bg-white shadow-sm') : (isDark ? 'hover:bg-gray-600' : 'hover:bg-gray-200')}`}
                      title="列表视图"
                    >
                      <List size={16} className={isDark ? 'text-gray-300' : 'text-gray-600'} />
                    </button>
                    <button
                      onClick={() => setViewMode('tree')}
                      className={`p-1.5 rounded ${viewMode === 'tree' ? (isDark ? 'bg-gray-700 shadow-sm' : 'bg-white shadow-sm') : (isDark ? 'hover:bg-gray-600' : 'hover:bg-gray-200')}`}
                      title="树形视图"
                    >
                      <TreeDeciduous size={16} className={isDark ? 'text-gray-300' : 'text-gray-600'} />
                    </button>
                  </div>
                </div>
                <div className="flex-1 overflow-y-auto min-h-0">
                  {viewMode === 'list' ? (
                    <div className="divide-y">
                      {filteredLore.length === 0 ? (
                        <div className={`p-8 text-center ${isDark ? 'text-gray-400' : 'text-gray-500'}`}>
                          暂无设定
                        </div>
                      ) : (
                        filteredLore.map(lore => (
                          <div
                            key={lore.id}
                            onClick={() => setSelectedLore(lore)}
                            className={`p-4 cursor-pointer transition-colors ${
                              selectedLore?.id === lore.id ? (isDark ? 'bg-blue-900/30' : 'bg-blue-50') : (isDark ? 'hover:bg-gray-700' : 'hover:bg-gray-50')
                            }`}
                          >
                            <div className="flex items-start gap-3">
                              <div className={`mt-1 ${isDark ? 'text-gray-400' : 'text-gray-500'}`}>
                                {categoryIcons[lore.category]}
                              </div>
                              <div className="flex-1 min-w-0">
                                <h4 className={`font-medium truncate ${isDark ? 'text-white' : 'text-gray-800'}`}>{lore.title}</h4>
                                <p className={`text-sm mt-1 line-clamp-2 ${isDark ? 'text-gray-400' : 'text-gray-500'}`}>
                                  {lore.summary || (lore.content ? lore.content.slice(0, 100) : '')}
                                </p>
                                <div className="flex items-center gap-2 mt-2">
                                  <span className={`text-xs px-2 py-0.5 rounded border ${getPriorityColors(lore.priority)}`}>
                                    {priorityLabels[lore.priority]}
                                  </span>
                                </div>
                              </div>
                            </div>
                          </div>
                        ))
                      )}
                    </div>
                  ) : (
                    <LoreTree
                      loreList={filteredLore}
                      selectedLoreId={selectedLore?.id}
                      onSelectLore={setSelectedLore}
                    />
                  )}
                </div>
              </Card>
            </div>

            {/* 右侧：设定详情 */}
            <div className="lg:col-span-2">
              {!selectedLore ? (
                <Card className={`h-[calc(100vh-200px)] flex items-center justify-center ${isDark ? 'text-gray-400' : 'text-gray-500'}`}>
                  <div className="text-center">
                    <BookOpen size={48} className="mx-auto mb-4 opacity-50" />
                    <p>选择一个设定查看详情</p>
                  </div>
                </Card>
              ) : (
                <Card className="h-[calc(100vh-200px)] overflow-y-auto">
                  <div className="p-6">
                    {/* 头部 */}
                    <div className="mb-6">
                      <div className="flex items-center gap-3 mb-2">
                        {categoryIcons[selectedLore.category]}
                        <span className={`text-xs px-2 py-0.5 rounded border ${getPriorityColors(selectedLore.priority)}`}>
                          {priorityLabels[selectedLore.priority]}
                        </span>
                        <div className="flex-1" />
                        <div className="flex gap-2 flex-shrink-0">
                          <Button variant="secondary" size="sm" onClick={() => openEditModal(selectedLore)}>
                            <Edit size={16} className="mr-1" /> 编辑
                          </Button>
                          <Button variant="danger" size="sm" onClick={() => handleDelete(selectedLore.id)}>
                            <Trash2 size={16} className="mr-1" /> 删除
                          </Button>
                        </div>
                      </div>
                      <h2 className={`text-2xl font-bold ${isDark ? 'text-white' : 'text-gray-800'}`}>{selectedLore.title}</h2>
                      {selectedLore.summary && (
                        <p className={`mt-2 ${isDark ? 'text-gray-400' : 'text-gray-600'}`}>{selectedLore.summary}</p>
                      )}
                    </div>

                    {/* 内容 */}
                    <div className="prose max-w-none mb-6">
                      <pre className={`whitespace-pre-wrap font-sans text-sm p-4 rounded-lg ${isDark ? 'text-gray-300 bg-gray-800' : 'text-gray-700 bg-gray-50'}`}>
                        {selectedLore.content}
                      </pre>
                    </div>

                    {/* 关键词 */}
                    {selectedLore.keywords.length > 0 && (
                      <div className="mb-6">
                        <h3 className={`font-medium mb-2 ${isDark ? 'text-white' : 'text-gray-800'}`}>关键词</h3>
                        <div className="flex flex-wrap gap-2">
                          {selectedLore.keywords.map((kw, i) => (
                            <span key={i} className={`px-3 py-1 rounded-full text-sm ${isDark ? 'bg-gray-700 text-gray-300' : 'bg-gray-100 text-gray-700'}`}>
                              {kw}
                            </span>
                          ))}
                        </div>
                      </div>
                    )}

                    {/* 约束条件 */}
                    {selectedLore.constraints.length > 0 && (
                      <div className="mb-6">
                        <h3 className={`font-medium mb-2 ${isDark ? 'text-white' : 'text-gray-800'}`}>约束条件</h3>
                        <ul className={`list-disc list-inside text-sm space-y-1 ${isDark ? 'text-gray-300' : 'text-gray-700'}`}>
                          {selectedLore.constraints.map((c, i) => (
                            <li key={i}>{c}</li>
                          ))}
                        </ul>
                      </div>
                    )}

                    {/* 角色引用解析 */}
                    {((selectedLore.related_character_refs?.length || 0) > 0 || (selectedLore.unresolved_character_refs?.length || 0) > 0) && (
                      <div className={`mb-6 rounded-xl border p-4 ${isDark ? 'border-gray-700 bg-gray-900/50' : 'border-gray-200 bg-white'}`}>
                        <div className="mb-3 flex items-center justify-between gap-3">
                          <h3 className={`font-medium ${isDark ? 'text-white' : 'text-gray-800'}`}>角色引用解析</h3>
                          <span className={`text-xs ${isDark ? 'text-gray-400' : 'text-gray-500'}`}>canonical related_characters 只保存已绑定角色 ID</span>
                        </div>
                        {referenceBindError && (
                          <div className={`mb-3 rounded-lg px-3 py-2 text-sm ${isDark ? 'bg-red-950/40 text-red-200' : 'bg-red-50 text-red-700'}`}>{referenceBindError}</div>
                        )}
                        {(selectedLore.related_character_refs || []).length > 0 && (
                          <div className="mb-3 space-y-2">
                            <div className={`text-xs font-medium ${isDark ? 'text-green-300' : 'text-green-700'}`}>已绑定角色</div>
                            {(selectedLore.related_character_refs || []).map((ref, index) => (
                              <div key={`${ref.character_id}-${index}`} className={`rounded-lg px-3 py-2 text-sm ${isDark ? 'bg-green-950/30 text-green-100' : 'bg-green-50 text-green-800'}`}>
                                {ref.source_text} → <span className="font-medium">{ref.character_name}</span>
                                <span className="ml-2 text-xs opacity-70">{ref.resolution_method}</span>
                              </div>
                            ))}
                          </div>
                        )}
                        {(selectedLore.unresolved_character_refs || []).length > 0 && (
                          <div className="space-y-3">
                            <div className={`text-xs font-medium ${isDark ? 'text-amber-300' : 'text-amber-700'}`}>待处理引用</div>
                            {(selectedLore.unresolved_character_refs || []).map((ref, index) => (
                              <div key={`${ref.source_text}-${index}`} className={`rounded-xl border p-3 text-sm ${isDark ? 'border-amber-800/60 bg-amber-950/20 text-amber-100' : 'border-amber-200 bg-amber-50 text-amber-900'}`}>
                                <div className="font-medium">{ref.source_text}</div>
                                <div className="mt-1 text-xs opacity-80">{ref.message || ref.reason}</div>
                                {ref.candidates?.length > 0 && (
                                  <div className="mt-2 flex flex-wrap gap-2">
                                    {ref.candidates.map(candidate => {
                                      const loadingKey = `${ref.source_text}:existing:${candidate.character_id}`
                                      return (
                                        <Button
                                          key={candidate.character_id}
                                          size="sm"
                                          variant="secondary"
                                          onClick={() => bindReference(ref, candidate.character_id)}
                                          disabled={bindingLoadingKey === loadingKey}
                                        >
                                          绑定候选：{candidate.name}
                                        </Button>
                                      )
                                    })}
                                  </div>
                                )}
                                <div className="mt-3 flex flex-wrap items-center gap-2">
                                  <Button size="sm" onClick={() => openCreateBindModal(ref)} disabled={Boolean(bindingLoadingKey)}>
                                    创建角色并绑定
                                  </Button>
                                  <Button size="sm" variant="secondary" onClick={loadCharactersForBinding} disabled={loadingCharactersForBinding}>
                                    {loadingCharactersForBinding ? '加载中...' : '选择其他已有角色'}
                                  </Button>
                                  {charactersForBinding.length > 0 && (
                                    <>
                                      <select
                                        value={selectedExistingCharacterId}
                                        onChange={(event) => setSelectedExistingCharacterId(event.target.value)}
                                        className={`rounded border px-2 py-1 text-sm ${isDark ? 'border-gray-700 bg-gray-950 text-gray-200' : 'border-amber-200 bg-white text-gray-700'}`}
                                      >
                                        <option value="">选择已有角色</option>
                                        {charactersForBinding.map(character => (
                                          <option key={character.id} value={character.id}>{character.name}</option>
                                        ))}
                                      </select>
                                      <Button size="sm" variant="secondary" onClick={() => selectedExistingCharacterId && bindReference(ref, selectedExistingCharacterId)} disabled={!selectedExistingCharacterId || Boolean(bindingLoadingKey)}>
                                        绑定所选角色
                                      </Button>
                                    </>
                                  )}
                                </div>
                              </div>
                            ))}
                          </div>
                        )}
                      </div>
                    )}

                    {/* 关联 */}
                    <div className="grid grid-cols-3 gap-4 text-sm">
                      <div className={`p-4 rounded-lg ${isDark ? 'bg-gray-800' : 'bg-gray-50'}`}>
                        <div className={`mb-1 ${isDark ? 'text-gray-400' : 'text-gray-500'}`}>关联角色</div>
                        <div className="font-medium">{selectedLore.related_characters.length}</div>
                      </div>
                      <div className={`p-4 rounded-lg ${isDark ? 'bg-gray-800' : 'bg-gray-50'}`}>
                        <div className={`mb-1 ${isDark ? 'text-gray-400' : 'text-gray-500'}`}>关联地点</div>
                        <div className="font-medium">{selectedLore.related_locations.length}</div>
                      </div>
                      <div className={`p-4 rounded-lg ${isDark ? 'bg-gray-800' : 'bg-gray-50'}`}>
                        <div className={`mb-1 ${isDark ? 'text-gray-400' : 'text-gray-500'}`}>关联物品</div>
                        <div className="font-medium">{selectedLore.related_items.length}</div>
                      </div>
                    </div>
                  </div>
                </Card>
              )}
            </div>
          </div>
        )}

        {/* 创建/编辑模态框 */}
        <Modal
          isOpen={showModal}
          onClose={() => setShowModal(false)}
          title={editingLore ? '编辑设定' : '新建设定'}
          size="lg"
        >
          <div className="space-y-4">
            <Input
              label="标题 *"
              value={formData.title}
              onChange={(e) => setFormData({ ...formData, title: e.target.value })}
              placeholder="设定标题"
            />

            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className={`block text-sm font-medium mb-1 ${isDark ? 'text-gray-300' : 'text-gray-700'}`}>类别</label>
                <select
                  className={`w-full px-3 py-2 border rounded-lg ${isDark ? 'bg-gray-800 border-gray-600 text-white' : 'border-gray-300'}`}
                  value={formData.category}
                  onChange={(e) => setFormData({ ...formData, category: e.target.value as LoreCategory })}
                >
                  {categories.map(cat => (
                    <option key={cat.value} value={cat.value}>{cat.label}</option>
                  ))}
                </select>
              </div>
              <div>
                <label className={`block text-sm font-medium mb-1 ${isDark ? 'text-gray-300' : 'text-gray-700'}`}>优先级</label>
                <select
                  className={`w-full px-3 py-2 border rounded-lg ${isDark ? 'bg-gray-800 border-gray-600 text-white' : 'border-gray-300'}`}
                  value={formData.priority}
                  onChange={(e) => setFormData({ ...formData, priority: e.target.value as LorePriority })}
                >
                  {priorities.map(pri => (
                    <option key={pri.value} value={pri.value}>{pri.label}</option>
                  ))}
                </select>
              </div>
            </div>

            <TextArea
              label="摘要"
              value={formData.summary || ''}
              onChange={(e) => setFormData({ ...formData, summary: e.target.value })}
              placeholder="简短描述这个设定..."
              rows={2}
            />

            <TextArea
              label="详细内容 *"
              value={formData.content}
              onChange={(e) => setFormData({ ...formData, content: e.target.value })}
              placeholder="详细描述设定内容，支持 Markdown 格式..."
              rows={8}
            />

            <Input
              label="关键词"
              value={keywordsInput}
              onChange={(e) => setKeywordsInput(e.target.value)}
              placeholder="用逗号分隔，如：修真，境界，功法"
            />

            <div className="flex justify-end gap-3 pt-4">
              <Button variant="secondary" onClick={() => setShowModal(false)}>取消</Button>
              <Button onClick={saveLore} disabled={!formData.title || !formData.content}>
                {editingLore ? '保存修改' : '创建'}
              </Button>
            </div>
          </div>
        </Modal>

        <Modal
          isOpen={Boolean(bindingRef)}
          onClose={() => setBindingRef(null)}
          title="创建角色并绑定引用"
          size="lg"
        >
          <div className="space-y-4">
            {bindingRef && (
              <div className={`rounded-lg px-3 py-2 text-sm ${isDark ? 'bg-amber-950/30 text-amber-100' : 'bg-amber-50 text-amber-800'}`}>
                将未解析引用 <span className="font-semibold">{bindingRef.source_text}</span> 创建为角色，并绑定到当前设定。
              </div>
            )}
            {referenceBindError && (
              <div className={`rounded-lg px-3 py-2 text-sm ${isDark ? 'bg-red-950/40 text-red-200' : 'bg-red-50 text-red-700'}`}>{referenceBindError}</div>
            )}
            <div className="grid grid-cols-2 gap-4">
              <Input
                label="角色名称 *"
                value={bindForm.name}
                onChange={(e) => setBindForm({ ...bindForm, name: e.target.value })}
                placeholder="角色名称"
              />
              <Input
                label="别名"
                value={bindAliasesInput}
                onChange={(e) => setBindAliasesInput(e.target.value)}
                placeholder="用逗号分隔"
              />
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className={`block text-sm font-medium mb-1 ${isDark ? 'text-gray-300' : 'text-gray-700'}`}>重要性层级</label>
                <select
                  className={`w-full px-3 py-2 border rounded-lg ${isDark ? 'bg-gray-800 border-gray-600 text-white' : 'border-gray-300'}`}
                  value={bindForm.importance_tier || CharacterImportanceTier.NPC}
                  onChange={(e) => setBindForm({ ...bindForm, importance_tier: e.target.value as CharacterImportanceTier })}
                >
                  {Object.values(CharacterImportanceTier).map(tier => (
                    <option key={tier} value={tier}>{TIER_DISPLAY_NAMES[tier]}</option>
                  ))}
                </select>
              </div>
              <Input
                label="性别"
                value={bindForm.gender || ''}
                onChange={(e) => setBindForm({ ...bindForm, gender: e.target.value })}
                placeholder="可选"
              />
            </div>
            <TextArea
              label="角色描述"
              value={bindForm.description || ''}
              onChange={(e) => setBindForm({ ...bindForm, description: e.target.value })}
              rows={3}
            />
            <TextArea
              label="外貌"
              value={bindForm.appearance || ''}
              onChange={(e) => setBindForm({ ...bindForm, appearance: e.target.value })}
              rows={2}
            />
            <TextArea
              label="性格 / 背景"
              value={bindForm.background_story || ''}
              onChange={(e) => setBindForm({ ...bindForm, background_story: e.target.value })}
              rows={3}
            />
            <Input
              label="说话风格"
              value={bindForm.speech_pattern || ''}
              onChange={(e) => setBindForm({ ...bindForm, speech_pattern: e.target.value })}
              placeholder="可选"
            />
            <div className="flex justify-end gap-3 pt-4">
              <Button variant="secondary" onClick={() => setBindingRef(null)}>取消</Button>
              <Button onClick={createAndBindReference} disabled={!bindForm.name?.trim() || bindingLoadingKey === `${bindingRef?.source_text}:create`}>
                {bindingLoadingKey === `${bindingRef?.source_text}:create` ? '创建中...' : '创建并绑定'}
              </Button>
            </div>
          </div>
        </Modal>

        {/* Setting Agent 聊天面板 */}
        {showAgentChat && currentProject && (
          <div className={`fixed right-0 top-0 h-full w-96 shadow-xl z-40 border-l ${isDark ? 'bg-gray-900 border-gray-700' : 'bg-white border-gray-200'}`}>
            <div className="h-full flex flex-col">
              <div className={`flex items-center justify-between p-4 border-b ${isDark ? 'border-gray-700' : 'border-gray-200'}`}>
                <h3 className={`font-medium ${isDark ? 'text-white' : 'text-gray-800'}`}>设定助手</h3>
                <button
                  onClick={() => setShowAgentChat(false)}
                  className={`${isDark ? 'text-gray-500 hover:text-gray-300' : 'text-gray-400 hover:text-gray-600'}`}
                >
                  ✕
                </button>
              </div>
              <div className="flex-1 overflow-hidden">
                <SettingAgentChat
                  projectId={currentProject.id}
                  onConflictResolved={loadLore}
                  onLoreChange={loadLore}
                />
              </div>
            </div>
          </div>
        )}
      </PageLayout>
    </div>
  )
}
