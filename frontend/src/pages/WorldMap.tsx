import { FormEvent, useCallback, useEffect, useMemo, useState } from 'react'
import { Edit2, Link2, MapPin, Plus, Search, Trash2, Users } from 'lucide-react'

import PageLayout from '@/components/PageLayout'
import MapView from '@/components/world/MapView'
import { useProject } from '@/contexts/ProjectContext'
import { getCharacters, type Character } from '@/api/characters'
import {
  createRegion,
  deleteRegion,
  getRegions,
  getWorlds,
  updateRegion,
  type CreateRegionDTO,
  type Region,
  type World,
} from '@/api/worlds'

const REGION_TYPES = [
  { value: 'custom', label: '自定义' },
  { value: 'city', label: '城市' },
  { value: 'village', label: '村庄' },
  { value: 'wilderness', label: '荒野' },
  { value: 'dungeon', label: '副本/秘境' },
  { value: 'building', label: '建筑' },
  { value: 'water', label: '水域' },
  { value: 'mountain', label: '山脉' },
  { value: 'forest', label: '森林' },
]

const TERRAIN_TYPES = [
  { value: 'custom', label: '自定义' },
  { value: 'plain', label: '平原' },
  { value: 'hill', label: '丘陵' },
  { value: 'mountain', label: '山地' },
  { value: 'desert', label: '沙漠' },
  { value: 'swamp', label: '沼泽' },
  { value: 'ice', label: '冰原' },
  { value: 'volcano', label: '火山' },
]

interface RegionFormState {
  name: string
  region_type: string
  terrain_type: string
  description: string
  atmosphere: string
  x: string
  y: string
  connections: string[]
  terrain_features_text: string
  landmarks_text: string
}

interface MapLocationCharacter {
  id: string
  name: string
  location_id: string
  location_reason?: string
}

interface MapLocation {
  id: string
  name: string
  description?: string
  type?: string
  x: number
  y: number
  connections?: string[]
  characters?: MapLocationCharacter[]
}

const emptyForm: RegionFormState = {
  name: '',
  region_type: 'custom',
  terrain_type: 'custom',
  description: '',
  atmosphere: '',
  x: '',
  y: '',
  connections: [],
  terrain_features_text: '',
  landmarks_text: '',
}

const getTypeLabel = (items: Array<{ value: string; label: string }>, value?: string) =>
  items.find(item => item.value === value)?.label || value || '未设置'

const parseTextItems = (text: string) =>
  text
    .split('\n')
    .map(item => item.trim())
    .filter(Boolean)
    .map(name => ({ name }))

const stringifyItems = (items?: Array<Record<string, unknown>>) =>
  (items || [])
    .map(item => String(item.name || item.title || item.description || ''))
    .filter(Boolean)
    .join('\n')

export default function WorldMap() {
  const { currentProject } = useProject()
  const [worlds, setWorlds] = useState<World[]>([])
  const [selectedWorldId, setSelectedWorldId] = useState('')
  const [regions, setRegions] = useState<Region[]>([])
  const [characters, setCharacters] = useState<Character[]>([])
  const [selectedRegionId, setSelectedRegionId] = useState<string>('')
  const [loading, setLoading] = useState(false)
  const [searchQuery, setSearchQuery] = useState('')
  const [filterRegionType, setFilterRegionType] = useState('')
  const [filterTerrainType, setFilterTerrainType] = useState('')
  const [showModal, setShowModal] = useState(false)
  const [editingRegion, setEditingRegion] = useState<Region | null>(null)
  const [formData, setFormData] = useState<RegionFormState>(emptyForm)

  const loadWorlds = useCallback(async () => {
    if (!currentProject) {
      setWorlds([])
      setSelectedWorldId('')
      return
    }

    const data = await getWorlds(currentProject.id)
    setWorlds(data)
    setSelectedWorldId(prev => (prev && data.some(world => world.id === prev) ? prev : data[0]?.id || ''))
  }, [currentProject])

  const loadRegions = useCallback(async () => {
    if (!selectedWorldId) {
      setRegions([])
      setSelectedRegionId('')
      return
    }

    setLoading(true)
    try {
      const data = await getRegions(selectedWorldId)
      setRegions(data)
      setSelectedRegionId(prev => (prev && data.some(region => region.id === prev) ? prev : data[0]?.id || ''))
    } catch (error) {
      console.error('Failed to load regions:', error)
      setRegions([])
    } finally {
      setLoading(false)
    }
  }, [selectedWorldId])

  const loadCharacters = useCallback(async () => {
    if (!currentProject?.id) {
      setCharacters([])
      return
    }

    try {
      const data = await getCharacters(currentProject.id)
      setCharacters(data)
    } catch (error) {
      console.error('Failed to load characters:', error)
      setCharacters([])
    }
  }, [currentProject?.id])

  useEffect(() => {
    loadWorlds().catch(error => console.error('Failed to load worlds:', error))
  }, [loadWorlds])

  useEffect(() => {
    loadRegions()
  }, [loadRegions])

  useEffect(() => {
    loadCharacters()
  }, [loadCharacters])

  const charactersByRegion = useMemo(() => {
    const grouped = new Map<string, MapLocationCharacter[]>()
    characters
      .filter(character => (
        character.current_region_id &&
        (!character.world_id || character.world_id === selectedWorldId)
      ))
      .forEach(character => {
        const regionId = character.current_region_id!
        const current = grouped.get(regionId) || []
        current.push({
          id: character.id || character.name,
          name: character.name,
          location_id: regionId,
          location_reason: character.current_location_reason,
        })
        grouped.set(regionId, current)
      })
    return grouped
  }, [characters, selectedWorldId])

  const filteredRegions = useMemo(() => {
    const query = searchQuery.trim().toLowerCase()
    return regions.filter(region => {
      const matchesQuery = !query || [region.name, region.description, region.atmosphere]
        .filter(Boolean)
        .some(value => value!.toLowerCase().includes(query))
      const matchesRegionType = !filterRegionType || region.region_type === filterRegionType
      const matchesTerrainType = !filterTerrainType || region.terrain_type === filterTerrainType
      return matchesQuery && matchesRegionType && matchesTerrainType
    })
  }, [regions, searchQuery, filterRegionType, filterTerrainType])

  const selectedRegion = useMemo(
    () => regions.find(region => region.id === selectedRegionId) || null,
    [regions, selectedRegionId],
  )

  const mapLocations = useMemo<MapLocation[]>(() => {
    const sortedRegions = [...filteredRegions].sort((a, b) => (a.created_at || a.name).localeCompare(b.created_at || b.name))
    const total = Math.max(sortedRegions.length, 1)
    const centerX = 400
    const centerY = 300
    const radius = Math.min(220, Math.max(120, total * 28))
    const visibleIds = new Set(sortedRegions.map(region => region.id).filter(Boolean))

    return sortedRegions.map((region, index) => {
      const angle = (Math.PI * 2 * index) / total - Math.PI / 2
      const x = typeof region.coordinates?.x === 'number' ? region.coordinates.x : Math.round(centerX + Math.cos(angle) * radius)
      const y = typeof region.coordinates?.y === 'number' ? region.coordinates.y : Math.round(centerY + Math.sin(angle) * radius)

      return {
        id: region.id || region.name,
        name: region.name,
        description: region.description,
        type: region.region_type || 'custom',
        x,
        y,
        connections: (region.connections || []).filter(id => visibleIds.has(id)),
        characters: region.id ? charactersByRegion.get(region.id) || [] : [],
      }
    })
  }, [filteredRegions, charactersByRegion])

  const openCreateModal = () => {
    setEditingRegion(null)
    setFormData(emptyForm)
    setShowModal(true)
  }

  const openEditModal = (region: Region) => {
    setEditingRegion(region)
    setFormData({
      name: region.name,
      region_type: region.region_type || 'custom',
      terrain_type: region.terrain_type || 'custom',
      description: region.description || '',
      atmosphere: region.atmosphere || '',
      x: typeof region.coordinates?.x === 'number' ? String(region.coordinates.x) : '',
      y: typeof region.coordinates?.y === 'number' ? String(region.coordinates.y) : '',
      connections: region.connections || [],
      terrain_features_text: stringifyItems(region.terrain_features),
      landmarks_text: stringifyItems(region.landmarks),
    })
    setShowModal(true)
  }

  const handleSubmit = async (event: FormEvent) => {
    event.preventDefault()
    if (!selectedWorldId || !formData.name.trim()) return

    const x = Number(formData.x)
    const y = Number(formData.y)
    const payload: CreateRegionDTO = {
      name: formData.name.trim(),
      region_type: formData.region_type,
      terrain_type: formData.terrain_type,
      description: formData.description.trim() || undefined,
      atmosphere: formData.atmosphere.trim() || undefined,
      coordinates: Number.isFinite(x) && Number.isFinite(y) ? { x, y } : {},
      area_size: editingRegion?.area_size || 0,
      terrain_features: parseTextItems(formData.terrain_features_text),
      landmarks: parseTextItems(formData.landmarks_text),
      encounters: editingRegion?.encounters || [],
      connections: formData.connections,
      local_rules: editingRegion?.local_rules || [],
      is_generated: editingRegion?.is_generated || false,
      visit_count: editingRegion?.visit_count || 0,
    }

    try {
      if (editingRegion?.id) {
        await updateRegion(selectedWorldId, editingRegion.id, payload)
        setSelectedRegionId(editingRegion.id)
      } else {
        const result = await createRegion(selectedWorldId, payload)
        setSelectedRegionId(result.id)
      }
      setShowModal(false)
      await loadRegions()
    } catch (error) {
      console.error('Failed to save region:', error)
      alert('保存区域失败，请查看控制台日志')
    }
  }

  const handleDelete = async (region: Region) => {
    if (!selectedWorldId || !region.id) return
    if (!confirm(`确定删除区域「${region.name}」吗？`)) return

    try {
      await deleteRegion(selectedWorldId, region.id)
      await loadRegions()
    } catch (error) {
      console.error('Failed to delete region:', error)
      alert('删除区域失败，请查看控制台日志')
    }
  }

  const selectedRegionCharacters = selectedRegion?.id ? charactersByRegion.get(selectedRegion.id) || [] : []

  const actions = (
    <button
      onClick={openCreateModal}
      disabled={!selectedWorldId}
      className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:bg-gray-300 flex items-center gap-2"
    >
      <Plus className="w-4 h-4" />
      新建区域
    </button>
  )

  return (
    <PageLayout title="世界地图" description="管理世界中的区域、地点与连接关系" actions={actions}>
      {!currentProject ? (
        <div className="h-full flex items-center justify-center text-gray-500">请先选择或创建项目</div>
      ) : worlds.length === 0 ? (
        <div className="h-full flex items-center justify-center text-gray-500">当前项目没有世界，请先到世界管理创建世界</div>
      ) : (
        <div className="h-full flex flex-col gap-4">
          <div className="bg-white rounded-xl border border-gray-200 p-4 flex flex-wrap items-center gap-3">
            <select
              value={selectedWorldId}
              onChange={event => setSelectedWorldId(event.target.value)}
              className="px-3 py-2 border border-gray-300 rounded-lg"
            >
              {worlds.map(world => (
                <option key={world.id} value={world.id}>{world.name}</option>
              ))}
            </select>
            <div className="relative flex-1 min-w-[220px]">
              <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
              <input
                value={searchQuery}
                onChange={event => setSearchQuery(event.target.value)}
                placeholder="搜索区域名称、描述或氛围"
                className="w-full pl-9 pr-3 py-2 border border-gray-300 rounded-lg"
              />
            </div>
            <select value={filterRegionType} onChange={event => setFilterRegionType(event.target.value)} className="px-3 py-2 border border-gray-300 rounded-lg">
              <option value="">全部区域类型</option>
              {REGION_TYPES.map(type => <option key={type.value} value={type.value}>{type.label}</option>)}
            </select>
            <select value={filterTerrainType} onChange={event => setFilterTerrainType(event.target.value)} className="px-3 py-2 border border-gray-300 rounded-lg">
              <option value="">全部地形</option>
              {TERRAIN_TYPES.map(type => <option key={type.value} value={type.value}>{type.label}</option>)}
            </select>
          </div>

          <div className="grid grid-cols-[280px_minmax(0,1fr)_320px] gap-4 min-h-[620px]">
            <aside className="bg-white rounded-xl border border-gray-200 overflow-hidden flex flex-col">
              <div className="px-4 py-3 border-b border-gray-200 font-medium">区域列表</div>
              <div className="flex-1 overflow-auto divide-y divide-gray-100">
                {loading ? (
                  <div className="p-4 text-sm text-gray-500">加载中...</div>
                ) : filteredRegions.length === 0 ? (
                  <div className="p-4 text-sm text-gray-500">暂无区域，创建第一个区域开始构建地图</div>
                ) : (
                  filteredRegions.map(region => (
                    <button
                      key={region.id}
                      onClick={() => setSelectedRegionId(region.id || '')}
                      className={`w-full text-left p-4 hover:bg-blue-50 transition-colors ${selectedRegionId === region.id ? 'bg-blue-50' : ''}`}
                    >
                      <div className="font-medium text-gray-900">{region.name}</div>
                      <div className="text-xs text-gray-500 mt-1">
                        {getTypeLabel(REGION_TYPES, region.region_type)} · {getTypeLabel(TERRAIN_TYPES, region.terrain_type)}
                      </div>
                      {region.description && <div className="text-sm text-gray-600 mt-2 line-clamp-2">{region.description}</div>}
                    </button>
                  ))
                )}
              </div>
            </aside>

            <main className="bg-white rounded-xl border border-gray-200 overflow-hidden">
              {mapLocations.length > 0 ? (
                <MapView
                  worldId={selectedWorldId}
                  locations={mapLocations}
                  selectedLocation={selectedRegionId}
                  onLocationSelect={setSelectedRegionId}
                />
              ) : (
                <div className="h-full flex flex-col items-center justify-center text-gray-500 gap-3">
                  <MapPin className="w-10 h-10" />
                  <span>暂无可展示区域</span>
                  <button onClick={openCreateModal} className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700">创建区域</button>
                </div>
              )}
            </main>

            <aside className="bg-white rounded-xl border border-gray-200 p-4 overflow-auto">
              {selectedRegion ? (
                <div className="space-y-4">
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <h2 className="text-xl font-bold text-gray-900">{selectedRegion.name}</h2>
                      <p className="text-sm text-gray-500 mt-1">
                        {getTypeLabel(REGION_TYPES, selectedRegion.region_type)} · {getTypeLabel(TERRAIN_TYPES, selectedRegion.terrain_type)}
                      </p>
                    </div>
                    <div className="flex gap-2">
                      <button onClick={() => openEditModal(selectedRegion)} className="p-2 text-blue-600 hover:bg-blue-50 rounded-lg" title="编辑">
                        <Edit2 className="w-4 h-4" />
                      </button>
                      <button onClick={() => handleDelete(selectedRegion)} className="p-2 text-red-600 hover:bg-red-50 rounded-lg" title="删除">
                        <Trash2 className="w-4 h-4" />
                      </button>
                    </div>
                  </div>

                  <section>
                    <h3 className="text-sm font-semibold text-gray-700 mb-2">描述</h3>
                    <p className="text-sm text-gray-600 whitespace-pre-wrap">{selectedRegion.description || '暂无描述'}</p>
                  </section>
                  <section>
                    <h3 className="text-sm font-semibold text-gray-700 mb-2">氛围</h3>
                    <p className="text-sm text-gray-600 whitespace-pre-wrap">{selectedRegion.atmosphere || '暂无氛围'}</p>
                  </section>
                  <section>
                    <h3 className="text-sm font-semibold text-gray-700 mb-2">坐标</h3>
                    <p className="text-sm text-gray-600">x: {selectedRegion.coordinates?.x ?? '自动布局'} · y: {selectedRegion.coordinates?.y ?? '自动布局'}</p>
                  </section>
                  <section>
                    <h3 className="text-sm font-semibold text-gray-700 mb-2 flex items-center gap-1"><Link2 className="w-4 h-4" /> 已连接区域</h3>
                    <div className="flex flex-wrap gap-2">
                      {(selectedRegion.connections || []).length === 0 ? (
                        <span className="text-sm text-gray-500">暂无连接</span>
                      ) : (
                        selectedRegion.connections?.map(id => {
                          const target = regions.find(region => region.id === id)
                          return <span key={id} className="px-2 py-1 bg-gray-100 rounded text-xs text-gray-700">{target?.name || id}</span>
                        })
                      )}
                    </div>
                  </section>
                  <section>
                    <h3 className="text-sm font-semibold text-gray-700 mb-2 flex items-center gap-1"><Users className="w-4 h-4" /> 当前在此角色</h3>
                    {selectedRegionCharacters.length === 0 ? (
                      <p className="text-sm text-gray-500">暂无角色位于此区域</p>
                    ) : (
                      <div className="space-y-2">
                        {selectedRegionCharacters.map(character => (
                          <div key={character.id} className="rounded-lg border border-amber-100 bg-amber-50 px-3 py-2">
                            <div className="text-sm font-medium text-gray-900">{character.name}</div>
                            <div className="text-xs text-gray-600 mt-1 whitespace-pre-wrap">
                              {character.location_reason || '未填写原因'}
                            </div>
                          </div>
                        ))}
                      </div>
                    )}
                  </section>
                  <section>
                    <h3 className="text-sm font-semibold text-gray-700 mb-2">地形特征</h3>
                    <p className="text-sm text-gray-600 whitespace-pre-wrap">{stringifyItems(selectedRegion.terrain_features) || '暂无'}</p>
                  </section>
                  <section>
                    <h3 className="text-sm font-semibold text-gray-700 mb-2">地标</h3>
                    <p className="text-sm text-gray-600 whitespace-pre-wrap">{stringifyItems(selectedRegion.landmarks) || '暂无'}</p>
                  </section>
                </div>
              ) : (
                <div className="h-full flex items-center justify-center text-gray-500">请选择区域查看详情</div>
              )}
            </aside>
          </div>
        </div>
      )}

      {showModal && (
        <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-[100] p-4">
          <form onSubmit={handleSubmit} className="bg-white rounded-xl shadow-xl w-full max-w-3xl max-h-[90vh] overflow-auto">
            <div className="p-6 border-b border-gray-200">
              <h2 className="text-xl font-bold">{editingRegion ? '编辑区域' : '新建区域'}</h2>
            </div>
            <div className="p-6 grid grid-cols-2 gap-4">
              <label className="col-span-2">
                <span className="block text-sm font-medium text-gray-700 mb-1">名称</span>
                <input value={formData.name} onChange={event => setFormData(prev => ({ ...prev, name: event.target.value }))} required className="w-full px-3 py-2 border border-gray-300 rounded-lg" />
              </label>
              <label>
                <span className="block text-sm font-medium text-gray-700 mb-1">区域类型</span>
                <select value={formData.region_type} onChange={event => setFormData(prev => ({ ...prev, region_type: event.target.value }))} className="w-full px-3 py-2 border border-gray-300 rounded-lg">
                  {REGION_TYPES.map(type => <option key={type.value} value={type.value}>{type.label}</option>)}
                </select>
              </label>
              <label>
                <span className="block text-sm font-medium text-gray-700 mb-1">地形类型</span>
                <select value={formData.terrain_type} onChange={event => setFormData(prev => ({ ...prev, terrain_type: event.target.value }))} className="w-full px-3 py-2 border border-gray-300 rounded-lg">
                  {TERRAIN_TYPES.map(type => <option key={type.value} value={type.value}>{type.label}</option>)}
                </select>
              </label>
              <label>
                <span className="block text-sm font-medium text-gray-700 mb-1">坐标 X</span>
                <input type="number" value={formData.x} onChange={event => setFormData(prev => ({ ...prev, x: event.target.value }))} placeholder="留空则自动布局" className="w-full px-3 py-2 border border-gray-300 rounded-lg" />
              </label>
              <label>
                <span className="block text-sm font-medium text-gray-700 mb-1">坐标 Y</span>
                <input type="number" value={formData.y} onChange={event => setFormData(prev => ({ ...prev, y: event.target.value }))} placeholder="留空则自动布局" className="w-full px-3 py-2 border border-gray-300 rounded-lg" />
              </label>
              <label className="col-span-2">
                <span className="block text-sm font-medium text-gray-700 mb-1">描述</span>
                <textarea value={formData.description} onChange={event => setFormData(prev => ({ ...prev, description: event.target.value }))} rows={3} className="w-full px-3 py-2 border border-gray-300 rounded-lg" />
              </label>
              <label className="col-span-2">
                <span className="block text-sm font-medium text-gray-700 mb-1">氛围</span>
                <textarea value={formData.atmosphere} onChange={event => setFormData(prev => ({ ...prev, atmosphere: event.target.value }))} rows={2} className="w-full px-3 py-2 border border-gray-300 rounded-lg" />
              </label>
              <label className="col-span-2">
                <span className="block text-sm font-medium text-gray-700 mb-1">连接区域</span>
                <select
                  multiple
                  value={formData.connections}
                  onChange={event => setFormData(prev => ({
                    ...prev,
                    connections: Array.from(event.target.selectedOptions).map(option => option.value),
                  }))}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg min-h-[120px]"
                >
                  {regions
                    .filter(region => region.id && region.id !== editingRegion?.id)
                    .map(region => <option key={region.id} value={region.id}>{region.name}</option>)}
                </select>
                <p className="text-xs text-gray-500 mt-1">按住 Ctrl/Command 可多选</p>
              </label>
              <label>
                <span className="block text-sm font-medium text-gray-700 mb-1">地形特征（每行一项）</span>
                <textarea value={formData.terrain_features_text} onChange={event => setFormData(prev => ({ ...prev, terrain_features_text: event.target.value }))} rows={4} className="w-full px-3 py-2 border border-gray-300 rounded-lg" />
              </label>
              <label>
                <span className="block text-sm font-medium text-gray-700 mb-1">地标（每行一项）</span>
                <textarea value={formData.landmarks_text} onChange={event => setFormData(prev => ({ ...prev, landmarks_text: event.target.value }))} rows={4} className="w-full px-3 py-2 border border-gray-300 rounded-lg" />
              </label>
            </div>
            <div className="p-6 border-t border-gray-200 flex justify-end gap-3">
              <button type="button" onClick={() => setShowModal(false)} className="px-4 py-2 border border-gray-300 rounded-lg hover:bg-gray-50">取消</button>
              <button type="submit" className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700">保存</button>
            </div>
          </form>
        </div>
      )}
    </PageLayout>
  )
}
