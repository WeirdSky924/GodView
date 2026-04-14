/**
 * 黄金三章检测组件
 * GodView v9: 质量检测系统
 */

import React, { useState, useCallback } from 'react';
import { checkGoldenThree, GoldenThreeCheckResult, CheckResult } from '../../api/quality';

interface GoldenThreeCheckerProps {
  projectId: string;
  onCheckComplete?: (result: GoldenThreeCheckResult) => void;
}

const GoldenThreeChecker: React.FC<GoldenThreeCheckerProps> = ({ projectId, onCheckComplete }) => {
  const [chapters, setChapters] = useState<number[]>([1, 2, 3]);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<GoldenThreeCheckResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  const handleCheck = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const checkResult = await checkGoldenThree({
        project_id: projectId,
        chapters,
      });
      setResult(checkResult);
      onCheckComplete?.(checkResult);
    } catch (err: any) {
      setError(err.message || '检测失败');
    } finally {
      setLoading(false);
    }
  }, [projectId, chapters, onCheckComplete]);

  const handleChapterChange = (index: number, value: string) => {
    const num = parseInt(value, 10);
    if (!isNaN(num) && num > 0) {
      const newChapters = [...chapters];
      newChapters[index] = num;
      setChapters(newChapters);
    }
  };

  const addChapter = () => {
    setChapters([...chapters, chapters[chapters.length - 1] + 1]);
  };

  const removeChapter = (index: number) => {
    if (chapters.length > 1) {
      setChapters(chapters.filter((_, i) => i !== index));
    }
  };

  const renderCheckResult = (title: string, check: CheckResult) => {
    const statusColor = check.passed ? 'text-green-500' : 'text-red-500';
    const bgColor = check.passed ? 'bg-green-50' : 'bg-red-50';
    const borderColor = check.passed ? 'border-green-200' : 'border-red-200';

    return (
      <div className={`p-4 rounded-lg border ${bgColor} ${borderColor}`}>
        <div className="flex items-center justify-between mb-2">
          <h4 className="font-medium text-gray-800">{title}</h4>
          <span className={`text-sm font-bold ${statusColor}`}>
            {check.passed ? '通过' : '未通过'} ({check.score}分)
          </span>
        </div>
        {check.details.length > 0 && (
          <ul className="text-sm text-gray-600 mb-2">
            {check.details.map((detail, i) => (
              <li key={i} className="flex items-start gap-2">
                <span className="text-green-500">✓</span>
                {detail}
              </li>
            ))}
          </ul>
        )}
        {check.issues.length > 0 && (
          <ul className="text-sm text-red-600">
            {check.issues.map((issue, i) => (
              <li key={i} className="flex items-start gap-2">
                <span>⚠</span>
                {issue}
              </li>
            ))}
          </ul>
        )}
      </div>
    );
  };

  const getScoreColor = (score: number) => {
    if (score >= 80) return 'text-green-500';
    if (score >= 60) return 'text-yellow-500';
    return 'text-red-500';
  };

  return (
    <div className="bg-white rounded-lg shadow-md p-6">
      <h3 className="text-lg font-bold text-gray-800 mb-4">黄金三章检测</h3>

      {/* 章节选择 */}
      <div className="mb-4">
        <label className="block text-sm font-medium text-gray-700 mb-2">
          检测章节
        </label>
        <div className="flex flex-wrap gap-2">
          {chapters.map((chapter, index) => (
            <div key={index} className="flex items-center gap-1">
              <input
                type="number"
                value={chapter}
                onChange={(e) => handleChapterChange(index, e.target.value)}
                className="w-16 px-2 py-1 border rounded text-center"
                min={1}
              />
              {chapters.length > 1 && (
                <button
                  onClick={() => removeChapter(index)}
                  className="text-red-500 hover:text-red-700"
                >
                  ×
                </button>
              )}
            </div>
          ))}
          <button
            onClick={addChapter}
            className="px-3 py-1 text-blue-500 border border-blue-300 rounded hover:bg-blue-50"
          >
            + 添加
          </button>
        </div>
      </div>

      {/* 检测按钮 */}
      <button
        onClick={handleCheck}
        disabled={loading}
        className={`w-full py-2 px-4 rounded font-medium ${
          loading
            ? 'bg-gray-300 text-gray-500 cursor-not-allowed'
            : 'bg-blue-500 text-white hover:bg-blue-600'
        }`}
      >
        {loading ? '检测中...' : '开始检测'}
      </button>

      {/* 错误提示 */}
      {error && (
        <div className="mt-4 p-3 bg-red-50 border border-red-200 rounded text-red-600">
          {error}
        </div>
      )}

      {/* 检测结果 */}
      {result && (
        <div className="mt-6">
          {/* 总分 */}
          <div className="text-center mb-6">
            <div className="text-sm text-gray-500 mb-1">综合评分</div>
            <div className={`text-4xl font-bold ${getScoreColor(result.total_score)}`}>
              {result.total_score}
              <span className="text-lg text-gray-400">/100</span>
            </div>
          </div>

          {/* 各项检测 */}
          <div className="space-y-4">
            {renderCheckResult('开头钩子检测', result.checks.hook_check)}
            {renderCheckResult('冲突设置检测', result.checks.conflict_check)}
            {renderCheckResult('主角塑造检测', result.checks.protagonist_check)}
          </div>

          {/* 章节分数 */}
          {Object.keys(result.chapter_scores).length > 0 && (
            <div className="mt-4 p-4 bg-gray-50 rounded-lg">
              <h4 className="font-medium text-gray-700 mb-2">各章得分</h4>
              <div className="flex gap-4">
                {Object.entries(result.chapter_scores).map(([chapter, score]) => (
                  <div key={chapter} className="text-center">
                    <div className="text-xs text-gray-500">第{chapter}章</div>
                    <div className={`font-bold ${getScoreColor(score)}`}>{score}</div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* 建议 */}
          {result.suggestions.length > 0 && (
            <div className="mt-4 p-4 bg-blue-50 border border-blue-200 rounded-lg">
              <h4 className="font-medium text-blue-800 mb-2">改进建议</h4>
              <ul className="text-sm text-blue-700 space-y-1">
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

export default GoldenThreeChecker;
