/**
 * 反派管理 API 客户端
 * GodView v9: 反派与冲突系统
 */

import { api as apiClient } from './client';

// ==================== 类型定义 ====================

export type VillainLevel = 'small' | 'medium' | 'major';
export type ConflictStatus = 'active' | 'escalated' | 'resolved';
export type ConflictType = 'main' | 'sub' | 'hidden';

export interface Villain {
  id: string;
  project_id: string;
  name: string;
  alias: string | null;
  level: VillainLevel;
  description: string;
  motivation: string;
  goals: string[];
  strengths: string[];
  weaknesses: string[];
  relationship_with_protagonist: string;
  first_appearance_chapter: number | null;
  defeat_chapter: number | null;
  defeat_method: string | null;
  status: 'active' | 'defeated' | 'escaped' | 'redeemed';
  subordinates: string[];
  resources: string[];
  created_at: string;
}

export interface Conflict {
  id: string;
  project_id: string;
  conflict_type: ConflictType;
  title: string;
  description: string;
  parties: string[];
  stakes: string;
  status: ConflictStatus;
  intensity: number;
  start_chapter: number | null;
  resolution_chapter: number | null;
  resolution_method: string | null;
  escalation_history: ConflictEscalation[];
  created_at: string;
}

export interface ConflictEscalation {
  chapter: number;
  from_intensity: number;
  to_intensity: number;
  reason: string;
}

export interface VillainDesignRequest {
  project_id: string;
  level: VillainLevel;
  name?: string;
  genre?: string;
  protagonist_traits?: string[];
}

export interface CreateVillainRequest {
  project_id: string;
  name: string;
  level: VillainLevel;
  description: string;
  motivation: string;
  goals?: string[];
  strengths?: string[];
  weaknesses?: string[];
}

export interface CreateConflictRequest {
  project_id: string;
  conflict_type: ConflictType;
  title: string;
  description: string;
  parties: string[];
  stakes: string;
  start_chapter?: number;
}

// ==================== API 函数 ====================

/**
 * 获取反派列表
 */
export async function getVillains(projectId: string, level?: VillainLevel): Promise<Villain[]> {
  const params = new URLSearchParams({ project_id: projectId });
  if (level) params.append('level', level);
  const response = await apiClient.get(`/villains?${params.toString()}`);
  return response.data;
}

/**
 * AI 设计反派
 */
export async function designVillain(data: VillainDesignRequest): Promise<Villain> {
  const response = await apiClient.post('/villains/design', data);
  return response.data;
}

/**
 * 创建反派
 */
export async function createVillain(data: CreateVillainRequest): Promise<Villain> {
  const response = await apiClient.post('/villains', data);
  return response.data;
}

/**
 * 获取反派详情
 */
export async function getVillain(villainId: string): Promise<Villain> {
  const response = await apiClient.get(`/villains/${villainId}`);
  return response.data;
}

/**
 * 更新反派
 */
export async function updateVillain(villainId: string, data: Partial<CreateVillainRequest>): Promise<Villain> {
  const response = await apiClient.put(`/villains/${villainId}`, data);
  return response.data;
}

/**
 * 标记反派被击败
 */
export async function defeatVillain(villainId: string, chapterNumber: number, method: string): Promise<Villain> {
  const response = await apiClient.post(`/villains/${villainId}/defeat`, {
    chapter: chapterNumber,
    method,
  });
  return response.data;
}

/**
 * 获取冲突线列表
 */
export async function getConflicts(projectId: string, status?: ConflictStatus): Promise<Conflict[]> {
  const params = new URLSearchParams({ project_id: projectId });
  if (status) params.append('status', status);
  const response = await apiClient.get(`/villains/conflicts?${params.toString()}`);
  return response.data;
}

/**
 * 创建冲突线
 */
export async function createConflict(data: CreateConflictRequest): Promise<Conflict> {
  const response = await apiClient.post('/villains/conflicts', data);
  return response.data;
}

/**
 * 获取冲突线详情
 */
export async function getConflict(conflictId: string): Promise<Conflict> {
  const response = await apiClient.get(`/villains/conflicts/${conflictId}`);
  return response.data;
}

/**
 * 升级冲突
 */
export async function escalateConflict(conflictId: string, chapter: number, reason: string): Promise<Conflict> {
  const response = await apiClient.post(`/villains/conflicts/${conflictId}/escalate`, {
    chapter,
    reason,
  });
  return response.data;
}

/**
 * 解决冲突
 */
export async function resolveConflict(conflictId: string, chapter: number, method: string): Promise<Conflict> {
  const response = await apiClient.post(`/villains/conflicts/${conflictId}/resolve`, {
    chapter,
    method,
  });
  return response.data;
}

/**
 * 冲突追踪分析
 */
export async function trackConflicts(projectId: string, chapter?: number): Promise<{
  active_conflicts: Conflict[];
  escalation_warnings: string[];
  resolution_suggestions: string[];
}> {
  const params = new URLSearchParams({ project_id: projectId });
  if (chapter) params.append('chapter', String(chapter));
  const response = await apiClient.post(`/villains/tracking?${params.toString()}`);
  return response.data;
}

export default {
  getVillains,
  designVillain,
  createVillain,
  getVillain,
  updateVillain,
  defeatVillain,
  getConflicts,
  createConflict,
  getConflict,
  escalateConflict,
  resolveConflict,
  trackConflicts,
};
