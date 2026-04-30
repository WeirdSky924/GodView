import { useMemo, useState } from 'react'
import { GitBranch, Plus, Trash2, Edit3, ArrowRight, AlertTriangle } from 'lucide-react'
import { Button, Input, TextArea } from '@/components/ui'
import type { Character } from '@/api/characters'

interface CharacterRelationshipEditorProps {
  characters: Character[]
  currentCharacterId?: string
  currentCharacterName: string
  value: Record<string, string>
  legacyRelationships?: string[]
  onChange: (next: Record<string, string>) => void
  onLegacyRelationshipsChange?: (next: string[]) => void
  isDark: boolean
}

const relationPresets = ['盟友', '宿敌', '家人', '师徒', '恋人', '竞争对手', '雇佣', '暗中保护', '欠债', '怀疑']

function splitLegacyRelationships(value: string) {
  return value
    .split('\n')
    .map((item) => item.trim())
    .filter(Boolean)
}

export default function CharacterRelationshipEditor({
  characters,
  currentCharacterId,
  currentCharacterName,
  value,
  legacyRelationships = [],
  onChange,
  onLegacyRelationshipsChange,
  isDark,
}: CharacterRelationshipEditorProps) {
  const [selectedTargetId, setSelectedTargetId] = useState('')
  const [relationshipText, setRelationshipText] = useState('')
  const [legacyInput, setLegacyInput] = useState(legacyRelationships.join('\n'))

  const currentCharacterKey = currentCharacterId || '__current__'
  const candidateCharacters = useMemo(
    () => characters.filter((character) => character.id && character.id !== currentCharacterId),
    [characters, currentCharacterId],
  )
  const characterById = useMemo(
    () => new Map(characters.filter((character) => character.id).map((character) => [character.id as string, character])),
    [characters],
  )

  const entries = useMemo(() => Object.entries(value || {}).filter(([, relation]) => relation?.trim()), [value])
  const resolvedEntries = entries.filter(([targetId]) => characterById.has(targetId))
  const unresolvedEntries = entries.filter(([targetId]) => !characterById.has(targetId))
  const incomingEntries = useMemo(() => {
    if (!currentCharacterId) return []
    return characters.flatMap((character) => {
      if (!character.id || character.id === currentCharacterId) return []
      const relation = character.key_relationships?.[currentCharacterId]
      return relation ? [{ source: character, relation }] : []
    })
  }, [characters, currentCharacterId])

  const graphNodes = useMemo(() => {
    const maxNodes = Math.min(candidateCharacters.length, 16)
    return candidateCharacters.slice(0, maxNodes).map((character, index) => {
      const angle = (index / Math.max(1, maxNodes)) * Math.PI * 2 - Math.PI / 2
      const radius = 118
      return {
        character,
        x: 180 + Math.cos(angle) * radius,
        y: 150 + Math.sin(angle) * radius,
        hasOutgoing: Boolean(character.id && value?.[character.id]),
        hasIncoming: Boolean(currentCharacterId && character.key_relationships?.[currentCharacterId]),
      }
    })
  }, [candidateCharacters, currentCharacterId, value])

  const selectTarget = (targetId: string) => {
    setSelectedTargetId(targetId)
    setRelationshipText(value?.[targetId] || '')
  }

  const upsertRelationship = () => {
    const targetId = selectedTargetId.trim()
    const relation = relationshipText.trim()
    if (!targetId || !relation || targetId === currentCharacterId) return
    onChange({ ...(value || {}), [targetId]: relation })
  }

  const removeRelationship = (targetId: string) => {
    const next = { ...(value || {}) }
    delete next[targetId]
    onChange(next)
    if (selectedTargetId === targetId) {
      setSelectedTargetId('')
      setRelationshipText('')
    }
  }

  const updateLegacyRelationships = (nextValue: string) => {
    setLegacyInput(nextValue)
    onLegacyRelationshipsChange?.(splitLegacyRelationships(nextValue))
  }

  const selectedName = selectedTargetId ? characterById.get(selectedTargetId)?.name || selectedTargetId : '未选择'

  return (
    <div className="space-y-4">
      <div className={`rounded-lg p-4 ${isDark ? 'bg-blue-950/30 border border-blue-800/40' : 'bg-blue-50 border border-blue-100'}`}>
        <div className={`flex items-start gap-2 text-sm ${isDark ? 'text-blue-200' : 'text-blue-700'}`}>
          <GitBranch size={16} className="mt-0.5 flex-shrink-0" />
          <p>
            当前编辑的是 <span className="font-semibold">{currentCharacterName || '当前角色'}</span> 指向其他角色的出向关系；不会自动生成反向关系。3D 关系图优先读取这些结构化关系。
          </p>
        </div>
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-[1.1fr,0.9fr]">
        <div className={`rounded-xl border p-3 ${isDark ? 'border-gray-700 bg-gray-900/60' : 'border-gray-200 bg-white'}`}>
          <div className={`mb-2 text-sm font-medium ${isDark ? 'text-gray-200' : 'text-gray-700'}`}>关系图预览</div>
          <div className="relative h-[310px] overflow-hidden rounded-lg bg-gradient-to-br from-slate-950 via-blue-950 to-purple-950">
            <svg viewBox="0 0 360 300" className="h-full w-full">
              <defs>
                <radialGradient id="relationshipCenterGlow" cx="50%" cy="50%" r="50%">
                  <stop offset="0%" stopColor="#fef3c7" stopOpacity="0.95" />
                  <stop offset="52%" stopColor="#60a5fa" stopOpacity="0.5" />
                  <stop offset="100%" stopColor="#60a5fa" stopOpacity="0" />
                </radialGradient>
              </defs>
              <circle cx="60" cy="42" r="1.2" fill="#fff" opacity="0.8" />
              <circle cx="312" cy="68" r="1.5" fill="#bfdbfe" opacity="0.7" />
              <circle cx="86" cy="236" r="1" fill="#ddd6fe" opacity="0.85" />
              <circle cx="288" cy="236" r="1.2" fill="#fff" opacity="0.75" />

              {graphNodes.map((node) => (
                <g key={`edge-${node.character.id}`}>
                  {node.hasOutgoing && (
                    <line x1="180" y1="150" x2={node.x} y2={node.y} stroke="#facc15" strokeWidth="2" opacity="0.9" />
                  )}
                  {node.hasIncoming && (
                    <line x1={node.x} y1={node.y} x2="180" y2="150" stroke="#38bdf8" strokeWidth="1.5" strokeDasharray="5 4" opacity="0.55" />
                  )}
                </g>
              ))}

              <circle cx="180" cy="150" r="46" fill="url(#relationshipCenterGlow)" />
              <circle cx="180" cy="150" r="25" fill="#facc15" stroke="#fff7ed" strokeWidth="2" />
              <text x="180" y="155" textAnchor="middle" fontSize="12" fontWeight="700" fill="#111827">
                {currentCharacterName.slice(0, 4) || '当前'}
              </text>

              {graphNodes.map((node) => {
                const selected = selectedTargetId === node.character.id
                return (
                  <g key={node.character.id} onClick={() => node.character.id && selectTarget(node.character.id)} className="cursor-pointer">
                    <circle
                      cx={node.x}
                      cy={node.y}
                      r={selected ? 18 : node.hasOutgoing ? 15 : 12}
                      fill={node.hasOutgoing ? '#facc15' : node.hasIncoming ? '#38bdf8' : '#94a3b8'}
                      opacity={selected ? 1 : 0.9}
                      stroke={selected ? '#ffffff' : 'rgba(255,255,255,0.65)'}
                      strokeWidth={selected ? 3 : 1.5}
                    />
                    <text x={node.x} y={node.y + 4} textAnchor="middle" fontSize="10" fontWeight="700" fill="#0f172a">
                      {node.character.name.slice(0, 2)}
                    </text>
                    <text x={node.x} y={node.y + 28} textAnchor="middle" fontSize="10" fill="#e5e7eb">
                      {node.character.name.slice(0, 6)}
                    </text>
                  </g>
                )
              })}
            </svg>
            {candidateCharacters.length > graphNodes.length && (
              <div className="absolute bottom-2 left-2 rounded bg-black/40 px-2 py-1 text-xs text-slate-300">
                预览显示前 {graphNodes.length} 个角色，其余可在右侧下拉选择
              </div>
            )}
          </div>
          <div className="mt-2 flex flex-wrap gap-3 text-xs text-gray-400">
            <span className="inline-flex items-center gap-1"><span className="h-2 w-4 rounded bg-yellow-400" />出向关系</span>
            <span className="inline-flex items-center gap-1"><span className="h-2 w-4 rounded border border-sky-400" />只读入向关系</span>
          </div>
        </div>

        <div className={`rounded-xl border p-3 ${isDark ? 'border-gray-700 bg-gray-900/60' : 'border-gray-200 bg-gray-50'}`}>
          <div className={`mb-3 text-sm font-medium ${isDark ? 'text-gray-200' : 'text-gray-700'}`}>编辑关系</div>
          <div className="space-y-3">
            <div>
              <label className={`mb-1 block text-sm font-medium ${isDark ? 'text-gray-300' : 'text-gray-700'}`}>目标角色</label>
              <select
                value={selectedTargetId}
                onChange={(event) => selectTarget(event.target.value)}
                className={`w-full rounded-lg border px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 ${isDark ? 'border-gray-600 bg-gray-800 text-white' : 'border-gray-300 bg-white text-gray-800'}`}
              >
                <option value="">选择目标角色</option>
                {candidateCharacters.map((character) => (
                  <option key={character.id} value={character.id}>{character.name}</option>
                ))}
              </select>
            </div>

            <Input
              label={`关系描述：${selectedName}`}
              value={relationshipText}
              onChange={(event) => setRelationshipText(event.target.value)}
              placeholder="如：导师、宿敌、盟友、暗中保护"
            />

            <div className="flex flex-wrap gap-2">
              {relationPresets.map((preset) => (
                <button
                  key={preset}
                  type="button"
                  onClick={() => setRelationshipText(preset)}
                  className={`rounded-full px-2.5 py-1 text-xs transition-colors ${isDark ? 'bg-gray-800 text-gray-300 hover:bg-blue-900/60' : 'bg-white text-gray-600 hover:bg-blue-50'}`}
                >
                  {preset}
                </button>
              ))}
            </div>

            <div className="flex gap-2">
              <Button onClick={upsertRelationship} disabled={!selectedTargetId || !relationshipText.trim()}>
                <Plus size={14} className="mr-1" />
                {selectedTargetId && value?.[selectedTargetId] ? '更新关系' : '添加关系'}
              </Button>
              <Button variant="secondary" onClick={() => selectedTargetId && removeRelationship(selectedTargetId)} disabled={!selectedTargetId || !value?.[selectedTargetId]}>
                <Trash2 size={14} className="mr-1" />删除
              </Button>
            </div>
          </div>
        </div>
      </div>

      <div className={`rounded-xl border p-3 ${isDark ? 'border-gray-700 bg-gray-900/50' : 'border-gray-200 bg-white'}`}>
        <div className={`mb-2 text-sm font-medium ${isDark ? 'text-gray-200' : 'text-gray-700'}`}>已建立关系</div>
        {resolvedEntries.length === 0 ? (
          <p className={`text-sm ${isDark ? 'text-gray-500' : 'text-gray-400'}`}>暂无结构化关系</p>
        ) : (
          <div className="space-y-2">
            {resolvedEntries.map(([targetId, relation]) => {
              const target = characterById.get(targetId)
              return (
                <div key={targetId} className={`flex items-center justify-between gap-3 rounded-lg border px-3 py-2 text-sm ${isDark ? 'border-gray-700 bg-gray-800/70 text-gray-200' : 'border-gray-200 bg-gray-50 text-gray-700'}`}>
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-2">
                      <span className="font-medium">{currentCharacterName || '当前角色'}</span>
                      <ArrowRight size={14} className={isDark ? 'text-gray-500' : 'text-gray-400'} />
                      <span className="font-medium">{target?.name || targetId}</span>
                    </div>
                    <div className={`mt-1 truncate text-xs ${isDark ? 'text-gray-400' : 'text-gray-500'}`}>{relation}</div>
                  </div>
                  <div className="flex gap-2">
                    <button type="button" onClick={() => selectTarget(targetId)} className={`rounded p-1.5 ${isDark ? 'hover:bg-gray-700' : 'hover:bg-gray-200'}`}>
                      <Edit3 size={14} />
                    </button>
                    <button type="button" onClick={() => removeRelationship(targetId)} className={`rounded p-1.5 text-red-400 ${isDark ? 'hover:bg-red-950/50' : 'hover:bg-red-50'}`}>
                      <Trash2 size={14} />
                    </button>
                  </div>
                </div>
              )
            })}
          </div>
        )}
      </div>

      {unresolvedEntries.length > 0 && (
        <div className={`rounded-xl border p-3 ${isDark ? 'border-amber-700/50 bg-amber-950/20' : 'border-amber-200 bg-amber-50'}`}>
          <div className={`mb-2 flex items-center gap-2 text-sm font-medium ${isDark ? 'text-amber-200' : 'text-amber-700'}`}>
            <AlertTriangle size={15} />未解析关系
          </div>
          <div className="space-y-2">
            {unresolvedEntries.map(([targetId, relation]) => (
              <div key={targetId} className={`flex items-center justify-between gap-3 rounded-lg px-3 py-2 text-sm ${isDark ? 'bg-gray-900/60 text-gray-300' : 'bg-white text-gray-700'}`}>
                <div className="min-w-0">
                  <div className="font-mono text-xs">{targetId}</div>
                  <div className={`mt-1 text-xs ${isDark ? 'text-gray-400' : 'text-gray-500'}`}>{relation}</div>
                </div>
                <Button variant="secondary" size="sm" onClick={() => removeRelationship(targetId)}>删除</Button>
              </div>
            ))}
          </div>
          <p className={`mt-2 text-xs ${isDark ? 'text-amber-200/70' : 'text-amber-700/70'}`}>这些 key 无法匹配当前项目角色 ID，已保留以避免旧数据丢失；可手动删除后重新添加为标准关系。</p>
        </div>
      )}

      {incomingEntries.length > 0 && (
        <div className={`rounded-xl border p-3 ${isDark ? 'border-sky-800/50 bg-sky-950/20' : 'border-sky-100 bg-sky-50'}`}>
          <div className={`mb-2 text-sm font-medium ${isDark ? 'text-sky-200' : 'text-sky-700'}`}>只读入向关系</div>
          <div className="space-y-1 text-sm">
            {incomingEntries.map(({ source, relation }) => (
              <div key={source.id} className={isDark ? 'text-gray-300' : 'text-gray-600'}>
                {source.name} → {currentCharacterName || '当前角色'}：{relation}
              </div>
            ))}
          </div>
        </div>
      )}

      <TextArea
        label="关系摘要 / 旧字段"
        value={legacyInput}
        onChange={(event) => updateLegacyRelationships(event.target.value)}
        placeholder="每行一条文字摘要；例如：林默与 K 是 AI 导师与战斗搭档"
        rows={4}
      />
      <p className={`text-xs ${isDark ? 'text-gray-500' : 'text-gray-400'}`}>
        上方结构化关系用于 3D 关系图和图上下文；这里保存为 relationships，用于补充文字摘要和兼容旧数据。
      </p>
    </div>
  )
}
