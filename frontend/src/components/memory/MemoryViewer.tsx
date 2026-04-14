/**
 * 记忆查看组件
 * GodView v9: 长篇记忆架构
 */

import React, { useState, useCallback, useEffect } from 'react';
import {
  getMemories,
  searchMemories,
  getSnapshot,
  getPendingForeshadowings,
  MemoryEntry,
  MemorySnapshot,
  Foreshadowing,
  MemoryType,
  MemoryCategory,
} from '../../api/memories';

interface MemoryViewerProps {
  projectId: string;
  currentChapter?: number;
}

const MemoryViewer: React.FC<MemoryViewerProps> = ({ projectId, currentChapter = 1 }) => {
  const [activeTab, setActiveTab] = useState<'memories' | 'snapshot' | 'foreshadowing'>('memories');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // 记忆列表
  const [memories, setMemories] = useState<MemoryEntry[]>([]);
  const [memoryType, setMemoryType] = useState<MemoryType | ''>('');
  const [category, setCategory] = useState<MemoryCategory | ''>('');
  const [searchQuery, setSearchQuery] = useState('');

  // 快照
  const [snapshot, setSnapshot] = useState<MemorySnapshot | null>(null);
  const [snapshotChapter, setSnapshotChapter] = useState(currentChapter);

  // 伏笔
  const [foreshadowings, setForeshadowings] = useState<Foreshadowing[]>([]);

  // 加载记忆列表
  const loadMemories = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const params: any = { limit: 50 };
      if (memoryType) params.memory_type = memoryType;
      if (category) params.category = category;
      const data = await getMemories(projectId, params);
      setMemories(data);
    } catch (err: any) {
      setError(err.message || '加载失败');
    } finally {
      setLoading(false);
    }
  }, [projectId, memoryType, category]);

  // 搜索记忆
  const handleSearch = useCallback(async () => {
    if (!searchQuery.trim()) {
      loadMemories();
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const result = await searchMemories({
        project_id: projectId,
        query: searchQuery,
        limit: 20,
      });
      setMemories(result.results);
    } catch (err: any) {
      setError(err.message || '搜索失败');
    } finally {
      setLoading(false);
    }
  }, [projectId, searchQuery, loadMemories]);

  // 加载快照
  const loadSnapshot = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await getSnapshot(projectId, snapshotChapter);
      setSnapshot(data);
    } catch (err: any) {
      setError(err.message || '加载快照失败');
    } finally {
      setLoading(false);
    }
  }, [projectId, snapshotChapter]);

  // 加载伏笔
  const loadForeshadowings = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await getPendingForeshadowings(projectId);
      setForeshadowings(data);
    } catch (err: any) {
      setError(err.message || '加载伏笔失败');
    } finally {
      setLoading(false);
    }
  }, [projectId]);

  // 初始化加载
  useEffect(() => {
    if (activeTab === 'memories') loadMemories();
    else if (activeTab === 'snapshot') loadSnapshot();
    else if (activeTab === 'foreshadowing') loadForeshadowings();
  }, [activeTab, loadMemories, loadSnapshot, loadForeshadowings]);

  const getMemoryTypeColor = (type: MemoryType) => {
    const colors: Record<MemoryType, string> = {
      short_term: 'bg-yellow-100 text-yellow-800',
      medium_term: 'bg-blue-100 text-blue-800',
      long_term: 'bg-purple-100 text-purple-800',
    };
    return colors[type];
  };

  const getMemoryTypeLabel = (type: MemoryType) => {
    const labels: Record<MemoryType, string> = {
      short_term: '短期',
      medium_term: '中期',
      long_term: '长期',
    };
    return labels[type];
  };

  const getForeshadowingStatusColor = (status: string) => {
    const colors: Record<string, string> = {
      planted: 'bg-orange-100 text-orange-800',
      revealed: 'bg-green-100 text-green-800',
      abandoned: 'bg-gray-100 text-gray-800',
    };
    return colors[status] || 'bg-gray-100';
  };

  const renderMemoryList = () => (
    <div>
      {/* 搜索和筛选 */}
      <div className="flex gap-2 mb-4">
        <input
          type="text"
          placeholder="搜索记忆..."
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          className="flex-1 px-3 py-2 border rounded"
        />
        <button
          onClick={handleSearch}
          className="px-4 py-2 bg-blue-500 text-white rounded hover:bg-blue-600"
        >
          搜索
        </button>
      </div>

      <div className="flex gap-2 mb-4">
        <select
          value={memoryType}
          onChange={(e) => setMemoryType(e.target.value as MemoryType | '')}
          className="px-3 py-2 border rounded"
        >
          <option value="">全部类型</option>
          <option value="short_term">短期记忆</option>
          <option value="medium_term">中期记忆</option>
          <option value="long_term">长期记忆</option>
        </select>
        <select
          value={category}
          onChange={(e) => setCategory(e.target.value as MemoryCategory | '')}
          className="px-3 py-2 border rounded"
        >
          <option value="">全部分类</option>
          <option value="character">角色</option>
          <option value="event">事件</option>
          <option value="setting">设定</option>
          <option value="relationship">关系</option>
          <option value="foreshadowing">伏笔</option>
          <option value="conflict">冲突</option>
        </select>
      </div>

      {/* 记忆列表 */}
      <div className="space-y-3 max-h-96 overflow-y-auto">
        {memories.map((memory) => (
          <div key={memory.id} className="p-3 bg-gray-50 rounded-lg border">
            <div className="flex items-start justify-between mb-2">
              <h4 className="font-medium text-gray-800">{memory.title}</h4>
              <span className={`text-xs px-2 py-1 rounded ${getMemoryTypeColor(memory.memory_type)}`}>
                {getMemoryTypeLabel(memory.memory_type)}
              </span>
            </div>
            <p className="text-sm text-gray-600 mb-2">{memory.content}</p>
            <div className="flex items-center gap-2 text-xs text-gray-400">
              {memory.chapter_reference && <span>第{memory.chapter_reference}章</span>}
              {memory.tags.length > 0 && (
                <div className="flex gap-1">
                  {memory.tags.slice(0, 3).map((tag, i) => (
                    <span key={i} className="px-1 bg-gray-200 rounded">
                      {tag}
                    </span>
                  ))}
                </div>
              )}
            </div>
          </div>
        ))}
        {memories.length === 0 && !loading && (
          <div className="text-center text-gray-400 py-8">暂无记忆数据</div>
        )}
      </div>
    </div>
  );

  const renderSnapshot = () => (
    <div>
      {/* 章节选择 */}
      <div className="mb-4">
        <label className="block text-sm font-medium text-gray-700 mb-2">查看章节</label>
        <input
          type="number"
          value={snapshotChapter}
          onChange={(e) => setSnapshotChapter(parseInt(e.target.value, 10) || 1)}
          className="w-24 px-3 py-2 border rounded"
          min={1}
        />
        <button
          onClick={loadSnapshot}
          className="ml-2 px-4 py-2 bg-blue-500 text-white rounded hover:bg-blue-600"
        >
          加载
        </button>
      </div>

      {snapshot && (
        <div className="space-y-4">
          {/* 角色状态 */}
          <div>
            <h4 className="font-medium text-gray-700 mb-2">角色状态</h4>
            <div className="grid grid-cols-2 gap-2">
              {Object.entries(snapshot.character_states).map(([id, state]) => (
                <div key={id} className="p-2 bg-gray-50 rounded border">
                  <div className="font-medium text-gray-800">{state.character_name}</div>
                  {state.current_location && (
                    <div className="text-xs text-gray-500">位置: {state.current_location}</div>
                  )}
                  {state.emotional_state && (
                    <div className="text-xs text-gray-500">情绪: {state.emotional_state}</div>
                  )}
                  {state.knowledge_gained.length > 0 && (
                    <div className="text-xs text-gray-500">
                      新知识: {state.knowledge_gained.slice(0, 2).join(', ')}
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>

          {/* 关键事件 */}
          {snapshot.key_events.length > 0 && (
            <div>
              <h4 className="font-medium text-gray-700 mb-2">关键事件</h4>
              <div className="space-y-2">
                {snapshot.key_events.map((event, i) => (
                  <div key={i} className="p-2 bg-blue-50 rounded border border-blue-200">
                    <div className="text-sm font-medium">{event.event}</div>
                    <div className="text-xs text-gray-500">第{event.chapter}章 · {event.impact}</div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* 待回收伏笔 */}
          {snapshot.active_foreshadowings.length > 0 && (
            <div>
              <h4 className="font-medium text-gray-700 mb-2">待回收伏笔</h4>
              <div className="text-sm text-orange-600">
                共 {snapshot.active_foreshadowings.length} 个伏笔待回收
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );

  const renderForeshadowing = () => (
    <div className="space-y-3">
      {foreshadowings.map((f) => (
        <div key={f.id} className="p-3 bg-gray-50 rounded-lg border">
          <div className="flex items-start justify-between mb-2">
            <h4 className="font-medium text-gray-800">{f.title}</h4>
            <span className={`text-xs px-2 py-1 rounded ${getForeshadowingStatusColor(f.status)}`}>
              {f.status === 'planted' ? '待回收' : f.status === 'revealed' ? '已揭示' : '已废弃'}
            </span>
          </div>
          <p className="text-sm text-gray-600 mb-2">{f.description}</p>
          <div className="flex items-center gap-4 text-xs text-gray-400">
            <span>埋设: 第{f.planted_chapter}章</span>
            {f.planned_reveal_chapter && (
              <span>计划揭示: 第{f.planned_reveal_chapter}章</span>
            )}
          </div>
          {f.notes && (
            <div className="mt-2 text-xs text-gray-500 bg-white p-2 rounded">
              {f.notes}
            </div>
          )}
        </div>
      ))}
      {foreshadowings.length === 0 && !loading && (
        <div className="text-center text-gray-400 py-8">暂无待回收伏笔</div>
      )}
    </div>
  );

  return (
    <div className="bg-white rounded-lg shadow-md p-6">
      <h3 className="text-lg font-bold text-gray-800 mb-4">记忆系统</h3>

      {/* 标签页 */}
      <div className="flex border-b mb-4">
        <button
          onClick={() => setActiveTab('memories')}
          className={`px-4 py-2 font-medium ${
            activeTab === 'memories'
              ? 'text-blue-600 border-b-2 border-blue-600'
              : 'text-gray-500 hover:text-gray-700'
          }`}
        >
          记忆列表
        </button>
        <button
          onClick={() => setActiveTab('snapshot')}
          className={`px-4 py-2 font-medium ${
            activeTab === 'snapshot'
              ? 'text-blue-600 border-b-2 border-blue-600'
              : 'text-gray-500 hover:text-gray-700'
          }`}
        >
          状态快照
        </button>
        <button
          onClick={() => setActiveTab('foreshadowing')}
          className={`px-4 py-2 font-medium ${
            activeTab === 'foreshadowing'
              ? 'text-blue-600 border-b-2 border-blue-600'
              : 'text-gray-500 hover:text-gray-700'
          }`}
        >
          伏笔追踪
        </button>
      </div>

      {/* 错误提示 */}
      {error && (
        <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded text-red-600">
          {error}
        </div>
      )}

      {/* 加载状态 */}
      {loading ? (
        <div className="text-center py-8 text-gray-400">加载中...</div>
      ) : (
        <>
          {activeTab === 'memories' && renderMemoryList()}
          {activeTab === 'snapshot' && renderSnapshot()}
          {activeTab === 'foreshadowing' && renderForeshadowing()}
        </>
      )}
    </div>
  );
};

export default MemoryViewer;
