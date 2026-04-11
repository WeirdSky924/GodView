/**
 * 干预日志组件
 * v8 Agent协作可视化工作台
 */

import { useState, useEffect } from 'react'
import { useTheme } from '@/contexts/ThemeContext'
import {
  getV8Interventions,
  exportV8Interventions,
  deleteV8Intervention,
  INTERVENTION_TYPE_LABELS,
  INTERVENTION_TYPE_COLORS,
  type V8InterventionLog,
  type V8InterventionQuery,
} from '@/api/interventions'
import {
  History,
  Filter,
  Download,
  ChevronRight,
  Bot,
  Clock,
  Search,
  Trash2,
  AlertTriangle,
} from 'lucide-react'

interface InterventionLogProps {
  projectId: string
  executionId?: string
}

export default function InterventionLog({ projectId, executionId }: InterventionLogProps) {
  const { theme } = useTheme()
  const isDark = theme === 'dark'

  const [logs, setLogs] = useState<V8InterventionLog[]>([])
  const [loading, setLoading] = useState(false)
  const [selectedLog, setSelectedLog] = useState<V8InterventionLog | null>(null)
  const [filter, setFilter] = useState<V8InterventionQuery>({
    project_id: projectId,
    workflow_execution_id: executionId,
    limit: 50,
  })
  const [showFilters, setShowFilters] = useState(false)
  const [searchKeyword, setSearchKeyword] = useState('')
  const [deleting, setDeleting] = useState<string | null>(null)
  const [showDeleteConfirm, setShowDeleteConfirm] = useState<string | null>(null)

  // 加载日志
  useEffect(() => {
    loadLogs()
  }, [filter])

  const loadLogs = async () => {
    setLoading(true)
    try {
      const result = await getV8Interventions(filter)
      setLogs(result)
    } catch (error) {
      console.error('Failed to load intervention logs:', error)
    } finally {
      setLoading(false)
    }
  }

  const handleSearch = () => {
    setFilter((prev) => ({
      ...prev,
      keyword: searchKeyword || undefined,
    }))
  }

  const handleExport = async (format: 'json' | 'csv' | 'markdown') => {
    try {
      const result = await exportV8Interventions(
        projectId,
        executionId,
        format,
        true,
      )

      // 创建下载链接
      const blob = new Blob([result.content], { type: 'text/plain' })
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = result.filename
      a.click()
      URL.revokeObjectURL(url)
    } catch (error) {
      console.error('Failed to export logs:', error)
    }
  }

  const handleDelete = async (logId: string) => {
    setDeleting(logId)
    try {
      await deleteV8Intervention(logId)
      // 从列表中移除
      setLogs((prev) => prev.filter((log) => log.id !== logId))
      if (selectedLog?.id === logId) {
        setSelectedLog(null)
      }
      setShowDeleteConfirm(null)
    } catch (error) {
      console.error('Failed to delete intervention:', error)
    } finally {
      setDeleting(null)
    }
  }

  // 格式化时间
  const formatTime = (dateStr: string) => {
    const date = new Date(dateStr)
    return date.toLocaleString('zh-CN', {
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
    })
  }

  // 获取干预类型显示
  const getInterventionTypeDisplay = (type: string) => {
    const typeKey = type as keyof typeof INTERVENTION_TYPE_LABELS
    return {
      label: INTERVENTION_TYPE_LABELS[typeKey] || type,
      color: INTERVENTION_TYPE_COLORS[typeKey] || '',
    }
  }

  return (
    <div className={`h-full flex flex-col ${isDark ? 'bg-gray-900' : 'bg-white'}`}>
      {/* 标题 */}
      <div
        className={`
          flex items-center justify-between p-4 border-b
          ${isDark ? 'border-gray-700' : 'border-gray-200'}
        `}
      >
        <h3
          className={`text-sm font-semibold flex items-center gap-2 ${
            isDark ? 'text-gray-200' : 'text-gray-700'
          }`}
        >
          <History size={16} />
          干预日志
        </h3>
        <div className="flex items-center gap-2">
          <button
            onClick={() => setShowFilters(!showFilters)}
            className={`p-1.5 rounded hover:bg-gray-100 dark:hover:bg-gray-800 ${
              showFilters ? 'text-blue-500' : ''
            }`}
            title="筛选"
          >
            <Filter size={16} />
          </button>
          <button
            onClick={() => handleExport('json')}
            className={`p-1.5 rounded hover:bg-gray-100 dark:hover:bg-gray-800`}
            title="导出 JSON"
          >
            <Download size={16} />
          </button>
        </div>
      </div>

      {/* 筛选器 */}
      {showFilters && (
        <div
          className={`
            p-4 border-b space-y-3
            ${isDark ? 'border-gray-700 bg-gray-800' : 'border-gray-200 bg-gray-50'}
          `}
        >
          <div className="flex gap-2">
            <input
              type="text"
              value={searchKeyword}
              onChange={(e) => setSearchKeyword(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
              placeholder="搜索关键词..."
              className={`
                flex-1 px-3 py-1.5 rounded border text-sm
                ${isDark
                  ? 'bg-gray-700 border-gray-600 text-white'
                  : 'bg-white border-gray-300'
                }
              `}
            />
            <button
              onClick={handleSearch}
              className="px-3 py-1.5 bg-blue-500 text-white rounded text-sm hover:bg-blue-600"
            >
              <Search size={14} />
            </button>
          </div>

          <div className="flex gap-2">
            <select
              value={filter.agent_type || ''}
              onChange={(e) =>
                setFilter((prev) => ({
                  ...prev,
                  agent_type: e.target.value || undefined,
                }))
              }
              className={`
                flex-1 px-2 py-1.5 rounded border text-sm
                ${isDark
                  ? 'bg-gray-700 border-gray-600 text-white'
                  : 'bg-white border-gray-300'
                }
              `}
            >
              <option value="">全部 Agent</option>
              <option value="setting">设定 Agent</option>
              <option value="writer">作家 Agent</option>
              <option value="master_plotter">编剧 Agent</option>
              <option value="character">角色 Agent</option>
              <option value="evaluator">评估 Agent</option>
            </select>

            <select
              value={filter.intervention_type || ''}
              onChange={(e) =>
                setFilter((prev) => ({
                  ...prev,
                  intervention_type: e.target.value as any || undefined,
                }))
              }
              className={`
                flex-1 px-2 py-1.5 rounded border text-sm
                ${isDark
                  ? 'bg-gray-700 border-gray-600 text-white'
                  : 'bg-white border-gray-300'
                }
              `}
            >
              <option value="">全部类型</option>
              <option value="guidance">指导性</option>
              <option value="correction">纠正性</option>
              <option value="direction">方向性</option>
              <option value="override">覆盖性</option>
            </select>
          </div>
        </div>
      )}

      {/* 日志列表 */}
      <div className="flex-1 overflow-y-auto">
        {loading ? (
          <div className="flex items-center justify-center h-32">
            <div className={`text-sm ${isDark ? 'text-gray-500' : 'text-gray-400'}`}>
              加载中...
            </div>
          </div>
        ) : logs.length === 0 ? (
          <div
            className={`
              flex items-center justify-center h-32 text-sm
              ${isDark ? 'text-gray-500' : 'text-gray-400'}
            `}
          >
            暂无干预记录
          </div>
        ) : (
          <div className="divide-y dark:divide-gray-700">
            {logs.map((log) => {
              const typeDisplay = getInterventionTypeDisplay(log.intervention_type)
              const logTime = log.timestamp || log.created_at || ''

              return (
                <div key={log.id}>
                  <button
                    onClick={() => setSelectedLog(selectedLog?.id === log.id ? null : log)}
                    className={`
                      w-full p-4 text-left hover:bg-gray-50 dark:hover:bg-gray-800
                      ${selectedLog?.id === log.id ? 'bg-blue-50 dark:bg-gray-800' : ''}
                    `}
                  >
                    <div className="flex items-center gap-3">
                      <div className="w-8 h-8 rounded-full bg-green-100 text-green-600 flex items-center justify-center">
                        <Bot size={14} />
                      </div>
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2">
                          <span
                            className={`font-medium text-sm ${
                              isDark ? 'text-gray-200' : 'text-gray-700'
                            }`}
                          >
                            {log.agent_name || log.agent_type}
                          </span>
                          <span
                            className={`text-xs px-1.5 py-0.5 rounded ${
                              isDark ? 'bg-gray-700' : 'bg-gray-100'
                            } ${typeDisplay.color}`}
                          >
                            {typeDisplay.label}
                          </span>
                        </div>
                        <div
                          className={`text-sm truncate ${
                            isDark ? 'text-gray-400' : 'text-gray-500'
                          }`}
                        >
                          {log.user_message}
                        </div>
                      </div>
                      <div className="flex items-center gap-2">
                        {log.response_time_ms && (
                          <span
                            className={`text-xs ${
                              isDark ? 'text-gray-500' : 'text-gray-400'
                            }`}
                          >
                            {log.response_time_ms}ms
                          </span>
                        )}
                        {/* 快速删除按钮 */}
                        <button
                          onClick={(e) => {
                            e.stopPropagation()
                            setShowDeleteConfirm(log.id)
                          }}
                          className={`p-1 rounded opacity-50 hover:opacity-100 hover:bg-red-100 dark:hover:bg-red-900/30 text-red-500`}
                          title="删除此记录"
                        >
                          <Trash2 size={14} />
                        </button>
                        <ChevronRight
                          size={16}
                          className={`transition-transform ${
                            selectedLog?.id === log.id ? 'rotate-90' : ''
                          }`}
                        />
                      </div>
                    </div>
                  </button>

                  {/* 展开详情 */}
                  {selectedLog?.id === log.id && (
                    <div
                      className={`
                        px-4 pb-4 space-y-3
                        ${isDark ? 'bg-gray-800' : 'bg-gray-50'}
                      `}
                    >
                      <div>
                        <div
                          className={`text-xs font-medium mb-1 ${
                            isDark ? 'text-gray-400' : 'text-gray-500'
                          }`}
                        >
                          用户消息
                        </div>
                        <div
                          className={`text-sm p-2 rounded ${
                            isDark ? 'bg-gray-700' : 'bg-white'
                          }`}
                        >
                          {log.user_message}
                        </div>
                      </div>
                      {log.agent_response && (
                        <div>
                          <div
                            className={`text-xs font-medium mb-1 ${
                              isDark ? 'text-gray-400' : 'text-gray-500'
                            }`}
                          >
                            Agent 响应
                          </div>
                          <div
                            className={`text-sm p-2 rounded whitespace-pre-wrap max-h-40 overflow-y-auto ${
                              isDark ? 'bg-gray-700' : 'bg-white'
                            }`}
                          >
                            {log.agent_response}
                          </div>
                        </div>
                      )}
                      <div className="flex items-center justify-between">
                        <div
                          className={`text-xs flex items-center gap-1 ${
                            isDark ? 'text-gray-500' : 'text-gray-400'
                          }`}
                        >
                          <Clock size={12} />
                          {logTime ? formatTime(logTime) : '-'}
                        </div>

                        {/* 删除按钮 */}
                        <div className="relative">
                          {showDeleteConfirm === log.id ? (
                            <div className="flex items-center gap-2">
                              <span className={`text-xs ${isDark ? 'text-gray-400' : 'text-gray-500'}`}>
                                <AlertTriangle size={12} className="inline mr-1 text-orange-500" />
                                确定删除?
                              </span>
                              <button
                                onClick={() => handleDelete(log.id)}
                                disabled={deleting === log.id}
                                className="px-2 py-1 bg-red-500 text-white text-xs rounded hover:bg-red-600 disabled:opacity-50"
                              >
                                {deleting === log.id ? '删除中...' : '确认'}
                              </button>
                              <button
                                onClick={() => setShowDeleteConfirm(null)}
                                className="px-2 py-1 bg-gray-500 text-white text-xs rounded hover:bg-gray-600"
                              >
                                取消
                              </button>
                            </div>
                          ) : (
                            <button
                              onClick={() => setShowDeleteConfirm(log.id)}
                              className={`p-1.5 rounded hover:bg-red-100 dark:hover:bg-red-900/30 text-red-500`}
                              title="删除此记录"
                            >
                              <Trash2 size={14} />
                            </button>
                          )}
                        </div>
                      </div>
                    </div>
                  )}
                </div>
              )
            })}
          </div>
        )}
      </div>

      {/* 统计 */}
      {logs.length > 0 && (
        <div
          className={`
            p-4 border-t text-xs
            ${isDark ? 'border-gray-700 text-gray-500' : 'border-gray-200 text-gray-400'}
          `}
        >
          共 {logs.length} 条干预记录
        </div>
      )}

      {/* 删除确认弹窗 */}
      {showDeleteConfirm && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className={`p-6 rounded-lg shadow-xl max-w-sm w-full mx-4 ${
            isDark ? 'bg-gray-800' : 'bg-white'
          }`}>
            <div className="flex items-center gap-3 mb-4">
              <div className="w-10 h-10 rounded-full bg-red-100 dark:bg-red-900/30 flex items-center justify-center">
                <AlertTriangle size={20} className="text-red-500" />
              </div>
              <div>
                <h3 className={`font-semibold ${isDark ? 'text-white' : 'text-gray-900'}`}>
                  确认删除
                </h3>
                <p className={`text-sm ${isDark ? 'text-gray-400' : 'text-gray-500'}`}>
                  此操作无法撤销
                </p>
              </div>
            </div>
            <p className={`text-sm mb-6 ${isDark ? 'text-gray-300' : 'text-gray-600'}`}>
              确定要删除这条干预记录吗？
            </p>
            <div className="flex justify-end gap-3">
              <button
                onClick={() => setShowDeleteConfirm(null)}
                className={`px-4 py-2 rounded text-sm ${
                  isDark
                    ? 'bg-gray-700 hover:bg-gray-600 text-gray-300'
                    : 'bg-gray-100 hover:bg-gray-200 text-gray-700'
                }`}
              >
                取消
              </button>
              <button
                onClick={() => handleDelete(showDeleteConfirm)}
                disabled={deleting === showDeleteConfirm}
                className="px-4 py-2 bg-red-500 hover:bg-red-600 text-white text-sm rounded disabled:opacity-50"
              >
                {deleting === showDeleteConfirm ? '删除中...' : '确认删除'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
