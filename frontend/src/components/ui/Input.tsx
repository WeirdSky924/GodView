import { forwardRef, useState } from 'react'
import { motion } from 'framer-motion'
import { useTheme } from '@/contexts/ThemeContext'

export interface InputProps extends React.InputHTMLAttributes<HTMLInputElement> {
  label?: string
  error?: string
}

export const Input = forwardRef<HTMLInputElement, InputProps>(
  ({ label, error, className = '', onFocus, onBlur, ...props }, ref) => {
    const [isFocused, setIsFocused] = useState(false)
    const { theme } = useTheme()
    const isDark = theme === 'dark'

    return (
      <div className="w-full">
        {label && (
          <label className={`block text-sm font-medium mb-2 ${isDark ? 'text-gray-300' : 'text-gray-700'}`}>
            {label}
          </label>
        )}
        <motion.div
          animate={{
            scale: isFocused ? 1.01 : 1,
          }}
          transition={{ duration: 0.15 }}
        >
          <input
            ref={ref}
            className={`w-full px-4 py-2.5 border rounded-xl transition-all ${
              isDark
                ? `bg-gray-800/50 text-white placeholder-gray-500 ${
                    error
                      ? 'border-red-500 focus:ring-red-500/50'
                      : 'border-gray-700 focus:border-blue-500 focus:ring-blue-500/50'
                  }`
                : `bg-white text-gray-800 placeholder-gray-400 ${
                    error
                      ? 'border-red-400 focus:ring-red-400/50'
                      : 'border-gray-300 focus:border-blue-500 focus:ring-blue-500/30'
                  }`
            } focus:outline-none focus:ring-2 ${className}`}
            onFocus={(e) => {
              setIsFocused(true)
              onFocus?.(e)
            }}
            onBlur={(e) => {
              setIsFocused(false)
              onBlur?.(e)
            }}
            {...props}
          />
        </motion.div>
        {error && (
          <motion.p
            initial={{ opacity: 0, y: -5 }}
            animate={{ opacity: 1, y: 0 }}
            className="mt-1.5 text-sm text-red-500"
          >
            {error}
          </motion.p>
        )}
      </div>
    )
  }
)

Input.displayName = 'Input'
