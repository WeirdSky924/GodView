/**
 * 工作流帮助组件
 * 显示工作流节点使用指南
 */

import { useState, useRef, useEffect } from 'react'
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
  Zap,
  Globe,
} from 'lucide-react'

interface HelpSection {
  id: string
  title: string
  icon?: React.ReactNode
  content: React.ReactNode
  defaultExpanded?: boolean
}

export default function WorkflowHelp() {
  const { theme } = useTheme()
  const isDark = theme === 'dark'
  const [isOpen, setIsOpen] = useState(false)
  const [expandedSections, setExpandedSections] = useState<Set<string>>(new Set(['quick-start']))
  const contentRef = useRef<HTMLDivElement>(null)

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

  // 防止滚动跳动
  useEffect(() => {
    if (isOpen && contentRef.current) {
      contentRef.current.scrollTop = 0
    }
  }, [isOpen])

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
      defaultExpanded: true,
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
            <NodeCard icon={<GitBranch size={14} />} name="总编剧" color="purple" description="规划整体剧情架构" />
            <NodeCard icon={<PenTool size={14} />} name="作家" color="green" description="执行章节内容写作" />
            <NodeCard icon={<BookOpen size={14} />} name="摘要" color="cyan" description="生成内容摘要" />
            <NodeCard icon={<Search size={14} />} name="评估" color="orange" description="评估内容质量" />
            <NodeCard icon={<Link size={14} />} name="伏笔" color="amber" description="管理伏笔埋设回收" />
            <NodeCard icon={<Settings size={14} />} name="设定" color="blue" description="维护世界观设定" />
            <NodeCard icon={<Dices size={14} />} name="事件" color="pink" description="生成故事事件" />
            <NodeCard icon={<Map size={14} />} name="地图" color="teal" description="管理地点空间" />
            <NodeCard icon={<Zap size={14} />} name="过程生成" color="yellow" description="过程化生成内容" />
            <NodeCard icon={<Globe size={14} />} name="副本生成" color="emerald" description="生成副本和关卡" />
            <NodeCard icon={<BookOpen size={14} />} name="章节大纲" color="rose" description="规划章节大纲" />
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
            description="多角色同台演绎场景，自动协调角色表演"
            usage="在属性面板选择参与角色"
          />
          <div className={`p-2 rounded text-xs ${isDark ? 'bg-gray-800' : 'bg-gray-50'}`}>
            <p className={isDark ? 'text-gray-400' : 'text-gray-500'}>
              <strong>场景模式：</strong><br />
              • <strong>互动模式</strong>：角色之间有互动对话<br />
              • <strong>并行模式</strong>：各角色独立行动
            </p>
            <p className={`mt-2 ${isDark ? 'text-gray-500' : 'text-gray-400'}`}>
              💡 场景演绎节点会自动调用角色Agent进行表演，无需单独使用角色节点
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
      title: '典型工作流示例',
      icon: <BookOpen size={16} />,
      content: (
        <div className="space-y-4">
          {/* 示例1：基础写作流程 */}
          <div className={`p-3 rounded-lg ${isDark ? 'bg-gray-800' : 'bg-gray-50'}`}>
            <h4 className={`font-semibold mb-2 ${isDark ? 'text-white' : 'text-gray-800'}`}>
              示例 1：基础写作流程
            </h4>
            <div className={`font-mono text-xs mb-2 ${isDark ? 'text-gray-400' : 'text-gray-500'}`}>
              开始 → 设定 → 总编剧 → 作家 → 结束
            </div>
            <p className={`text-xs ${isDark ? 'text-gray-500' : 'text-gray-400'}`}>
              最简单的线性流程，适合快速生成短篇内容
            </p>
          </div>

          {/* 示例2：标准创作流程 */}
          <div className={`p-3 rounded-lg ${isDark ? 'bg-gray-800' : 'bg-gray-50'}`}>
            <h4 className={`font-semibold mb-2 ${isDark ? 'text-white' : 'text-gray-800'}`}>
              示例 2：标准创作流程
            </h4>
            <div className={`font-mono text-xs mb-2 ${isDark ? 'text-gray-400' : 'text-gray-500'}`}>
              <pre>{`开始
  ↓
设定 → 伏笔
  ↓      ↓
总编剧 → 事件
  ↓
章节大纲
  ↓
作家
  ↓
评估 → 条件分支 → (retry) → 作家
  ↓ pass
摘要
  ↓
结束`}</pre>
            </div>
            <p className={`text-xs ${isDark ? 'text-gray-500' : 'text-gray-400'}`}>
              包含评估循环的完整创作流程，确保内容质量
            </p>
          </div>

          {/* 示例3：并行执行流程 */}
          <div className={`p-3 rounded-lg ${isDark ? 'bg-gray-800' : 'bg-gray-50'}`}>
            <h4 className={`font-semibold mb-2 ${isDark ? 'text-white' : 'text-gray-800'}`}>
              示例 3：并行执行流程
            </h4>
            <div className={`font-mono text-xs mb-2 ${isDark ? 'text-gray-400' : 'text-gray-500'}`}>
              <pre>{`         ┌→ 设定 ──────┐
         │              │
开始 → 并行 ──→ 事件 ────┼→ 场景演绎 → 结束
         │              │
         └→ 地图 ──────┘`}</pre>
            </div>
            <p className={`text-xs ${isDark ? 'text-gray-500' : 'text-gray-400'}`}>
              通过并行执行节点并发准备设定、事件、地图等素材，然后进行场景演绎（自动协调角色表演）
            </p>
          </div>

          {/* 示例4：完整小说创作流程 */}
          <div className={`p-3 rounded-lg ${isDark ? 'bg-gray-800' : 'bg-gray-50'}`}>
            <h4 className={`font-semibold mb-2 ${isDark ? 'text-white' : 'text-gray-800'}`}>
              示例 4：完整小说创作流程
            </h4>
            <div className={`font-mono text-xs mb-2 ${isDark ? 'text-gray-400' : 'text-gray-500'}`}>
              <pre>{`开始
  ↓
     ┌─────────── 并行 ───────────┐
     ↓            ↓              ↓
   设定        伏笔           地图
     ↓            ↓              ↓
     └─────────── 并行 ───────────┘
                   ↓
               总编剧
                   ↓
              章节大纲
                   ↓
     ┌─────────── 并行 ───────────┐
     ↓            ↓              ↓
   事件        过程生成       副本生成
     ↓            ↓              ↓
     └─────────── 并行 ───────────┘
                   ↓
              场景演绎
                   ↓
                作家
                   ↓
                评估 → 条件分支 → (retry) → 作家
                   ↓ pass
                摘要
                   ↓
            ┌─────判断─────┐
            ↓              ↓
        (继续下章)      (完结)
            ↓              ↓
        章节大纲 ←────    结束
            ↓
        循环...`}</pre>
            </div>
            <p className={`text-xs ${isDark ? 'text-gray-500' : 'text-gray-400'}`}>
              最完整的小说创作流程，包含所有Agent节点的协作
            </p>
          </div>

          {/* 示例5：副本生成流程 */}
          <div className={`p-3 rounded-lg ${isDark ? 'bg-gray-800' : 'bg-gray-50'}`}>
            <h4 className={`font-semibold mb-2 ${isDark ? 'text-white' : 'text-gray-800'}`}>
              示例 5：副本/关卡生成流程
            </h4>
            <div className={`font-mono text-xs mb-2 ${isDark ? 'text-gray-400' : 'text-gray-500'}`}>
              <pre>{`开始
  ↓
设定
  ↓
地图
  ↓
     ┌───── 并行 ─────┐
     ↓                ↓
 过程生成        副本生成
     ↓                ↓
     └───── 并行 ─────┘
            ↓
        事件
            ↓
        场景演绎
            ↓
        作家
            ↓
        评估 → 条件分支
            ↓ pass
        结束`}</pre>
            </div>
            <p className={`text-xs ${isDark ? 'text-gray-500' : 'text-gray-400'}`}>
              适合游戏副本、冒险关卡的内容生成
            </p>
          </div>

          {/* 示例6：集体讨论流程 */}
          <div className={`p-3 rounded-lg ${isDark ? 'bg-gray-800' : 'bg-gray-50'}`}>
            <h4 className={`font-semibold mb-2 ${isDark ? 'text-white' : 'text-gray-800'}`}>
              示例 6：集体讨论流程
            </h4>
            <div className={`font-mono text-xs mb-2 ${isDark ? 'text-gray-400' : 'text-gray-500'}`}>
              <pre>{`开始
  ↓
设定
  ↓
     ┌─────── 集体讨论 ───────┐
     │   (总编剧+章节大纲+作家)   │
     └───────────────────────┘
            ↓
        章节大纲
            ↓
        作家
            ↓
        结束`}</pre>
            </div>
            <p className={`text-xs ${isDark ? 'text-gray-500' : 'text-gray-400'}`}>
              多个Agent共同讨论后再进行创作
            </p>
          </div>
        </div>
      ),
    },
    {
      id: 'node-order',
      title: '节点推荐顺序',
      icon: <Layers size={16} />,
      content: (
        <div className="space-y-4">
          <div className={`p-3 rounded-lg ${isDark ? 'bg-blue-900/30' : 'bg-blue-50'}`}>
            <p className={`text-sm ${isDark ? 'text-blue-300' : 'text-blue-700'}`}>
              以下是各类节点在工作流中的推荐执行顺序
            </p>
          </div>

          {/* 前期准备阶段 */}
          <div className={`p-3 rounded-lg border ${isDark ? 'border-gray-700' : 'border-gray-200'}`}>
            <h4 className={`font-semibold mb-2 ${isDark ? 'text-green-400' : 'text-green-600'}`}>
              📋 前期准备阶段
            </h4>
            <div className={`text-sm space-y-1 ${isDark ? 'text-gray-300' : 'text-gray-600'}`}>
              <p>1. <strong>设定</strong> - 加载世界观设定</p>
              <p>2. <strong>地图</strong> - 确认地点信息</p>
              <p>3. <strong>伏笔</strong> - 准备伏笔池</p>
              <p>4. <strong>事件</strong> - 生成事件池</p>
              <p className="text-xs opacity-70 mt-2">💡 这些节点可以并行执行</p>
            </div>
          </div>

          {/* 规划阶段 */}
          <div className={`p-3 rounded-lg border ${isDark ? 'border-gray-700' : 'border-gray-200'}`}>
            <h4 className={`font-semibold mb-2 ${isDark ? 'text-purple-400' : 'text-purple-600'}`}>
              🎯 规划阶段
            </h4>
            <div className={`text-sm space-y-1 ${isDark ? 'text-gray-300' : 'text-gray-600'}`}>
              <p>1. <strong>总编剧</strong> - 整体剧情架构</p>
              <p>2. <strong>章节大纲</strong> - 章节细纲与场景规划</p>
            </div>
          </div>

          {/* 执行阶段 */}
          <div className={`p-3 rounded-lg border ${isDark ? 'border-gray-700' : 'border-gray-200'}`}>
            <h4 className={`font-semibold mb-2 ${isDark ? 'text-orange-400' : 'text-orange-600'}`}>
              ✍️ 执行阶段
            </h4>
            <div className={`text-sm space-y-1 ${isDark ? 'text-gray-300' : 'text-gray-600'}`}>
              <p>1. <strong>事件</strong> - 事件 Agent 生成候选事件</p>
              <p>2. <strong>过程生成</strong> - 动态生成内容</p>
              <p>3. <strong>副本生成</strong> - 关卡/副本内容</p>
              <p>4. <strong>场景演绎</strong> - 多角色场景表演（自动协调角色）</p>
              <p>5. <strong>作家</strong> - 最终输出</p>
            </div>
          </div>

          {/* 评估阶段 */}
          <div className={`p-3 rounded-lg border ${isDark ? 'border-gray-700' : 'border-gray-200'}`}>
            <h4 className={`font-semibold mb-2 ${isDark ? 'text-red-400' : 'text-red-600'}`}>
              🔍 评估阶段
            </h4>
            <div className={`text-sm space-y-1 ${isDark ? 'text-gray-300' : 'text-gray-600'}`}>
              <p>1. <strong>评估</strong> - 质量检查</p>
              <p>2. <strong>条件分支</strong> - 通过/重试</p>
              <p>3. <strong>摘要</strong> - 内容摘要（通过后）</p>
            </div>
          </div>

          {/* 完整顺序图 */}
          <div className={`p-3 rounded-lg ${isDark ? 'bg-gray-800' : 'bg-gray-50'}`}>
            <h4 className={`font-semibold mb-2 ${isDark ? 'text-white' : 'text-gray-800'}`}>
              完整推荐顺序
            </h4>
            <div className={`font-mono text-xs ${isDark ? 'text-gray-400' : 'text-gray-500'}`}>
              <pre>{`设定/地图/伏笔/事件 (并行)
        ↓
      总编剧
        ↓
     章节大纲
        ↓
事件/过程生成/副本生成 (并行)
        ↓
     场景演绎
        ↓
       作家
        ↓
       评估
        ↓
    条件分支
   ↙      ↘
retry      pass
  ↓          ↓
作家       摘要
            ↓
          结束`}</pre>
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
            <p className={isDark ? 'text-gray-400' : 'text-gray-600'}>A: 检查评估节点是否正确连接，确保两条出边都设置了条件</p>
          </div>
          <div>
            <p className={`font-semibold ${isDark ? 'text-white' : 'text-gray-800'}`}>Q: 场景演绎如何选择角色？</p>
            <p className={isDark ? 'text-gray-400' : 'text-gray-600'}>A: 需先在「角色管理」创建角色，然后在节点属性面板选择</p>
          </div>
          <div>
            <p className={`font-semibold ${isDark ? 'text-white' : 'text-gray-800'}`}>Q: 重试次数有限制吗？</p>
            <p className={isDark ? 'text-gray-400' : 'text-gray-600'}>A: 重试最多 3 次，超过后自动通过</p>
          </div>
          <div>
            <p className={`font-semibold ${isDark ? 'text-white' : 'text-gray-800'}`}>Q: 哪些节点可以并行？</p>
            <p className={isDark ? 'text-gray-400' : 'text-gray-600'}>A: 设定、地图、伏笔、事件等准备类节点适合并行；总编剧→章节大纲→作家等依赖类节点需要顺序执行</p>
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
        <div className={`h-[70vh] overflow-y-auto ${isDark ? 'bg-gray-900' : 'bg-white'}`} ref={contentRef}>
          <div className="p-4 space-y-2">
            {helpSections.map((section) => {
              const isExpanded = expandedSections.has(section.id)
              return (
                <div key={section.id}>
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
                    <span className="w-4 h-4 flex-shrink-0">
                      {isExpanded ? <ChevronDown size={16} /> : <ChevronRight size={16} />}
                    </span>
                    {section.icon}
                    <span className="font-medium">{section.title}</span>
                  </button>

                  {isExpanded && (
                    <div className="mt-1 mb-2 px-3 py-2">
                      {section.content}
                    </div>
                  )}
                </div>
              )
            })}
          </div>
        </div>

        {/* 底部操作 */}
        <div className={`flex justify-between items-center p-4 border-t ${isDark ? 'border-gray-700' : 'border-gray-200'}`}>
          <p className={`text-xs ${isDark ? 'text-gray-500' : 'text-gray-400'}`}>
            点击标题展开/折叠详细内容
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
