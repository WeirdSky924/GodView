/**
 * 工作流帮助组件
 * 显示工作流节点使用指南
 */

import { useState } from 'react'
import { useTheme } from '@/contexts/ThemeContext'
import { Modal } from '@/components/ui'
import {
  HelpCircle,
  Play,
  Square,
  GitBranch,
  Layers,
  MessageSquare,
  PenTool,
  BookOpen,
  Search,
  Link,
  Settings,
  Dices,
  Map,
  Users,
  MessageCircle,
  ChevronDown,
  ChevronRight,
  X,
} from 'lucide-react'

interface HelpSection {
  id: string
  title: string
  icon?: React.ReactNode
  content: React.ReactNode
  subsections?: HelpSection[]
}

export default function WorkflowHelp() {
  const { theme } = useTheme()
  const isDark = theme === 'dark'
  const [isOpen, setIsOpen] = useState(false)
  const [expandedSections, setExpandedSections] = useState<Set<string>>(new Set(['quick-start']))

  const toggleSection = (id: string) => {
    setExpandedSections((prev) => {
      const next = new Set(prev)
      if (next.has(id)) {
        next.delete(id)
      } else {
        next.add(id)
      }
      return next
    })
  }

  const Section = ({ section, level = 0 }: { section: HelpSection; level?: number }) => {
    const isExpanded = expandedSections.has(section.id)
    const hasSubsections = section.subsections && section.subsections.length > 0

    return (
      <div className={`${level > 0 ? 'ml-4' : ''}`}>
        <button
          onClick={() => toggleSection(section.id)}
          className={`w-full flex items-center gap-2 py-2 px-3 rounded-lg text-left transition-colors ${
            isExpanded
              ? isDark
                ? 'bg-blue-900/30 text-blue-300'
                : 'bg-blue-50 text-blue-700'
              : isDark
                ? 'hover:bg-gray-800 text-gray-300'
                : 'hover:bg-gray-50 text-gray-700'
          }`}
        >
          {hasSubsections && (
            <span className="w-4 h-4">
              {isExpanded ? <ChevronDown size={16} /> : <ChevronRight size={16} />}
            </span>
          )}
          {!hasSubsections && <span className="w-4" />}
          {section.icon}
          <span className="font-medium">{section.title}</span>
        </button>

        {isExpanded && (
          <div className={`mt-1 mb-2 ${hasSubsections ? '' : 'px-3 py-2'}`}>
            {section.content}
            {hasSubsections && section.subsections!.map((sub) => (
              <Section key={sub.id} section={sub} level={level + 1} />
            ))}
          </div>
        )}
      </div>
    )
  }

  const NodeCard = ({
    icon,
    name,
    color,
    description,
    usage,
  }: {
    icon: React.ReactNode
    name: string
    color: string
    description: string
    usage?: string
  }) => (
    <div
      className={`p-3 rounded-lg border ${
        isDark ? 'bg-gray-800 border-gray-700' : 'bg-white border-gray-200'
      }`}
    >
      <div className="flex items-center gap-2 mb-1">
        <span className={`w-6 h-6 flex items-center justify-center rounded bg-${color}-100 text-${color}-600`}>
          {icon}
        </span>
        <span className={`font-semibold ${isDark ? 'text-white' : 'text-gray-800'}`}>{name}</span>
      </div>
      <p className={`text-sm ${isDark ? 'text-gray-400' : 'text-gray-600'}`}>{description}</p>
      {usage && (
        <p className={`text-xs mt-1 ${isDark ? 'text-gray-500' : 'text-gray-400'}`}>用法：{usage}</p>
      )}
    </div>
  )

  const helpSections: HelpSection[] = [
    {
      id: 'quick-start',
      title: '快速入门',
      icon: <Play size={16} />,
      content: (
        <div className="space-y-3">
          <ol className={`list-decimal list-inside space-y-2 text-sm ${isDark ? 'text-gray-300' : 'text-gray-600'}`}>
            <li><strong>新建工作流</strong>：点击左侧「新建」按钮</li>
            <li><strong>添加节点</strong>：从左侧节点面板点击需要的节点</li>
            <li><strong>连接节点</strong>：在画布上从一个节点的连接点拖线到另一个节点</li>
            <li><strong>配置节点</strong>：选中节点后在右侧属性面板配置参数</li>
            <li><strong>保存工作流</strong>：点击顶部「保存」按钮</li>
          </ol>
          <div className={`p-3 rounded-lg ${isDark ? 'bg-yellow-900/30' : 'bg-yellow-50'}`}>
            <p className={`text-sm ${isDark ? 'text-yellow-300' : 'text-yellow-700'}`}>
              💡 提示：按 Delete 键可删除选中的节点或连线
            </p>
          </div>
        </div>
      ),
    },
    {
      id: 'control-nodes',
      title: '控制节点',
      icon: <Settings size={16} />,
      content: (
        <div className="space-y-3">
          <NodeCard
            icon={<Play size={14} />}
            name="开始"
            color="green"
            description="工作流入口点，每个工作流必须有且仅有一个"
          />
          <NodeCard
            icon={<Square size={14} />}
            name="结束"
            color="red"
            description="工作流出口点，执行到此节点时工作流完成"
          />
          <NodeCard
            icon={<GitBranch size={14} />}
            name="条件分支"
            color="amber"
            description="根据评估结果选择执行路径，支持重试循环"
            usage="连接两条出边：左侧 pass，右侧 retry"
          />
          <NodeCard
            icon={<Layers size={14} />}
            name="并行执行"
            color="purple"
            description="同时执行多个分支，所有分支完成后继续"
          />
          <NodeCard
            icon={<MessageSquare size={14} />}
            name="用户输入"
            color="blue"
            description="暂停工作流等待用户输入后继续"
          />
        </div>
      ),
      subsections: [
        {
          id: 'condition-detail',
          title: '条件分支详解',
          icon: <GitBranch size={14} />,
          content: (
            <div className="space-y-2 text-sm">
              <p className={isDark ? 'text-gray-300' : 'text-gray-600'}>
                条件分支节点是实现质量评估循环的核心：
              </p>
              <ol className={`list-decimal list-inside space-y-1 ${isDark ? 'text-gray-400' : 'text-gray-500'}`}>
                <li>从节点<strong>左侧</strong>拖线到「通过」目标</li>
                <li>从节点<strong>右侧</strong>拖线到「重试」目标</li>
                <li>选中连线，在右侧面板设置条件结果</li>
              </ol>
              <div className={`p-2 rounded mt-2 font-mono text-xs ${isDark ? 'bg-gray-900' : 'bg-gray-100'}`}>
                <pre>{`开始 → 作家 → 评估员 → 条件判断 → 结束
                    ↓ retry
                   作家 ←──重试循环──┘`}</pre>
              </div>
              <p className={`text-xs ${isDark ? 'text-gray-500' : 'text-gray-400'}`}>
                ⚠️ 重试最多 3 次，超过后自动通过
              </p>
            </div>
          ),
        },
      ],
    },
    {
      id: 'agent-nodes',
      title: 'Agent 节点',
      icon: <PenTool size={16} />,
      content: (
        <div className="space-y-3">
          <div className={`p-2 rounded text-sm ${isDark ? 'bg-gray-800' : 'bg-gray-50'}`}>
            <p className={isDark ? 'text-gray-300' : 'text-gray-600'}>
              Agent 是工作流的核心执行单元，每个 Agent 负责特定任务
            </p>
          </div>
          <div className="grid grid-cols-2 gap-2">
            <NodeCard icon={<GitBranch size={14} />} name="总编剧" color="purple" description="规划剧情大纲、章节结构" />
            <NodeCard icon={<PenTool size={14} />} name="作家" color="green" description="执行章节内容写作" />
            <NodeCard icon={<BookOpen size={14} />} name="摘要员" color="cyan" description="生成内容摘要" />
            <NodeCard icon={<Search size={14} />} name="评估员" color="red" description="评估内容质量" />
            <NodeCard icon={<Link size={14} />} name="伏笔管理员" color="orange" description="管理伏笔埋设回收" />
            <NodeCard icon={<Settings size={14} />} name="设定管理员" color="blue" description="维护世界观设定" />
            <NodeCard icon={<Dices size={14} />} name="事件生成器" color="pink" description="生成故事事件" />
            <NodeCard icon={<Map size={14} />} name="地图管理员" color="teal" description="管理地点空间" />
          </div>
        </div>
      ),
    },
    {
      id: 'interaction-nodes',
      title: '交互节点',
      icon: <Users size={16} />,
      content: (
        <div className="space-y-3">
          <NodeCard
            icon={<Users size={14} />}
            name="场景演绎"
            color="rose"
            description="多角色同台演绎场景，自动协调角色Agent"
            usage="在属性面板选择参与角色"
          />
          <div className={`p-2 rounded text-xs ${isDark ? 'bg-gray-800' : 'bg-gray-50'}`}>
            <p className={isDark ? 'text-gray-400' : 'text-gray-500'}>
              <strong>场景模式：</strong><br />
              • <strong>互动模式</strong>：角色之间有互动对话<br />
              • <strong>并行模式</strong>：各角色独立行动
            </p>
          </div>
          <NodeCard
            icon={<MessageCircle size={14} />}
            name="集体讨论"
            color="indigo"
            description="多个Agent进行创作会议讨论"
            usage="设置讨论主题和参与Agent"
          />
        </div>
      ),
    },
    {
      id: 'connections',
      title: '连线与条件',
      icon: <Link size={16} />,
      content: (
        <div className="space-y-3">
          <table className={`w-full text-sm ${isDark ? 'text-gray-300' : 'text-gray-600'}`}>
            <thead>
              <tr className={isDark ? 'border-gray-700' : 'border-gray-200'}>
                <th className="text-left py-1">连线类型</th>
                <th className="text-left py-1">颜色</th>
                <th className="text-left py-1">说明</th>
              </tr>
            </thead>
            <tbody>
              <tr><td>普通连线</td><td>灰色</td><td>默认流程</td></tr>
              <tr><td>通过连线</td><td className="text-green-500">绿色</td><td>评估通过时走</td></tr>
              <tr><td>重试连线</td><td className="text-red-500">红色</td><td>评估不通过时走</td></tr>
            </tbody>
          </table>
          <div className={`p-3 rounded-lg ${isDark ? 'bg-blue-900/30' : 'bg-blue-50'}`}>
            <p className={`text-sm ${isDark ? 'text-blue-300' : 'text-blue-700'}`}>
              📌 设置条件：选中连线 → 右侧面板 → 选择「条件结果」
            </p>
          </div>
        </div>
      ),
    },
    {
      id: 'examples',
      title: '典型示例',
      icon: <BookOpen size={16} />,
      content: (
        <div className="space-y-4">
          <div className={`p-3 rounded-lg ${isDark ? 'bg-gray-800' : 'bg-gray-50'}`}>
            <h4 className={`font-semibold mb-2 ${isDark ? 'text-white' : 'text-gray-800'}`}>
              示例 1：简单写作流程
            </h4>
            <div className={`font-mono text-xs ${isDark ? 'text-gray-400' : 'text-gray-500'}`}>
              开始 → 设定管理员 → 总编剧 → 作家 → 结束
            </div>
          </div>

          <div className={`p-3 rounded-lg ${isDark ? 'bg-gray-800' : 'bg-gray-50'}`}>
            <h4 className={`font-semibold mb-2 ${isDark ? 'text-white' : 'text-gray-800'}`}>
              示例 2：带评估循环
            </h4>
            <div className={`font-mono text-xs ${isDark ? 'text-gray-400' : 'text-gray-500'}`}>
              <pre>{`开始 → 作家 → 评估员 → 条件判断 → 结束
                      ↑_______↓ retry`}</pre>
            </div>
          </div>

          <div className={`p-3 rounded-lg ${isDark ? 'bg-gray-800' : 'bg-gray-50'}`}>
            <h4 className={`font-semibold mb-2 ${isDark ? 'text-white' : 'text-gray-800'}`}>
              示例 3：并行准备
            </h4>
            <div className={`font-mono text-xs ${isDark ? 'text-gray-400' : 'text-gray-500'}`}>
              <pre>{`         ┌→ 设定管理员 ┐
开始 → 并行 ──┼→ 事件生成器 ─┼→ 场景演绎 → 结束
         └→ 地图管理员 ┘`}</pre>
            </div>
          </div>
        </div>
      ),
    },
    {
      id: 'faq',
      title: '常见问题',
      icon: <HelpCircle size={16} />,
      content: (
        <div className="space-y-3 text-sm">
          <div>
            <p className={`font-semibold ${isDark ? 'text-white' : 'text-gray-800'}`}>Q: 如何删除节点？</p>
            <p className={isDark ? 'text-gray-400' : 'text-gray-600'}>A: 选中节点后按 Delete 或 Backspace 键</p>
          </div>
          <div>
            <p className={`font-semibold ${isDark ? 'text-white' : 'text-gray-800'}`}>Q: 条件分支不工作？</p>
            <p className={isDark ? 'text-gray-400' : 'text-gray-600'}>A: 检查评估员是否正确连接，确保两条出边都设置了条件</p>
          </div>
          <div>
            <p className={`font-semibold ${isDark ? 'text-white' : 'text-gray-800'}`}>Q: 场景演绎如何选择角色？</p>
            <p className={isDark ? 'text-gray-400' : 'text-gray-600'}>A: 需先在「角色管理」创建角色，然后在节点属性面板选择</p>
          </div>
        </div>
      ),
    },
  ]

  return (
    <>
      {/* 帮助按钮 */}
      <button
        onClick={() => setIsOpen(true)}
        className={`flex items-center gap-1 px-3 py-1.5 rounded text-sm transition-colors ${
          isDark
            ? 'bg-gray-800 hover:bg-gray-700 text-gray-300'
            : 'bg-gray-100 hover:bg-gray-200 text-gray-700'
        }`}
        title="使用帮助"
      >
        <HelpCircle size={14} />
        帮助
      </button>

      {/* 帮助模态框 */}
      <Modal isOpen={isOpen} onClose={() => setIsOpen(false)} title="工作流使用指南" size="xl">
        <div className={`h-[70vh] overflow-y-auto ${isDark ? 'bg-gray-900' : 'bg-white'}`}>
          <div className="p-4 space-y-2">
            {helpSections.map((section) => (
              <Section key={section.id} section={section} />
            ))}
          </div>
        </div>

        {/* 底部操作 */}
        <div className={`flex justify-between items-center p-4 border-t ${isDark ? 'border-gray-700' : 'border-gray-200'}`}>
          <p className={`text-xs ${isDark ? 'text-gray-500' : 'text-gray-400'}`}>
            详细文档：docs/workflow-node-guide.md
          </p>
          <button
            onClick={() => setIsOpen(false)}
            className="px-4 py-2 bg-blue-500 text-white rounded hover:bg-blue-600"
          >
            关闭
          </button>
        </div>
      </Modal>
    </>
  )
}
