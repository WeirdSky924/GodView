/**
 * Token 统计组件
 */

import { useEffect, useState } from 'react'
import {
  getProjectTokenStats,
  getProjectDailyStats,
  getProjectTokenSummary,
  ProjectTokenStats,
  DailyTokenStats,
  TokenUsageSummary,
} from '@/api/tokenUsage'
import { useProject } from '@/contexts/ProjectContext'
import { Coins, TrendingUp, Calendar, BarChart3 } from 'lucide-react'

export default function TokenStats() {
  const { currentProject } = useProject()
  const [stats, setStats] = useState<ProjectTokenStats | null>(null)
  const [summary, setSummary] = useState<TokenUsageSummary | null>(null)
  const [dailyStats, setDailyStats] = useState<DailyTokenStats[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    if (currentProject) {
      loadData()
    }
  }, [currentProject])

  const loadData = async () => {
    if (!currentProject) return

    setLoading(true)
    try {
      const [statsData, summaryData, dailyData] = await Promise.all([
        getProjectTokenStats(currentProject.id),
        getProjectTokenSummary(currentProject.id),
        getProjectDailyStats(currentProject.id, 7),
      ])
      setStats(statsData)
      setSummary(summaryData)
      setDailyStats(dailyData)
    } catch (error) {
      console.error('Failed to load token stats:', error)
    } finally {
      setLoading(false)
    }
  }

  const formatNumber = (num: number) => {
    if (num >= 1000000) return `${(num / 1000000).toFixed(1)}M`
    if (num >= 1000) return `${(num / 1000).toFixed(1)}K`
    return num.toString()
  }

  const formatCost = (cost: number) => {
    if (cost >= 1) return `$${cost.toFixed(2)}`
    if (cost >= 0.01) return `$${cost.toFixed(3)}`
    return `$${cost.toFixed(4)}`
  }

  // 计算最大值用于柱状图
  const maxDailyTokens = Math.max(...dailyStats.map((d) => d.total_tokens), 1)

  if (loading) {
    return (
      <div className="bg-white rounded-lg border p-6">
        <p className="text-gray-500 text-center">加载中...</p>
      </div>
    )
  }

  if (!stats) {
    return (
      <div className="bg-white rounded-lg border p-6">
        <p className="text-gray-500 text-center">暂无数据</p>
      </div>
    )
  }

  return (
    <div className="space-y-4">
      {/* 核心指标卡片 */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <div className="bg-white rounded-lg border p-4">
          <div className="flex items-center gap-2 text-gray-500 text-sm mb-2">
            <Coins size={16} />
            <span>总量</span>
          </div>
          <div className="text-2xl font-bold text-gray-800">
            {formatNumber(stats.total_tokens)}
          </div>
          <div className="text-xs text-gray-400 mt-1">
            {formatCost(stats.total_cost)}
          </div>
        </div>

        <div className="bg-white rounded-lg border p-4">
          <div className="flex items-center gap-2 text-gray-500 text-sm mb-2">
            <TrendingUp size={16} />
            <span>今日</span>
          </div>
          <div className="text-2xl font-bold text-blue-600">
            {formatNumber(stats.today_tokens)}
          </div>
          <div className="text-xs text-gray-400 mt-1">
            {formatCost(stats.today_cost)}
          </div>
        </div>

        <div className="bg-white rounded-lg border p-4">
          <div className="flex items-center gap-2 text-gray-500 text-sm mb-2">
            <Calendar size={16} />
            <span>本周</span>
          </div>
          <div className="text-2xl font-bold text-green-600">
            {formatNumber(stats.week_tokens)}
          </div>
          <div className="text-xs text-gray-400 mt-1">
            {formatCost(stats.week_cost)}
          </div>
        </div>

        <div className="bg-white rounded-lg border p-4">
          <div className="flex items-center gap-2 text-gray-500 text-sm mb-2">
            <BarChart3 size={16} />
            <span>本月</span>
          </div>
          <div className="text-2xl font-bold text-purple-600">
            {formatNumber(stats.month_tokens)}
          </div>
          <div className="text-xs text-gray-400 mt-1">
            {formatCost(stats.month_cost)}
          </div>
        </div>
      </div>

      {/* 7 天趋势柱状图 */}
      {dailyStats.length > 0 && (
        <div className="bg-white rounded-lg border p-4">
          <h4 className="text-sm font-medium text-gray-700 mb-4">7 天趋势</h4>
          <div className="flex items-end gap-2 h-32">
            {dailyStats
              .slice()
              .reverse()
              .map((day) => (
                <div key={day.date} className="flex-1 flex flex-col items-center gap-1">
                  <div
                    className="w-full bg-blue-500 rounded-t transition-all hover:bg-blue-600"
                    style={{
                      height: `${Math.max((day.total_tokens / maxDailyTokens) * 100, 5)}%`,
                    }}
                    title={`${day.date}: ${formatNumber(day.total_tokens)} tokens`}
                  />
                  <span className="text-xs text-gray-400">
                    {new Date(day.date).toLocaleDateString('zh-CN', { weekday: 'short' })}
                  </span>
                </div>
              ))}
          </div>
        </div>
      )}

      {/* 使用场景分布 */}
      {summary?.by_category && Object.keys(summary.by_category).length > 0 && (
        <div className="bg-white rounded-lg border p-4">
          <h4 className="text-sm font-medium text-gray-700 mb-4">使用场景分布</h4>
          <div className="space-y-2">
            {Object.entries(summary.by_category)
              .sort(([, a], [, b]) => (b as number) - (a as number))
              .map(([category, tokens]) => {
                const tokensNum = tokens as number
                const percentage = (tokensNum / summary.total_tokens) * 100
                const categoryLabels: Record<string, string> = {
                  bootstrap: '项目初始化',
                  character: '角色生成',
                  world: '世界生成',
                  plot: '剧情生成',
                  chapter: '章节生成',
                  hook: '伏笔管理',
                  director: '导演模式',
                  setting_agent: '设定代理',
                  skill: 'Skill 执行',
                  rag: 'RAG 检索',
                  other: '其他',
                }
                return (
                  <div key={category}>
                    <div className="flex items-center justify-between text-sm mb-1">
                      <span className="text-gray-600">
                        {categoryLabels[category] || category}
                      </span>
                      <span className="text-gray-400">{formatNumber(tokensNum)}</span>
                    </div>
                    <div className="h-2 bg-gray-100 rounded-full overflow-hidden">
                      <div
                        className="h-full bg-gradient-to-r from-blue-500 to-blue-400 rounded-full"
                        style={{ width: `${percentage}%` }}
                      />
                    </div>
                  </div>
                )
              })}
          </div>
        </div>
      )}
    </div>
  )
}
