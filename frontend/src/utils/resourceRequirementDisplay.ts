type RequirementLike = {
  id?: string
  requirement_type?: string
  original_resource_type?: string
  resource_type?: string
  matched_resource_id?: string | null
  matched_resource_type?: string | null
  resource_name?: string
  status?: string
  suggested_payload?: Record<string, any>
  draft_payload?: Record<string, any>
  metadata?: Record<string, any>
  resolved_at?: string | null
}

const REQUIREMENT_TYPE_LABELS: Record<string, string> = {
  character: '角色',
  role: '角色',
  '角色': '角色',
  '人物': '角色',
  lore: '设定',
  setting: '设定',
  '设定': '设定',
  faction: '势力',
  '势力': '势力',
  organization: '组织',
  '组织': '组织',
  location: '地点',
  place: '地点',
  '地点': '地点',
  '场景地点': '地点',
  item: '道具',
  '道具': '道具',
  ability: '能力',
  '能力': '能力',
  relationship: '关系变化',
  '关系': '关系变化',
  '关系变化': '关系变化',
  character_state: '角色状态',
  '角色状态': '角色状态',
  continuity: '连续性',
  '连续性': '连续性',
  event_rule: '事件规则',
  '事件规则': '事件规则',
  crisis_resolution: '危机解法',
  '危机解法': '危机解法',
  crisis: '危机',
  '危机': '危机',
  hook: '伏笔',
  foreshadowing: '伏笔',
  plot_hook: '伏笔',
  '伏笔': '伏笔',
}

const TARGET_TYPE_BY_REQUIREMENT: Record<string, string> = {
  character: 'character',
  role: 'character',
  '角色': 'character',
  '人物': 'character',
  lore: 'lore',
  setting: 'lore',
  '设定': 'lore',
  faction: 'lore',
  '势力': 'lore',
  organization: 'lore',
  '组织': 'lore',
  location: 'location',
  place: 'location',
  '地点': 'location',
  '场景地点': 'location',
  item: 'lore',
  '道具': 'lore',
  ability: 'lore',
  '能力': 'lore',
  relationship: 'lore',
  '关系': 'lore',
  '关系变化': 'lore',
  character_state: 'lore',
  '角色状态': 'lore',
  continuity: 'lore',
  '连续性': 'lore',
  event_rule: 'lore',
  '事件规则': 'lore',
  crisis_resolution: 'lore',
  '危机解法': 'lore',
  crisis: 'lore',
  '危机': 'lore',
  hook: 'hook',
  foreshadowing: 'hook',
  plot_hook: 'hook',
  '伏笔': 'hook',
}

const RESOLUTION_METHOD_LABELS: Record<string, string> = {
  bind_existing: '已绑定资源',
  create_resource: '已创建补全资源',
  manual_resolved: '人工标记解决',
  ignored: '已忽略',
}

const CLOSED_REQUIREMENT_STATUSES = new Set(['resolved', 'ignored', 'superseded'])

export function normalizeRequirementType(value?: unknown) {
  return String(value || '').trim().toLowerCase()
}

export function getRequirementTypeLabel(type?: unknown) {
  const normalized = normalizeRequirementType(type)
  if (!normalized) return '未知类型'
  return REQUIREMENT_TYPE_LABELS[normalized] || String(type)
}

export function getRequirementOriginalType(item?: RequirementLike | null) {
  if (!item) return ''
  return normalizeRequirementType(
    item.requirement_type ||
    item.original_resource_type ||
    item.draft_payload?.original_resource_type ||
    item.suggested_payload?.original_resource_type ||
    item.metadata?.original_resource_type ||
    item.resource_type,
  )
}

export function getRequirementTargetType(item?: RequirementLike | null) {
  if (!item) return ''
  const original = getRequirementOriginalType(item)
  if (original) return TARGET_TYPE_BY_REQUIREMENT[original] || original
  const explicit = normalizeRequirementType(item.resource_type || item.matched_resource_type)
  return TARGET_TYPE_BY_REQUIREMENT[explicit] || explicit || 'lore'
}

export function formatRequirementTypeFlow(item?: RequirementLike | null) {
  const original = getRequirementOriginalType(item)
  const target = getRequirementTargetType(item)
  const originalLabel = getRequirementTypeLabel(original)
  const targetLabel = getRequirementTypeLabel(target)
  if (!original || original === target || originalLabel === targetLabel) return originalLabel
  return `${originalLabel} → ${targetLabel}`
}

export function formatRequirementSummary(item?: RequirementLike | null) {
  if (!item) return '未知资源需求'
  const name = item.resource_name || item.draft_payload?.name || item.draft_payload?.title || item.id || '未命名资源'
  return `${getRequirementTypeLabel(getRequirementOriginalType(item))} · ${name}`
}

export function getRequirementRecoveryPath(item?: RequirementLike | null) {
  const targetType = getRequirementTargetType(item)
  const basePath = targetType === 'character'
    ? '/characters'
    : targetType === 'location'
      ? '/world-map'
      : targetType === 'hook'
        ? '/hooks'
        : '/lore'
  const requirementId = String(item?.id || '').trim()
  if (!requirementId) return basePath
  const params = new URLSearchParams({ requirement_id: requirementId, action: 'create' })
  return `${basePath}?${params.toString()}`
}

export function getRequirementRecoveryActionLabel(item?: RequirementLike | null) {
  const targetType = getRequirementTargetType(item)
  if (targetType === 'character') return '去角色库补齐'
  if (targetType === 'location') return '去世界地图补齐'
  if (targetType === 'hook') return '去伏笔库补齐'
  return '去设定库补齐'
}

export function formatRequirementList(items: RequirementLike[], limit = 5) {
  const names = items
    .slice(0, limit)
    .map(formatRequirementSummary)
    .filter(Boolean)
    .join('、')
  return items.length > limit ? `${names} 等 ${items.length} 项` : names
}

export function isRequirementClosed(item?: RequirementLike | null) {
  return CLOSED_REQUIREMENT_STATUSES.has(normalizeRequirementType(item?.status))
}

export function getRequirementResolutionMethod(item?: RequirementLike | null) {
  if (!item) return ''
  const metadataMethod = normalizeRequirementType(item.metadata?.resolution_method)
  if (metadataMethod) return metadataMethod
  const status = normalizeRequirementType(item.status)
  if (status === 'resolved' && item.matched_resource_id) return 'bind_existing'
  if (status === 'resolved') return 'manual_resolved'
  if (status === 'ignored') return 'ignored'
  return ''
}

export function getRequirementResolutionMethodLabel(item?: RequirementLike | null) {
  const method = getRequirementResolutionMethod(item)
  if (method) return RESOLUTION_METHOD_LABELS[method] || method
  if (normalizeRequirementType(item?.status) === 'superseded') return '已过期'
  return isRequirementClosed(item) ? '已关闭' : ''
}

export function getRequirementResolutionTimestamp(item?: RequirementLike | null) {
  if (!item) return ''
  return String(item.metadata?.resolution_recorded_at || item.resolved_at || '').trim()
}

export function formatRequirementResolutionResult(item?: RequirementLike | null) {
  if (!item || !isRequirementClosed(item)) return ''
  const parts = [getRequirementResolutionMethodLabel(item)].filter(Boolean)
  const resourceType = normalizeRequirementType(item.metadata?.resolved_with_resource_type || item.matched_resource_type)
  if (resourceType) parts.push(`资源类型：${getRequirementTypeLabel(resourceType)}`)
  if (item.matched_resource_id) parts.push(`资源ID：${item.matched_resource_id}`)
  const timestamp = getRequirementResolutionTimestamp(item)
  if (timestamp) parts.push(`时间：${timestamp}`)
  return parts.join(' · ')
}
