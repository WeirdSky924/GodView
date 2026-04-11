import { useEffect, useState, useRef } from 'react'
import { Card, Button, Input, TextArea } from '@/components/ui'
import PageLayout from '@/components/PageLayout'
import { getCharacters, getCharacter, updateCharacter } from '@/api/characters'
import type { Character, UpdateCharacterDTO } from '@/api/characters'
import { Mic2, Plus, X, Volume2, Ban, FolderOpen, Check } from 'lucide-react'
import { useTheme } from '@/contexts/ThemeContext'
import { useProject } from '@/contexts/ProjectContext'

export default function CharacterVoice() {
  const { theme } = useTheme()
  const isDark = theme === 'dark'
  const { currentProject } = useProject()

  const [characters, setCharacters] = useState<Character[]>([])
  const [selectedId, setSelectedId] = useState<string>('')
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [saved, setSaved] = useState(false)
  const [form, setForm] = useState<Character | null>(null)
  const [newLexicon, setNewLexicon] = useState('')
  const [newForbidden, setNewForbidden] = useState('')
  const [newSample, setNewSample] = useState('')

  const debounceRef = useRef<NodeJS.Timeout | null>(null)

  useEffect(() => {
    loadCharacters()
  }, [currentProject?.id])

  const loadCharacters = async () => {
    setLoading(true)
    try {
      const data = await getCharacters(currentProject?.id)
      setCharacters(data)
      // 如果当前选中的角色不在新列表中，清空选择
      if (selectedId && !data.find(c => c.id === selectedId)) {
        setSelectedId('')
        setForm(null)
      }
      if (data.length > 0 && !selectedId) {
        await selectCharacter(data[0].id || '')
      }
    } catch (error) {
      console.error('Failed to load characters:', error)
    } finally {
      setLoading(false)
    }
  }

  const selectCharacter = async (id: string) => {
    if (!id) return
    setSelectedId(id)
    try {
      const data = await getCharacter(id)
      setForm({
        ...data,
        lexicon: data.lexicon || [],
        forbidden_words: data.forbidden_words || [],
        voice_samples: data.voice_samples || [],
      })
    } catch (error) {
      console.error('Failed to load character detail:', error)
    }
  }

  // 自动保存函数
  const autoSave = async (data: Character) => {
    if (!data?.id) return
    setSaving(true)
    try {
      const payload: UpdateCharacterDTO = {
        id: data.id,
        name: data.name,
        role: data.role,
        status: data.status,
        description: data.description,
        project_id: data.project_id,
        personality: data.personality,
        appearance: data.appearance,
        background_story: data.background_story,
        speech_pattern: data.speech_pattern,
        lexicon: data.lexicon || [],
        forbidden_words: data.forbidden_words || [],
        voice_samples: data.voice_samples || [],
      }
      await updateCharacter(data.id, payload)
      setCharacters(prev => prev.map(c => c.id === data.id ? { ...c, ...payload } : c))
      setSaved(true)
      setTimeout(() => setSaved(false), 2000)
    } catch (error) {
      console.error('Failed to auto-save:', error)
    } finally {
      setSaving(false)
    }
  }

  // 说话风格变更处理（带 debounce）
  const handleSpeechPatternChange = (value: string) => {
    if (!form) return
    const updatedForm = { ...form, speech_pattern: value }
    setForm(updatedForm)

    // 清除之前的定时器
    if (debounceRef.current) {
      clearTimeout(debounceRef.current)
    }
    // 设置新的 debounce 定时器（800ms）
    debounceRef.current = setTimeout(() => {
      autoSave(updatedForm)
    }, 800)
  }

  // 组件卸载时清理定时器
  useEffect(() => {
    return () => {
      if (debounceRef.current) {
        clearTimeout(debounceRef.current)
      }
    }
  }, [])

  const addListItem = async (field: 'lexicon' | 'forbidden_words' | 'voice_samples', value: string, clear: () => void) => {
    if (!form || !value.trim()) return
    const next = [...(form[field] || []), value.trim()]
    const updatedForm = { ...form, [field]: next }
    setForm(updatedForm)
    clear()
    await autoSave(updatedForm)
  }

  const removeListItem = async (field: 'lexicon' | 'forbidden_words' | 'voice_samples', index: number) => {
    if (!form) return
    const next = [...(form[field] || [])]
    next.splice(index, 1)
    const updatedForm = { ...form, [field]: next }
    setForm(updatedForm)
    await autoSave(updatedForm)
  }

  return (
    <PageLayout
      title="角色声音管理"
      description="管理角色说话风格、常用词汇和禁用词"
      actions={
        saving ? (
          <span className={`text-sm ${isDark ? 'text-gray-400' : 'text-gray-500'}`}>保存中...</span>
        ) : saved ? (
          <span className="flex items-center gap-1 text-sm text-green-500">
            <Check size={14} /> 已保存
          </span>
        ) : null
      }
    >
      {!currentProject ? (
        <Card>
          <div className="text-center py-16">
            <FolderOpen size={48} className={`mx-auto mb-4 ${isDark ? 'text-gray-600' : 'text-gray-300'}`} />
            <p className={`text-lg ${isDark ? 'text-gray-400' : 'text-gray-500'}`}>请先选择一个项目</p>
            <p className={`mt-2 text-sm ${isDark ? 'text-gray-500' : 'text-gray-400'}`}>在左侧项目列表中选择项目后，即可管理该项目的角色声音</p>
          </div>
        </Card>
      ) : loading ? (
        <div className={`text-center py-12 ${isDark ? 'text-gray-400' : 'text-gray-500'}`}>加载角色中...</div>
      ) : characters.length === 0 ? (
        <Card>
          <div className="text-center py-16">
            <Mic2 size={48} className={`mx-auto mb-4 ${isDark ? 'text-gray-600' : 'text-gray-300'}`} />
            <p className={`text-lg ${isDark ? 'text-gray-400' : 'text-gray-500'}`}>当前项目暂无角色</p>
            <p className={`mt-2 text-sm ${isDark ? 'text-gray-500' : 'text-gray-400'}`}>请先在角色管理页面创建角色</p>
          </div>
        </Card>
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
          <Card className="lg:col-span-1">
            <h2 className={`font-semibold mb-4 ${isDark ? 'text-white' : 'text-gray-800'}`}>角色列表 ({characters.length})</h2>
            <div className="space-y-2">
              {characters.map((character) => (
                <button
                  key={character.id}
                  onClick={() => selectCharacter(character.id || '')}
                  className={`w-full text-left p-3 rounded-lg transition-colors ${
                    selectedId === character.id
                      ? 'bg-blue-900/30 text-blue-300'
                      : isDark
                        ? 'hover:bg-gray-800 text-gray-300'
                        : 'hover:bg-gray-50 text-gray-800'
                  }`}
                >
                  <p className="font-medium">{character.name}</p>
                  <p className={`text-xs mt-1 ${isDark ? 'text-gray-500' : 'text-gray-500'}`}>{character.role}</p>
                </button>
              ))}
            </div>
          </Card>

          <div className="lg:col-span-3 space-y-6">
            {!form ? (
              <Card>
                <div className={`text-center py-12 ${isDark ? 'text-gray-400' : 'text-gray-500'}`}>请选择一个角色开始配置</div>
              </Card>
            ) : (
              <>
                <Card>
                  <div className="flex items-center gap-3 mb-4">
                    <Volume2 size={20} className="text-blue-600" />
                    <h2 className={`font-semibold ${isDark ? 'text-white' : 'text-gray-800'}`}>说话风格</h2>
                  </div>
                  <TextArea
                    label="Speech Pattern"
                    value={form.speech_pattern || ''}
                    onChange={(e) => handleSpeechPatternChange(e.target.value)}
                    placeholder="例如：说话直接、带江湖气、不喜欢绕弯子..."
                    rows={4}
                  />
                </Card>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                  <Card>
                    <h2 className={`font-semibold mb-4 ${isDark ? 'text-white' : 'text-gray-800'}`}>常用词汇表</h2>
                    <div className="flex gap-2 mb-4">
                      <Input value={newLexicon} onChange={(e) => setNewLexicon(e.target.value)} placeholder="新增常用词" />
                      <Button onClick={() => addListItem('lexicon', newLexicon, () => setNewLexicon(''))}><Plus size={16} /></Button>
                    </div>
                    <div className="flex flex-wrap gap-2">
                      {(form.lexicon || []).map((item, index) => (
                        <span key={`${item}-${index}`} className={`inline-flex items-center gap-1 px-3 py-1 rounded-full text-sm ${isDark ? 'bg-blue-900 text-blue-300' : 'bg-blue-100 text-blue-700'}`}>
                          {item}
                          <button onClick={() => removeListItem('lexicon', index)}><X size={14} /></button>
                        </span>
                      ))}
                    </div>
                  </Card>

                  <Card>
                    <div className="flex items-center gap-2 mb-4">
                      <Ban size={18} className="text-red-600" />
                      <h2 className={`font-semibold ${isDark ? 'text-white' : 'text-gray-800'}`}>禁用词</h2>
                    </div>
                    <div className="flex gap-2 mb-4">
                      <Input value={newForbidden} onChange={(e) => setNewForbidden(e.target.value)} placeholder="新增禁用词" />
                      <Button onClick={() => addListItem('forbidden_words', newForbidden, () => setNewForbidden(''))}><Plus size={16} /></Button>
                    </div>
                    <div className="flex flex-wrap gap-2">
                      {(form.forbidden_words || []).map((item, index) => (
                        <span key={`${item}-${index}`} className={`inline-flex items-center gap-1 px-3 py-1 rounded-full text-sm ${isDark ? 'bg-red-900 text-red-300' : 'bg-red-100 text-red-700'}`}>
                          {item}
                          <button onClick={() => removeListItem('forbidden_words', index)}><X size={14} /></button>
                        </span>
                      ))}
                    </div>
                  </Card>
                </div>

                <Card>
                  <h2 className={`font-semibold mb-4 ${isDark ? 'text-white' : 'text-gray-800'}`}>典型台词样本</h2>
                  <div className="flex gap-2 mb-4">
                    <Input value={newSample} onChange={(e) => setNewSample(e.target.value)} placeholder="新增典型台词" />
                    <Button onClick={() => addListItem('voice_samples', newSample, () => setNewSample(''))}><Plus size={16} /></Button>
                  </div>
                  <div className="space-y-3">
                    {(form.voice_samples || []).map((item, index) => (
                      <div key={`${item}-${index}`} className={`flex items-start justify-between gap-3 p-3 rounded-lg ${isDark ? 'bg-gray-800' : 'bg-gray-50'}`}>
                        <p className={`text-sm ${isDark ? 'text-gray-300' : 'text-gray-700'}`}>{item}</p>
                        <button className={`hover:text-red-500 ${isDark ? 'text-gray-500' : 'text-gray-400'}`} onClick={() => removeListItem('voice_samples', index)}>
                          <X size={16} />
                        </button>
                      </div>
                    ))}
                  </div>
                </Card>
              </>
            )}
          </div>
        </div>
      )}
    </PageLayout>
  )
}
