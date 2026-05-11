/**
 * 卷规划编辑器组件
 * GodView v9: 卷级规划系统
 */

import React, { useState, useCallback, useEffect } from 'react';
import {
  getVolumes,
  planVolume,
  getVolume,
  updateVolume,
  designClimax,
  getEmotionalArc,
  activateVolume,
  completeVolume,
  VolumeOutline,
  EmotionArcPoint,
  VolumePlanResponse,
} from '../api/volumes';

interface VolumePlannerProps {
  projectId: string;
}

const volumePlanToOutline = (
  result: VolumePlanResponse,
  projectId: string,
  volumeNumber: number,
  theme?: string,
): VolumeOutline => {
  const info = result.volume_info || {};
  const chapterPlan = result.chapter_plan || [];
  const climaxDesign = result.climax_design || {};
  return {
    id: String(info.id || `planned_volume_${volumeNumber}`),
    project_id: projectId,
    volume_number: Number(info.volume_number || volumeNumber),
    title: String(info.title || `第${volumeNumber}卷`),
    theme: String(info.theme || theme || ''),
    summary: String(info.summary || ''),
    start_chapter: Number(info.start_chapter || chapterPlan[0]?.chapter || 1),
    end_chapter: Number(info.end_chapter || chapterPlan[chapterPlan.length - 1]?.chapter || 1),
    target_word_count: Number(info.target_word_count || info.target_words || 50000),
    climax_description: String(climaxDesign.description || climaxDesign.climax_description || ''),
    climax_chapter: climaxDesign.chapter || climaxDesign.climax_chapter || null,
    emotional_arc: Array.isArray(result.emotional_arc) ? result.emotional_arc : [],
    key_events: chapterPlan.map((item, index) => ({
      chapter: Number(item.chapter || index + 1),
      event: String(item.event || item.summary || item.title || ''),
      type: String(item.type || 'plot'),
    })),
    status: 'planning',
    created_at: new Date().toISOString(),
  };
};

const VolumePlanner: React.FC<VolumePlannerProps> = ({ projectId }) => {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // 卷列表
  const [volumes, setVolumes] = useState<VolumeOutline[]>([]);
  const [selectedVolume, setSelectedVolume] = useState<VolumeOutline | null>(null);

  // 新建卷
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [newVolumeNumber, setNewVolumeNumber] = useState(1);
  const [newVolumeTheme, setNewVolumeTheme] = useState('');

  // 情绪曲线
  const [emotionalArc, setEmotionalArc] = useState<{
    emotional_arc: EmotionArcPoint[];
    peak_chapter: number;
    valley_chapter: number;
  } | null>(null);

  // 加载卷列表
  const loadVolumes = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await getVolumes(projectId);
      setVolumes(data);
      if (data.length > 0 && !selectedVolume) {
        setSelectedVolume(data[0]);
      }
    } catch (err: any) {
      setError(err.message || '加载失败');
    } finally {
      setLoading(false);
    }
  }, [projectId, selectedVolume]);

  // AI 规划卷
  const handlePlanVolume = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const result = await planVolume({
        project_id: projectId,
        volume_number: newVolumeNumber,
        theme: newVolumeTheme || undefined,
      });
      const newVolume = volumePlanToOutline(result, projectId, newVolumeNumber, newVolumeTheme || undefined);
      setVolumes([...volumes, newVolume]);
      setSelectedVolume(newVolume);
      setShowCreateModal(false);
      setNewVolumeTheme('');
    } catch (err: any) {
      setError(err.message || '规划失败');
    } finally {
      setLoading(false);
    }
  }, [projectId, newVolumeNumber, newVolumeTheme, volumes]);

  // 加载情绪曲线
  const loadEmotionalArc = useCallback(async (volumeNumber: number) => {
    setLoading(true);
    try {
      const data = await getEmotionalArc(volumeNumber, projectId);
      setEmotionalArc(data);
    } catch (err: any) {
      setError(err.message || '加载失败');
    } finally {
      setLoading(false);
    }
  }, [projectId]);

  // 设计高潮
  const handleDesignClimax = useCallback(async () => {
    if (!selectedVolume) return;
    setLoading(true);
    setError(null);
    try {
      const result = await designClimax({
        project_id: projectId,
        volume_number: selectedVolume.volume_number,
        volume_id: selectedVolume.id,
        climax_event: selectedVolume.climax_description || selectedVolume.summary || selectedVolume.title,
        emotional_peak: '高潮',
      });
      // 更新选中的卷
      const updated = {
        ...selectedVolume,
        climax_description: result.climax_description,
        climax_chapter: result.climax_chapter,
      };
      setSelectedVolume(updated);
      setVolumes(volumes.map(v => v.volume_number === updated.volume_number ? updated : v));
    } catch (err: any) {
      setError(err.message || '设计失败');
    } finally {
      setLoading(false);
    }
  }, [projectId, selectedVolume, volumes]);

  // 激活卷
  const handleActivate = useCallback(async () => {
    if (!selectedVolume) return;
    setLoading(true);
    try {
      const updated = await activateVolume(selectedVolume.volume_number, projectId);
      setSelectedVolume(updated);
      setVolumes(volumes.map(v => v.volume_number === updated.volume_number ? updated : v));
    } catch (err: any) {
      setError(err.message || '激活失败');
    } finally {
      setLoading(false);
    }
  }, [projectId, selectedVolume, volumes]);

  // 完成卷
  const handleComplete = useCallback(async () => {
    if (!selectedVolume) return;
    setLoading(true);
    try {
      const updated = await completeVolume(selectedVolume.volume_number, projectId);
      setSelectedVolume(updated);
      setVolumes(volumes.map(v => v.volume_number === updated.volume_number ? updated : v));
    } catch (err: any) {
      setError(err.message || '操作失败');
    } finally {
      setLoading(false);
    }
  }, [projectId, selectedVolume, volumes]);

  // 初始化
  useEffect(() => {
    loadVolumes();
  }, [loadVolumes]);

  // 选中卷变化时加载情绪曲线
  useEffect(() => {
    if (selectedVolume) {
      loadEmotionalArc(selectedVolume.volume_number);
    }
  }, [selectedVolume, loadEmotionalArc]);

  const getStatusColor = (status: string) => {
    const colors: Record<string, string> = {
      planning: 'bg-gray-100 text-gray-800',
      active: 'bg-green-100 text-green-800',
      completed: 'bg-blue-100 text-blue-800',
    };
    return colors[status] || 'bg-gray-100';
  };

  const getStatusLabel = (status: string) => {
    const labels: Record<string, string> = {
      planning: '规划中',
      active: '进行中',
      completed: '已完成',
    };
    return labels[status] || status;
  };

  const getEmotionColor = (emotion: string) => {
    const colors: Record<string, string> = {
      高兴: 'text-green-500',
      激动: 'text-red-500',
      紧张: 'text-orange-500',
      悲伤: 'text-blue-500',
      愤怒: 'text-red-600',
      期待: 'text-purple-500',
      平静: 'text-gray-500',
    };
    return colors[emotion] || 'text-gray-600';
  };

  const renderEmotionalArcChart = () => {
    if (!emotionalArc || emotionalArc.emotional_arc.length === 0) {
      return <div className="text-gray-400 text-center py-4">暂无情绪曲线数据</div>;
    }

    const maxIntensity = Math.max(...emotionalArc.emotional_arc.map(p => p.intensity));
    const minIntensity = Math.min(...emotionalArc.emotional_arc.map(p => p.intensity));

    return (
      <div className="mt-4">
        <div className="flex items-end justify-between h-32 gap-1">
          {emotionalArc.emotional_arc.map((point, i) => {
            const height = ((point.intensity - minIntensity) / (maxIntensity - minIntensity || 1)) * 100;
            return (
              <div key={i} className="flex-1 flex flex-col items-center">
                <div
                  className={`w-full rounded-t transition-all hover:opacity-80 ${
                    point.chapter === emotionalArc.peak_chapter
                      ? 'bg-red-400'
                      : point.chapter === emotionalArc.valley_chapter
                      ? 'bg-blue-400'
                      : 'bg-purple-300'
                  }`}
                  style={{ height: `${Math.max(height, 10)}%` }}
                  title={`${point.description} (${point.intensity})`}
                />
              </div>
            );
          })}
        </div>
        <div className="flex justify-between mt-2 text-xs text-gray-400">
          <span>第{emotionalArc.emotional_arc[0]?.chapter}章</span>
          <span>第{emotionalArc.emotional_arc[emotionalArc.emotional_arc.length - 1]?.chapter}章</span>
        </div>
        <div className="flex justify-center gap-4 mt-2 text-xs">
          <span className="flex items-center gap-1">
            <span className="w-3 h-3 bg-red-400 rounded" />
            高潮点
          </span>
          <span className="flex items-center gap-1">
            <span className="w-3 h-3 bg-blue-400 rounded" />
            低谷点
          </span>
        </div>
      </div>
    );
  };

  return (
    <div className="bg-white rounded-lg shadow-md p-6">
      <h3 className="text-lg font-bold text-gray-800 mb-4">卷规划编辑器</h3>

      <div className="flex gap-4">
        {/* 左侧卷列表 */}
        <div className="w-48 flex-shrink-0">
          <div className="flex justify-between items-center mb-2">
            <span className="text-sm font-medium text-gray-700">卷列表</span>
            <button
              onClick={() => {
                setNewVolumeNumber(volumes.length + 1);
                setShowCreateModal(true);
              }}
              className="text-blue-500 text-sm hover:text-blue-600"
            >
              + 新建
            </button>
          </div>
          <div className="space-y-1">
            {volumes.map((volume) => (
              <div
                key={volume.id}
                onClick={() => setSelectedVolume(volume)}
                className={`p-2 rounded cursor-pointer transition ${
                  selectedVolume?.id === volume.id
                    ? 'bg-blue-100 border border-blue-300'
                    : 'bg-gray-50 hover:bg-gray-100'
                }`}
              >
                <div className="font-medium text-sm text-gray-800">
                  第{volume.volume_number}卷
                </div>
                <div className="text-xs text-gray-500 truncate">{volume.title}</div>
              </div>
            ))}
            {volumes.length === 0 && !loading && (
              <div className="text-center text-gray-400 py-4 text-sm">暂无卷数据</div>
            )}
          </div>
        </div>

        {/* 右侧详情 */}
        <div className="flex-1">
          {selectedVolume ? (
            <div className="space-y-4">
              {/* 基本信息 */}
              <div className="p-4 bg-gray-50 rounded-lg">
                <div className="flex items-start justify-between mb-2">
                  <div>
                    <h4 className="font-bold text-lg text-gray-800">{selectedVolume.title}</h4>
                    <div className="text-sm text-gray-500">
                      第{selectedVolume.start_chapter}-{selectedVolume.end_chapter}章
                    </div>
                  </div>
                  <span className={`text-xs px-2 py-1 rounded ${getStatusColor(selectedVolume.status)}`}>
                    {getStatusLabel(selectedVolume.status)}
                  </span>
                </div>
                <div className="grid grid-cols-2 gap-2 text-sm mt-3">
                  <div>
                    <span className="text-gray-500">主题:</span> {selectedVolume.theme || '未设定'}
                  </div>
                  <div>
                    <span className="text-gray-500">目标字数:</span> {selectedVolume.target_word_count?.toLocaleString() || '未设定'}
                  </div>
                </div>
                {selectedVolume.summary && (
                  <p className="text-sm text-gray-600 mt-2">{selectedVolume.summary}</p>
                )}
              </div>

              {/* 卷高潮 */}
              <div className="p-4 bg-gradient-to-r from-red-50 to-orange-50 rounded-lg border border-red-200">
                <div className="flex items-center justify-between mb-2">
                  <h4 className="font-medium text-red-800">卷高潮</h4>
                  <button
                    onClick={handleDesignClimax}
                    disabled={loading}
                    className="text-xs px-3 py-1 bg-red-500 text-white rounded hover:bg-red-600"
                  >
                    设计高潮
                  </button>
                </div>
                {selectedVolume.climax_description ? (
                  <>
                    <p className="text-sm text-red-700">{selectedVolume.climax_description}</p>
                    {selectedVolume.climax_chapter && (
                      <div className="text-xs text-red-500 mt-1">
                        计划高潮章节: 第{selectedVolume.climax_chapter}章
                      </div>
                    )}
                  </>
                ) : (
                  <p className="text-sm text-red-400">点击"设计高潮"AI生成</p>
                )}
              </div>

              {/* 情绪曲线 */}
              <div className="p-4 bg-purple-50 rounded-lg border border-purple-200">
                <h4 className="font-medium text-purple-800 mb-2">情绪曲线</h4>
                {renderEmotionalArcChart()}
              </div>

              {/* 关键事件 */}
              {selectedVolume.key_events.length > 0 && (
                <div className="p-4 bg-blue-50 rounded-lg border border-blue-200">
                  <h4 className="font-medium text-blue-800 mb-2">关键事件</h4>
                  <div className="space-y-2">
                    {selectedVolume.key_events.map((event, i) => (
                      <div key={i} className="flex items-center gap-2 text-sm">
                        <span className="text-xs text-blue-500 bg-blue-100 px-2 py-0.5 rounded">
                          第{event.chapter}章
                        </span>
                        <span className="text-blue-700">{event.event}</span>
                        <span className="text-xs text-blue-400">({event.type})</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* 操作按钮 */}
              <div className="flex gap-2">
                {selectedVolume.status === 'planning' && (
                  <button
                    onClick={handleActivate}
                    disabled={loading}
                    className="px-4 py-2 bg-green-500 text-white rounded hover:bg-green-600"
                  >
                    激活此卷
                  </button>
                )}
                {selectedVolume.status === 'active' && (
                  <button
                    onClick={handleComplete}
                    disabled={loading}
                    className="px-4 py-2 bg-blue-500 text-white rounded hover:bg-blue-600"
                  >
                    完成此卷
                  </button>
                )}
              </div>
            </div>
          ) : (
            <div className="text-center text-gray-400 py-8">
              选择或创建一个卷开始规划
            </div>
          )}
        </div>
      </div>

      {/* 错误提示 */}
      {error && (
        <div className="mt-4 p-3 bg-red-50 border border-red-200 rounded text-red-600">
          {error}
        </div>
      )}

      {/* 新建卷弹窗 */}
      {showCreateModal && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg p-6 max-w-md w-full mx-4">
            <h3 className="text-lg font-bold mb-4">AI 规划新卷</h3>
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium mb-1">卷号</label>
                <input
                  type="number"
                  value={newVolumeNumber}
                  onChange={(e) => setNewVolumeNumber(parseInt(e.target.value, 10) || 1)}
                  className="w-full px-3 py-2 border rounded"
                  min={1}
                />
              </div>
              <div>
                <label className="block text-sm font-medium mb-1">主题 (可选)</label>
                <input
                  type="text"
                  value={newVolumeTheme}
                  onChange={(e) => setNewVolumeTheme(e.target.value)}
                  className="w-full px-3 py-2 border rounded"
                  placeholder="留空则AI生成"
                />
              </div>
            </div>
            <div className="flex gap-2 mt-4">
              <button
                onClick={handlePlanVolume}
                disabled={loading}
                className="flex-1 py-2 bg-purple-500 text-white rounded"
              >
                {loading ? '生成中...' : '生成卷规划'}
              </button>
              <button
                onClick={() => setShowCreateModal(false)}
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
};

export default VolumePlanner;
