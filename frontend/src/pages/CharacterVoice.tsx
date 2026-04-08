import { useEffect, useState } from 'react'
import { Card, Button, Input, TextArea } from '@/components/ui'
import PageLayout from '@/components/PageLayout'
import { getCharacters, getCharacter, updateCharacter } from '@/api/characters'
import type { Character, UpdateCharacterDTO } from '@/api/characters'
import { Mic2, Plus, X, Volume2, Ban } from 'lucide-react'
import { useTheme } from '@/contexts/ThemeContext'

export default function CharacterVoice() {
  const { theme } = useTheme()
  const isDark = theme === 'dark'

  const [characters, setCharacters] = useState<Character[]>([])
  const [selectedId, setSelectedId] = useState<string>('')
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [form, setForm] = useState<Character | null>(null)
  const [newLexicon, setNewLexicon] = useState('')
  const [newForbidden, setNewForbidden] = useState('')
  const [newSample, setNewSample] = useState('')

  useEffect(() => {
    loadCharacters()
  }, [])

  const loadCharacters = async () => {
    try {
      const data = await getCharacters()
      setCharacters(data)
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

  const saveVoiceConfig = async () => {
    if (!form?.id) return
    setSaving(true)
    try {
      const payload: UpdateCharacterDTO = {
        id: form.id,
        name: form.name,
        role: form.role,
        status: form.status,
        description: form.description,
        personality: form.personality,
        appearance: form.appearance,
        background: form.background,
        speech_pattern: form.speech_pattern,
        lexicon: form.lexicon || [],
        forbidden_words: form.forbidden_words || [],
        voice_samples: form.voice_samples || [],
      }
      await updateCharacter(form.id, payload)
      await selectCharacter(form.id)
      alert('角色声音配置已保存')
    } catch (error) {
      console.error('Failed to save voice config:', error)
      alert('保存失败，请重试')
    } finally {
      setSaving(false)
    }
  }

  const addListItem = (field: 'lexicon' | 'forbidden_words' | 'voice_samples', value: string, clear: () => void) => {
    if (!form || !value.trim()) return
    const next = [...(form[field] || []), value.trim()]
    setForm({ ...form, [field]: next })
    clear()
  }

  const removeListItem = (field: 'lexicon' | 'forbidden_words' | 'voice_samples', index: number) => {
    if (!form) return
    const next = [...(form[field] || [])]
    next.splice(index, 1)
    setForm({ ...form, [field]: next })
  }

  return (
    <PageLayout
      title="角色声音管理"
      description="管理角色说话风格、常用词汇和禁用词"
      actions={
        <Button onClick={saveVoiceConfig} loading={saving} disabled={!form}>
          <Mic2 size={18} className="mr-2" />保存声音配置
        </Button>
      }
    >
      {loading ? (
        <div className={`text-center py-12 ${isDark ? 'text-gray-400' : 'text-gray-500'}`}>加载角色中...</div>
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
          <Card className="lg:col-span-1">
            <h2 className={`font-semibold mb-4 ${isDark ? 'text-white' : 'text-gray-800'}`}>角色列表</h2>
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
                    onChange={(e) => setForm({ ...form, speech_pattern: e.target.value })}
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
