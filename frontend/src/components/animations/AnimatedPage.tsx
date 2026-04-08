/**
 * 动画组件库
 * 基于 framer-motion 的通用动画组件
 */

import { motion, AnimatePresence, Variants } from 'framer-motion'
import { ReactNode } from 'react'
import { transitions, variants, staggerContainer, staggerItem } from '@/config/animations'

// ==================== 页面包装器 ====================

interface AnimatedPageProps {
  children: ReactNode
  className?: string
}

export function AnimatedPage({ children, className = '' }: AnimatedPageProps) {
  return (
    <motion.div
      initial="initial"
      animate="animate"
      exit="exit"
      variants={variants.fadeIn}
      transition={transitions.normal}
      className={className}
    >
      {children}
    </motion.div>
  )
}

// ==================== 卡片动画 ====================

interface AnimatedCardProps {
  children: ReactNode
  className?: string
  delay?: number
  hover?: boolean
  onClick?: () => void
}

export function AnimatedCard({ children, className = '', delay = 0, hover = true, onClick }: AnimatedCardProps) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -10 }}
      transition={{ ...transitions.normal, delay }}
      whileHover={hover ? { y: -4, boxShadow: '0 10px 40px rgba(0, 0, 0, 0.3)' } : undefined}
      whileTap={onClick ? { scale: 0.98 } : undefined}
      onClick={onClick}
      className={className}
    >
      {children}
    </motion.div>
  )
}

// ==================== 按钮动画 ====================

interface AnimatedButtonProps {
  children: ReactNode
  className?: string
  onClick?: () => void
  disabled?: boolean
  variant?: 'primary' | 'secondary' | 'danger'
}

export function AnimatedButton({ children, className = '', onClick, disabled, variant = 'primary' }: AnimatedButtonProps) {
  const glowColors = {
    primary: '0 0 15px rgba(59, 130, 246, 0.4)',
    secondary: '0 0 15px rgba(156, 163, 175, 0.3)',
    danger: '0 0 15px rgba(239, 68, 68, 0.4)',
  }

  return (
    <motion.button
      whileHover={!disabled ? { scale: 1.02, boxShadow: glowColors[variant] } : undefined}
      whileTap={!disabled ? { scale: 0.98 } : undefined}
      transition={transitions.fast}
      onClick={onClick}
      disabled={disabled}
      className={className}
    >
      {children}
    </motion.button>
  )
}

// ==================== 列表动画（交错进入） ====================

interface AnimatedListProps {
  children: ReactNode
  className?: string
}

export function AnimatedList({ children, className = '' }: AnimatedListProps) {
  return (
    <motion.div
      initial="initial"
      animate="animate"
      variants={staggerContainer}
      className={className}
    >
      {children}
    </motion.div>
  )
}

interface AnimatedListItemProps {
  children: ReactNode
  className?: string
}

export function AnimatedListItem({ children, className = '' }: AnimatedListItemProps) {
  return (
    <motion.div variants={staggerItem} className={className}>
      {children}
    </motion.div>
  )
}

// ==================== 弹窗动画 ====================

interface AnimatedModalProps {
  isOpen: boolean
  onClose: () => void
  children: ReactNode
  className?: string
}

export function AnimatedModal({ isOpen, onClose, children, className = '' }: AnimatedModalProps) {
  return (
    <AnimatePresence>
      {isOpen && (
        <motion.div
          className="fixed inset-0 z-50 flex items-center justify-center"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
        >
          {/* Backdrop */}
          <motion.div
            className="absolute inset-0 bg-black/60 backdrop-blur-sm"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={onClose}
          />
          {/* Content */}
          <motion.div
            className={`relative ${className}`}
            variants={variants.modal}
            initial="initial"
            animate="animate"
            exit="exit"
            transition={transitions.spring}
          >
            {children}
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  )
}

// ==================== 渐入动画 ====================

interface FadeInProps {
  children: ReactNode
  className?: string
  delay?: number
  direction?: 'up' | 'down' | 'left' | 'right' | 'none'
}

export function FadeIn({ children, className = '', delay = 0, direction = 'up' }: FadeInProps) {
  const directionVariants: Record<string, Variants> = {
    up: variants.slideUp,
    down: variants.slideDown,
    left: variants.slideLeft,
    right: variants.slideRight,
    none: variants.fadeIn,
  }

  return (
    <motion.div
      initial="initial"
      animate="animate"
      exit="exit"
      variants={directionVariants[direction]}
      transition={{ ...transitions.normal, delay }}
      className={className}
    >
      {children}
    </motion.div>
  )
}

// ==================== 滑入动画 ====================

interface SlideInProps {
  children: ReactNode
  className?: string
  direction?: 'left' | 'right' | 'top' | 'bottom'
  delay?: number
}

export function SlideIn({ children, className = '', direction = 'left', delay = 0 }: SlideInProps) {
  const initialPosition = {
    left: { x: -50, y: 0 },
    right: { x: 50, y: 0 },
    top: { x: 0, y: -50 },
    bottom: { x: 0, y: 50 },
  }

  return (
    <motion.div
      initial={{ opacity: 0, ...initialPosition[direction] }}
      animate={{ opacity: 1, x: 0, y: 0 }}
      exit={{ opacity: 0, ...initialPosition[direction] }}
      transition={{ ...transitions.normal, delay }}
      className={className}
    >
      {children}
    </motion.div>
  )
}

// ==================== 漂浮装饰元素 ====================

interface FloatingElementProps {
  children: ReactNode
  className?: string
  duration?: number
  distance?: number
}

export function FloatingElement({ children, className = '', duration = 3, distance = 10 }: FloatingElementProps) {
  return (
    <motion.div
      animate={{
        y: [-distance, distance, -distance],
      }}
      transition={{
        duration,
        repeat: Infinity,
        ease: 'easeInOut',
      }}
      className={className}
    >
      {children}
    </motion.div>
  )
}

// ==================== 骨架屏 ====================

interface ShimmerProps {
  className?: string
  width?: string | number
  height?: string | number
}

export function Shimmer({ className = '', width = '100%', height = '20px' }: ShimmerProps) {
  return (
    <motion.div
      className={`relative overflow-hidden rounded bg-gray-700 ${className}`}
      style={{ width, height }}
    >
      <motion.div
        className="absolute inset-0 bg-gradient-to-r from-transparent via-gray-600 to-transparent"
        animate={{ x: ['-100%', '100%'] }}
        transition={{ duration: 1.5, repeat: Infinity, ease: 'linear' }}
      />
    </motion.div>
  )
}

// ==================== 加载动画 ====================

interface LoadingSpinnerProps {
  size?: number
  color?: string
  className?: string
}

export function LoadingSpinner({ size = 24, color = '#3b82f6', className = '' }: LoadingSpinnerProps) {
  return (
    <motion.div
      className={`inline-block ${className}`}
      animate={{ rotate: 360 }}
      transition={{ duration: 1, repeat: Infinity, ease: 'linear' }}
      style={{ width: size, height: size }}
    >
      <svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
        <circle
          cx="12"
          cy="12"
          r="10"
          stroke={color}
          strokeWidth="3"
          strokeLinecap="round"
          strokeDasharray="31.4 31.4"
        />
      </svg>
    </motion.div>
  )
}

// ==================== 渐变背景 ====================

interface GradientBackgroundProps {
  children?: ReactNode
  className?: string
  colors?: string[]
  animated?: boolean
}

export function GradientBackground({
  children,
  className = '',
  colors = ['#3b82f6', '#8b5cf6', '#06b6d4'],
  animated = true,
}: GradientBackgroundProps) {
  const gradientStyle = {
    background: `linear-gradient(135deg, ${colors.join(', ')})`,
    backgroundSize: animated ? '200% 200%' : undefined,
  }

  return (
    <motion.div
      className={className}
      style={gradientStyle}
      animate={
        animated
          ? {
              backgroundPosition: ['0% 0%', '100% 100%', '0% 0%'],
            }
          : undefined
      }
      transition={
        animated
          ? {
              duration: 10,
              repeat: Infinity,
              ease: 'linear',
            }
          : undefined
      }
    >
      {children}
    </motion.div>
  )
}

// ==================== 数字跳动动画 ====================

interface AnimatedNumberProps {
  value: number
  duration?: number
  className?: string
}

export function AnimatedNumber({ value, duration = 0.5, className = '' }: AnimatedNumberProps) {
  return (
    <motion.span
      key={value}
      initial={{ opacity: 0, y: -10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration }}
      className={className}
    >
      {value}
    </motion.span>
  )
}

// ==================== 打字效果 ====================

interface TypewriterProps {
  text: string
  speed?: number
  className?: string
  onComplete?: () => void
}

export function Typewriter({ text, speed = 50, className = '', onComplete }: TypewriterProps) {
  return (
    <motion.span className={className}>
      {text.split('').map((char, index) => (
        <motion.span
          key={index}
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: index * (speed / 1000), duration: 0.05 }}
          onAnimationComplete={index === text.length - 1 ? onComplete : undefined}
        >
          {char}
        </motion.span>
      ))}
    </motion.span>
  )
}

// ==================== 导出所有组件 ====================

export default {
  AnimatedPage,
  AnimatedCard,
  AnimatedButton,
  AnimatedList,
  AnimatedListItem,
  AnimatedModal,
  FadeIn,
  SlideIn,
  FloatingElement,
  Shimmer,
  LoadingSpinner,
  GradientBackground,
  AnimatedNumber,
  Typewriter,
}
