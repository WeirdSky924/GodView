/**
 * 质量检测 API 客户端
 * GodView v9: 小说质量优化系统
 */

import { api as apiClient } from './client';

// ==================== 类型定义 ====================

export interface GoldenThreeCheckRequest {
  project_id: string;
  chapters: number[];
}

export interface GoldenThreeCheckResult {
  project_id: string;
  total_score: number;
  chapter_scores: Record<number, number>;
  checks: {
    hook_check: CheckResult;
    conflict_check: CheckResult;
    protagonist_check: CheckResult;
  };
  suggestions: string[];
}

export interface CheckResult {
  passed: boolean;
  score: number;
  details: string[];
  issues: string[];
}

export interface SatisfactionAnalysisRequest {
  project_id: string;
  chapter_number: number;
  content?: string;
}

export interface SatisfactionAnalysisResult {
  project_id: string;
  chapter_number: number;
  satisfaction_score: number;
  cool_points: CoolPoint[];
 铺垫_burst_structure: PibuBurstStructure[];
  suggestions: string[];
}

export interface CoolPoint {
  type: string;
  description: string;
  intensity: number;
  position: string;
}

export interface PibuBurstStructure {
  setup: string;
  burst: string;
  satisfaction_level: number;
}

export interface OpeningDesignRequest {
  project_id: string;
  genre?: string;
  protagonist_type?: string;
  golden_finger_type?: string;
}

export interface OpeningDesignResult {
  project_id: string;
  golden_finger: GoldenFingerDesign;
  opening_conflict: OpeningConflict;
  goals: GoalSetting[];
  attraction_points: string[];
  suggestions: string[];
}

export interface GoldenFingerDesign {
  type: string;
  name: string;
  description: string;
  rules: string[];
  limitations: string[];
}

export interface OpeningConflict {
  type: string;
  description: string;
  stakes: string;
  resolution_hint: string;
}

export interface GoalSetting {
  type: 'short' | 'medium' | 'long';
  description: string;
  target_chapter: number;
}

export interface GenreTemplate {
  genre_type: string;
  name: string;
  description: string;
}

export interface GenreTemplateDetail extends GenreTemplate {
  core_elements: string[];
  power_system: Record<string, any>;
  world_structure: Record<string, any>;
  plot_patterns: Record<string, any>[];
  conflict_types: Record<string, any>[];
  climax_patterns: Record<string, any>[];
  protagonist_types: Record<string, any>[];
  villain_types: Record<string, any>[];
  relationship_patterns: Record<string, any>[];
  writing_guidelines: string[];
  taboo_list: string[];
  recommended_words: string[];
  commercial_tips: string[];
}

// ==================== API 函数 ====================

/**
 * 黄金三章检测
 */
export async function checkGoldenThree(data: GoldenThreeCheckRequest): Promise<GoldenThreeCheckResult> {
  const response = await apiClient.post('/quality/golden-three', data);
  return response.data;
}

/**
 * 爽点分析
 */
export async function analyzeSatisfaction(data: SatisfactionAnalysisRequest): Promise<SatisfactionAnalysisResult> {
  const response = await apiClient.post('/quality/satisfaction', data);
  return response.data;
}

/**
 * 开局设计
 */
export async function designOpening(data: OpeningDesignRequest): Promise<OpeningDesignResult> {
  const response = await apiClient.post('/quality/opening-design', data);
  return response.data;
}

/**
 * 金手指建议
 */
export async function suggestGoldenFinger(projectId: string, genre?: string): Promise<GoldenFingerDesign[]> {
  const params = new URLSearchParams({ project_id: projectId });
  if (genre) params.append('genre', genre);
  const response = await apiClient.post(`/quality/golden-finger-suggest?${params.toString()}`);
  return response.data.suggestions;
}

/**
 * 获取可用 Skills
 */
export async function getAvailableSkills(): Promise<string[]> {
  const response = await apiClient.get('/quality/skills');
  return response.data.skills;
}

/**
 * 设定一致性检测
 */
export async function checkConsistency(projectId: string): Promise<any> {
  const response = await apiClient.post('/quality/consistency', { project_id: projectId });
  return response.data;
}

/**
 * 剧情漏洞检测
 */
export async function detectPlotHoles(projectId: string, chapterNumber?: number): Promise<any> {
  const data: any = { project_id: projectId };
  if (chapterNumber) data.chapter_number = chapterNumber;
  const response = await apiClient.post('/quality/plot-hole', data);
  return response.data;
}

/**
 * 对话风格检查
 */
export async function checkDialogueStyle(projectId: string, chapterNumber: number): Promise<any> {
  const response = await apiClient.post('/quality/dialogue-style', {
    project_id: projectId,
    chapter_number: chapterNumber,
  });
  return response.data;
}

/**
 * 节奏分析
 */
export async function analyzePacing(projectId: string, startChapter: number, endChapter: number): Promise<any> {
  const response = await apiClient.post('/quality/pacing', {
    project_id: projectId,
    start_chapter: startChapter,
    end_chapter: endChapter,
  });
  return response.data;
}

/**
 * 获取题材模板列表
 */
export async function getGenreTemplates(): Promise<GenreTemplate[]> {
  const response = await apiClient.get('/genre-templates');
  return response.data;
}

/**
 * 获取题材模板详情
 */
export async function getGenreTemplate(genreType: string): Promise<GenreTemplateDetail> {
  const response = await apiClient.get(`/genre-templates/${genreType}`);
  return response.data;
}

export default {
  checkGoldenThree,
  analyzeSatisfaction,
  designOpening,
  suggestGoldenFinger,
  getAvailableSkills,
  checkConsistency,
  detectPlotHoles,
  checkDialogueStyle,
  analyzePacing,
  getGenreTemplates,
  getGenreTemplate,
};
