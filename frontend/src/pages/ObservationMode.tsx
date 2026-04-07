/**
 * 多维度观测模式页面
 * v5.2 功能：提供沉浸式的世界观测体验
 */

import React, { useState, useEffect } from 'react'
import { Globe, Eye, Clock, Users, MapPin, Activity, Layers, Settings, Zap, Pause, Play, RotateCcw } from 'lucide-react'
import MapView from '@/components/world/MapView'
import NetworkGraph from '@/components/world/NetworkGraph'
import EventStream from '@/components/world/EventStream'
import WorldAnalytics from '@/components/analytics/WorldAnalytics'

type ObservationView = 'god' | 'character' | 'timeline' | 'analytics'

interface CharacterInfo {
  id: string
  name: string
  description?: string
}

export default function ObservationMode() {
  const [viewMode, setViewMode] = useState<ObservationView>('god')
  const [selectedCharacterId, setSelectedCharacterId] = useState<string | null>(null)
  const [characters, setCharacters] = useState<CharacterInfo[]>([])
  const [selectedWorldId, setSelectedWorldId] = useState('world_1')
  const [isPaused, setIsPaused] = useState(false)
  const [showAnalytics, setShowAnalytics] = useState(false)

  // 模拟数据加载
  useEffect(() => {
    // 加载角色列表
    setCharacters([
      { id: 'char1', name: '艾伦', description: '主角' },
      { id: 'char2', name: '莉娜', description: '女主角' },
      { id: 'char3', name: '凯文', description: '配角' },
      { id: 'char4', name: '索菲亚', description: '反派' },
    ])
  }, [])

  const selectedCharacter = characters.find(c => c.id === selectedCharacterId)

  const renderMainContent = () => {
    switch (viewMode) {
      case 'god':
        return (
          <div className="grid grid-cols-2 gap-4 h-full">
            {/* 地图视图 */}
            <div className="bg-white rounded-lg shadow-sm border border-gray-200 overflow-hidden">
              <div className="px-4 py-3 border-b border-gray-200 bg-gray-50 flex items-center gap-2">
                <MapPin className="w-4 h-4 text-blue-600" />
                <span className="font-medium text-gray-800">世界地图</span>
              </div>
              <div className="h-[calc(100%-48px)]">
                <MapView
                  worldId={selectedWorldId}
                  onLocationSelect={(locId) => console.log('Selected location:', locId)}
                />
              </div>
            </div>

            {/* 关系网络图 */}
            <div className="bg-white rounded-lg shadow-sm border border-gray-200 overflow-hidden">
              <div className="px-4 py-3 border-b border-gray-200 bg-gray-50 flex items-center gap-2">
                <Users className="w-4 h-4 text-green-600" />
                <span className="font-medium text-gray-800">关系网络</span>
              </div>
              <div className="h-[calc(100%-48px)]">
                <NetworkGraph
                  worldId={selectedWorldId}
                  onNodeSelect={(nodeId) => console.log('Selected node:', nodeId)}
                />
              </div>
            </div>
          </div>
        )

      case 'character':
        return (
          <div className="h-full flex">
            {/* 角色选择侧边栏 */}
            <div className="w-64 border-r border-gray-200 bg-white p-4">
              <h3 className="font-medium text-gray-800 mb-4">选择角色</h3>
              <div className="space-y-2">
                {characters.map(char => (
                  <button
                    key={char.id}
                    onClick={() => setSelectedCharacterId(char.id)}
                    className={`w-full p-3 text-left rounded-lg border transition-all ${
                      selectedCharacterId === char.id
                        ? 'border-blue-500 bg-blue-50'
                        : 'border-gray-200 hover:border-gray-300'
                    }`}
                  >
                    <div className="font-medium text-gray-800">{char.name}</div>
                    <div className="text-sm text-gray-600">{char.description}</div>
                  </button>
                ))}
              </div>
            </div>

            {/* 角色详情 */}
            <div className="flex-1 p-6 overflow-y-auto">
              {selectedCharacter ? (
                <div className="space-y-6">
                  {/* 角色基本信息 */}
                  <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6">
                    <div className="flex items-center gap-4 mb-4">
                      <div className="w-16 h-16 rounded-full bg-blue-100 flex items-center justify-center text-2xl">
                        👤
                      </div>
                      <div>
                        <h2 className="text-2xl font-bold text-gray-800">{selectedCharacter.name}</h2>
                        <p className="text-gray-600">{selectedCharacter.description}</p>
                      </div>
                    </div>
                  </div>

                  {/* 角色状态 */}
                  <div className="grid grid-cols-3 gap-4">
                    <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-4">
                      <div className="text-sm text-gray-500 mb-1">心情</div>
                      <div className="text-lg font-medium text-gray-800">愉快 😊</div>
                    </div>
                    <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-4">
                      <div className="text-sm text-gray-500 mb-1">精力</div>
                      <div className="text-lg font-medium text-gray-800">85%</div>
                    </div>
                    <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-4">
                      <div className="text-sm text-gray-500 mb-1">位置</div>
                      <div className="text-lg font-medium text-gray-800">王都</div>
                    </div>
                  </div>

                  {/* 角色记忆流 */}
                  <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6">
                    <h3 className="font-medium text-gray-800 mb-4">记忆流</h3>
                    <div className="space-y-3">
                      <div className="p-3 bg-blue-50 rounded-lg">
                        <div className="text-xs text-blue-600 mb-1">今天 · 刚刚</div>
                        <div className="text-gray-800">在王都遇到了故友，得知了一些重要消息</div>
                      </div>
                      <div className="p-3 bg-gray-50 rounded-lg">
                        <div className="text-xs text-gray-500 mb-1">昨天</div>
                        <div className="text-gray-800">完成了重要的任务，获得了奖励</div>
                      </div>
                      <div className="p-3 bg-gray-50 rounded-lg">
                        <div className="text-xs text-gray-500 mb-1">3天前</div>
                        <div className="text-gray-800">开始了新的旅程，踏上了冒险之路</div>
                      </div>
                    </div>
                  </div>

                  {/* 角色目标 */}
                  <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6">
                    <h3 className="font-medium text-gray-800 mb-4">目标</h3>
                    <div className="space-y-2">
                      <div className="flex items-center gap-3">
                        <div className="w-2 h-2 rounded-full bg-green-500" />
                        <span className="text-gray-700">寻找失散的父亲</span>
                      </div>
                      <div className="flex items-center gap-3">
                        <div className="w-2 h-2 rounded-full bg-yellow-500" />
                        <span className="text-gray-700">提升实力成为强者</span>
                      </div>
                      <div className="flex items-center gap-3">
                        <div className="w-2 h-2 rounded-full bg-gray-400" />
                        <span className="text-gray-700">解开身世之谜</span>
                      </div>
                    </div>
                  </div>
                </div>
              ) : (
                <div className="h-full flex items-center justify-center text-gray-500">
                  <div className="text-center">
                    <Eye className="w-16 h-16 mx-auto mb-4 text-gray-300" />
                    <p>请选择要观测的角色</p>
                  </div>
                </div>
              )}
            </div>
          </div>
        )

      case 'timeline':
        return (
          <div className="h-full">
            <EventStream worldId={selectedWorldId} realTime={!isPaused} />
          </div>
        )

      case 'analytics':
        return (
          <div className="h-full overflow-y-auto">
            <WorldAnalytics worldId={selectedWorldId} />
          </div>
        )
    }
  }

  return (
    <div className="h-screen bg-gray-50 flex flex-col">
      {/* 顶部控制栏 */}
      <div className="bg-white border-b border-gray-200 px-6 py-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-4">
            <div className="flex items-center gap-2">
              <Globe className="w-8 h-8 text-blue-600" />
              <h1 className="text-xl font-bold text-gray-800">观测模式</h1>
            </div>

            {/* 视图选择 */}
            <div className="flex items-center gap-1 ml-8">
              <button
                onClick={() => setViewMode('god')}
                className={`flex items-center gap-2 px-4 py-2 rounded-lg ${
                  viewMode === 'god'
                    ? 'bg-blue-100 text-blue-700'
                    : 'text-gray-600 hover:bg-gray-100'
                }`}
              >
                <Eye className="w-4 h-4" />
                上帝视角
              </button>
              <button
                onClick={() => setViewMode('character')}
                className={`flex items-center gap-2 px-4 py-2 rounded-lg ${
                  viewMode === 'character'
                    ? 'bg-blue-100 text-blue-700'
                    : 'text-gray-600 hover:bg-gray-100'
                }`}
              >
                <Users className="w-4 h-4" />
                角色视角
              </button>
              <button
                onClick={() => setViewMode('timeline')}
                className={`flex items-center gap-2 px-4 py-2 rounded-lg ${
                  viewMode === 'timeline'
                    ? 'bg-blue-100 text-blue-700'
                    : 'text-gray-600 hover:bg-gray-100'
                }`}
              >
                <Clock className="w-4 h-4" />
                时间流
              </button>
              <button
                onClick={() => setViewMode('analytics')}
                className={`flex items-center gap-2 px-4 py-2 rounded-lg ${
                  viewMode === 'analytics'
                    ? 'bg-blue-100 text-blue-700'
                    : 'text-gray-600 hover:bg-gray-100'
                }`}
              >
                <Activity className="w-4 h-4" />
                分析面板
              </button>
            </div>
          </div>

          <div className="flex items-center gap-4">
            {/* 播放控制 */}
            <div className="flex items-center gap-2 px-3 py-1 bg-gray-100 rounded-lg">
              <button
                onClick={() => setIsPaused(!isPaused)}
                className="p-2 hover:bg-gray-200 rounded"
              >
                {isPaused ? <Play className="w-4 h-4" /> : <Pause className="w-4 h-4" />}
              </button>
              <button className="p-2 hover:bg-gray-200 rounded">
                <RotateCcw className="w-4 h-4" />
              </button>
            </div>

            {/* 时间显示 */}
            <div className="flex items-center gap-2 px-4 py-2 bg-blue-50 rounded-lg">
              <Clock className="w-4 h-4 text-blue-600" />
              <span className="font-medium text-blue-800">第 5 天 14:30</span>
            </div>

            {/* 模拟状态 */}
            <div className="flex items-center gap-2">
              <div className={`w-2 h-2 rounded-full ${isPaused ? 'bg-yellow-500' : 'bg-green-500'}`} />
              <span className="text-sm text-gray-600">
                {isPaused ? '已暂停' : '运行中'}
              </span>
            </div>
          </div>
        </div>
      </div>

      {/* 主内容区域 */}
      <div className="flex-1 p-4 overflow-hidden">
        {renderMainContent()}
      </div>

      {/* 底部状态栏 */}
      <div className="bg-white border-t border-gray-200 px-6 py-2 flex items-center justify-between text-sm text-gray-500">
        <div className="flex items-center gap-4">
          <span>世界: {selectedWorldId}</span>
          <span>·</span>
          <span>实体: {characters.length}</span>
          <span>·</span>
          <span>活跃事件: 3</span>
        </div>
        <div className="flex items-center gap-4">
          <span>时间流速: 1.0x</span>
          <span>·</span>
          <span>内存使用: 128MB</span>
        </div>
      </div>
    </div>
  )
}