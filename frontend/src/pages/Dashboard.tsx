/**
 * 仪表盘页面
 * v7 美化版：渐变背景、卡片动画、数字跳动、支持明亮/黑暗主题
 */

import { BookOpen, Users, Globe, Sliders, Sparkles } from 'lucide-react'
import TokenStats from '@/components/TokenStats'
import { AnimatedCard, AnimatedList, AnimatedListItem, AnimatedNumber, GradientBackground } from '@/components/animations'
import { useTheme } from '@/contexts/ThemeContext'

export default function Dashboard() {
  const { theme } = useTheme()
  const isDark = theme === 'dark'

  const stats = [
    { icon: <Users size={24} />, label: '角色数量', value: 0, color: 'from-blue-500 to-blue-600', glow: 'glow-primary' },
    { icon: <Globe size={24} />, label: '世界设定', value: 0, color: 'from-green-500 to-emerald-600', glow: 'glow-success' },
    { icon: <BookOpen size={24} />, label: '已生成章节', value: 0, color: 'from-purple-500 to-violet-600', glow: 'glow-secondary' },
    { icon: <Sliders size={24} />, label: 'AI 助手', value: 6, color: 'from-orange-500 to-amber-600', glow: 'glow-warning' },
  ]

  const agents = [
    { name: 'Summarizer', status: 'ready', desc: '剧情总结员' },
    { name: 'Master Plotter', status: 'ready', desc: '总编剧' },
    { name: 'Hook Manager', status: 'ready', desc: '伏笔管理员' },
    { name: 'Writer', status: 'ready', desc: '内容执行官' },
    { name: 'Evaluator', status: 'ready', desc: '剧情评估员' },
    { name: 'Character Agent', status: 'ready', desc: '角色演绎' },
  ]

  return (
    <div className="min-h-screen">
      {/* 顶部欢迎区域 */}
      <div className="mb-8">
        <h1 className="text-3xl font-bold gradient-text mb-2">仪表盘</h1>
        <p className={isDark ? 'text-gray-400' : 'text-gray-500'}>欢迎回来，今天想创作什么？</p>
      </div>

      {/* 统计卡片 */}
      <AnimatedList className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
        {stats.map((stat, index) => (
          <AnimatedListItem key={stat.label}>
            <AnimatedCard delay={index * 0.1} className={`overflow-hidden ${isDark ? 'glass-card' : 'bg-white shadow-md border border-gray-100'}`}>
              <div className="p-6">
                <div className="flex items-center gap-4">
                  <div className={`bg-gradient-to-br ${stat.color} text-white p-3 rounded-xl shadow-lg ${stat.glow}`}>
                    {stat.icon}
                  </div>
                  <div>
                    <p className={`text-sm ${isDark ? 'text-gray-400' : 'text-gray-500'}`}>{stat.label}</p>
                    <p className={`text-2xl font-bold ${isDark ? 'text-white' : 'text-gray-800'}`}>
                      <AnimatedNumber value={stat.value} />
                    </p>
                  </div>
                </div>
              </div>
              <div className={`h-1 bg-gradient-to-r ${stat.color}`} />
            </AnimatedCard>
          </AnimatedListItem>
        ))}
      </AnimatedList>

      {/* Token 统计 */}
      <AnimatedCard delay={0.4} className={`mb-8 ${isDark ? 'glass-card' : 'bg-white shadow-md border border-gray-100'}`}>
        <div className="p-6">
          <h2 className={`text-lg font-semibold mb-4 flex items-center gap-2 ${isDark ? 'text-white' : 'text-gray-800'}`}>
            <span className="text-xl">📊</span> Token 消耗统计
          </h2>
          <TokenStats />
        </div>
      </AnimatedCard>

      {/* 快速入口 */}
      <AnimatedList className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-8">
        <AnimatedListItem>
          <AnimatedCard hover className="relative overflow-hidden">
            <GradientBackground colors={['#3b82f6', '#8b5cf6']} className="absolute inset-0" />
            <div className="relative p-6 text-white">
              <div className="flex items-center gap-2 mb-2">
                <Sparkles className="w-5 h-5" />
                <h2 className="text-xl font-semibold">开始创作</h2>
              </div>
              <p className="text-blue-100 mb-4">进入导演模式，让 AI 协助你创作小说</p>
              <a
                href="/director"
                className="inline-block bg-white/20 backdrop-blur-sm text-white px-4 py-2 rounded-lg font-medium hover:bg-white/30 transition-all border border-white/20"
              >
                进入导演模式 →
              </a>
            </div>
          </AnimatedCard>
        </AnimatedListItem>

        <AnimatedListItem>
          <AnimatedCard hover className="relative overflow-hidden">
            <GradientBackground colors={['#8b5cf6', '#ec4899']} className="absolute inset-0" />
            <div className="relative p-6 text-white">
              <div className="flex items-center gap-2 mb-2">
                <Sliders className="w-5 h-5" />
                <h2 className="text-xl font-semibold">配置系统</h2>
              </div>
              <p className="text-purple-100 mb-4">设置 AI 模型、Embedding 服务和其他选项</p>
              <a
                href="/settings"
                className="inline-block bg-white/20 backdrop-blur-sm text-white px-4 py-2 rounded-lg font-medium hover:bg-white/30 transition-all border border-white/20"
              >
                系统设置 →
              </a>
            </div>
          </AnimatedCard>
        </AnimatedListItem>
      </AnimatedList>

      {/* Agent 状态概览 */}
      <AnimatedCard delay={0.5} className={isDark ? 'glass-card' : 'bg-white shadow-md border border-gray-100'}>
        <div className="p-6">
          <h2 className={`text-lg font-semibold mb-4 flex items-center gap-2 ${isDark ? 'text-white' : 'text-gray-800'}`}>
            <span className="text-xl">🤖</span> Agent 状态
          </h2>
          <AnimatedList className="space-y-3">
            {agents.map((agent, index) => (
              <AnimatedListItem key={agent.name}>
                <div
                  className={`flex items-center justify-between p-4 rounded-xl transition-colors border ${
                    isDark
                      ? 'bg-gray-800/50 hover:bg-gray-800 border-gray-700'
                      : 'bg-gray-50 hover:bg-gray-100 border-gray-200'
                  }`}
                  style={{ animationDelay: `${index * 0.05}s` }}
                >
                  <div className="flex items-center gap-3">
                    <span className={`w-2.5 h-2.5 rounded-full ${agent.status === 'ready' ? 'bg-green-500 animate-pulse' : 'bg-gray-400'}`} />
                    <div>
                      <p className={`font-medium ${isDark ? 'text-white' : 'text-gray-800'}`}>{agent.name}</p>
                      <p className={`text-sm ${isDark ? 'text-gray-400' : 'text-gray-500'}`}>{agent.desc}</p>
                    </div>
                  </div>
                  <span className={`px-3 py-1 text-xs rounded-full ${
                    agent.status === 'ready'
                      ? isDark
                        ? 'bg-green-900/50 text-green-400 border border-green-700'
                        : 'bg-green-100 text-green-600 border border-green-200'
                      : isDark
                        ? 'bg-gray-700 text-gray-400'
                        : 'bg-gray-200 text-gray-500'
                  }`}>
                    {agent.status === 'ready' ? '就绪' : agent.status}
                  </span>
                </div>
              </AnimatedListItem>
            ))}
          </AnimatedList>
        </div>
      </AnimatedCard>
    </div>
  )
}
