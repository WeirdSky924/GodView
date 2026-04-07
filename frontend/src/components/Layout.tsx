import { useState } from 'react'
import { NavLink } from 'react-router-dom'
import {
  LayoutDashboard, Users, Globe, BookOpen, BookMarked, Sliders, FileText, Settings, Flag, GitCompare, ShieldAlert, Eye, Network, Mic2, CheckCircle2, FolderOpen, ChevronDown, Plus, Layers
} from 'lucide-react'
import { useProject } from '@/contexts/ProjectContext'

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
  { path: '/lore', icon: <BookMarked size={20} />, label: '设定库' },
  { path: '/plots', icon: <BookOpen size={20} />, label: '剧情管理' },
  { path: '/hooks', icon: <Flag size={20} />, label: '伏笔管理' },
  { path: '/interventions', icon: <ShieldAlert size={20} />, label: '干预日志' },
  { path: '/simulator', icon: <Eye size={20} />, label: '读者模拟' },
  { path: '/visualize', icon: <Network size={20} />, label: '可视化工作台' },
  { path: '/chapter-evaluator', icon: <CheckCircle2 size={20} />, label: '章节判定器' },
  { path: '/director', icon: <Sliders size={20} />, label: '导演模式' },
  { path: '/novel', icon: <FileText size={20} />, label: '小说编辑器' },
  { path: '/skills', icon: <Layers size={20} />, label: 'Agent Skills' },
  { path: '/diff', icon: <GitCompare size={20} />, label: '版本对比' },
  { path: '/settings', icon: <Settings size={20} />, label: '系统设置' },
]

export default function Layout({ children }: { children: React.ReactNode }) {
  const { currentProject, projects, setCurrentProject, loading } = useProject()
  const [showProjectMenu, setShowProjectMenu] = useState(false)

  return (
    <div className="min-h-screen bg-gray-50 flex">
      <aside className="w-64 bg-white border-r border-gray-200 fixed h-full overflow-y-auto">
        {/* 项目选择器 */}
        <div className="p-4 border-b">
          <div className="relative">
            <button
              onClick={() => setShowProjectMenu(!showProjectMenu)}
              className="w-full flex items-center justify-between p-3 bg-gray-50 rounded-lg hover:bg-gray-100 transition-colors"
              disabled={loading}
            >
              <div className="flex items-center gap-2">
                <FolderOpen size={18} className="text-blue-600" />
                <span className="font-medium text-gray-800 truncate">
                  {loading ? '加载中...' : currentProject?.name || '选择项目'}
                </span>
              </div>
              <ChevronDown size={16} className={`text-gray-400 transition-transform ${showProjectMenu ? 'rotate-180' : ''}`} />
            </button>

            {showProjectMenu && (
              <div className="absolute top-full left-0 right-0 mt-1 bg-white border rounded-lg shadow-lg z-50 max-h-64 overflow-auto">
                {projects.length === 0 ? (
                  <div className="px-4 py-3 text-gray-500 text-sm">暂无项目</div>
                ) : (
                  projects.map(project => (
                    <button
                      key={project.id}
                      onClick={() => {
                        setCurrentProject(project)
                        setShowProjectMenu(false)
                      }}
                      className={`w-full text-left px-4 py-2 hover:bg-gray-50 flex items-center gap-2 transition-colors ${
                        currentProject?.id === project.id ? 'bg-blue-50 text-blue-600' : ''
                      }`}
                    >
                      <FolderOpen size={16} />
                      <span className="truncate">{project.name}</span>
                    </button>
                  ))
                )}
                <div className="border-t">
                  <NavLink
                    to="/project-setup"
                    onClick={() => setShowProjectMenu(false)}
                    className="w-full text-left px-4 py-2 hover:bg-gray-50 flex items-center gap-2 text-blue-600"
                  >
                    <Plus size={16} />
                    <span>新建项目</span>
                  </NavLink>
                </div>
              </div>
            )}
          </div>
        </div>

        {/* Logo */}
        <div className="p-4">
          <h1 className="text-xl font-bold text-gray-800">🎬 GodView</h1>
          <p className="text-xs text-gray-500 mt-1">AI 小说生成系统</p>
        </div>

        {/* 导航菜单 */}
        <nav className="mt-2">
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
