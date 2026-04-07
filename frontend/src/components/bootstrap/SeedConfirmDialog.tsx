/**
 * 结构化种子确认对话框
 * v4 功能：展示提取的种子数据，允许用户编辑确认
 */

import React, { useState } from 'react'
import { X, CheckCircle, Edit3, Globe, Users, MapPin, Sparkles } from 'lucide-react'
import type { SeedData } from '@/api/bootstrap'

interface SeedConfirmDialogProps {
  seedData: SeedData
  onConfirm: (seedData: SeedData) => void
  onCancel: () => void
}

export default function SeedConfirmDialog({ seedData, onConfirm, onCancel }: SeedConfirmDialogProps) {
  const [editMode, setEditMode] = useState(false)
  const [editedSeed, setEditedSeed] = useState<SeedData>(seedData)

  const handleConfirm = () => {
    onConfirm(editMode ? editedSeed : seedData)
  }

  const updateWorldSetting = (field: string, value: string) => {
    setEditedSeed({
      ...editedSeed,
      world_setting: {
        ...editedSeed.world_setting,
        [field]: value
      }
    })
  }

  const updateMainCharacters = (index: number, field: string, value: string) => {
    const newCharacters = [...(editedSeed.main_characters || [])]
    newCharacters[index] = {
      ...newCharacters[index],
      [field]: value
    }
    setEditedSeed({
      ...editedSeed,
      main_characters: newCharacters
    })
  }

  const updateRegions = (index: number, field: string, value: string) => {
    const newRegions = [...(editedSeed.regions || [])]
    newRegions[index] = {
      ...newRegions[index],
      [field]: value
    }
    setEditedSeed({
      ...editedSeed,
      regions: newRegions
    })
  }

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
      <div className="bg-white rounded-xl shadow-2xl w-full max-w-4xl max-h-[90vh] overflow-hidden flex flex-col">
        {/* 标题栏 */}
        <div className="px-6 py-4 border-b border-gray-200 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <Sparkles className="w-6 h-6 text-blue-600" />
            <h2 className="text-xl font-bold text-gray-800">确认结构化种子</h2>
          </div>
          <div className="flex items-center gap-3">
            <button
              onClick={() => setEditMode(!editMode)}
              className={`flex items-center gap-2 px-4 py-2 rounded-lg ${
                editMode
                  ? 'bg-blue-100 text-blue-700'
                  : 'border border-gray-300 text-gray-700 hover:bg-gray-50'
              }`}
            >
              <Edit3 className="w-4 h-4" />
              {editMode ? '编辑中' : '编辑'}
            </button>
            <button
              onClick={onCancel}
              className="p-2 hover:bg-gray-100 rounded-lg"
            >
              <X className="w-5 h-5 text-gray-500" />
            </button>
          </div>
        </div>

        {/* 内容区域 */}
        <div className="flex-1 overflow-y-auto p-6">
          <div className="space-y-6">
            {/* 世界设定 */}
            <div className="border border-gray-200 rounded-lg p-4">
              <div className="flex items-center gap-2 mb-4">
                <Globe className="w-5 h-5 text-blue-600" />
                <h3 className="font-bold text-gray-800">世界设定</h3>
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    世界名称
                  </label>
                  {editMode ? (
                    <input
                      type="text"
                      value={editedSeed.world_setting?.name || ''}
                      onChange={(e) => updateWorldSetting('name', e.target.value)}
                      className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                    />
                  ) : (
                    <div className="px-3 py-2 bg-gray-50 rounded-lg text-gray-800">
                      {seedData.world_setting?.name || '未命名世界'}
                    </div>
                  )}
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    世界类型
                  </label>
                  {editMode ? (
                    <select
                      value={editedSeed.world_setting?.world_type || 'fantasy'}
                      onChange={(e) => updateWorldSetting('world_type', e.target.value)}
                      className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                    >
                      <option value="fantasy">奇幻</option>
                      <option value="scifi">科幻</option>
                      <option value="modern">现代</option>
                      <option value="historical">历史</option>
                      <option value="wuxia">武侠</option>
                    </select>
                  ) : (
                    <div className="px-3 py-2 bg-gray-50 rounded-lg text-gray-800">
                      {getWorldTypeLabel(seedData.world_setting?.world_type)}
                    </div>
                  )}
                </div>
                <div className="col-span-2">
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    世界描述
                  </label>
                  {editMode ? (
                    <textarea
                      value={editedSeed.world_setting?.description || ''}
                      onChange={(e) => updateWorldSetting('description', e.target.value)}
                      className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 resize-none"
                      rows={3}
                    />
                  ) : (
                    <div className="px-3 py-2 bg-gray-50 rounded-lg text-gray-800 min-h-[80px]">
                      {seedData.world_setting?.description || '无描述'}
                    </div>
                  )}
                </div>
              </div>
            </div>

            {/* 主要角色 */}
            <div className="border border-gray-200 rounded-lg p-4">
              <div className="flex items-center gap-2 mb-4">
                <Users className="w-5 h-5 text-green-600" />
                <h3 className="font-bold text-gray-800">主要角色</h3>
                <span className="text-sm text-gray-500">
                  ({seedData.main_characters?.length || 0} 个)
                </span>
              </div>
              {seedData.main_characters && seedData.main_characters.length > 0 ? (
                <div className="space-y-4">
                  {seedData.main_characters.map((char, idx) => (
                    <div key={idx} className="bg-gray-50 rounded-lg p-3">
                      {editMode ? (
                        <div className="grid grid-cols-2 gap-3">
                          <input
                            type="text"
                            value={editedSeed.main_characters?.[idx]?.name || ''}
                            onChange={(e) => updateMainCharacters(idx, 'name', e.target.value)}
                            placeholder="角色名称"
                            className="px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                          />
                          <input
                            type="text"
                            value={editedSeed.main_characters?.[idx]?.role || ''}
                            onChange={(e) => updateMainCharacters(idx, 'role', e.target.value)}
                            placeholder="角色定位"
                            className="px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                          />
                          <textarea
                            value={editedSeed.main_characters?.[idx]?.description || ''}
                            onChange={(e) => updateMainCharacters(idx, 'description', e.target.value)}
                            placeholder="角色描述"
                            className="col-span-2 px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 resize-none"
                            rows={2}
                          />
                        </div>
                      ) : (
                        <>
                          <div className="font-medium text-gray-800">{char.name}</div>
                          <div className="text-sm text-gray-600 mt-1">{char.role || '未设定角色'}</div>
                          {char.description && (
                            <div className="text-sm text-gray-500 mt-2">{char.description}</div>
                          )}
                        </>
                      )}
                    </div>
                  ))}
                </div>
              ) : (
                <div className="text-center py-4 text-gray-500">
                  暂无主要角色
                </div>
              )}
            </div>

            {/* 区域 */}
            <div className="border border-gray-200 rounded-lg p-4">
              <div className="flex items-center gap-2 mb-4">
                <MapPin className="w-5 h-5 text-purple-600" />
                <h3 className="font-bold text-gray-800">区域</h3>
                <span className="text-sm text-gray-500">
                  ({seedData.regions?.length || 0} 个)
                </span>
              </div>
              {seedData.regions && seedData.regions.length > 0 ? (
                <div className="grid grid-cols-2 gap-3">
                  {seedData.regions.map((region, idx) => (
                    <div key={idx} className="bg-gray-50 rounded-lg p-3">
                      {editMode ? (
                        <div className="space-y-2">
                          <input
                            type="text"
                            value={editedSeed.regions?.[idx]?.name || ''}
                            onChange={(e) => updateRegions(idx, 'name', e.target.value)}
                            placeholder="区域名称"
                            className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                          />
                          <input
                            type="text"
                            value={editedSeed.regions?.[idx]?.description || ''}
                            onChange={(e) => updateRegions(idx, 'description', e.target.value)}
                            placeholder="区域描述"
                            className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                          />
                        </div>
                      ) : (
                        <>
                          <div className="font-medium text-gray-800">{region.name}</div>
                          {region.description && (
                            <div className="text-sm text-gray-500 mt-1">{region.description}</div>
                          )}
                        </>
                      )}
                    </div>
                  ))}
                </div>
              ) : (
                <div className="text-center py-4 text-gray-500">
                  暂无区域
                </div>
              )}
            </div>

            {/* 其他信息 */}
            <div className="grid grid-cols-2 gap-4">
              <div className="border border-gray-200 rounded-lg p-4">
                <h4 className="font-medium text-gray-700 mb-2">力量体系</h4>
                <div className="text-gray-800">
                  {seedData.power_system || '未设定'}
                </div>
              </div>
              <div className="border border-gray-200 rounded-lg p-4">
                <h4 className="font-medium text-gray-700 mb-2">技术水平</h4>
                <div className="text-gray-800">
                  {seedData.technology_level || '未设定'}
                </div>
              </div>
              <div className="border border-gray-200 rounded-lg p-4">
                <h4 className="font-medium text-gray-700 mb-2">叙事基调</h4>
                <div className="text-gray-800">
                  {seedData.narrative_tone || '未设定'}
                </div>
              </div>
              <div className="border border-gray-200 rounded-lg p-4">
                <h4 className="font-medium text-gray-700 mb-2">写作风格</h4>
                <div className="text-gray-800">
                  {seedData.writing_style || '未设定'}
                </div>
              </div>
            </div>

            {/* 剧情钩子 */}
            {seedData.plot_hooks && seedData.plot_hooks.length > 0 && (
              <div className="border border-gray-200 rounded-lg p-4">
                <h3 className="font-bold text-gray-800 mb-4">剧情钩子</h3>
                <div className="space-y-2">
                  {seedData.plot_hooks.map((hook, idx) => (
                    <div key={idx} className="flex items-start gap-2">
                      <CheckCircle className="w-4 h-4 text-green-500 mt-0.5 flex-shrink-0" />
                      <span className="text-gray-700">{hook.title || hook.description || JSON.stringify(hook)}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
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
            onClick={handleConfirm}
            className="px-8 py-2 bg-green-600 text-white font-medium rounded-lg hover:bg-green-700"
          >
            确认并继续
          </button>
        </div>
      </div>
    </div>
  )
}

function getWorldTypeLabel(type?: string): string {
  const labels: Record<string, string> = {
    fantasy: '奇幻',
    scifi: '科幻',
    modern: '现代',
    historical: '历史',
    wuxia: '武侠',
  }
  return labels[type || 'fantasy'] || type || '奇幻'
}