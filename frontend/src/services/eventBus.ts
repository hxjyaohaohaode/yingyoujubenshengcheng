type EventHandler = (payload: unknown) => void

const handlers = new Map<string, Set<EventHandler>>()

export const eventBus = {
  on(event: string, handler: EventHandler): () => void {
    if (!handlers.has(event)) {
      handlers.set(event, new Set())
    }
    handlers.get(event)!.add(handler)
    return () => {
      handlers.get(event)?.delete(handler)
    }
  },

  emit(event: string, payload?: unknown): void {
    const set = handlers.get(event)
    if (!set) return
    set.forEach((fn) => {
      try { fn(payload) } catch { /* swallow */ }
    })
  },

  off(event: string, handler: EventHandler): void {
    handlers.get(event)?.delete(handler)
  },
}

export const DataEvents = {
  SCENE_CREATED: 'data:scene-created',
  SCENE_UPDATED: 'data:scene-updated',
  SCENE_DELETED: 'data:scene-deleted',
  SCENE_FINALIZED: 'data:scene-finalized',
  CHAPTER_CREATED: 'data:chapter-created',
  CHAPTER_UPDATED: 'data:chapter-updated',
  CHAPTER_DELETED: 'data:chapter-deleted',
  CHARACTER_CREATED: 'data:character-created',
  CHARACTER_UPDATED: 'data:character-updated',
  CHARACTER_DELETED: 'data:character-deleted',
  RELATION_CREATED: 'data:relation-created',
  RELATION_UPDATED: 'data:relation-updated',
  RELATION_DELETED: 'data:relation-deleted',
  FORESHADOW_CREATED: 'data:foreshadow-created',
  FORESHADOW_UPDATED: 'data:foreshadow-updated',
  FORESHADOW_DELETED: 'data:foreshadow-deleted',
  PROJECT_SWITCHED: 'data:project-switched',
  PROJECT_CONFIG_UPDATED: 'data:project-config-updated',
  WORLD_CONFIG_UPDATED: 'data:world-config-updated',
  AI_GENERATION_STARTED: 'ai:generation-started',
  AI_GENERATION_COMPLETED: 'ai:generation-completed',
  AI_AUDIT_STARTED: 'ai:audit-started',
  AI_AUDIT_COMPLETED: 'ai:audit-completed',
  PIPELINE_ADVANCED: 'pipeline:advanced',
  PIPELINE_STATUS_CHANGED: 'pipeline:status-changed',
} as const
