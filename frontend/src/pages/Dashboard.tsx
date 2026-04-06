import { BookOpen, Users, Globe, Sliders } from 'lucide-react'

export default function Dashboard() {
  const stats = [
    { icon: <Users size={24} />, label: '角色数量', value: '0', color: 'bg-blue-500' },
    { icon: <Globe size={24} />, label: '世界设定', value: '0', color: 'bg-green-500' },
    { icon: <BookOpen size={24} />, label: '已生成章节', value: '0', color: 'bg-purple-500' },
    { icon: <Sliders size={24} />, label: 'AI 助手', value: '6', color: 'bg-orange-500' },
  ]

  return (
    <div>
      <h1 className="text-3xl font-bold text-gray-800 mb-8">仪表盘</h1>

      {/* 统计卡片 */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
        {stats.map((stat) => (
          <div key={stat.label} className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
            <div className="flex items-center gap-4">
              <div className={`${stat.color} text-white p-3 rounded-lg`}>
                {stat.icon}
              </div>
              <div>
                <p className="text-sm text-gray-500">{stat.label}</p>
                <p className="text-2xl font-bold text-gray-800">{stat.value}</p>
              </div>
            </div>
          </div>
        ))}
      </div>

      {/* 快速入口 */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <div className="bg-gradient-to-br from-blue-500 to-blue-600 rounded-xl p-6 text-white">
          <h2 className="text-xl font-semibold mb-2">🚀 开始创作</h2>
          <p className="text-blue-100 mb-4">进入导演模式，让 AI 协助你创作小说</p>
          <a href="/director" className="inline-block bg-white text-blue-600 px-4 py-2 rounded-lg font-medium hover:bg-blue-50 transition-colors">
            进入导演模式
          </a>
        </div>

        <div className="bg-gradient-to-br from-purple-500 to-purple-600 rounded-xl p-6 text-white">
          <h2 className="text-xl font-semibold mb-2">⚙️ 配置系统</h2>
          <p className="text-purple-100 mb-4">设置 AI 模型、Embedding 服务和其他选项</p>
          <a href="/settings" className="inline-block bg-white text-purple-600 px-4 py-2 rounded-lg font-medium hover:bg-purple-50 transition-colors">
            系统设置
          </a>
        </div>
      </div>

      {/* Agent 状态概览 */}
      <div className="mt-8 bg-white rounded-xl shadow-sm border border-gray-200 p-6">
        <h2 className="text-lg font-semibold text-gray-800 mb-4">Agent 状态</h2>
        <div className="space-y-3">
          {[
            { name: 'Summarizer', status: 'ready', desc: '剧情总结员' },
            { name: 'Master Plotter', status: 'ready', desc: '总编剧' },
            { name: 'Hook Manager', status: 'ready', desc: '伏笔管理员' },
            { name: 'Writer', status: 'ready', desc: '内容执行官' },
            { name: 'Evaluator', status: 'ready', desc: '剧情评估员' },
            { name: 'Character Agent', status: 'ready', desc: '角色演绎' },
          ].map((agent) => (
            <div key={agent.name} className="flex items-center justify-between p-3 bg-gray-50 rounded-lg">
              <div className="flex items-center gap-3">
                <span className={`w-2 h-2 rounded-full ${agent.status === 'ready' ? 'bg-green-500' : 'bg-gray-400'}`} />
                <div>
                  <p className="font-medium text-gray-800">{agent.name}</p>
                  <p className="text-sm text-gray-500">{agent.desc}</p>
                </div>
              </div>
              <span className="text-sm text-gray-500 capitalize">{agent.status}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
