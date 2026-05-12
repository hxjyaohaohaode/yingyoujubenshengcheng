import { create } from 'zustand'

export type AgentName = 'creator' | 'auditor' | 'orchestrator' | 'foreshadow' | 'material' | 'state_manager' | '系统'

export type AgentStatusType = 'idle' | 'busy' | 'error' | 'offline'
export type TaskStatus = 'queued' | 'running' | 'retrying' | 'completed' | 'failed' | 'cancelled' | 'timeout' | 'unknown'
export type PipelineRunStatus = 'not_started' | 'running' | 'waiting_human' | 'completed' | 'failed' | 'cancelled'

export interface AgentState {
  name: AgentName
  status: AgentStatusType
  currentTask: string
  lastActive: string
}

export interface AITask {
  taskId: string
  agentName: string
  message: string
  progress: number
  status: TaskStatus
  timestamp: string
}

export interface PipelinePhase {
  name: string
  steps: number
  humanGate: boolean
  currentStep: number
  status: 'pending' | 'running' | 'completed' | 'waiting' | 'failed'
}

export interface PipelineState {
  status: PipelineRunStatus
  currentPhase: string
  currentPhaseIndex: number
  totalPhases: number
  overallProgress: number
  message: string
  phases: PipelinePhase[]
}

interface AITaskState {
  agents: AgentState[]
  activeTasks: AITask[]
  taskHistory: AITask[]
  pipeline: PipelineState | null
  isPipelineRunning: boolean

  updateAgent: (name: string, status: string, currentTask?: string) => void
  addTask: (task: AITask) => void
  updateTask: (taskId: string, updates: Partial<AITask>) => void
  setPipeline: (pipeline: PipelineState | null) => void
  updatePipeline: (updates: Partial<PipelineState>) => void
  setPipelineRunning: (running: boolean) => void
  clearAll: () => void
}

const defaultAgents: AgentState[] = [
  { name: 'creator', status: 'idle', currentTask: '', lastActive: '' },
  { name: 'auditor', status: 'idle', currentTask: '', lastActive: '' },
  { name: 'orchestrator', status: 'idle', currentTask: '', lastActive: '' },
  { name: 'foreshadow', status: 'idle', currentTask: '', lastActive: '' },
  { name: 'material', status: 'idle', currentTask: '', lastActive: '' },
  { name: 'state_manager', status: 'idle', currentTask: '', lastActive: '' },
  { name: '系统', status: 'idle', currentTask: '', lastActive: '' },
]

const MAX_HISTORY = 50

export const useAITaskStore = create<AITaskState>((set) => ({
  agents: defaultAgents,
  activeTasks: [],
  taskHistory: [],
  pipeline: null,
  isPipelineRunning: false,

  updateAgent: (name, status, currentTask) =>
    set((state) => ({
      agents: state.agents.map((a) =>
        a.name === name
          ? { ...a, status: status as AgentStatusType, currentTask: currentTask || a.currentTask, lastActive: new Date().toISOString() }
          : a
      ),
    })),

  addTask: (task) =>
    set((state) => {
      const newActive = [task, ...state.activeTasks.filter(t => t.taskId !== task.taskId)].slice(0, 20)
      return { activeTasks: newActive }
    }),

  updateTask: (taskId, updates) =>
    set((state) => {
      const updatedActive = state.activeTasks.map((t) =>
        t.taskId === taskId ? { ...t, ...updates } : t
      )
      const completedTask = updatedActive.find(
        t => t.taskId === taskId && (t.status === 'completed' || t.status === 'failed' || t.status === 'cancelled' || t.status === 'timeout')
      )
      let newHistory = state.taskHistory
      let newActive = updatedActive
      if (completedTask) {
        newHistory = [completedTask, ...state.taskHistory].slice(0, MAX_HISTORY)
        newActive = updatedActive.filter(t => t.status === 'queued' || t.status === 'running' || t.status === 'retrying')
      }
      return { activeTasks: newActive, taskHistory: newHistory }
    }),

  setPipeline: (pipeline) => set({ pipeline }),

  updatePipeline: (updates) =>
    set((state) => ({
      pipeline: state.pipeline ? { ...state.pipeline, ...updates } : null,
    })),

  setPipelineRunning: (running) => set({ isPipelineRunning: running }),

  clearAll: () => set({
    agents: defaultAgents,
    activeTasks: [],
    taskHistory: [],
    pipeline: null,
    isPipelineRunning: false,
  }),
}))
