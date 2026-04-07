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
  getProviderModels,
  LLMProviderInfo,
  LLMModelInfo,
} from '@/api/config'
import { Check, RefreshCw, ExternalLink, ChevronDown, Settings2, Sparkles, Zap } from 'lucide-react'

export default function Settings() {
  const [embeddingProviders, setEmbeddingProviders] = useState<any[]>([])
  const [llmProviders, setLlmProviders] = useState<LLMProviderInfo[]>([])
  const [providerModels, setProviderModels] = useState<LLMModelInfo[]>([])
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
  const [showAdvanced, setShowAdvanced] = useState(false)

  useEffect(() => {
    loadSettings()
  }, [])

  useEffect(() => {
    // 当 provider 改变时加载模型列表
    if (llmConfig.provider) {
      loadProviderModels(llmConfig.provider)
    }
  }, [llmConfig.provider])

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

  const loadProviderModels = async (providerId: string) => {
    try {
      const response = await getProviderModels(providerId)
      setProviderModels(response.models || [])
    } catch (error) {
      console.error('Failed to load provider models:', error)
      setProviderModels([])
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

  const selectLLMProvider = (provider: LLMProviderInfo) => {
    setLlmConfig((prev) => ({
      ...prev,
      provider: provider.id,
      model: provider.default_model,
      base_url: provider.default_url,
    }))
  }

  const getSelectedProvider = () => {
    return llmProviders.find((p) => p.id === llmConfig.provider)
  }

  const formatContextLength = (length: number) => {
    if (length >= 1000000) return `${(length / 1000000).toFixed(1)}M`
    if (length >= 1000) return `${Math.round(length / 1000)}K`
    return String(length)
  }

  // Provider 分组
  const domesticProviders = llmProviders.filter((p) =>
    ['zhipu', 'qwen', 'deepseek', 'moonshot', 'baichuan', 'wenxin', 'yi', 'minimax'].includes(p.id)
  )
  const internationalProviders = llmProviders.filter((p) =>
    ['openai', 'anthropic'].includes(p.id)
  )
  const gatewayProviders = llmProviders.filter((p) => ['openrouter', 'custom'].includes(p.id))

  return (
    <div className="max-w-5xl mx-auto">
      <h1 className="text-3xl font-bold text-gray-800 mb-8">⚙️ 系统设置</h1>

      {loading ? (
        <p className="text-center text-gray-500 py-12">加载中...</p>
      ) : (
        <div className="space-y-6">
          {/* LLM 模型配置 */}
          <Card title="LLM 模型配置" description="用于剧情生成、角色对话与导演流程">
            <div className="space-y-6">
              {/* Provider 选择区域 */}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-3">
                  <Sparkles size={16} className="inline mr-1" />
                  选择模型提供商
                </label>

                {/* 国际模型 */}
                <div className="mb-4">
                  <p className="text-xs text-gray-500 mb-2 uppercase tracking-wide">国际模型</p>
                  <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-3">
                    {internationalProviders.map((p) => (
                      <button
                        key={p.id}
                        onClick={() => selectLLMProvider(p)}
                        className={`p-3 border-2 rounded-lg text-left transition-all ${
                          llmConfig.provider === p.id
                            ? 'border-blue-500 bg-blue-50 ring-2 ring-blue-200'
                            : 'border-gray-200 hover:border-gray-300 hover:bg-gray-50'
                        }`}
                      >
                        <div className="flex items-center justify-between mb-1">
                          <span className="font-medium text-sm">{p.name}</span>
                          {llmConfig.provider === p.id && <Check size={16} className="text-blue-500" />}
                        </div>
                        <p className="text-xs text-gray-500 line-clamp-2">{p.description}</p>
                      </button>
                    ))}
                  </div>
                </div>

                {/* 国内模型 */}
                <div className="mb-4">
                  <p className="text-xs text-gray-500 mb-2 uppercase tracking-wide">国内模型</p>
                  <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-3">
                    {domesticProviders.map((p) => (
                      <button
                        key={p.id}
                        onClick={() => selectLLMProvider(p)}
                        className={`p-3 border-2 rounded-lg text-left transition-all ${
                          llmConfig.provider === p.id
                            ? 'border-blue-500 bg-blue-50 ring-2 ring-blue-200'
                            : 'border-gray-200 hover:border-gray-300 hover:bg-gray-50'
                        }`}
                      >
                        <div className="flex items-center justify-between mb-1">
                          <span className="font-medium text-sm">{p.name}</span>
                          {llmConfig.provider === p.id && <Check size={16} className="text-blue-500" />}
                        </div>
                        <p className="text-xs text-gray-500 line-clamp-2">{p.description}</p>
                      </button>
                    ))}
                  </div>
                </div>

                {/* 聚合网关 */}
                <div>
                  <p className="text-xs text-gray-500 mb-2 uppercase tracking-wide">聚合网关</p>
                  <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-3">
                    {gatewayProviders.map((p) => (
                      <button
                        key={p.id}
                        onClick={() => selectLLMProvider(p)}
                        className={`p-3 border-2 rounded-lg text-left transition-all ${
                          llmConfig.provider === p.id
                            ? 'border-blue-500 bg-blue-50 ring-2 ring-blue-200'
                            : 'border-gray-200 hover:border-gray-300 hover:bg-gray-50'
                        }`}
                      >
                        <div className="flex items-center justify-between mb-1">
                          <span className="font-medium text-sm">{p.name}</span>
                          {llmConfig.provider === p.id && <Check size={16} className="text-blue-500" />}
                        </div>
                        <p className="text-xs text-gray-500 line-clamp-2">{p.description}</p>
                      </button>
                    ))}
                  </div>
                </div>
              </div>

              {/* Provider 详情 */}
              {getSelectedProvider() && (
                <div className="bg-gray-50 rounded-lg p-4">
                  <div className="flex items-start justify-between">
                    <div>
                      <h4 className="font-medium text-gray-800">{getSelectedProvider()?.name}</h4>
                      <p className="text-sm text-gray-600 mt-1">{getSelectedProvider()?.description}</p>
                    </div>
                    {getSelectedProvider()?.api_key_url && (
                      <a
                        href={getSelectedProvider()?.api_key_url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-blue-600 hover:text-blue-700 text-sm flex items-center gap-1"
                      >
                        获取 API Key <ExternalLink size={14} />
                      </a>
                    )}
                  </div>
                </div>
              )}

              {/* 模型选择 */}
              {providerModels.length > 0 && (
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">选择模型</label>
                  <div className="relative">
                    <select
                      value={llmConfig.model}
                      onChange={(e) => setLlmConfig({ ...llmConfig, model: e.target.value })}
                      className="w-full p-3 border border-gray-300 rounded-lg appearance-none bg-white pr-10 focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                    >
                      <option value="">选择模型...</option>
                      {providerModels.map((m) => (
                        <option key={m.id} value={m.id}>
                          {m.name} ({formatContextLength(m.context_length)} 上下文) - {m.description}
                        </option>
                      ))}
                    </select>
                    <ChevronDown size={18} className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 pointer-events-none" />
                  </div>
                </div>
              )}

              {/* 配置输入 */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <Input
                  label="模型名称"
                  value={llmConfig.model}
                  onChange={(e) => setLlmConfig({ ...llmConfig, model: e.target.value })}
                  placeholder="手动输入模型名称"
                />
                <Input
                  label="基础 URL"
                  value={llmConfig.base_url}
                  onChange={(e) => setLlmConfig({ ...llmConfig, base_url: e.target.value })}
                  placeholder="API 基础地址"
                />
              </div>

              <Input
                label="API Key"
                type="password"
                value={llmConfig.api_key}
                onChange={(e) => setLlmConfig({ ...llmConfig, api_key: e.target.value })}
                placeholder="输入 API Key"
              />

              {/* 高级参数 */}
              <div>
                <button
                  onClick={() => setShowAdvanced(!showAdvanced)}
                  className="flex items-center gap-2 text-sm text-gray-600 hover:text-gray-800 transition-colors"
                >
                  <Settings2 size={16} />
                  高级参数
                  <ChevronDown
                    size={16}
                    className={`transition-transform ${showAdvanced ? 'rotate-180' : ''}`}
                  />
                </button>

                {showAdvanced && (
                  <div className="mt-4 space-y-4 p-4 bg-gray-50 rounded-lg">
                    {/* Temperature 滑块 */}
                    <div>
                      <div className="flex items-center justify-between mb-2">
                        <label className="text-sm font-medium text-gray-700">Temperature</label>
                        <span className="text-sm text-gray-500">{llmConfig.temperature.toFixed(2)}</span>
                      </div>
                      <input
                        type="range"
                        min="0"
                        max="2"
                        step="0.1"
                        value={llmConfig.temperature}
                        onChange={(e) => setLlmConfig({ ...llmConfig, temperature: parseFloat(e.target.value) })}
                        className="w-full h-2 bg-gray-200 rounded-lg appearance-none cursor-pointer accent-blue-500"
                      />
                      <div className="flex justify-between text-xs text-gray-400 mt-1">
                        <span>精确 (0)</span>
                        <span>创意 (2)</span>
                      </div>
                    </div>

                    {/* Max Tokens 滑块 */}
                    <div>
                      <div className="flex items-center justify-between mb-2">
                        <label className="text-sm font-medium text-gray-700">Max Tokens</label>
                        <span className="text-sm text-gray-500">{llmConfig.max_tokens.toLocaleString()}</span>
                      </div>
                      <input
                        type="range"
                        min="256"
                        max="32768"
                        step="256"
                        value={llmConfig.max_tokens}
                        onChange={(e) => setLlmConfig({ ...llmConfig, max_tokens: parseInt(e.target.value) })}
                        className="w-full h-2 bg-gray-200 rounded-lg appearance-none cursor-pointer accent-blue-500"
                      />
                      <div className="flex justify-between text-xs text-gray-400 mt-1">
                        <span>256</span>
                        <span>32K</span>
                      </div>
                    </div>
                  </div>
                )}
              </div>

              {/* 测试结果 */}
              {llmResult && (
                <div
                  className={`p-4 rounded-lg ${
                    llmResult.success ? 'bg-green-50 text-green-800' : 'bg-red-50 text-red-800'
                  }`}
                >
                  {llmResult.message}
                </div>
              )}

              {/* 操作按钮 */}
              <div className="flex gap-3 pt-4">
                <Button onClick={handleLLMTest} loading={testingLLM}>
                  <RefreshCw size={18} className={`mr-2 ${testingLLM ? 'animate-spin' : ''}`} />
                  测试连接
                </Button>
                <Button onClick={handleLLMSave}>保存配置</Button>
              </div>
            </div>
          </Card>

          {/* Embedding 服务配置 */}
          <Card title="Embedding 服务配置" description="用于向量检索和语义相似度计算">
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  <Zap size={16} className="inline mr-1" />
                  选择服务类型
                </label>
                <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                  {embeddingProviders.map((p) => (
                    <button
                      key={p.id}
                      onClick={() => selectEmbeddingProvider(p)}
                      className={`p-4 border-2 rounded-lg text-left transition-all ${
                        embeddingConfig.provider === p.id
                          ? 'border-blue-500 bg-blue-50'
                          : 'border-gray-200 hover:border-gray-300'
                      }`}
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
                <Input
                  label="模型名称"
                  value={embeddingConfig.model}
                  onChange={(e) => setEmbeddingConfig({ ...embeddingConfig, model: e.target.value })}
                />
                <Input
                  label="向量维度"
                  type="number"
                  value={String(embeddingConfig.dimension)}
                  onChange={(e) => setEmbeddingConfig({ ...embeddingConfig, dimension: parseInt(e.target.value, 10) || 0 })}
                />
              </div>

              <Input
                label="API Key"
                type="password"
                value={embeddingConfig.api_key}
                onChange={(e) => setEmbeddingConfig({ ...embeddingConfig, api_key: e.target.value })}
              />
              <Input
                label="基础 URL"
                value={embeddingConfig.base_url}
                onChange={(e) => setEmbeddingConfig({ ...embeddingConfig, base_url: e.target.value })}
              />

              {embeddingResult && (
                <div
                  className={`p-4 rounded-lg ${
                    embeddingResult.success ? 'bg-green-50 text-green-800' : 'bg-red-50 text-red-800'
                  }`}
                >
                  {embeddingResult.message}
                </div>
              )}

              <div className="flex gap-3 pt-4">
                <Button onClick={handleEmbeddingTest} loading={testingEmbedding}>
                  <RefreshCw size={18} className={`mr-2 ${testingEmbedding ? 'animate-spin' : ''}`} />
                  测试连接
                </Button>
                <Button onClick={handleEmbeddingSave}>保存配置</Button>
              </div>
            </div>
          </Card>
        </div>
      )}
    </div>
  )
}
