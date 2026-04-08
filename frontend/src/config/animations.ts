/**
 * 动画配置
 * 统一管理 framer-motion 动画参数
 */

export const transitions = {
  fast: { duration: 0.15 },
  normal: { duration: 0.3 },
  slow: { duration: 0.5 },
  spring: { type: 'spring' as const, stiffness: 300, damping: 30 },
  bouncy: { type: 'spring' as const, stiffness: 400, damping: 15 },
}

export const variants = {
  fadeIn: {
    initial: { opacity: 0 },
    animate: { opacity: 1 },
    exit: { opacity: 0 },
  },
  slideUp: {
    initial: { opacity: 0, y: 20 },
    animate: { opacity: 1, y: 0 },
    exit: { opacity: 0, y: -20 },
  },
  slideDown: {
    initial: { opacity: 0, y: -20 },
    animate: { opacity: 1, y: 0 },
    exit: { opacity: 0, y: 20 },
  },
  slideLeft: {
    initial: { opacity: 0, x: 20 },
    animate: { opacity: 1, x: 0 },
    exit: { opacity: 0, x: -20 },
  },
  slideRight: {
    initial: { opacity: 0, x: -20 },
    animate: { opacity: 1, x: 0 },
    exit: { opacity: 0, x: 20 },
  },
  scale: {
    initial: { opacity: 0, scale: 0.9 },
    animate: { opacity: 1, scale: 1 },
    exit: { opacity: 0, scale: 0.9 },
  },
  modal: {
    initial: { opacity: 0, scale: 0.95, y: 10 },
    animate: { opacity: 1, scale: 1, y: 0 },
    exit: { opacity: 0, scale: 0.95, y: 10 },
  },
}

export const staggerContainer = {
  initial: {},
  animate: {
    transition: {
      staggerChildren: 0.05,
    },
  },
}

export const staggerItem = {
  initial: { opacity: 0, y: 10 },
  animate: { opacity: 1, y: 0 },
}

// 颜色主题
export const colors = {
  primary: {
    from: '#3b82f6',
    to: '#8b5cf6',
  },
  secondary: {
    from: '#06b6d4',
    to: '#3b82f6',
  },
  accent: {
    from: '#f59e0b',
    to: '#ef4444',
  },
  success: '#10b981',
  warning: '#f59e0b',
  danger: '#ef4444',
}

// 发光效果配置
export const glowEffects = {
  primary: '0 0 20px rgba(59, 130, 246, 0.5)',
  secondary: '0 0 20px rgba(139, 92, 246, 0.5)',
  success: '0 0 20px rgba(16, 185, 129, 0.5)',
  warning: '0 0 20px rgba(245, 158, 11, 0.5)',
  danger: '0 0 20px rgba(239, 68, 68, 0.5)',
}
