import { useState, useEffect } from 'react'
import { NavLink, useNavigate, useLocation } from 'react-router-dom'
import {
  LayoutDashboard, Users, Globe, BookOpen, BookMarked, FileText, Settings, Flag, GitCompare, ShieldAlert, Eye, Network, Mic2, CheckCircle2, FolderOpen, ChevronDown, Plus, Layers, MessageSquare, Bot, PenTool, Sparkles, Sun, Moon, Database, Server, AlertCircle, CheckCircle, XCircle, Clapperboard, Play, ListTree, MapPin
} from 'lucide-react'
import { useProject } from '@/contexts/ProjectContext'
import { useTheme } from '@/contexts/ThemeContext'
import { motion, AnimatePresence } from 'framer-motion'
import { getDatabaseStatus } from '@/api/config'
import type { DatabaseStatusResponse } from '@/api/config'

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
  { path: '/world-map', icon: <MapPin size={20} />, label: '地图管理' },
  { path: '/lore', icon: <BookMarked size={20} />, label: '设定库' },
  { path: '/plots', icon: <BookOpen size={20} />, label: '剧情管理' },
  { path: '/outlines', icon: <ListTree size={20} />, label: '章节大纲' },
  { path: '/hooks', icon: <Flag size={20} />, label: '伏笔管理' },
  { path: '/interventions', icon: <ShieldAlert size={20} />, label: '干预日志' },
  { path: '/simulator', icon: <Eye size={20} />, label: '读者模拟' },
  { path: '/visualize', icon: <Network size={20} />, label: '可视化工作台' },
  { path: '/chapter-evaluator', icon: <CheckCircle2 size={20} />, label: '章节判定器' },
  { path: '/novel', icon: <FileText size={20} />, label: '小说编辑器' },
  { path: '/skills', icon: <Layers size={20} />, label: 'Agent Skills' },
  { path: '/prompts', icon: <MessageSquare size={20} />, label: 'Prompt 库' },
  { path: '/agent-templates', icon: <Bot size={20} />, label: 'Agent 模板' },
  { path: '/writing-rules', icon: <PenTool size={20} />, label: '写作规则' },
  { path: '/diff', icon: <GitCompare size={20} />, label: '版本对比' },
  { path: '/settings', icon: <Settings size={20} />, label: '系统设置' },
]

const icpNumber = (import.meta as { env?: { VITE_ICP_NUMBER?: string } }).env?.VITE_ICP_NUMBER

export default function Layout({ children }: { children: React.ReactNode }) {
  const { currentProject, projects, setCurrentProject, loading } = useProject()
  const { theme, toggleTheme } = useTheme()
  const navigate = useNavigate()
  const location = useLocation()
  const [showProjectMenu, setShowProjectMenu] = useState(false)
  const [dbStatus, setDbStatus] = useState<DatabaseStatusResponse | null>(null)
  const [showDbPopover, setShowDbPopover] = useState(false)

  const isDark = theme === 'dark'

  // 仅在设置页或状态浮窗打开时获取数据库状态
  useEffect(() => {
    const shouldFetchDbStatus = location.pathname === '/settings' || showDbPopover

    if (!shouldFetchDbStatus) {
      return
    }

    const fetchDbStatus = async () => {
      try {
        const status = await getDatabaseStatus()
        setDbStatus(status)
      } catch (e) {
        console.error('Failed to fetch database status:', e)
      }
    }

    fetchDbStatus()
    const interval = setInterval(fetchDbStatus, 60000)
    return () => clearInterval(interval)
  }, [location.pathname, showDbPopover])

  return (
    <div className={`min-h-screen flex ${isDark ? 'bg-gradient-to-br from-gray-900 via-gray-900 to-slate-900' : 'bg-gradient-to-br from-slate-50 via-white to-blue-50'}`}>
      {/* 侧边栏 */}
      <aside className="w-64 glass-sidebar fixed h-full flex flex-col">
        {/* 固定的顶部区域：Logo + 项目选择器 */}
        <div className="sticky top-0 z-20 glass-sidebar">
          {/* Logo */}
          <div className="p-4 border-b" style={{ borderColor: 'var(--sidebar-border)' }}>
            <motion.div
              className="flex items-center justify-between"
              initial={{ opacity: 0, y: -10 }}
              animate={{ opacity: 1, y: 0 }}
            >
              <div className="flex items-center gap-2">
                <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-blue-500 to-purple-600 flex items-center justify-center glow-primary">
                  <Sparkles className="w-5 h-5 text-white" />
                </div>
                <div>
                  <h1 className="text-xl font-bold gradient-text">GodView</h1>
                  <p className={`text-xs ${isDark ? 'text-gray-500' : 'text-gray-400'}`}>AI 小说生成系统</p>
                </div>
              </div>
              {/* 主题切换按钮 */}
              <motion.button
                onClick={toggleTheme}
                className={`p-2 rounded-lg transition-colors ${isDark ? 'bg-gray-800 hover:bg-gray-700 text-yellow-400' : 'bg-gray-100 hover:bg-gray-200 text-blue-600'}`}
                whileHover={{ scale: 1.1, rotate: 15 }}
                whileTap={{ scale: 0.9 }}
                title={isDark ? '切换到明亮模式' : '切换到黑暗模式'}
              >
                {isDark ? <Sun size={18} /> : <Moon size={18} />}
              </motion.button>
            </motion.div>
          </div>

          {/* 项目选择器 - 固定不动 */}
          <div className="p-4 border-b" style={{ borderColor: 'var(--sidebar-border)' }}>
            <div className="relative">
              <motion.button
                onClick={() => setShowProjectMenu(!showProjectMenu)}
                className={`w-full flex items-center justify-between p-3 rounded-xl transition-colors border ${
                  isDark
                    ? 'bg-gray-800/50 hover:bg-gray-800 border-gray-700'
                    : 'bg-white hover:bg-gray-50 border-gray-200 shadow-sm'
                }`}
                disabled={loading}
                whileHover={{ scale: 1.01 }}
                whileTap={{ scale: 0.99 }}
              >
                <div className="flex items-center gap-2">
                  <FolderOpen size={18} className="text-blue-500" />
                  <span className={`font-medium truncate ${isDark ? 'text-white' : 'text-gray-800'}`}>
                    {loading ? '加载中...' : currentProject?.name || '选择项目'}
                  </span>
                </div>
                <motion.div
                  animate={{ rotate: showProjectMenu ? 180 : 0 }}
                  transition={{ duration: 0.2 }}
                >
                  <ChevronDown size={16} className={isDark ? 'text-gray-400' : 'text-gray-500'} />
                </motion.div>
              </motion.button>

              <AnimatePresence>
                {showProjectMenu && (
                  <motion.div
                    initial={{ opacity: 0, y: -10 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={{ opacity: 0, y: -10 }}
                    className={`absolute top-full left-0 right-0 mt-2 border rounded-xl shadow-xl z-50 max-h-64 overflow-auto ${
                      isDark ? 'bg-gray-800 border-gray-700' : 'bg-white border-gray-200'
                    }`}
                  >
                    {projects.length === 0 ? (
                      <div className={`px-4 py-3 text-sm ${isDark ? 'text-gray-500' : 'text-gray-400'}`}>暂无项目</div>
                    ) : (
                      projects.map(project => (
                        <motion.button
                          key={project.id}
                          onClick={() => {
                            setCurrentProject(project)
                            setShowProjectMenu(false)
                          }}
                          className={`w-full text-left px-4 py-2 flex items-center gap-2 transition-colors ${
                            currentProject?.id === project.id
                              ? isDark
                                ? 'bg-blue-900/30 text-blue-400'
                                : 'bg-blue-50 text-blue-600'
                              : isDark
                                ? 'text-gray-300 hover:bg-gray-700'
                                : 'text-gray-700 hover:bg-gray-50'
                          }`}
                          whileHover={{ x: 4 }}
                        >
                          <FolderOpen size={16} />
                          <span className="truncate">{project.name}</span>
                        </motion.button>
                      ))
                    )}
                    <div className={`border-t ${isDark ? 'border-gray-700' : 'border-gray-100'}`}>
                      <NavLink
                        to="/project-setup"
                        onClick={() => setShowProjectMenu(false)}
                        className={`w-full text-left px-4 py-2 flex items-center gap-2 text-blue-500 transition-colors ${
                          isDark ? 'hover:bg-gray-700' : 'hover:bg-gray-50'
                        }`}
                      >
                        <Plus size={16} />
                        <span>新建项目</span>
                      </NavLink>
                    </div>
                  </motion.div>
                )}
              </AnimatePresence>
            </div>
          </div>

          {/* 上帝模式入口 - 炫酷按钮 */}
          <div className="p-4">
            <motion.button
              onClick={() => navigate('/director')}
              className="relative w-full overflow-hidden rounded-xl"
              whileHover={{ scale: 1.02 }}
              whileTap={{ scale: 0.98 }}
            >
              {/* 背景动画层 */}
              <div className="absolute inset-0 bg-gradient-to-r from-violet-600 via-purple-600 to-fuchsia-600 animate-pulse-slow" />

              {/* 光效流动层 */}
              <div className="absolute inset-0 bg-gradient-to-r from-transparent via-white/20 to-transparent animate-shimmer" />

              {/* 星星粒子效果 */}
              <div className="absolute inset-0 overflow-hidden">
                {[...Array(6)].map((_, i) => (
                  <motion.div
                    key={i}
                    className="absolute w-1 h-1 bg-white rounded-full"
                    initial={{
                      x: Math.random() * 100 + '%',
                      y: '100%',
                      opacity: 0
                    }}
                    animate={{
                      y: '-10%',
                      opacity: [0, 1, 0]
                    }}
                    transition={{
                      duration: 2 + Math.random(),
                      repeat: Infinity,
                      delay: i * 0.3
                    }}
                  />
                ))}
              </div>

              {/* 内容 */}
              <div className="relative px-4 py-3 flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <motion.div
                    animate={{ rotate: [0, 10, -10, 0] }}
                    transition={{ duration: 2, repeat: Infinity, ease: "easeInOut" }}
                  >
                    <Clapperboard className="w-6 h-6 text-white" />
                  </motion.div>
                  <div className="text-left">
                    <div className="text-white font-bold text-sm flex items-center gap-1.5">
                      上帝模式
                      <motion.span
                        animate={{ scale: [1, 1.2, 1] }}
                        transition={{ duration: 1.5, repeat: Infinity }}
                      >
                        ✨
                      </motion.span>
                    </div>
                    <div className="text-white/70 text-xs">一键生成章节</div>
                  </div>
                </div>
                <motion.div
                  animate={{ x: [0, 4, 0] }}
                  transition={{ duration: 1.5, repeat: Infinity }}
                >
                  <Play className="w-5 h-5 text-white" fill="white" />
                </motion.div>
              </div>
            </motion.button>
          </div>
        </div>

        {/* 可滚动的导航菜单 */}
        <nav className="flex-1 overflow-y-auto px-2 py-2">
          {navItems.map((item, index) => (
            <NavLink
              key={item.path}
              to={item.path}
              className={({ isActive }) =>
                `flex items-center gap-3 px-4 py-2.5 text-sm rounded-xl mb-1 transition-all ${
                  isActive
                    ? isDark
                      ? 'bg-gradient-to-r from-blue-600/20 to-purple-600/20 text-white border border-blue-500/30'
                      : 'bg-gradient-to-r from-blue-500/10 to-purple-500/10 text-blue-700 border border-blue-200'
                    : isDark
                      ? 'text-gray-400 hover:text-white hover:bg-gray-800/50'
                      : 'text-gray-600 hover:text-gray-900 hover:bg-gray-100'
                }`
              }
            >
              {({ isActive }) => (
                <motion.div
                  className="flex items-center gap-3 w-full"
                  initial={{ opacity: 0, x: -10 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ delay: index * 0.02 }}
                  whileHover={{ x: 4 }}
                >
                  <span className={isActive ? 'text-blue-500' : ''}>{item.icon}</span>
                  <span>{item.label}</span>
                </motion.div>
              )}
            </NavLink>
          ))}
        </nav>

        {/* 底部信息 */}
        <div className={`p-4 border-t text-xs ${isDark ? 'border-gray-700 text-gray-500' : 'border-gray-200 text-gray-400'}`}>
          {icpNumber && (
            <a
              href="https://beian.miit.gov.cn/"
              target="_blank"
              rel="noopener noreferrer"
              className={`mb-2 block truncate transition-colors ${isDark ? 'hover:text-gray-300' : 'hover:text-gray-600'}`}
              title={icpNumber}
            >
              {icpNumber}
            </a>
          )}
          <div className="flex items-center justify-between">
            <span>v7.0.0</span>
            <div className="flex items-center gap-2">
              {/* 数据库状态指示器 */}
              <div
                className="relative"
                onMouseEnter={() => setShowDbPopover(true)}
                onMouseLeave={() => setShowDbPopover(false)}
              >
                <div className="flex items-center gap-1 cursor-pointer">
                  <Database size={12} />
                  <span className={`w-2 h-2 rounded-full ${
                    dbStatus?.summary.status === 'healthy' ? 'bg-green-500' :
                    dbStatus?.summary.status === 'degraded' ? 'bg-yellow-500' : 'bg-red-500'
                  }`} />
                </div>

                {/* 悬停浮窗 */}
                <AnimatePresence>
                  {showDbPopover && dbStatus && (
                    <motion.div
                      initial={{ opacity: 0, y: 10 }}
                      animate={{ opacity: 1, y: 0 }}
                      exit={{ opacity: 0, y: 10 }}
                      className={`absolute bottom-full left-0 mb-2 w-56 p-3 rounded-lg shadow-xl z-50 border ${
                        isDark ? 'bg-gray-800 border-gray-700' : 'bg-white border-gray-200'
                      }`}
                    >
                      <div className={`text-sm font-medium mb-2 flex items-center gap-2 ${isDark ? 'text-white' : 'text-gray-800'}`}>
                        <Server size={14} />
                        数据库状态
                      </div>
                      <div className="space-y-2">
                        {dbStatus.databases.map((db) => (
                          <div key={db.name} className="flex items-center justify-between">
                            <div className="flex items-center gap-2">
                              {db.status === 'connected' ? (
                                <CheckCircle size={12} className="text-green-500" />
                              ) : db.status === 'reachable' ? (
                                <AlertCircle size={12} className="text-yellow-500" />
                              ) : (
                                <XCircle size={12} className="text-red-500" />
                              )}
                              <span className={`text-xs ${isDark ? 'text-gray-300' : 'text-gray-600'}`}>
                                {db.name}
                              </span>
                            </div>
                            <span className={`text-xs ${
                              db.status === 'connected' ? 'text-green-500' :
                              db.status === 'reachable' ? 'text-yellow-500' : 'text-red-500'
                            }`}>
                              {db.status === 'connected' ? '已连接' :
                               db.status === 'reachable' ? '可达' : '断开'}
                            </span>
                          </div>
                        ))}
                      </div>
                      <div className={`mt-2 pt-2 border-t text-xs ${isDark ? 'border-gray-700 text-gray-500' : 'border-gray-100 text-gray-400'}`}>
                        {dbStatus.summary.connected}/{dbStatus.summary.total} 已连接
                      </div>
                    </motion.div>
                  )}
                </AnimatePresence>
              </div>
              <span className={isDark ? 'text-gray-600' : 'text-gray-300'}>
                {isDark ? '🌙' : '☀️'}
              </span>
            </div>
          </div>
        </div>
      </aside>

      {/* 主内容区 */}
      <main className="ml-64 flex-1 p-8 min-h-screen overflow-auto">
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.3 }}
        >
          {children}
        </motion.div>
      </main>
    </div>
  )
}
