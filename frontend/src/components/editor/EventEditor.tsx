/**
 * 事件编辑器组件
 * v5.2 功能：创建和编辑自定义事件模板
 */

import React, { useState } from 'react'
import { X, Save, Trash2, Plus, Search, Filter, Calendar, MapPin, Users, Zap, AlertCircle, Star, MessageSquare, Sword } from 'lucide-react'

interface EventTemplate {
  id: string
  name: string
  event_type: string
  description: string
  trigger_conditions: TriggerCondition[]
  effects: EventEffect[]
  parameters: Record<string, any>
  created_at?: string
  updated_at?: string
}

interface TriggerCondition {
  type: string
  field: string
  operator: string
  value: any
}

interface EventEffect {
  type: string
  target: string
  value: any
  duration?: number
}

interface EventEditorProps {
  template?: EventTemplate
  onSave: (template: EventTemplate) => void
  onCancel: () => void
  onDelete?: (templateId: string) => void
  worldId: string
}

const EVENT_TYPES = [
  { value: 'social', label: '社交事件', icon: '💬' },
  { value: 'combat', label: '战斗事件', icon: '⚔️' },
  { value: 'discovery', label: '发现事件', icon: '🔍' },
  { value: 'weather', label: '天气事件', icon: '🌤️' },
  { value: 'milestone', label: '里程碑', icon: '🎯' },
  { value: 'hazard', label: '危险事件', icon: '⚠️' },
]

export default function EventEditor({ template, onSave, onCancel, onDelete, worldId }: EventEditorProps) {
  const [eventData, setEventData] = useState<EventTemplate>(
    template || {
      id: `event_${Date.now()}`,
      name: '',
      event_type: 'social',
      description: '',
      trigger_conditions: [],
      effects: [],
      parameters: {
        location: '',
        characters: [],
        duration: 0,
        severity: 'medium',
      }
    }
  )

  const [activeTab, setActiveTab] = useState<'basic' | 'trigger' | 'effects'>('basic')
  const [saving, setSaving] = useState(false)

  const handleChange = (field: string, value: any) => {
    setEventData(prev => ({
      ...prev,
      [field]: value
    }))
  }

  const handleParameterChange = (param: string, value: any) => {
    setEventData(prev => ({
      ...prev,
      parameters: {
        ...prev.parameters,
        [param]: value
      }
    }))
  }

  const handleAddTrigger = () => {
    setEventData(prev => ({
      ...prev,
      trigger_conditions: [
        ...prev.trigger_conditions,
        { type: 'character', field: 'location', operator: 'eq', value: '' }
      ]
    }))
  }

  const handleRemoveTrigger = (index: number) => {
    setEventData(prev => ({
      ...prev,
      trigger_conditions: prev.trigger_conditions.filter((_, i) => i !== index)
    }))
  }

  const handleTriggerChange = (index: number, field: string, value: any) => {
    setEventData(prev => ({
      ...prev,
      trigger_conditions: prev.trigger_conditions.map((cond, i) =>
        i === index ? { ...cond, [field]: value } : cond
      )
    }))
  }

  const handleAddEffect = () => {
    setEventData(prev => ({
      ...prev,
      effects: [
        ...prev.effects,
        { type: 'modify_attribute', target: '', value: 0 }
      ]
    }))
  }

  const handleRemoveEffect = (index: number) => {
    setEventData(prev => ({
      ...prev,
      effects: prev.effects.filter((_, i) => i !== index)
    }))
  }

  const handleEffectChange = (index: number, field: string, value: any) => {
    setEventData(prev => ({
      ...prev,
      effects: prev.effects.map((effect, i) =>
        i === index ? { ...effect, [field]: value } : effect
      )
    }))
  }

  const handleSave = async () => {
    if (!eventData.name.trim()) {
      alert('请输入事件名称')
      return
    }

    setSaving(true)
    try {
      await onSave(eventData)
    } finally {
      setSaving(false)
    }
  }

  const getEventTypeInfo = (type: string) => {
    return EVENT_TYPES.find(t => t.value === type) || EVENT_TYPES[0]
  }

  return (
    <div className="h-full flex flex-col bg-white">
      {/* 标题栏 */}
      <div className="px-6 py-4 border-b border-gray-200 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="text-2xl">{getEventTypeInfo(eventData.event_type).icon}</div>
          <h2 className="text-xl font-bold text-gray-800">
            {template ? '编辑事件模板' : '创建事件模板'}
          </h2>
        </div>
        <div className="flex items-center gap-2">
          {onDelete && template && (
            <button
              onClick={() => onDelete(eventData.id)}
              className="p-2 text-red-600 hover:bg-red-50 rounded-lg"
            >
              <Trash2 className="w-5 h-5" />
            </button>
          )}
          <button
            onClick={onCancel}
            className="p-2 text-gray-500 hover:bg-gray-100 rounded-lg"
          >
            <X className="w-5 h-5" />
          </button>
        </div>
      </div>

      {/* 标签页导航 */}
      <div className="border-b border-gray-200">
        <nav className="flex">
          <button
            onClick={() => setActiveTab('basic')}
            className={`py-3 px-6 text-sm font-medium ${
              activeTab === 'basic'
                ? 'text-blue-600 border-b-2 border-blue-600'
                : 'text-gray-500 hover:text-gray-700'
            }`}
          >
            基本信息
          </button>
          <button
            onClick={() => setActiveTab('trigger')}
            className={`py-3 px-6 text-sm font-medium ${
              activeTab === 'trigger'
                ? 'text-blue-600 border-b-2 border-blue-600'
                : 'text-gray-500 hover:text-gray-700'
            }`}
          >
            触发条件
            {eventData.trigger_conditions.length > 0 && (
              <span className="ml-2 px-2 py-0.5 text-xs bg-blue-100 text-blue-700 rounded-full">
                {eventData.trigger_conditions.length}
              </span>
            )}
          </button>
          <button
            onClick={() => setActiveTab('effects')}
            className={`py-3 px-6 text-sm font-medium ${
              activeTab === 'effects'
                ? 'text-blue-600 border-b-2 border-blue-600'
                : 'text-gray-500 hover:text-gray-700'
            }`}
          >
            事件效果
            {eventData.effects.length > 0 && (
              <span className="ml-2 px-2 py-0.5 text-xs bg-blue-100 text-blue-700 rounded-full">
                {eventData.effects.length}
              </span>
            )}
          </button>
        </nav>
      </div>

      {/* 内容区域 */}
      <div className="flex-1 overflow-y-auto p-6">
        {activeTab === 'basic' && (
          <div className="space-y-6">
            {/* 事件名称 */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                事件名称 *
              </label>
              <input
                type="text"
                value={eventData.name}
                onChange={(e) => handleChange('name', e.target.value)}
                className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                placeholder="例如：突然的袭击"
              />
            </div>

            {/* 事件类型 */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                事件类型
              </label>
              <div className="grid grid-cols-3 gap-3">
                {EVENT_TYPES.map(type => (
                  <button
                    key={type.value}
                    onClick={() => handleChange('event_type', type.value)}
                    className={`p-3 border rounded-lg text-left transition-all ${
                      eventData.event_type === type.value
                        ? 'border-blue-500 bg-blue-50'
                        : 'border-gray-200 hover:border-gray-300'
                    }`}
                  >
                    <div className="text-lg mb-1">{type.icon}</div>
                    <div className="text-sm font-medium text-gray-800">{type.label}</div>
                  </button>
                ))}
              </div>
            </div>

            {/* 事件描述 */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                事件描述
              </label>
              <textarea
                value={eventData.description}
                onChange={(e) => handleChange('description', e.target.value)}
                className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 resize-none"
                rows={4}
                placeholder="描述这个事件的背景和内容..."
              />
            </div>

            {/* 参数设置 */}
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  地点
                </label>
                <input
                  type="text"
                  value={eventData.parameters.location || ''}
                  onChange={(e) => handleParameterChange('location', e.target.value)}
                  className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                  placeholder="事件发生地点"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  严重程度
                </label>
                <select
                  value={eventData.parameters.severity || 'medium'}
                  onChange={(e) => handleParameterChange('severity', e.target.value)}
                  className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                >
                  <option value="low">低</option>
                  <option value="medium">中</option>
                  <option value="high">高</option>
                  <option value="critical">严重</option>
                </select>
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  持续时间（小时）
                </label>
                <input
                  type="number"
                  value={eventData.parameters.duration || 0}
                  onChange={(e) => handleParameterChange('duration', parseInt(e.target.value))}
                  className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                  min="0"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  涉及角色数
                </label>
                <input
                  type="number"
                  value={eventData.parameters.character_count || 0}
                  onChange={(e) => handleParameterChange('character_count', parseInt(e.target.value))}
                  className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                  min="0"
                  max="10"
                />
              </div>
            </div>
          </div>
        )}

        {activeTab === 'trigger' && (
          <div className="space-y-4">
            <div className="flex items-center justify-between mb-4">
              <h3 className="font-medium text-gray-800">触发条件</h3>
              <button
                onClick={handleAddTrigger}
                className="flex items-center gap-1 px-3 py-1 text-sm text-blue-600 hover:bg-blue-50 rounded"
              >
                <Plus className="w-4 h-4" />
                添加条件
              </button>
            </div>

            {eventData.trigger_conditions.length === 0 ? (
              <div className="text-center py-8 text-gray-500">
                <Filter className="w-12 h-12 mx-auto mb-3 text-gray-300" />
                <p>暂无触发条件</p>
                <p className="text-sm">点击"添加条件"创建触发规则</p>
              </div>
            ) : (
              <div className="space-y-3">
                {eventData.trigger_conditions.map((condition, index) => (
                  <div key={index} className="p-4 bg-gray-50 rounded-lg border border-gray-200">
                    <div className="flex items-center justify-between mb-3">
                      <span className="text-sm font-medium text-gray-700">条件 {index + 1}</span>
                      <button
                        onClick={() => handleRemoveTrigger(index)}
                        className="text-red-500 hover:text-red-700"
                      >
                        <Trash2 className="w-4 h-4" />
                      </button>
                    </div>
                    <div className="grid grid-cols-4 gap-3">
                      <div>
                        <label className="block text-xs text-gray-500 mb-1">条件类型</label>
                        <select
                          value={condition.type}
                          onChange={(e) => handleTriggerChange(index, 'type', e.target.value)}
                          className="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg"
                        >
                          <option value="character">角色状态</option>
                          <option value="location">位置条件</option>
                          <option value="time">时间条件</option>
                          <option value="relationship">关系条件</option>
                        </select>
                      </div>
                      <div>
                        <label className="block text-xs text-gray-500 mb-1">字段</label>
                        <input
                          type="text"
                          value={condition.field}
                          onChange={(e) => handleTriggerChange(index, 'field', e.target.value)}
                          className="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg"
                          placeholder="字段名"
                        />
                      </div>
                      <div>
                        <label className="block text-xs text-gray-500 mb-1">操作符</label>
                        <select
                          value={condition.operator}
                          onChange={(e) => handleTriggerChange(index, 'operator', e.target.value)}
                          className="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg"
                        >
                          <option value="eq">等于</option>
                          <option value="ne">不等于</option>
                          <option value="gt">大于</option>
                          <option value="lt">小于</option>
                          <option value="contains">包含</option>
                        </select>
                      </div>
                      <div>
                        <label className="block text-xs text-gray-500 mb-1">值</label>
                        <input
                          type="text"
                          value={condition.value}
                          onChange={(e) => handleTriggerChange(index, 'value', e.target.value)}
                          className="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg"
                          placeholder="值"
                        />
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {activeTab === 'effects' && (
          <div className="space-y-4">
            <div className="flex items-center justify-between mb-4">
              <h3 className="font-medium text-gray-800">事件效果</h3>
              <button
                onClick={handleAddEffect}
                className="flex items-center gap-1 px-3 py-1 text-sm text-blue-600 hover:bg-blue-50 rounded"
              >
                <Plus className="w-4 h-4" />
                添加效果
              </button>
            </div>

            {eventData.effects.length === 0 ? (
              <div className="text-center py-8 text-gray-500">
                <Zap className="w-12 h-12 mx-auto mb-3 text-gray-300" />
                <p>暂无事件效果</p>
                <p className="text-sm">点击"添加效果"定义事件的影响</p>
              </div>
            ) : (
              <div className="space-y-3">
                {eventData.effects.map((effect, index) => (
                  <div key={index} className="p-4 bg-gray-50 rounded-lg border border-gray-200">
                    <div className="flex items-center justify-between mb-3">
                      <span className="text-sm font-medium text-gray-700">效果 {index + 1}</span>
                      <button
                        onClick={() => handleRemoveEffect(index)}
                        className="text-red-500 hover:text-red-700"
                      >
                        <Trash2 className="w-4 h-4" />
                      </button>
                    </div>
                    <div className="grid grid-cols-3 gap-3">
                      <div>
                        <label className="block text-xs text-gray-500 mb-1">效果类型</label>
                        <select
                          value={effect.type}
                          onChange={(e) => handleEffectChange(index, 'type', e.target.value)}
                          className="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg"
                        >
                          <option value="modify_attribute">修改属性</option>
                          <option value="change_relationship">改变关系</option>
                          <option value="trigger_event">触发事件</option>
                          <option value="modify_inventory">修改物品</option>
                          <option value="change_location">改变位置</option>
                        </select>
                      </div>
                      <div>
                        <label className="block text-xs text-gray-500 mb-1">目标</label>
                        <input
                          type="text"
                          value={effect.target || ''}
                          onChange={(e) => handleEffectChange(index, 'target', e.target.value)}
                          className="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg"
                          placeholder="目标ID"
                        />
                      </div>
                      <div>
                        <label className="block text-xs text-gray-500 mb-1">值/参数</label>
                        <input
                          type="text"
                          value={effect.value}
                          onChange={(e) => handleEffectChange(index, 'value', e.target.value)}
                          className="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg"
                          placeholder="值"
                        />
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
      </div>

      {/* 底部按钮 */}
      <div className="px-6 py-4 border-t border-gray-200 flex justify-end gap-3">
        <button
          onClick={onCancel}
          className="px-6 py-2 border border-gray-300 text-gray-700 font-medium rounded-lg hover:bg-gray-50"
        >
          取消
        </button>
        <button
          onClick={handleSave}
          disabled={saving || !eventData.name.trim()}
          className="flex items-center gap-2 px-8 py-2 bg-blue-600 text-white font-medium rounded-lg hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed"
        >
          <Save className="w-4 h-4" />
          {saving ? '保存中...' : '保存'}
        </button>
      </div>
    </div>
  )
}