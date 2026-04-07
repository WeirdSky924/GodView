/**
 * 时间控制面板组件
 * GodView v5 时间流逝系统的UI组件
 */

import React, { useState, useEffect, useCallback } from 'react'
import { Play, Pause, FastForward, Rewind, Clock, RotateCw, Save, GitBranch, History } from 'lucide-react'
import { useTimeControl } from '@/hooks/useTimeWebSocket'
import { useTimeHistory } from '@/hooks/useTimeWebSocket'
import type { TimeUpdateResult } from '@/api/time'

interface TimeControlPanelProps {
  worldId: string
}

export default function TimeControlPanel({ worldId }: TimeControlPanelProps) {
  const [noteInput, setNoteInput] = useState('')
  const [jumpMinutes, setJumpMinutes] = useState(60)
  const [selectedTab, setSelectedTab] = useState<'control' | 'history' | 'branches'>('control')

  const timeControl = useTimeControl(worldId)
  const timeHistory = useTimeHistory(worldId)

  // 时间跳跃处理器
  const handleForwardJump = useCallback(async () => {
    await timeControl.send({
      type: 'time_jump',
      action: 'forward',
      delta_minutes: jumpMinutes
    })
  }, [timeControl, jumpMinutes])

  const handleBackwardJump = useCallback(async () => {
    await timeControl.send({
      type: 'time_jump',
      action: 'backward',
      delta_minutes: jumpMinutes
    })
  }, [timeControl, jumpMinutes])

  const handleTimeFreeze = useCallback(async () => {
    await timeControl.toggleFreeze()
  }, [timeControl])

  const handleTimeScaleChange = useCallback(async (scale: number) => {
    await timeControl.setTimeScale(scale)
  }, [timeControl.setTimeScale])

  const handleRecordTimePoint = useCallback(async () => {
    if (noteInput.trim()) {
      const success = await timeHistory.recordTimePoint(noteInput)
      if (success) {
        setNoteInput('')
      }
    }
  }, [noteInput, timeHistory])

  const handleManualTick = useCallback(async () => {
    await timeControl.manualTick(10) // 默认推进10分钟
  }, [timeControl.manualTick])

  const timeInfo = timeControl.currentTime ? new Date(timeControl.currentTime) : null
  const friendlyTimeDisplay = timeControl.getFriendlyTimeDisplay ? timeControl.getFriendlyTimeDisplay() : '等待连接...'

  return (
    <div className="bg-white rounded-lg shadow-md p-6 space-y-4">
      {/* 时间显示 */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Clock className="w-6 h-6 text-blue-600" />
          <div>
            <h2 className="text-xl font-bold text-gray-800">时间控制</h2>
            <p className="text-sm text-gray-500">世界时间: {friendlyTimeDisplay}</p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <div className={`px-3 py-1 rounded-full text-sm ${
            timeControl.isFrozen
              ? 'bg-yellow-100 text-yellow-700'
              : timeControl.connected
                ? 'bg-green-100 text-green-700'
                : 'bg-gray-100 text-gray-600'
          }`}>
            {timeControl.isFrozen ? '● 已冻结' :
             timeControl.connected ? '● 已连接' : '○ 未连接'}
          </div>
        </div>
      </div>

      {/* 连接状态提示 */}
      {!timeControl.connected && (
        <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-3">
          <p className="text-sm text-yellow-700">正在连接时间系统...</p>
        </div>
      )}

      {/* 标签页 */}
      <div className="border-b border-gray-200">
        <nav className="flex space-x-8">
          <button
            onClick={() => setSelectedTab('control')}
            className={`pb-2 px-1 border-b-2 font-medium text-sm ${
              selectedTab === 'control'
                ? 'border-blue-500 text-blue-600'
                : 'border-transparent text-gray-500 hover:text-gray-700'
            }`}
          >
            时间控制
          </button>
          <button
            onClick={() => setSelectedTab('history')}
            className={`pb-2 px-1 border-b-2 font-medium text-sm ${
              selectedTab === 'history'
                ? 'border-blue-500 text-blue-600'
                : 'border-transparent text-gray-500 hover:text-gray-700'
            }`}
          >
            <History className="w-4 h-4 inline mr-1" />
            时间历史
          </button>
          <button
            onClick={() => setSelectedTab('branches')}
            className={`pb-2 px-1 border-b-2 font-medium text-sm ${
              selectedTab === 'branches'
                ? 'border-blue-500 text-blue-600'
                : 'border-transparent text-gray-500 hover:text-gray-700'
            }`}
          >
            <GitBranch className="w-4 h-4 inline mr-1" />
            时间分支
          </button>
        </nav>
      </div>

      {/* 标签页内容 */}
      {selectedTab === 'control' && (
        <div className="space-y-6">
          {/* 播放控制 */}
          <div>
            <h3 className="text-sm font-medium text-gray-700 mb-3">模拟控制</h3>
            <div className="flex gap-2">
              <button
                onClick={handleManualTick}
                disabled={!timeControl.connected}
                className="flex-1 flex items-center justify-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                <RotateCw className="w-5 h-5" />
                手动推进
              </button>
              <button
                onClick={handleTimeFreeze}
                disabled={!timeControl.connected}
                className={`flex-1 flex items-center justify-center gap-2 px-4 py-2 rounded-lg ${
                  timeControl.isFrozen
                    ? 'bg-green-600 text-white hover:bg-green-700'
                    : 'bg-yellow-600 text-white hover:bg-yellow-700'
                } disabled:opacity-50 disabled:cursor-not-allowed`}
              >
                {timeControl.isFrozen ? (
                  <>
                    <Play className="w-5 h-5" />
                    解冻时间
                  </>
                ) : (
                  <>
                    <Pause className="w-5 h-5" />
                    冻结时间
                  </>
                )}
              </button>
            </div>
          </div>

          {/* 时间跳跃 */}
          <div>
            <h3 className="text-sm font-medium text-gray-700 mb-3">时间跳跃</h3>
            <div className="space-y-3">
              <div className="flex gap-2">
                <input
                  type="number"
                  value={jumpMinutes}
                  onChange={(e) => setJumpMinutes(parseInt(e.target.value) || 60)}
                  className="flex-1 px-3 py-2 border border-gray-300 rounded-lg text-center"
                  placeholder="分钟数"
                />
                <span className="flex items-center px-3 py-2 bg-gray-100 rounded-lg text-gray-600">
                  分钟
                </span>
              </div>
              <div className="flex gap-2">
                <button
                  onClick={handleForwardJump}
                  disabled={!timeControl.connected}
                  className="flex-1 flex items-center justify-center gap-2 px-4 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  <FastForward className="w-5 h-5" />
                  前进
                </button>
                <button
                  onClick={handleBackwardJump}
                  disabled={!timeControl.connected}
                  className="flex-1 flex items-center justify-center gap-2 px-4 py-2 bg-purple-600 text-white rounded-lg hover:bg-purple-700 disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  <Rewind className="w-5 h-5" />
                  后退
                </button>
              </div>
            </div>
          </div>

          {/* 时间流速控制 */}
          <div>
            <h3 className="text-sm font-medium text-gray-700 mb-3">时间流速: {timeControl.timeScale?.toFixed(1)}x</h3>
            <div className="space-y-2">
              <input
                type="range"
                min="0.1"
                max="10"
                step="0.1"
                value={timeControl.timeScale || 1.0}
                onChange={(e) => handleTimeScaleChange(parseFloat(e.target.value))}
                disabled={!timeControl.connected}
                className="w-full"
              />
              <div className="flex justify-between text-xs text-gray-500">
                <span>0.1x</span>
                <span>1.0x</span>
                <span>5.0x</span>
                <span>10.0x</span>
              </div>
            </div>
          </div>

          {/* 时间记录 */}
          <div>
            <h3 className="text-sm font-medium text-gray-700 mb-3">记录时间点</h3>
            <div className="flex gap-2">
              <input
                type="text"
                value={noteInput}
                onChange={(e) => setNoteInput(e.target.value)}
                placeholder="输入备注信息..."
                className="flex-1 px-3 py-2 border border-gray-300 rounded-lg"
                onKeyPress={(e) => e.key === 'Enter' && handleRecordTimePoint()}
              />
              <button
                onClick={handleRecordTimePoint}
                disabled={!noteInput.trim() || !timeControl.connected}
                className="flex items-center gap-2 px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                <Save className="w-5 h-5" />
                记录
              </button>
            </div>
          </div>
        </div>
      )}

      {selectedTab === 'history' && (
        <div className="space-y-4">
          {timeHistory.loading ? (
            <div className="text-center py-4 text-gray-500">加载时间历史...</div>
          ) : timeHistory.history && timeHistory.history.time_points.length > 0 ? (
            <div className="max-h-64 overflow-y-auto space-y-2">
              {timeHistory.history.time_points.map((point, index) => (
                <div key={index} className="flex items-start gap-3 p-3 bg-gray-50 rounded-lg">
                  <div className="flex-1">
                    <div className="font-medium text-gray-800">{point.note || '无备注'}</div>
                    <div className="text-sm text-gray-500">
                      {new Date(point.time).toLocaleString('zh-CN')} · {point.day_phase} · {point.season}
                    </div>
                  </div>
                  <div className="text-xs text-gray-400">Tick #{point.tick_count}</div>
                </div>
              ))}
            </div>
          ) : (
            <div className="text-center py-8 text-gray-500">
              暂无时间历史记录
            </div>
          )}
        </div>
      )}

      {selectedTab === 'branches' && (
        <div className="space-y-4">
          {timeHistory.loading ? (
            <div className="text-center py-4 text-gray-500">加载时间分支...</div>
          ) : timeHistory.history && timeHistory.history.branches.length > 0 ? (
            <div className="space-y-2">
              {timeHistory.history.branches.map((branch, index) => (
                <div key={index} className="flex items-start gap-3 p-3 bg-gray-50 rounded-lg">
                  <GitBranch className="w-5 h-5 text-purple-600 mt-0.5" />
                  <div className="flex-1">
                    <div className="font-medium text-gray-800">{branch.name}</div>
                    <div className="text-sm text-gray-500">
                      {new Date(branch.time).toLocaleString('zh-CN')} · {branch.scheduled_events_count} 个定时事件
                    </div>
                  </div>
                  <div className="text-xs text-gray-400">Tick #{branch.tick_count}</div>
                </div>
              ))}
            </div>
          ) : (
            <div className="text-center py-8 text-gray-500">
              暂无时间分支
            </div>
          )}
        </div>
      )}

      {/* 连接信息 */}
      {timeControl.connected && timeControl.tickCount !== null && (
        <div className="pt-4 border-t border-gray-200">
          <div className="flex justify-between text-sm text-gray-600">
            <span>时钟周期: {timeControl.tickCount}</span>
            <span>时间流速: {timeControl.timeScale?.toFixed(1)}x</span>
          </div>
        </div>
      )}
    </div>
  )
}