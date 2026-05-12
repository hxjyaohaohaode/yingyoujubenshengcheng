import { useEffect, useRef } from 'react'
import { useWebSocket } from '../hooks/useWebSocket'
import { useProjectStore } from '../stores/projectStore'
import { useAgentStore } from '../stores/agentStore'
import { useAITaskStore } from '../stores/aiTaskStore'
import { useQueryClient } from '@tanstack/react-query'
import { eventBus, DataEvents } from './eventBus'

export default function GlobalWebSocket() {
  const currentProject = useProjectStore((s) => s.currentProject)
  const updateAgent = useAgentStore((s) => s.updateAgent)
  const updateAIAgent = useAITaskStore((s) => s.updateAgent)
  const addTask = useAITaskStore((s) => s.addTask)
  const updateTask = useAITaskStore((s) => s.updateTask)
  const setPipeline = useAITaskStore((s) => s.setPipeline)
  const updatePipeline = useAITaskStore((s) => s.updatePipeline)
  const setPipelineRunning = useAITaskStore((s) => s.setPipelineRunning)
  const queryClient = useQueryClient()
  const queryClientRef = useRef(queryClient)
  queryClientRef.current = queryClient
  const prevProjectIdRef = useRef<string | null>(null)

  const { connected } = useWebSocket(currentProject?.id || '', {
    onMessage(data: any) {
      if (!data || typeof data !== 'object') return

      switch (data.type) {

        case 'agent_status':
        case 'agent_update':
          if (data.agent_name && data.status) {
            updateAgent(data.agent_name, {
              status: data.status,
              currentTask: data.current_task || undefined,
            })
            updateAIAgent(data.agent_name, data.status, data.current_task)
          }
          break

        case 'task_progress':
          if (data.task_id) {
            const taskData = {
              taskId: data.task_id,
              agentName: data.agent_name || '系统',
              message: data.message || '',
              progress: data.progress || 0,
              status: data.status || 'running',
              timestamp: data.timestamp || new Date().toISOString(),
            }

            if (data.status === 'running' || data.status === 'queued') {
              addTask(taskData)
            } else {
              updateTask(data.task_id, {
                progress: data.progress,
                status: data.status,
                message: data.message,
              })
            }
          }

          if (data.task_name || data.agent_name) {
            updateAgent(data.agent_name || '系统', {
              status: 'busy',
              currentTask: data.task_name || data.message || undefined,
            } as any)
          }
          break

        case 'pipeline_progress':
          {
            const existingPipeline = useAITaskStore.getState().pipeline
            const phaseIndex = data.phase_index ?? data.current_phase_index ?? -1

            if (!existingPipeline || existingPipeline.phases.length === 0) {
              if (data.phases && data.phases.length > 0) {
                setPipeline({
                  status: data.status === 'cancelled' ? 'cancelled' : data.status === 'completed' ? 'completed' : data.status === 'waiting_human' ? 'waiting_human' : data.status === 'failed' ? 'failed' : 'running',
                  currentPhase: data.phase || '',
                  currentPhaseIndex: phaseIndex >= 0 ? phaseIndex : 0,
                  totalPhases: data.phases.length,
                  overallProgress: data.progress || 0,
                  message: data.message || '',
                  phases: data.phases.map((p: any, i: number) => ({
                    name: p.name,
                    steps: p.steps || (p.steps_list ? p.steps_list.length : 1),
                    humanGate: p.human_gate || false,
                    currentStep: 0,
                    status: i < (phaseIndex >= 0 ? phaseIndex : 0) ? 'completed' as const : i === (phaseIndex >= 0 ? phaseIndex : 0) ? 'running' as const : 'pending' as const,
                  })),
                })
              } else {
                setPipeline({
                  status: data.status === 'cancelled' ? 'cancelled' : data.status === 'completed' ? 'completed' : data.status === 'waiting_human' ? 'waiting_human' : data.status === 'failed' ? 'failed' : 'running',
                  currentPhase: data.phase || '',
                  currentPhaseIndex: phaseIndex >= 0 ? phaseIndex : 0,
                  totalPhases: data.total_phases || 4,
                  overallProgress: data.progress || 0,
                  message: data.message || '',
                  phases: [],
                })
              }
              setPipelineRunning(data.status === 'running' || data.status === 'waiting_human')
            } else {
              let phaseIdx = phaseIndex >= 0 ? phaseIndex : existingPipeline.phases.findIndex(p => p.name === data.phase)
              if (phaseIdx < 0) phaseIdx = existingPipeline.currentPhaseIndex || 0

              const updatedPhases = existingPipeline.phases.map((p, i) => {
                if (i < phaseIdx) return { ...p, status: 'completed' as const }
                if (i === phaseIdx) return { ...p, status: data.status === 'running' ? 'running' as const : data.status === 'completed' ? 'completed' as const : data.status === 'waiting_human' ? 'waiting' as const : data.status === 'failed' ? 'failed' as const : 'running' as const, currentStep: data.step_index || p.currentStep }
                return p
              })

              updatePipeline({
                status: data.status === 'cancelled' ? 'cancelled' : data.status === 'completed' ? 'completed' : data.status === 'waiting_human' ? 'waiting_human' : data.status === 'failed' ? 'failed' : 'running',
                currentPhase: data.phase || existingPipeline.currentPhase,
                currentPhaseIndex: phaseIdx,
                overallProgress: data.progress ?? existingPipeline.overallProgress,
                message: data.message || existingPipeline.message,
                phases: updatedPhases,
              })

              if (data.status === 'completed' || data.status === 'cancelled' || data.status === 'failed') {
                setPipelineRunning(false)
              }
            }

            eventBus.emit(DataEvents.PIPELINE_STATUS_CHANGED, data)
          }
          break

        case 'scene_created':
          queryClientRef.current.invalidateQueries({ queryKey: ['scenes'] })
          queryClientRef.current.invalidateQueries({ queryKey: ['dashboard'] })
          eventBus.emit(DataEvents.SCENE_CREATED, { sceneId: data.entity_id })
          break

        case 'scene_updated':
          queryClientRef.current.invalidateQueries({ queryKey: ['scenes'] })
          queryClientRef.current.invalidateQueries({ queryKey: ['dashboard'] })
          eventBus.emit(DataEvents.SCENE_UPDATED, { sceneId: data.entity_id })
          break

        case 'scene_deleted':
          queryClientRef.current.invalidateQueries({ queryKey: ['scenes'] })
          queryClientRef.current.invalidateQueries({ queryKey: ['dashboard'] })
          eventBus.emit(DataEvents.SCENE_DELETED, { sceneId: data.entity_id })
          break

        case 'scene_finalized':
          queryClientRef.current.invalidateQueries({ queryKey: ['scenes'] })
          queryClientRef.current.invalidateQueries({ queryKey: ['dashboard'] })
          eventBus.emit(DataEvents.SCENE_FINALIZED, { sceneId: data.entity_id })
          break

        case 'chapter_created':
          queryClientRef.current.invalidateQueries({ queryKey: ['chapters'] })
          queryClientRef.current.invalidateQueries({ queryKey: ['dashboard'] })
          eventBus.emit(DataEvents.CHAPTER_CREATED, { chapterId: data.entity_id })
          break

        case 'chapter_updated':
          queryClientRef.current.invalidateQueries({ queryKey: ['chapters'] })
          queryClientRef.current.invalidateQueries({ queryKey: ['dashboard'] })
          eventBus.emit(DataEvents.CHAPTER_UPDATED, { chapterId: data.entity_id })
          break

        case 'chapter_deleted':
          queryClientRef.current.invalidateQueries({ queryKey: ['chapters'] })
          queryClientRef.current.invalidateQueries({ queryKey: ['dashboard'] })
          eventBus.emit(DataEvents.CHAPTER_DELETED, { chapterId: data.entity_id })
          break

        case 'character_created':
          queryClientRef.current.invalidateQueries({ queryKey: ['characters'] })
          queryClientRef.current.invalidateQueries({ queryKey: ['dashboard'] })
          eventBus.emit(DataEvents.CHARACTER_CREATED, { characterId: data.entity_id })
          break

        case 'character_updated':
          queryClientRef.current.invalidateQueries({ queryKey: ['characters'] })
          queryClientRef.current.invalidateQueries({ queryKey: ['dashboard'] })
          eventBus.emit(DataEvents.CHARACTER_UPDATED, { characterId: data.entity_id })
          break

        case 'character_deleted':
          queryClientRef.current.invalidateQueries({ queryKey: ['characters'] })
          queryClientRef.current.invalidateQueries({ queryKey: ['dashboard'] })
          eventBus.emit(DataEvents.CHARACTER_DELETED, { characterId: data.entity_id })
          break

        case 'relation_created':
          queryClientRef.current.invalidateQueries({ queryKey: ['relations'] })
          queryClientRef.current.invalidateQueries({ queryKey: ['dashboard'] })
          eventBus.emit(DataEvents.RELATION_CREATED, { relationId: data.entity_id })
          break

        case 'relation_updated':
          queryClientRef.current.invalidateQueries({ queryKey: ['relations'] })
          queryClientRef.current.invalidateQueries({ queryKey: ['dashboard'] })
          eventBus.emit(DataEvents.RELATION_UPDATED, { relationId: data.entity_id })
          break

        case 'relation_deleted':
          queryClientRef.current.invalidateQueries({ queryKey: ['relations'] })
          queryClientRef.current.invalidateQueries({ queryKey: ['dashboard'] })
          eventBus.emit(DataEvents.RELATION_DELETED, { relationId: data.entity_id })
          break

        case 'foreshadow_created':
          queryClientRef.current.invalidateQueries({ queryKey: ['foreshadows'] })
          queryClientRef.current.invalidateQueries({ queryKey: ['dashboard'] })
          eventBus.emit(DataEvents.FORESHADOW_CREATED, { foreshadowId: data.entity_id })
          break

        case 'foreshadow_updated':
          queryClientRef.current.invalidateQueries({ queryKey: ['foreshadows'] })
          queryClientRef.current.invalidateQueries({ queryKey: ['dashboard'] })
          eventBus.emit(DataEvents.FORESHADOW_UPDATED, { foreshadowId: data.entity_id })
          break

        case 'foreshadow_deleted':
          queryClientRef.current.invalidateQueries({ queryKey: ['foreshadows'] })
          queryClientRef.current.invalidateQueries({ queryKey: ['dashboard'] })
          eventBus.emit(DataEvents.FORESHADOW_DELETED, { foreshadowId: data.entity_id })
          break

        case 'pipeline_status':
          queryClientRef.current.invalidateQueries({ queryKey: ['dashboard'] })
          eventBus.emit(DataEvents.PIPELINE_STATUS_CHANGED, data)
          break

        case 'world_config_updated':
          queryClientRef.current.invalidateQueries({ queryKey: ['dashboard'] })
          eventBus.emit(DataEvents.WORLD_CONFIG_UPDATED, data)
          break

        case 'notification':
          break

        default:
          break
      }
    },
  })

  useEffect(() => {
    if (currentProject?.id && currentProject.id !== prevProjectIdRef.current) {
      eventBus.emit(DataEvents.PROJECT_SWITCHED, { projectId: currentProject.id })
      queryClientRef.current.invalidateQueries({ queryKey: ['dashboard', currentProject.id] })
      queryClientRef.current.invalidateQueries({ queryKey: ['pipeline', currentProject.id] })
    }
    prevProjectIdRef.current = currentProject?.id || null
  }, [currentProject?.id])

  return null
}
