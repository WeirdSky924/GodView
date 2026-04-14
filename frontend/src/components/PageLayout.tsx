/**
 * 页面布局组件
 * 统一页面结构：固定顶部标题栏 + 可滚动内容区
 */

import { ReactNode } from 'react'
import { useTheme } from '@/contexts/ThemeContext'

interface PageLayoutProps {
  title: string
  description?: string
  actions?: ReactNode
  children: ReactNode
  tabs?: {
    key: string
    label: string
    icon?: ReactNode
  }[]
  activeTab?: string
  onTabChange?: (key: string) => void
  filters?: ReactNode
}

export default function PageLayout({
  title,
  description,
  actions,
  children,
  tabs,
  activeTab,
  onTabChange,
  filters,
}: PageLayoutProps) {
  const { theme } = useTheme()
  const isDark = theme === 'dark'

  return (
    <div className="h-[calc(100vh-4rem)] flex flex-col relative">
      {/* 固定的顶部区域 - 考虑侧边栏宽度 (ml-64 = 16rem = 256px) */}
      <div className={`sticky top-0 z-50 ${isDark ? 'bg-gray-900/95' : 'bg-white/95'} backdrop-blur-sm border-b ${isDark ? 'border-gray-700' : 'border-gray-200'}`}>
        {/* 标题和操作按钮 */}
        <div className="p-4">
          <div className="flex items-center justify-between">
            <div>
              <h1 className={`text-2xl font-bold ${isDark ? 'text-white' : 'text-gray-800'}`}>{title}</h1>
              {description && (
                <p className={`text-sm mt-1 ${isDark ? 'text-gray-400' : 'text-gray-500'}`}>{description}</p>
              )}
            </div>
            {actions && <div className="flex gap-2">{actions}</div>}
          </div>
        </div>

        {/* Tab 切换 */}
        {tabs && tabs.length > 0 && (
          <div className="px-4 py-2">
            <div className="flex gap-2">
              {tabs.map((tab) => (
                <button
                  key={tab.key}
                  onClick={() => onTabChange?.(tab.key)}
                  className={`flex items-center gap-2 px-4 py-2 rounded-lg transition-colors ${
                    activeTab === tab.key
                      ? 'bg-blue-600 text-white'
                      : isDark
                        ? 'bg-gray-800 hover:bg-gray-700 text-gray-300'
                        : 'bg-gray-100 hover:bg-gray-200 text-gray-700'
                  }`}
                >
                  {tab.icon}
                  {tab.label}
                </button>
              ))}
            </div>
          </div>
        )}

        {/* 筛选器区域 */}
        {filters && (
          <div className="px-4 py-3">
            {filters}
          </div>
        )}
      </div>

      {/* 可滚动的内容区域 */}
      <div className="flex-1 overflow-auto p-4">
        {children}
      </div>
    </div>
  )
}
