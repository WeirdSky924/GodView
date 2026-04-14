/**
 * 爽点分析组件
 * GodView v9: 质量检测系统
 */

import React, { useState, useCallback } from 'react';
import { analyzeSatisfaction, SatisfactionAnalysisResult, CoolPoint } from '../../api/quality';

interface SatisfactionAnalyzerProps {
  projectId: string;
  currentChapter?: number;
  onAnalyzeComplete?: (result: SatisfactionAnalysisResult) => void;
}

const SatisfactionAnalyzer: React.FC<SatisfactionAnalyzerProps> = ({
  projectId,
  currentChapter = 1,
  onAnalyzeComplete,
}) => {
  const [chapter, setChapter] = useState(currentChapter);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<SatisfactionAnalysisResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  const handleAnalyze = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const analysisResult = await analyzeSatisfaction({
        project_id: projectId,
        chapter_number: chapter,
      });
      setResult(analysisResult);
      onAnalyzeComplete?.(analysisResult);
    } catch (err: any) {
      setError(err.message || '分析失败');
    } finally {
      setLoading(false);
    }
  }, [projectId, chapter, onAnalyzeComplete]);

  const getCoolPointIcon = (type: string) => {
    const icons: Record<string, string> = {
      face_slap: '👋',
      counterattack: '⚔️',
      upgrade: '⬆️',
      treasure: '💎',
      revenge: '🔥',
      recognition: '👏',
      power_display: '💪',
      plot_twist: '🔄',
    };
    return icons[type] || '✨';
  };

  const getIntensityColor = (intensity: number) => {
    if (intensity >= 0.8) return 'bg-red-500';
    if (intensity >= 0.6) return 'bg-orange-500';
    if (intensity >= 0.4) return 'bg-yellow-500';
    return 'bg-green-500';
  };

  const getScoreColor = (score: number) => {
    if (score >= 80) return 'text-green-500';
    if (score >= 60) return 'text-yellow-500';
    return 'text-red-500';
  };

  const renderCoolPoint = (point: CoolPoint, index: number) => (
    <div key={index} className="p-3 bg-gray-50 rounded-lg border">
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-2">
          <span className="text-2xl">{getCoolPointIcon(point.type)}</span>
          <span className="font-medium text-gray-800">{point.description}</span>
        </div>
        <span className="text-sm text-gray-500">{point.type}</span>
      </div>
      <div className="flex items-center gap-2">
        <span className="text-xs text-gray-500">强度:</span>
        <div className="flex-1 h-2 bg-gray-200 rounded-full overflow-hidden">
          <div
            className={`h-full ${getIntensityColor(point.intensity)}`}
            style={{ width: `${point.intensity * 100}%` }}
          />
        </div>
        <span className="text-xs font-medium text-gray-600">
          {Math.round(point.intensity * 100)}%
        </span>
      </div>
      <div className="text-xs text-gray-400 mt-1">位置: {point.position}</div>
    </div>
  );

  return (
    <div className="bg-white rounded-lg shadow-md p-6">
      <h3 className="text-lg font-bold text-gray-800 mb-4">爽点分析</h3>

      {/* 章节选择 */}
      <div className="mb-4">
        <label className="block text-sm font-medium text-gray-700 mb-2">
          分析章节
        </label>
        <input
          type="number"
          value={chapter}
          onChange={(e) => setChapter(parseInt(e.target.value, 10) || 1)}
          className="w-24 px-3 py-2 border rounded"
          min={1}
        />
      </div>

      {/* 分析按钮 */}
      <button
        onClick={handleAnalyze}
        disabled={loading}
        className={`w-full py-2 px-4 rounded font-medium ${
          loading
            ? 'bg-gray-300 text-gray-500 cursor-not-allowed'
            : 'bg-purple-500 text-white hover:bg-purple-600'
        }`}
      >
        {loading ? '分析中...' : '开始分析'}
      </button>

      {/* 错误提示 */}
      {error && (
        <div className="mt-4 p-3 bg-red-50 border border-red-200 rounded text-red-600">
          {error}
        </div>
      )}

      {/* 分析结果 */}
      {result && (
        <div className="mt-6">
          {/* 爽点评分 */}
          <div className="text-center mb-6">
            <div className="text-sm text-gray-500 mb-1">爽点满意度</div>
            <div className={`text-4xl font-bold ${getScoreColor(result.satisfaction_score)}`}>
              {result.satisfaction_score}
              <span className="text-lg text-gray-400">/100</span>
            </div>
          </div>

          {/* 爽点列表 */}
          {result.cool_points.length > 0 && (
            <div className="mb-6">
              <h4 className="font-medium text-gray-700 mb-3">
                检测到的爽点 ({result.cool_points.length})
              </h4>
              <div className="space-y-3">
                {result.cool_points.map(renderCoolPoint)}
              </div>
            </div>
          )}

          {/* 铺垫-爆发结构 */}
          {result.铺垫_burst_structure && result.铺垫_burst_structure.length > 0 && (
            <div className="mb-6">
              <h4 className="font-medium text-gray-700 mb-3">铺垫-爆发结构</h4>
              <div className="space-y-3">
                {result.铺垫_burst_structure.map((structure, i) => (
                  <div key={i} className="p-3 bg-gradient-to-r from-blue-50 to-purple-50 rounded-lg border">
                    <div className="flex items-center gap-2 mb-2">
                      <div className="flex-1">
                        <div className="text-xs text-gray-500">铺垫</div>
                        <div className="text-sm text-gray-700">{structure.setup}</div>
                      </div>
                      <div className="text-2xl">→</div>
                      <div className="flex-1">
                        <div className="text-xs text-gray-500">爆发</div>
                        <div className="text-sm text-gray-700">{structure.burst}</div>
                      </div>
                    </div>
                    <div className="flex items-center gap-2">
                      <span className="text-xs text-gray-500">满足感:</span>
                      <div className="flex-1 h-2 bg-gray-200 rounded-full overflow-hidden">
                        <div
                          className="h-full bg-gradient-to-r from-blue-500 to-purple-500"
                          style={{ width: `${structure.satisfaction_level * 100}%` }}
                        />
                      </div>
                      <span className="text-xs font-medium">
                        {Math.round(structure.satisfaction_level * 100)}%
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* 建议 */}
          {result.suggestions.length > 0 && (
            <div className="p-4 bg-purple-50 border border-purple-200 rounded-lg">
              <h4 className="font-medium text-purple-800 mb-2">优化建议</h4>
              <ul className="text-sm text-purple-700 space-y-1">
                {result.suggestions.map((suggestion, i) => (
                  <li key={i}>• {suggestion}</li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}
    </div>
  );
};

export default SatisfactionAnalyzer;
