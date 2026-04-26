import { useState, useRef, useEffect } from 'react'
import type { ReactNode } from 'react'
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
  User,
} from 'lucide-react'

interface HelpSection {
  id: string
  title: string
  icon?: ReactNode
  content: ReactNode
}

type ColorKey =
  | 'green'
  | 'red'
  | 'amber'
  | 'indigo'
  | 'blue'
  | 'purple'
  | 'violet'
  | 'cyan'
  | 'pink'
  | 'teal'
  | 'yellow'
  | 'emerald'
  | 'rose'
  | 'orange'
  | 'slate'

interface AuditNodeItem {
  id: string
  name: string
  summary: string
  category: string
  color: ColorKey
  icon: ReactNode
  inputs: string[]
  work: string[]
  outputs: string[]
  sourceRefs: string[]
  notes?: string[]
}

interface AuditGroup {
  id: string
  title: string
  items: AuditNodeItem[]
}

const colorStyles: Record<ColorKey, { badge: string; panel: string; text: string; border: string }> = {
  green: {
    badge: 'bg-green-100 text-green-700',
    panel: 'bg-green-50',
    text: 'text-green-700',
    border: 'border-green-200',
  },
  red: {
    badge: 'bg-red-100 text-red-700',
    panel: 'bg-red-50',
    text: 'text-red-700',
    border: 'border-red-200',
  },
  amber: {
    badge: 'bg-amber-100 text-amber-700',
    panel: 'bg-amber-50',
    text: 'text-amber-700',
    border: 'border-amber-200',
  },
  indigo: {
    badge: 'bg-indigo-100 text-indigo-700',
    panel: 'bg-indigo-50',
    text: 'text-indigo-700',
    border: 'border-indigo-200',
  },
  blue: {
    badge: 'bg-blue-100 text-blue-700',
    panel: 'bg-blue-50',
    text: 'text-blue-700',
    border: 'border-blue-200',
  },
  purple: {
    badge: 'bg-purple-100 text-purple-700',
    panel: 'bg-purple-50',
    text: 'text-purple-700',
    border: 'border-purple-200',
  },
  violet: {
    badge: 'bg-violet-100 text-violet-700',
    panel: 'bg-violet-50',
    text: 'text-violet-700',
    border: 'border-violet-200',
  },
  cyan: {
    badge: 'bg-cyan-100 text-cyan-700',
    panel: 'bg-cyan-50',
    text: 'text-cyan-700',
    border: 'border-cyan-200',
  },
  pink: {
    badge: 'bg-pink-100 text-pink-700',
    panel: 'bg-pink-50',
    text: 'text-pink-700',
    border: 'border-pink-200',
  },
  teal: {
    badge: 'bg-teal-100 text-teal-700',
    panel: 'bg-teal-50',
    text: 'text-teal-700',
    border: 'border-teal-200',
  },
  yellow: {
    badge: 'bg-yellow-100 text-yellow-700',
    panel: 'bg-yellow-50',
    text: 'text-yellow-700',
    border: 'border-yellow-200',
  },
  emerald: {
    badge: 'bg-emerald-100 text-emerald-700',
    panel: 'bg-emerald-50',
    text: 'text-emerald-700',
    border: 'border-emerald-200',
  },
  rose: {
    badge: 'bg-rose-100 text-rose-700',
    panel: 'bg-rose-50',
    text: 'text-rose-700',
    border: 'border-rose-200',
  },
  orange: {
    badge: 'bg-orange-100 text-orange-700',
    panel: 'bg-orange-50',
    text: 'text-orange-700',
    border: 'border-orange-200',
  },
  slate: {
    badge: 'bg-slate-100 text-slate-700',
    panel: 'bg-slate-50',
    text: 'text-slate-700',
    border: 'border-slate-200',
  },
}

const flowSemantics = {
  inputSources: [
    'database：运行时从数据库读取数据集。',
    'context：直接读取 execution.context[key]。',
    'upstream：从上游节点 output_data 的指定字段取值。',
    'variable：读取工作流变量。',
    'user_input：读取用户在暂停节点后提交的输入。',
  ],
  outputTargets: [
    'context：将节点输出写回 execution.context，后续节点可继续读取。',
    'downstream：保留给下游传递，当前主要仍通过 context 聚合。',
    'database：声明保存到数据库时，由引擎负责落库。',
  ],
  runtimeNotes: [
    '输入准备以 app/services/workflow_engine.py::_prepare_node_inputs 为准。',
    '节点执行分发以 app/services/workflow_engine.py::_execute_node 为准。',
    '输出写回以 app/services/workflow_engine.py::_process_node_outputs 为准。',
    '本页“当前输入/输出”优先按 frontend/src/pages/Visualizer.tsx 中标准全节点模板描述。',
  ],
}

const auditGroups: AuditGroup[] = [
  {
    id: 'control',
    title: '控制节点',
    items: [
      {
        id: 'start',
        name: '开始',
        summary: '装载项目运行上下文，是后续节点的数据起点。',
        category: 'control',
        color: 'green',
        icon: <Play size={14} />,
        inputs: ['无显式输入。'],
        work: [
          '由 _execute_start_node 读取项目、世界、角色、伏笔、事件、地点、前文章节等基础数据。',
          '补齐 retry_count、last_user_input、last_confirmation_response 等运行时字段。',
        ],
        outputs: [
          'project_info',
          'world_info',
          'characters',
          'lore_entries',
          'existing_hooks',
          'events',
          'locations',
          'previous_chapters',
        ],
        sourceRefs: ['app/services/workflow_engine.py::_execute_start_node'],
      },
      {
        id: 'end',
        name: '结束',
        summary: '工作流终点，节点本身不再补充业务内容。',
        category: 'control',
        color: 'red',
        icon: <Square size={14} />,
        inputs: ['读取上游已聚合好的 context，但当前标准模板未声明显式 inputs。'],
        work: ['在 _execute_node 中直接返回 {status: "completed"}。'],
        outputs: ['无标准业务输出；结束当前执行。'],
        sourceRefs: ['app/services/workflow_engine.py::_execute_node'],
      },
      {
        id: 'condition',
        name: '条件分支',
        summary: '根据 context 中的判定值选择 pass 或 retry 分支。',
        category: 'control',
        color: 'amber',
        icon: <GitBranch size={14} />,
        inputs: [
          '读取 node.config.condition_key 指向的 context 值。',
          '当前标准模板会带 summary / chapter_outline 或 evaluation_passed / evaluation_feedback。',
        ],
        work: [
          '由 _execute_condition_node 根据 pass_value、pass_when_missing、retry_count 计算结果。',
          '标准模板中既用于“是否需要人工补充”，也用于“评估是否通过”。',
        ],
        outputs: [
          'condition_evaluated',
          'quality_passed',
          'condition_result',
          'condition_key',
          'retry_count',
          'evaluation_feedback',
        ],
        sourceRefs: ['app/services/workflow_engine.py::_execute_condition_node'],
      },
      {
        id: 'parallel',
        name: '并行执行',
        summary: '并行节点本身是调度标记，分支执行由拓扑调度负责。',
        category: 'control',
        color: 'indigo',
        icon: <Layers size={14} />,
        inputs: ['通常承接上游上下文，不要求额外显式输入。'],
        work: [
          '当前 _execute_parallel_node 只返回 {parallel_executed: true}。',
          '真正的并行关系依赖节点拓扑和多条出边，而不是节点内部再调度一次。',
        ],
        outputs: ['parallel_executed'],
        sourceRefs: ['app/services/workflow_engine.py::_execute_parallel_node'],
      },
      {
        id: 'input',
        name: '用户输入',
        summary: '将工作流置为暂停，等待人工补充信息后再继续。',
        category: 'control',
        color: 'blue',
        icon: <MessageSquare size={14} />,
        inputs: ['读取当前上下文与节点 config.prompt。'],
        work: [
          '在 _execute_node 中将 execution.status 置为 paused。',
          '返回 waiting_for_input，等待后续 API 补充用户输入。',
        ],
        outputs: ['当前标准模板映射 status -> input_status。'],
        sourceRefs: ['app/services/workflow_engine.py::_execute_node'],
      },
    ],
  },
  {
    id: 'interaction',
    title: '交互节点',
    items: [
      {
        id: 'group_discussion',
        name: '集体讨论',
        summary: '汇总多个上游结果，组织会议讨论或表演式讨论。',
        category: 'interaction',
        color: 'indigo',
        icon: <MessageCircle size={14} />,
        inputs: [
          'chapter_title / chapter_outline / chapter_goals（来自章节大纲节点）',
          'events（来自事件 Agent）',
          'lore_entries（来自设定 Agent）',
          'locations（来自地图 Agent）',
          'regions（来自过程生成 Agent）',
          'dungeon_plan（来自副本生成 Agent）',
        ],
        work: [
          '由 _execute_group_discussion_node 根据 discussion_mode 进入会议讨论或角色表演。',
          '若讨论完成，会附加 discussion_assets 与 discussion_asset_digest。',
          '若 require_user_confirmation 为 true，则会暂停工作流等待用户确认。',
        ],
        outputs: ['group_discussion', 'last_discussion_summary'],
        sourceRefs: ['app/services/workflow_engine.py::_execute_group_discussion_node'],
        notes: ['运行时还能生成 discussion_assets / discussion_asset_digest，但是否持久暴露取决于节点 outputs 配置。'],
      },
      {
        id: 'scene_performance',
        name: '场景演绎',
        summary: '把场景指令转成多角色同台演绎结果。',
        category: 'interaction',
        color: 'rose',
        icon: <Users size={14} />,
        inputs: [
          'scene_directions（来自章节大纲节点）',
          'chapter_outline（来自章节大纲节点）',
          'characters（来自 context）',
        ],
        work: [
          '由 _execute_scene_performance_node 调用 _execute_multi_character_scene。',
          '按照 scene_mode、required_characters 等配置组织角色参与。',
        ],
        outputs: ['performance_result', 'dialogues'],
        sourceRefs: ['app/services/workflow_engine.py::_execute_scene_performance_node'],
      },
    ],
  },
  {
    id: 'agents',
    title: 'Agent 节点',
    items: [
      {
        id: 'plot_outline',
        name: '章节大纲 Agent',
        summary: '优先输出已准备的指定章节大纲；缺失时才兜底生成。',
        category: 'agent',
        color: 'rose',
        icon: <BookOpen size={14} />,
        inputs: [
          'chapter_num（context.chapter_num，必填，默认 1）',
          'project_info / world_info / lore_entries / characters / existing_hooks（来自 context）',
          'previous_chapters（来自 context）',
          '若 execution.context 已提前注入 chapter_outline，会优先直接使用。',
        ],
        work: [
          '这是 service_adapter 节点，不走普通 direct_agent 路径。',
          '执行顺序为：先读 execution.context[chapter_outline]，再查 get_chapter_outline_for_workflow(...)，最后才调用 generate_outline(...)。',
          '统一补齐 title / summary / chapter_goals / scenes，并组装 scene_directions。',
        ],
        outputs: [
          'chapter_number',
          'chapter_title',
          'chapter_outline',
          'chapter_summary',
          'chapter_goals',
          'scene_directions',
          'outline_id',
          'saved_outline',
          'suggestions',
          'warnings',
          'outline_source',
        ],
        sourceRefs: [
          'app/services/workflow_adapters/plot_outline_adapter.py::execute',
          'app/services/workflow_engine.py::start_workflow_execution',
          'app/services/workflow_node_registry.py::get_workflow_node_adapter',
        ],
      },
      {
        id: 'setting',
        name: '设定 Agent',
        summary: '根据进入节点的章节、场景、角色与地点线索，动态选择相关已有设定。',
        category: 'agent',
        color: 'blue',
        icon: <Settings size={14} />,
        inputs: [
          'chapter_outline / chapter_goals（来自章节大纲节点，作为检索线索）',
          'scene_directions / selected_characters / locations / world_info（来自 context，作为相关性线索）',
          'lore_entries（可选 context 候选池；会被过滤和限量，不会整包透传）',
        ],
        work: [
          '属于 service_adapter 节点，由 workflow_adapters/setting_adapter.py 执行。',
          '基于当前节点输入组装 setting_query，并按关键词、角色、地点、场景等相关性筛选已有设定。',
          '无候选池时使用 LoreIndexService 智能检索或受限关键词 SQL 检索，始终带 limit。',
          '工作流模式只读：不调用普通 SettingAgent chat，不生成新设定，不全量加载设定库，不落库。',
        ],
        outputs: [
          'lore_entries / selected_lore_entries（动态选中的相关已有设定）',
          'setting_updates / new_lores / updated_lores / validated_lores（只读模式下为空）',
          'setting_query / setting_source / setting_count / setting_read_only / warnings',
        ],
        sourceRefs: [
          'app/services/workflow_adapters/setting_adapter.py::execute',
          'app/services/lore_index_service.py::smart_search',
          'app/services/workflow_node_registry.py::get_workflow_node_adapter',
          'app/services/workflow_engine.py::_execute_agent_node',
        ],
      },
      {
        id: 'master_plotter',
        name: '总编剧 Agent',
        summary: '把已汇总素材整理成统一写作计划。',
        category: 'agent',
        color: 'indigo',
        icon: <GitBranch size={14} />,
        inputs: [
          'chapter_outline / chapter_goals / summary / hooks / events / locations（来自 context）',
        ],
        work: [
          '属于 direct_agent 节点。',
          '当前标准模板把它放在写作前，用于再次统一整理写作计划。',
        ],
        outputs: ['plot_outline', 'chapter_outline', 'chapter_goals'],
        sourceRefs: ['app/services/workflow_engine.py::_execute_agent_node'],
      },
      {
        id: 'plotter',
        name: '编剧 Agent',
        summary: '偏局部剧情与桥段规划；当前标准全节点模板未使用该节点。',
        category: 'agent',
        color: 'violet',
        icon: <GitBranch size={14} />,
        inputs: [
          '当前标准模板未声明固定 inputs。',
          '若自定义工作流使用它，则以节点 inputs 配置为准；若未配置，则由 _load_agent_context 按 agent_type 自动装载上下文。',
        ],
        work: [
          '属于 direct_agent 节点。',
          '运行时行为与其他普通 Agent 一致，由 workflow_engine 负责上下文组装与调用。',
        ],
        outputs: ['取决于节点 outputs 配置；常见用途是输出局部桥段、桥接方案或场景计划。'],
        sourceRefs: ['app/services/workflow_engine.py::_execute_agent_node'],
      },
      {
        id: 'writer',
        name: '作家 Agent',
        summary: '根据大纲、摘要和场景信息输出章节正文。',
        category: 'agent',
        color: 'purple',
        icon: <PenTool size={14} />,
        inputs: [
          'chapter_title / chapter_outline / chapter_goals / summary / scene_directions / hooks（来自 context）',
          'retry_message（来自 context，返工时可用）',
        ],
        work: [
          '属于 direct_agent 节点。',
          '通常承接前面节点已经结构化好的上下文，进行最终文本生成。',
        ],
        outputs: ['content -> chapter_content', 'summary -> writer_summary'],
        sourceRefs: ['app/services/workflow_engine.py::_execute_agent_node'],
      },
      {
        id: 'summarizer',
        name: '摘要 Agent',
        summary: '把大纲、讨论、演绎结果压缩成后续可复用摘要。',
        category: 'agent',
        color: 'amber',
        icon: <BookOpen size={14} />,
        inputs: [
          'chapter_summary（来自章节大纲节点）',
          'last_discussion_summary / performance_result / hooks（来自 context）',
        ],
        work: [
          '属于 direct_agent 节点。',
          '常用于把前面多节点产物压缩成写作和评估更易消费的摘要。',
        ],
        outputs: ['summary', 'chapter_summary'],
        sourceRefs: ['app/services/workflow_engine.py::_execute_agent_node'],
      },
      {
        id: 'evaluator',
        name: '评估 Agent',
        summary: '给出通过/返工判定和修订建议。',
        category: 'agent',
        color: 'orange',
        icon: <Search size={14} />,
        inputs: [
          'chapter_content / chapter_outline / chapter_goals / lore_entries（来自 context）',
        ],
        work: [
          '属于 direct_agent 节点。',
          '其结果通常会被后续条件分支节点读取，用于决定 pass 或 retry。',
        ],
        outputs: ['quality_passed', 'issues -> evaluation_issues', 'suggestions -> revision_notes'],
        sourceRefs: ['app/services/workflow_engine.py::_execute_agent_node'],
      },
      {
        id: 'hook_manager',
        name: '伏笔 Agent',
        summary: '根据大纲和讨论结果安排伏笔埋设与状态更新。',
        category: 'agent',
        color: 'cyan',
        icon: <Link size={14} />,
        inputs: [
          'chapter_outline / chapter_goals（来自章节大纲节点）',
          'existing_hooks / last_discussion_summary（来自 context）',
        ],
        work: [
          '属于 direct_agent 节点。',
          '典型职责是读取当前伏笔池并产出更新后的 hooks / existing_hooks。',
        ],
        outputs: ['hooks', 'existing_hooks'],
        sourceRefs: ['app/services/workflow_engine.py::_execute_agent_node'],
      },
      {
        id: 'event_generator',
        name: '事件 Agent',
        summary: '围绕本章大纲生成事件候选并补充事件池。',
        category: 'agent',
        color: 'pink',
        icon: <Dices size={14} />,
        inputs: [
          'chapter_outline / chapter_goals（来自章节大纲节点）',
          'events（来自 context）',
        ],
        work: [
          '属于 direct_agent 节点。',
          '常与设定、地图、过程生成并行执行，作为素材准备阶段的一部分。',
        ],
        outputs: ['events', 'event_candidates'],
        sourceRefs: ['app/services/workflow_engine.py::_execute_agent_node'],
      },
      {
        id: 'world_map_manager',
        name: '地图 Agent',
        summary: '为当前章节准备地点、地图与空间关系信息。',
        category: 'agent',
        color: 'teal',
        icon: <Map size={14} />,
        inputs: [
          'scene_directions / chapter_outline（来自章节大纲节点）',
          'world_info / locations（来自 context）',
        ],
        work: [
          '属于 direct_agent 节点。',
          '常在场景演绎前补齐地点信息，供后续角色行动与空间逻辑使用。',
        ],
        outputs: ['locations', 'world_map_plan'],
        sourceRefs: ['app/services/workflow_engine.py::_execute_agent_node'],
      },
      {
        id: 'proc_gen',
        name: '过程生成 Agent',
        summary: '扩展探索区域、环境细节或可生成素材。',
        category: 'agent',
        color: 'yellow',
        icon: <Zap size={14} />,
        inputs: [
          'scene_directions / chapter_goals（来自章节大纲节点）',
          'world_info（来自 context）',
        ],
        work: [
          '属于 direct_agent 节点。',
          '当前标准模板把它作为并行素材准备的一部分。',
        ],
        outputs: ['regions', 'procgen_result'],
        sourceRefs: ['app/services/workflow_engine.py::_execute_agent_node'],
      },
      {
        id: 'dungeon_generator',
        name: '副本生成 Agent',
        summary: '在章节涉及副本/探索时提供结构化场景方案。',
        category: 'agent',
        color: 'emerald',
        icon: <Globe size={14} />,
        inputs: ['scene_directions / chapter_outline（来自章节大纲节点）'],
        work: [
          '属于 direct_agent 节点。',
          '通常在探索型剧情中补充副本结构、关卡或区域规划。',
        ],
        outputs: ['dungeon_plan'],
        sourceRefs: ['app/services/workflow_engine.py::_execute_agent_node'],
      },
      {
        id: 'character',
        name: '角色 Agent',
        summary: '项目角色会在运行时动态生成专属 Agent 节点。',
        category: 'agent',
        color: 'green',
        icon: <User size={14} />,
        inputs: [
          '当前标准模板未直接放入该节点。',
          '若用户把角色节点拖入工作流，输入仍取决于该节点 inputs 配置，或由默认 agent 上下文装载。',
        ],
        work: [
          '节点定义由 get_project_character_nodes 根据项目角色列表动态生成。',
          '执行时仍走普通 direct_agent 路径。',
        ],
        outputs: ['取决于节点 outputs 配置；常见于对话、角色视角内容或角色反馈。'],
        sourceRefs: [
          'app/services/workflow_node_catalog.py::get_project_character_nodes',
          'app/services/workflow_engine.py::_execute_agent_node',
        ],
      },
    ],
  },
]

function SectionList({
  title,
  items,
  isDark,
}: {
  title: string
  items: string[]
  isDark: boolean
}) {
  return (
    <div>
      <h5 className={`text-xs font-semibold mb-2 ${isDark ? 'text-gray-200' : 'text-gray-700'}`}>{title}</h5>
      <ul className={`space-y-1.5 text-xs ${isDark ? 'text-gray-300' : 'text-gray-600'}`}>
        {items.map((item) => (
          <li key={item} className="leading-5">
            {item}
          </li>
        ))}
      </ul>
    </div>
  )
}

function AuditNodeCard({
  item,
  isDark,
  expanded,
  onToggle,
}: {
  item: AuditNodeItem
  isDark: boolean
  expanded: boolean
  onToggle: () => void
}) {
  const style = colorStyles[item.color]

  return (
    <div className={`rounded-xl border ${isDark ? 'border-gray-700 bg-gray-900' : `border ${style.border} bg-white`}`}>
      <button
        onClick={onToggle}
        className={`w-full px-4 py-3 text-left rounded-xl transition-colors ${
          isDark ? 'hover:bg-gray-800' : style.panel
        }`}
      >
        <div className="flex items-start gap-3">
          <span className={`mt-0.5 flex h-8 w-8 items-center justify-center rounded-lg ${isDark ? 'bg-gray-800 text-gray-200' : style.badge}`}>
            {item.icon}
          </span>
          <div className="min-w-0 flex-1">
            <div className="flex items-center gap-2 flex-wrap">
              <span className={`font-semibold ${isDark ? 'text-white' : 'text-gray-900'}`}>{item.name}</span>
              <span className={`rounded-full px-2 py-0.5 text-[11px] ${isDark ? 'bg-gray-800 text-gray-300' : style.badge}`}>
                {item.category}
              </span>
            </div>
            <p className={`mt-1 text-sm leading-5 ${isDark ? 'text-gray-300' : 'text-gray-700'}`}>{item.summary}</p>
          </div>
          <span className={`mt-1 ${isDark ? 'text-gray-400' : 'text-gray-500'}`}>
            {expanded ? <ChevronDown size={16} /> : <ChevronRight size={16} />}
          </span>
        </div>
      </button>

      {expanded && (
        <div className={`border-t px-4 py-4 ${isDark ? 'border-gray-700 bg-gray-900' : 'border-gray-200 bg-white'}`}>
          <div className="grid gap-4 lg:grid-cols-3">
            <SectionList title="当前输入" items={item.inputs} isDark={isDark} />
            <SectionList title="节点内工作" items={item.work} isDark={isDark} />
            <SectionList title="当前输出" items={item.outputs} isDark={isDark} />
          </div>

          <div className="mt-4 grid gap-4 lg:grid-cols-2">
            <div>
              <h5 className={`text-xs font-semibold mb-2 ${isDark ? 'text-gray-200' : 'text-gray-700'}`}>运行依据</h5>
              <div className="space-y-1.5">
                {item.sourceRefs.map((ref) => (
                  <div
                    key={ref}
                    className={`rounded-lg px-2.5 py-2 font-mono text-[11px] ${
                      isDark ? 'bg-gray-800 text-gray-300' : 'bg-gray-50 text-gray-700'
                    }`}
                  >
                    {ref}
                  </div>
                ))}
              </div>
            </div>

            {item.notes && item.notes.length > 0 ? (
              <div>
                <h5 className={`text-xs font-semibold mb-2 ${isDark ? 'text-gray-200' : 'text-gray-700'}`}>审计备注</h5>
                <div className="space-y-1.5">
                  {item.notes.map((note) => (
                    <div
                      key={note}
                      className={`rounded-lg px-3 py-2 text-xs leading-5 ${
                        isDark ? 'bg-gray-800 text-gray-300' : 'bg-slate-50 text-slate-700'
                      }`}
                    >
                      {note}
                    </div>
                  ))}
                </div>
              </div>
            ) : null}
          </div>
        </div>
      )}
    </div>
  )
}

export default function WorkflowHelp() {
  const { theme } = useTheme()
  const isDark = theme === 'dark'
  const [isOpen, setIsOpen] = useState(false)
  const [expandedSections, setExpandedSections] = useState<Set<string>>(new Set(['quick-start', 'audit']))
  const [expandedNodes, setExpandedNodes] = useState<Set<string>>(new Set(['plot_outline']))
  const contentRef = useRef<HTMLDivElement>(null)

  const toggleSection = (id: string) => {
    setExpandedSections((prev) => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }

  const toggleNode = (id: string) => {
    setExpandedNodes((prev) => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }

  useEffect(() => {
    if (isOpen && contentRef.current) {
      contentRef.current.scrollTop = 0
    }
  }, [isOpen])

  const helpSections: HelpSection[] = [
    {
      id: 'quick-start',
      title: '如何用这份帮助页审查节点职责',
      icon: <Play size={16} />,
      content: (
        <div className="space-y-3">
          <ol className={`list-decimal list-inside space-y-2 text-sm ${isDark ? 'text-gray-300' : 'text-gray-700'}`}>
            <li>先看“当前输入”，确认节点是否真的只消费它应该消费的数据。</li>
            <li>再看“节点内工作”，确认它是在做编排、调用 Agent，还是直接执行内建逻辑。</li>
            <li>最后看“当前输出”，检查是否把不该由它负责的内容写回了 context。</li>
            <li>若自定义工作流修改了节点 inputs / outputs，请以当前工作流配置覆盖本页标准模板说明。</li>
          </ol>
          <div className={`rounded-lg p-3 text-sm ${isDark ? 'bg-gray-800 text-gray-300' : 'bg-slate-50 text-slate-700'}`}>
            这份帮助页的目标不是教学式概览，而是提供可审计的“输入 / 节点内工作 / 输出”基线，方便逐节点检查职责漂移。
          </div>
        </div>
      ),
    },
    {
      id: 'semantics',
      title: '数据流与执行语义',
      icon: <Settings size={16} />,
      content: (
        <div className="grid gap-4 lg:grid-cols-3">
          <SectionList title="输入来源" items={flowSemantics.inputSources} isDark={isDark} />
          <SectionList title="输出目标" items={flowSemantics.outputTargets} isDark={isDark} />
          <SectionList title="实际运行依据" items={flowSemantics.runtimeNotes} isDark={isDark} />
        </div>
      ),
    },
    {
      id: 'audit',
      title: '内置节点审计视图',
      icon: <Search size={16} />,
      content: (
        <div className="space-y-5">
          {auditGroups.map((group) => (
            <div key={group.id}>
              <h4 className={`mb-3 text-sm font-semibold ${isDark ? 'text-gray-100' : 'text-gray-900'}`}>{group.title}</h4>
              <div className="space-y-3">
                {group.items.map((item) => (
                  <AuditNodeCard
                    key={item.id}
                    item={item}
                    isDark={isDark}
                    expanded={expandedNodes.has(item.id)}
                    onToggle={() => toggleNode(item.id)}
                  />
                ))}
              </div>
            </div>
          ))}
        </div>
      ),
    },
    {
      id: 'review-checklist',
      title: '建议重点检查的职责边界',
      icon: <Link size={16} />,
      content: (
        <div className="grid gap-4 lg:grid-cols-2">
          <SectionList
            title="优先检查这些节点"
            items={[
              '章节大纲 Agent：是否保持 read-first，而不是重新生成覆盖已有大纲。',
              '总编剧 / 编剧：是否开始承担本该由章节大纲节点负责的章节规划。',
              '场景演绎 / 集体讨论：是否把中间资产直接写成最终正文。',
              '评估 / 条件分支：是否只负责判定与回流，不顺带改写主内容。',
            ]}
            isDark={isDark}
          />
          <SectionList
            title="看到异常时怎么定位"
            items={[
              '先核对节点卡片里的运行依据代码位置。',
              '再去 workflow_monitor 查看该节点 input_data / output_data。',
              '若标准模板与实际工作流不同，优先检查当前工作流节点配置。',
              '若输出 shape 变了，继续追踪 _process_node_outputs 和下游节点 inputs。',
            ]}
            isDark={isDark}
          />
        </div>
      ),
    },
  ]

  return (
    <>
      <button
        onClick={() => setIsOpen(true)}
        className={`flex items-center gap-1 px-3 py-1.5 rounded text-sm transition-colors ${
          isDark ? 'bg-gray-800 hover:bg-gray-700 text-gray-300' : 'bg-gray-100 hover:bg-gray-200 text-gray-700'
        }`}
        title="工作流帮助与节点审计"
      >
        <HelpCircle size={14} />
        帮助
      </button>

      <Modal isOpen={isOpen} onClose={() => setIsOpen(false)} title="工作流帮助与节点审计" size="xl">
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

                  {isExpanded && <div className="mt-1 mb-2 px-3 py-2">{section.content}</div>}
                </div>
              )
            })}
          </div>
        </div>

        <div className={`flex justify-between items-center p-4 border-t ${isDark ? 'border-gray-700' : 'border-gray-200'}`}>
          <p className={`text-xs ${isDark ? 'text-gray-500' : 'text-gray-400'}`}>
            展开节点卡片可查看当前输入、节点内工作、当前输出与运行依据。
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
