import { useEffect, useState, useRef } from 'react'
import { Card, Button, Input } from '@/components/ui'
import PageLayout from '@/components/PageLayout'
import {
  getEmbeddingProviders,
  updateEmbeddingConfig,
  testEmbeddingConfig,
  getEmbeddingConfig,
  getEmbeddingProviderConfig,
  getEmbeddingDownloadProgress,
  getLLMConfig,
  getLLMProviderConfig,
  updateLLMConfig,
  testLLMConfig,
} from '@/api/config'
import type { EmbeddingProviderInfo, DownloadProgress } from '@/api/config'
import { Check, RefreshCw, Zap, Bot, Download, Loader2 } from 'lucide-react'
import { useTheme } from '@/contexts/ThemeContext'

export default function Settings() {
  const { theme } = useTheme()
  const isDark = theme === 'dark'

  const [embeddingProviders, setEmbeddingProviders] = useState<EmbeddingProviderInfo[]>([])
  const [embeddingConfig, setEmbeddingConfig] = useState({
    provider: '',
    model: '',
    api_key: '',
    base_url: '',
  })
  const [embeddingDimension, setEmbeddingDimension] = useState<number | null>(null)
  const [llmConfig, setLlmConfig] = useState({
    provider: '',
    model: '',
    api_key: '',
    base_url: '',
    temperature: 0.7,
    max_tokens: 4096,
  })
  const [loading, setLoading] = useState(true)
  const [testingEmbedding, setTestingEmbedding] = useState(false)
  const [testingLLM, setTestingLLM] = useState(false)
  const [embeddingResult, setEmbeddingResult] = useState<{ success?: boolean; message?: string; dimension?: number } | null>(null)
  const [llmResult, setLlmResult] = useState<{ success?: boolean; message?: string } | null>(null)
  const [showAdvanced, setShowAdvanced] = useState(false)
  const [downloadProgress, setDownloadProgress] = useState<DownloadProgress>({
    status: 'idle',
    progress: 0,
    message: '',
    model: '',
  })
  const progressIntervalRef = useRef<NodeJS.Timeout | null>(null)

  useEffect(() => {
    loadSettings()
    return () => {
      if (progressIntervalRef.current) {
        clearInterval(progressIntervalRef.current)
      }
    }
  }, [])

  // 轮询下载进度
  const startProgressPolling = () => {
    if (progressIntervalRef.current) {
      clearInterval(progressIntervalRef.current)
    }
    progressIntervalRef.current = setInterval(async () => {
      try {
        const progress = await getEmbeddingDownloadProgress()
        setDownloadProgress(progress)
        if (progress.status === 'completed' || progress.status === 'error') {
          if (progressIntervalRef.current) {
            clearInterval(progressIntervalRef.current)
            progressIntervalRef.current = null
          }
        }
      } catch (e) {
        console.error('Failed to fetch download progress:', e)
      }
    }, 500)
  }

  const loadSettings = async () => {
    try {
      const [embeddingProvidersData, embeddingConfigData, llmConfigData] = await Promise.all([
        getEmbeddingProviders(),
        getEmbeddingConfig(),
        getLLMConfig(),
      ])
      setEmbeddingProviders(embeddingProvidersData)
      setEmbeddingConfig({
        provider: embeddingConfigData.provider,
        model: embeddingConfigData.model,
        api_key: embeddingConfigData.api_key || '',
        base_url: embeddingConfigData.base_url || '',
      })
      setEmbeddingDimension(embeddingConfigData.dimension)
      setLlmConfig({
        provider: llmConfigData.provider,
        model: llmConfigData.model,
        api_key: llmConfigData.api_key || '',
        base_url: llmConfigData.base_url || '',
        temperature: llmConfigData.temperature,
        max_tokens: llmConfigData.max_tokens,
      })
    } catch (error) {
      console.error('Failed to load settings:', error)
    } finally {
      setLoading(false)
    }
  }

  const handleEmbeddingTest = async () => {
    setTestingEmbedding(true)
    setEmbeddingResult(null)
    // 如果是 sentence_transformers，开始轮询进度
    if (embeddingConfig.provider === 'sentence_transformers') {
      startProgressPolling()
    }
    try {
      const result = await testEmbeddingConfig(embeddingConfig)
      setEmbeddingResult(result)
      if (result.dimension) {
        setEmbeddingDimension(result.dimension)
      }
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

  const selectEmbeddingProvider = async (provider: EmbeddingProviderInfo) => {
    // 如果点击的是当前已选中的 provider，不做任何操作
    if (embeddingConfig.provider === provider.id) {
      return
    }

    // 切换到新 provider 时，从后端加载该 provider 的独立配置
    try {
      const providerConfig = await getEmbeddingProviderConfig(provider.id)
      setEmbeddingConfig({
        provider: provider.id,
        model: providerConfig.model || provider.default_model,
        api_key: providerConfig.api_key || '',
        base_url: providerConfig.base_url || '',
      })
      setEmbeddingDimension(providerConfig.dimension || null)
    } catch (error) {
      // 如果加载失败，使用默认值
      setEmbeddingConfig({
        provider: provider.id,
        model: provider.default_model,
        api_key: '',
        base_url: provider.default_url || '',
      })
      setEmbeddingDimension(null)
    }
    setEmbeddingResult(null)
  }

  const selectLLMProvider = async (providerId: string) => {
    // 如果点击的是当前已选中的 provider，不做任何操作
    if (llmConfig.provider === providerId) {
      return
    }

    // 切换到新 provider 时，从后端加载该 provider 的独立配置
    try {
      const providerConfig = await getLLMProviderConfig(providerId)
      setLlmConfig({
        provider: providerId,
        model: providerConfig.model,
        api_key: providerConfig.api_key || '',
        base_url: providerConfig.base_url || '',
        temperature: providerConfig.temperature,
        max_tokens: providerConfig.max_tokens,
      })
    } catch (error) {
      // 如果加载失败，保留当前配置
      setLlmConfig((prev) => ({
        ...prev,
        provider: providerId,
      }))
    }
    setLlmResult(null)
  }

  return (
    <PageLayout
      title="系统设置"
      description="配置 AI 模型、Embedding 服务和其他选项"
    >
      <div className="max-w-4xl mx-auto space-y-6">
        {loading ? (
          <p className={`text-center py-12 ${isDark ? 'text-gray-400' : 'text-gray-500'}`}>加载中...</p>
        ) : (
          <>
            {/* LLM 模型配置 */}
            <Card title="LLM 模型配置" description="用于剧情生成、角色对话与导演流程">
              <div className="space-y-6">
                {/* Provider 选择 */}
                <div>
                  <label className={`block text-sm font-medium mb-3 ${isDark ? 'text-gray-300' : 'text-gray-700'}`}>
                    选择服务提供商
                  </label>
                  <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
                    {[
                      { id: 'openai', name: 'OpenAI', icon: Zap },
                      { id: 'anthropic', name: 'Anthropic', icon: Bot },
                      { id: 'zhipu', name: '智谱AI', icon: Zap },
                      { id: 'qwen', name: '通义千问', icon: Zap },
                      { id: 'deepseek', name: 'DeepSeek', icon: Zap },
                      { id: 'moonshot', name: 'Moonshot', icon: Zap },
                    ].map((p) => {
                      const Icon = p.icon
                      return (
                        <button
                          key={p.id}
                          onClick={() => selectLLMProvider(p.id)}
                          className={`p-3 border-2 rounded-lg text-left transition-all relative ${
                            llmConfig.provider === p.id
                              ? 'border-blue-500 bg-blue-900/20'
                              : isDark
                                ? 'border-gray-700 hover:border-gray-600'
                                : 'border-gray-200 hover:border-gray-300'
                          }`}
                        >
                          <div className="flex items-center gap-2">
                            <Icon size={18} className={llmConfig.provider === p.id ? 'text-blue-400' : isDark ? 'text-gray-500' : 'text-gray-400'} />
                            <span className={`font-medium text-sm ${isDark ? 'text-white' : 'text-gray-800'}`}>{p.name}</span>
                          </div>
                          {llmConfig.provider === p.id && (
                            <Check size={14} className="absolute right-2 top-2 text-blue-400" />
                          )}
                        </button>
                      )
                    })}
                  </div>
                </div>

                {/* 配置输入 */}
                <div className="space-y-4">
                  <Input
                    label="API Base URL"
                    value={llmConfig.base_url}
                    onChange={(e) => setLlmConfig({ ...llmConfig, base_url: e.target.value })}
                    placeholder="例如: https://api.openai.com/v1"
                  />

                  <Input
                    label="模型名称"
                    value={llmConfig.model}
                    onChange={(e) => setLlmConfig({ ...llmConfig, model: e.target.value })}
                    placeholder="例如: gpt-4o, claude-sonnet-4-20250514"
                  />

                  <Input
                    label="API Key"
                    type="password"
                    value={llmConfig.api_key}
                    onChange={(e) => setLlmConfig({ ...llmConfig, api_key: e.target.value })}
                    placeholder="输入 API Key"
                  />
                </div>

                {/* 高级参数 */}
                <div>
                  <button
                    onClick={() => setShowAdvanced(!showAdvanced)}
                    className={`flex items-center gap-2 text-sm transition-colors ${isDark ? 'text-gray-400 hover:text-gray-200' : 'text-gray-600 hover:text-gray-800'}`}
                  >
                    高级参数
                    <RefreshCw size={14} className={`transition-transform ${showAdvanced ? 'rotate-180' : ''}`} />
                  </button>

                  {showAdvanced && (
                    <div className={`mt-4 space-y-4 p-4 rounded-lg ${isDark ? 'bg-gray-800' : 'bg-gray-50'}`}>
                      {/* Temperature 滑块 */}
                      <div>
                        <div className="flex items-center justify-between mb-2">
                          <label className={`text-sm font-medium ${isDark ? 'text-gray-300' : 'text-gray-700'}`}>Temperature</label>
                          <span className={`text-sm ${isDark ? 'text-gray-400' : 'text-gray-500'}`}>{llmConfig.temperature.toFixed(2)}</span>
                        </div>
                        <input
                          type="range"
                          min="0"
                          max="2"
                          step="0.1"
                          value={llmConfig.temperature}
                          onChange={(e) => setLlmConfig({ ...llmConfig, temperature: parseFloat(e.target.value) })}
                          className="w-full h-2 bg-gray-600 rounded-lg appearance-none cursor-pointer accent-blue-500"
                        />
                        <div className={`flex justify-between text-xs mt-1 ${isDark ? 'text-gray-500' : 'text-gray-400'}`}>
                          <span>精确 (0)</span>
                          <span>创意 (2)</span>
                        </div>
                      </div>

                      {/* Max Tokens 滑块 */}
                      <div>
                        <div className="flex items-center justify-between mb-2">
                          <label className={`text-sm font-medium ${isDark ? 'text-gray-300' : 'text-gray-700'}`}>Max Tokens</label>
                          <span className={`text-sm ${isDark ? 'text-gray-400' : 'text-gray-500'}`}>{llmConfig.max_tokens.toLocaleString()}</span>
                        </div>
                        <input
                          type="range"
                          min="256"
                          max="32768"
                          step="256"
                          value={llmConfig.max_tokens}
                          onChange={(e) => setLlmConfig({ ...llmConfig, max_tokens: parseInt(e.target.value) })}
                          className="w-full h-2 bg-gray-600 rounded-lg appearance-none cursor-pointer accent-blue-500"
                        />
                        <div className={`flex justify-between text-xs mt-1 ${isDark ? 'text-gray-500' : 'text-gray-400'}`}>
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
                      llmResult.success ? (isDark ? 'bg-green-900/30 text-green-300' : 'bg-green-50 text-green-800') : (isDark ? 'bg-red-900/30 text-red-300' : 'bg-red-50 text-red-800')
                    }`}
                  >
                    {llmResult.message}
                  </div>
                )}

                {/* 操作按钮 */}
                <div className="flex gap-3 pt-4">
                  <Button onClick={handleLLMTest} loading={testingLLM}>
                    {!testingLLM && <RefreshCw size={16} className="mr-2" />}
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
                  <label className={`block text-sm font-medium mb-2 ${isDark ? 'text-gray-300' : 'text-gray-700'}`}>
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
                            ? 'border-blue-500 bg-blue-900/20'
                            : isDark
                              ? 'border-gray-700 hover:border-gray-600'
                              : 'border-gray-200 hover:border-gray-300'
                        }`}
                      >
                        <div className="flex items-center justify-between">
                          <span className={`font-medium ${isDark ? 'text-white' : 'text-gray-800'}`}>{p.name}</span>
                          {embeddingConfig.provider === p.id && <Check size={18} className="text-blue-400" />}
                        </div>
                        <p className={`text-xs mt-1 ${isDark ? 'text-gray-500' : 'text-gray-500'}`}>{p.description}</p>
                      </button>
                    ))}
                  </div>
                </div>

                <Input
                  label="模型名称"
                  value={embeddingConfig.model}
                  onChange={(e) => setEmbeddingConfig({ ...embeddingConfig, model: e.target.value })}
                />

                {/* 显示检测到的维度 */}
                {embeddingDimension && (
                  <div className={`p-3 rounded-lg flex items-center gap-2 ${isDark ? 'bg-blue-900/20 text-blue-300' : 'bg-blue-50 text-blue-700'}`}>
                    <Zap size={16} />
                    <span className="text-sm">向量维度: <strong>{embeddingDimension}</strong>（由模型自动检测）</span>
                  </div>
                )}

                {/* 根据服务类型显示不同配置 */}
                {embeddingConfig.provider === 'openai' && (
                  <>
                    <Input
                      label="API Key"
                      type="password"
                      value={embeddingConfig.api_key}
                      onChange={(e) => setEmbeddingConfig({ ...embeddingConfig, api_key: e.target.value })}
                      placeholder="sk-..."
                    />
                    <Input
                      label="API URL"
                      value={embeddingConfig.base_url}
                      onChange={(e) => setEmbeddingConfig({ ...embeddingConfig, base_url: e.target.value })}
                      placeholder="https://api.openai.com/v1"
                    />
                  </>
                )}

                {embeddingConfig.provider === 'ollama' && (
                  <Input
                    label="Ollama 服务地址"
                    value={embeddingConfig.base_url}
                    onChange={(e) => setEmbeddingConfig({ ...embeddingConfig, base_url: e.target.value })}
                    placeholder="http://localhost:11434"
                  />
                )}

                {embeddingConfig.provider === 'sentence_transformers' && (
                  <>
                    <Input
                      label="模型存储路径（可选）"
                      value={embeddingConfig.base_url}
                      onChange={(e) => setEmbeddingConfig({ ...embeddingConfig, base_url: e.target.value })}
                      placeholder="留空使用默认: ~/.cache/huggingface/hub"
                    />

                    {/* 下载进度条 */}
                    {downloadProgress.status === 'downloading' && (
                      <div className={`p-4 rounded-lg ${isDark ? 'bg-gray-800' : 'bg-gray-50'}`}>
                        <div className="flex items-center gap-2 mb-2">
                          <Loader2 size={16} className="animate-spin text-blue-500" />
                          <span className={`text-sm font-medium ${isDark ? 'text-white' : 'text-gray-800'}`}>
                            {downloadProgress.message || '下载模型中...'}
                          </span>
                        </div>
                        <div className={`h-2 rounded-full overflow-hidden ${isDark ? 'bg-gray-700' : 'bg-gray-200'}`}>
                          <div
                            className="h-full bg-blue-500 transition-all duration-300"
                            style={{ width: `${downloadProgress.progress}%` }}
                          />
                        </div>
                        <div className={`text-xs mt-2 ${isDark ? 'text-gray-400' : 'text-gray-500'}`}>
                          模型: {downloadProgress.model}
                        </div>
                      </div>
                    )}

                    <div className={`p-4 rounded-lg text-sm ${isDark ? 'bg-green-900/20 text-green-300' : 'bg-green-50 text-green-700'}`}>
                      <p className="font-medium flex items-center gap-2">
                        <Download size={16} />
                        本地模式说明
                      </p>
                      <p className="mt-1">首次使用会自动下载模型文件，下载完成后可完全离线使用。</p>
                      <p className={`mt-1 text-xs ${isDark ? 'text-green-400' : 'text-green-600'}`}>
                        默认存储路径: ~/.cache/huggingface/hub
                      </p>
                    </div>
                  </>
                )}

                {embeddingResult && (
                  <div
                    className={`p-4 rounded-lg ${
                      embeddingResult.success ? (isDark ? 'bg-green-900/30 text-green-300' : 'bg-green-50 text-green-800') : (isDark ? 'bg-red-900/30 text-red-300' : 'bg-red-50 text-red-800')
                    }`}
                  >
                    {embeddingResult.message}
                  </div>
                )}

                <div className="flex gap-3 pt-4">
                  <Button onClick={handleEmbeddingTest} loading={testingEmbedding}>
                    {!testingEmbedding && <RefreshCw size={16} className="mr-2" />}
                    测试连接
                  </Button>
                  <Button onClick={handleEmbeddingSave}>保存配置</Button>
                </div>
              </div>
            </Card>
          </>
        )}
      </div>
    </PageLayout>
  )
}
