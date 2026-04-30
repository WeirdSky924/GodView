import { useState, useEffect, useCallback } from 'react'
import { Card, Button, Input, TextArea, Modal } from '@/components/ui'
import PageLayout from '@/components/PageLayout'
import {
  getCharacters,
  createCharacter,
  updateCharacter,
  deleteCharacter,
  getCharacterVoiceSamples,
  addCharacterVoiceSample,
  syncCharacterVoiceSamples,
  searchCharacterVoiceSamples,
  getCharacterAgentPrompt,
  batchEnableCharacterAgents,
  generateCharacterPersonality,
  CharacterImportanceTier,
  TIER_DISPLAY_NAMES,
  TIER_GROUPS,
} from '@/api/characters'
import type {
  Character,
  CreateCharacterDTO,
  UpdateCharacterDTO,
  CharacterVoiceSampleSearchResult,
  CharacterAgentPrompt,
} from '@/api/characters'
import { Plus, Edit, Trash2, User, Mic, Search, RefreshCw, FolderOpen, Bot, Target, Brain, Eye, Sparkles, Crown, Star, Users, Zap, MessageSquare, Heart, Shield, Sword, Ghost, Settings, FileText, ChevronRight, MapPin, GitBranch } from 'lucide-react'
import { useProject } from '@/contexts/ProjectContext'
import { useTheme } from '@/contexts/ThemeContext'
import { getRegions, type Region } from '@/api/worlds'
import { useProjectWorlds } from '@/hooks/useProjectWorlds'
import { motion, AnimatePresence } from 'framer-motion'
import CharacterRelationshipEditor from '@/components/characters/CharacterRelationshipEditor'

function splitCsvInput(value: string) {
  return value
    .split(/[，,\n]/)
    .map((item) => item.trim())
    .filter(Boolean)
}

function normalizeKeyRelationships(
  value: Record<string, string> | undefined,
  currentCharacterId?: string,
) {
  const result: Record<string, string> = {}
  Object.entries(value || {}).forEach(([targetId, relation]) => {
    const cleanTargetId = targetId.trim()
    const cleanRelation = relation.trim()
    if (!cleanTargetId || !cleanRelation || cleanTargetId === currentCharacterId) return
    result[cleanTargetId] = cleanRelation
  })
  return result
}

function resolveRelationshipTargetName(targetId: string, characters: Character[]) {
  return characters.find((character) => character.id === targetId || character.name === targetId)?.name || targetId
}

// 角色层级对应的图标和颜色
const TIER_ICONS: Record<string, { icon: React.ElementType; bgClass: string }> = {
  [CharacterImportanceTier.PROTAGONIST]: { icon: Crown, bgClass: 'from-yellow-400 to-amber-500' },
  [CharacterImportanceTier.CO_PROTAGONIST]: { icon: Star, bgClass: 'from-orange-400 to-yellow-500' },
  [CharacterImportanceTier.DEUTERAGONIST]: { icon: Star, bgClass: 'from-purple-400 to-purple-600' },
  [CharacterImportanceTier.MENTOR]: { icon: Shield, bgClass: 'from-blue-400 to-indigo-500' },
  [CharacterImportanceTier.LOVE_INTEREST]: { icon: Heart, bgClass: 'from-pink-400 to-rose-500' },
  [CharacterImportanceTier.BEST_FRIEND]: { icon: Users, bgClass: 'from-cyan-400 to-blue-500' },
  [CharacterImportanceTier.ARCHENEMY]: { icon: Sword, bgClass: 'from-red-500 to-red-700' },
  [CharacterImportanceTier.MAJOR_ALLY]: { icon: Shield, bgClass: 'from-green-400 to-emerald-500' },
  [CharacterImportanceTier.MAJOR_ANTAGONIST]: { icon: Sword, bgClass: 'from-red-400 to-orange-500' },
  [CharacterImportanceTier.RIVAL]: { icon: Zap, bgClass: 'from-yellow-500 to-orange-500' },
  [CharacterImportanceTier.FAMILY_MEMBER]: { icon: Heart, bgClass: 'from-pink-300 to-pink-500' },
  [CharacterImportanceTier.GUARDIAN]: { icon: Shield, bgClass: 'from-blue-400 to-cyan-500' },
  [CharacterImportanceTier.ARC_ANTAGONIST]: { icon: Sword, bgClass: 'from-red-400 to-red-600' },
  [CharacterImportanceTier.ARC_ALLY]: { icon: Users, bgClass: 'from-teal-400 to-green-500' },
  [CharacterImportanceTier.RECURRING]: { icon: Users, bgClass: 'from-gray-400 to-gray-600' },
  [CharacterImportanceTier.CATALYST]: { icon: Zap, bgClass: 'from-violet-400 to-purple-500' },
  [CharacterImportanceTier.MYSTERY_FIGURE]: { icon: Ghost, bgClass: 'from-indigo-400 to-violet-500' },
  [CharacterImportanceTier.MINION]: { icon: User, bgClass: 'from-gray-400 to-gray-500' },
  [CharacterImportanceTier.INFORMANT]: { icon: MessageSquare, bgClass: 'from-slate-400 to-slate-600' },
  [CharacterImportanceTier.COMIC_RELIEF]: { icon: MessageSquare, bgClass: 'from-amber-400 to-yellow-500' },
  [CharacterImportanceTier.VICTIM]: { icon: User, bgClass: 'from-gray-400 to-gray-500' },
  [CharacterImportanceTier.NPC]: { icon: User, bgClass: 'from-gray-400 to-gray-500' },
  [CharacterImportanceTier.BACKGROUND]: { icon: User, bgClass: 'from-gray-300 to-gray-400' },
  [CharacterImportanceTier.CAMEO]: { icon: User, bgClass: 'from-gray-300 to-gray-400' },
}

// 状态配置
const STATUS_CONFIG: Record<string, { label: string; bgClass: string; textClass: string }> = {
  active: { label: '活跃', bgClass: 'bg-green-500/20', textClass: 'text-green-400' },
  inactive: { label: '不活跃', bgClass: 'bg-gray-500/20', textClass: 'text-gray-400' },
  dead: { label: '已故', bgClass: 'bg-red-500/20', textClass: 'text-red-400' },
  ghost: { label: '幽灵', bgClass: 'bg-purple-500/20', textClass: 'text-purple-400' },
  resurrected: { label: '复活', bgClass: 'bg-yellow-500/20', textClass: 'text-yellow-400' },
  paused: { label: '暂停', bgClass: 'bg-orange-500/20', textClass: 'text-orange-400' },
}

export default function Characters() {
  const { currentProject } = useProject()
  const { theme } = useTheme()
  const isDark = theme === 'dark'

  const [characters, setCharacters] = useState<Character[]>([])
  const [showModal, setShowModal] = useState(false)
  const [editingChar, setEditingChar] = useState<Character | null>(null)
  const [loading, setLoading] = useState(true)
  const [selectedCharacterId, setSelectedCharacterId] = useState<string>('')
  const [voiceSamples, setVoiceSamples] = useState<CharacterVoiceSampleSearchResult[]>([])
  const [voiceSearchResults, setVoiceSearchResults] = useState<CharacterVoiceSampleSearchResult[]>([])
  const [voiceLoading, setVoiceLoading] = useState(false)
  const [voiceSearchLoading, setVoiceSearchLoading] = useState(false)
  const [syncingVoice, setSyncingVoice] = useState(false)
  const [voiceForm, setVoiceForm] = useState({ text: '', context: '', query: '' })
  const [showAgentPromptModal, setShowAgentPromptModal] = useState(false)
  const [agentPromptData, setAgentPromptData] = useState<CharacterAgentPrompt | null>(null)
  const [agentPromptLoading, setAgentPromptLoading] = useState(false)
  const [batchEnabling, setBatchEnabling] = useState(false)
  const [generatingPersonality, setGeneratingPersonality] = useState(false)
  const [regions, setRegions] = useState<Region[]>([])
  const { worlds, formatWorldLabel } = useProjectWorlds(currentProject?.id, currentProject?.world_id)

  // 编辑窗口的标签页
  const [activeTab, setActiveTab] = useState<'basic' | 'relationships' | 'location' | 'appearance' | 'voice' | 'agent'>('basic')

  const [formData, setFormData] = useState<CreateCharacterDTO>({
    name: '',
    status: 'active',
    description: '',
    world_id: '',
    current_location: '',
    current_region_id: '',
    current_location_reason: '',
    importance_tier: CharacterImportanceTier.NPC,
    narrative_weight: undefined,
    story_arc_role: undefined,
    personality: '',
    appearance: '',
    background_story: '',
    gender: '',
    speech_pattern: '',
    lexicon: [],
    forbidden_words: [],
    voice_samples: [],
    has_agent: false,
    agent_enabled: true,
    agent_goals: [],
    agent_memory: [],
    relationships: [],
    key_relationships: {},
  })
  const [lexiconInput, setLexiconInput] = useState('')
  const [forbiddenWordsInput, setForbiddenWordsInput] = useState('')
  const [voiceSamplesInput, setVoiceSamplesInput] = useState('')
  const [agentGoalsInput, setAgentGoalsInput] = useState('')
  const [agentMemoryInput, setAgentMemoryInput] = useState('')

  const loadCharacters = useCallback(async () => {
    setLoading(true)
    try {
      const data = await getCharacters(currentProject?.id)
      setCharacters(data)
      setSelectedCharacterId((current) => current || data[0]?.id || '')
    } catch (error) {
      console.error('Failed to load characters:', error)
    } finally {
      setLoading(false)
    }
  }, [currentProject?.id])

  const loadRegions = useCallback(async (worldId?: string) => {
    if (!worldId) {
      setRegions([])
      return
    }

    try {
      const data = await getRegions(worldId)
      setRegions(data)
    } catch (error) {
      console.error('Failed to load regions:', error)
      setRegions([])
    }
  }, [])

  const loadVoiceSamples = useCallback(async (characterId: string) => {
    if (!characterId) {
      setVoiceSamples([])
      return
    }

    setVoiceLoading(true)
    try {
      const data = await getCharacterVoiceSamples(characterId, 10, currentProject?.id)
      setVoiceSamples(data)
    } catch (error) {
      console.error('Failed to load voice samples:', error)
      setVoiceSamples([])
    } finally {
      setVoiceLoading(false)
    }
  }, [currentProject?.id])

  useEffect(() => {
    loadCharacters()
  }, [loadCharacters])

  useEffect(() => {
    loadRegions(formData.world_id)
  }, [formData.world_id, loadRegions])

  useEffect(() => {
    if (selectedCharacterId) {
      loadVoiceSamples(selectedCharacterId)
      setVoiceSearchResults([])
    }
  }, [selectedCharacterId, loadVoiceSamples])

  const openCreateModal = () => {
    setEditingChar(null)
    setFormData({
      name: '',
      status: 'active',
      description: '',
      world_id: '',
      current_location: '',
      current_region_id: '',
      current_location_reason: '',
      importance_tier: CharacterImportanceTier.NPC,
      personality: '',
      appearance: '',
      background_story: '',
      gender: '',
      speech_pattern: '',
      lexicon: [],
      forbidden_words: [],
      voice_samples: [],
      has_agent: false,
      agent_enabled: true,
      agent_goals: [],
      agent_memory: [],
      relationships: [],
      key_relationships: {},
    })
    setLexiconInput('')
    setForbiddenWordsInput('')
    setVoiceSamplesInput('')
    setAgentGoalsInput('')
    setAgentMemoryInput('')
    setActiveTab('basic')
    setShowModal(true)
  }

  const openEditModal = (character: Character) => {
    setEditingChar(character)
    setFormData({
      name: character.name,
      status: character.status,
      description: character.description,
      world_id: character.world_id || '',
      current_location: character.current_location || '',
      current_region_id: character.current_region_id || '',
      current_location_reason: character.current_location_reason || '',
      importance_tier: character.importance_tier || CharacterImportanceTier.NPC,
      narrative_weight: character.narrative_weight,
      story_arc_role: character.story_arc_role,
      personality: character.personality,
      appearance: character.appearance,
      background_story: character.background_story,
      gender: character.gender,
      speech_pattern: character.speech_pattern,
      lexicon: character.lexicon || [],
      forbidden_words: character.forbidden_words || [],
      voice_samples: character.voice_samples || [],
      has_agent: character.has_agent || false,
      agent_enabled: character.agent_enabled ?? true,
      agent_goals: character.agent_goals || [],
      agent_memory: character.agent_memory || [],
      relationships: character.relationships || [],
      key_relationships: character.key_relationships || {},
    })
    setLexiconInput((character.lexicon || []).join('，'))
    setForbiddenWordsInput((character.forbidden_words || []).join('，'))
    setVoiceSamplesInput((character.voice_samples || []).join('\n'))
    setAgentGoalsInput((character.agent_goals || []).join('\n'))
    setAgentMemoryInput((character.agent_memory || []).join('\n'))
    setActiveTab('basic')
    setShowModal(true)
  }

  const saveCharacter = async () => {
    try {
      const selectedRegion = regions.find(region => region.id === formData.current_region_id)
      const normalizedData: CreateCharacterDTO = {
        ...formData,
        world_id: formData.world_id || undefined,
        current_region_id: formData.current_region_id || undefined,
        current_location: (formData.current_location || selectedRegion?.name || '').trim(),
        current_location_reason: formData.current_location_reason?.trim() || '',
        lexicon: splitCsvInput(lexiconInput),
        forbidden_words: splitCsvInput(forbiddenWordsInput),
        voice_samples: splitCsvInput(voiceSamplesInput),
        agent_goals: splitCsvInput(agentGoalsInput),
        agent_memory: splitCsvInput(agentMemoryInput),
        relationships: formData.relationships || [],
        key_relationships: normalizeKeyRelationships(formData.key_relationships, editingChar?.id),
      }

      if (editingChar?.id) {
        const updateData: UpdateCharacterDTO = {
          id: editingChar.id,
          ...normalizedData,
          project_id: editingChar.project_id || currentProject?.id,
        }
        await updateCharacter(editingChar.id, updateData)
      } else {
        await createCharacter({
          ...normalizedData,
          project_id: currentProject?.id,
        })
      }
      await loadCharacters()
      setShowModal(false)
    } catch (error) {
      console.error('Failed to save character:', error)
      alert('保存失败，请重试')
    }
  }

  const handleDelete = async (id: string | undefined) => {
    if (!id || !confirm('确定要删除这个角色吗？')) return
    try {
      await deleteCharacter(id)
      await loadCharacters()
      if (selectedCharacterId === id) {
        setSelectedCharacterId('')
        setVoiceSamples([])
        setVoiceSearchResults([])
      }
    } catch (error) {
      console.error('Failed to delete character:', error)
    }
  }

  const handleAddVoiceSample = async () => {
    if (!selectedCharacterId || !voiceForm.text.trim()) return

    try {
      await addCharacterVoiceSample(selectedCharacterId, {
        id: crypto.randomUUID(),
        character_id: selectedCharacterId,
        text: voiceForm.text.trim(),
        context: voiceForm.context.trim(),
      })
      setVoiceForm((prev) => ({ ...prev, text: '', context: '' }))
      await loadVoiceSamples(selectedCharacterId)
      await loadCharacters()
    } catch (error) {
      console.error('Failed to add voice sample:', error)
      alert('声音样本添加失败')
    }
  }

  const handleSyncVoiceSamples = async () => {
    if (!selectedCharacterId) return

    setSyncingVoice(true)
    try {
      await syncCharacterVoiceSamples(selectedCharacterId)
      await loadVoiceSamples(selectedCharacterId)
    } catch (error) {
      console.error('Failed to sync voice samples:', error)
      alert('声音样本同步失败')
    } finally {
      setSyncingVoice(false)
    }
  }

  const handleSearchVoiceSamples = async () => {
    if (!selectedCharacterId || !voiceForm.query.trim()) return

    setVoiceSearchLoading(true)
    try {
      const results = await searchCharacterVoiceSamples(
        selectedCharacterId,
        voiceForm.query.trim(),
        5,
        currentProject?.id
      )
      setVoiceSearchResults(results)
    } catch (error) {
      console.error('Failed to search voice samples:', error)
      alert('声音样本检索失败')
    } finally {
      setVoiceSearchLoading(false)
    }
  }

  const handlePreviewAgentPrompt = async () => {
    if (!selectedCharacterId) return

    setAgentPromptLoading(true)
    setShowAgentPromptModal(true)
    try {
      const data = await getCharacterAgentPrompt(selectedCharacterId)
      setAgentPromptData(data)
    } catch (error) {
      console.error('Failed to get agent prompt:', error)
      setAgentPromptData({ has_agent: false, message: '获取 Agent Prompt 失败' })
    } finally {
      setAgentPromptLoading(false)
    }
  }

  const handleBatchEnableAgents = async () => {
    if (!currentProject?.id) return
    if (!confirm('确定要为项目中所有主要角色启用 Agent 吗？\n这将自动配置角色的目标和记忆。')) return

    setBatchEnabling(true)
    try {
      const result = await batchEnableCharacterAgents(currentProject.id)
      alert(`批量启用完成！\n更新: ${result.updated_count} 个角色\n跳过: ${result.skipped_count} 个角色\n错误: ${result.error_count} 个`)
      await loadCharacters()
    } catch (error) {
      console.error('Failed to batch enable agents:', error)
      alert('批量启用失败')
    } finally {
      setBatchEnabling(false)
    }
  }

  // 在编辑窗口中生成外貌和性格
  const handleGenerateAppearanceAndPersonality = async () => {
    if (!formData.name) {
      alert('请先填写角色名称')
      return
    }

    setGeneratingPersonality(true)
    try {
      // 如果是编辑现有角色，直接调用 API
      if (editingChar?.id) {
        const result = await generateCharacterPersonality(editingChar.id)
        if (result.success) {
          // 更新表单数据
          if (result.appearance) setFormData(prev => ({ ...prev, appearance: result.appearance }))
          if (result.personality) setFormData(prev => ({ ...prev, personality: result.personality }))
          if (result.speech_pattern) setFormData(prev => ({ ...prev, speech_pattern: result.speech_pattern }))
          if (result.agent_goals) setAgentGoalsInput(result.agent_goals.join('\n'))
          if (result.agent_memory) setAgentMemoryInput(result.agent_memory.join('\n'))
          // 自动启用 Agent
          setFormData(prev => ({ ...prev, has_agent: true, agent_enabled: true }))
        } else {
          alert('生成失败：' + (result.message || '未知错误'))
        }
      } else {
        // 新建角色时，需要先保存再生成
        alert('请先保存角色后再生成外貌和性格')
      }
    } catch (error) {
      console.error('Failed to generate personality:', error)
      alert('生成失败')
    } finally {
      setGeneratingPersonality(false)
    }
  }

  // 在声音样本面板中生成性格（针对已选中的角色）
  const handleGeneratePersonalityForSelected = async () => {
    if (!selectedCharacterId) return
    if (!confirm('确定要调用 Setting Agent 为该角色生成外貌和性格设定吗？')) return

    setGeneratingPersonality(true)
    try {
      const result = await generateCharacterPersonality(selectedCharacterId)
      if (result.success) {
        alert(`生成成功！\n\n外貌：${result.appearance || '无'}\n性格：${result.personality}\n说话风格：${result.speech_pattern}`)
        await loadCharacters()
      } else {
        alert('生成失败：' + (result.message || '未知错误'))
      }
    } catch (error) {
      console.error('Failed to generate personality:', error)
      alert('生成失败')
    } finally {
      setGeneratingPersonality(false)
    }
  }

  const selectedCharacter = characters.find((char) => char.id === selectedCharacterId)

  // 获取角色的图标和颜色配置
  const getTierConfig = (tier?: string) => {
    if (!tier) return { icon: User, bgClass: 'from-gray-400 to-gray-500' }
    return TIER_ICONS[tier] || { icon: User, bgClass: 'from-gray-400 to-gray-500' }
  }

  return (
    <PageLayout
      title="角色管理"
      description="管理小说中的角色信息和声音样本"
      actions={
        <div className="flex gap-2">
          <Button variant="secondary" onClick={handleBatchEnableAgents} disabled={!currentProject || batchEnabling}>
            <Bot size={18} className="mr-2" />
            {batchEnabling ? '启用中...' : '批量启用 Agent'}
          </Button>
          <Button onClick={openCreateModal} disabled={!currentProject}>
            <Plus size={18} className="mr-2" />
            新增角色
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
        <p className={`text-center py-12 ${isDark ? 'text-gray-400' : 'text-gray-500'}`}>加载中...</p>
      ) : (
        <div className="grid grid-cols-1 xl:grid-cols-[2fr,1fr] gap-6">
          {/* 角色卡片网格 */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {characters.length === 0 ? (
              <div className={`col-span-full text-center py-12 ${isDark ? 'text-gray-400' : 'text-gray-500'}`}>
                暂无角色，点击"新增角色"开始创建
              </div>
            ) : (
              characters.map((char) => {
                const tierConfig = getTierConfig(char.importance_tier)
                const statusConfig = STATUS_CONFIG[char.status] || STATUS_CONFIG.inactive
                const IconComponent = tierConfig.icon

                return (
                  <motion.div
                    key={char.id}
                    initial={{ opacity: 0, y: 10 }}
                    animate={{ opacity: 1, y: 0 }}
                    whileHover={{ scale: 1.02 }}
                    className={`relative overflow-hidden rounded-xl cursor-pointer transition-all ${
                      selectedCharacterId === char.id
                        ? 'ring-2 ring-blue-500 ring-offset-2 ring-offset-transparent'
                        : ''
                    }`}
                    onClick={() => setSelectedCharacterId(char.id || '')}
                  >
                    {/* 卡片背景渐变 */}
                    <div className={`absolute inset-0 bg-gradient-to-br ${tierConfig.bgClass} opacity-5`} />

                    <Card className={`relative h-full ${
                      isDark ? 'bg-gray-800/80 hover:bg-gray-800' : 'bg-white hover:bg-gray-50'
                    }`}>
                      <div className="p-4 flex flex-col h-full">
                        {/* 头部：头像 + 名称 + 状态 */}
                        <div className="flex items-center gap-3 mb-3">
                          <div className={`w-14 h-14 rounded-xl bg-gradient-to-br ${tierConfig.bgClass} flex items-center justify-center text-white shadow-lg flex-shrink-0`}>
                            <IconComponent size={26} />
                          </div>
                          <div className="flex-1 min-w-0">
                            <h3 className={`text-lg font-semibold truncate ${isDark ? 'text-white' : 'text-gray-900'}`}>
                              {char.name}
                            </h3>
                            <div className="flex items-center gap-2 mt-1 flex-wrap">
                              <span className={`px-2 py-0.5 text-xs font-medium rounded ${
                                char.importance_tier === CharacterImportanceTier.PROTAGONIST ? 'bg-yellow-500 text-white' :
                                char.importance_tier === CharacterImportanceTier.CO_PROTAGONIST ? 'bg-orange-500 text-white' :
                                [CharacterImportanceTier.DEUTERAGONIST, CharacterImportanceTier.MENTOR, CharacterImportanceTier.LOVE_INTEREST, CharacterImportanceTier.BEST_FRIEND, CharacterImportanceTier.ARCHENEMY].includes(char.importance_tier as any) ?
                                  (isDark ? 'bg-purple-900/80 text-purple-300' : 'bg-purple-100 text-purple-700') :
                                (isDark ? 'bg-gray-700 text-gray-300' : 'bg-gray-200 text-gray-600')
                              }`}>
                                {TIER_DISPLAY_NAMES[char.importance_tier as CharacterImportanceTier] || 'NPC'}
                              </span>
                              <span className={`px-2 py-0.5 text-xs font-medium rounded-full ${statusConfig.bgClass} ${statusConfig.textClass}`}>
                                {statusConfig.label}
                              </span>
                              {char.has_agent && (
                                <span className={`flex items-center gap-1 px-2 py-0.5 text-xs font-medium rounded ${isDark ? 'bg-purple-900/60 text-purple-300' : 'bg-purple-100 text-purple-700'}`}>
                                  <Bot size={12} />
                                  Agent
                                </span>
                              )}
                            </div>
                          </div>
                        </div>

                        {/* 详细信息区域 */}
                        <div className="flex-1 space-y-2 mb-3">
                          {/* 简介 */}
                          {char.description && (
                            <div>
                              <span className={`text-xs font-medium ${isDark ? 'text-gray-500' : 'text-gray-400'}`}>简介：</span>
                              <p className={`text-sm line-clamp-2 ${isDark ? 'text-gray-300' : 'text-gray-600'}`}>
                                {char.description}
                              </p>
                            </div>
                          )}

                          {/* 外貌 */}
                          {char.appearance && (
                            <div>
                              <span className={`text-xs font-medium ${isDark ? 'text-gray-500' : 'text-gray-400'}`}>外貌：</span>
                              <p className={`text-sm line-clamp-2 ${isDark ? 'text-gray-300' : 'text-gray-600'}`}>
                                {char.appearance}
                              </p>
                            </div>
                          )}

                          {/* 性格 */}
                          {char.personality && (
                            <div>
                              <span className={`text-xs font-medium ${isDark ? 'text-gray-500' : 'text-gray-400'}`}>性格：</span>
                              <p className={`text-sm line-clamp-2 ${isDark ? 'text-gray-300' : 'text-gray-600'}`}>
                                {char.personality}
                              </p>
                            </div>
                          )}

                          {/* 当前位置 */}
                          {(char.current_location || char.current_location_reason) && (
                            <div>
                              <span className={`text-xs font-medium ${isDark ? 'text-gray-500' : 'text-gray-400'}`}>位置：</span>
                              <p className={`text-sm line-clamp-2 ${isDark ? 'text-gray-300' : 'text-gray-600'}`}>
                                {char.current_location || '未命名地点'}{char.current_location_reason ? ` · ${char.current_location_reason}` : ''}
                              </p>
                            </div>
                          )}

                          {/* 如果没有详细信息 */}
                          {!char.description && !char.appearance && !char.personality && !char.current_location && !char.current_location_reason && (
                            <p className={`text-sm italic ${isDark ? 'text-gray-500' : 'text-gray-400'}`}>
                              暂无详细设定
                            </p>
                          )}
                        </div>

                        {/* 底部操作按钮 */}
                        <div className={`flex items-center justify-between pt-3 border-t ${isDark ? 'border-gray-700' : 'border-gray-100'}`}>
                          <div className="flex items-center gap-2 text-xs">
                            {char.gender && (
                              <span className={`px-2 py-1 rounded ${isDark ? 'bg-gray-700 text-gray-400' : 'bg-gray-100 text-gray-500'}`}>
                                {char.gender === 'male' ? '♂ 男' : char.gender === 'female' ? '♀ 女' : '⚧ 其他'}
                              </span>
                            )}
                            {char.speech_pattern && (
                              <span className={`px-2 py-1 rounded ${isDark ? 'bg-gray-700 text-gray-400' : 'bg-gray-100 text-gray-500'}`}>
                                已设风格
                              </span>
                            )}
                            {Object.keys(char.key_relationships || {}).length > 0 && (
                              <span className={`px-2 py-1 rounded ${isDark ? 'bg-blue-900/50 text-blue-300' : 'bg-blue-50 text-blue-600'}`}>
                                {Object.keys(char.key_relationships || {}).length} 个关系
                              </span>
                            )}
                          </div>
                          <div className="flex items-center gap-2">
                            <button
                              onClick={(e) => { e.stopPropagation(); openEditModal(char); }}
                              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm font-medium transition-colors ${
                                isDark
                                  ? 'bg-gray-700 hover:bg-blue-600 text-gray-300 hover:text-white'
                                  : 'bg-gray-100 hover:bg-blue-500 text-gray-600 hover:text-white'
                              }`}
                            >
                              <Edit size={16} />
                              编辑
                            </button>
                            <button
                              onClick={(e) => { e.stopPropagation(); handleDelete(char.id); }}
                              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm font-medium transition-colors ${
                                isDark
                                  ? 'bg-gray-700 hover:bg-red-600 text-gray-300 hover:text-white'
                                  : 'bg-gray-100 hover:bg-red-500 text-gray-600 hover:text-white'
                              }`}
                            >
                              <Trash2 size={16} />
                              删除
                            </button>
                          </div>
                        </div>
                      </div>
                    </Card>
                  </motion.div>
                )
              })
            )}
          </div>

          {/* 右侧声音样本面板 */}
          <Card noPadding className="flex h-[calc(100vh-9rem)] min-h-[620px] flex-col overflow-hidden xl:sticky xl:top-4">
            <div className={`shrink-0 p-6 pb-4 ${isDark ? 'bg-gray-800' : 'bg-white'}`}>
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <Mic size={18} className={isDark ? 'text-gray-400' : 'text-gray-500'} />
                  <h2 className={`text-lg font-semibold ${isDark ? 'text-white' : 'text-gray-800'}`}>声音样本</h2>
                </div>
                <Button
                  variant="secondary"
                  size="sm"
                  onClick={handleSyncVoiceSamples}
                  disabled={!selectedCharacterId || syncingVoice}
                >
                  <RefreshCw size={14} className="mr-1" />
                  {syncingVoice ? '同步中' : '同步向量'}
                </Button>
              </div>
            </div>

            <div className="min-h-0 flex-1 overflow-y-auto px-6 pb-6 pr-5">
            {!selectedCharacter ? (
              <p className={`text-sm ${isDark ? 'text-gray-400' : 'text-gray-500'}`}>请选择左侧角色后查看和管理声音样本。</p>
            ) : (
              <div className="space-y-4">
                <div className={`rounded-lg p-3 text-sm ${isDark ? 'bg-gray-800 text-gray-300' : 'bg-gray-50 text-gray-700'}`}>
                  <div className="flex items-center justify-between">
                    <div><span className="font-medium">当前角色：</span>{selectedCharacter.name}</div>
                    {selectedCharacter.importance_tier && (
                      <span className={`px-2 py-0.5 text-xs rounded ${
                        selectedCharacter.importance_tier === CharacterImportanceTier.PROTAGONIST ? 'bg-yellow-500 text-white' :
                        selectedCharacter.importance_tier === CharacterImportanceTier.CO_PROTAGONIST ? 'bg-yellow-600 text-white' :
                        [CharacterImportanceTier.DEUTERAGONIST, CharacterImportanceTier.MENTOR, CharacterImportanceTier.LOVE_INTEREST, CharacterImportanceTier.BEST_FRIEND, CharacterImportanceTier.ARCHENEMY].includes(selectedCharacter.importance_tier as any) ?
                          (isDark ? 'bg-purple-900 text-purple-300' : 'bg-purple-100 text-purple-700') :
                        'bg-gray-500 text-white'
                      }`}>
                        {TIER_DISPLAY_NAMES[selectedCharacter.importance_tier as CharacterImportanceTier] || selectedCharacter.importance_tier}
                      </span>
                    )}
                  </div>
                  <div className="mt-1"><span className="font-medium">说话风格：</span>{selectedCharacter.speech_pattern || '未设置'}</div>
                  <div className="mt-1"><span className="font-medium">当前位置：</span>{selectedCharacter.current_location || '未设置'}</div>
                  <div className="mt-1"><span className="font-medium">到达原因：</span>{selectedCharacter.current_location_reason || '未填写原因'}</div>
                  <div className="mt-3">
                    <div className="mb-1 flex items-center gap-1.5 font-medium">
                      <GitBranch size={14} />关键关系
                    </div>
                    {Object.entries(selectedCharacter.key_relationships || {}).length === 0 ? (
                      <div className={isDark ? 'text-gray-500' : 'text-gray-400'}>暂无关键关系</div>
                    ) : (
                      <div className="space-y-1">
                        {Object.entries(selectedCharacter.key_relationships || {}).slice(0, 3).map(([targetId, relation]) => (
                          <div key={targetId} className={`rounded px-2 py-1 text-xs ${isDark ? 'bg-gray-900/70 text-gray-300' : 'bg-white text-gray-600'}`}>
                            {resolveRelationshipTargetName(targetId, characters)}：{relation}
                          </div>
                        ))}
                        {Object.keys(selectedCharacter.key_relationships || {}).length > 3 && (
                          <div className={isDark ? 'text-gray-500' : 'text-gray-400'}>... 共 {Object.keys(selectedCharacter.key_relationships || {}).length} 条</div>
                        )}
                      </div>
                    )}
                  </div>
                  {selectedCharacter.has_agent && (
                    <div className="mt-2 flex items-center gap-2">
                      <span className={`inline-flex items-center px-2 py-0.5 text-xs rounded ${isDark ? 'bg-purple-900 text-purple-300' : 'bg-purple-100 text-purple-700'}`}>
                        <Bot size={12} className="mr-1" />Agent {(selectedCharacter.agent_enabled ?? true) ? '已激活' : '未激活'}
                      </span>
                    </div>
                  )}
                  <div className="mt-3 flex gap-2">
                    <Button
                      size="sm"
                      variant="secondary"
                      onClick={handleGeneratePersonalityForSelected}
                      disabled={generatingPersonality}
                    >
                      <Sparkles size={14} className="mr-1" />
                      {generatingPersonality ? '生成中...' : 'AI 生成外貌性格'}
                    </Button>
                  </div>
                </div>

                {selectedCharacter.has_agent && (
                  <div className={`rounded-lg p-3 text-sm ${isDark ? 'bg-purple-900/20 border border-purple-700/30' : 'bg-purple-50 border border-purple-200'}`}>
                    <div className="flex items-center justify-between mb-2">
                      <div className="flex items-center gap-2">
                        <Bot size={16} className={isDark ? 'text-purple-400' : 'text-purple-600'} />
                        <span className={`font-medium ${isDark ? 'text-purple-300' : 'text-purple-700'}`}>Agent 配置</span>
                      </div>
                      <Button size="sm" variant="secondary" onClick={handlePreviewAgentPrompt}>
                        <Eye size={14} className="mr-1" /> 预览 Prompt
                      </Button>
                    </div>
                    {selectedCharacter.agent_goals && selectedCharacter.agent_goals.length > 0 && (
                      <div className="mb-2">
                        <span className={`text-xs ${isDark ? 'text-gray-400' : 'text-gray-500'}`}>目标：</span>
                        <ul className={`text-xs mt-1 ${isDark ? 'text-gray-300' : 'text-gray-600'}`}>
                          {selectedCharacter.agent_goals.map((goal, i) => (
                            <li key={i}>• {goal}</li>
                          ))}
                        </ul>
                      </div>
                    )}
                    {selectedCharacter.agent_memory && selectedCharacter.agent_memory.length > 0 && (
                      <div>
                        <span className={`text-xs ${isDark ? 'text-gray-400' : 'text-gray-500'}`}>记忆：</span>
                        <ul className={`text-xs mt-1 ${isDark ? 'text-gray-300' : 'text-gray-600'}`}>
                          {selectedCharacter.agent_memory.slice(0, 3).map((mem, i) => (
                            <li key={i}>• {mem}</li>
                          ))}
                          {selectedCharacter.agent_memory.length > 3 && (
                            <li className={isDark ? 'text-gray-500' : 'text-gray-400'}>... 共 {selectedCharacter.agent_memory.length} 条</li>
                          )}
                        </ul>
                      </div>
                    )}
                  </div>
                )}

                <TextArea
                  label="新增台词样本"
                  value={voiceForm.text}
                  onChange={(e) => setVoiceForm((prev) => ({ ...prev, text: e.target.value }))}
                  placeholder="输入能代表该角色语言风格的典型台词"
                />
                <Input
                  label="样本上下文"
                  value={voiceForm.context}
                  onChange={(e) => setVoiceForm((prev) => ({ ...prev, context: e.target.value }))}
                  placeholder="如：争吵场景、初次见面、自言自语"
                />
                <Button onClick={handleAddVoiceSample} disabled={!voiceForm.text.trim()}>
                  添加声音样本
                </Button>

                <div className={`pt-4 ${isDark ? 'border-gray-700' : 'border-gray-200'} border-t`}>
                  <div className="flex gap-2">
                    <Input
                      label="语义检索"
                      value={voiceForm.query}
                      onChange={(e) => setVoiceForm((prev) => ({ ...prev, query: e.target.value }))}
                      placeholder="输入一句待对比台词"
                    />
                    <div className="flex items-end">
                      <Button onClick={handleSearchVoiceSamples} disabled={!voiceForm.query.trim() || voiceSearchLoading}>
                        <Search size={14} className="mr-1" />
                        {voiceSearchLoading ? '检索中' : '检索'}
                      </Button>
                    </div>
                  </div>
                </div>

                <div>
                  <h3 className={`text-sm font-medium mb-2 ${isDark ? 'text-gray-300' : 'text-gray-700'}`}>已存样本</h3>
                  {voiceLoading ? (
                    <p className={`text-sm ${isDark ? 'text-gray-400' : 'text-gray-500'}`}>加载中...</p>
                  ) : voiceSamples.length === 0 ? (
                    <p className={`text-sm ${isDark ? 'text-gray-400' : 'text-gray-500'}`}>暂无声音样本</p>
                  ) : (
                    <div className="space-y-2 max-h-64 overflow-auto">
                      {voiceSamples.map((sample) => (
                        <div key={sample.id} className={`rounded border p-3 text-sm ${isDark ? 'border-gray-700' : 'border-gray-200'}`}>
                          <div className={isDark ? 'text-gray-200' : 'text-gray-800'}>{sample.payload.text}</div>
                          {sample.payload.context ? (
                            <div className={`mt-1 text-xs ${isDark ? 'text-gray-500' : 'text-gray-400'}`}>上下文：{sample.payload.context}</div>
                          ) : null}
                        </div>
                      ))}
                    </div>
                  )}
                </div>

                <div>
                  <h3 className={`text-sm font-medium mb-2 ${isDark ? 'text-gray-300' : 'text-gray-700'}`}>检索结果</h3>
                  {voiceSearchResults.length === 0 ? (
                    <p className={`text-sm ${isDark ? 'text-gray-400' : 'text-gray-500'}`}>暂无检索结果</p>
                  ) : (
                    <div className="space-y-2 max-h-56 overflow-auto">
                      {voiceSearchResults.map((sample) => (
                        <div key={sample.id} className="rounded border border-blue-500/30 bg-blue-900/20 p-3 text-sm">
                          <div className="flex items-center justify-between gap-3">
                            <span className={isDark ? 'text-gray-200' : 'text-gray-800'}>{sample.payload.text}</span>
                            <span className="text-xs text-blue-400">相似度 {sample.score.toFixed(3)}</span>
                          </div>
                          {sample.payload.context ? (
                            <div className={`mt-1 text-xs ${isDark ? 'text-gray-500' : 'text-gray-400'}`}>上下文：{sample.payload.context}</div>
                          ) : null}
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            )}
            </div>
          </Card>
        </div>
      )}

      {/* 编辑角色 Modal - 重新设计的标签页布局 */}
      <Modal
        isOpen={showModal}
        onClose={() => setShowModal(false)}
        title={editingChar ? '编辑角色' : '新建角色'}
        size="xl"
      >
        <div className="space-y-4">
          {/* 标签页导航 */}
          <div className={`flex border-b ${isDark ? 'border-gray-700' : 'border-gray-200'}`}>
            {[
              { key: 'basic', label: '基础信息', icon: User },
              { key: 'relationships', label: '关系网络', icon: GitBranch },
              { key: 'location', label: '位置地图', icon: MapPin },
              { key: 'appearance', label: '外观性格', icon: Heart },
              { key: 'voice', label: '语言风格', icon: MessageSquare },
              { key: 'agent', label: 'Agent 配置', icon: Bot },
            ].map((tab) => (
              <button
                key={tab.key}
                onClick={() => setActiveTab(tab.key as typeof activeTab)}
                className={`flex items-center gap-1.5 px-4 py-2.5 text-sm font-medium border-b-2 transition-colors ${
                  activeTab === tab.key
                    ? `border-blue-500 ${isDark ? 'text-blue-400' : 'text-blue-600'}`
                    : `border-transparent ${isDark ? 'text-gray-400 hover:text-gray-300' : 'text-gray-500 hover:text-gray-700'}`
                }`}
              >
                <tab.icon size={14} />
                {tab.label}
              </button>
            ))}
          </div>

          {/* 标签页内容 */}
          <div className="max-h-[60vh] overflow-y-auto pr-2">
            {/* 基础信息 Tab */}
            {activeTab === 'basic' && (
              <div className="space-y-4">
                <div className="grid grid-cols-2 gap-4">
                  <Input
                    label="角色名称 *"
                    value={formData.name}
                    onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                    placeholder="输入角色名称"
                  />
                  <div>
                    <label className={`block text-sm font-medium mb-1 ${isDark ? 'text-gray-300' : 'text-gray-700'}`}>
                      性别
                    </label>
                    <select
                      className={`w-full px-3 py-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 ${isDark ? 'bg-gray-800 border-gray-600 text-white' : 'bg-white border-gray-300 text-gray-800'}`}
                      value={formData.gender || ''}
                      onChange={(e) => setFormData({ ...formData, gender: e.target.value })}
                    >
                      <option value="">未知</option>
                      <option value="male">男</option>
                      <option value="female">女</option>
                      <option value="other">其他</option>
                    </select>
                  </div>
                </div>

                {/* 角色重要性层级 */}
                <div>
                  <label className={`block text-sm font-medium mb-1 ${isDark ? 'text-gray-300' : 'text-gray-700'}`}>
                    <Crown size={14} className="inline mr-1" /> 角色重要性层级
                  </label>
                  <select
                    className={`w-full px-3 py-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 text-sm ${isDark ? 'bg-gray-800 border-gray-600 text-white' : 'bg-white border-gray-300 text-gray-800'}`}
                    value={formData.importance_tier || CharacterImportanceTier.NPC}
                    onChange={(e) => setFormData({ ...formData, importance_tier: e.target.value as CharacterImportanceTier })}
                  >
                    <optgroup label="主角层 (Tier 1) - 故事核心">
                      <option value={CharacterImportanceTier.PROTAGONIST}>主角 - 故事核心，所有剧情围绕其展开</option>
                      <option value={CharacterImportanceTier.CO_PROTAGONIST}>共同主角 - 与主角同等重要</option>
                    </optgroup>
                    <optgroup label="核心配角层 (Tier 2) - 贯穿全文">
                      <option value={CharacterImportanceTier.DEUTERAGONIST}>第二主角 - 重要性仅次于主角</option>
                      <option value={CharacterImportanceTier.MENTOR}>导师/引路人 - 指导主角成长</option>
                      <option value={CharacterImportanceTier.LOVE_INTEREST}>恋爱对象 - 主角感情线核心</option>
                      <option value={CharacterImportanceTier.BEST_FRIEND}>挚友/跟班 - 主角最亲密的伙伴</option>
                      <option value={CharacterImportanceTier.ARCHENEMY}>宿敌/主要反派 - 贯穿全文的反派BOSS</option>
                    </optgroup>
                    <optgroup label="重要配角层 (Tier 3) - 有独立剧情线">
                      <option value={CharacterImportanceTier.MAJOR_ALLY}>重要盟友</option>
                      <option value={CharacterImportanceTier.MAJOR_ANTAGONIST}>重要反派 - 阶段性BOSS</option>
                      <option value={CharacterImportanceTier.RIVAL}>竞争对手</option>
                      <option value={CharacterImportanceTier.FAMILY_MEMBER}>家人</option>
                      <option value={CharacterImportanceTier.GUARDIAN}>守护者</option>
                    </optgroup>
                    <optgroup label="阶段性角色层 (Tier 4)">
                      <option value={CharacterImportanceTier.ARC_ANTAGONIST}>篇章反派</option>
                      <option value={CharacterImportanceTier.ARC_ALLY}>篇章盟友</option>
                      <option value={CharacterImportanceTier.RECURRING}>常驻配角</option>
                      <option value={CharacterImportanceTier.CATALYST}>催化剂角色 - 推动剧情转折</option>
                      <option value={CharacterImportanceTier.MYSTERY_FIGURE}>神秘人物</option>
                    </optgroup>
                    <optgroup label="功能性角色层 (Tier 5)">
                      <option value={CharacterImportanceTier.MINION}>爪牙/手下</option>
                      <option value={CharacterImportanceTier.INFORMANT}>消息提供者</option>
                      <option value={CharacterImportanceTier.COMIC_RELIEF}>喜剧担当</option>
                      <option value={CharacterImportanceTier.VICTIM}>受害者</option>
                    </optgroup>
                    <optgroup label="背景层 (Tier 6)">
                      <option value={CharacterImportanceTier.NPC}>NPC - 路人角色</option>
                      <option value={CharacterImportanceTier.BACKGROUND}>背景人物</option>
                      <option value={CharacterImportanceTier.CAMEO}>客串</option>
                    </optgroup>
                  </select>
                  <p className={`mt-1 text-xs ${isDark ? 'text-gray-500' : 'text-gray-400'}`}>
                    层级越高，Agent 在生成剧情时越优先考虑该角色
                  </p>
                </div>

                <div>
                  <label className={`block text-sm font-medium mb-1 ${isDark ? 'text-gray-300' : 'text-gray-700'}`}>状态</label>
                  <select
                    className={`w-full px-3 py-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 ${isDark ? 'bg-gray-800 border-gray-600 text-white' : 'bg-white border-gray-300 text-gray-800'}`}
                    value={formData.status}
                    onChange={(e) => setFormData({ ...formData, status: e.target.value as Character['status'] })}
                  >
                    <option value="active">活跃</option>
                    <option value="inactive">不活跃</option>
                    <option value="dead">已故</option>
                    <option value="ghost">幽灵</option>
                    <option value="resurrected">复活</option>
                    <option value="paused">暂停</option>
                  </select>
                </div>

                <TextArea
                  label="角色描述 *"
                  value={formData.description}
                  onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                  placeholder="描述角色的基本情况..."
                  rows={3}
                />

                <TextArea
                  label="背景故事"
                  value={formData.background_story || ''}
                  onChange={(e) => setFormData({ ...formData, background_story: e.target.value })}
                  placeholder="角色的背景故事、经历..."
                  rows={4}
                />
              </div>
            )}

            {/* 关系网络 Tab */}
            {activeTab === 'relationships' && (
              <CharacterRelationshipEditor
                characters={characters}
                currentCharacterId={editingChar?.id}
                currentCharacterName={formData.name || editingChar?.name || '当前角色'}
                value={formData.key_relationships || {}}
                legacyRelationships={formData.relationships || []}
                onChange={(next) => setFormData({ ...formData, key_relationships: next })}
                onLegacyRelationshipsChange={(next) => setFormData({ ...formData, relationships: next })}
                isDark={isDark}
              />
            )}

            {/* 位置地图 Tab */}
            {activeTab === 'location' && (
              <div className="space-y-4">
                <div className={`p-4 rounded-lg ${isDark ? 'bg-blue-900/20 border border-blue-700/30' : 'bg-blue-50 border border-blue-100'}`}>
                  <div className={`flex items-start gap-2 text-sm ${isDark ? 'text-blue-200' : 'text-blue-700'}`}>
                    <MapPin size={16} className="mt-0.5 flex-shrink-0" />
                    <p>记录角色当前所在地图区域，以及“为什么来到这里”的简短因果概述，供后续剧情和工作流节点追踪位置逻辑。</p>
                  </div>
                </div>

                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className={`block text-sm font-medium mb-1 ${isDark ? 'text-gray-300' : 'text-gray-700'}`}>
                      所属世界
                    </label>
                    <select
                      className={`w-full px-3 py-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 ${isDark ? 'bg-gray-800 border-gray-600 text-white' : 'bg-white border-gray-300 text-gray-800'}`}
                      value={formData.world_id || ''}
                      onChange={(e) => setFormData({
                        ...formData,
                        world_id: e.target.value,
                        current_region_id: '',
                        current_location: '',
                      })}
                    >
                      <option value="">未关联世界</option>
                      {worlds.map((world) => (
                        <option key={world.id} value={world.id}>{formatWorldLabel(world)}</option>
                      ))}
                    </select>
                    <p className={`mt-1 text-xs ${isDark ? 'text-gray-500' : 'text-gray-400'}`}>
                      如选择区域，后端会校验区域必须属于该世界。
                    </p>
                  </div>

                  <div>
                    <label className={`block text-sm font-medium mb-1 ${isDark ? 'text-gray-300' : 'text-gray-700'}`}>
                      当前所在区域
                    </label>
                    <select
                      className={`w-full px-3 py-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:opacity-60 ${isDark ? 'bg-gray-800 border-gray-600 text-white' : 'bg-white border-gray-300 text-gray-800'}`}
                      value={formData.current_region_id || ''}
                      disabled={!formData.world_id}
                      onChange={(e) => {
                        const nextRegion = regions.find(region => region.id === e.target.value)
                        setFormData({
                          ...formData,
                          current_region_id: e.target.value,
                          current_location: nextRegion?.name || '',
                        })
                      }}
                    >
                      <option value="">{formData.world_id ? '未选择区域' : '请先选择世界'}</option>
                      {regions.map((region) => (
                        <option key={region.id} value={region.id}>{region.name}</option>
                      ))}
                    </select>
                  </div>
                </div>

                <Input
                  label="当前位置文本"
                  value={formData.current_location || ''}
                  onChange={(e) => setFormData({ ...formData, current_location: e.target.value })}
                  placeholder="可作为展示名或旧数据兼容字段；选择区域后会自动填入区域名"
                />

                <TextArea
                  label="来到这里的理由概述"
                  value={formData.current_location_reason || ''}
                  onChange={(e) => setFormData({ ...formData, current_location_reason: e.target.value })}
                  placeholder="简短说明角色为何来到此地，例如：追踪线索、躲避追杀、履行约定"
                  rows={4}
                />
              </div>
            )}

            {/* 外观性格 Tab */}
            {activeTab === 'appearance' && (
              <div className="space-y-4">
                {/* AI 生成按钮 */}
                <div className={`p-4 rounded-lg ${isDark ? 'bg-gradient-to-r from-purple-900/30 to-blue-900/30 border border-purple-700/30' : 'bg-gradient-to-r from-purple-50 to-blue-50 border border-purple-200'}`}>
                  <div className="flex items-center justify-between">
                    <div>
                      <h4 className={`font-medium ${isDark ? 'text-purple-300' : 'text-purple-700'}`}>
                        <Sparkles size={16} className="inline mr-1.5" />
                        AI 智能生成
                      </h4>
                      <p className={`text-xs mt-1 ${isDark ? 'text-gray-400' : 'text-gray-500'}`}>
                        由设定 Agent 根据角色信息自动生成外貌和性格设定
                      </p>
                    </div>
                    <Button
                      onClick={handleGenerateAppearanceAndPersonality}
                      disabled={generatingPersonality || !editingChar?.id}
                    >
                      {generatingPersonality ? (
                        <>
                          <RefreshCw size={14} className="mr-1.5 animate-spin" />
                          生成中...
                        </>
                      ) : (
                        <>
                          <Sparkles size={14} className="mr-1.5" />
                          {editingChar?.id ? '生成外貌和性格' : '保存后可生成'}
                        </>
                      )}
                    </Button>
                  </div>
                  {!editingChar?.id && (
                    <p className={`text-xs mt-2 ${isDark ? 'text-yellow-400/80' : 'text-yellow-600'}`}>
                      💡 新建角色请先保存后再使用 AI 生成功能
                    </p>
                  )}
                </div>

                <TextArea
                  label="外貌描述"
                  value={formData.appearance || ''}
                  onChange={(e) => setFormData({ ...formData, appearance: e.target.value })}
                  placeholder="描述角色的外貌特征、穿着打扮、气质等..."
                  rows={3}
                />

                <TextArea
                  label="性格特点"
                  value={formData.personality || ''}
                  onChange={(e) => setFormData({ ...formData, personality: e.target.value })}
                  placeholder="描述角色的性格、习惯、价值观等..."
                  rows={4}
                />
              </div>
            )}

            {/* 语言风格 Tab */}
            {activeTab === 'voice' && (
              <div className="space-y-4">
                <TextArea
                  label="说话风格"
                  value={formData.speech_pattern || ''}
                  onChange={(e) => setFormData({ ...formData, speech_pattern: e.target.value })}
                  placeholder="如：简短凌厉、爱反问、喜欢古风措辞"
                  rows={2}
                />

                <Input
                  label="常用词汇"
                  value={lexiconInput}
                  onChange={(e) => setLexiconInput(e.target.value)}
                  placeholder="用逗号分隔，如：江湖，义气，动手"
                />

                <Input
                  label="禁用词"
                  value={forbiddenWordsInput}
                  onChange={(e) => setForbiddenWordsInput(e.target.value)}
                  placeholder="用逗号分隔，如：斟酌，考量，之乎者也"
                />

                <TextArea
                  label="预置声音样本"
                  value={voiceSamplesInput}
                  onChange={(e) => setVoiceSamplesInput(e.target.value)}
                  placeholder="每行一条典型台词"
                  rows={5}
                />
              </div>
            )}

            {/* Agent 配置 Tab */}
            {activeTab === 'agent' && (
              <div className="space-y-4">
                <div className={`p-4 rounded-lg ${isDark ? 'bg-gray-800' : 'bg-gray-50'}`}>
                  <p className={`text-sm mb-3 ${isDark ? 'text-gray-400' : 'text-gray-500'}`}>
                    启用后，该角色将拥有独立的 Agent，可参与故事发展和对话
                  </p>

                  <label className={`flex items-center gap-2 mb-4 cursor-pointer ${isDark ? 'text-gray-300' : 'text-gray-700'}`}>
                    <input
                      type="checkbox"
                      checked={formData.has_agent || false}
                      onChange={(e) => setFormData({ ...formData, has_agent: e.target.checked })}
                      className="w-4 h-4 rounded"
                    />
                    <span className="font-medium">启用角色 Agent</span>
                  </label>

                  {formData.has_agent && (
                    <div className="space-y-4 pl-4 border-l-2 border-purple-500/30">
                      <label className={`flex items-center gap-2 cursor-pointer ${isDark ? 'text-gray-300' : 'text-gray-700'}`}>
                        <input
                          type="checkbox"
                          checked={formData.agent_enabled ?? true}
                          onChange={(e) => setFormData({ ...formData, agent_enabled: e.target.checked })}
                          className="w-4 h-4 rounded"
                        />
                        <span>Agent 激活状态</span>
                      </label>

                      <div>
                        <label className={`block text-sm mb-1 ${isDark ? 'text-gray-400' : 'text-gray-600'}`}>
                          <Target size={14} className="inline mr-1" /> Agent 目标
                        </label>
                        <TextArea
                          value={agentGoalsInput}
                          onChange={(e) => setAgentGoalsInput(e.target.value)}
                          placeholder="每行一个目标，如：&#10;保护主角安全&#10;寻找失散的家人&#10;提升自身实力"
                          rows={4}
                        />
                      </div>

                      <div>
                        <label className={`block text-sm mb-1 ${isDark ? 'text-gray-400' : 'text-gray-600'}`}>
                          <Brain size={14} className="inline mr-1" /> Agent 记忆要点
                        </label>
                        <TextArea
                          value={agentMemoryInput}
                          onChange={(e) => setAgentMemoryInput(e.target.value)}
                          placeholder="每行一个记忆要点，如：&#10;曾受过主角救命之恩&#10;知道一个重要秘密&#10;与反派有深仇大恨"
                          rows={4}
                        />
                      </div>
                    </div>
                  )}
                </div>
              </div>
            )}
          </div>

          {/* 底部操作按钮 */}
          <div className={`flex justify-between items-center pt-4 border-t ${isDark ? 'border-gray-700' : 'border-gray-200'}`}>
            <div className={`text-xs ${isDark ? 'text-gray-500' : 'text-gray-400'}`}>
              {formData.has_agent && '✓ Agent 已启用'}
            </div>
            <div className="flex gap-3">
              <Button variant="secondary" onClick={() => setShowModal(false)}>取消</Button>
              <Button onClick={saveCharacter}>{editingChar ? '保存修改' : '创建角色'}</Button>
            </div>
          </div>
        </div>
      </Modal>

      {/* Agent Prompt 预览 Modal */}
      <Modal
        isOpen={showAgentPromptModal}
        onClose={() => setShowAgentPromptModal(false)}
        title="Agent Prompt 预览"
        size="xl"
      >
        {agentPromptLoading ? (
          <div className={`text-center py-8 ${isDark ? 'text-gray-400' : 'text-gray-500'}`}>加载中...</div>
        ) : agentPromptData?.has_agent ? (
          <div className="space-y-4">
            <div className={`p-3 rounded-lg ${isDark ? 'bg-gray-800' : 'bg-gray-50'}`}>
              <div className="flex items-center gap-2 mb-2">
                <span className={`font-medium ${isDark ? 'text-white' : 'text-gray-800'}`}>
                  {agentPromptData.character_name}
                </span>
                <span className={`px-2 py-0.5 text-xs rounded ${agentPromptData.agent_enabled ? 'bg-green-100 text-green-700' : 'bg-gray-200 text-gray-500'}`}>
                  {agentPromptData.agent_enabled ? '已激活' : '未激活'}
                </span>
              </div>
              <div className={`text-xs ${isDark ? 'text-gray-400' : 'text-gray-500'}`}>
                Prompt 长度: {agentPromptData.prompt_length} 字符
              </div>
            </div>

            {agentPromptData.variables && (
              <div>
                <h4 className={`text-sm font-medium mb-2 ${isDark ? 'text-gray-300' : 'text-gray-700'}`}>变量</h4>
                <div className={`p-3 rounded text-xs font-mono ${isDark ? 'bg-gray-800' : 'bg-gray-100'}`}>
                  <div><span className="text-blue-400">character_background:</span> {agentPromptData.variables.character_background?.substring(0, 100)}...</div>
                  <div><span className="text-blue-400">character_personality:</span> {agentPromptData.variables.character_personality?.substring(0, 100)}...</div>
                  <div><span className="text-blue-400">character_goals:</span> {agentPromptData.variables.character_goals?.split('\n')[0]}...</div>
                </div>
              </div>
            )}

            <div>
              <h4 className={`text-sm font-medium mb-2 ${isDark ? 'text-gray-300' : 'text-gray-700'}`}>完整 Prompt</h4>
              <pre className={`p-4 rounded text-xs overflow-auto max-h-[400px] whitespace-pre-wrap ${isDark ? 'bg-gray-900 text-gray-300' : 'bg-gray-100 text-gray-700'}`}>
                {agentPromptData.prompt}
              </pre>
            </div>
          </div>
        ) : (
          <div className={`text-center py-8 ${isDark ? 'text-gray-400' : 'text-gray-500'}`}>
            {agentPromptData?.message || '该角色未启用 Agent'}
          </div>
        )}
      </Modal>
    </PageLayout>
  )
}
