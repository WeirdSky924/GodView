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

function sameMachineWsBaseUrl() {
  return `${window.location.protocol === 'https:' ? 'wss:' : 'ws:'}//${window.location.host}`
}

function resolveBrowserWsBaseUrl(configuredUrl?: string) {
  if (!configuredUrl) return sameMachineWsBaseUrl()

  try {
    const url = new URL(configuredUrl)
    const browserHost = window.location.hostname
    const configuredHost = url.hostname
    const configuredPort = url.port

    if (
      configuredHost === 'localhost' ||
      configuredHost === '127.0.0.1' ||
      configuredHost === '0.0.0.0'
    ) {
      return sameMachineWsBaseUrl()
    }

    if (window.location.protocol === 'https:' && url.protocol === 'ws:') {
      url.protocol = 'wss:'
    }

    if (configuredPort === '80' || configuredPort === '443') {
      url.port = ''
    }

    return url.toString().replace(/\/$/, '')
  } catch {
    return sameMachineWsBaseUrl()
  }
}

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
      ws_base_url: sameMachineWsBaseUrl(),
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
  return resolveBrowserWsBaseUrl(config.ws_base_url)
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
