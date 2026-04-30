import { CharacterImportanceTier, type Character } from '@/api/characters'
import type { Region, World } from '@/api/worlds'

export interface Point3D {
  x: number
  y: number
  z: number
}

export interface WorldSceneNode {
  id: string
  world: World
  position: Point3D
  radius: number
  color: string
  depth: number
  childCount: number
  regions: Region[]
  characterCount: number
}

export interface WorldSceneEdge {
  source: string
  target: string
}

export interface RegionSceneNode {
  id: string
  region: Region
  worldId: string
  position: Point3D
  radius: number
  color: string
  characters: Character[]
}

export interface RegionSceneEdge {
  source: string
  target: string
}

export interface WorldScene {
  worlds: WorldSceneNode[]
  worldEdges: WorldSceneEdge[]
  regions: RegionSceneNode[]
  regionEdges: RegionSceneEdge[]
}

export type RelationshipType = 'friendship' | 'enemy' | 'rivalry' | 'romance' | 'family' | 'mentorship' | 'relationship'
export type CharacterVisualType = 'main' | 'core' | 'antagonist' | 'supporting' | 'npc'

export interface RelationshipGraphNode {
  id: string
  character: Character
  position: Point3D
  radius: number
  color: string
  visualType: CharacterVisualType
  degree: number
}

export interface RelationshipGraphEdge {
  id: string
  source: string
  target: string
  label: string
  type: RelationshipType
  strength: number
}

export interface CharacterRelationshipScene {
  nodes: RelationshipGraphNode[]
  edges: RelationshipGraphEdge[]
}

const importanceOrder: Record<string, number> = {
  [CharacterImportanceTier.PROTAGONIST]: 10,
  [CharacterImportanceTier.CO_PROTAGONIST]: 20,
  [CharacterImportanceTier.DEUTERAGONIST]: 30,
  [CharacterImportanceTier.MENTOR]: 40,
  [CharacterImportanceTier.LOVE_INTEREST]: 50,
  [CharacterImportanceTier.BEST_FRIEND]: 60,
  [CharacterImportanceTier.ARCHENEMY]: 70,
  [CharacterImportanceTier.MAJOR_ALLY]: 80,
  [CharacterImportanceTier.MAJOR_ANTAGONIST]: 90,
  [CharacterImportanceTier.RIVAL]: 100,
  [CharacterImportanceTier.FAMILY_MEMBER]: 110,
  [CharacterImportanceTier.GUARDIAN]: 120,
  [CharacterImportanceTier.ARC_ANTAGONIST]: 130,
  [CharacterImportanceTier.ARC_ALLY]: 140,
  [CharacterImportanceTier.RECURRING]: 150,
  [CharacterImportanceTier.CATALYST]: 160,
  [CharacterImportanceTier.MYSTERY_FIGURE]: 170,
  [CharacterImportanceTier.MINION]: 180,
  [CharacterImportanceTier.INFORMANT]: 190,
  [CharacterImportanceTier.MENTOR_FIGURE]: 200,
  [CharacterImportanceTier.COMIC_RELIEF]: 210,
  [CharacterImportanceTier.VICTIM]: 220,
  [CharacterImportanceTier.NPC]: 230,
  [CharacterImportanceTier.BACKGROUND]: 240,
  [CharacterImportanceTier.CAMEO]: 250,
}

const worldScopeColors: Record<string, string> = {
  root: '#60a5fa',
  plane: '#a78bfa',
  arc_world: '#f472b6',
  instance: '#34d399',
  region_world: '#f59e0b',
}

const terrainColors: Record<string, string> = {
  mountain: '#94a3b8',
  forest: '#22c55e',
  city: '#60a5fa',
  desert: '#f59e0b',
  water: '#38bdf8',
  ocean: '#0ea5e9',
  dungeon: '#8b5cf6',
  plain: '#84cc16',
  ruins: '#a855f7',
}

export function sortCharactersByGraphImportance(characters: Character[]) {
  return [...characters].sort((a, b) => {
    const aTier = importanceOrder[a.importance_tier || CharacterImportanceTier.NPC] ?? 999
    const bTier = importanceOrder[b.importance_tier || CharacterImportanceTier.NPC] ?? 999
    if (aTier !== bTier) return aTier - bTier

    const aPriority = a.plot_priority ?? 0
    const bPriority = b.plot_priority ?? 0
    if (aPriority !== bPriority) return bPriority - aPriority

    return a.name.localeCompare(b.name, 'zh-CN')
  })
}

export function getCharacterVisualType(character: Character): CharacterVisualType {
  const tier = character.importance_tier
  const role = `${character.role || ''} ${tier || ''}`.toLowerCase()

  if (tier === CharacterImportanceTier.PROTAGONIST || tier === CharacterImportanceTier.CO_PROTAGONIST) return 'main'
  if (
    tier === CharacterImportanceTier.ARCHENEMY ||
    tier === CharacterImportanceTier.MAJOR_ANTAGONIST ||
    tier === CharacterImportanceTier.ARC_ANTAGONIST ||
    role.includes('antagonist') ||
    role.includes('villain') ||
    role.includes('反派')
  ) return 'antagonist'
  if (
    tier === CharacterImportanceTier.DEUTERAGONIST ||
    tier === CharacterImportanceTier.MENTOR ||
    tier === CharacterImportanceTier.LOVE_INTEREST ||
    tier === CharacterImportanceTier.BEST_FRIEND ||
    tier === CharacterImportanceTier.MAJOR_ALLY
  ) return 'core'
  if (
    tier === CharacterImportanceTier.NPC ||
    tier === CharacterImportanceTier.BACKGROUND ||
    tier === CharacterImportanceTier.CAMEO
  ) return 'npc'
  return 'supporting'
}

export function classifyRelationship(label: string): RelationshipType {
  const text = label.toLowerCase()
  if (/友|盟|挚|friend|ally|companion/.test(text)) return 'friendship'
  if (/敌|仇|宿敌|enemy|foe|hostile|villain/.test(text)) return 'enemy'
  if (/竞争|对手|rival/.test(text)) return 'rivalry'
  if (/恋|爱|伴侣|love|romance|partner/.test(text)) return 'romance'
  if (/父|母|兄|弟|姐|妹|家人|family|sibling|parent/.test(text)) return 'family'
  if (/师|导师|mentor|teacher|guide/.test(text)) return 'mentorship'
  return 'relationship'
}

function relationshipStrength(label: string, base: number) {
  const text = label.toLowerCase()
  let strength = base
  if (/挚|宿|深|强|重要|至亲|死敌|best|arch|deep|strong|major/.test(text)) strength += 0.2
  if (/弱|曾经|普通|minor|weak/.test(text)) strength -= 0.15
  return Math.max(0.25, Math.min(1, strength))
}

function resolveCharacterReference(ref: string, characters: Character[]) {
  const normalized = ref.trim().toLowerCase()
  return characters.find((character) => character.id === ref)
    || characters.find((character) => character.name === ref)
    || characters.find((character) => character.name.toLowerCase() === normalized)
}

function findMentionedCharacter(text: string, sourceId: string, characters: Character[]) {
  return characters.find((character) => {
    const id = character.id || character.name
    return id !== sourceId && character.name && text.includes(character.name)
  })
}

function includeCharacterForWorld(character: Character, worldId?: string) {
  if (!worldId) return true
  return !character.world_id || character.world_id === worldId
}

function characterColor(type: CharacterVisualType) {
  switch (type) {
    case 'main': return '#facc15'
    case 'core': return '#38bdf8'
    case 'antagonist': return '#fb7185'
    case 'npc': return '#94a3b8'
    default: return '#34d399'
  }
}

export function buildCharacterRelationshipScene(characters: Character[], worldId?: string): CharacterRelationshipScene {
  const scopedCharacters = sortCharactersByGraphImportance(characters.filter((character) => includeCharacterForWorld(character, worldId)))
  const ids = new Set(scopedCharacters.map((character) => character.id || character.name))
  const edgesByKey = new Map<string, RelationshipGraphEdge>()

  scopedCharacters.forEach((character) => {
    const source = character.id || character.name

    Object.entries(character.key_relationships || {}).forEach(([targetRef, label]) => {
      const target = resolveCharacterReference(targetRef, scopedCharacters)
      const targetId = target?.id || target?.name
      if (!targetId || targetId === source || !ids.has(targetId)) return
      const normalizedPair = [source, targetId].sort().join('|')
      const key = `${normalizedPair}|${label}`
      if (edgesByKey.has(key)) return
      edgesByKey.set(key, {
        id: key,
        source,
        target: targetId,
        label: label || '关系',
        type: classifyRelationship(label || ''),
        strength: relationshipStrength(label || '', 0.75),
      })
    })

    ;(character.relationships || []).forEach((relationship, index) => {
      const target = resolveCharacterReference(relationship, scopedCharacters) || findMentionedCharacter(relationship, source, scopedCharacters)
      const targetId = target?.id || target?.name
      if (!targetId || targetId === source || !ids.has(targetId)) return
      const normalizedPair = [source, targetId].sort().join('|')
      const key = `${normalizedPair}|${relationship || index}`
      if (edgesByKey.has(key)) return
      edgesByKey.set(key, {
        id: key,
        source,
        target: targetId,
        label: relationship || '关系',
        type: classifyRelationship(relationship || ''),
        strength: relationshipStrength(relationship || '', 0.5),
      })
    })
  })

  const edges = Array.from(edgesByKey.values())
  const degree = new Map<string, number>()
  edges.forEach((edge) => {
    degree.set(edge.source, (degree.get(edge.source) || 0) + 1)
    degree.set(edge.target, (degree.get(edge.target) || 0) + 1)
  })

  const nodes = scopedCharacters.map((character, index) => {
    const id = character.id || character.name
    const visualType = getCharacterVisualType(character)
    const nodeDegree = degree.get(id) || 0
    const ring = Math.floor(index / 6) + 1
    const angle = index * 2.399963229728653
    const centerBias = visualType === 'main' ? 0.75 : visualType === 'core' ? 0.92 : 1.1
    const radius = 150 + ring * 78 * centerBias + Math.max(0, 4 - nodeDegree) * 16
    const height = (index % 7 - 3) * 72 + nodeDegree * 12

    return {
      id,
      character,
      position: {
        x: Math.cos(angle) * radius,
        y: Math.sin(angle) * radius,
        z: height,
      },
      radius: 6 + Math.min(8, nodeDegree * 1.1) + Math.max(0, character.plot_priority || 0) * 0.45,
      color: characterColor(visualType),
      visualType,
      degree: nodeDegree,
    }
  })

  return { nodes, edges }
}

function worldDepth(world: World, worldById: Map<string, World>) {
  let depth = 0
  let current = world
  const visited = new Set<string>()
  while (current.parent_world_id && !visited.has(current.parent_world_id)) {
    visited.add(current.parent_world_id)
    const parent = worldById.get(current.parent_world_id)
    if (!parent) break
    depth += 1
    current = parent
  }
  return depth
}

function terrainColor(region: Region) {
  const terrain = `${region.terrain_type || region.region_type || ''}`.toLowerCase()
  return Object.entries(terrainColors).find(([key]) => terrain.includes(key))?.[1] || '#22d3ee'
}

function terrainHeight(region: Region) {
  const terrain = `${region.terrain_type || region.region_type || ''}`.toLowerCase()
  if (/mountain|山|高原|峰/.test(terrain)) return 48
  if (/city|城|building|tower|宫/.test(terrain)) return 32
  if (/forest|林|wood/.test(terrain)) return 22
  if (/water|ocean|river|海|水|湖/.test(terrain)) return -8
  if (/dungeon|地下|洞|ruin|遗迹/.test(terrain)) return -18
  return 12
}

export function buildWorldScene(
  worlds: World[],
  regionsByWorldId: Record<string, Region[]>,
  characters: Character[],
  selectedWorldId?: string,
): WorldScene {
  const worldById = new Map(worlds.filter((world) => world.id).map((world) => [world.id as string, world]))
  const childrenByParent = new Map<string, World[]>()
  worlds.forEach((world) => {
    const parentId = world.parent_world_id || '__root__'
    childrenByParent.set(parentId, [...(childrenByParent.get(parentId) || []), world])
  })

  const sortedWorlds = [...worlds].sort((a, b) => {
    const aDepth = worldDepth(a, worldById)
    const bDepth = worldDepth(b, worldById)
    if (aDepth !== bDepth) return aDepth - bDepth
    return (a.order_index || 0) - (b.order_index || 0) || a.name.localeCompare(b.name, 'zh-CN')
  })

  const worldNodes = sortedWorlds.map((world, index) => {
    const id = world.id || world.name
    const depth = worldDepth(world, worldById)
    const siblings = childrenByParent.get(world.parent_world_id || '__root__') || []
    const siblingIndex = Math.max(0, siblings.findIndex((item) => (item.id || item.name) === id))
    const angle = siblingIndex * ((Math.PI * 2) / Math.max(1, siblings.length)) + depth * 0.35
    const distance = depth === 0 ? 0 : 150 + depth * 82
    const regions = regionsByWorldId[id] || []
    const characterCount = characters.filter((character) => character.world_id === id || (!character.world_id && world.id === selectedWorldId)).length

    return {
      id,
      world,
      position: {
        x: Math.cos(angle) * distance + (depth === 0 ? (index - sortedWorlds.length / 2) * 18 : 0),
        y: Math.sin(angle) * distance,
        z: depth * 55,
      },
      radius: (world.is_default ? 34 : 26) + Math.min(18, regions.length * 2),
      color: worldScopeColors[world.scope_type || 'root'] || '#60a5fa',
      depth,
      childCount: childrenByParent.get(id)?.length || 0,
      regions,
      characterCount,
    }
  })

  const worldEdges = sortedWorlds
    .filter((world) => world.id && world.parent_world_id && worldById.has(world.parent_world_id))
    .map((world) => ({ source: world.parent_world_id as string, target: world.id as string }))

  const activeWorldId = selectedWorldId || worldNodes[0]?.id
  const activeRegions = regionsByWorldId[activeWorldId || ''] || []
  const activeCharacters = characters.filter((character) => !character.world_id || character.world_id === activeWorldId)
  const regionCharacters = new Map<string, Character[]>()
  activeCharacters.forEach((character) => {
    if (!character.current_region_id) return
    regionCharacters.set(character.current_region_id, [...(regionCharacters.get(character.current_region_id) || []), character])
  })

  const regionNodes = activeRegions.map((region, index) => {
    const id = region.id || region.name
    const angle = index * ((Math.PI * 2) / Math.max(1, activeRegions.length))
    const fallbackRadius = 118 + Math.floor(index / 8) * 46
    const x = typeof region.coordinates?.x === 'number' ? region.coordinates.x : Math.cos(angle) * fallbackRadius
    const y = typeof region.coordinates?.y === 'number' ? region.coordinates.y : Math.sin(angle) * fallbackRadius
    const scale = Math.max(0.5, Math.min(2.2, activeRegions.some((item) => typeof item.coordinates?.x === 'number') ? 0.8 : 1))

    return {
      id,
      region,
      worldId: activeWorldId || '',
      position: {
        x: x * scale,
        y: y * scale,
        z: terrainHeight(region),
      },
      radius: 12 + Math.min(18, (region.area_size || 1) * 2),
      color: terrainColor(region),
      characters: regionCharacters.get(id) || [],
    }
  })

  const regionIds = new Set(regionNodes.map((node) => node.id))
  const regionEdges: RegionSceneEdge[] = []
  activeRegions.forEach((region) => {
    const source = region.id || region.name
    ;(region.connections || []).forEach((target) => {
      if (!regionIds.has(target)) return
      regionEdges.push({ source, target })
    })
  })

  return { worlds: worldNodes, worldEdges, regions: regionNodes, regionEdges }
}
