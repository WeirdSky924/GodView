/**
 * 开局设计向导组件
 * GodView v9: 开局设计系统
 */

import React, { useState, useCallback } from 'react';
import { designOpening, suggestGoldenFinger, OpeningDesignResult, GoldenFingerDesign } from '../api/quality';

interface OpeningDesignerProps {
  projectId: string;
  onDesignComplete?: (result: OpeningDesignResult) => void;
}

const OpeningDesigner: React.FC<OpeningDesignerProps> = ({ projectId, onDesignComplete }) => {
  const [step, setStep] = useState(1);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // 设计参数
  const [genre, setGenre] = useState('');
  const [protagonistType, setProtagonistType] = useState('');
  const [goldenFingerType, setGoldenFingerType] = useState('');

  // 结果
  const [result, setResult] = useState<OpeningDesignResult | null>(null);
  const [goldenFingerSuggestions, setGoldenFingerSuggestions] = useState<GoldenFingerDesign[]>([]);

  const genreOptions = [
    { value: 'xuanhuan', label: '玄幻/仙侠' },
    { value: 'urban', label: '都市' },
    { value: 'history', label: '历史军事' },
    { value: 'scifi', label: '科幻' },
    { value: 'game', label: '游戏' },
  ];

  const protagonistTypes = [
    { value: 'reborn', label: '重生者' },
    { value: 'transmigrated', label: '穿越者' },
    { value: 'underdog', label: '废材逆袭' },
    { value: 'genius_fallen', label: '天才陨落' },
    { value: 'ordinary', label: '普通人' },
  ];

  const goldenFingerTypes = [
    { value: 'system', label: '系统金手指' },
    { value: 'space', label: '空间/随身空间' },
    { value: 'rebirth', label: '重生记忆' },
    { value: 'talent', label: '天赋能力' },
    { value: 'artifact', label: '神器/法宝' },
    { value: 'knowledge', label: '前世知识' },
  ];

  // 获取金手指建议
  const handleGetSuggestions = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const suggestions = await suggestGoldenFinger(projectId, genre);
      setGoldenFingerSuggestions(suggestions);
    } catch (err: any) {
      setError(err.message || '获取建议失败');
    } finally {
      setLoading(false);
    }
  }, [projectId, genre]);

  // 生成开局设计
  const handleDesign = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const designResult = await designOpening({
        project_id: projectId,
        genre,
        protagonist_type: protagonistType,
        golden_finger_type: goldenFingerType,
      });
      setResult(designResult);
      onDesignComplete?.(designResult);
      setStep(3);
    } catch (err: any) {
      setError(err.message || '设计失败');
    } finally {
      setLoading(false);
    }
  }, [projectId, genre, protagonistType, goldenFingerType, onDesignComplete]);

  const nextStep = () => {
    if (step === 1 && genre && protagonistType) {
      setStep(2);
    }
  };

  const prevStep = () => {
    if (step > 1) setStep(step - 1);
  };

  const renderStep1 = () => (
    <div className="space-y-6">
      <div>
        <label className="block text-sm font-medium text-gray-700 mb-2">
          选择题材
        </label>
        <div className="grid grid-cols-2 md:grid-cols-3 gap-2">
          {genreOptions.map((option) => (
            <button
              key={option.value}
              onClick={() => setGenre(option.value)}
              className={`p-3 rounded-lg border text-left transition ${
                genre === option.value
                  ? 'bg-blue-50 border-blue-500 text-blue-700'
                  : 'bg-white border-gray-200 hover:border-gray-300'
              }`}
            >
              {option.label}
            </button>
          ))}
        </div>
      </div>

      <div>
        <label className="block text-sm font-medium text-gray-700 mb-2">
          主角类型
        </label>
        <div className="grid grid-cols-2 gap-2">
          {protagonistTypes.map((option) => (
            <button
              key={option.value}
              onClick={() => setProtagonistType(option.value)}
              className={`p-3 rounded-lg border text-left transition ${
                protagonistType === option.value
                  ? 'bg-green-50 border-green-500 text-green-700'
                  : 'bg-white border-gray-200 hover:border-gray-300'
              }`}
            >
              {option.label}
            </button>
          ))}
        </div>
      </div>

      <button
        onClick={nextStep}
        disabled={!genre || !protagonistType}
        className={`w-full py-3 rounded-lg font-medium ${
          genre && protagonistType
            ? 'bg-blue-500 text-white hover:bg-blue-600'
            : 'bg-gray-200 text-gray-400 cursor-not-allowed'
        }`}
      >
        下一步：设计金手指
      </button>
    </div>
  );

  const renderStep2 = () => (
    <div className="space-y-6">
      <div>
        <label className="block text-sm font-medium text-gray-700 mb-2">
          金手指类型
        </label>
        <div className="grid grid-cols-2 md:grid-cols-3 gap-2">
          {goldenFingerTypes.map((option) => (
            <button
              key={option.value}
              onClick={() => setGoldenFingerType(option.value)}
              className={`p-3 rounded-lg border text-left transition ${
                goldenFingerType === option.value
                  ? 'bg-purple-50 border-purple-500 text-purple-700'
                  : 'bg-white border-gray-200 hover:border-gray-300'
              }`}
            >
              {option.label}
            </button>
          ))}
        </div>
      </div>

      {/* 获取建议按钮 */}
      <button
        onClick={handleGetSuggestions}
        disabled={loading}
        className="w-full py-2 border border-blue-300 text-blue-600 rounded-lg hover:bg-blue-50"
      >
        {loading ? '获取中...' : '获取金手指建议'}
      </button>

      {/* 建议列表 */}
      {goldenFingerSuggestions.length > 0 && (
        <div className="space-y-2">
          <h4 className="font-medium text-gray-700">建议的金手指</h4>
          {goldenFingerSuggestions.map((gf, i) => (
            <div
              key={i}
              className="p-3 bg-purple-50 border border-purple-200 rounded-lg cursor-pointer hover:bg-purple-100"
              onClick={() => setGoldenFingerType(gf.type)}
            >
              <div className="font-medium text-purple-800">{gf.name}</div>
              <div className="text-sm text-purple-600">{gf.description}</div>
            </div>
          ))}
        </div>
      )}

      <div className="flex gap-2">
        <button
          onClick={prevStep}
          className="flex-1 py-3 border border-gray-300 text-gray-600 rounded-lg hover:bg-gray-50"
        >
          上一步
        </button>
        <button
          onClick={handleDesign}
          disabled={loading || !goldenFingerType}
          className={`flex-1 py-3 rounded-lg font-medium ${
            goldenFingerType && !loading
              ? 'bg-purple-500 text-white hover:bg-purple-600'
              : 'bg-gray-200 text-gray-400 cursor-not-allowed'
          }`}
        >
          {loading ? '生成中...' : '生成开局设计'}
        </button>
      </div>
    </div>
  );

  const renderStep3 = () => (
    <div className="space-y-6">
      {result && (
        <>
          {/* 金手指设计 */}
          <div className="p-4 bg-purple-50 border border-purple-200 rounded-lg">
            <h4 className="font-medium text-purple-800 mb-2">金手指设计</h4>
            <div className="font-bold text-lg text-purple-900">{result.golden_finger.name}</div>
            <p className="text-sm text-purple-700 mt-1">{result.golden_finger.description}</p>
            {result.golden_finger.rules.length > 0 && (
              <div className="mt-3">
                <div className="text-xs text-purple-600 font-medium">规则限制</div>
                <ul className="text-sm text-purple-700 mt-1">
                  {result.golden_finger.rules.map((rule, i) => (
                    <li key={i}>• {rule}</li>
                  ))}
                </ul>
              </div>
            )}
            {result.golden_finger.limitations.length > 0 && (
              <div className="mt-2">
                <div className="text-xs text-purple-600 font-medium">使用限制</div>
                <ul className="text-sm text-purple-700 mt-1">
                  {result.golden_finger.limitations.map((lim, i) => (
                    <li key={i}>• {lim}</li>
                  ))}
                </ul>
              </div>
            )}
          </div>

          {/* 开局冲突 */}
          <div className="p-4 bg-red-50 border border-red-200 rounded-lg">
            <h4 className="font-medium text-red-800 mb-2">开局冲突</h4>
            <div className="text-sm text-red-700">{result.opening_conflict.description}</div>
            <div className="mt-2 text-xs text-red-600">
              <div>类型: {result.opening_conflict.type}</div>
              <div>赌注: {result.opening_conflict.stakes}</div>
              <div>解决提示: {result.opening_conflict.resolution_hint}</div>
            </div>
          </div>

          {/* 目标设定 */}
          <div className="p-4 bg-green-50 border border-green-200 rounded-lg">
            <h4 className="font-medium text-green-800 mb-2">目标设定</h4>
            <div className="space-y-2">
              {result.goals.map((goal, i) => (
                <div key={i} className="flex items-center justify-between">
                  <div>
                    <span className="font-medium text-green-800">{goal.description}</span>
                    <span className="text-xs text-green-600 ml-2">
                      ({goal.type === 'short' ? '短期' : goal.type === 'medium' ? '中期' : '长期'})
                    </span>
                  </div>
                  <span className="text-xs text-green-500">约第{goal.target_chapter}章</span>
                </div>
              ))}
            </div>
          </div>

          {/* 吸引力要点 */}
          <div className="p-4 bg-blue-50 border border-blue-200 rounded-lg">
            <h4 className="font-medium text-blue-800 mb-2">主角吸引力设计</h4>
            <ul className="text-sm text-blue-700">
              {result.attraction_points.map((point, i) => (
                <li key={i}>• {point}</li>
              ))}
            </ul>
          </div>

          {/* 建议 */}
          {result.suggestions.length > 0 && (
            <div className="p-4 bg-gray-50 border border-gray-200 rounded-lg">
              <h4 className="font-medium text-gray-800 mb-2">写作建议</h4>
              <ul className="text-sm text-gray-600">
                {result.suggestions.map((s, i) => (
                  <li key={i}>• {s}</li>
                ))}
              </ul>
            </div>
          )}

          {/* 重新设计按钮 */}
          <button
            onClick={() => {
              setStep(1);
              setResult(null);
            }}
            className="w-full py-2 border border-gray-300 text-gray-600 rounded-lg hover:bg-gray-50"
          >
            重新设计
          </button>
        </>
      )}
    </div>
  );

  return (
    <div className="bg-white rounded-lg shadow-md p-6">
      <h3 className="text-lg font-bold text-gray-800 mb-4">开局设计向导</h3>

      {/* 步骤指示器 */}
      <div className="flex items-center justify-center mb-6">
        {[1, 2, 3].map((s) => (
          <React.Fragment key={s}>
            <div
              className={`w-8 h-8 rounded-full flex items-center justify-center font-medium ${
                s === step
                  ? 'bg-blue-500 text-white'
                  : s < step
                  ? 'bg-green-500 text-white'
                  : 'bg-gray-200 text-gray-500'
              }`}
            >
              {s < step ? '✓' : s}
            </div>
            {s < 3 && (
              <div
                className={`w-12 h-1 ${s < step ? 'bg-green-500' : 'bg-gray-200'}`}
              />
            )}
          </React.Fragment>
        ))}
      </div>

      {/* 错误提示 */}
      {error && (
        <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded text-red-600">
          {error}
        </div>
      )}

      {/* 步骤内容 */}
      {loading ? (
        <div className="text-center py-8 text-gray-400">生成中...</div>
      ) : (
        <>
          {step === 1 && renderStep1()}
          {step === 2 && renderStep2()}
          {step === 3 && renderStep3()}
        </>
      )}
    </div>
  );
};

export default OpeningDesigner;
