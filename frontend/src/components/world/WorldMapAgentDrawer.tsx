import { useEffect, useMemo, useState } from 'react'
import { Bot, Check, Compass, Loader2, MapPinned, Pencil, Route, Sparkles, Trash2, X } from 'lucide-react'

import {
  generateWorldMapDrafts,
  type CreateRegionDTO,
  type Region,
  type WorldMapAgentDraftRegion,
} from '@/api/worlds'
import { createAssistantSession, getAssistantHistory, type AssistantContextSummary } from '@/api/assistantContext'
import { formatApiErrorMessage } from '@/api/workflows'
import AssistantContextControls from '@/components/assistant/AssistantContextControls'

interface WorldMapAgentDrawerProps {
  open: boolean
  onClose: () => void
  projectId: string
  worldId: string
  worldName?: string
  regions: Region[]
  selectedRegion?: Region | null
  onCreateDraft: (draft: CreateRegionDTO) => Promise<void> | void
  onOpenDraftInEditor: (draft: CreateRegionDTO) => void
  onCreated?: () => Promise<void> | void
}

const promptChips = [
  '根据当前剧情补齐 3 个地点缺口',
  '围绕当前选中区域生成相邻区域',
  '梳理现有区域之间的道路与冲突点',
  '生成一个适合追踪、伏击和转场的地点',
  '补一个能承接下一章冲突的关键场景',
]

const toCreateRegionDTO = (draft: WorldMapAgentDraftRegion): CreateRegionDTO => ({
  name: draft.name,
  region_type: draft.region_type || 'custom',
  terrain_type: draft.terrain_type || 'custom',
  description: draft.description,
  atmosphere: draft.atmosphere,
  coordinates: draft.coordinates || {},
  area_size: draft.area_size || 0,
  terrain_features: draft.terrain_features || [],
  landmarks: draft.landmarks || [],
  encounters: draft.encounters || [],
  connections: draft.connections || [],
  local_rules: draft.local_rules || [],
  is_generated: true,
  visit_count: draft.visit_count || 0,
})

const summarizeItems = (items?: Array<Record<string, unknown>>) =>
  (items || [])
    .map(item => String(item.name || item.title || item.description || '').trim())
    .filter(Boolean)

const createRequestId = () => `world_map_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`

const worldMapAssistantSessionStorageKey = (projectId: string, worldId: string) =>
  `worldMapAssistantSession:${projectId}:${worldId}`

export default function WorldMapAgentDrawer({
  open,
  onClose,
  projectId,
  worldId,
  worldName,
  regions,
  selectedRegion,
  onCreateDraft,
  onOpenDraftInEditor,
  onCreated,
}: WorldMapAgentDrawerProps) {
  const [message, setMessage] = useState('')
  const [generationCount, setGenerationCount] = useState(3)
  const [includeSelectedRegion, setIncludeSelectedRegion] = useState(true)
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [overview, setOverview] = useState('')
  const [drafts, setDrafts] = useState<WorldMapAgentDraftRegion[]>([])
  const [lastRequest, setLastRequest] = useState('')
  const [ignoredDraftIds, setIgnoredDraftIds] = useState<Set<string>>(new Set())
  const [createdDraftIds, setCreatedDraftIds] = useState<Set<string>>(new Set())
  const [creatingDraftId, setCreatingDraftId] = useState<string | null>(null)
  const [assistantSessionId, setAssistantSessionId] = useState<string | null>(null)
  const [contextPacket, setContextPacket] = useState<AssistantContextSummary | null>(null)

  const assistantMode = worldId ? `world:${worldId}` : 'world:none'
  const assistantScope = useMemo(
    () => ({
      world_id: worldId,
      selected_region_id: selectedRegion?.id || null,
      entry: 'world_map',
    }),
    [selectedRegion?.id, worldId],
  )

  const visibleDrafts = useMemo(
    () => drafts.filter(draft => !ignoredDraftIds.has(draft.client_id)),
    [drafts, ignoredDraftIds],
  )

  useEffect(() => {
    if (!open || !projectId || !worldId) {
      setAssistantSessionId(null)
      setContextPacket(null)
      return
    }

    let cancelled = false
    const loadAssistantSession = async () => {
      const storageKey = worldMapAssistantSessionStorageKey(projectId, worldId)
      const storedSessionId = localStorage.getItem(storageKey) || undefined
      try {
        const assistantSession = await createAssistantSession(projectId, {
          assistant_surface: 'world_map_agent',
          mode: assistantMode,
          session_id: storedSessionId,
          scope: assistantScope,
        })
        if (cancelled) return
        setAssistantSessionId(assistantSession.session_id)
        localStorage.setItem(storageKey, assistantSession.session_id)

        const history = await getAssistantHistory(projectId, assistantSession.session_id, 80)
        if (cancelled) return
        if (history.context_packet) setContextPacket(history.context_packet)
      } catch (err) {
        console.error('Failed to load world map assistant session:', err)
      }
    }

    loadAssistantSession()
    return () => {
      cancelled = true
    }
  }, [assistantMode, assistantScope, open, projectId, worldId])

  if (!open) return null

  const handleGenerate = async () => {
    const trimmed = message.trim()
    if (!trimmed || !worldId) return

    setSubmitting(true)
    setError(null)
    try {
      const result = await generateWorldMapDrafts(worldId, {
        project_id: projectId,
        world_id: worldId,
        message: trimmed,
        task: 'create_draft',
        selected_region_id: includeSelectedRegion ? selectedRegion?.id : undefined,
        generation_count: generationCount,
        include_existing_regions: true,
        assistant_session_id: assistantSessionId || undefined,
        request_id: createRequestId(),
      })
      if (result.assistant_session_id) {
        setAssistantSessionId(result.assistant_session_id)
        localStorage.setItem(worldMapAssistantSessionStorageKey(projectId, worldId), result.assistant_session_id)
      }
      if (result.context_packet) setContextPacket(result.context_packet)
      setOverview(result.overview || result.message || '')
      setDrafts(result.draft_regions || [])
      setIgnoredDraftIds(new Set())
      setCreatedDraftIds(new Set())
      setLastRequest(trimmed)
    } catch (err) {
      setError(formatApiErrorMessage(err, '地图 Agent 生成失败'))
    } finally {
      setSubmitting(false)
    }
  }

  const handleDirectCreate = async (draft: WorldMapAgentDraftRegion) => {
    setCreatingDraftId(draft.client_id)
    setError(null)
    try {
      await onCreateDraft(toCreateRegionDTO(draft))
      setCreatedDraftIds(prev => new Set([...prev, draft.client_id]))
      await onCreated?.()
    } catch (err) {
      setError(formatApiErrorMessage(err, '创建区域失败'))
    } finally {
      setCreatingDraftId(null)
    }
  }

  const handleIgnore = (draftId: string) => {
    setIgnoredDraftIds(prev => new Set([...prev, draftId]))
  }

  return (
    <div className="fixed inset-0 z-[80] flex justify-end bg-slate-950/30 backdrop-blur-[2px]">
      <button className="flex-1 cursor-default" onClick={onClose} aria-label="关闭地图 Agent 抽屉" />
      <aside className="h-full w-full max-w-[520px] overflow-hidden border-l border-amber-200 bg-[#fbf4e4] shadow-2xl">
        <div className="flex h-full flex-col">
          <header className="border-b border-amber-200 bg-gradient-to-br from-[#3a2a18] via-[#4a321b] to-[#7a4a1c] px-5 py-4 text-amber-50">
            <div className="flex items-start justify-between gap-4">
              <div>
                <div className="flex items-center gap-2 text-xs uppercase tracking-[0.28em] text-amber-200">
                  <Compass className="h-4 w-4" /> Cartographer Desk
                </div>
                <h2 className="mt-2 text-2xl font-bold">地图 Agent</h2>
                <p className="mt-1 text-sm text-amber-100/85">
                  {worldName || '未命名世界'} · {regions.length} 个现有区域 · 草稿需确认后才会入库
                </p>
              </div>
              <button onClick={onClose} className="rounded-full p-2 text-amber-100 hover:bg-white/10" aria-label="关闭">
                <X className="h-5 w-5" />
              </button>
            </div>
          </header>

          <div className="flex-1 overflow-y-auto px-5 py-4">
            {!worldId ? (
              <div className="rounded-2xl border border-dashed border-amber-300 bg-white/60 p-6 text-center text-sm text-stone-600">
                请先选择或创建一个世界，再让地图 Agent 生成区域草稿。
              </div>
            ) : (
              <div className="space-y-4">
                <AssistantContextControls
                  projectId={projectId}
                  sessionId={assistantSessionId}
                  assistantSurface="world_map_agent"
                  mode={assistantMode}
                  scope={assistantScope}
                  contextPacket={contextPacket}
                  compact
                  onHistoryReset={(newSessionId) => {
                    setAssistantSessionId(newSessionId)
                    setContextPacket(null)
                    setOverview('')
                    setDrafts([])
                    setLastRequest('')
                    setIgnoredDraftIds(new Set())
                    setCreatedDraftIds(new Set())
                    localStorage.setItem(worldMapAssistantSessionStorageKey(projectId, worldId), newSessionId)
                  }}
                  onRereadComplete={(response) => setContextPacket(response.packet_metadata)}
                />

                <section className="rounded-2xl border border-amber-200 bg-white/70 p-4 shadow-sm">
                  <div className="mb-3 flex items-center justify-between gap-3">
                    <div className="flex items-center gap-2 text-sm font-semibold text-stone-800">
                      <Bot className="h-4 w-4 text-amber-700" /> 勘测需求
                    </div>
                    {selectedRegion && (
                      <label className="flex items-center gap-2 text-xs text-stone-600">
                        <input
                          type="checkbox"
                          checked={includeSelectedRegion}
                          onChange={event => setIncludeSelectedRegion(event.target.checked)}
                        />
                        参考「{selectedRegion.name}」
                      </label>
                    )}
                  </div>
                  <div className="mb-3 flex flex-wrap gap-2">
                    {promptChips.map(chip => (
                      <button
                        key={chip}
                        onClick={() => setMessage(chip)}
                        className="rounded-full border border-amber-200 bg-amber-50 px-3 py-1 text-xs text-amber-900 hover:bg-amber-100"
                      >
                        {chip}
                      </button>
                    ))}
                  </div>
                  <textarea
                    value={message}
                    onChange={event => setMessage(event.target.value)}
                    placeholder="例如：围绕旧车站生成三个能承接追踪戏的地点，其中一个要能连接主角藏身处。"
                    className="min-h-[120px] w-full rounded-xl border border-amber-200 bg-[#fffaf0] px-3 py-3 text-sm text-stone-800 outline-none focus:border-amber-500 focus:ring-2 focus:ring-amber-200"
                  />
                  <div className="mt-3 flex items-center justify-between gap-3">
                    <label className="flex items-center gap-2 text-sm text-stone-600">
                      生成数量
                      <select
                        value={generationCount}
                        onChange={event => setGenerationCount(Number(event.target.value))}
                        className="rounded-lg border border-amber-200 bg-white px-2 py-1"
                      >
                        {[1, 2, 3, 5, 8].map(value => <option key={value} value={value}>{value}</option>)}
                      </select>
                    </label>
                    <button
                      onClick={handleGenerate}
                      disabled={submitting || message.trim().length < 2}
                      className="inline-flex items-center gap-2 rounded-xl bg-stone-900 px-4 py-2 text-sm font-semibold text-amber-50 shadow hover:bg-stone-800 disabled:cursor-not-allowed disabled:bg-stone-400"
                    >
                      {submitting ? <Loader2 className="h-4 w-4 animate-spin" /> : <Sparkles className="h-4 w-4" />}
                      生成提案
                    </button>
                  </div>
                </section>

                {error && <div className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">{error}</div>}

                {(overview || lastRequest) && (
                  <section className="rounded-2xl border border-stone-200 bg-[#fffdf7] p-4 shadow-sm">
                    <div className="flex items-center gap-2 text-sm font-semibold text-stone-800">
                      <MapPinned className="h-4 w-4 text-amber-700" /> 勘测报告
                    </div>
                    {lastRequest && <p className="mt-2 text-xs text-stone-500">用户需求：{lastRequest}</p>}
                    {overview && <p className="mt-2 whitespace-pre-wrap text-sm leading-6 text-stone-700">{overview}</p>}
                  </section>
                )}

                {visibleDrafts.length === 0 && !submitting ? (
                  <div className="rounded-2xl border border-dashed border-amber-300 bg-white/50 p-6 text-center text-sm text-stone-500">
                    暂无区域草稿。描述剧情或地理需求后，地图 Agent 会生成可编辑提案。
                  </div>
                ) : (
                  <div className="space-y-3">
                    {visibleDrafts.map(draft => {
                      const features = summarizeItems(draft.terrain_features)
                      const landmarks = summarizeItems(draft.landmarks)
                      const isCreated = createdDraftIds.has(draft.client_id)
                      return (
                        <article key={draft.client_id} className="rounded-2xl border border-amber-200 bg-[#fffdf7] p-4 shadow-sm">
                          <div className="flex items-start justify-between gap-3">
                            <div>
                              <h3 className="text-lg font-bold text-stone-900">{draft.name}</h3>
                              <div className="mt-1 flex flex-wrap gap-2 text-xs">
                                <span className="rounded-full bg-stone-900 px-2 py-1 text-amber-50">{draft.region_type || 'custom'}</span>
                                <span className="rounded-full bg-amber-100 px-2 py-1 text-amber-900">{draft.terrain_type || 'custom'}</span>
                              </div>
                            </div>
                            {isCreated && <span className="inline-flex items-center gap-1 rounded-full bg-emerald-100 px-2 py-1 text-xs text-emerald-700"><Check className="h-3 w-3" /> 已创建</span>}
                          </div>
                          {draft.description && <p className="mt-3 whitespace-pre-wrap text-sm leading-6 text-stone-700">{draft.description}</p>}
                          {draft.atmosphere && <p className="mt-2 text-sm text-stone-600"><span className="font-medium">氛围：</span>{draft.atmosphere}</p>}
                          {draft.importance && <p className="mt-2 text-sm text-amber-800"><span className="font-medium">剧情用途：</span>{draft.importance}</p>}
                          {(features.length > 0 || landmarks.length > 0) && (
                            <div className="mt-3 grid gap-2 text-xs text-stone-600 sm:grid-cols-2">
                              <div><span className="font-semibold">地形特征：</span>{features.length ? features.join('、') : '—'}</div>
                              <div><span className="font-semibold">地标：</span>{landmarks.length ? landmarks.join('、') : '—'}</div>
                            </div>
                          )}
                          {(draft.connections || []).length > 0 && (
                            <div className="mt-3 flex items-center gap-2 text-xs text-stone-600">
                              <Route className="h-4 w-4" />
                              {(draft.connections || []).map(id => regions.find(region => region.id === id)?.name || id).join('、')}
                            </div>
                          )}
                          {(draft.validation_warnings || []).length > 0 && (
                            <div className="mt-3 rounded-xl border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-900">
                              {draft.validation_warnings?.map(item => <div key={item}>• {item}</div>)}
                            </div>
                          )}
                          <div className="mt-4 flex flex-wrap justify-end gap-2">
                            <button
                              onClick={() => handleIgnore(draft.client_id)}
                              className="inline-flex items-center gap-1 rounded-lg px-3 py-2 text-sm text-stone-500 hover:bg-stone-100"
                            >
                              <Trash2 className="h-4 w-4" /> 忽略
                            </button>
                            <button
                              onClick={() => onOpenDraftInEditor(toCreateRegionDTO(draft))}
                              className="inline-flex items-center gap-1 rounded-lg border border-amber-300 bg-white px-3 py-2 text-sm font-medium text-amber-900 hover:bg-amber-50"
                            >
                              <Pencil className="h-4 w-4" /> 编辑后创建
                            </button>
                            <button
                              onClick={() => handleDirectCreate(draft)}
                              disabled={isCreated || creatingDraftId === draft.client_id}
                              className="inline-flex items-center gap-1 rounded-lg bg-blue-600 px-3 py-2 text-sm font-semibold text-white hover:bg-blue-700 disabled:bg-blue-300"
                            >
                              {creatingDraftId === draft.client_id ? <Loader2 className="h-4 w-4 animate-spin" /> : <Check className="h-4 w-4" />}
                              直接创建
                            </button>
                          </div>
                        </article>
                      )
                    })}
                  </div>
                )}
              </div>
            )}
          </div>
        </div>
      </aside>
    </div>
  )
}
