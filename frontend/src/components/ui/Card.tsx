import { ReactNode, MouseEventHandler } from 'react'
import { motion } from 'framer-motion'
import { useTheme } from '@/contexts/ThemeContext'

interface CardProps {
  children: ReactNode
  className?: string
  title?: string
  description?: string
  action?: ReactNode
  hover?: boolean
  noPadding?: boolean
  onClick?: MouseEventHandler<HTMLDivElement>
}

export function Card({ children, className = '', title, description, action, hover = false, noPadding = false, onClick }: CardProps) {
  const { theme } = useTheme()
  const isDark = theme === 'dark'

  return (
    <motion.div
      className={`backdrop-blur-sm rounded-xl border transition-colors ${
        isDark
          ? `bg-gray-800/50 border-gray-700/50 ${hover ? 'hover:border-blue-500/50' : ''}`
          : `bg-white border-gray-200 shadow-sm ${hover ? 'hover:border-blue-300 hover:shadow-md' : ''}`
      } ${className}`}
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      whileHover={hover ? { y: -2 } : undefined}
      transition={{ duration: 0.2 }}
      onClick={onClick}
    >
      {(title || description || action) && (
        <div className={`px-6 py-4 border-b flex items-start justify-between ${
          isDark ? 'border-gray-700/50' : 'border-gray-100'
        }`}>
          <div>
            {title && <h3 className={`text-lg font-semibold ${isDark ? 'text-white' : 'text-gray-800'}`}>{title}</h3>}
            {description && <p className={`text-sm mt-1 ${isDark ? 'text-gray-400' : 'text-gray-500'}`}>{description}</p>}
          </div>
          {action && <div>{action}</div>}
        </div>
      )}
      {noPadding ? children : <div className="p-6">{children}</div>}
    </motion.div>
  )
}
