import { useEffect, useMemo, useRef, useState } from 'react'
import { CharacterImportanceTier, TIER_DISPLAY_NAMES, type Character } from '@/api/characters'
import {
  buildCharacterRelationshipScene,
  type Point3D,
  type RelationshipGraphEdge,
  type RelationshipGraphNode,
} from './visualizer3dTransforms'

interface CharacterRelationshipGraph3DProps {
  worldId?: string
  characters: Character[]
  selectedCharacterId?: string
  onCharacterSelect?: (characterId: string) => void
  isDark?: boolean
}

interface ProjectedNode extends RelationshipGraphNode {
  screenX: number
  screenY: number
  depth: number
  projectedRadius: number
}

interface StarPoint {
  x: number
  y: number
  z: number
  radius: number
  alpha: number
  hue: number
  twinkle: number
  drift: number
}

const edgeColors: Record<string, string> = {
  friendship: '#22c55e',
  enemy: '#fb7185',
  rivalry: '#f59e0b',
  romance: '#ec4899',
  family: '#a78bfa',
  mentorship: '#38bdf8',
  relationship: '#94a3b8',
}

export default function CharacterRelationshipGraph3D({
  worldId,
  characters,
  selectedCharacterId,
  onCharacterSelect,
  isDark = false,
}: CharacterRelationshipGraph3DProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const containerRef = useRef<HTMLDivElement>(null)
  const animationRef = useRef<number>()
  const dragRef = useRef({ x: 0, y: 0, dragging: false, moved: false })
  const [size, setSize] = useState({ width: 980, height: 660 })
  const [rotation, setRotation] = useState({ x: 0.45, y: 0.2 })
  const [zoom, setZoom] = useState(1)
  const [hoveredNodeId, setHoveredNodeId] = useState<string>('')
  const [focusedNodeId, setFocusedNodeId] = useState(selectedCharacterId || '')
  const [autoRotate, setAutoRotate] = useState(true)
  const projectedRef = useRef<ProjectedNode[]>([])

  const scene = useMemo(() => buildCharacterRelationshipScene(characters, worldId), [characters, worldId])
  const starfield = useMemo(() => createStarfield(220), [])
  const focusedNode = scene.nodes.find((node) => node.id === focusedNodeId) || null
  const activeNodeId = focusedNodeId || hoveredNodeId
  const adjacentIds = useMemo(() => {
    if (!activeNodeId) return new Set<string>()
    const ids = new Set<string>([activeNodeId])
    scene.edges.forEach((edge) => {
      if (edge.source === activeNodeId) ids.add(edge.target)
      if (edge.target === activeNodeId) ids.add(edge.source)
    })
    return ids
  }, [activeNodeId, scene.edges])

  useEffect(() => {
    setFocusedNodeId(selectedCharacterId || '')
  }, [selectedCharacterId])

  useEffect(() => {
    const updateSize = () => {
      const rect = containerRef.current?.getBoundingClientRect()
      if (rect) setSize({ width: Math.max(720, rect.width), height: Math.max(560, rect.height) })
    }
    updateSize()
    window.addEventListener('resize', updateSize)
    return () => window.removeEventListener('resize', updateSize)
  }, [])

  const projectPoint = (point: Point3D, rotationOverride = rotation) => {
    const cosY = Math.cos(rotationOverride.y)
    const sinY = Math.sin(rotationOverride.y)
    const cosX = Math.cos(rotationOverride.x)
    const sinX = Math.sin(rotationOverride.x)
    const x1 = point.x * cosY - point.y * sinY
    const y1 = point.x * sinY + point.y * cosY
    const z1 = point.z
    const y2 = y1 * cosX - z1 * sinX
    const z2 = y1 * sinX + z1 * cosX
    const perspective = 760 / (760 - z2)
    return {
      x: size.width / 2 + x1 * perspective * zoom * 0.82,
      y: size.height / 2 + y2 * perspective * zoom * 0.82,
      depth: z2,
      scale: perspective,
    }
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

    const rotationForFrame = autoRotate && !focusedNodeId
      ? { ...rotation, y: rotation.y + time * 0.00008 }
      : rotation

    drawCosmicBackground(ctx, size.width, size.height, time, starfield, isDark)

    const projected = scene.nodes.map((node) => {
      const targetBoost = focusedNodeId === node.id ? 1.9 : adjacentIds.has(node.id) && focusedNodeId ? 1.22 : 1
      const pulse = 1 + Math.sin(time / 420 + node.position.x) * 0.04
      const projectedPoint = projectPoint(node.position, rotationForFrame)
      return {
        ...node,
        screenX: projectedPoint.x,
        screenY: projectedPoint.y,
        depth: projectedPoint.depth,
        projectedRadius: node.radius * projectedPoint.scale * zoom * targetBoost * pulse,
      }
    })
    projectedRef.current = projected
    const projectedById = new Map(projected.map((node) => [node.id, node]))

    scene.edges.forEach((edge) => drawEdge(ctx, edge, projectedById, time, Boolean(activeNodeId), adjacentIds, isDark))

    projected
      .sort((a, b) => a.depth - b.depth)
      .forEach((node) => {
        const faded = activeNodeId && !adjacentIds.has(node.id)
        const selected = focusedNodeId === node.id
        const hovered = hoveredNodeId === node.id
        const alpha = faded ? 0.18 : 1
        const glowRadius = node.projectedRadius * (selected ? 5.2 : hovered ? 4.1 : 3)
        const halo = ctx.createRadialGradient(node.screenX, node.screenY, 0, node.screenX, node.screenY, glowRadius)
        halo.addColorStop(0, `${node.color}${Math.round(alpha * (selected ? 210 : 155)).toString(16).padStart(2, '0')}`)
        halo.addColorStop(0.36, `${node.color}${Math.round(alpha * 70).toString(16).padStart(2, '0')}`)
        halo.addColorStop(1, `${node.color}00`)
        ctx.fillStyle = halo
        ctx.beginPath()
        ctx.arc(node.screenX, node.screenY, glowRadius, 0, Math.PI * 2)
        ctx.fill()

        const rayLength = node.projectedRadius * (selected ? 3.8 : hovered ? 2.8 : node.visualType === 'main' ? 2.3 : 1.75)
        if (!faded && (selected || hovered || node.visualType === 'main' || node.degree >= 2)) {
          drawStarRays(ctx, node.screenX, node.screenY, rayLength, node.color, selected ? 0.95 : 0.45, time + node.position.x)
        }

        const core = ctx.createRadialGradient(
          node.screenX - node.projectedRadius * 0.22,
          node.screenY - node.projectedRadius * 0.3,
          0,
          node.screenX,
          node.screenY,
          node.projectedRadius * 1.35,
        )
        core.addColorStop(0, '#ffffff')
        core.addColorStop(0.2, '#fef9c3')
        core.addColorStop(0.48, node.color)
        core.addColorStop(1, isDark ? '#172554' : '#1e3a8a')
        ctx.globalAlpha = alpha
        ctx.fillStyle = core
        ctx.beginPath()
        ctx.arc(node.screenX, node.screenY, node.projectedRadius, 0, Math.PI * 2)
        ctx.fill()
        ctx.strokeStyle = selected ? '#fde68a' : hovered ? '#ffffff' : 'rgba(219,234,254,0.72)'
        ctx.lineWidth = selected ? 3 : hovered ? 2 : 1
        ctx.stroke()
        ctx.globalAlpha = 1

        if (selected || hovered || node.visualType === 'main' || node.degree >= 2) {
          ctx.font = `${selected ? 700 : 500} ${selected ? 15 : 12}px sans-serif`
          ctx.textAlign = 'center'
          ctx.fillStyle = faded ? 'rgba(148,163,184,0.4)' : isDark ? '#e5e7eb' : '#111827'
          ctx.fillText(node.character.name, node.screenX, node.screenY + node.projectedRadius + 17)
        }
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

  const pickNode = (x: number, y: number) => {
    const sorted = [...projectedRef.current].sort((a, b) => b.depth - a.depth)
    return sorted.find((node) => Math.hypot(node.screenX - x, node.screenY - y) <= Math.max(12, node.projectedRadius + 4)) || null
  }

  const pointerPosition = (event: React.PointerEvent<HTMLCanvasElement>) => {
    const rect = event.currentTarget.getBoundingClientRect()
    return { x: event.clientX - rect.left, y: event.clientY - rect.top }
  }

  if (scene.nodes.length === 0) {
    return <EmptyGraph isDark={isDark} text="当前世界暂无角色" />
  }

  return (
    <div ref={containerRef} className="relative h-[650px] min-h-[560px] overflow-hidden rounded-xl">
      <canvas
        ref={canvasRef}
        className="h-full w-full cursor-grab active:cursor-grabbing"
        onPointerDown={(event) => {
          const pos = pointerPosition(event)
          dragRef.current = { x: pos.x, y: pos.y, dragging: true, moved: false }
          setAutoRotate(false)
          event.currentTarget.setPointerCapture(event.pointerId)
        }}
        onPointerMove={(event) => {
          const pos = pointerPosition(event)
          if (dragRef.current.dragging) {
            const dx = pos.x - dragRef.current.x
            const dy = pos.y - dragRef.current.y
            if (Math.abs(dx) + Math.abs(dy) > 2) dragRef.current.moved = true
            setRotation((current) => ({ x: Math.max(-1.2, Math.min(1.2, current.x + dy * 0.006)), y: current.y + dx * 0.006 }))
            dragRef.current.x = pos.x
            dragRef.current.y = pos.y
          } else {
            const node = pickNode(pos.x, pos.y)
            setHoveredNodeId(node?.id || '')
          }
        }}
        onPointerUp={(event) => {
          const pos = pointerPosition(event)
          const node = pickNode(pos.x, pos.y)
          if (!dragRef.current.moved) {
            if (node) {
              setFocusedNodeId(node.id)
              onCharacterSelect?.(node.id)
              setZoom((current) => Math.max(current, 1.08))
            } else {
              setFocusedNodeId('')
            }
          }
          dragRef.current.dragging = false
        }}
        onPointerLeave={() => {
          dragRef.current.dragging = false
          setHoveredNodeId('')
        }}
        onWheel={(event) => {
          event.preventDefault()
          setZoom((current) => Math.max(0.5, Math.min(2.6, current - event.deltaY * 0.001)))
        }}
      />

      <div className="absolute left-4 top-4 rounded-xl border border-white/10 bg-slate-950/75 p-3 text-white shadow-xl backdrop-blur">
        <div className="text-sm font-semibold">星空 3D 角色关系网</div>
        <div className="mt-1 text-xs text-slate-300">角色是星辰，关系是星轨；拖拽旋转，滚轮缩放，点击节点聚焦详情</div>
        <div className="mt-2 flex gap-3 text-[11px] text-slate-300">
          <span>角色 {scene.nodes.length}</span>
          <span>关系 {scene.edges.length}</span>
          {scene.edges.length === 0 && <span className="text-amber-300">暂无可解析关系边</span>}
        </div>
      </div>

      <div className="absolute right-4 top-4 flex gap-2">
        <button
          type="button"
          onClick={() => setAutoRotate((value) => !value)}
          className="rounded-lg bg-white/90 px-3 py-1.5 text-sm font-medium text-slate-700 shadow hover:bg-white"
        >
          {autoRotate ? '暂停自转' : '开启自转'}
        </button>
        <button
          type="button"
          onClick={() => {
            setRotation({ x: 0.45, y: 0.2 })
            setZoom(1)
            setFocusedNodeId('')
            setAutoRotate(true)
          }}
          className="rounded-lg bg-white/90 px-3 py-1.5 text-sm font-medium text-slate-700 shadow hover:bg-white"
        >
          重置视角
        </button>
      </div>

      {focusedNode && <CharacterDetailPanel node={focusedNode} edges={scene.edges} isDark={isDark} />}
    </div>
  )
}

function hashUnit(seed: number) {
  return Math.abs(Math.sin(seed * 12.9898) * 43758.5453) % 1
}

function createStarfield(count: number): StarPoint[] {
  return Array.from({ length: count }, (_, index) => ({
    x: hashUnit(index + 1),
    y: hashUnit(index + 31),
    z: hashUnit(index + 67),
    radius: 0.45 + hashUnit(index + 103) * 1.7,
    alpha: 0.26 + hashUnit(index + 149) * 0.64,
    hue: 205 + hashUnit(index + 191) * 75,
    twinkle: 0.6 + hashUnit(index + 233) * 1.8,
    drift: hashUnit(index + 277) * 2 - 1,
  }))
}

function drawCosmicBackground(
  ctx: CanvasRenderingContext2D,
  width: number,
  height: number,
  time: number,
  stars: StarPoint[],
  isDark: boolean,
) {
  const bg = ctx.createRadialGradient(width * 0.48, height * 0.46, 0, width * 0.5, height * 0.54, Math.max(width, height) * 0.8)
  bg.addColorStop(0, isDark ? '#172554' : '#dbeafe')
  bg.addColorStop(0.34, isDark ? '#0f172a' : '#eff6ff')
  bg.addColorStop(0.72, isDark ? '#07001f' : '#dbeafe')
  bg.addColorStop(1, isDark ? '#00020c' : '#bfdbfe')
  ctx.fillStyle = bg
  ctx.fillRect(0, 0, width, height)

  drawNebula(ctx, width * 0.25, height * 0.28, Math.max(width, height) * 0.46, 'rgba(124,58,237,0.22)')
  drawNebula(ctx, width * 0.78, height * 0.62, Math.max(width, height) * 0.5, 'rgba(14,165,233,0.18)')
  drawNebula(ctx, width * 0.52, height * 0.78, Math.max(width, height) * 0.38, 'rgba(236,72,153,0.13)')

  ctx.save()
  stars.forEach((star) => {
    const parallax = 1 + star.z * 0.45
    const x = ((star.x * width + Math.sin(time * 0.00008 * star.twinkle) * star.drift * 18 * parallax) + width) % width
    const y = ((star.y * height + Math.cos(time * 0.00006 * star.twinkle) * star.drift * 10 * parallax) + height) % height
    const twinkle = 0.62 + Math.sin(time * 0.002 * star.twinkle + star.x * 8) * 0.38
    const alpha = star.alpha * twinkle * (isDark ? 1 : 0.78)
    const radius = star.radius * parallax
    ctx.fillStyle = `hsla(${star.hue}, 95%, ${isDark ? 83 : 70}%, ${alpha})`
    ctx.beginPath()
    ctx.arc(x, y, radius, 0, Math.PI * 2)
    ctx.fill()

    if (star.radius > 1.45) {
      ctx.strokeStyle = `rgba(255,255,255,${alpha * 0.45})`
      ctx.lineWidth = 0.6
      ctx.beginPath()
      ctx.moveTo(x - radius * 2.8, y)
      ctx.lineTo(x + radius * 2.8, y)
      ctx.moveTo(x, y - radius * 2.8)
      ctx.lineTo(x, y + radius * 2.8)
      ctx.stroke()
    }
  })
  ctx.restore()
}

function drawNebula(ctx: CanvasRenderingContext2D, x: number, y: number, radius: number, color: string) {
  const gradient = ctx.createRadialGradient(x, y, 0, x, y, radius)
  gradient.addColorStop(0, color)
  gradient.addColorStop(0.42, color.replace(/0\.\d+\)/, '0.08)'))
  gradient.addColorStop(1, 'rgba(0,0,0,0)')
  ctx.fillStyle = gradient
  ctx.beginPath()
  ctx.arc(x, y, radius, 0, Math.PI * 2)
  ctx.fill()
}

function drawStarRays(
  ctx: CanvasRenderingContext2D,
  x: number,
  y: number,
  length: number,
  color: string,
  alpha: number,
  time: number,
) {
  const pulse = 0.82 + Math.sin(time * 0.004) * 0.18
  ctx.save()
  ctx.translate(x, y)
  ctx.rotate(time * 0.0007)
  ctx.strokeStyle = `${color}${Math.round(alpha * 120).toString(16).padStart(2, '0')}`
  ctx.lineWidth = 1.1
  for (let i = 0; i < 4; i += 1) {
    ctx.rotate(Math.PI / 4)
    ctx.beginPath()
    ctx.moveTo(-length * pulse, 0)
    ctx.lineTo(length * pulse, 0)
    ctx.stroke()
  }
  ctx.restore()
}

function drawEdge(
  ctx: CanvasRenderingContext2D,
  edge: RelationshipGraphEdge,
  projectedById: Map<string, ProjectedNode>,
  time: number,
  hasActiveNode: boolean,
  adjacentIds: Set<string>,
  isDark: boolean,
) {
  const source = projectedById.get(edge.source)
  const target = projectedById.get(edge.target)
  if (!source || !target) return
  const active = !hasActiveNode || (adjacentIds.has(edge.source) && adjacentIds.has(edge.target))
  const color = edgeColors[edge.type] || edgeColors.relationship
  const alpha = active ? 0.28 + edge.strength * 0.45 : 0.08
  const gradient = ctx.createLinearGradient(source.screenX, source.screenY, target.screenX, target.screenY)
  gradient.addColorStop(0, `${color}${Math.round(alpha * 255).toString(16).padStart(2, '0')}`)
  gradient.addColorStop(0.5, isDark ? `#ffffff${Math.round(alpha * 160).toString(16).padStart(2, '0')}` : `${color}${Math.round(alpha * 220).toString(16).padStart(2, '0')}`)
  gradient.addColorStop(1, `${color}${Math.round(alpha * 255).toString(16).padStart(2, '0')}`)
  ctx.strokeStyle = gradient
  ctx.lineWidth = active ? 1 + edge.strength * 2.2 : 0.8
  ctx.beginPath()
  ctx.moveTo(source.screenX, source.screenY)
  ctx.lineTo(target.screenX, target.screenY)
  ctx.stroke()

  if (active) {
    const t = (Math.sin(time * 0.002 + edge.id.length) + 1) / 2
    const px = source.screenX + (target.screenX - source.screenX) * t
    const py = source.screenY + (target.screenY - source.screenY) * t
    ctx.fillStyle = color
    ctx.beginPath()
    ctx.arc(px, py, 2.2 + edge.strength * 2, 0, Math.PI * 2)
    ctx.fill()
  }
}

function EmptyGraph({ text, isDark }: { text: string; isDark: boolean }) {
  return (
    <div className={`flex h-[650px] items-center justify-center rounded-xl border border-dashed ${isDark ? 'border-gray-700 text-gray-400' : 'border-gray-200 text-gray-500'}`}>
      {text}
    </div>
  )
}

function CharacterDetailPanel({ node, edges, isDark }: { node: RelationshipGraphNode; edges: RelationshipGraphEdge[]; isDark: boolean }) {
  const relatedEdges = edges.filter((edge) => edge.source === node.id || edge.target === node.id)
  const tier = node.character.importance_tier
    ? TIER_DISPLAY_NAMES[node.character.importance_tier as CharacterImportanceTier] || node.character.importance_tier
    : node.character.role || '角色'

  return (
    <div className={`absolute bottom-4 right-4 w-96 rounded-2xl border p-4 shadow-2xl backdrop-blur ${isDark ? 'border-gray-700 bg-gray-900/92 text-gray-100' : 'border-gray-200 bg-white/92 text-gray-800'}`}>
      <div className="flex items-start gap-3">
        <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-full text-lg font-bold text-slate-950" style={{ background: node.color }}>
          {node.character.name.slice(0, 1)}
        </div>
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2">
            <h3 className="truncate text-base font-semibold">{node.character.name}</h3>
            {node.character.has_agent && <span className="rounded bg-purple-500/20 px-2 py-0.5 text-xs text-purple-300">Agent</span>}
          </div>
          <div className={`mt-1 text-xs ${isDark ? 'text-gray-400' : 'text-gray-500'}`}>
            {tier} · 优先级 {node.character.plot_priority ?? 0} · {node.character.status}
          </div>
        </div>
      </div>

      <p className={`mt-3 line-clamp-4 text-sm ${isDark ? 'text-gray-300' : 'text-gray-600'}`}>
        {node.character.description || '暂无角色描述'}
      </p>

      <div className="mt-3 grid grid-cols-2 gap-2 text-xs">
        <InfoPill label="当前位置" value={node.character.current_location || node.character.current_region_id || '未知'} isDark={isDark} />
        <InfoPill label="关系数量" value={String(relatedEdges.length)} isDark={isDark} />
      </div>

      <div className="mt-4">
        <div className={`mb-2 text-xs font-medium ${isDark ? 'text-gray-300' : 'text-gray-600'}`}>直接关系</div>
        <div className="max-h-32 space-y-1 overflow-y-auto pr-1">
          {relatedEdges.length === 0 ? (
            <div className={`text-xs ${isDark ? 'text-gray-500' : 'text-gray-400'}`}>暂无可解析关系</div>
          ) : relatedEdges.map((edge) => (
            <div key={edge.id} className={`rounded-lg px-2 py-1.5 text-xs ${isDark ? 'bg-gray-800 text-gray-300' : 'bg-gray-100 text-gray-600'}`}>
              <span className="font-medium" style={{ color: edgeColors[edge.type] }}>{edge.type}</span>
              <span className="mx-1">·</span>
              {edge.label}
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}

function InfoPill({ label, value, isDark }: { label: string; value: string; isDark: boolean }) {
  return (
    <div className={`rounded-lg px-2 py-1.5 ${isDark ? 'bg-gray-800' : 'bg-gray-100'}`}>
      <div className={`text-[10px] ${isDark ? 'text-gray-500' : 'text-gray-400'}`}>{label}</div>
      <div className="truncate text-xs font-medium">{value}</div>
    </div>
  )
}
