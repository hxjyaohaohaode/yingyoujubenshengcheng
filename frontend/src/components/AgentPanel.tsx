import { useState, useRef } from 'react'
import {
  Button, Badge, Tag, Progress, Empty,
} from 'antd'
import {
  RobotOutlined, CloseOutlined,
  ThunderboltOutlined, HistoryOutlined,
} from '@ant-design/icons'
import { useAgentStore, AgentStatus } from '../stores/agentStore'
import { useAITaskStore } from '../stores/aiTaskStore'

interface TaskItem {
  id: string
  agent: string
  action: string
  target: string
  progress: number
  status: 'running' | 'queued' | 'done' | 'failed'
  created_at: string
}

const AGENT_ICONS: Record<string, string> = {
  '编排Agent': '📋',
  '创作Agent': '✍️',
  '审计Agent': '🔍',
  '状态Agent': '📊',
  '素材Agent': '🎨',
  '伏笔Agent': '🎯',
  '创意Agent': '💡',
}

export default function AgentPanel() {
  const { agents, taskQueue } = useAgentStore()
  const { activeTasks, taskHistory } = useAITaskStore()
  const [expanded, setExpanded] = useState(false)
  const [showTasks, setShowTasks] = useState(false)
  const [showLogs, setShowLogs] = useState(false)
  const panelRef = useRef<HTMLDivElement>(null)

  const busyAgents = agents.filter(a => a.status === 'busy').length
  const errorAgents = agents.filter(a => a.status === 'error').length
  const onlineAgents = agents.filter(a => a.status !== 'offline').length

  const getStatusColor = (status: AgentStatus['status']) => {
    switch (status) {
      case 'idle': return '#52c41a'
      case 'busy': return '#faad14'
      case 'error': return '#ff4d4f'
      case 'offline': return '#d9d9d9'
    }
  }

  const getStatusLabel = (status: AgentStatus['status']) => {
    switch (status) {
      case 'idle': return '空闲'
      case 'busy': return '处理中'
      case 'error': return '错误'
      case 'offline': return '离线'
    }
  }

  const displayTasks = activeTasks.map(t => ({
    id: t.taskId,
    agent: t.agentName,
    action: t.message,
    target: '',
    progress: t.progress,
    status: (t.status === 'running' ? 'running' : t.status === 'queued' || t.status === 'retrying' ? 'queued' : 'done') as 'running' | 'queued' | 'done' | 'failed',
    created_at: t.timestamp,
  }))
  const runningTask = displayTasks.find(t => t.status === 'running')

  return (
    <div ref={panelRef} className="fixed bottom-4 right-4 z-[999] flex flex-col items-end gap-2">
      {expanded && (
        <div className="w-[340px] bg-white dark:bg-slate-900 border border-gray-200 dark:border-slate-700 rounded-xl shadow-2xl overflow-hidden transition-all animate-fade-in">
          <div className="flex items-center justify-between px-3 py-2.5 border-b border-gray-100 dark:border-slate-700 bg-gradient-to-r from-primary-50 to-blue-50 dark:from-primary-900/20 dark:to-blue-900/10">
            <div className="flex items-center gap-2">
              <RobotOutlined className="text-primary-600" />
              <span className="font-semibold text-sm">Agent 集群</span>
              <Tag className="text-[10px]">{onlineAgents}/7 在线</Tag>
            </div>
            <Button size="small" type="text" icon={<CloseOutlined />} onClick={() => setExpanded(false)} />
          </div>

          <div className="p-2 space-y-1 max-h-[280px] overflow-auto">
            {agents.map(agent => (
              <div key={agent.name} className="flex items-center gap-2 p-1.5 rounded-lg hover:bg-gray-50 dark:hover:bg-slate-800 transition-colors">
                <span className="text-sm">{AGENT_ICONS[agent.name] || '🤖'}</span>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-1.5">
                    <span className="text-xs font-medium">{agent.name}</span>
                    <span
                      className="inline-block w-1.5 h-1.5 rounded-full shrink-0"
                      style={{ backgroundColor: getStatusColor(agent.status) }}
                    />
                    <span className="text-[10px] text-gray-400">{getStatusLabel(agent.status)}</span>
                  </div>
                  {agent.currentTask && (
                    <div className="text-[10px] text-gray-400 truncate mt-0.5">{agent.currentTask}</div>
                  )}
                </div>
                {agent.queueCount > 0 && (
                  <Badge count={agent.queueCount} size="small" className="shrink-0" />
                )}
              </div>
            ))}
          </div>

          <div className="flex border-t border-gray-100 dark:border-slate-700">
            <button
              onClick={() => { setShowTasks(true); setShowLogs(false) }}
              className={`flex-1 py-1.5 text-xs font-medium transition-colors ${showTasks || !showLogs ? 'text-primary-600 border-b-2 border-primary-600' : 'text-gray-400 hover:text-gray-600'}`}
            >
              <ThunderboltOutlined className="mr-1" />任务队列 {taskQueue > 0 && `(${taskQueue})`}
            </button>
            <button
              onClick={() => { setShowLogs(true); setShowTasks(false) }}
              className={`flex-1 py-1.5 text-xs font-medium transition-colors ${showLogs ? 'text-primary-600 border-b-2 border-primary-600' : 'text-gray-400 hover:text-gray-600'}`}
            >
              <HistoryOutlined className="mr-1" />Agent状态
            </button>
          </div>

          {(showTasks || !showLogs) && (
            <div className="max-h-[200px] overflow-auto">
              {displayTasks.length === 0 ? (
                <div className="p-4 text-center"><Empty description="暂无排队任务" image={Empty.PRESENTED_IMAGE_SIMPLE} /></div>
              ) : (
                displayTasks.map(task => (
                  <div key={task.id} className="flex items-center gap-1.5 p-1.5 text-xs border-b border-gray-50 dark:border-slate-800 last:border-0">
                    <span className="text-[10px]">{AGENT_ICONS[task.agent] || '🤖'}</span>
                    <span className="flex-1 truncate">{task.agent} · {task.action}</span>
                    <Progress percent={task.progress} size="small" className="w-[80px]" />
                  </div>
                ))
              )}
            </div>
          )}

          {showLogs && (
            <div className="max-h-[200px] overflow-auto p-2">
              {agents.filter(a => a.status === 'busy' || a.status === 'error').length === 0 ? (
                <Empty description="所有Agent正常运行" image={Empty.PRESENTED_IMAGE_SIMPLE} />
              ) : (
                agents.filter(a => a.status !== 'idle').map(agent => (
                  <div key={agent.name} className="text-xs p-1 text-gray-500">
                    <span className="font-medium">{agent.name}</span>: {agent.currentTask || getStatusLabel(agent.status)}
                  </div>
                ))
              )}
            </div>
          )}
        </div>
      )}

      <Button
        type="primary"
        shape="circle"
        size="large"
        className="shadow-lg hover:scale-105 transition-transform"
        icon={<RobotOutlined />}
        onClick={() => setExpanded(!expanded)}
        style={{
          background: errorAgents > 0 ? '#ef4444' : busyAgents > 0 ? '#f59e0b' : '#3b82f6',
        }}
      >
        {busyAgents > 0 && (
          <Badge count={busyAgents} size="small" className="absolute -top-1 -right-1" />
        )}
      </Button>

      {runningTask && !expanded && (
        <div className="bg-white dark:bg-slate-800 border border-gray-200 dark:border-slate-600 rounded-lg shadow-lg p-2 text-xs max-w-[220px] animate-fade-in">
          <div className="flex items-center gap-1.5 mb-1">
            <span>{AGENT_ICONS[runningTask.agent] || '🤖'}</span>
            <span className="font-medium">{runningTask.agent}</span>
          </div>
          <div className="text-gray-500 mb-1">{runningTask.action}</div>
          <Progress percent={runningTask.progress} size="small" strokeColor="#3b82f6" />
        </div>
      )}
    </div>
  )
}
