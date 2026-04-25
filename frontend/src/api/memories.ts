/**
 * 记忆系统 API 客户端
 * GodView v9: 长篇记忆架构
 */

import { api as apiClient } from './client';

function unwrap<T>(response: T | { data: T }): T {
  if (response && typeof response === 'object' && 'data' in response) {
    return (response as { data: T }).data;
  }
  return response as T;
}

function unwrapListResponse<T>(response: T[] | { data: T[] } | { memories: T[] } | { data: { memories: T[] } }): T[] {
  const unwrapped = unwrap(response as T[] | { memories: T[] } | { data: T[] } | { data: { memories: T[] } });
  if (Array.isArray(unwrapped)) return unwrapped;
  if (unwrapped && typeof unwrapped === 'object' && 'memories' in unwrapped) {
    return (unwrapped as { memories: T[] }).memories;
  }
  return [];
}

// ==================== 类型定义 ====================

export type MemoryType = 'short_term' | 'medium_term' | 'long_term';
export type MemoryCategory = 'character' | 'event' | 'setting' | 'relationship' | 'foreshadowing' | 'conflict';

export interface MemoryEntry {
  id: string;
  project_id: string;
  memory_type: MemoryType;
  category: MemoryCategory;
  title: string;
  content: string;
  chapter_reference: number | null;
  character_ids: string[];
  importance: number;
  tags: string[];
  embedding: number[] | null;
  created_at: string;
  expires_at: string | null;
}

export interface MemorySnapshot {
  id: string;
  project_id: string;
  chapter_number: number;
  character_states: Record<string, CharacterMemoryState>;
  key_events: KeyEvent[];
  active_foreshadowings: string[];
  world_state: Record<string, any>;
  created_at: string;
}

export interface CharacterMemoryState {
  character_id: string;
  character_name: string;
  current_location: string | null;
  emotional_state: string | null;
  knowledge_gained: string[];
  relationships_changed: string[];
  goals_updated: string[];
}

export interface KeyEvent {
  chapter: number;
  event: string;
  impact: string;
}

export interface Foreshadowing {
  id: string;
  project_id: string;
  title: string;
  description: string;
  planted_chapter: number;
  planned_reveal_chapter: number | null;
  actual_reveal_chapter: number | null;
  status: 'planted' | 'revealed' | 'abandoned';
  importance: number;
  notes: string;
}

export interface CreateMemoryRequest {
  project_id: string;
  memory_type: MemoryType;
  category: MemoryCategory;
  title: string;
  content: string;
  chapter_reference?: number;
  character_ids?: string[];
  importance?: number;
  tags?: string[];
}

export interface SearchMemoryRequest {
  project_id: string;
  query: string;
  memory_types?: MemoryType[];
  categories?: MemoryCategory[];
  character_ids?: string[];
  chapter_range?: [number, number];
  limit?: number;
}

export interface SearchMemoryResult {
  results: MemoryEntry[];
  total: number;
  query: string;
}

// ==================== API 函数 ====================

/**
 * 获取记忆列表
 */
export async function getMemories(projectId: string, params?: {
  memory_type?: MemoryType;
  category?: MemoryCategory;
  chapter?: number;
  limit?: number;
  offset?: number;
}): Promise<MemoryEntry[]> {
  const searchParams = new URLSearchParams({ project_id: projectId });
  if (params) {
    Object.entries(params).forEach(([key, value]) => {
      if (value !== undefined) searchParams.append(key, String(value));
    });
  }
  const response = await apiClient.get<MemoryEntry[] | { data: MemoryEntry[] } | { memories: MemoryEntry[] } | { data: { memories: MemoryEntry[] } }>(`/memories?${searchParams.toString()}`);
  return unwrapListResponse(response);
}

/**
 * 创建记忆
 */
export async function createMemory(data: CreateMemoryRequest): Promise<MemoryEntry> {
  const response = await apiClient.post<MemoryEntry | { data: MemoryEntry }>('/memories', data);
  return unwrap(response);
}

/**
 * 获取记忆详情
 */
export async function getMemory(memoryId: string): Promise<MemoryEntry> {
  const response = await apiClient.get<MemoryEntry | { data: MemoryEntry }>(`/memories/${memoryId}`);
  return unwrap(response);
}

/**
 * 更新记忆
 */
export async function updateMemory(memoryId: string, data: Partial<CreateMemoryRequest>): Promise<MemoryEntry> {
  const response = await apiClient.put<MemoryEntry | { data: MemoryEntry }>(`/memories/${memoryId}`, data);
  return unwrap(response);
}

/**
 * 删除记忆
 */
export async function deleteMemory(memoryId: string): Promise<void> {
  await apiClient.delete(`/memories/${memoryId}`);
}

/**
 * 搜索记忆
 */
export async function searchMemories(data: SearchMemoryRequest): Promise<SearchMemoryResult> {
  const response = await apiClient.post<SearchMemoryResult | { data: SearchMemoryResult } | { results: Array<{ memory: MemoryEntry; relevance_score?: number }>; total: number }>('/memories/search', data);
  const result = unwrap(response);
  const typedResult = result as SearchMemoryResult | { results: Array<MemoryEntry | { memory: MemoryEntry }>; total: number; query?: string };
  return {
    ...typedResult,
    query: typedResult.query || data.query,
    results: typedResult.results.map((item: MemoryEntry | { memory: MemoryEntry }) => ('memory' in item ? item.memory : item)),
  };
}

/**
 * 获取记忆快照
 */
export async function getSnapshot(projectId: string, chapterNumber?: number): Promise<MemorySnapshot> {
  const params = new URLSearchParams({ project_id: projectId });
  if (chapterNumber) params.append('chapter', String(chapterNumber));
  const response = await apiClient.get<MemorySnapshot | { data: MemorySnapshot }>(`/memories/snapshot?${params.toString()}`);
  return unwrap(response);
}

/**
 * 构建记忆快照
 */
export async function buildSnapshot(projectId: string, chapterNumber: number): Promise<MemorySnapshot> {
  const response = await apiClient.post<MemorySnapshot | { data: MemorySnapshot }>('/memories/snapshot/build', {
    project_id: projectId,
    chapter_number: chapterNumber,
  });
  return unwrap(response);
}

/**
 * 获取角色记忆状态
 */
export async function getCharacterMemoryState(projectId: string, characterId: string): Promise<CharacterMemoryState> {
  const response = await apiClient.get<CharacterMemoryState | { data: CharacterMemoryState }>(`/memories/character/${characterId}`, {
    params: { project_id: projectId },
  });
  return unwrap(response);
}

/**
 * 获取待回收伏笔
 */
export async function getPendingForeshadowings(projectId: string): Promise<Foreshadowing[]> {
  const response = await apiClient.get<Foreshadowing[] | { data: Foreshadowing[] }>('/memories/foreshadowing', {
    params: { project_id: projectId },
  });
  return unwrap(response);
}

/**
 * 标记伏笔已揭示
 */
export async function revealForeshadowing(foreshadowingId: string, chapterNumber: number): Promise<Foreshadowing> {
  const response = await apiClient.post<Foreshadowing | { data: Foreshadowing }>(`/memories/foreshadowing/${foreshadowingId}/reveal`, {
    reveal_chapter: chapterNumber,
  });
  return unwrap(response);
}

export default {
  getMemories,
  createMemory,
  getMemory,
  updateMemory,
  deleteMemory,
  searchMemories,
  getSnapshot,
  buildSnapshot,
  getCharacterMemoryState,
  getPendingForeshadowings,
  revealForeshadowing,
};
