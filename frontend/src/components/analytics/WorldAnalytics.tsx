/**
 * 世界分析仪表板组件
 * v5.2 功能：提供世界健康状况和统计分析
 */

import React, { useState, useEffect } from 'react'
import {
  TrendingUp, Users, MapPin, Calendar, Activity, AlertCircle,
  Heart, Sword, Star, BarChart2, PieChart, LineChart, RefreshCw
} from 'lucide-react'

interface WorldStats {
  total_characters: number
  active_characters: number
  total_locations: number
  active_locations: number
  total_events: number
  events_last_24h: number
  average_relationship_strength: number
  plot_progress: number
}

interface CharacterActivity {
  name: string
  action_count: number
  social_score: number
}

interface LocationStats {
  name: string
  visit_count: number
  event_count: number
}

interface WorldAnalyticsProps {
  worldId: string
}

export default function WorldAnalytics({ worldId }: WorldAnalyticsProps) {
  const [loading, setLoading] = useState(true)
  const [stats, setStats] = useState<WorldStats>({
    total_characters: 12,
    active_characters: 8,
    total_locations: 15,
    active_locations: 6,
    total_events: 156,
    events_last_24h: 23,
    average_relationship_strength: 0.65,
    plot_progress: 0.35,
  })

  const [characterActivities, setCharacterActivities] = useState<CharacterActivity[]>([
    { name: '艾伦', action_count: 45, social_score: 8.5 },
    { name: '莉娜', action_count: 38, social_score: 9.2 },
    { name: '凯文', action_count: 32, social_score: 7.1 },
    { name: '索菲亚', action_count: 28, social_score: 6.5 },
    { name: '雷克斯', action_count: 22, social_score: 5.8 },
  ])

  const [locationStats, setLocationStats] = useState<LocationStats[]>([
    { name: '王都', visit_count: 156, event_count: 45 },
    { name: '北境森林', visit_count: 89, event_count: 32 },
    { name: '东海港口', visit_count: 67, event_count: 21 },
    { name: '火山地带', visit_count: 34, event_count: 18 },
    { name: '隐秘山谷', visit_count: 23, event_count: 12 },
  ])

  useEffect(() => {
    // 模拟加载数据
    setTimeout(() => setLoading(false), 500)
  }, [worldId])

  const getHealthScore = (): number => {
    // 计算综合健康评分 (0-100)
    const characterScore = (stats.active_characters / stats.total_characters) * 30
    const locationScore = (stats.active_locations / stats.total_locations) * 20
    const eventScore = Math.min(stats.events_last_24h / 30, 1) * 20
    const relationshipScore = stats.average_relationship_strength * 20
    const plotScore = stats.plot_progress * 10

    return Math.round(characterScore + locationScore + eventScore + relationshipScore + plotScore)
  }

  const getHealthStatus = (score: number): { label: string; color: string; icon: JSX.Element } => {
    if (score >= 80) return { label: '优秀', color: 'text-green-600', icon: <Star className="w-4 h-4" /> }
    if (score >= 60) return { label: '良好', color: 'text-blue-600', icon: <TrendingUp className="w-4 h-4" /> }
    if (score >= 40) return { label: '一般', color: 'text-yellow-600', icon: <Activity className="w-4 h-4" /> }
    return { label: '需要关注', color: 'text-red-600', icon: <AlertCircle className="w-4 h-4" /> }
  }

  const healthScore = getHealthScore()
  const healthStatus = getHealthStatus(healthScore)

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <RefreshCw className="w-8 h-8 text-blue-600 animate-spin" />
      </div>
    )
  }

  return (
    <div className="p-6 space-y-6">
      {/* 页面标题 */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold text-gray-800">世界分析仪表板</h2>
          <p className="text-gray-600 mt-1">全面了解世界的运行状况和发展趋势</p>
        </div>
        <button
          onClick={() => setLoading(true)}
          className="flex items-center gap-2 px-4 py-2 border border-gray-300 rounded-lg hover:bg-gray-50"
        >
          <RefreshCw className="w-4 h-4" />
          刷新数据
        </button>
      </div>

      {/* 健康评分 */}
      <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
        <div className="flex items-center justify-between">
          <div>
            <h3 className="text-lg font-medium text-gray-800 mb-2">世界健康评分</h3>
            <div className="flex items-center gap-3">
              <span className={`text-4xl font-bold ${healthStatus.color}`}>
                {healthScore}
              </span>
              <span className={`text-xl ${healthStatus.color}`}>
                /100
              </span>
              <div className="flex items-center gap-1 ml-4">
                {healthStatus.icon}
                <span className={`font-medium ${healthStatus.color}`}>
                  {healthStatus.label}
                </span>
              </div>
            </div>
          </div>

          {/* 评分进度条 */}
          <div className="w-48">
            <div className="h-4 bg-gray-100 rounded-full overflow-hidden">
              <div
                className={`h-full transition-all ${
                  healthScore >= 80 ? 'bg-green-500' :
                  healthScore >= 60 ? 'bg-blue-500' :
                  healthScore >= 40 ? 'bg-yellow-500' : 'bg-red-500'
                }`}
                style={{ width: `${healthScore}%` }}
              />
            </div>
            <div className="flex justify-between text-xs text-gray-500 mt-1">
              <span>0</span>
              <span>100</span>
            </div>
          </div>
        </div>
      </div>

      {/* 关键指标 */}
      <div className="grid grid-cols-4 gap-4">
        <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-4">
          <div className="flex items-center gap-3 mb-2">
            <div className="p-2 bg-blue-100 rounded-lg">
              <Users className="w-5 h-5 text-blue-600" />
            </div>
            <div>
              <div className="text-sm text-gray-500">活跃角色</div>
              <div className="text-xl font-bold text-gray-800">
                {stats.active_characters}/{stats.total_characters}
              </div>
            </div>
          </div>
          <div className="text-xs text-gray-500">
            {Math.round(stats.active_characters / stats.total_characters * 100)}% 活跃率
          </div>
        </div>

        <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-4">
          <div className="flex items-center gap-3 mb-2">
            <div className="p-2 bg-green-100 rounded-lg">
              <MapPin className="w-5 h-5 text-green-600" />
            </div>
            <div>
              <div className="text-sm text-gray-500">活跃区域</div>
              <div className="text-xl font-bold text-gray-800">
                {stats.active_locations}/{stats.total_locations}
              </div>
            </div>
          </div>
          <div className="text-xs text-gray-500">
            {Math.round(stats.active_locations / stats.total_locations * 100)}% 使用率
          </div>
        </div>

        <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-4">
          <div className="flex items-center gap-3 mb-2">
            <div className="p-2 bg-purple-100 rounded-lg">
              <Calendar className="w-5 h-5 text-purple-600" />
            </div>
            <div>
              <div className="text-sm text-gray-500">24小时事件</div>
              <div className="text-xl font-bold text-gray-800">
                {stats.events_last_24h}
              </div>
            </div>
          </div>
          <div className="text-xs text-gray-500">
            总计: {stats.total_events} 事件
          </div>
        </div>

        <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-4">
          <div className="flex items-center gap-3 mb-2">
            <div className="p-2 bg-yellow-100 rounded-lg">
              <TrendingUp className="w-5 h-5 text-yellow-600" />
            </div>
            <div>
              <div className="text-sm text-gray-500">剧情进度</div>
              <div className="text-xl font-bold text-gray-800">
                {Math.round(stats.plot_progress * 100)}%
              </div>
            </div>
          </div>
          <div className="text-xs text-gray-500">
            平均关系强度: {(stats.average_relationship_strength * 100).toFixed(0)}%
          </div>
        </div>
      </div>

      {/* 详细分析 */}
      <div className="grid grid-cols-2 gap-6">
        {/* 角色活动分析 */}
        <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
          <h3 className="font-medium text-gray-800 mb-4 flex items-center gap-2">
            <BarChart2 className="w-5 h-5 text-blue-600" />
            角色活动排行
          </h3>
          <div className="space-y-3">
            {characterActivities.map((char, index) => (
              <div key={index} className="flex items-center gap-3">
                <div className="w-6 h-6 rounded-full bg-gray-100 flex items-center justify-center text-xs font-medium text-gray-600">
                  {index + 1}
                </div>
                <div className="flex-1">
                  <div className="flex items-center justify-between mb-1">
                    <span className="font-medium text-gray-800">{char.name}</span>
                    <span className="text-sm text-gray-500">{char.action_count} 次行动</span>
                  </div>
                  <div className="h-2 bg-gray-100 rounded-full overflow-hidden">
                    <div
                      className="h-full bg-blue-500"
                      style={{ width: `${(char.action_count / 50) * 100}%` }}
                    />
                  </div>
                </div>
                <div className="w-12 text-right">
                  <span className={`text-sm ${char.social_score >= 8 ? 'text-green-600' : 'text-gray-600'}`}>
                    {char.social_score}
                  </span>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* 区域热度分析 */}
        <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
          <h3 className="font-medium text-gray-800 mb-4 flex items-center gap-2">
            <PieChart className="w-5 h-5 text-green-600" />
            区域活动热度
          </h3>
          <div className="space-y-3">
            {locationStats.map((loc, index) => (
              <div key={index} className="flex items-center gap-3">
                <div className="w-16 text-sm text-gray-600 truncate">{loc.name}</div>
                <div className="flex-1">
                  <div className="h-2 bg-gray-100 rounded-full overflow-hidden">
                    <div
                      className="h-full bg-green-500"
                      style={{ width: `${(loc.visit_count / 200) * 100}%` }}
                    />
                  </div>
                </div>
                <div className="w-20 text-right text-sm text-gray-500">
                  {loc.visit_count} 次访问
                </div>
                <div className="w-16 text-right text-sm text-gray-500">
                  {loc.event_count} 事件
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* 关系网络健康 */}
        <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
          <h3 className="font-medium text-gray-800 mb-4 flex items-center gap-2">
            <Heart className="w-5 h-5 text-red-500" />
            关系网络健康
          </h3>
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <span className="text-gray-600">平均关系强度</span>
              <span className="font-medium text-gray-800">
                {(stats.average_relationship_strength * 100).toFixed(0)}%
              </span>
            </div>
            <div className="h-3 bg-gray-100 rounded-full overflow-hidden">
              <div
                className="h-full bg-red-500"
                style={{ width: `${stats.average_relationship_strength * 100}%` }}
              />
            </div>

            <div className="grid grid-cols-3 gap-4 mt-4">
              <div className="text-center p-3 bg-red-50 rounded-lg">
                <div className="text-2xl font-bold text-red-600">3</div>
                <div className="text-xs text-gray-600">敌对关系</div>
              </div>
              <div className="text-center p-3 bg-yellow-50 rounded-lg">
                <div className="text-2xl font-bold text-yellow-600">5</div>
                <div className="text-xs text-gray-600">竞争关系</div>
              </div>
              <div className="text-center p-3 bg-green-50 rounded-lg">
                <div className="text-2xl font-bold text-green-600">8</div>
                <div className="text-xs text-gray-600">友好关系</div>
              </div>
            </div>
          </div>
        </div>

        {/* 趋势预测 */}
        <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
          <h3 className="font-medium text-gray-800 mb-4 flex items-center gap-2">
            <LineChart className="w-5 h-5 text-purple-600" />
            趋势预测
          </h3>
          <div className="space-y-3">
            <div className="p-3 bg-blue-50 rounded-lg border border-blue-100">
              <div className="flex items-center gap-2 mb-1">
                <TrendingUp className="w-4 h-4 text-blue-600" />
                <span className="font-medium text-blue-800">剧情发展趋势</span>
              </div>
              <p className="text-sm text-gray-600">
                预计在接下来的 3-5 个时间周期内，剧情将进入高潮阶段，角色关系将发生重大变化。
              </p>
            </div>

            <div className="p-3 bg-green-50 rounded-lg border border-green-100">
              <div className="flex items-center gap-2 mb-1">
                <Users className="w-4 h-4 text-green-600" />
                <span className="font-medium text-green-800">角色参与度</span>
              </div>
              <p className="text-sm text-gray-600">
                角色活动保持稳定，主要角色有较高的参与度，世界活力良好。
              </p>
            </div>

            <div className="p-3 bg-yellow-50 rounded-lg border border-yellow-100">
              <div className="flex items-center gap-2 mb-1">
                <AlertCircle className="w-4 h-4 text-yellow-600" />
                <span className="font-medium text-yellow-800">需要注意</span>
              </div>
              <p className="text-sm text-gray-600">
                火山地带区域活动较少，建议增加事件触发以提升该区域的活跃度。
              </p>
            </div>
          </div>
        </div>
      </div>

      {/* 建议 */}
      <div className="bg-gradient-to-r from-blue-50 to-purple-50 rounded-xl border border-blue-100 p-6">
        <h3 className="font-medium text-gray-800 mb-3 flex items-center gap-2">
          <Star className="w-5 h-5 text-yellow-500" />
          优化建议
        </h3>
        <div className="grid grid-cols-3 gap-4">
          <div className="p-4 bg-white rounded-lg border border-blue-100">
            <div className="font-medium text-gray-800 mb-1">增加角色互动</div>
            <p className="text-sm text-gray-600">
              建议触发更多社交事件，促进角色之间的关系发展。
            </p>
          </div>
          <div className="p-4 bg-white rounded-lg border border-blue-100">
            <div className="font-medium text-gray-800 mb-1">平衡区域活动</div>
            <p className="text-sm text-gray-600">
              隐秘山谷区域使用率较低，可以设计专门的剧情进入该区域。
            </p>
          </div>
          <div className="p-4 bg-white rounded-lg border border-blue-100">
            <div className="font-medium text-gray-800 mb-1">推进剧情发展</div>
            <p className="text-sm text-gray-600">
              当前剧情进度为 35%，建议增加关键事件以推动故事前进。
            </p>
          </div>
        </div>
      </div>
    </div>
  )
}