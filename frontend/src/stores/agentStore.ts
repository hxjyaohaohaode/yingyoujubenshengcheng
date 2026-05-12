import { create } from 'zustand'

export interface AgentStatus {
  name: string
  status: 'idle' | 'busy' | 'error' | 'offline'
  currentTask?: string
  queueCount: number
}

interface AgentState {
  agents: AgentStatus[]
  taskQueue: number
  setAgents: (agents: AgentStatus[]) => void
  updateAgent: (name: string, updates: Partial<AgentStatus>) => void
  setTaskQueue: (count: number) => void
}

const defaultAgents: AgentStatus[] = [
  { name: 'orchestrator', status: 'idle', queueCount: 0 },
  { name: 'creator', status: 'idle', queueCount: 0 },
  { name: 'auditor', status: 'idle', queueCount: 0 },
  { name: 'state_manager', status: 'idle', queueCount: 0 },
  { name: 'material', status: 'idle', queueCount: 0 },
  { name: 'foreshadow', status: 'idle', queueCount: 0 },
  { name: '系统', status: 'idle', queueCount: 0 },
]

export const useAgentStore = create<AgentState>((set) => ({
  agents: defaultAgents,
  taskQueue: 0,
  setAgents: (agents) => set({ agents }),
  updateAgent: (name, updates) =>
    set((state) => ({
      agents: state.agents.map((a) => (a.name === name ? { ...a, ...updates } : a)),
    })),
  setTaskQueue: (count) => set({ taskQueue: count }),
}))