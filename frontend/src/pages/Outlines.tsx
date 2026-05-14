/**
 * 章节大纲管理页面
 * 与 Plot Outline Agent 协作管理章节大纲
 */

import { useEffect, useMemo, useState } from 'react'
import { Card, Button, Input } from '@/components/ui'
import PageLayout from '@/components/PageLayout'
import AssistantContextControls from '@/components/assistant/AssistantContextControls'
import { createAssistantSession, getAssistantHistory, type AssistantContextSummary } from '@/api/assistantContext'
import { getCharacters, type Character } from '@/api/characters'
import { getLoreList, type LoreEntry } from '@/api/lore'
import { getRegions, getWorlds, type Region } from '@/api/worlds'
import { useProject } from '@/contexts/ProjectContext'
import { useTheme } from '@/contexts/ThemeContext'
import {
  getOutlines,
  getOutline,
  getOutlineById,
  getOutlineVersions,
  approveOutlineById,
  rejectOutlineRevisionById,
  chatWithAgent,
  savePendingOutlines,
  formatSavePendingOutlinesFailure,
  deleteOutline,
  getOutlineResourceRequirements,
  getChapterResourceReadiness,
  generateResourceSupplementDrafts,
  confirmResourceSupplementDrafts,
  updateOutlineResourceRequirementStatus,
  type ChapterOutline,
  type SceneOutline,
  type EmotionPoint,
  type OutlineStatus,
  type OutlineResourceRequirement,
  type ChapterResourceReadiness,
  type ResourceSupplementDraft,
  type ResourceRequirementStatus,
  type OutlineVersionsResponse,
} from '@/api/outlines'
import { formatApiErrorMessage } from '@/api/workflows'
import {
  formatRequirementResolutionResult,
  formatRequirementTypeFlow,
  getRequirementOriginalType,
  getRequirementTargetType,
  getRequirementTypeLabel,
} from '@/utils/resourceRequirementDisplay'
import {
  BookOpen, Plus, Edit2, Check, MessageSquare, Send, RefreshCw,
  ChevronLeft, ChevronRight, Play, Sparkles, Target, Users,
  MapPin, Clock, Zap, CheckCircle, X, Loader2, Trash2
} from 'lucide-react'

// 情绪类型映射
const EMOTION_LABELS: Record<string, { label: string; color: string }> = {
  joy: { label: '喜悦', color: 'text-yellow-500' },
  anger: { label: '愤怒', color: 'text-red-500' },
  sadness: { label: '悲伤', color: 'text-blue-500' },
  fear: { label: '恐惧', color: 'text-purple-500' },
  surprise: { label: '惊讶', color: 'text-orange-500' },
  disgust: { label: '厌恶', color: 'text-green-500' },
  anticipation: { label: '期待', color: 'text-cyan-500' },
  trust: { label: '信任', color: 'text-teal-500' },
  tension: { label: '紧张', color: 'text-amber-500' },
  relief: { label: '释然', color: 'text-lime-500' },
  neutral: { label: '中性', color: 'text-gray-500' },
}

// 场景类型映射
const SCENE_TYPE_LABELS: Record<string, string> = {
  dialogue: '对话',
  action: '动作',
  description: '描写',
  transition: '过渡',
  climax: '高潮',
  resolution: '结局',
  flashback: '回忆',
  foreshadow: '伏笔',
}

// 状态映射
const STATUS_CONFIG: Record<OutlineStatus, { label: string; color: string }> = {
  draft: { label: '草稿', color: 'bg-gray-100 text-gray-700' },
  approved: { label: '已审批', color: 'bg-green-100 text-green-700' },
  in_writing: { label: '写作中', color: 'bg-blue-100 text-blue-700' },
  completed: { label: '已完成', color: 'bg-purple-100 text-purple-700' },
  revision: { label: '修订提案', color: 'bg-orange-100 text-orange-700' },
  rejected: { label: '已拒绝', color: 'bg-red-100 text-red-700' },
}

type BindableResourceType = 'character' | 'lore' | 'location'

type RevisionNotice = {
  approvedOutlineId: string
  revisionOutlineId: string
  message: string
}

interface BindableResourceOption {
  id: string
  name: string
  type: BindableResourceType
  subtitle?: string
  description?: string
}

export default function Outlines() {
  const { theme } = useTheme()
  const isDark = theme === 'dark'
  const { currentProject } = useProject()

  // 状态
  const [outlines, setOutlines] = useState<ChapterOutline[]>([])
  const [selectedChapter, setSelectedChapter] = useState<number | null>(null)
  const [currentOutline, setCurrentOutline] = useState<ChapterOutline | null>(null)
  const [loading, setLoading] = useState(false)

  // 聊天状态
  const [showChat, setShowChat] = useState(false)
  const [chatMessages, setChatMessages] = useState<Array<{ role: 'user' | 'assistant'; content: string }>>([])
  const [chatInput, setChatInput] = useState('')
  const [sendingMessage, setSendingMessage] = useState(false)
  const [outlineChatAutoSave, setOutlineChatAutoSave] = useState(false)
  const [assistantSessionId, setAssistantSessionId] = useState<string | null>(null)
  const [contextPacket, setContextPacket] = useState<AssistantContextSummary | null>(null)

  // 编辑状态
  const [showSceneEditor, setShowSceneEditor] = useState(false)

  // 资源就绪状态
  const [resourceRequirements, setResourceRequirements] = useState<OutlineResourceRequirement[]>([])
  const [resourceReadiness, setResourceReadiness] = useState<ChapterResourceReadiness | null>(null)
  const [resourceDrafts, setResourceDrafts] = useState<ResourceSupplementDraft[]>([])
  const [loadingResources, setLoadingResources] = useState(false)
  const [generatingDrafts, setGeneratingDrafts] = useState(false)
  const [confirmingDrafts, setConfirmingDrafts] = useState(false)
  const [bindingRequirement, setBindingRequirement] = useState<OutlineResourceRequirement | null>(null)
  const [bindableResources, setBindableResources] = useState<BindableResourceOption[]>([])
  const [selectedBindableResourceId, setSelectedBindableResourceId] = useState('')
  const [loadingBindableResources, setLoadingBindableResources] = useState(false)
  const [bindingResource, setBindingResource] = useState(false)
  const [revisionNotice, setRevisionNotice] = useState<RevisionNotice | null>(null)
  const [outlineVersions, setOutlineVersions] = useState<OutlineVersionsResponse | null>(null)
  const [loadingVersions, setLoadingVersions] = useState(false)

  const directlyCreatableResourceTypes = ['character', 'lore', 'location']

  const getDraftDisplayResourceType = (draft: ResourceSupplementDraft) => formatRequirementTypeFlow(draft)

  const isDirectlyCreatableDraft = (draft: ResourceSupplementDraft) =>
    directlyCreatableResourceTypes.includes(draft.resource_type)

  const statusPriority: Record<OutlineStatus, number> = {
    approved: 0,
    in_writing: 1,
    completed: 2,
    draft: 3,
    revision: 4,
    rejected: 5,
  }

  const mergeOutlines = (current: ChapterOutline[], incoming: ChapterOutline[]) => {
    const outlineMap = new Map(current.map(outline => [outline.id, outline]))

    for (const outline of incoming) {
      outlineMap.set(outline.id, outline)
    }

    return Array.from(outlineMap.values()).sort((a, b) => {
      if (a.chapter_number !== b.chapter_number) return a.chapter_number - b.chapter_number
      return statusPriority[a.status] - statusPriority[b.status] || a.id.localeCompare(b.id)
    })
  }

  const getChapterNavigationOutlines = (source: ChapterOutline[]) => {
    const chapterMap = new Map<number, ChapterOutline>()

    for (const outline of source) {
      const current = chapterMap.get(outline.chapter_number)
      if (!current || statusPriority[outline.status] < statusPriority[current.status]) {
        chapterMap.set(outline.chapter_number, outline)
      }
    }

    return Array.from(chapterMap.values()).sort((a, b) => a.chapter_number - b.chapter_number)
  }

  const chapterNavigationOutlines = useMemo(
    () => getChapterNavigationOutlines(outlines),
    [outlines]
  )

  const upsertOutline = (outline: ChapterOutline) => {
    setOutlines(prev => mergeOutlines(prev, [outline]))
  }

  const upsertOutlines = (incoming: ChapterOutline[]) => {
    setOutlines(prev => mergeOutlines(prev, incoming))
  }

  const loadOutlineVersions = async (chapterNumber: number) => {
    if (!currentProject?.id) return
    setLoadingVersions(true)
    try {
      const versions = await getOutlineVersions(currentProject.id, chapterNumber)
      setOutlineVersions(versions)
      upsertOutlines(versions.versions)
    } catch (error) {
      console.error('Failed to load outline versions:', error)
      setOutlineVersions(null)
    } finally {
      setLoadingVersions(false)
    }
  }

  const selectOutlineVersion = async (outlineId: string) => {
    if (!currentProject?.id) return
    setLoading(true)
    try {
      const outline = await getOutlineById(currentProject.id, outlineId)
      setCurrentOutline(outline)
      setSelectedChapter(outline.chapter_number)
      setRevisionNotice(null)
      await loadResourceStatus(outline.chapter_number, outline.id)
      await loadOutlineVersions(outline.chapter_number)
      await loadOutlineAssistantSession(outline.chapter_number)
    } catch (error) {
      console.error('Failed to load outline version:', error)
      alert('加载大纲版本失败')
    } finally {
      setLoading(false)
    }
  }


  // 加载大纲列表
  useEffect(() => {
    if (currentProject?.id) {
      loadOutlines()
    }
  }, [currentProject?.id])

  const getOutlineAgentStorageKey = (projectId: string) => `plotOutlineAgentSession:${projectId}:outlines`
  const getLegacyFirstChapterAgentStorageKey = (projectId: string) => `plotOutlineAgentSession:${projectId}:1`
  const outlineAgentMode = 'chapter:1'

  const loadOutlineAssistantSession = async (selectedChapterNumber = selectedChapter || 1) => {
    if (!currentProject?.id) return
    setAssistantSessionId(null)
    setContextPacket(null)
    const storageKey = getOutlineAgentStorageKey(currentProject.id)
    const legacyFirstChapterStorageKey = getLegacyFirstChapterAgentStorageKey(currentProject.id)
    const storedSessionId = localStorage.getItem(storageKey) || localStorage.getItem(legacyFirstChapterStorageKey) || undefined
    try {
      const session = await createAssistantSession(currentProject.id, {
        assistant_surface: 'plot_outline_agent',
        mode: outlineAgentMode,
        session_id: storedSessionId,
        scope: { entry: 'outlines', selected_chapter_number: selectedChapterNumber },
      })
      setAssistantSessionId(session.session_id)
      localStorage.setItem(storageKey, session.session_id)
      localStorage.setItem(legacyFirstChapterStorageKey, session.session_id)
      const history = await getAssistantHistory(currentProject.id, session.session_id, 80)
      setChatMessages(history.messages
        .filter(message => message.role === 'user' || message.role === 'assistant')
        .map(message => ({ role: message.role as 'user' | 'assistant', content: message.content })))
    } catch (error) {
      console.error('Failed to load outline assistant session:', error)
    }
  }

  const loadOutlines = async () => {
    if (!currentProject?.id) return
    setLoading(true)
    try {
      const result = await getOutlines(currentProject.id)
      setOutlines(result.outlines)
      const navigationOutlines = getChapterNavigationOutlines(result.outlines)
      if (navigationOutlines.length > 0 && !selectedChapter) {
        selectChapter(navigationOutlines[0].chapter_number)
      } else if (navigationOutlines.length === 0 && !selectedChapter) {
        setSelectedChapter(1)
        setCurrentOutline(null)
        setOutlineVersions(null)
      }
    } catch (error) {
      console.error('Failed to load outlines:', error)
    } finally {
      setLoading(false)
    }
  }

  const loadResourceStatus = async (chapterNumber: number, outlineId?: string, refresh = true) => {
    if (!currentProject?.id) return
    setLoadingResources(true)
    try {
      const resourceFilters = {
        chapter_num: chapterNumber,
        ...(outlineId ? { outline_id: outlineId } : {}),
      }
      const [requirementsResult, readinessResult] = await Promise.all([
        getOutlineResourceRequirements(currentProject.id, resourceFilters),
        getChapterResourceReadiness(currentProject.id, {
          ...resourceFilters,
          refresh,
        }),
      ])
      setResourceRequirements(requirementsResult.requirements)
      const readiness = outlineId
        ? readinessResult.readiness.find(item => item.outline_id === outlineId) ?? readinessResult.readiness[0] ?? null
        : readinessResult.readiness.find(item => !item.outline_id) ?? readinessResult.readiness[0] ?? null
      setResourceReadiness(readiness)
    } catch (error) {
      console.error('Failed to load resource readiness:', error)
      setResourceRequirements([])
      setResourceReadiness(null)
    } finally {
      setLoadingResources(false)
    }
  }

  const selectChapter = async (chapterNumber: number) => {
    if (!currentProject?.id) return
    setSelectedChapter(chapterNumber)
    setRevisionNotice(null)
    setResourceDrafts([])
    setLoading(true)
    try {
      const outline = await getOutline(currentProject.id, chapterNumber)
      setCurrentOutline(outline)
      await loadResourceStatus(chapterNumber, outline.id)
      await loadOutlineVersions(chapterNumber)
    } catch (error) {
      console.error('Failed to load outline:', error)
      setCurrentOutline(null)
      setOutlineVersions(null)
      await loadResourceStatus(chapterNumber)
    } finally {
      if (showChat && !assistantSessionId) {
        await loadOutlineAssistantSession(chapterNumber)
      }
      setLoading(false)
    }
  }

  const refreshResourceStatus = async (refresh = true) => {
    if (!selectedChapter) return
    await loadResourceStatus(selectedChapter, currentOutline?.id, refresh)
  }

  const handleGenerateResourceDrafts = async (includeAdvisory = false) => {
    if (!currentProject?.id || !selectedChapter) return
    setGeneratingDrafts(true)
    try {
      const result = await generateResourceSupplementDrafts({
        project_id: currentProject.id,
        chapter_num: selectedChapter,
        outline_id: currentOutline?.id,
        include_advisory: includeAdvisory,
      })
      setResourceDrafts(result.drafts)
      if (result.drafts.length === 0) {
        alert('当前没有可生成补全草案的未解决资源需求')
      }
    } catch (error) {
      console.error('Failed to generate resource drafts:', error)
      alert(formatApiErrorMessage(error, '生成资源补全草案失败'))
    } finally {
      setGeneratingDrafts(false)
    }
  }

  const handleConfirmResourceDrafts = async () => {
    if (!currentProject?.id || resourceDrafts.length === 0) return
    const creatableDrafts = resourceDrafts.filter(isDirectlyCreatableDraft)
    if (creatableDrafts.length === 0) {
      alert('当前草案暂不包含可直接创建的角色、设定或地点资源')
      return
    }
    setConfirmingDrafts(true)
    try {
      const result = await confirmResourceSupplementDrafts({
        project_id: currentProject.id,
        drafts: creatableDrafts.map(draft => ({
          requirement_id: draft.requirement_id,
          resource_type: draft.resource_type,
          draft_payload: draft.draft_payload,
        })),
      })
      const failedMessage = result.failed.length > 0 ? `，${result.failed.length} 个失败` : ''
      alert(`已创建 ${result.created.length} 个资源${failedMessage}`)
      setResourceDrafts([])
      await refreshResourceStatus(true)
    } catch (error) {
      console.error('Failed to confirm resource drafts:', error)
      alert(formatApiErrorMessage(error, '确认创建资源失败'))
    } finally {
      setConfirmingDrafts(false)
    }
  }

  const getBindableResourceType = (requirement: OutlineResourceRequirement): BindableResourceType | null => {
    const type = requirement.requirement_type.toLowerCase()
    if (['character', 'role', '人物', '角色'].includes(type)) return 'character'
    if (['lore', 'setting', '设定'].includes(type)) return 'lore'
    if (['location', 'place', '地点', '场景地点'].includes(type)) return 'location'
    return null
  }

  const loadBindableResources = async (requirement: OutlineResourceRequirement) => {
    if (!currentProject?.id) return
    const resourceType = getBindableResourceType(requirement)
    if (!resourceType) {
      alert('当前需求类型暂不支持绑定已有资源')
      return
    }

    setBindingRequirement(requirement)
    setSelectedBindableResourceId('')
    setBindableResources([])
    setLoadingBindableResources(true)
    try {
      if (resourceType === 'character') {
        const characters = await getCharacters(currentProject.id)
        setBindableResources(characters
          .filter((character: Character) => character.id)
          .map((character: Character) => ({
            id: character.id as string,
            name: character.name,
            type: 'character',
            subtitle: character.role || character.importance_tier,
            description: character.description,
          })))
      } else if (resourceType === 'lore') {
        let lores = await getLoreList(currentProject.id, undefined, undefined, requirement.resource_name)
        if (lores.length === 0) {
          lores = await getLoreList(currentProject.id)
        }
        setBindableResources(lores.map((lore: LoreEntry) => ({
          id: lore.id,
          name: lore.title,
          type: 'lore',
          subtitle: lore.category,
          description: lore.summary || lore.content,
        })))
      } else if (resourceType === 'location') {
        const worlds = await getWorlds(currentProject.id)
        const regionGroups = await Promise.all(
          worlds
            .filter(world => world.id)
            .map(async world => ({
              world,
              regions: await getRegions(world.id as string),
            }))
        )
        const options: BindableResourceOption[] = regionGroups.flatMap(({ world, regions }) =>
          regions
            .map((region: Region) => ({
              id: region.id || region.name,
              name: region.name,
              type: 'location' as const,
              subtitle: `${world.name || '未命名世界'} · ${region.region_type || 'location'}`,
              description: region.description || region.atmosphere,
            }))
            .filter(resource => resource.id)
        )
        setBindableResources(options)
      }
    } catch (error) {
      console.error('Failed to load bindable resources:', error)
      alert('加载可绑定资源失败')
      setBindingRequirement(null)
    } finally {
      setLoadingBindableResources(false)
    }
  }

  const handleUpdateRequirementStatus = async (requirementId: string, status: ResourceRequirementStatus) => {
    try {
      await updateOutlineResourceRequirementStatus(requirementId, {
        status,
        ...(status === 'resolved' ? { resolution_method: 'manual_resolved' as const } : {}),
        ...(status === 'ignored' ? { resolution_method: 'ignored' as const } : {}),
      })
      await refreshResourceStatus(true)
    } catch (error) {
      console.error('Failed to update resource requirement:', error)
      alert(formatApiErrorMessage(error, '更新资源需求状态失败'))
    }
  }

  const handleBindExistingResource = async () => {
    if (!bindingRequirement || !selectedBindableResourceId) return
    const selected = bindableResources.find(resource => resource.id === selectedBindableResourceId)
    if (!selected) return

    setBindingResource(true)
    try {
      await updateOutlineResourceRequirementStatus(bindingRequirement.id, {
        status: 'resolved',
        matched_resource_id: selected.id,
        matched_resource_type: selected.type,
        resolution_method: 'bind_existing',
      })
      setBindingRequirement(null)
      setBindableResources([])
      setSelectedBindableResourceId('')
      await refreshResourceStatus(true)
    } catch (error) {
      console.error('Failed to bind existing resource:', error)
      alert(formatApiErrorMessage(error, '绑定已有资源失败'))
    } finally {
      setBindingResource(false)
    }
  }

  const handleApprove = async () => {
    if (!currentProject?.id || !currentOutline) return
    try {
      const updated = await approveOutlineById(currentProject.id, currentOutline.id, 'user')
      setCurrentOutline(updated)
      upsertOutline(updated)
      setRevisionNotice(null)
      await loadOutlineVersions(updated.chapter_number)
      await loadResourceStatus(updated.chapter_number, updated.id)
    } catch (error) {
      console.error('Failed to approve outline:', error)
      alert(formatApiErrorMessage(error, '审批大纲失败'))
    }
  }

  const handleRejectRevision = async () => {
    if (!currentProject?.id || !currentOutline || currentOutline.status !== 'revision') return
    if (!confirm('确认拒绝当前修订提案？原已审批大纲会保持不变。')) return

    try {
      const rejected = await rejectOutlineRevisionById(currentProject.id, currentOutline.id)
      setCurrentOutline(rejected)
      upsertOutline(rejected)
      setRevisionNotice(null)
      await loadOutlineVersions(rejected.chapter_number)
      if (outlineVersions?.current_approved) {
        await selectOutlineVersion(outlineVersions.current_approved.id)
      }
    } catch (error) {
      console.error('Failed to reject outline revision:', error)
      alert('拒绝修订失败')
    }
  }

  const handleDelete = async () => {
    if (!currentProject?.id || !selectedChapter) return
    const keepContent = confirm(
      `删除第${selectedChapter}章大纲时，默认保留已经生成的小说正文。\n\n点击“确定”：仅删除大纲，保留正文。\n点击“取消”：继续选择是否同时软删除正文。`
    )
    let softDeleteGeneratedChapters = false

    if (!keepContent) {
      softDeleteGeneratedChapters = confirm(
        `是否同时软删除第${selectedChapter}章大纲关联生成的小说正文？\n\n正文会被标记为已删除，默认列表不再显示，但不是物理删除。`
      )
      if (!softDeleteGeneratedChapters) return
    }

    const deleteAllVersions = confirm(
      `是否删除第${selectedChapter}章的全部大纲版本？\n\n点击“确定”：删除本章所有草稿/修订/已审批版本。\n点击“取消”：只删除当前有效版本。`
    )

    try {
      const deletedChapter = selectedChapter
      const result = await deleteOutline(currentProject.id, deletedChapter, { softDeleteGeneratedChapters, deleteAllVersions })
      setCurrentOutline(null)
      setOutlineVersions(null)
      setResourceReadiness(null)
      setResourceRequirements([])
      setResourceDrafts([])
      await loadOutlines()
      try {
        await loadOutlineVersions(deletedChapter)
      } catch {
        setOutlineVersions(null)
      }
      alert(result.message)
    } catch (error) {
      console.error('Failed to delete outline:', error)
      alert('删除失败，请稍后再试')
    }
  }

  const handleStartFirstChapterChat = async () => {
    // 设置为第一章
    setSelectedChapter(1)
    setResourceRequirements([])
    setResourceReadiness(null)
    setResourceDrafts([])
    // 打开聊天面板
    setShowChat(true)
    // 设置初始消息
    const initialMessage = '请帮我生成第一章大纲'
    setChatInput(initialMessage)
    await loadOutlineAssistantSession(1)
    // 自动发送消息
    await sendChatMessage(initialMessage, 1)
  }

  const openOutlineChat = async (chapterNumber = selectedChapter || 1) => {
    setSelectedChapter(chapterNumber)
    setShowChat(true)
    await loadOutlineAssistantSession(chapterNumber)
  }

  const sendChatMessage = async (message: string, explicitChapterNumber?: number) => {
    if (!currentProject?.id) return

    const chapterNumber = explicitChapterNumber || selectedChapter || 1
    setSelectedChapter(chapterNumber)
    setSendingMessage(true)

    // 添加用户消息
    setChatMessages(prev => [...prev, { role: 'user' as const, content: message }])

    try {
      let sessionId = assistantSessionId || undefined
      const storageKey = getOutlineAgentStorageKey(currentProject.id)
      const legacyFirstChapterStorageKey = getLegacyFirstChapterAgentStorageKey(currentProject.id)
      if (!sessionId) {
        const session = await createAssistantSession(currentProject.id, {
          assistant_surface: 'plot_outline_agent',
          mode: outlineAgentMode,
          session_id: localStorage.getItem(storageKey) || localStorage.getItem(legacyFirstChapterStorageKey) || undefined,
          scope: { entry: 'outlines', selected_chapter_number: chapterNumber },
        })
        sessionId = session.session_id
        setAssistantSessionId(session.session_id)
        localStorage.setItem(storageKey, session.session_id)
        localStorage.setItem(legacyFirstChapterStorageKey, session.session_id)
      }
      const requestId = `outline_chat_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`
      const response = await chatWithAgent(
        currentProject.id,
        chapterNumber,
        message,
        { selected_chapter_number: chapterNumber, entry: 'outlines' },
        sessionId,
        requestId,
        outlineChatAutoSave,
      )
      if (response.assistant_session_id) {
        setAssistantSessionId(response.assistant_session_id)
        localStorage.setItem(storageKey, response.assistant_session_id)
        localStorage.setItem(legacyFirstChapterStorageKey, response.assistant_session_id)
      }
      if (response.context_packet) setContextPacket(response.context_packet)
      setChatMessages(prev => [...prev, { role: 'assistant' as const, content: response.message }])
      if (response.parse_status === 'outline_parse_failed') {
        const warning = response.warnings?.[0] || '未解析到可保存的大纲 JSON，因此没有创建左侧草稿。'
        setChatMessages(prev => [...prev, { role: 'assistant' as const, content: warning }])
        return
      }

      // 处理多章大纲保存
      const savedOutlines = response.saved_outlines
      if (savedOutlines && savedOutlines.length > 0) {
        setChatMessages(prev => [...prev, {
          role: 'assistant' as const,
          content: `已保存 ${savedOutlines.length} 章大纲草稿：${savedOutlines.map(o => `第${o.chapter_number}章`).join('、')}`
        }])
        upsertOutlines(savedOutlines)
        const firstSaved = savedOutlines[0]
        setCurrentOutline(firstSaved)
        setSelectedChapter(firstSaved.chapter_number)
        await loadResourceStatus(firstSaved.chapter_number, firstSaved.id)
      } else if (response.saved_outline) {
        setCurrentOutline(response.saved_outline)
        setSelectedChapter(response.saved_outline.chapter_number)
        upsertOutline(response.saved_outline)
        await loadResourceStatus(response.saved_outline.chapter_number, response.saved_outline.id)
      } else if (response.pending_outlines && response.pending_outlines.length > 0) {
        const saveResult = await savePendingOutlines(currentProject.id, response.pending_outlines)
        if (saveResult.saved_count <= 0) {
          setChatMessages(prev => [...prev, {
            role: 'assistant' as const,
            content: formatSavePendingOutlinesFailure(saveResult)
          }])
          return
        }

        setChatMessages(prev => [...prev, {
          role: 'assistant' as const,
          content: `已生成并保存 ${saveResult.saved_count} 章大纲草稿。${saveResult.failed_count ? `失败 ${saveResult.failed_count} 章，请查看日志或重试。` : ''}`
        }])
        const savedIds = new Set(saveResult.results.filter(item => item.status === 'saved' && item.outline_id).map(item => item.outline_id as string))
        const firstSavedChapter = saveResult.results.find(item => item.status === 'saved')?.chapter_number || response.pending_outlines[0]?.chapter_number || chapterNumber
        const refreshed = await getOutlines(currentProject.id)
        setOutlines(refreshed.outlines)
        const savedFromList = refreshed.outlines.filter(outline => savedIds.has(outline.id))
        if (savedFromList.length === 0) {
          setChatMessages(prev => [...prev, {
            role: 'assistant' as const,
            content: '后端返回保存成功，但刷新列表后没有找到对应草稿。请不要相信本轮“保存成功”，请检查后端保存日志或重试。'
          }])
          return
        }
        upsertOutlines(savedFromList)
        setSelectedChapter(firstSavedChapter)
        try {
          const outline = await getOutline(currentProject.id, firstSavedChapter)
          setCurrentOutline(outline)
          upsertOutline(outline)
          await loadResourceStatus(firstSavedChapter, outline.id)
          await loadOutlineVersions(firstSavedChapter)
        } catch (error) {
          console.error('Failed to load saved pending outline:', error)
        }
      } else if (response.outline_updates) {
        setCurrentOutline(prev => prev ? { ...prev, ...response.outline_updates } : prev)
      }
    } catch (error) {
      console.error('Chat error:', error)
      setChatMessages(prev => [
        ...prev,
        { role: 'assistant' as const, content: '抱歉，发生了错误。请稍后再试。' }
      ])
    } finally {
      setSendingMessage(false)
    }
  }

  const handleSendMessage = async () => {
    if (!currentProject?.id || !chatInput.trim() || sendingMessage) return
    const message = chatInput.trim()
    setChatInput('')
    await sendChatMessage(message)
  }

  const handleQuickCommand = (command: string) => {
    setChatInput(command)
  }

  const readinessConfig = (status?: ChapterResourceReadiness['readiness_status']) => {
    switch (status) {
      case 'blocked':
        return { label: '资源阻塞', color: 'bg-red-100 text-red-700' }
      case 'ready_with_warnings':
        return { label: '可启动但有警告', color: 'bg-yellow-100 text-yellow-700' }
      case 'ready':
        return { label: '资源就绪', color: 'bg-green-100 text-green-700' }
      case 'stale':
        return { label: '需重新审计', color: 'bg-orange-100 text-orange-700' }
      case 'not_audited':
      default:
        return { label: '未审计', color: 'bg-gray-100 text-gray-700' }
    }
  }

  const requirementLabel = (requirement: OutlineResourceRequirement) => {
    const severityLabel = requirement.severity === 'blocking' ? '阻塞' : requirement.severity === 'advisory' ? '建议' : '可选'
    return `${severityLabel} · ${formatRequirementTypeFlow(requirement)}`
  }

  const isRequirementActionable = (status: ResourceRequirementStatus) => ['pending', 'in_progress'].includes(status)

  const renderOutlineVersionPanel = () => {
    if (!currentOutline) return null

    const versions = outlineVersions?.versions ?? [currentOutline]
    const currentApproved = outlineVersions?.current_approved ?? null
    const pendingCount = outlineVersions?.pending_revisions.length ?? 0

    return (
      <Card className="p-4 mb-6">
        <div className="flex items-center justify-between mb-3">
          <div>
            <h3 className={`text-sm font-medium ${isDark ? 'text-gray-300' : 'text-gray-700'}`}>版本与修订</h3>
            <p className={`text-xs mt-1 ${isDark ? 'text-gray-500' : 'text-gray-500'}`}>
              章节启动默认使用已审批版本；修订提案只有审批后才成为后续写作依据。
            </p>
          </div>
          <Button size="sm" variant="secondary" onClick={() => loadOutlineVersions(currentOutline.chapter_number)} disabled={loadingVersions}>
            {loadingVersions ? <Loader2 className="w-4 h-4 mr-1 animate-spin" /> : <RefreshCw className="w-4 h-4 mr-1" />}
            刷新版本
          </Button>
        </div>

        {pendingCount > 0 && currentOutline.status !== 'revision' && (
          <p className={`text-xs mb-3 ${isDark ? 'text-orange-300' : 'text-orange-700'}`}>
            当前章节有 {pendingCount} 个待处理修订。请点选修订提案审查，或继续使用当前已审批版本。
          </p>
        )}

        <div className="space-y-2">
          {versions.map(version => {
            const status = STATUS_CONFIG[version.status]
            const active = currentOutline.id === version.id
            const isApprovedBaseline = currentApproved?.id === version.id
            return (
              <button
                key={version.id}
                onClick={() => selectOutlineVersion(version.id)}
                className={`w-full text-left p-3 rounded border transition-colors ${
                  active
                    ? isDark ? 'border-blue-700 bg-blue-950/40' : 'border-blue-200 bg-blue-50'
                    : isDark ? 'border-gray-700 bg-gray-800 hover:bg-gray-700' : 'border-gray-200 bg-white hover:bg-gray-50'
                }`}
              >
                <div className="flex items-center justify-between gap-2">
                  <div className="min-w-0">
                    <p className={`text-sm font-medium truncate ${isDark ? 'text-gray-100' : 'text-gray-800'}`}>{version.title}</p>
                    <p className={`text-xs mt-1 ${isDark ? 'text-gray-500' : 'text-gray-500'}`}>ID: {version.id}</p>
                  </div>
                  <div className="flex items-center gap-2 flex-shrink-0">
                    {isApprovedBaseline && (
                      <span className="px-2 py-0.5 text-xs rounded bg-green-100 text-green-700">当前基准</span>
                    )}
                    <span className={`px-2 py-0.5 text-xs rounded ${status.color}`}>{status.label}</span>
                  </div>
                </div>
                {version.previous_outline_id && (
                  <p className={`text-xs mt-2 ${isDark ? 'text-orange-300' : 'text-orange-700'}`}>
                    修订来源：{version.previous_outline_id}
                  </p>
                )}
              </button>
            )
          })}
        </div>
      </Card>
    )
  }

  const renderResourceReadinessPanel = () => {
    const config = readinessConfig(resourceReadiness?.readiness_status)
    const unresolvedRequirements = resourceRequirements.filter(req => !['resolved', 'ignored', 'superseded'].includes(req.status))
    const unresolvedBlockingRequirements = unresolvedRequirements.filter(req => req.severity === 'blocking')
    const supportedDrafts = resourceDrafts.filter(isDirectlyCreatableDraft)

    return (
      <Card className="p-4 mb-6">
        <div className="flex items-center justify-between mb-3">
          <div>
            <h3 className={`text-sm font-medium ${isDark ? 'text-gray-300' : 'text-gray-700'}`}>
              资源就绪检查
            </h3>
            <p className={`text-xs mt-1 ${isDark ? 'text-gray-500' : 'text-gray-500'}`}>
              生成补全草案不会直接创建资源，确认后才会写入角色/设定/地点并更新需求状态。
            </p>
          </div>
          <span className={`px-3 py-1 text-xs rounded-full ${config.color}`}>{config.label}</span>
        </div>

        <div className="grid grid-cols-2 md:grid-cols-4 gap-2 mb-4">
          <div className={`p-3 rounded ${isDark ? 'bg-gray-800' : 'bg-gray-50'}`}>
            <p className={`text-xs ${isDark ? 'text-gray-500' : 'text-gray-500'}`}>Blocking</p>
            <p className={`text-sm font-medium ${isDark ? 'text-gray-200' : 'text-gray-700'}`}>
              {resourceReadiness ? `${resourceReadiness.blocking_resolved}/${resourceReadiness.blocking_total}` : '0/0'}
            </p>
          </div>
          <div className={`p-3 rounded ${isDark ? 'bg-gray-800' : 'bg-gray-50'}`}>
            <p className={`text-xs ${isDark ? 'text-gray-500' : 'text-gray-500'}`}>Advisory</p>
            <p className={`text-sm font-medium ${isDark ? 'text-gray-200' : 'text-gray-700'}`}>
              {resourceReadiness ? `${resourceReadiness.advisory_resolved}/${resourceReadiness.advisory_total}` : '0/0'}
            </p>
          </div>
          <div className={`p-3 rounded ${isDark ? 'bg-gray-800' : 'bg-gray-50'}`}>
            <p className={`text-xs ${isDark ? 'text-gray-500' : 'text-gray-500'}`}>未解决需求</p>
            <p className={`text-sm font-medium ${isDark ? 'text-gray-200' : 'text-gray-700'}`}>{unresolvedRequirements.length}</p>
          </div>
          <div className={`p-3 rounded ${isDark ? 'bg-gray-800' : 'bg-gray-50'}`}>
            <p className={`text-xs ${isDark ? 'text-gray-500' : 'text-gray-500'}`}>草案</p>
            <p className={`text-sm font-medium ${isDark ? 'text-gray-200' : 'text-gray-700'}`}>{resourceDrafts.length}</p>
          </div>
        </div>

        <div className="flex flex-wrap gap-2 mb-4">
          <Button size="sm" variant="secondary" onClick={() => refreshResourceStatus(true)} disabled={loadingResources}>
            {loadingResources ? <Loader2 className="w-4 h-4 mr-1 animate-spin" /> : <RefreshCw className="w-4 h-4 mr-1" />}
            刷新资源状态
          </Button>
          <Button size="sm" onClick={() => handleGenerateResourceDrafts(false)} disabled={generatingDrafts || unresolvedBlockingRequirements.length === 0}>
            {generatingDrafts ? <Loader2 className="w-4 h-4 mr-1 animate-spin" /> : <Sparkles className="w-4 h-4 mr-1" />}
            生成 blocking 草案 ({unresolvedBlockingRequirements.length})
          </Button>
          <Button size="sm" variant="secondary" onClick={() => handleGenerateResourceDrafts(true)} disabled={generatingDrafts || unresolvedRequirements.length === 0}>
            包含 advisory
          </Button>
          {resourceDrafts.length > 0 && (
            <Button size="sm" onClick={handleConfirmResourceDrafts} disabled={confirmingDrafts || supportedDrafts.length === 0}>
              {confirmingDrafts ? <Loader2 className="w-4 h-4 mr-1 animate-spin" /> : <Check className="w-4 h-4 mr-1" />}
              确认创建可支持草案 ({supportedDrafts.length})
            </Button>
          )}
        </div>

        {unresolvedRequirements.length > 0 && unresolvedBlockingRequirements.length === 0 && (
          <p className={`text-xs mb-3 ${isDark ? 'text-yellow-300' : 'text-yellow-700'}`}>
            当前没有 blocking 缺口；如需处理建议类缺口，请使用“包含 advisory”，或直接忽略/标记解决。
          </p>
        )}

        {resourceRequirements.length === 0 ? (
          <p className={`text-sm ${isDark ? 'text-gray-500' : 'text-gray-500'}`}>暂无资源需求记录。</p>
        ) : (
          <div className="space-y-2 mb-4">
            {resourceRequirements.map(requirement => (
              <div key={requirement.id} className={`p-3 rounded border ${isDark ? 'border-gray-700 bg-gray-800' : 'border-gray-200 bg-gray-50'}`}>
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <div className="flex flex-wrap items-center gap-2 mb-1">
                      <span className={`text-xs px-2 py-0.5 rounded ${requirement.severity === 'blocking' ? 'bg-red-100 text-red-700' : requirement.severity === 'advisory' ? 'bg-yellow-100 text-yellow-700' : 'bg-gray-100 text-gray-700'}`}>
                        {requirementLabel(requirement)}
                      </span>
                      <span className={`text-xs px-2 py-0.5 rounded ${isDark ? 'bg-gray-700 text-gray-300' : 'bg-gray-200 text-gray-600'}`}>
                        {requirement.status}
                      </span>
                    </div>
                    <p className={`text-sm font-medium ${isDark ? 'text-gray-200' : 'text-gray-800'}`}>{requirement.resource_name}</p>
                    <div className={`text-xs mt-1 flex flex-wrap gap-2 ${isDark ? 'text-gray-400' : 'text-gray-600'}`}>
                      <span>需求类型：{getRequirementTypeLabel(getRequirementOriginalType(requirement))}</span>
                      <span>处理入口：{getRequirementTypeLabel(getRequirementTargetType(requirement))}</span>
                      <span>状态：{requirement.status}</span>
                    </div>
                    {requirement.reason && (
                      <p className={`text-xs mt-1 ${isDark ? 'text-gray-400' : 'text-gray-600'}`}>{requirement.reason}</p>
                    )}
                  </div>
                  <div className="flex flex-wrap gap-1 justify-end">
                    {isRequirementActionable(requirement.status) ? (
                      <>
                        {getBindableResourceType(requirement) && (
                          <Button size="sm" variant="secondary" onClick={() => loadBindableResources(requirement)}>绑定已有</Button>
                        )}
                        <Button size="sm" variant="secondary" onClick={() => handleUpdateRequirementStatus(requirement.id, 'in_progress')}>设为处理中</Button>
                        <Button size="sm" variant="secondary" onClick={() => handleUpdateRequirementStatus(requirement.id, 'ignored')}>忽略此需求</Button>
                        <Button size="sm" onClick={() => handleUpdateRequirementStatus(requirement.id, 'resolved')}>人工标记解决</Button>
                      </>
                    ) : (
                      <span className={`text-xs ${isDark ? 'text-gray-500' : 'text-gray-500'}`}>
                        {formatRequirementResolutionResult(requirement) || '已关闭'}
                      </span>
                    )}
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}

        {resourceDrafts.length > 0 && (
          <div className="space-y-2">
            <h4 className={`text-xs font-medium ${isDark ? 'text-gray-400' : 'text-gray-600'}`}>待确认补全草案</h4>
            {resourceDrafts.map(draft => (
              <div key={draft.requirement_id} className={`p-3 rounded border ${isDark ? 'border-blue-900 bg-blue-950/30' : 'border-blue-100 bg-blue-50'}`}>
                <div className="flex items-center justify-between mb-1">
                  <p className={`text-sm font-medium ${isDark ? 'text-blue-200' : 'text-blue-900'}`}>
                    {draft.resource_name || draft.draft_payload?.name || '未命名资源'}
                  </p>
                  <span className={`text-xs px-2 py-0.5 rounded ${isDark ? 'bg-blue-900 text-blue-200' : 'bg-blue-100 text-blue-700'}`}>
                    {getDraftDisplayResourceType(draft)}
                  </span>
                </div>
                {draft.reason && <p className={`text-xs ${isDark ? 'text-blue-300' : 'text-blue-700'}`}>{draft.reason}</p>}
                <div className={`text-xs mt-1 flex flex-wrap gap-2 ${isDark ? 'text-blue-300' : 'text-blue-700'}`}>
                  <span>需求类型：{getRequirementTypeLabel(getRequirementOriginalType(draft))}</span>
                  <span>处理入口：{getRequirementTypeLabel(getRequirementTargetType(draft))}</span>
                </div>
                {!isDirectlyCreatableDraft(draft) && (
                  <p className={`text-xs mt-1 ${isDark ? 'text-yellow-300' : 'text-yellow-700'}`}>
                    当前仅支持直接确认创建 character / lore / location，此草案需后续资源界面处理。
                  </p>
                )}
              </div>
            ))}
          </div>
        )}
      </Card>
    )
  }

  // 情绪曲线可视化
  const renderEmotionCurve = () => {
    if (!currentOutline?.emotion_curve?.points) return null

    const points = currentOutline.emotion_curve.points
    const height = 100
    const width = 300

    return (
      <div className="mt-4">
        <h4 className={`text-sm font-medium mb-2 ${isDark ? 'text-gray-300' : 'text-gray-700'}`}>
          情绪曲线
        </h4>
        <svg width={width} height={height} className="w-full">
          {/* 背景网格 */}
          <line x1="0" y1={height / 2} x2={width} y2={height / 2} stroke={isDark ? '#374151' : '#e5e7eb'} strokeWidth="1" />

          {/* 情绪曲线 */}
          <polyline
            fill="none"
            stroke={isDark ? '#60a5fa' : '#3b82f6'}
            strokeWidth="2"
            points={points.map((p, i) => {
              const x = (p.position * width)
              const y = height - (p.intensity * height * 0.8) - 10
              return `${x},${y}`
            }).join(' ')}
          />

          {/* 数据点 */}
          {points.map((p, i) => {
            const x = (p.position * width)
            const y = height - (p.intensity * height * 0.8) - 10
            const emotionInfo = EMOTION_LABELS[p.emotion] || EMOTION_LABELS.neutral
            return (
              <g key={i}>
                <circle cx={x} cy={y} r="4" className={isDark ? 'fill-blue-400' : 'fill-blue-500'} />
                <text
                  x={x}
                  y={y - 8}
                  textAnchor="middle"
                  className={`text-xs ${emotionInfo.color}`}
                >
                  {emotionInfo.label}
                </text>
              </g>
            )
          })}
        </svg>
      </div>
    )
  }

  return (
    <PageLayout
      title="章节大纲"
      description="与 Plot Outline Agent 协作管理章节大纲"
    >
      <div className="h-full flex">
        {/* 左侧：章节列表 */}
        <div className={`w-64 border-r flex-shrink-0 ${isDark ? 'border-gray-700 bg-gray-800' : 'border-gray-200 bg-white'}`}>
          <div className={`p-4 border-b ${isDark ? 'border-gray-700' : 'border-gray-200'}`}>
            <div className="flex items-center justify-between mb-2">
              <h2 className={`text-lg font-semibold ${isDark ? 'text-white' : 'text-gray-800'}`}>
                章节大纲
              </h2>
              <Button size="sm" onClick={() => {
                const newChapter = chapterNavigationOutlines.length > 0 ? Math.max(...chapterNavigationOutlines.map(o => o.chapter_number)) + 1 : 1
                setSelectedChapter(newChapter)
                setCurrentOutline(null)
                setResourceRequirements([])
                setResourceReadiness(null)
                setResourceDrafts([])
                setOutlineVersions(null)
              }}>
                <Plus className="w-4 h-4" />
              </Button>
            </div>
            <p className={`text-sm ${isDark ? 'text-gray-400' : 'text-gray-500'}`}>
              {currentProject?.name || '未选择项目'}
            </p>
          </div>

          <div className="overflow-y-auto h-[calc(100vh-200px)]">
            {loading && chapterNavigationOutlines.length === 0 ? (
              <div className={`p-4 text-center ${isDark ? 'text-gray-400' : 'text-gray-500'}`}>
                加载中...
              </div>
            ) : chapterNavigationOutlines.length === 0 ? (
              <div className={`p-4 text-center ${isDark ? 'text-gray-400' : 'text-gray-500'}`}>
                <BookOpen className="w-12 h-12 mx-auto mb-2 opacity-50" />
                <p className="text-sm">暂无大纲</p>
                <Button size="sm" className="mt-2" onClick={handleStartFirstChapterChat}>
                  生成第一章
                </Button>
              </div>
            ) : (
              <div className="p-2 space-y-1">
                {chapterNavigationOutlines.map((outline) => {
                  const status = STATUS_CONFIG[outline.status]
                  const isSelected = selectedChapter === outline.chapter_number
                  return (
                    <button
                      key={outline.id}
                      onClick={() => selectChapter(outline.chapter_number)}
                      className={`w-full text-left p-3 rounded-lg transition-colors ${
                        isSelected
                          ? isDark ? 'bg-blue-900 text-blue-100' : 'bg-blue-50 text-blue-900'
                          : isDark ? 'hover:bg-gray-700 text-gray-200' : 'hover:bg-gray-50 text-gray-700'
                      }`}
                    >
                      <div className="flex items-center justify-between">
                        <span className="font-medium text-sm">
                          第{outline.chapter_number}章
                        </span>
                        <span className={`px-2 py-0.5 text-xs rounded ${status.color}`}>
                          {status.label}
                        </span>
                      </div>
                      <p className={`text-xs mt-1 truncate ${isDark ? 'text-gray-400' : 'text-gray-500'}`}>
                        {outline.title}
                      </p>
                      <div className={`flex items-center gap-2 mt-1 text-xs ${isDark ? 'text-gray-500' : 'text-gray-400'}`}>
                        <span>{outline.scenes.length} 场景</span>
                        <span>·</span>
                        <span>{outline.target_word_count} 字</span>
                      </div>
                    </button>
                  )
                })}
              </div>
            )}
          </div>
        </div>

        {/* 中间：大纲详情 */}
        <div className="flex-1 overflow-y-auto">
          {selectedChapter ? (
            currentOutline ? (
              <div className="p-6">
                {/* 头部信息 */}
                <div className="mb-6">
                  <div className="flex items-center justify-between mb-2">
                    <h2 className={`text-2xl font-bold ${isDark ? 'text-white' : 'text-gray-800'}`}>
                      第{currentOutline.chapter_number}章：{currentOutline.title}
                    </h2>
                    <div className="flex items-center gap-2">
                      <span className={`px-3 py-1 text-sm rounded-full ${STATUS_CONFIG[currentOutline.status].color}`}>
                        {STATUS_CONFIG[currentOutline.status].label}
                      </span>
                      {['draft', 'revision'].includes(currentOutline.status) && (
                        <Button size="sm" onClick={handleApprove}>
                          <Check className="w-4 h-4 mr-1" />
                          {currentOutline.status === 'revision' ? '审批修订' : '审批'}
                        </Button>
                      )}
                      {currentOutline.status === 'revision' && (
                        <Button size="sm" variant="secondary" onClick={handleRejectRevision}>
                          <X className="w-4 h-4 mr-1" />
                          拒绝修订
                        </Button>
                      )}
                      <Button size="sm" variant="secondary" onClick={handleDelete}>
                        <Trash2 className="w-4 h-4 mr-1" />
                        删除
                      </Button>
                    </div>
                  </div>
                  <p className={`text-sm ${isDark ? 'text-gray-400' : 'text-gray-600'}`}>
                    {currentOutline.summary}
                  </p>
                  {currentOutline.previous_outline_id && (
                    <p className={`text-xs mt-2 ${isDark ? 'text-orange-300' : 'text-orange-700'}`}>
                      修订来源：{currentOutline.previous_outline_id}
                    </p>
                  )}
                  {currentOutline.next_outline_id && (
                    <p className={`text-xs mt-2 ${isDark ? 'text-green-300' : 'text-green-700'}`}>
                      后续已审批修订：{currentOutline.next_outline_id}
                    </p>
                  )}
                </div>

                {revisionNotice && currentOutline.id === revisionNotice.revisionOutlineId && (
                  <Card className={`p-4 mb-6 border ${isDark ? 'border-orange-800 bg-orange-950/30' : 'border-orange-200 bg-orange-50'}`}>
                    <p className={`text-sm font-medium ${isDark ? 'text-orange-200' : 'text-orange-800'}`}>
                      已创建修订提案
                    </p>
                    <p className={`text-xs mt-1 ${isDark ? 'text-orange-300' : 'text-orange-700'}`}>
                      {revisionNotice.message} 原审批大纲：{revisionNotice.approvedOutlineId}；当前修订：{revisionNotice.revisionOutlineId}。
                    </p>
                  </Card>
                )}

                {renderOutlineVersionPanel()}

                {renderResourceReadinessPanel()}

                {/* 章节目标 */}
                {currentOutline.chapter_goals.length > 0 && (
                  <Card className="p-4 mb-6">
                    <h3 className={`text-sm font-medium mb-2 ${isDark ? 'text-gray-300' : 'text-gray-700'}`}>
                      <Target className="w-4 h-4 inline mr-1" />
                      章节目标
                    </h3>
                    <div className="flex flex-wrap gap-2">
                      {currentOutline.chapter_goals.map((goal, i) => (
                        <span
                          key={i}
                          className={`px-3 py-1 text-sm rounded-full ${
                            isDark ? 'bg-gray-700 text-gray-200' : 'bg-gray-100 text-gray-700'
                          }`}
                        >
                          {goal}
                        </span>
                      ))}
                    </div>
                  </Card>
                )}

                {/* 场景列表 */}
                <Card className="p-4 mb-6">
                  <div className="flex items-center justify-between mb-4">
                    <h3 className={`text-sm font-medium ${isDark ? 'text-gray-300' : 'text-gray-700'}`}>
                      <Play className="w-4 h-4 inline mr-1" />
                      场景规划 ({currentOutline.scenes.length} 场景)
                    </h3>
                    <Button size="sm" variant="secondary" onClick={() => setShowSceneEditor(true)}>
                      <Edit2 className="w-4 h-4 mr-1" />
                      编辑场景
                    </Button>
                  </div>

                  {currentOutline.scenes.length === 0 ? (
                    <div className={`text-center py-8 ${isDark ? 'text-gray-400' : 'text-gray-500'}`}>
                      <p>暂无场景规划</p>
                      <Button size="sm" className="mt-2" onClick={() => openOutlineChat()}>
                        与 Agent 讨论
                      </Button>
                    </div>
                  ) : (
                    <div className="space-y-3">
                      {currentOutline.scenes.map((scene, index) => (
                        <div
                          key={scene.id}
                          className={`p-4 rounded-lg border ${
                            isDark ? 'bg-gray-800 border-gray-700' : 'bg-gray-50 border-gray-200'
                          }`}
                        >
                          <div className="flex items-center justify-between mb-2">
                            <div className="flex items-center gap-2">
                              <span className={`text-xs px-2 py-0.5 rounded ${
                                isDark ? 'bg-blue-900 text-blue-300' : 'bg-blue-100 text-blue-700'
                              }`}>
                                场景 {scene.scene_number}
                              </span>
                              <span className={`font-medium ${isDark ? 'text-gray-200' : 'text-gray-800'}`}>
                                {scene.title}
                              </span>
                            </div>
                            <span className={`text-xs px-2 py-0.5 rounded ${
                              isDark ? 'bg-gray-700 text-gray-300' : 'bg-gray-200 text-gray-600'
                            }`}>
                              {SCENE_TYPE_LABELS[scene.scene_type] || scene.scene_type}
                            </span>
                          </div>

                          <p className={`text-sm mb-2 ${isDark ? 'text-gray-400' : 'text-gray-600'}`}>
                            {scene.summary}
                          </p>

                          <div className="flex items-center gap-4 text-xs">
                            {scene.location && (
                              <span className={`flex items-center gap-1 ${isDark ? 'text-gray-400' : 'text-gray-500'}`}>
                                <MapPin className="w-3 h-3" />
                                {scene.location}
                              </span>
                            )}
                            {scene.time_of_day && (
                              <span className={`flex items-center gap-1 ${isDark ? 'text-gray-400' : 'text-gray-500'}`}>
                                <Clock className="w-3 h-3" />
                                {scene.time_of_day}
                              </span>
                            )}
                            {scene.participating_characters.length > 0 && (
                              <span className={`flex items-center gap-1 ${isDark ? 'text-gray-400' : 'text-gray-500'}`}>
                                <Users className="w-3 h-3" />
                                {scene.participating_characters.length} 角色
                              </span>
                            )}
                            <span className={`flex items-center gap-1 ${isDark ? 'text-gray-400' : 'text-gray-500'}`}>
                              约 {scene.estimated_words} 字
                            </span>
                          </div>

                          {/* 情绪变化 */}
                          <div className="mt-2 flex items-center gap-2">
                            <span className="text-xs">情绪：</span>
                            <span className={`text-xs ${EMOTION_LABELS[scene.emotion_start]?.color || ''}`}>
                              {EMOTION_LABELS[scene.emotion_start]?.label || scene.emotion_start}
                            </span>
                            <span className="text-xs">→</span>
                            <span className={`text-xs ${EMOTION_LABELS[scene.emotion_end]?.color || ''}`}>
                              {EMOTION_LABELS[scene.emotion_end]?.label || scene.emotion_end}
                            </span>
                          </div>

                          {/* 关键事件 */}
                          {scene.key_events.length > 0 && (
                            <div className="mt-2">
                              <p className={`text-xs mb-1 ${isDark ? 'text-gray-500' : 'text-gray-400'}`}>关键事件：</p>
                              <div className="flex flex-wrap gap-1">
                                {scene.key_events.map((event, i) => (
                                  <span
                                    key={i}
                                    className={`text-xs px-2 py-0.5 rounded ${
                                      isDark ? 'bg-gray-700 text-gray-300' : 'bg-gray-200 text-gray-600'
                                    }`}
                                  >
                                    {event}
                                  </span>
                                ))}
                              </div>
                            </div>
                          )}
                        </div>
                      ))}
                    </div>
                  )}
                </Card>

                {/* 情绪曲线 */}
                {currentOutline.emotion_curve && (
                  <Card className="p-4 mb-6">
                    <h3 className={`text-sm font-medium mb-2 ${isDark ? 'text-gray-300' : 'text-gray-700'}`}>
                      <Zap className="w-4 h-4 inline mr-1" />
                      情绪曲线
                    </h3>
                    {renderEmotionCurve()}
                    {currentOutline.emotion_curve.reader_experience_goal && (
                      <p className={`text-sm mt-2 ${isDark ? 'text-gray-400' : 'text-gray-600'}`}>
                        读者体验目标：{currentOutline.emotion_curve.reader_experience_goal}
                      </p>
                    )}
                  </Card>
                )}

                {/* 伏笔管理 */}
                {(currentOutline.hooks_planted.length > 0 || currentOutline.hooks_resolved.length > 0) && (
                  <Card className="p-4 mb-6">
                    <h3 className={`text-sm font-medium mb-2 ${isDark ? 'text-gray-300' : 'text-gray-700'}`}>
                      伏笔管理
                    </h3>
                    <div className="grid grid-cols-2 gap-4">
                      <div>
                        <p className={`text-xs mb-1 ${isDark ? 'text-gray-400' : 'text-gray-500'}`}>埋设伏笔</p>
                        {currentOutline.hooks_planted.length > 0 ? (
                          <ul className={`text-sm ${isDark ? 'text-gray-300' : 'text-gray-700'}`}>
                            {currentOutline.hooks_planted.map((hook, i) => (
                              <li key={i} className="flex items-center gap-1">
                                <span className="w-1.5 h-1.5 rounded-full bg-blue-500" />
                                {hook}
                              </li>
                            ))}
                          </ul>
                        ) : (
                          <p className={`text-sm ${isDark ? 'text-gray-500' : 'text-gray-400'}`}>无</p>
                        )}
                      </div>
                      <div>
                        <p className={`text-xs mb-1 ${isDark ? 'text-gray-400' : 'text-gray-500'}`}>回收伏笔</p>
                        {currentOutline.hooks_resolved.length > 0 ? (
                          <ul className={`text-sm ${isDark ? 'text-gray-300' : 'text-gray-700'}`}>
                            {currentOutline.hooks_resolved.map((hook, i) => (
                              <li key={i} className="flex items-center gap-1">
                                <CheckCircle className="w-3 h-3 text-green-500" />
                                {hook}
                              </li>
                            ))}
                          </ul>
                        ) : (
                          <p className={`text-sm ${isDark ? 'text-gray-500' : 'text-gray-400'}`}>无</p>
                        )}
                      </div>
                    </div>
                  </Card>
                )}

                {/* 底部操作栏 */}
                <div className={`sticky bottom-0 p-4 border-t ${isDark ? 'bg-gray-900 border-gray-700' : 'bg-white border-gray-200'}`}>
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <Button
                        variant="secondary"
                        onClick={() => selectedChapter > 1 && selectChapter(selectedChapter - 1)}
                        disabled={selectedChapter <= 1}
                      >
                        <ChevronLeft className="w-4 h-4" />
                        上一章
                      </Button>
                      <Button
                        variant="secondary"
                        onClick={() => selectChapter(selectedChapter + 1)}
                        disabled={!outlines.find(o => o.chapter_number === selectedChapter + 1)}
                      >
                        下一章
                        <ChevronRight className="w-4 h-4" />
                      </Button>
                    </div>
                    <div className="flex items-center gap-2">
                      <Button variant="secondary" onClick={() => openOutlineChat()}>
                        <MessageSquare className="w-4 h-4 mr-1" />
                        与 Agent 讨论
                      </Button>
                      <Button variant="secondary" onClick={() => {
                        openOutlineChat()
                        setChatInput('请帮我重新生成这一章的大纲')
                      }}>
                        <RefreshCw className="w-4 h-4 mr-1" />
                        重新生成
                      </Button>
                    </div>
                  </div>
                </div>
              </div>
            ) : (
              // 空状态：章节未创建大纲
              <div className="h-full flex items-center justify-center">
                <div className={`text-center max-w-md ${isDark ? 'text-gray-400' : 'text-gray-500'}`}>
                  <BookOpen className="w-16 h-16 mx-auto mb-4 opacity-50" />
                  <h3 className={`text-lg font-medium mb-2 ${isDark ? 'text-gray-200' : 'text-gray-700'}`}>
                    第{selectedChapter}章大纲
                  </h3>
                  <p className="mb-4">该章节尚未生成大纲</p>
                  <div className="flex justify-center gap-2">
                    <Button variant="secondary" onClick={() => openOutlineChat()}>
                      <MessageSquare className="w-4 h-4 mr-1" />
                      与 Agent 讨论
                    </Button>
                    <Button onClick={() => {
                      openOutlineChat()
                      setChatInput(`请帮我生成第${selectedChapter}章的大纲`)
                    }}>
                      <Sparkles className="w-4 h-4 mr-1" />
                      生成大纲
                    </Button>
                  </div>
                </div>
              </div>
            )
          ) : (
            // 未选择章节
            <div className="h-full flex items-center justify-center">
              <div className={`text-center ${isDark ? 'text-gray-400' : 'text-gray-500'}`}>
                <BookOpen className="w-16 h-16 mx-auto mb-4 opacity-50" />
                <p>请选择一个章节查看或创建大纲</p>
              </div>
            </div>
          )}
        </div>

        {bindingRequirement && (
          <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
            <div className={`w-full max-w-lg rounded-lg shadow-xl ${isDark ? 'bg-gray-900 text-gray-100' : 'bg-white text-gray-900'}`}>
              <div className={`p-4 border-b flex items-start justify-between gap-3 ${isDark ? 'border-gray-700' : 'border-gray-200'}`}>
                <div>
                  <h3 className="font-medium">绑定已有资源</h3>
                  <p className={`text-xs mt-1 ${isDark ? 'text-gray-400' : 'text-gray-500'}`}>
                    将“{bindingRequirement.resource_name}”绑定到已有资源，并把该需求标记为 resolved。
                  </p>
                </div>
                <Button variant="ghost" size="sm" onClick={() => setBindingRequirement(null)}>
                  <X className="w-4 h-4" />
                </Button>
              </div>
              <div className="p-4 space-y-3">
                {loadingBindableResources ? (
                  <div className={`flex items-center gap-2 text-sm ${isDark ? 'text-gray-400' : 'text-gray-600'}`}>
                    <Loader2 className="w-4 h-4 animate-spin" />
                    正在加载可绑定资源...
                  </div>
                ) : bindableResources.length === 0 ? (
                  <p className={`text-sm ${isDark ? 'text-gray-400' : 'text-gray-600'}`}>未找到可绑定的已有资源。</p>
                ) : (
                  <select
                    value={selectedBindableResourceId}
                    onChange={event => setSelectedBindableResourceId(event.target.value)}
                    className={`w-full px-3 py-2 rounded border ${isDark ? 'bg-gray-800 border-gray-700 text-gray-100' : 'bg-white border-gray-300 text-gray-900'}`}
                  >
                    <option value="">请选择已有资源</option>
                    {bindableResources.map(resource => (
                      <option key={`${resource.type}:${resource.id}`} value={resource.id}>
                        {resource.name}{resource.subtitle ? ` · ${resource.subtitle}` : ''}
                      </option>
                    ))}
                  </select>
                )}

                {selectedBindableResourceId && (
                  <div className={`p-3 rounded ${isDark ? 'bg-gray-800' : 'bg-gray-50'}`}>
                    {(() => {
                      const selected = bindableResources.find(resource => resource.id === selectedBindableResourceId)
                      if (!selected) return null
                      return (
                        <>
                          <p className="text-sm font-medium">{selected.name}</p>
                          {selected.description && (
                            <p className={`text-xs mt-1 ${isDark ? 'text-gray-400' : 'text-gray-600'}`}>{selected.description.slice(0, 180)}</p>
                          )}
                        </>
                      )
                    })()}
                  </div>
                )}
              </div>
              <div className={`p-4 border-t flex justify-end gap-2 ${isDark ? 'border-gray-700' : 'border-gray-200'}`}>
                <Button variant="secondary" onClick={() => setBindingRequirement(null)}>取消</Button>
                <Button onClick={handleBindExistingResource} disabled={!selectedBindableResourceId || bindingResource}>
                  {bindingResource ? <Loader2 className="w-4 h-4 mr-1 animate-spin" /> : <Check className="w-4 h-4 mr-1" />}
                  确认绑定
                </Button>
              </div>
            </div>
          </div>
        )}

        {/* 右侧：Agent 聊天面板 */}
        {showChat && (
          <div className={`w-96 border-l flex-shrink-0 flex flex-col ${isDark ? 'bg-gray-800 border-gray-700' : 'bg-white border-gray-200'}`}>
            <div className={`p-4 border-b flex items-center justify-between ${isDark ? 'border-gray-700' : 'border-gray-200'}`}>
              <div className="flex items-center gap-2">
                <div className="w-8 h-8 rounded-full bg-gradient-to-r from-purple-500 to-pink-500 flex items-center justify-center">
                  <Sparkles className="w-4 h-4 text-white" />
                </div>
                <div>
                  <h3 className={`font-medium ${isDark ? 'text-white' : 'text-gray-800'}`}>Plot Outline Agent</h3>
                  <p className={`text-xs ${isDark ? 'text-gray-400' : 'text-gray-500'}`}>
                    /outlines 全局大纲会话{selectedChapter ? ` · 当前查看第${selectedChapter}章` : ''}
                  </p>
                </div>
              </div>
              <Button variant="ghost" size="sm" onClick={() => setShowChat(false)}>
                <X className="w-4 h-4" />
              </Button>
            </div>

            {currentProject?.id && (
              <div className={`p-3 border-b ${isDark ? 'border-gray-700' : 'border-gray-200'}`}>
                <AssistantContextControls
                  projectId={currentProject.id}
                  sessionId={assistantSessionId}
                  assistantSurface="plot_outline_agent"
                  mode={outlineAgentMode}
                  scope={{ entry: 'outlines', selected_chapter_number: selectedChapter || 1 }}
                  contextPacket={contextPacket}
                  compact
                  onHistoryReset={(newSessionId) => {
                    setAssistantSessionId(newSessionId)
                    setChatMessages([])
                    localStorage.setItem(getOutlineAgentStorageKey(currentProject.id), newSessionId)
                    localStorage.setItem(getLegacyFirstChapterAgentStorageKey(currentProject.id), newSessionId)
                  }}
                  onRereadComplete={(response) => setContextPacket(response.packet_metadata)}
                />
              </div>
            )}

            <div className={`px-3 py-2 border-b text-xs ${isDark ? 'border-gray-700 text-gray-300' : 'border-gray-200 text-gray-600'}`}>
              <label className="flex items-start gap-2 cursor-pointer">
                <input
                  type="checkbox"
                  className="mt-0.5"
                  checked={outlineChatAutoSave}
                  onChange={(event) => setOutlineChatAutoSave(event.target.checked)}
                />
                <span>
                  自动保存 Agent 输出的大纲 JSON
                  <span className={`block ${isDark ? 'text-gray-500' : 'text-gray-400'}`}>
                    默认关闭时，新生成的大纲仍会保存为草稿并显示在左侧；开启后修改已审批大纲会创建修订提案，不覆盖原审批版本。
                  </span>
                </span>
              </label>
            </div>

            {/* 快捷命令 */}
            <div className={`p-3 border-b ${isDark ? 'border-gray-700' : 'border-gray-200'}`}>
              <p className={`text-xs mb-2 ${isDark ? 'text-gray-400' : 'text-gray-500'}`}>快捷命令</p>
              <div className="flex flex-wrap gap-1">
                {[
                  '生成3个场景',
                  '添加一个高潮场景',
                  '调整情绪曲线',
                  '检查伏笔一致性',
                  '优化场景顺序',
                ].map((cmd) => (
                  <button
                    key={cmd}
                    onClick={() => handleQuickCommand(cmd)}
                    className={`px-2 py-1 text-xs rounded ${
                      isDark ? 'bg-gray-700 text-gray-300 hover:bg-gray-600' : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
                    }`}
                  >
                    {cmd}
                  </button>
                ))}
              </div>
            </div>

            {/* 聊天消息 */}
            <div className="flex-1 overflow-y-auto p-4 space-y-4">
              {chatMessages.length === 0 ? (
                <div className={`text-center py-8 ${isDark ? 'text-gray-400' : 'text-gray-500'}`}>
                  <MessageSquare className="w-8 h-8 mx-auto mb-2 opacity-50" />
                  <p className="text-sm">开始与 Agent 讨论{selectedChapter ? `第${selectedChapter}章` : ''}大纲</p>
                </div>
              ) : (
                chatMessages.map((msg, i) => (
                  <div
                    key={i}
                    className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}
                  >
                    <div
                      className={`max-w-[85%] p-3 rounded-lg ${
                        msg.role === 'user'
                          ? 'bg-blue-500 text-white'
                          : isDark ? 'bg-gray-700 text-gray-200' : 'bg-gray-100 text-gray-800'
                      }`}
                    >
                      <p className="text-sm whitespace-pre-wrap">{msg.content}</p>
                    </div>
                  </div>
                ))
              )}
              {sendingMessage && (
                <div className="flex justify-start">
                  <div className={`p-3 rounded-lg ${isDark ? 'bg-gray-700' : 'bg-gray-100'}`}>
                    <Loader2 className="w-4 h-4 animate-spin" />
                  </div>
                </div>
              )}
            </div>

            {/* 输入框 */}
            <div className={`p-4 border-t ${isDark ? 'border-gray-700' : 'border-gray-200'}`}>
              <div className="flex gap-2">
                <Input
                  value={chatInput}
                  onChange={(e) => setChatInput(e.target.value)}
                  placeholder="描述你想要的大纲..."
                  onKeyDown={(e) => e.key === 'Enter' && !e.shiftKey && handleSendMessage()}
                  className="flex-1"
                />
                <Button onClick={handleSendMessage} disabled={!chatInput.trim() || sendingMessage}>
                  <Send className="w-4 h-4" />
                </Button>
              </div>
            </div>
          </div>
        )}
      </div>
    </PageLayout>
  )
}
