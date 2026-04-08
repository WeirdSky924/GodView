import { useState, useEffect, useCallback } from 'react'
import { Card, Button, Input, TextArea, Modal } from '@/components/ui'
import PageLayout from '@/components/PageLayout'
import {
  getCharacters,
  createCharacter,
  updateCharacter,
  deleteCharacter,
  getCharacterVoiceSamples,
  addCharacterVoiceSample,
  syncCharacterVoiceSamples,
  searchCharacterVoiceSamples,
} from '@/api/characters'
import type {
  Character,
  CreateCharacterDTO,
  UpdateCharacterDTO,
  CharacterVoiceSampleSearchResult,
} from '@/api/characters'
import { Plus, Edit, Trash2, User, Mic, Search, RefreshCw, FolderOpen } from 'lucide-react'
import { useProject } from '@/contexts/ProjectContext'
import { useTheme } from '@/contexts/ThemeContext'

function splitCsvInput(value: string) {
  return value
    .split(/[，,\n]/)
    .map((item) => item.trim())
    .filter(Boolean)
}

export default function Characters() {
  const { currentProject } = useProject()
  const { theme } = useTheme()
  const isDark = theme === 'dark'

  const [characters, setCharacters] = useState<Character[]>([])
  const [showModal, setShowModal] = useState(false)
  const [editingChar, setEditingChar] = useState<Character | null>(null)
  const [loading, setLoading] = useState(true)
  const [selectedCharacterId, setSelectedCharacterId] = useState<string>('')
  const [voiceSamples, setVoiceSamples] = useState<CharacterVoiceSampleSearchResult[]>([])
  const [voiceSearchResults, setVoiceSearchResults] = useState<CharacterVoiceSampleSearchResult[]>([])
  const [voiceLoading, setVoiceLoading] = useState(false)
  const [voiceSearchLoading, setVoiceSearchLoading] = useState(false)
  const [syncingVoice, setSyncingVoice] = useState(false)
  const [voiceForm, setVoiceForm] = useState({ text: '', context: '', query: '' })

  const [formData, setFormData] = useState<CreateCharacterDTO>({
    name: '',
    role: '',
    status: 'active',
    description: '',
    speech_pattern: '',
    lexicon: [],
    forbidden_words: [],
    voice_samples: [],
  })
  const [lexiconInput, setLexiconInput] = useState('')
  const [forbiddenWordsInput, setForbiddenWordsInput] = useState('')
  const [voiceSamplesInput, setVoiceSamplesInput] = useState('')

  const loadCharacters = useCallback(async () => {
    setLoading(true)
    try {
      const data = await getCharacters(currentProject?.id)
      setCharacters(data)
      setSelectedCharacterId((current) => current || data[0]?.id || '')
    } catch (error) {
      console.error('Failed to load characters:', error)
    } finally {
      setLoading(false)
    }
  }, [currentProject?.id])

  const loadVoiceSamples = useCallback(async (characterId: string) => {
    if (!characterId) {
      setVoiceSamples([])
      return
    }

    setVoiceLoading(true)
    try {
      const data = await getCharacterVoiceSamples(characterId)
      setVoiceSamples(data)
    } catch (error) {
      console.error('Failed to load voice samples:', error)
      setVoiceSamples([])
    } finally {
      setVoiceLoading(false)
    }
  }, [])

  useEffect(() => {
    loadCharacters()
  }, [loadCharacters])

  useEffect(() => {
    if (selectedCharacterId) {
      loadVoiceSamples(selectedCharacterId)
      setVoiceSearchResults([])
    }
  }, [selectedCharacterId, loadVoiceSamples])

  const openCreateModal = () => {
    setEditingChar(null)
    setFormData({
      name: '',
      role: '',
      status: 'active',
      description: '',
      personality: '',
      appearance: '',
      background: '',
      speech_pattern: '',
      lexicon: [],
      forbidden_words: [],
      voice_samples: [],
    })
    setLexiconInput('')
    setForbiddenWordsInput('')
    setVoiceSamplesInput('')
    setShowModal(true)
  }

  const openEditModal = (character: Character) => {
    setEditingChar(character)
    setFormData({
      name: character.name,
      role: character.role,
      status: character.status,
      description: character.description,
      personality: character.personality,
      appearance: character.appearance,
      background: character.background,
      speech_pattern: character.speech_pattern,
      lexicon: character.lexicon || [],
      forbidden_words: character.forbidden_words || [],
      voice_samples: character.voice_samples || [],
    })
    setLexiconInput((character.lexicon || []).join('，'))
    setForbiddenWordsInput((character.forbidden_words || []).join('，'))
    setVoiceSamplesInput((character.voice_samples || []).join('\n'))
    setShowModal(true)
  }

  const saveCharacter = async () => {
    try {
      const normalizedData: CreateCharacterDTO = {
        ...formData,
        lexicon: splitCsvInput(lexiconInput),
        forbidden_words: splitCsvInput(forbiddenWordsInput),
        voice_samples: splitCsvInput(voiceSamplesInput),
      }

      if (editingChar?.id) {
        const updateData: UpdateCharacterDTO = {
          id: editingChar.id,
          ...normalizedData,
        }
        await updateCharacter(editingChar.id, updateData)
      } else {
        await createCharacter(normalizedData)
      }
      await loadCharacters()
      setShowModal(false)
    } catch (error) {
      console.error('Failed to save character:', error)
      alert('保存失败，请重试')
    }
  }

  const handleDelete = async (id: string | undefined) => {
    if (!id || !confirm('确定要删除这个角色吗？')) return
    try {
      await deleteCharacter(id)
      await loadCharacters()
      if (selectedCharacterId === id) {
        setSelectedCharacterId('')
        setVoiceSamples([])
        setVoiceSearchResults([])
      }
    } catch (error) {
      console.error('Failed to delete character:', error)
    }
  }

  const handleAddVoiceSample = async () => {
    if (!selectedCharacterId || !voiceForm.text.trim()) return

    try {
      await addCharacterVoiceSample(selectedCharacterId, {
        id: `${selectedCharacterId}_${Date.now()}`,
        character_id: selectedCharacterId,
        text: voiceForm.text.trim(),
        context: voiceForm.context.trim(),
      })
      setVoiceForm((prev) => ({ ...prev, text: '', context: '' }))
      await loadVoiceSamples(selectedCharacterId)
      await loadCharacters()
    } catch (error) {
      console.error('Failed to add voice sample:', error)
      alert('声音样本添加失败')
    }
  }

  const handleSyncVoiceSamples = async () => {
    if (!selectedCharacterId) return

    setSyncingVoice(true)
    try {
      await syncCharacterVoiceSamples(selectedCharacterId)
      await loadVoiceSamples(selectedCharacterId)
    } catch (error) {
      console.error('Failed to sync voice samples:', error)
      alert('声音样本同步失败')
    } finally {
      setSyncingVoice(false)
    }
  }

  const handleSearchVoiceSamples = async () => {
    if (!selectedCharacterId || !voiceForm.query.trim()) return

    setVoiceSearchLoading(true)
    try {
      const results = await searchCharacterVoiceSamples(selectedCharacterId, voiceForm.query.trim())
      setVoiceSearchResults(results)
    } catch (error) {
      console.error('Failed to search voice samples:', error)
      alert('声音样本检索失败')
    } finally {
      setVoiceSearchLoading(false)
    }
  }

  const selectedCharacter = characters.find((char) => char.id === selectedCharacterId)

  return (
    <PageLayout
      title="角色管理"
      description="管理小说中的角色信息和声音样本"
      actions={
        <Button onClick={openCreateModal} disabled={!currentProject}>
          <Plus size={18} className="mr-2" />
          新增角色
        </Button>
      }
    >
      {!currentProject ? (
        <div className={`text-center py-20 ${isDark ? 'text-gray-400' : 'text-gray-500'}`}>
          <FolderOpen size={48} className="mx-auto mb-4 opacity-50" />
          <p>请先在侧边栏选择一个项目</p>
        </div>
      ) : loading ? (
        <p className={`text-center py-12 ${isDark ? 'text-gray-400' : 'text-gray-500'}`}>加载中...</p>
      ) : (
        <div className="grid grid-cols-1 xl:grid-cols-[2fr,1fr] gap-6">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            {characters.length === 0 ? (
              <div className={`col-span-full text-center py-12 ${isDark ? 'text-gray-400' : 'text-gray-500'}`}>
                暂无角色，点击"新增角色"开始创建
              </div>
            ) : (
              characters.map((char) => (
                <Card
                  key={char.id}
                  className={`transition-shadow ${selectedCharacterId === char.id ? 'ring-2 ring-blue-500' : ''}`}
                >
                  <div className="flex items-start gap-4">
                    <div className="w-16 h-16 bg-gradient-to-br from-blue-400 to-purple-500 rounded-lg flex items-center justify-center text-white text-2xl">
                      <User size={24} />
                    </div>
                    <div className="flex-1 min-w-0 cursor-pointer" onClick={() => setSelectedCharacterId(char.id || '')}>
                      <h3 className={`font-semibold text-lg truncate ${isDark ? 'text-white' : 'text-gray-800'}`}>{char.name}</h3>
                      <p className={`text-sm mt-1 ${isDark ? 'text-gray-400' : 'text-gray-500'}`}>{char.role}</p>
                      <p className={`text-sm mt-2 line-clamp-2 ${isDark ? 'text-gray-300' : 'text-gray-600'}`}>{char.description}</p>
                      <div className="mt-3 flex flex-wrap gap-2">
                        <span className={`inline-block px-2 py-1 text-xs rounded ${
                          char.status === 'active' ? 'bg-green-900 text-green-300' :
                          char.status === 'inactive' ? (isDark ? 'bg-gray-700 text-gray-300' : 'bg-gray-200 text-gray-700') :
                          'bg-red-900 text-red-300'
                        }`}>
                          {char.status === 'active' ? '活跃' : char.status === 'inactive' ? '不活跃' : '已故'}
                        </span>
                        <span className={`inline-block px-2 py-1 text-xs rounded ${isDark ? 'bg-blue-900 text-blue-300' : 'bg-blue-100 text-blue-700'}`}>
                          声音样本 {char.voice_samples?.length || 0}
                        </span>
                      </div>
                    </div>
                  </div>
                  <div className={`flex gap-2 mt-4 pt-4 ${isDark ? 'border-gray-700' : 'border-gray-200'} border-t`}>
                    <Button variant="secondary" size="sm" onClick={() => openEditModal(char)}>
                      <Edit size={14} className="mr-1" /> 编辑
                    </Button>
                    <Button variant="danger" size="sm" onClick={() => handleDelete(char.id)}>
                      <Trash2 size={14} className="mr-1" /> 删除
                    </Button>
                  </div>
                </Card>
              ))
            )}
          </div>

          <Card>
            <div className="flex items-center justify-between mb-4">
              <div className="flex items-center gap-2">
                <Mic size={18} className={isDark ? 'text-gray-400' : 'text-gray-500'} />
                <h2 className={`text-lg font-semibold ${isDark ? 'text-white' : 'text-gray-800'}`}>声音样本</h2>
              </div>
              <Button
                variant="secondary"
                size="sm"
                onClick={handleSyncVoiceSamples}
                disabled={!selectedCharacterId || syncingVoice}
              >
                <RefreshCw size={14} className="mr-1" />
                {syncingVoice ? '同步中' : '同步向量'}
              </Button>
            </div>

            {!selectedCharacter ? (
              <p className={`text-sm ${isDark ? 'text-gray-400' : 'text-gray-500'}`}>请选择左侧角色后查看和管理声音样本。</p>
            ) : (
              <div className="space-y-4">
                <div className={`rounded-lg p-3 text-sm ${isDark ? 'bg-gray-800 text-gray-300' : 'bg-gray-50 text-gray-700'}`}>
                  <div><span className="font-medium">当前角色：</span>{selectedCharacter.name}</div>
                  <div className="mt-1"><span className="font-medium">说话风格：</span>{selectedCharacter.speech_pattern || '未设置'}</div>
                </div>

                <TextArea
                  label="新增台词样本"
                  value={voiceForm.text}
                  onChange={(e) => setVoiceForm((prev) => ({ ...prev, text: e.target.value }))}
                  placeholder="输入能代表该角色语言风格的典型台词"
                />
                <Input
                  label="样本上下文"
                  value={voiceForm.context}
                  onChange={(e) => setVoiceForm((prev) => ({ ...prev, context: e.target.value }))}
                  placeholder="如：争吵场景、初次见面、自言自语"
                />
                <Button onClick={handleAddVoiceSample} disabled={!voiceForm.text.trim()}>
                  添加声音样本
                </Button>

                <div className={`pt-4 ${isDark ? 'border-gray-700' : 'border-gray-200'} border-t`}>
                  <div className="flex gap-2">
                    <Input
                      label="语义检索"
                      value={voiceForm.query}
                      onChange={(e) => setVoiceForm((prev) => ({ ...prev, query: e.target.value }))}
                      placeholder="输入一句待对比台词"
                    />
                    <div className="flex items-end">
                      <Button onClick={handleSearchVoiceSamples} disabled={!voiceForm.query.trim() || voiceSearchLoading}>
                        <Search size={14} className="mr-1" />
                        {voiceSearchLoading ? '检索中' : '检索'}
                      </Button>
                    </div>
                  </div>
                </div>

                <div>
                  <h3 className={`text-sm font-medium mb-2 ${isDark ? 'text-gray-300' : 'text-gray-700'}`}>已存样本</h3>
                  {voiceLoading ? (
                    <p className={`text-sm ${isDark ? 'text-gray-400' : 'text-gray-500'}`}>加载中...</p>
                  ) : voiceSamples.length === 0 ? (
                    <p className={`text-sm ${isDark ? 'text-gray-400' : 'text-gray-500'}`}>暂无声音样本</p>
                  ) : (
                    <div className="space-y-2 max-h-64 overflow-auto">
                      {voiceSamples.map((sample) => (
                        <div key={sample.id} className={`rounded border p-3 text-sm ${isDark ? 'border-gray-700' : 'border-gray-200'}`}>
                          <div className={isDark ? 'text-gray-200' : 'text-gray-800'}>{sample.payload.text}</div>
                          {sample.payload.context ? (
                            <div className={`mt-1 text-xs ${isDark ? 'text-gray-500' : 'text-gray-400'}`}>上下文：{sample.payload.context}</div>
                          ) : null}
                        </div>
                      ))}
                    </div>
                  )}
                </div>

                <div>
                  <h3 className={`text-sm font-medium mb-2 ${isDark ? 'text-gray-300' : 'text-gray-700'}`}>检索结果</h3>
                  {voiceSearchResults.length === 0 ? (
                    <p className={`text-sm ${isDark ? 'text-gray-400' : 'text-gray-500'}`}>暂无检索结果</p>
                  ) : (
                    <div className="space-y-2 max-h-56 overflow-auto">
                      {voiceSearchResults.map((sample) => (
                        <div key={sample.id} className="rounded border border-blue-500/30 bg-blue-900/20 p-3 text-sm">
                          <div className="flex items-center justify-between gap-3">
                            <span className={isDark ? 'text-gray-200' : 'text-gray-800'}>{sample.payload.text}</span>
                            <span className="text-xs text-blue-400">相似度 {sample.score.toFixed(3)}</span>
                          </div>
                          {sample.payload.context ? (
                            <div className={`mt-1 text-xs ${isDark ? 'text-gray-500' : 'text-gray-400'}`}>上下文：{sample.payload.context}</div>
                          ) : null}
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            )}
          </Card>
        </div>
      )}

      <Modal
        isOpen={showModal}
        onClose={() => setShowModal(false)}
        title={editingChar ? '编辑角色' : '新建角色'}
        size="lg"
      >
        <div className="space-y-4">
          <Input
            label="角色名称 *"
            value={formData.name}
            onChange={(e) => setFormData({ ...formData, name: e.target.value })}
            placeholder="输入角色名称"
          />
          <div className="grid grid-cols-2 gap-4">
            <Input
              label="角色定位"
              value={formData.role}
              onChange={(e) => setFormData({ ...formData, role: e.target.value })}
              placeholder="如：主角 / 反派 / 配角"
            />
            <div>
              <label className={`block text-sm font-medium mb-1 ${isDark ? 'text-gray-300' : 'text-gray-700'}`}>状态</label>
              <select
                className={`w-full px-3 py-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 ${isDark ? 'bg-gray-800 border-gray-600 text-white' : 'bg-white border-gray-300 text-gray-800'}`}
                value={formData.status}
                onChange={(e) => setFormData({ ...formData, status: e.target.value as Character['status'] })}
              >
                <option value="active">活跃</option>
                <option value="inactive">不活跃</option>
                <option value="deceased">已故</option>
              </select>
            </div>
          </div>
          <TextArea
            label="角色描述 *"
            value={formData.description}
            onChange={(e) => setFormData({ ...formData, description: e.target.value })}
            placeholder="描述角色的基本情况..."
          />
          <TextArea
            label="性格特点"
            value={formData.personality || ''}
            onChange={(e) => setFormData({ ...formData, personality: e.target.value })}
            placeholder="描述角色的性格、习惯、口头禅等..."
          />
          <TextArea
            label="说话风格"
            value={formData.speech_pattern || ''}
            onChange={(e) => setFormData({ ...formData, speech_pattern: e.target.value })}
            placeholder="如：简短凌厉、爱反问、喜欢古风措辞"
          />
          <Input
            label="常用词汇"
            value={lexiconInput}
            onChange={(e) => setLexiconInput(e.target.value)}
            placeholder="用逗号分隔，如：江湖，义气，动手"
          />
          <Input
            label="禁用词"
            value={forbiddenWordsInput}
            onChange={(e) => setForbiddenWordsInput(e.target.value)}
            placeholder="用逗号分隔，如：斟酌，考量，之乎者也"
          />
          <TextArea
            label="预置声音样本"
            value={voiceSamplesInput}
            onChange={(e) => setVoiceSamplesInput(e.target.value)}
            placeholder="每行一条典型台词"
          />
          <div className="flex justify-end gap-3 pt-4">
            <Button variant="secondary" onClick={() => setShowModal(false)}>取消</Button>
            <Button onClick={saveCharacter}>{editingChar ? '保存修改' : '创建角色'}</Button>
          </div>
        </div>
      </Modal>
    </PageLayout>
  )
}
