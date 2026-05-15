import { ViewPlugin } from './types'

const registry = new Map<string, ViewPlugin>()

export function registerPlugin(plugin: ViewPlugin) {
  if (registry.has(plugin.id)) {
    console.warn(`[ScriptViz] ViewPlugin "${plugin.id}" already registered, replacing.`)
  }
  registry.set(plugin.id, plugin)
}

export function unregisterPlugin(id: string) {
  registry.delete(id)
}

export function getPlugin(id: string): ViewPlugin | undefined {
  return registry.get(id)
}

export function getAllPlugins(): ViewPlugin[] {
  return Array.from(registry.values())
}

export function getDefaultPlugin(): ViewPlugin | undefined {
  const all = getAllPlugins()
  return all.length > 0 ? all[0] : undefined
}