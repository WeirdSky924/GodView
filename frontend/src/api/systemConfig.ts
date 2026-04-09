/**
 * 系统配置服务
 * 从后端获取前端需要的配置信息
 */

import { api } from './client'

export interface SystemConfig {
  app_name: string
  app_version: string
  api_base_url: string
  ws_base_url: string
}

// 缓存配置，避免重复请求
let cachedConfig: SystemConfig | null = null

/**
 * 获取系统配置
 */
export async function getSystemConfig(): Promise<SystemConfig> {
  if (cachedConfig) {
    return cachedConfig
  }

  try {
    cachedConfig = await api.get<SystemConfig>('/config/system')
    return cachedConfig
  } catch (error) {
    console.error('Failed to fetch system config, using defaults:', error)
    // 返回默认配置
    const defaultConfig: SystemConfig = {
      app_name: 'Godview',
      app_version: '1.0.0',
      api_base_url: window.location.origin,
      ws_base_url: `${window.location.protocol === 'https:' ? 'wss:' : 'ws:'}//${window.location.host}`,
    }
    cachedConfig = defaultConfig
    return defaultConfig
  }
}

/**
 * 获取 WebSocket 基础 URL
 */
export async function getWsBaseUrl(): Promise<string> {
  const config = await getSystemConfig()
  return config.ws_base_url
}

/**
 * 获取 API 基础 URL
 */
export async function getApiBaseUrl(): Promise<string> {
  const config = await getSystemConfig()
  return config.api_base_url
}

/**
 * 清除配置缓存（用于配置更新后刷新）
 */
export function clearConfigCache(): void {
  cachedConfig = null
}
