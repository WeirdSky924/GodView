/**
 * 反派管理面板组件
 * GodView v9: 反派与冲突系统
 */

import React, { useState, useCallback, useEffect } from 'react';
import {
  getVillains,
  designVillain,
  createVillain,
  defeatVillain,
  getConflicts,
  createConflict,
  escalateConflict,
  resolveConflict,
  trackConflicts,
  Villain,
  Conflict,
  VillainLevel,
  ConflictType,
} from '../api/villains';

interface VillainManagerProps {
  projectId: string;
}

const VillainManager: React.FC<VillainManagerProps> = ({ projectId }) => {
  const [activeTab, setActiveTab] = useState<'villains' | 'conflicts'>('villains');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // 反派
  const [villains, setVillains] = useState<Villain[]>([]);
  const [selectedVillain, setSelectedVillain] = useState<Villain | null>(null);
  const [showDesignModal, setShowDesignModal] = useState(false);
  const [designLevel, setDesignLevel] = useState<VillainLevel>('medium');
  const [designName, setDesignName] = useState('');

  // 冲突
  const [conflicts, setConflicts] = useState<Conflict[]>([]);
  const [selectedConflict, setSelectedConflict] = useState<Conflict | null>(null);
  const [trackingResult, setTrackingResult] = useState<any>(null);

  // 加载反派列表
  const loadVillains = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await getVillains(projectId);
      setVillains(data);
    } catch (err: any) {
      setError(err.message || '加载失败');
    } finally {
      setLoading(false);
    }
  }, [projectId]);

  // 加载冲突列表
  const loadConflicts = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await getConflicts(projectId);
      setConflicts(data);
    } catch (err: any) {
      setError(err.message || '加载失败');
    } finally {
      setLoading(false);
    }
  }, [projectId]);

  // 追踪冲突
  const handleTrackConflicts = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const result = await trackConflicts(projectId);
      setTrackingResult(result);
    } catch (err: any) {
      setError(err.message || '追踪失败');
    } finally {
      setLoading(false);
    }
  }, [projectId]);

  // AI 设计反派
  const handleDesignVillain = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const newVillain = await designVillain({
        project_id: projectId,
        level: designLevel,
        name: designName || undefined,
      });
      setVillains([...villains, newVillain]);
      setShowDesignModal(false);
      setDesignName('');
    } catch (err: any) {
      setError(err.message || '设计失败');
    } finally {
      setLoading(false);
    }
  }, [projectId, designLevel, designName, villains]);

  // 标记反派被击败
  const handleDefeatVillain = useCallback(async (villainId: string, chapter: number, method: string) => {
    setLoading(true);
    try {
      const updated = await defeatVillain(villainId, chapter, method);
      setVillains(villains.map(v => v.id === villainId ? updated : v));
      setSelectedVillain(null);
    } catch (err: any) {
      setError(err.message || '操作失败');
    } finally {
      setLoading(false);
    }
  }, [villains]);

  // 升级冲突
  const handleEscalateConflict = useCallback(async (conflictId: string, chapter: number, reason: string) => {
    setLoading(true);
    try {
      const updated = await escalateConflict(conflictId, chapter, reason);
      setConflicts(conflicts.map(c => c.id === conflictId ? updated : c));
    } catch (err: any) {
      setError(err.message || '操作失败');
    } finally {
      setLoading(false);
    }
  }, [conflicts]);

  // 解决冲突
  const handleResolveConflict = useCallback(async (conflictId: string, chapter: number, method: string) => {
    setLoading(true);
    try {
      const updated = await resolveConflict(conflictId, chapter, method);
      setConflicts(conflicts.map(c => c.id === conflictId ? updated : c));
      setSelectedConflict(null);
    } catch (err: any) {
      setError(err.message || '操作失败');
    } finally {
      setLoading(false);
    }
  }, [conflicts]);

  // 初始化加载
  useEffect(() => {
    if (activeTab === 'villains') loadVillains();
    else loadConflicts();
  }, [activeTab, loadVillains, loadConflicts]);

  const getLevelColor = (level: VillainLevel) => {
    const colors: Record<VillainLevel, string> = {
      small: 'bg-gray-100 text-gray-800',
      medium: 'bg-yellow-100 text-yellow-800',
      major: 'bg-red-100 text-red-800',
    };
    return colors[level];
  };

  const getLevelLabel = (level: VillainLevel) => {
    const labels: Record<VillainLevel, string> = {
      small: '小BOSS',
      medium: '中BOSS',
      major: '大BOSS',
    };
    return labels[level];
  };

  const getStatusColor = (status: string) => {
    const colors: Record<string, string> = {
      active: 'bg-green-100 text-green-800',
      defeated: 'bg-gray-100 text-gray-800',
      escaped: 'bg-orange-100 text-orange-800',
      redeemed: 'bg-blue-100 text-blue-800',
    };
    return colors[status] || 'bg-gray-100';
  };

  const getConflictTypeLabel = (type: ConflictType) => {
    const labels: Record<ConflictType, string> = {
      main: '主线',
      sub: '支线',
      hidden: '暗线',
    };
    return labels[type];
  };

  const renderVillainList = () => (
    <div>
      {/* 顶部操作 */}
      <div className="flex justify-between items-center mb-4">
        <div className="flex gap-2">
          <select className="px-3 py-2 border rounded">
            <option value="">全部层级</option>
            <option value="small">小BOSS</option>
            <option value="medium">中BOSS</option>
            <option value="major">大BOSS</option>
          </select>
        </div>
        <button
          onClick={() => setShowDesignModal(true)}
          className="px-4 py-2 bg-red-500 text-white rounded hover:bg-red-600"
        >
          + 设计反派
        </button>
      </div>

      {/* 反派列表 */}
      <div className="grid gap-3">
        {villains.map((villain) => (
          <div
            key={villain.id}
            className="p-4 bg-gray-50 rounded-lg border hover:shadow cursor-pointer"
            onClick={() => setSelectedVillain(villain)}
          >
            <div className="flex items-start justify-between mb-2">
              <div>
                <span className="font-bold text-gray-800">{villain.name}</span>
                {villain.alias && (
                  <span className="text-sm text-gray-500 ml-2">({villain.alias})</span>
                )}
              </div>
              <div className="flex gap-1">
                <span className={`text-xs px-2 py-1 rounded ${getLevelColor(villain.level)}`}>
                  {getLevelLabel(villain.level)}
                </span>
                <span className={`text-xs px-2 py-1 rounded ${getStatusColor(villain.status)}`}>
                  {villain.status === 'active' ? '活跃' : villain.status}
                </span>
              </div>
            </div>
            <p className="text-sm text-gray-600 line-clamp-2">{villain.description}</p>
            <div className="mt-2 text-xs text-gray-400">
              动机: {villain.motivation}
            </div>
          </div>
        ))}
        {villains.length === 0 && !loading && (
          <div className="text-center text-gray-400 py-8">暂无反派数据</div>
        )}
      </div>

      {/* 反派详情弹窗 */}
      {selectedVillain && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg p-6 max-w-lg w-full mx-4 max-h-[80vh] overflow-y-auto">
            <h3 className="text-lg font-bold mb-4">{selectedVillain.name}</h3>
            <div className="space-y-3 text-sm">
              <p><span className="text-gray-500">描述:</span> {selectedVillain.description}</p>
              <p><span className="text-gray-500">动机:</span> {selectedVillain.motivation}</p>
              {selectedVillain.goals.length > 0 && (
                <div>
                  <span className="text-gray-500">目标:</span>
                  <ul className="list-disc ml-5">
                    {selectedVillain.goals.map((g, i) => <li key={i}>{g}</li>)}
                  </ul>
                </div>
              )}
              {selectedVillain.strengths.length > 0 && (
                <div>
                  <span className="text-gray-500">优势:</span>
                  <ul className="list-disc ml-5">
                    {selectedVillain.strengths.map((s, i) => <li key={i}>{s}</li>)}
                  </ul>
                </div>
              )}
              {selectedVillain.weaknesses.length > 0 && (
                <div>
                  <span className="text-gray-500">弱点:</span>
                  <ul className="list-disc ml-5">
                    {selectedVillain.weaknesses.map((w, i) => <li key={i}>{w}</li>)}
                  </ul>
                </div>
              )}
            </div>
            <div className="flex gap-2 mt-4">
              {selectedVillain.status === 'active' && (
                <button
                  onClick={() => {
                    const chapter = prompt('击败章节号:');
                    const method = prompt('击败方式:');
                    if (chapter && method) {
                      handleDefeatVillain(selectedVillain.id, parseInt(chapter), method);
                    }
                  }}
                  className="px-4 py-2 bg-gray-500 text-white rounded"
                >
                  标记击败
                </button>
              )}
              <button
                onClick={() => setSelectedVillain(null)}
                className="px-4 py-2 border rounded"
              >
                关闭
              </button>
            </div>
          </div>
        </div>
      )}

      {/* 设计反派弹窗 */}
      {showDesignModal && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg p-6 max-w-md w-full mx-4">
            <h3 className="text-lg font-bold mb-4">AI 设计反派</h3>
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium mb-1">反派名称 (可选)</label>
                <input
                  type="text"
                  value={designName}
                  onChange={(e) => setDesignName(e.target.value)}
                  className="w-full px-3 py-2 border rounded"
                  placeholder="留空则AI生成"
                />
              </div>
              <div>
                <label className="block text-sm font-medium mb-1">反派层级</label>
                <select
                  value={designLevel}
                  onChange={(e) => setDesignLevel(e.target.value as VillainLevel)}
                  className="w-full px-3 py-2 border rounded"
                >
                  <option value="small">小BOSS</option>
                  <option value="medium">中BOSS</option>
                  <option value="major">大BOSS</option>
                </select>
              </div>
            </div>
            <div className="flex gap-2 mt-4">
              <button
                onClick={handleDesignVillain}
                disabled={loading}
                className="flex-1 py-2 bg-red-500 text-white rounded"
              >
                {loading ? '生成中...' : '生成反派'}
              </button>
              <button
                onClick={() => setShowDesignModal(false)}
                className="px-4 py-2 border rounded"
              >
                取消
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );

  const renderConflictList = () => (
    <div>
      {/* 顶部操作 */}
      <div className="flex justify-between items-center mb-4">
        <button
          onClick={handleTrackConflicts}
          className="px-4 py-2 border border-orange-300 text-orange-600 rounded hover:bg-orange-50"
        >
          冲突追踪分析
        </button>
      </div>

      {/* 追踪结果 */}
      {trackingResult && (
        <div className="mb-4 p-3 bg-orange-50 border border-orange-200 rounded-lg">
          <h4 className="font-medium text-orange-800 mb-2">冲突追踪结果</h4>
          {trackingResult.escalation_warnings.length > 0 && (
            <div className="text-sm text-orange-700 mb-2">
              <span className="font-medium">警告:</span>
              <ul className="list-disc ml-5">
                {trackingResult.escalation_warnings.map((w: string, i: number) => (
                  <li key={i}>{w}</li>
                ))}
              </ul>
            </div>
          )}
          {trackingResult.resolution_suggestions.length > 0 && (
            <div className="text-sm text-orange-600">
              <span className="font-medium">建议:</span>
              <ul className="list-disc ml-5">
                {trackingResult.resolution_suggestions.map((s: string, i: number) => (
                  <li key={i}>{s}</li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}

      {/* 冲突列表 */}
      <div className="grid gap-3">
        {conflicts.map((conflict) => (
          <div
            key={conflict.id}
            className="p-4 bg-gray-50 rounded-lg border hover:shadow cursor-pointer"
            onClick={() => setSelectedConflict(conflict)}
          >
            <div className="flex items-start justify-between mb-2">
              <span className="font-bold text-gray-800">{conflict.title}</span>
              <div className="flex gap-1">
                <span className="text-xs px-2 py-1 rounded bg-blue-100 text-blue-800">
                  {getConflictTypeLabel(conflict.conflict_type)}
                </span>
                <span className="text-xs px-2 py-1 rounded bg-green-100 text-green-800">
                  强度: {conflict.intensity}
                </span>
              </div>
            </div>
            <p className="text-sm text-gray-600">{conflict.description}</p>
            <div className="mt-2 text-xs text-gray-400">
              赌注: {conflict.stakes}
            </div>
          </div>
        ))}
        {conflicts.length === 0 && !loading && (
          <div className="text-center text-gray-400 py-8">暂无冲突数据</div>
        )}
      </div>

      {/* 冲突详情弹窗 */}
      {selectedConflict && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg p-6 max-w-lg w-full mx-4 max-h-[80vh] overflow-y-auto">
            <h3 className="text-lg font-bold mb-4">{selectedConflict.title}</h3>
            <div className="space-y-3 text-sm">
              <p><span className="text-gray-500">描述:</span> {selectedConflict.description}</p>
              <p><span className="text-gray-500">赌注:</span> {selectedConflict.stakes}</p>
              <p><span className="text-gray-500">当前强度:</span> {selectedConflict.intensity}</p>
              {selectedConflict.escalation_history.length > 0 && (
                <div>
                  <span className="text-gray-500">升级历史:</span>
                  <ul className="list-disc ml-5">
                    {selectedConflict.escalation_history.map((e, i) => (
                      <li key={i}>
                        第{e.chapter}章: {e.from_intensity} → {e.to_intensity} ({e.reason})
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
            <div className="flex gap-2 mt-4">
              {selectedConflict.status === 'active' && (
                <>
                  <button
                    onClick={() => {
                      const chapter = prompt('升级章节号:');
                      const reason = prompt('升级原因:');
                      if (chapter && reason) {
                        handleEscalateConflict(selectedConflict.id, parseInt(chapter), reason);
                      }
                    }}
                    className="px-4 py-2 bg-orange-500 text-white rounded"
                  >
                    升级冲突
                  </button>
                  <button
                    onClick={() => {
                      const chapter = prompt('解决章节号:');
                      const method = prompt('解决方式:');
                      if (chapter && method) {
                        handleResolveConflict(selectedConflict.id, parseInt(chapter), method);
                      }
                    }}
                    className="px-4 py-2 bg-green-500 text-white rounded"
                  >
                    解决冲突
                  </button>
                </>
              )}
              <button
                onClick={() => setSelectedConflict(null)}
                className="px-4 py-2 border rounded"
              >
                关闭
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );

  return (
    <div className="bg-white rounded-lg shadow-md p-6">
      <h3 className="text-lg font-bold text-gray-800 mb-4">反派与冲突管理</h3>

      {/* 标签页 */}
      <div className="flex border-b mb-4">
        <button
          onClick={() => setActiveTab('villains')}
          className={`px-4 py-2 font-medium ${
            activeTab === 'villains'
              ? 'text-red-600 border-b-2 border-red-600'
              : 'text-gray-500 hover:text-gray-700'
          }`}
        >
          反派管理
        </button>
        <button
          onClick={() => setActiveTab('conflicts')}
          className={`px-4 py-2 font-medium ${
            activeTab === 'conflicts'
              ? 'text-red-600 border-b-2 border-red-600'
              : 'text-gray-500 hover:text-gray-700'
          }`}
        >
          冲突追踪
        </button>
      </div>

      {/* 错误提示 */}
      {error && (
        <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded text-red-600">
          {error}
        </div>
      )}

      {/* 内容 */}
      {loading ? (
        <div className="text-center py-8 text-gray-400">加载中...</div>
      ) : (
        <>
          {activeTab === 'villains' && renderVillainList()}
          {activeTab === 'conflicts' && renderConflictList()}
        </>
      )}
    </div>
  );
};

export default VillainManager;
