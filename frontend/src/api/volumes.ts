/**
 * 卷规划 API 客户端
 * GodView v9: 卷级规划系统
 */

import { api as apiClient } from './client';

// ==================== 类型定义 ====================

export interface VolumeOutline {
  id: string;
  project_id: string;
  volume_number: number;
  title: string;
  theme: string;
  summary: string;
  start_chapter: number;
  end_chapter: number;
  target_word_count: number;
  climax_description: string;
  climax_chapter: number | null;
  emotional_arc: EmotionArcPoint[];
  key_events: KeyEvent[];
  status: 'planning' | 'active' | 'completed';
  created_at: string;
}

export interface EmotionArcPoint {
  chapter: number;
  emotion: string;
  intensity: number;
  description: string;
}

export interface KeyEvent {
  chapter: number;
  event: string;
  type: string;
}

export interface CreateVolumeRequest {
  project_id: string;
  volume_number: number;
  title: string;
  theme?: string;
  start_chapter: number;
  end_chapter: number;
  target_word_count?: number;
}

export interface UpdateVolumeRequest {
  title?: string;
  theme?: string;
  summary?: string;
  climax_description?: string;
  climax_chapter?: number;
}

export interface PlanVolumeRequest {
  project_id: string;
  volume_number: number;
  theme?: string;
  total_chapters?: number;
  genre?: string;
}

export interface DesignClimaxRequest {
  project_id: string;
  volume_number: number;
  emotional_peak?: number;
  key_characters?: string[];
  conflict_resolution?: string;
}

// ==================== API 函数 ====================

/**
 * 获取卷列表
 */
export async function getVolumes(projectId: string): Promise<VolumeOutline[]> {
  const response = await apiClient.get('/volumes', {
    params: { project_id: projectId },
  });
  return response.data;
}

/**
 * 创建卷
 */
export async function createVolume(data: CreateVolumeRequest): Promise<VolumeOutline> {
  const response = await apiClient.post('/volumes', data);
  return response.data;
}

/**
 * AI 规划卷大纲
 */
export async function planVolume(data: PlanVolumeRequest): Promise<VolumeOutline> {
  const response = await apiClient.post('/volumes/plan', data);
  return response.data;
}

/**
 * 获取卷详情
 */
export async function getVolume(volumeNumber: number, projectId: string): Promise<VolumeOutline> {
  const response = await apiClient.get(`/volumes/${volumeNumber}`, {
    params: { project_id: projectId },
  });
  return response.data;
}

/**
 * 更新卷信息
 */
export async function updateVolume(volumeNumber: number, projectId: string, data: UpdateVolumeRequest): Promise<VolumeOutline> {
  const response = await apiClient.put(`/volumes/${volumeNumber}`, {
    project_id: projectId,
    ...data,
  });
  return response.data;
}

/**
 * 设计卷高潮
 */
export async function designClimax(data: DesignClimaxRequest): Promise<{
  climax_description: string;
  climax_chapter: number;
  emotional_arc: EmotionArcPoint[];
  key_events: KeyEvent[];
}> {
  const response = await apiClient.post(`/volumes/${data.volume_number}/climax`, data);
  return response.data;
}

/**
 * 获取情绪曲线
 */
export async function getEmotionalArc(volumeNumber: number, projectId: string): Promise<{
  volume_number: number;
  emotional_arc: EmotionArcPoint[];
  peak_chapter: number;
  valley_chapter: number;
}> {
  const response = await apiClient.get(`/volumes/${volumeNumber}/emotional-arc`, {
    params: { project_id: projectId },
  });
  return response.data;
}

/**
 * 激活卷
 */
export async function activateVolume(volumeNumber: number, projectId: string): Promise<VolumeOutline> {
  const response = await apiClient.post(`/volumes/${volumeNumber}/activate`, {
    project_id: projectId,
  });
  return response.data;
}

/**
 * 完成卷
 */
export async function completeVolume(volumeNumber: number, projectId: string): Promise<VolumeOutline> {
  const response = await apiClient.post(`/volumes/${volumeNumber}/complete`, {
    project_id: projectId,
  });
  return response.data;
}

export default {
  getVolumes,
  createVolume,
  planVolume,
  getVolume,
  updateVolume,
  designClimax,
  getEmotionalArc,
  activateVolume,
  completeVolume,
};
