import { NavLink } from 'react-router-dom'
import {
  LayoutDashboard, Users, Globe, BookOpen, Sliders, FileText, Settings, Flag, GitCompare, ShieldAlert, Eye, Network, Mic2, CheckCircle2
} from 'lucide-react'

interface NavItem {
  path: string
  icon: React.ReactNode
  label: string
}

const navItems: NavItem[] = [
  { path: '/', icon: <LayoutDashboard size={20} />, label: '仪表盘' },
  { path: '/characters', icon: <Users size={20} />, label: '角色管理' },
  { path: '/character-voice', icon: <Mic2 size={20} />, label: '角色声音' },
  { path: '/worlds', icon: <Globe size={20} />, label: '世界管理' },
  { path: '/plots', icon: <BookOpen size={20} />, label: '剧情管理' },
  { path: '/hooks', icon: <Flag size={20} />, label: '伏笔管理' },
  { path: '/interventions', icon: <ShieldAlert size={20} />, label: '干预日志' },
  { path: '/simulator', icon: <Eye size={20} />, label: '读者模拟' },
  { path: '/visualize', icon: <Network size={20} />, label: '可视化工作台' },
  { path: '/chapter-evaluator', icon: <CheckCircle2 size={20} />, label: '章节判定器' },
  { path: '/director', icon: <Sliders size={20} />, label: '导演模式' },
  { path: '/novel', icon: <FileText size={20} />, label: '小说编辑器' },
  { path: '/diff', icon: <GitCompare size={20} />, label: '版本对比' },
  { path: '/settings', icon: <Settings size={20} />, label: '系统设置' },
]

export default function Layout({ children }: { children: React.ReactNode }) {
  return (
    <div className="min-h-screen bg-gray-50 flex">
      <aside className="w-64 bg-white border-r border-gray-200 fixed h-full overflow-y-auto">
        <div className="p-4">
          <h1 className="text-xl font-bold text-gray-800">🎬 GodView</h1>
          <p className="text-xs text-gray-500 mt-1">AI 小说生成系统</p>
        </div>

        <nav className="mt-4">
          {navItems.map((item) => (
            <NavLink
              key={item.path}
              to={item.path}
              className={({ isActive }) =>
                `flex items-center gap-3 px-4 py-3 text-sm transition-colors ${
                  isActive
                    ? 'bg-blue-50 text-blue-600 border-r-2 border-blue-600'
                    : 'text-gray-600 hover:bg-gray-50 hover:text-gray-900'
                }`
              }
            >
              {item.icon}
              <span>{item.label}</span>
            </NavLink>
          ))}
        </nav>
      </aside>

      <main className="ml-64 flex-1 p-8">
        {children}
      </main>
    </div>
  )
}
