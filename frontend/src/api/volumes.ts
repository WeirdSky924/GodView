/**
 * 卷规划 API 客户端
 * GodView v9: 卷级规划系统
 */

import { api as apiClient } from './client';
import type { AssistantContextSummary } from './assistantContext';

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
  book_outline?: string;
  previous_volume_summary?: string;
  target_words?: number;
  assistant_session_id?: string;
  request_id?: string;
}

export interface DesignClimaxRequest {
  project_id: string;
  volume_number: number;
  volume_id?: string;
  climax_event?: string;
  emotional_peak?: string | number;
  key_characters?: string[];
  participating_characters?: string[];
  conflict_resolution?: string;
  assistant_session_id?: string;
  request_id?: string;
}

export interface VolumePlanResponse {
  success: boolean;
  volume_info: Record<string, any>;
  emotional_arc: Record<string, any>;
  climax_design: Record<string, any>;
  chapter_plan: Array<Record<string, any>>;
  transitions: Record<string, any>;
  word_distribution: Record<string, any>;
  assistant_session_id?: string | null;
  context_packet?: AssistantContextSummary | null;
}

export interface ClimaxDesignResponse {
  success: boolean;
  climax_chapter: number;
  climax_description: string;
  buildup_scenes: Array<Record<string, any>>;
  aftermath_scenes: Array<Record<string, any>>;
  assistant_session_id?: string | null;
  context_packet?: AssistantContextSummary | null;
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
export async function planVolume(data: PlanVolumeRequest): Promise<VolumePlanResponse> {
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
export async function designClimax(data: DesignClimaxRequest): Promise<ClimaxDesignResponse> {
  const response = await apiClient.post(`/volumes/${data.volume_number}/climax`, {
    ...data,
    volume_id: data.volume_id || `volume_${data.volume_number}`,
    climax_event: data.climax_event || data.conflict_resolution || '',
    participating_characters: data.participating_characters || data.key_characters || [],
  });
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
