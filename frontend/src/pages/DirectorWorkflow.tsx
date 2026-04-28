/**
 * 工作流导演页面
 * v8 Agent协作可视化工作台
 */

import { useState, useCallback } from 'react'
import PageLayout from '@/components/PageLayout'
import { useProject } from '@/contexts/ProjectContext'
import { useTheme } from '@/contexts/ThemeContext'
import {
  WorkflowEditor,
  WorkflowMonitor,
  WorkflowTrace,
  AgentChat,
  InterventionLog,
} from '@/components/workflow'
import type { WorkflowDefinition } from '@/api/workflows'
import {
  FolderOpen,
  Layout,
  Activity,
  MessageSquare,
  History,
  GitBranch,
  ChevronLeft,
  ChevronRight,
} from 'lucide-react'

// 标签页类型
type TabType = 'editor' | 'monitor' | 'trace' | 'chat' | 'logs'

export default function DirectorWorkflow() {
  const { currentProject } = useProject()
  const { theme } = useTheme()
  const isDark = theme === 'dark'

  // 状态
  const [activeTab, setActiveTab] = useState<TabType>('editor')
  const [executionId, setExecutionId] = useState<string | null>(null)
  const [currentWorkflow, setCurrentWorkflow] = useState<WorkflowDefinition | null>(null)
  const [rightPanelCollapsed, setRightPanelCollapsed] = useState(false)

  // 处理执行开始
  const handleExecutionStart = useCallback((execId: string) => {
    setExecutionId(execId)
    setActiveTab('monitor')
  }, [])

  // 处理工作流保存
  const handleWorkflowSave = useCallback((workflow: WorkflowDefinition) => {
    setCurrentWorkflow(workflow)
  }, [])

  // 右侧面板内容
  const renderRightPanel = () => {
    if (rightPanelCollapsed) {
      return (
        <div className="w-12 flex flex-col items-center py-4 border-l border-gray-200 dark:border-gray-700">
          <button
            onClick={() => setRightPanelCollapsed(false)}
            className="p-2 rounded hover:bg-gray-100 dark:hover:bg-gray-800"
          >
            <ChevronLeft size={18} />
          </button>
          <div className="mt-4 flex flex-col gap-2">
            <button
              onClick={() => { setActiveTab('monitor'); setRightPanelCollapsed(false) }}
              className={`p-2 rounded ${activeTab === 'monitor' ? 'bg-blue-100 text-blue-600 dark:bg-blue-900' : ''}`}
              title="监控"
            >
              <Activity size={18} />
            </button>
            <button
              onClick={() => { setActiveTab('chat'); setRightPanelCollapsed(false) }}
              className={`p-2 rounded ${activeTab === 'chat' ? 'bg-blue-100 text-blue-600 dark:bg-blue-900' : ''}`}
              title="私聊"
            >
              <MessageSquare size={18} />
            </button>
            <button
              onClick={() => { setActiveTab('trace'); setRightPanelCollapsed(false) }}
              className={`p-2 rounded ${activeTab === 'trace' ? 'bg-blue-100 text-blue-600 dark:bg-blue-900' : ''}`}
              title="Trace"
            >
              <GitBranch size={18} />
            </button>
            <button
              onClick={() => { setActiveTab('logs'); setRightPanelCollapsed(false) }}
              className={`p-2 rounded ${activeTab === 'logs' ? 'bg-blue-100 text-blue-600 dark:bg-blue-900' : ''}`}
              title="日志"
            >
              <History size={18} />
            </button>
          </div>
        </div>
      )
    }

    return (
      <div className="w-96 border-l border-gray-200 dark:border-gray-700 flex flex-col">
        {/* 标签栏 */}
        <div className="flex border-b border-gray-200 dark:border-gray-700">
          <button
            onClick={() => setActiveTab('monitor')}
            className={`flex-1 flex items-center justify-center gap-1.5 px-3 py-2.5 text-sm transition-colors ${
              activeTab === 'monitor'
                ? 'border-b-2 border-blue-500 text-blue-600'
                : isDark
                  ? 'text-gray-400 hover:text-gray-200'
                  : 'text-gray-500 hover:text-gray-700'
            }`}
          >
            <Activity size={14} />
            监控
          </button>
          <button
            onClick={() => setActiveTab('chat')}
            className={`flex-1 flex items-center justify-center gap-1.5 px-3 py-2.5 text-sm transition-colors ${
              activeTab === 'chat'
                ? 'border-b-2 border-blue-500 text-blue-600'
                : isDark
                  ? 'text-gray-400 hover:text-gray-200'
                  : 'text-gray-500 hover:text-gray-700'
            }`}
          >
            <MessageSquare size={14} />
            私聊
          </button>
          <button
            onClick={() => setActiveTab('trace')}
            className={`flex-1 flex items-center justify-center gap-1.5 px-3 py-2.5 text-sm transition-colors ${
              activeTab === 'trace'
                ? 'border-b-2 border-blue-500 text-blue-600'
                : isDark
                  ? 'text-gray-400 hover:text-gray-200'
                  : 'text-gray-500 hover:text-gray-700'
            }`}
          >
            <GitBranch size={14} />
            Trace
          </button>
          <button
            onClick={() => setActiveTab('logs')}
            className={`flex-1 flex items-center justify-center gap-1.5 px-3 py-2.5 text-sm transition-colors ${
              activeTab === 'logs'
                ? 'border-b-2 border-blue-500 text-blue-600'
                : isDark
                  ? 'text-gray-400 hover:text-gray-200'
                  : 'text-gray-500 hover:text-gray-700'
            }`}
          >
            <History size={14} />
            日志
          </button>
          <button
            onClick={() => setRightPanelCollapsed(true)}
            className="p-2 hover:bg-gray-100 dark:hover:bg-gray-800"
          >
            <ChevronRight size={18} />
          </button>
        </div>

        {/* 面板内容 */}
        <div className="flex-1 overflow-hidden">
          {activeTab === 'monitor' && (
            <WorkflowMonitor
              executionId={executionId}
            />
          )}
          {activeTab === 'trace' && (
            <WorkflowTrace executionId={executionId} />
          )}
          {activeTab === 'chat' && currentProject && (
            <AgentChat
              executionId={executionId}
              projectId={currentProject.id}
              onInterventionSent={() => setActiveTab('logs')}
            />
          )}
          {activeTab === 'logs' && currentProject && (
            <InterventionLog
              projectId={currentProject.id}
              executionId={executionId || undefined}
            />
          )}
        </div>
      </div>
    )
  }

  if (!currentProject) {
    return (
      <PageLayout title="工作流导演" description="可视化 Agent 协作">
        <div className={`h-full flex items-center justify-center ${isDark ? 'text-gray-400' : 'text-gray-500'}`}>
          <div className="text-center">
            <FolderOpen size={48} className="mx-auto mb-4 opacity-50" />
            <p>请先在侧边栏选择一个项目</p>
          </div>
        </div>
      </PageLayout>
    )
  }

  return (
    <PageLayout
      title="工作流导演"
      description={`${currentProject.name} - 可视化 Agent 协作`}
    >
      <div className="h-[calc(100vh-120px)] flex">
        {/* 左侧：工作流编辑器 */}
        <div className="flex-1 overflow-hidden">
          <WorkflowEditor
            projectId={currentProject.id}
            workflow={currentWorkflow || undefined}
            onExecutionStart={handleExecutionStart}
            onWorkflowSave={handleWorkflowSave}
          />
        </div>

        {/* 右侧：监控/私聊/日志面板 */}
        {renderRightPanel()}
      </div>
    </PageLayout>
  )
}
