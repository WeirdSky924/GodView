import { forwardRef } from 'react'
import { useTheme } from '@/contexts/ThemeContext'

export interface TextAreaProps extends React.TextareaHTMLAttributes<HTMLTextAreaElement> {
  label?: string
  error?: string
}

export const TextArea = forwardRef<HTMLTextAreaElement, TextAreaProps>(
  ({ label, error, className = '', ...props }, ref) => {
    const { theme } = useTheme()
    const isDark = theme === 'dark'

    return (
      <div className="w-full">
        {label && (
          <label className={`block text-sm font-medium mb-1 ${isDark ? 'text-gray-300' : 'text-gray-700'}`}>
            {label}
          </label>
        )}
        <textarea
          ref={ref}
          className={`w-full px-3 py-2 border rounded-lg shadow-sm transition-colors min-h-[100px] resize-y ${
            isDark
              ? `bg-gray-800/50 text-white placeholder-gray-500 ${
                  error ? 'border-red-500 focus:ring-red-500/50' : 'border-gray-700 focus:ring-blue-500/50'
                }`
              : `bg-white text-gray-800 placeholder-gray-400 ${
                  error ? 'border-red-400 focus:ring-red-400/50' : 'border-gray-300 focus:ring-blue-500/30'
                }`
          } focus:outline-none focus:ring-2 focus:border-transparent ${className}`}
          {...props}
        />
        {error && (
          <p className="mt-1 text-sm text-red-500">{error}</p>
        )}
      </div>
    )
  }
)

TextArea.displayName = 'TextArea'
