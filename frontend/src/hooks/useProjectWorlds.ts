import { useCallback, useEffect, useMemo, useState } from 'react'
import { getWorlds, type World } from '@/api/worlds'

const getStorageKey = (projectId: string) => `currentWorldId:${projectId}`

export function getWorldDepth(world: World, worlds: World[]) {
  let depth = 0
  let parentId = world.parent_world_id
  const seen = new Set<string>()

  while (parentId && !seen.has(parentId)) {
    seen.add(parentId)
    const parent = worlds.find(item => item.id === parentId)
    if (!parent) break
    depth += 1
    parentId = parent.parent_world_id
  }

  return depth
}

export function formatWorldOptionLabel(world: World, worlds: World[]) {
  const depth = getWorldDepth(world, worlds)
  const prefix = depth > 0 ? `${'　'.repeat(depth)}└ ` : ''
  const badges = [
    world.is_default ? '默认' : '',
    world.scope_type && world.scope_type !== 'root' ? world.scope_type : '',
  ].filter(Boolean)
  return `${prefix}${world.name || world.id}${badges.length ? `（${badges.join(' · ')}）` : ''}`
}

export function sortWorldsForDisplay(worlds: World[]) {
  return [...worlds].sort((a, b) => {
    if (a.is_default !== b.is_default) return a.is_default ? -1 : 1
    if (!!a.parent_world_id !== !!b.parent_world_id) return a.parent_world_id ? 1 : -1
    return (a.order_index || 0) - (b.order_index || 0) || (a.created_at || '').localeCompare(b.created_at || '')
  })
}

export function useProjectWorlds(projectId?: string | null, preferredWorldId?: string | null) {
  const [worlds, setWorlds] = useState<World[]>([])
  const [selectedWorldId, setSelectedWorldIdState] = useState('')
  const [loading, setLoading] = useState(false)

  const resolveDefaultWorldId = useCallback((items: World[]) => {
    const preferred = preferredWorldId ? items.find(world => world.id === preferredWorldId) : null
    if (preferred?.id) return preferred.id
    const markedDefault = items.find(world => world.is_default)
    if (markedDefault?.id) return markedDefault.id
    const root = items.find(world => !world.parent_world_id)
    return root?.id || items[0]?.id || ''
  }, [preferredWorldId])

  const loadWorlds = useCallback(async () => {
    if (!projectId) {
      setWorlds([])
      setSelectedWorldIdState('')
      return
    }

    setLoading(true)
    try {
      const data = sortWorldsForDisplay(await getWorlds(projectId))
      setWorlds(data)
      setSelectedWorldIdState(current => {
        const saved = localStorage.getItem(getStorageKey(projectId))
        const candidate = current || saved || resolveDefaultWorldId(data)
        return candidate && data.some(world => world.id === candidate) ? candidate : resolveDefaultWorldId(data)
      })
    } catch (error) {
      console.error('Failed to load worlds:', error)
      setWorlds([])
      setSelectedWorldIdState('')
    } finally {
      setLoading(false)
    }
  }, [projectId, resolveDefaultWorldId])

  useEffect(() => {
    loadWorlds()
  }, [loadWorlds])

  const setSelectedWorldId = useCallback((worldId: string) => {
    setSelectedWorldIdState(worldId)
    if (projectId) {
      if (worldId) localStorage.setItem(getStorageKey(projectId), worldId)
      else localStorage.removeItem(getStorageKey(projectId))
    }
  }, [projectId])

  const selectedWorld = useMemo(
    () => worlds.find(world => world.id === selectedWorldId) || null,
    [worlds, selectedWorldId],
  )

  const defaultWorld = useMemo(
    () => worlds.find(world => world.is_default) || worlds.find(world => !world.parent_world_id) || worlds[0] || null,
    [worlds],
  )

  return {
    worlds,
    selectedWorldId,
    setSelectedWorldId,
    selectedWorld,
    defaultWorld,
    isMultiWorld: worlds.length > 1,
    loading,
    refreshWorlds: loadWorlds,
    formatWorldLabel: (world: World) => formatWorldOptionLabel(world, worlds),
  }
}
