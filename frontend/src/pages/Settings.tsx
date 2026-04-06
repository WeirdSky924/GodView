import { useEffect, useState } from 'react'
import { Card, Button, Input } from '@/components/ui'
import {
  getEmbeddingProviders,
  updateEmbeddingConfig,
  testEmbeddingConfig,
  getEmbeddingConfig,
  getLLMProviders,
  getLLMConfig,
  updateLLMConfig,
  testLLMConfig,
} from '@/api/config'
import { Check, RefreshCw } from 'lucide-react'

export default function Settings() {
  const [embeddingProviders, setEmbeddingProviders] = useState<any[]>([])
  const [llmProviders, setLlmProviders] = useState<any[]>([])
  const [embeddingConfig, setEmbeddingConfig] = useState({
    provider: 'sentence_transformers',
    model: '',
    api_key: '',
    base_url: '',
    dimension: 0,
  })
  const [llmConfig, setLlmConfig] = useState({
    provider: 'openai',
    model: '',
    api_key: '',
    base_url: '',
    temperature: 0.7,
    max_tokens: 4096,
  })
  const [loading, setLoading] = useState(true)
  const [testingEmbedding, setTestingEmbedding] = useState(false)
  const [testingLLM, setTestingLLM] = useState(false)
  const [embeddingResult, setEmbeddingResult] = useState<{ success?: boolean; message?: string } | null>(null)
  const [llmResult, setLlmResult] = useState<{ success?: boolean; message?: string } | null>(null)

  useEffect(() => {
    loadSettings()
  }, [])

  const loadSettings = async () => {
    try {
      const [embeddingProvidersData, embeddingConfigData, llmProvidersData, llmConfigData] = await Promise.all([
        getEmbeddingProviders(),
        getEmbeddingConfig(),
        getLLMProviders(),
        getLLMConfig(),
      ])
      setEmbeddingProviders(embeddingProvidersData)
      setEmbeddingConfig(embeddingConfigData)
      setLlmProviders(llmProvidersData)
      setLlmConfig(llmConfigData)
    } catch (error) {
      console.error('Failed to load settings:', error)
    } finally {
      setLoading(false)
    }
  }

  const handleEmbeddingTest = async () => {
    setTestingEmbedding(true)
    setEmbeddingResult(null)
    try {
      setEmbeddingResult(await testEmbeddingConfig(embeddingConfig))
    } catch (error) {
      setEmbeddingResult({ success: false, message: String(error) })
    } finally {
      setTestingEmbedding(false)
    }
  }

  const handleLLMTest = async () => {
    setTestingLLM(true)
    setLlmResult(null)
    try {
      setLlmResult(await testLLMConfig(llmConfig))
    } catch (error) {
      setLlmResult({ success: false, message: String(error) })
    } finally {
      setTestingLLM(false)
    }
  }

  const handleEmbeddingSave = async () => {
    await updateEmbeddingConfig(embeddingConfig)
    await handleEmbeddingTest()
  }

  const handleLLMSave = async () => {
    await updateLLMConfig(llmConfig)
    await handleLLMTest()
  }

  const selectEmbeddingProvider = (provider: any) => {
    setEmbeddingConfig((prev) => ({
      ...prev,
      provider: provider.id,
      model: provider.default_model,
      base_url: provider.default_url,
      dimension: provider.default_dimension,
    }))
  }

  const selectLLMProvider = (provider: any) => {
    setLlmConfig((prev) => ({
      ...prev,
      provider: provider.id,
      model: provider.default_model,
      base_url: provider.default_url,
    }))
  }

  return (
    <div>
      <h1 className="text-3xl font-bold text-gray-800 mb-8">⚙️ 系统设置</h1>

      {loading ? (
        <p className="text-center text-gray-500 py-12">加载中...</p>
      ) : (
        <div className="space-y-6">
          <Card title="Embedding 服务配置" description="用于向量检索和语义相似度计算">
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">选择服务类型</label>
                <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                  {embeddingProviders.map((p) => (
                    <button
                      key={p.id}
                      onClick={() => selectEmbeddingProvider(p)}
                      className={`p-4 border-2 rounded-lg text-left transition-all ${embeddingConfig.provider === p.id ? 'border-blue-500 bg-blue-50' : 'border-gray-200 hover:border-gray-300'}`}
                    >
                      <div className="flex items-center justify-between">
                        <span className="font-medium">{p.name}</span>
                        {embeddingConfig.provider === p.id && <Check size={18} className="text-blue-500" />}
                      </div>
                      <p className="text-xs text-gray-500 mt-1">{p.description}</p>
                    </button>
                  ))}
                </div>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <Input label="模型名称" value={embeddingConfig.model} onChange={(e) => setEmbeddingConfig({ ...embeddingConfig, model: e.target.value })} />
                <Input label="向量维度" type="number" value={String(embeddingConfig.dimension)} onChange={(e) => setEmbeddingConfig({ ...embeddingConfig, dimension: parseInt(e.target.value, 10) || 0 })} />
              </div>

              <Input label="API Key" type="password" value={embeddingConfig.api_key} onChange={(e) => setEmbeddingConfig({ ...embeddingConfig, api_key: e.target.value })} />
              <Input label="基础 URL" value={embeddingConfig.base_url} onChange={(e) => setEmbeddingConfig({ ...embeddingConfig, base_url: e.target.value })} />

              {embeddingResult && <div className={`p-4 rounded-lg ${embeddingResult.success ? 'bg-green-50 text-green-800' : 'bg-red-50 text-red-800'}`}>{embeddingResult.message}</div>}

              <div className="flex gap-3 pt-4">
                <Button onClick={handleEmbeddingTest} loading={testingEmbedding}>
                  <RefreshCw size={18} className={`mr-2 ${testingEmbedding ? 'animate-spin' : ''}`} />测试连接
                </Button>
                <Button onClick={handleEmbeddingSave}>保存配置</Button>
              </div>
            </div>
          </Card>

          <Card title="LLM 模型配置" description="用于剧情生成、角色对话与导演流程">
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">选择 LLM Provider</label>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                  {llmProviders.map((p) => (
                    <button
                      key={p.id}
                      onClick={() => selectLLMProvider(p)}
                      className={`p-4 border-2 rounded-lg text-left transition-all ${llmConfig.provider === p.id ? 'border-blue-500 bg-blue-50' : 'border-gray-200 hover:border-gray-300'}`}
                    >
                      <div className="flex items-center justify-between">
                        <span className="font-medium">{p.name}</span>
                        {llmConfig.provider === p.id && <Check size={18} className="text-blue-500" />}
                      </div>
                      <p className="text-xs text-gray-500 mt-1">{p.description}</p>
                    </button>
                  ))}
                </div>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <Input label="模型名称" value={llmConfig.model} onChange={(e) => setLlmConfig({ ...llmConfig, model: e.target.value })} />
                <Input label="基础 URL" value={llmConfig.base_url} onChange={(e) => setLlmConfig({ ...llmConfig, base_url: e.target.value })} />
                <Input label="Temperature" type="number" value={String(llmConfig.temperature)} onChange={(e) => setLlmConfig({ ...llmConfig, temperature: Number(e.target.value) || 0 })} />
                <Input label="Max Tokens" type="number" value={String(llmConfig.max_tokens)} onChange={(e) => setLlmConfig({ ...llmConfig, max_tokens: parseInt(e.target.value, 10) || 0 })} />
              </div>

              <Input label="API Key" type="password" value={llmConfig.api_key} onChange={(e) => setLlmConfig({ ...llmConfig, api_key: e.target.value })} />

              {llmResult && <div className={`p-4 rounded-lg ${llmResult.success ? 'bg-green-50 text-green-800' : 'bg-red-50 text-red-800'}`}>{llmResult.message}</div>}

              <div className="flex gap-3 pt-4">
                <Button onClick={handleLLMTest} loading={testingLLM}>
                  <RefreshCw size={18} className={`mr-2 ${testingLLM ? 'animate-spin' : ''}`} />测试连接
                </Button>
                <Button onClick={handleLLMSave}>保存配置</Button>
              </div>
            </div>
          </Card>
        </div>
      )}
    </div>
  )
}
