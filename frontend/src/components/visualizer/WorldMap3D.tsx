import { useEffect, useMemo, useRef, useState } from 'react'
import type { Character } from '@/api/characters'
import type { Region, World } from '@/api/worlds'
import { buildWorldScene, type Point3D, type RegionSceneNode, type WorldSceneNode } from './visualizer3dTransforms'

interface WorldMap3DProps {
  worlds: World[]
  regionsByWorldId: Record<string, Region[]>
  characters: Character[]
  selectedWorldId?: string
  onWorldSelect?: (worldId: string) => void
  onRegionSelect?: (regionId: string) => void
  onCharacterSelect?: (characterId: string) => void
  isDark?: boolean
}

interface ProjectedPoint extends Point3D {
  screenX: number
  screenY: number
  scale: number
}

type HoverTarget =
  | { type: 'world'; node: WorldSceneNode }
  | { type: 'region'; node: RegionSceneNode }
  | { type: 'character'; character: Character; region: RegionSceneNode }
  | null

export default function WorldMap3D({
  worlds,
  regionsByWorldId,
  characters,
  selectedWorldId,
  onWorldSelect,
  onRegionSelect,
  onCharacterSelect,
  isDark = false,
}: WorldMap3DProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const containerRef = useRef<HTMLDivElement>(null)
  const animationRef = useRef<number>()
  const [size, setSize] = useState({ width: 900, height: 620 })
  const [rotation, setRotation] = useState({ x: -0.55, y: 0.68 })
  const [zoom, setZoom] = useState(1)
  const [pan, setPan] = useState({ x: 0, y: 0 })
  const [hover, setHover] = useState<HoverTarget>(null)
  const [selectedRegionId, setSelectedRegionId] = useState<string>('')
  const dragRef = useRef<{ x: number; y: number; dragging: boolean; moved: boolean }>({ x: 0, y: 0, dragging: false, moved: false })
  const hitTargetsRef = useRef<Array<{ x: number; y: number; radius: number; target: HoverTarget }>>([])

  const scene = useMemo(
    () => buildWorldScene(worlds, regionsByWorldId, characters, selectedWorldId),
    [worlds, regionsByWorldId, characters, selectedWorldId],
  )

  const activeWorld = scene.worlds.find((node) => node.id === selectedWorldId) || scene.worlds[0]

  useEffect(() => {
    const updateSize = () => {
      const rect = containerRef.current?.getBoundingClientRect()
      if (rect) {
        setSize({ width: Math.max(640, rect.width), height: Math.max(520, rect.height) })
      }
    }
    updateSize()
    window.addEventListener('resize', updateSize)
    return () => window.removeEventListener('resize', updateSize)
  }, [])

  const project = (point: Point3D): ProjectedPoint => {
    const cosY = Math.cos(rotation.y)
    const sinY = Math.sin(rotation.y)
    const cosX = Math.cos(rotation.x)
    const sinX = Math.sin(rotation.x)

    const x1 = point.x * cosY - point.y * sinY
    const y1 = point.x * sinY + point.y * cosY
    const z1 = point.z
    const y2 = y1 * cosX - z1 * sinX
    const z2 = y1 * sinX + z1 * cosX
    const depthScale = Math.max(0.45, Math.min(1.35, 1 + z2 / 700))

    return {
      ...point,
      screenX: size.width / 2 + pan.x + x1 * zoom,
      screenY: size.height / 2 + pan.y + y2 * zoom,
      scale: depthScale,
    }
  }

  const drawGlowCircle = (ctx: CanvasRenderingContext2D, x: number, y: number, radius: number, color: string, alpha = 0.45) => {
    const gradient = ctx.createRadialGradient(x, y, 0, x, y, radius * 2.4)
    gradient.addColorStop(0, `${color}${Math.round(alpha * 255).toString(16).padStart(2, '0')}`)
    gradient.addColorStop(1, `${color}00`)
    ctx.fillStyle = gradient
    ctx.beginPath()
    ctx.arc(x, y, radius * 2.4, 0, Math.PI * 2)
    ctx.fill()
  }

  const draw = (time: number) => {
    const canvas = canvasRef.current
    const ctx = canvas?.getContext('2d')
    if (!canvas || !ctx) return

    const dpr = window.devicePixelRatio || 1
    canvas.width = size.width * dpr
    canvas.height = size.height * dpr
    canvas.style.width = `${size.width}px`
    canvas.style.height = `${size.height}px`
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0)
    hitTargetsRef.current = []

    const bg = ctx.createLinearGradient(0, 0, 0, size.height)
    bg.addColorStop(0, isDark ? '#020617' : '#eff6ff')
    bg.addColorStop(1, isDark ? '#111827' : '#ffffff')
    ctx.fillStyle = bg
    ctx.fillRect(0, 0, size.width, size.height)

    ctx.save()
    ctx.globalAlpha = isDark ? 0.22 : 0.35
    ctx.strokeStyle = isDark ? '#38bdf8' : '#93c5fd'
    for (let i = -8; i <= 8; i += 1) {
      const a = project({ x: -420, y: i * 52, z: -50 })
      const b = project({ x: 420, y: i * 52, z: -50 })
      const c = project({ x: i * 52, y: -420, z: -50 })
      const d = project({ x: i * 52, y: 420, z: -50 })
      ctx.beginPath(); ctx.moveTo(a.screenX, a.screenY); ctx.lineTo(b.screenX, b.screenY); ctx.stroke()
      ctx.beginPath(); ctx.moveTo(c.screenX, c.screenY); ctx.lineTo(d.screenX, d.screenY); ctx.stroke()
    }
    ctx.restore()

    const worldProjected = new Map(scene.worlds.map((node) => [node.id, project(node.position)]))
    const regionProjected = new Map(scene.regions.map((node) => [node.id, project({
      x: node.position.x + (activeWorld?.position.x || 0),
      y: node.position.y + (activeWorld?.position.y || 0),
      z: node.position.z + (activeWorld?.position.z || 0) + 16,
    })]))

    scene.worldEdges.forEach((edge) => {
      const source = worldProjected.get(edge.source)
      const target = worldProjected.get(edge.target)
      if (!source || !target) return
      ctx.strokeStyle = isDark ? 'rgba(168, 85, 247, 0.5)' : 'rgba(124, 58, 237, 0.45)'
      ctx.lineWidth = 2
      ctx.setLineDash([8, 8])
      ctx.beginPath()
      ctx.moveTo(source.screenX, source.screenY)
      ctx.lineTo(target.screenX, target.screenY)
      ctx.stroke()
      ctx.setLineDash([])
    })

    scene.regionEdges.forEach((edge) => {
      const source = regionProjected.get(edge.source)
      const target = regionProjected.get(edge.target)
      if (!source || !target) return
      ctx.strokeStyle = isDark ? 'rgba(34, 211, 238, 0.5)' : 'rgba(14, 165, 233, 0.45)'
      ctx.lineWidth = 1.5
      ctx.beginPath()
      ctx.moveTo(source.screenX, source.screenY)
      ctx.lineTo(target.screenX, target.screenY)
      ctx.stroke()
    })

    scene.worlds
      .map((node) => ({ node, p: worldProjected.get(node.id)! }))
      .sort((a, b) => a.p.scale - b.p.scale)
      .forEach(({ node, p }) => {
        const selected = node.id === selectedWorldId
        const radius = node.radius * zoom * p.scale * (selected ? 1.18 : 1)
        drawGlowCircle(ctx, p.screenX, p.screenY, radius, node.color, selected ? 0.5 : 0.25)

        ctx.fillStyle = 'rgba(15, 23, 42, 0.25)'
        ctx.beginPath()
        ctx.ellipse(p.screenX + 6, p.screenY + radius * 0.75, radius * 1.15, radius * 0.35, 0, 0, Math.PI * 2)
        ctx.fill()

        const body = ctx.createRadialGradient(p.screenX - radius * 0.35, p.screenY - radius * 0.35, 2, p.screenX, p.screenY, radius)
        body.addColorStop(0, '#ffffff')
        body.addColorStop(0.25, node.color)
        body.addColorStop(1, isDark ? '#1e1b4b' : '#1e40af')
        ctx.fillStyle = body
        ctx.beginPath()
        ctx.arc(p.screenX, p.screenY, radius, 0, Math.PI * 2)
        ctx.fill()
        ctx.strokeStyle = selected ? '#facc15' : 'rgba(255,255,255,0.65)'
        ctx.lineWidth = selected ? 3 : 1.5
        ctx.stroke()

        if (node.id === selectedWorldId || node.world.is_default) {
          ctx.fillStyle = isDark ? '#e5e7eb' : '#111827'
          ctx.font = '600 13px sans-serif'
          ctx.textAlign = 'center'
          ctx.fillText(node.world.name, p.screenX, p.screenY + radius + 18)
        }

        hitTargetsRef.current.push({ x: p.screenX, y: p.screenY, radius: Math.max(18, radius), target: { type: 'world', node } })
      })

    scene.regions
      .map((node) => ({ node, p: regionProjected.get(node.id)! }))
      .sort((a, b) => a.p.scale - b.p.scale)
      .forEach(({ node, p }) => {
        const selected = node.id === selectedRegionId
        const pulse = 1 + Math.sin(time / 320 + node.position.x) * 0.04
        const radius = node.radius * zoom * p.scale * pulse * (selected ? 1.35 : 1)
        drawGlowCircle(ctx, p.screenX, p.screenY, radius, node.color, selected ? 0.45 : 0.2)
        ctx.fillStyle = 'rgba(2, 6, 23, 0.25)'
        ctx.beginPath()
        ctx.ellipse(p.screenX + 4, p.screenY + radius * 0.9, radius * 1.4, radius * 0.42, 0, 0, Math.PI * 2)
        ctx.fill()
        ctx.fillStyle = node.color
        ctx.beginPath()
        ctx.moveTo(p.screenX, p.screenY - radius)
        ctx.lineTo(p.screenX + radius * 1.1, p.screenY)
        ctx.lineTo(p.screenX, p.screenY + radius * 0.75)
        ctx.lineTo(p.screenX - radius * 1.1, p.screenY)
        ctx.closePath()
        ctx.fill()
        ctx.strokeStyle = selected ? '#facc15' : 'rgba(255,255,255,0.55)'
        ctx.lineWidth = selected ? 2.5 : 1
        ctx.stroke()

        node.characters.slice(0, 5).forEach((character, index) => {
          const angle = (Math.PI * 2 * index) / Math.max(1, node.characters.length)
          const cx = p.screenX + Math.cos(angle) * radius * 0.9
          const cy = p.screenY - radius * 0.65 + Math.sin(angle) * radius * 0.35
          ctx.fillStyle = character.has_agent ? '#c084fc' : '#facc15'
          ctx.beginPath()
          ctx.arc(cx, cy, 3.5 * p.scale, 0, Math.PI * 2)
          ctx.fill()
          hitTargetsRef.current.push({ x: cx, y: cy, radius: 8, target: { type: 'character', character, region: node } })
        })

        if (selected || radius > 11) {
          ctx.fillStyle = isDark ? '#dbeafe' : '#1f2937'
          ctx.font = '12px sans-serif'
          ctx.textAlign = 'center'
          ctx.fillText(node.region.name, p.screenX, p.screenY + radius + 14)
        }
        hitTargetsRef.current.push({ x: p.screenX, y: p.screenY, radius: Math.max(14, radius), target: { type: 'region', node } })
      })
  }

  useEffect(() => {
    const loop = (time: number) => {
      draw(time)
      animationRef.current = requestAnimationFrame(loop)
    }
    animationRef.current = requestAnimationFrame(loop)
    return () => {
      if (animationRef.current) cancelAnimationFrame(animationRef.current)
    }
  })

  const pickTarget = (x: number, y: number) => {
    for (let i = hitTargetsRef.current.length - 1; i >= 0; i -= 1) {
      const hit = hitTargetsRef.current[i]
      const dist = Math.hypot(hit.x - x, hit.y - y)
      if (dist <= hit.radius) return hit.target
    }
    return null
  }

  const pointerPosition = (event: React.PointerEvent<HTMLCanvasElement>) => {
    const rect = event.currentTarget.getBoundingClientRect()
    return { x: event.clientX - rect.left, y: event.clientY - rect.top }
  }

  if (worlds.length === 0) {
    return <EmptyScene isDark={isDark} text="暂无世界数据，请先创建世界" />
  }

  return (
    <div ref={containerRef} className="relative h-[650px] min-h-[560px] overflow-hidden rounded-xl">
      <canvas
        ref={canvasRef}
        className="h-full w-full cursor-grab active:cursor-grabbing"
        onPointerDown={(event) => {
          const pos = pointerPosition(event)
          dragRef.current = { x: pos.x, y: pos.y, dragging: true, moved: false }
          event.currentTarget.setPointerCapture(event.pointerId)
        }}
        onPointerMove={(event) => {
          const pos = pointerPosition(event)
          if (dragRef.current.dragging) {
            const dx = pos.x - dragRef.current.x
            const dy = pos.y - dragRef.current.y
            if (Math.abs(dx) + Math.abs(dy) > 2) dragRef.current.moved = true
            setRotation((current) => ({ x: Math.max(-1.15, Math.min(0.25, current.x + dy * 0.006)), y: current.y + dx * 0.006 }))
            dragRef.current.x = pos.x
            dragRef.current.y = pos.y
          } else {
            setHover(pickTarget(pos.x, pos.y))
          }
        }}
        onPointerUp={(event) => {
          const pos = pointerPosition(event)
          const target = pickTarget(pos.x, pos.y)
          if (!dragRef.current.moved && target) {
            if (target.type === 'world') onWorldSelect?.(target.node.id)
            if (target.type === 'region') {
              setSelectedRegionId(target.node.id)
              onRegionSelect?.(target.node.id)
            }
            if (target.type === 'character') onCharacterSelect?.(target.character.id || target.character.name)
          }
          dragRef.current.dragging = false
        }}
        onPointerLeave={() => {
          dragRef.current.dragging = false
          setHover(null)
        }}
        onWheel={(event) => {
          event.preventDefault()
          setZoom((current) => Math.max(0.45, Math.min(2.4, current - event.deltaY * 0.001)))
        }}
      />

      <div className="absolute left-4 top-4 max-w-sm rounded-xl border border-white/10 bg-slate-950/70 p-3 text-white shadow-xl backdrop-blur">
        <div className="text-sm font-semibold">多位面世界图</div>
        <div className="mt-1 text-xs text-slate-300">
          {activeWorld ? `当前聚焦：${activeWorld.world.name}` : '拖拽旋转，滚轮缩放，点击位面切换世界'}
        </div>
        <div className="mt-2 flex flex-wrap gap-2 text-[11px] text-slate-300">
          <span>世界 {scene.worlds.length}</span>
          <span>区域 {scene.regions.length}</span>
          <span>角色 {characters.length}</span>
        </div>
      </div>

      <button
        type="button"
        onClick={() => {
          setRotation({ x: -0.55, y: 0.68 })
          setZoom(1)
          setPan({ x: 0, y: 0 })
          setSelectedRegionId('')
        }}
        className="absolute right-4 top-4 rounded-lg bg-white/90 px-3 py-1.5 text-sm font-medium text-slate-700 shadow hover:bg-white"
      >
        重置视角
      </button>

      {hover && <HoverCard hover={hover} isDark={isDark} />}
    </div>
  )
}

function EmptyScene({ text, isDark }: { text: string; isDark: boolean }) {
  return (
    <div className={`flex h-[650px] items-center justify-center rounded-xl border border-dashed ${isDark ? 'border-gray-700 text-gray-400' : 'border-gray-200 text-gray-500'}`}>
      {text}
    </div>
  )
}

function HoverCard({ hover, isDark }: { hover: HoverTarget; isDark: boolean }) {
  if (!hover) return null
  const title = hover.type === 'world' ? hover.node.world.name : hover.type === 'region' ? hover.node.region.name : hover.character.name
  const description = hover.type === 'world'
    ? hover.node.world.description
    : hover.type === 'region'
      ? hover.node.region.description
      : hover.character.description

  return (
    <div className={`absolute bottom-4 left-4 max-w-md rounded-xl border p-4 shadow-xl backdrop-blur ${isDark ? 'border-gray-700 bg-gray-900/90 text-gray-100' : 'border-gray-200 bg-white/90 text-gray-800'}`}>
      <div className="text-sm font-semibold">{title}</div>
      <div className={`mt-1 line-clamp-3 text-xs ${isDark ? 'text-gray-400' : 'text-gray-500'}`}>{description || '暂无描述'}</div>
      {hover.type === 'world' && (
        <div className="mt-2 text-xs">类型：{hover.node.world.scope_type || 'root'} · 区域：{hover.node.regions.length} · 角色：{hover.node.characterCount}</div>
      )}
      {hover.type === 'region' && (
        <div className="mt-2 text-xs">地形：{hover.node.region.terrain_type || '未知'} · 角色：{hover.node.characters.length}</div>
      )}
      {hover.type === 'character' && (
        <div className="mt-2 text-xs">状态：{hover.character.status} · 区域：{hover.region.region.name}</div>
      )}
    </div>
  )
}
