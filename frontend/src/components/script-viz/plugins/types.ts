import { Node, Edge } from '@xyflow/react'

export type ViewLayout = 'tree' | 'timeline' | 'force' | 'radial' | 'grid' | 'layered' | 'custom'

export interface ViewPluginProps {
  data: AnalysisData
  containerWidth: number
  containerHeight: number
  onNodeClick?: (event: React.MouseEvent, node: Node) => void
  onEdgeClick?: (event: React.MouseEvent, edge: Edge) => void
  onPaneClick?: () => void
  selectedNodeId?: string | null
  highlightedNodeId?: string | null
}

export interface ViewPlugin {
  id: string
  label: string
  icon: string
  component: React.ComponentType<ViewPluginProps>
  defaultLayout: ViewLayout
  description: string
  supportsFiltering: boolean
  supportsExport: boolean
}

export interface AnalysisData {
  project_id: string
  characters: CharacterData[]
  relations: RelationData[]
  scenes: SceneData[]
  foreshadows: ForeshadowData[]
  events: EventData[]
  scene_links: SceneLinkData[]
  foreshadow_links: ForeshadowLinkData[]
}

export interface CharacterData {
  id: string
  name: string
  role_type: string
  core_goal: string
  core_fear: string
  background?: string
  surface_image?: string | null
  true_self?: string | null
  arc_description?: string | null
  status: string
}

export interface RelationData {
  id: string
  char_a_id: string
  char_b_id: string
  relation_type: string
  trust: number
  favor: number
  info_asymmetry?: Record<string, unknown>
  is_hidden?: boolean
  arc_direction?: string
  description?: string
}

export interface SceneData {
  id: string
  scene_code: string
  scene_type: string
  location: string
  emotion_level: number
  narration_preview?: string
  characters_involved?: string[]
  is_wow_moment: boolean
  wow_type?: string
  status: string
  chapter_id?: string | null
}

export interface ForeshadowData {
  id: string
  fs_code: string
  name: string
  fs_type: string
  surface_layer: string
  deep_layer: string
  truth_layer: string
  health: string
  current_status: string
  reinforce_count: number
  plant_scene_id?: string | null
  reveal_scene_id?: string | null
  depends_on?: string[]
  enables?: string[]
}

export interface EventData {
  id: string
  name: string
  scene_id?: string
  type: string
  emotion_impact: number
  chapter_number?: number | null
}

export interface SceneLinkData {
  source: string
  target: string
  strength: number
  type: string
}

export interface ForeshadowLinkData {
  id?: string
  source: string
  target: string
  strength: number
  type: string
  description?: string
}

export interface CharacterFilter {
  roleTypes: string[]
  relationTypes: string[]
  showOnlyMajor: boolean
  searchText: string
}