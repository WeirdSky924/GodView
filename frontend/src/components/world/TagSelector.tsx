/**
 * 多维度标签选择器组件
 * 支持多选、分组展示、搜索过滤
 */

import React, { useState } from 'react'
import { ChevronDown, ChevronUp, Check, Search, X } from 'lucide-react'
import {
  TAG_CATEGORIES,
  type TagOption,
  type TagCategory,
} from '@/constants/worldTags'

interface TagSelectorProps {
  selectedTags: Record<string, string[]>
  onTagsChange: (tags: Record<string, string[]>) => void
  categories?: string[]
  className?: string
}

// 颜色映射到 Tailwind 类
const colorClassMap: Record<string, { bg: string; text: string; border: string }> = {
  purple: { bg: 'bg-purple-100', text: 'text-purple-700', border: 'border-purple-200' },
  indigo: { bg: 'bg-indigo-100', text: 'text-indigo-700', border: 'border-indigo-200' },
  gray: { bg: 'bg-gray-100', text: 'text-gray-700', border: 'border-gray-200' },
  blue: { bg: 'bg-blue-100', text: 'text-blue-700', border: 'border-blue-200' },
  cyan: { bg: 'bg-cyan-100', text: 'text-cyan-700', border: 'border-cyan-200' },
  amber: { bg: 'bg-amber-100', text: 'text-amber-700', border: 'border-amber-200' },
  violet: { bg: 'bg-violet-100', text: 'text-violet-700', border: 'border-violet-200' },
  gold: { bg: 'bg-yellow-100', text: 'text-yellow-700', border: 'border-yellow-200' },
  slate: { bg: 'bg-slate-100', text: 'text-slate-700', border: 'border-slate-200' },
  yellow: { bg: 'bg-yellow-100', text: 'text-yellow-700', border: 'border-yellow-200' },
  pink: { bg: 'bg-pink-100', text: 'text-pink-700', border: 'border-pink-200' },
  red: { bg: 'bg-red-100', text: 'text-red-700', border: 'border-red-200' },
  rose: { bg: 'bg-rose-100', text: 'text-rose-700', border: 'border-rose-200' },
  orange: { bg: 'bg-orange-100', text: 'text-orange-700', border: 'border-orange-200' },
  teal: { bg: 'bg-teal-100', text: 'text-teal-700', border: 'border-teal-200' },
  green: { bg: 'bg-green-100', text: 'text-green-700', border: 'border-green-200' },
  emerald: { bg: 'bg-emerald-100', text: 'text-emerald-700', border: 'border-emerald-200' },
  sky: { bg: 'bg-sky-100', text: 'text-sky-700', border: 'border-sky-200' },
  navy: { bg: 'bg-slate-200', text: 'text-slate-800', border: 'border-slate-300' },
  stone: { bg: 'bg-stone-100', text: 'text-stone-700', border: 'border-stone-200' },
  zinc: { bg: 'bg-zinc-200', text: 'text-zinc-800', border: 'border-zinc-300' },
  fuchsia: { bg: 'bg-fuchsia-100', text: 'text-fuchsia-700', border: 'border-fuchsia-200' },
  neutral: { bg: 'bg-neutral-200', text: 'text-neutral-800', border: 'border-neutral-300' },
  dark: { bg: 'bg-gray-800', text: 'text-gray-100', border: 'border-gray-700' },
}

export default function TagSelector({
  selectedTags,
  onTagsChange,
  categories,
  className = '',
}: TagSelectorProps) {
  const [expandedGroups, setExpandedGroups] = useState<Set<string>>(
    new Set(TAG_CATEGORIES.map(c => c.key))
  )
  const [searchQuery, setSearchQuery] = useState('')

  // 过滤要显示的分类
  const displayCategories = categories
    ? TAG_CATEGORIES.filter(c => categories.includes(c.key))
    : TAG_CATEGORIES

  const toggleTag = (categoryKey: string, tagValue: string, multiSelect: boolean) => {
    const currentSelected = selectedTags[categoryKey] || []

    if (multiSelect) {
      // 多选模式
      const newSelected = currentSelected.includes(tagValue)
        ? currentSelected.filter(v => v !== tagValue)
        : [...currentSelected, tagValue]
      onTagsChange({
        ...selectedTags,
        [categoryKey]: newSelected,
      })
    } else {
      // 单选模式 - 点击已选中的标签取消选择，否则选择新标签
      const newSelected = currentSelected.includes(tagValue) ? [] : [tagValue]
      onTagsChange({
        ...selectedTags,
        [categoryKey]: newSelected,
      })
    }
  }

  const toggleGroup = (key: string) => {
    const newExpanded = new Set(expandedGroups)
    if (newExpanded.has(key)) {
      newExpanded.delete(key)
    } else {
      newExpanded.add(key)
    }
    setExpandedGroups(newExpanded)
  }

  const getSelectedCount = (categoryKey: string) => {
    return (selectedTags[categoryKey] || []).length
  }

  const filteredCategories = displayCategories.map(category => ({
    ...category,
    tags: searchQuery
      ? category.tags.filter(
          t =>
            t.label.toLowerCase().includes(searchQuery.toLowerCase()) ||
            t.description.toLowerCase().includes(searchQuery.toLowerCase())
        )
      : category.tags,
  })).filter(c => c.tags.length > 0 || !searchQuery)

  return (
    <div className={`space-y-4 ${className}`}>
      {/* 搜索框 */}
      <div className="relative">
        <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400 w-4 h-4" />
        <input
          type="text"
          value={searchQuery}
          onChange={e => setSearchQuery(e.target.value)}
          placeholder="搜索标签..."
          className="w-full pl-9 pr-4 py-2 text-sm border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
        />
        {searchQuery && (
          <button
            onClick={() => setSearchQuery('')}
            className="absolute right-3 top-1/2 transform -translate-y-1/2 text-gray-400 hover:text-gray-600"
          >
            <X className="w-4 h-4" />
          </button>
        )}
      </div>

      {/* 标签分组 */}
      {filteredCategories.map(category => {
        const selectedCount = getSelectedCount(category.key)
        const isExpanded = expandedGroups.has(category.key)
        const isMaxReached = category.maxSelect && selectedCount >= category.maxSelect
        const currentSelected = selectedTags[category.key] || []

        return (
          <div key={category.key} className="border border-gray-200 rounded-lg overflow-hidden">
            {/* 分组标题 */}
            <button
              type="button"
              onClick={() => toggleGroup(category.key)}
              className="w-full px-4 py-3 flex items-center justify-between bg-gray-50 hover:bg-gray-100 transition-colors"
            >
              <div className="flex items-center gap-3">
                <span className="font-medium text-gray-800">{category.label}</span>
                {selectedCount > 0 && (
                  <span className="px-2 py-0.5 text-xs bg-blue-100 text-blue-700 rounded-full">
                    {selectedCount}
                    {category.maxSelect && `/${category.maxSelect}`}
                  </span>
                )}
              </div>
              <div className="flex items-center gap-2 text-gray-500">
                <span className="text-xs">{category.description}</span>
                {isExpanded ? (
                  <ChevronUp className="w-4 h-4" />
                ) : (
                  <ChevronDown className="w-4 h-4" />
                )}
              </div>
            </button>

            {/* 标签列表 */}
            {isExpanded && (
              <div className="p-3 bg-white">
                {category.tags.length === 0 ? (
                  <p className="text-sm text-gray-500 text-center py-2">没有匹配的标签</p>
                ) : (
                  <div className="flex flex-wrap gap-2">
                    {category.tags.map(tag => {
                      const isSelected = currentSelected.includes(tag.value)
                      const colorClasses = colorClassMap[tag.color] || colorClassMap.gray
                      const isDisabled = !isSelected && isMaxReached

                      return (
                        <button
                          key={tag.value}
                          type="button"
                          onClick={() => toggleTag(category.key, tag.value, category.multiSelect)}
                          disabled={isDisabled}
                          title={tag.description}
                          className={`
                            relative px-3 py-1.5 rounded-full text-sm transition-all
                            ${isSelected
                              ? `${colorClasses.bg} ${colorClasses.text} ${colorClasses.border} border font-medium`
                              : 'border border-gray-200 hover:border-gray-300 bg-white text-gray-700'}
                            ${isDisabled ? 'opacity-50 cursor-not-allowed' : 'cursor-pointer'}
                          `}
                        >
                          <span className="flex items-center gap-1.5">
                            {tag.label}
                            {isSelected && <Check className="w-3.5 h-3.5" />}
                          </span>
                        </button>
                      )
                    })}
                  </div>
                )}
              </div>
            )}
          </div>
        )
      })}

      {/* 已选标签摘要 */}
      {Object.values(selectedTags).flat().length > 0 && (
        <div className="p-3 bg-blue-50 rounded-lg border border-blue-100">
          <h4 className="text-sm font-medium text-blue-800 mb-2">
            已选择 {Object.values(selectedTags).flat().length} 个标签
          </h4>
          <div className="flex flex-wrap gap-1.5">
            {displayCategories.map(category => {
              const selected = selectedTags[category.key] || []
              return selected.map(value => {
                const tag = category.tags.find(t => t.value === value)
                if (!tag) return null
                const colorClasses = colorClassMap[tag.color] || colorClassMap.blue

                return (
                  <span
                    key={`${category.key}-${value}`}
                    className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs ${colorClasses.bg} ${colorClasses.text} border ${colorClasses.border}`}
                  >
                    {tag.label}
                    <button
                      type="button"
                      onClick={e => {
                        e.stopPropagation()
                        toggleTag(category.key, value, category.multiSelect)
                      }}
                      className="hover:text-red-500 transition-colors"
                    >
                      <X className="w-3 h-3" />
                    </button>
                  </span>
                )
              })
            })}
          </div>
        </div>
      )}
    </div>
  )
}

// 标签徽章展示组件
export function TagBadges({
  tags,
  maxDisplay = 5,
  size = 'sm',
  className = '',
}: {
  tags: { category: string; value: string }[]
  maxDisplay?: number
  size?: 'sm' | 'md'
  className?: string
}) {
  const displayTags = tags.slice(0, maxDisplay)
  const remainingCount = tags.length - maxDisplay

  const sizeClasses = {
    sm: 'text-xs px-2 py-0.5',
    md: 'text-sm px-3 py-1',
  }

  if (tags.length === 0) return null

  return (
    <div className={`flex flex-wrap gap-1.5 ${className}`}>
      {displayTags.map((tag, index) => {
        const category = TAG_CATEGORIES.find(c => c.key === tag.category)
        const tagInfo = category?.tags.find(t => t.value === tag.value)
        if (!tagInfo) return null

        const colorClasses = colorClassMap[tagInfo.color] || colorClassMap.blue

        return (
          <span
            key={`${tag.category}-${tag.value}-${index}`}
            className={`rounded-full border ${colorClasses.bg} ${colorClasses.text} ${colorClasses.border} ${sizeClasses[size]}`}
            title={tagInfo.description}
          >
            {tagInfo.label}
          </span>
        )
      })}
      {remainingCount > 0 && (
        <span className={`${sizeClasses[size]} rounded-full bg-gray-100 text-gray-500 border border-gray-200`}>
          +{remainingCount}
        </span>
      )}
    </div>
  )
}
