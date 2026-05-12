const API_BASE = import.meta.env.VITE_API_BASE_URL
  || (window.location.hostname === 'localhost' ? '/api' : 'https://yingyoujubenshengcheng.onrender.com/api')

class ApiError extends Error {
  status: number
  detail: string
  constructor(status: number, detail: string) {
    super(detail)
    this.name = 'ApiError'
    this.status = status
    this.detail = detail
  }
}

function extractErrorMessage(error: unknown): string {
  if (typeof error === 'string') return error
  if (Array.isArray(error)) {
    const msgs = error.map((e: any) => {
      const loc = e?.loc?.join('.') || ''
      return loc ? `${loc}: ${e.msg}` : e.msg
    })
    return msgs.join('; ')
  }
  if (error && typeof error === 'object' && 'detail' in error) {
    return extractErrorMessage((error as any).detail)
  }
  if (error && typeof error === 'object' && 'message' in error) {
    return String((error as any).message)
  }
  return String(error || '请求失败')
}

async function request<T>(url: string, options?: RequestInit & { signal?: AbortSignal }): Promise<T> {
  const { signal, ...rest } = options || {}
  const hasBody = rest?.body !== undefined && rest?.body !== null
  const headers: Record<string, string> = {}
  if (hasBody) {
    headers['Content-Type'] = 'application/json'
  }
  let res: Response
  try {
    res = await fetch(`${API_BASE}${url}`, {
      headers: { ...headers, ...rest?.headers as Record<string, string> },
      ...rest,
      signal,
    })
  } catch (e: any) {
    if (e?.name === 'AbortError' || signal?.aborted) {
      const abortErr = new Error('Request aborted') as any
      abortErr.name = 'AbortError'
      abortErr.silent = true
      throw abortErr
    }
    throw new ApiError(0, e?.message || '网络请求失败')
  }
  if (!res.ok) {
    if (res.status === 0) throw new ApiError(0, '请求已取消')
    const errorBody = await res.json().catch(() => ({ detail: '请求失败' }))
    throw new ApiError(res.status, extractErrorMessage(errorBody))
  }
  if (res.status === 204) return undefined as T
  return res.json()
}

export const api = {
  get: <T>(url: string, signal?: AbortSignal) => request<T>(url, { signal }),
  post: <T>(url: string, data?: unknown, signal?: AbortSignal) =>
    request<T>(url, { method: 'POST', body: data ? JSON.stringify(data) : undefined, signal }),
  put: <T>(url: string, data?: unknown, signal?: AbortSignal) =>
    request<T>(url, { method: 'PUT', body: data ? JSON.stringify(data) : undefined, signal }),
  delete: <T>(url: string, signal?: AbortSignal) => request<T>(url, { method: 'DELETE', signal }),
}

// ========== Types ==========

export interface ProjectConfigSchema {
  target_word_count: number
  genre: string
  sub_genre: string
  core_contradiction: string
  theme: string
  tone: string
  chapter_count: number
  min_words_per_chapter: number
  max_words_per_chapter: number
  scenes_per_chapter_min: number
  scenes_per_chapter_max: number
  target_ending_count: number
  max_branch_depth: number
  min_branches_per_choice: number
  max_branches_per_choice: number
  wow_moment_density: number
  min_dialogue_ratio: number
  max_narration_ratio: number
  narrative_pov: string
  writing_style: string
  language_complexity: string
  world_building_depth: number
  character_depth_target: number
  plot_complexity: number
  commercial_fit: string
  target_audience: string
  age_rating: string
  enable_constraint_checking: boolean
  enable_water_detection: boolean
  enable_genre_alignment: boolean
  enable_voice_consistency: boolean
  enable_conflict_tracking: boolean
  enable_satisfaction_tracking: boolean
  custom_evaluation_weights: Record<string, number> | null
  custom_checker_rules: Record<string, unknown> | null
  creator_prompt_template: string
  auditor_prompt_template: string
  language: string
  work_mode: string
  player_count: string
  style: string
  social_structure?: string
  tech_magic?: string
  geography?: string
  history?: string
  culture?: string
  constraints?: string
  impossible?: string
}

export interface Project {
  id: string
  name: string
  description: string
  status: string
  template_id: string | null
  config: ProjectConfigSchema | null
  created_at: string
  updated_at: string
}

export interface ProjectListResponse {
  total: number
  projects: Project[]
}

export interface Character {
  id: string
  project_id: string
  char_code: string
  name: string
  role_type: string | null
  background: string | null
  core_goal: string | null
  core_fear: string | null
  surface_image: string | null
  true_self: string | null
  language_style: string | null
  catchphrase: string | null
  dark_secret: string | null
  arc_description: string | null
  behavior_inevitable: unknown[]
  behavior_never: unknown[]
  behavior_conditional: unknown[]
  status: string
  created_at: string
}

export interface CharacterRelation {
  id: string
  project_id: string
  char_a_id: string
  char_b_id: string
  relation_type: string | null
  trust: number
  favor: number
  description?: string
  info_known_a_about_b: unknown[]
  info_known_b_about_a: unknown[]
  info_asymmetry: Record<string, unknown>
  is_hidden: boolean
  arc_direction: string
  trigger_condition: string | null
  arc_milestones: unknown[]
  updated_at: string
}

export interface Foreshadow {
  id: string
  project_id: string
  fs_code: string
  name: string
  fs_type: string
  foreshadow_tier: string | null
  surface_layer: string | null
  deep_layer: string | null
  truth_layer: string | null
  plant_scene_id: string | null
  reinforce_scenes: unknown[]
  reveal_scene_id: string | null
  wow_factor: string | null
  player_reaction: string | null
  depends_on: unknown[]
  enables: unknown[]
  current_status: string
  reinforce_count: number
  health: string
  wow_plans: unknown[]
  wow_selected: string | null
  worldview_refs: unknown[]
  character_refs: unknown[]
  foreshadow_links: unknown[]
  plant_location: string | null
  reinforce_locations: unknown[]
  reveal_location: string | null
  reclaim_status: string
  created_at: string
}

export interface ForeshadowRelation {
  id: string
  project_id: string
  from_fs_id: string
  to_fs_id: string
  relation_type: string
  description?: string
  created_at: string
}

export interface Scene {
  id: string
  project_id: string
  chapter_id: string | null
  scene_code: string
  scene_type: string | null
  location: string | null
  weather: string | null
  time_start: string | null
  time_end: string | null
  emotion_level: number
  narration: string | null
  dialogue: unknown[]
  actions: unknown[]
  foreshadow_ops: unknown[]
  choices: unknown[]
  causal_chain: unknown | null
  is_wow_moment: boolean
  wow_type: string | null
  wow_spec: string | null
  characters_involved: unknown[]
  status: string
  version: number
  audit_reports: unknown[]
  human_reviewed: boolean
  human_feedback: string | null
  git_commit_hash: string | null
  created_at: string
  updated_at: string
}

export interface Chapter {
  id: string
  project_id: string
  chapter_number: number
  title: string | null
  summary: string | null
  outline: string | null
  core_conflict: string | null
  emotion_target: number
  key_turning_points: unknown[]
  foreshadow_tasks: unknown[]
  focus_characters: unknown[]
  worldview_refs: unknown[]
  branch_structure: string | null
  anchor_scenes: unknown[]
  status: string
  created_at: string
  sections: ChapterSection[]
}

export interface ChapterSection {
  id: string
  project_id: string
  chapter_id: string
  section_number: number
  title: string | null
  word_target: number
  emotion_target: number
  scene_ids: unknown[]
  choices: unknown | null
  foreshadow_tasks: unknown[]
  focus_characters: unknown[]
  branch_type: string
  summary: string | null
  status: string
  created_at: string
  updated_at: string
}

export interface ChoiceDesign {
  id: string
  project_id: string
  section_id: string
  choice_number: number
  text: string
  consequence_direct: string | null
  consequence_indirect: string | null
  consequence_long_term: string | null
  character_impact: unknown[]
  is_hidden: boolean
  hidden_condition: string | null
  moral_alignment: string
  branch_target: string | null
  created_at: string
  updated_at: string
}

// ========== Projects API ==========

export interface ProjectCreatePayload {
  name: string
  description?: string
  template_id?: string
  config?: Partial<ProjectConfigSchema>
}

export interface RecommendConfigResponse {
  target_word_count: number
  scale_tier: [string, string]
  recommendation: {
    chapter_count: number
    min_words_per_chapter: number
    max_words_per_chapter: number
    scenes_per_chapter_min: number
    scenes_per_chapter_max: number
    target_ending_count: number
    max_branch_depth: number
    min_branches_per_choice: number
    max_branches_per_choice: number
    wow_moment_density: number
    world_building_depth: number
    character_depth_target: number
    plot_complexity: number
    min_dialogue_ratio: number
    max_narration_ratio: number
  }
  estimates: {
    total_scenes: number
    wow_moments: number
    branch_nodes: number
  }
  genre_notes: string
  reasoning: string
}

export interface ValidateConfigResponse {
  is_valid: boolean
  message: string
  suggestions: Record<string, number> | null
}

export const projectsApi = {
  list: () => api.get<ProjectListResponse>('/projects'),
  get: (id: string) => api.get<Project>(`/projects/${id}`),
  create: (data: ProjectCreatePayload) => api.post<Project>('/projects', data),
  update: (id: string, data: Partial<Project> & { config?: Partial<ProjectConfigSchema> }) => api.put<Project>(`/projects/${id}`, data),
  delete: (id: string) => api.delete<void>(`/projects/${id}`),
  recommendConfig: (data: { target_word_count: number; genre?: string; work_mode?: string; player_count?: string }) =>
    api.post<RecommendConfigResponse>('/projects/recommend-config', data),
  validateConfig: (data: { target_word_count: number; chapter_count: number; min_words_per_chapter: number; max_words_per_chapter: number; target_ending_count: number; max_branch_depth: number }) =>
    api.post<ValidateConfigResponse>('/projects/validate-config', data),
}

// ========== Characters API ==========

export const charactersApi = {
  list: (projectId: string, params?: { role_type?: string }, signal?: AbortSignal) => {
    const qs = params?.role_type ? `?role_type=${params.role_type}` : ''
    return api.get<Character[]>(`/projects/${projectId}/characters${qs}`, signal)
  },
  get: (projectId: string, charId: string) =>
    api.get<Character>(`/projects/${projectId}/characters/${charId}`),
  create: (projectId: string, data: Partial<Character>) =>
    api.post<Character>(`/projects/${projectId}/characters`, data),
  update: (projectId: string, charId: string, data: Partial<Character>) =>
    api.put<Character>(`/projects/${projectId}/characters/${charId}`, data),
  delete: (projectId: string, charId: string) =>
    api.delete<void>(`/projects/${projectId}/characters/${charId}`),
}

// ========== Relations API ==========

export const relationsApi = {
  list: (projectId: string, signal?: AbortSignal) =>
    api.get<CharacterRelation[]>(`/projects/${projectId}/relations`, signal),
  create: (projectId: string, data: Partial<CharacterRelation>) =>
    api.post<CharacterRelation>(`/projects/${projectId}/relations`, data),
  update: (projectId: string, relId: string, data: Partial<CharacterRelation>) =>
    api.put<CharacterRelation>(`/projects/${projectId}/relations/${relId}`, data),
  delete: (projectId: string, relId: string) =>
    api.delete<void>(`/projects/${projectId}/relations/${relId}`),
}

// ========== Foreshadows API ==========

export const foreshadowsApi = {
  list: (projectId: string, params?: { fs_type?: string; current_status?: string }, signal?: AbortSignal) => {
    const parts: string[] = []
    if (params?.fs_type) parts.push(`fs_type=${params.fs_type}`)
    if (params?.current_status) parts.push(`current_status=${params.current_status}`)
    const qs = parts.length ? `?${parts.join('&')}` : ''
    return api.get<Foreshadow[]>(`/projects/${projectId}/foreshadows${qs}`, signal)
  },
  get: (projectId: string, fsId: string) =>
    api.get<Foreshadow>(`/projects/${projectId}/foreshadows/${fsId}`),
  create: (projectId: string, data: Partial<Foreshadow>) =>
    api.post<Foreshadow>(`/projects/${projectId}/foreshadows`, data),
  update: (projectId: string, fsId: string, data: Partial<Foreshadow>) =>
    api.put<Foreshadow>(`/projects/${projectId}/foreshadows/${fsId}`, data),
  delete: (projectId: string, fsId: string) =>
    api.delete<void>(`/projects/${projectId}/foreshadows/${fsId}`),
  listRelations: (projectId: string, signal?: AbortSignal) =>
    api.get<ForeshadowRelation[]>(`/projects/${projectId}/foreshadows/relations`, signal),
  createRelation: (projectId: string, data: Partial<ForeshadowRelation>) =>
    api.post<ForeshadowRelation>(`/projects/${projectId}/foreshadows/relations`, data),
  updateRelation: (projectId: string, relId: string, data: Partial<ForeshadowRelation>) =>
    api.put<ForeshadowRelation>(`/projects/${projectId}/foreshadows/relations/${relId}`, data),
  deleteRelation: (projectId: string, relId: string) =>
    api.delete<void>(`/projects/${projectId}/foreshadows/relations/${relId}`),
  graph: (projectId: string) =>
    api.get<{ nodes: unknown[]; edges: unknown[] }>(`/projects/${projectId}/foreshadows-graph`),
  health: (projectId: string) =>
    api.get<{ overall_health: string; details: unknown[]; stats: unknown }>(`/projects/${projectId}/foreshadow-health`),
  chemicalReaction: (projectId: string, foreshadowIds?: string[]) =>
    api.post<{ reactions: unknown[]; total_pairs: number; high_synergy_count: number }>(
      `/projects/${projectId}/foreshadow-chemical-reaction`,
      foreshadowIds ? { foreshadow_ids: foreshadowIds } : undefined,
    ),
}

// ========== Scenes API ==========

export const scenesApi = {
  list: (projectId: string, params?: { chapter_id?: string; status?: string }) => {
    const parts: string[] = []
    if (params?.chapter_id) parts.push(`chapter_id=${params.chapter_id}`)
    if (params?.status) parts.push(`status=${params.status}`)
    const qs = parts.length ? `?${parts.join('&')}` : ''
    return api.get<Scene[]>(`/projects/${projectId}/scenes${qs}`)
  },
  get: (projectId: string, sceneId: string) =>
    api.get<Scene>(`/projects/${projectId}/scenes/${sceneId}`),
  create: (projectId: string, data: Partial<Scene>) =>
    api.post<Scene>(`/projects/${projectId}/scenes`, data),
  update: (projectId: string, sceneId: string, data: Partial<Scene>) =>
    api.put<Scene>(`/projects/${projectId}/scenes/${sceneId}`, data),
  delete: (projectId: string, sceneId: string) =>
    api.delete<void>(`/projects/${projectId}/scenes/${sceneId}`),
}

// ========== Chapters API ==========

export const chaptersApi = {
  list: (projectId: string) =>
    api.get<Chapter[]>(`/projects/${projectId}/chapters`),
  get: (projectId: string, chId: string) =>
    api.get<Chapter>(`/projects/${projectId}/chapters/${chId}`),
  create: (projectId: string, data: Partial<Chapter>) =>
    api.post<Chapter>(`/projects/${projectId}/chapters`, data),
  update: (projectId: string, chId: string, data: Partial<Chapter>) =>
    api.put<Chapter>(`/projects/${projectId}/chapters/${chId}`, data),
  delete: (projectId: string, chId: string) =>
    api.delete<void>(`/projects/${projectId}/chapters/${chId}`),
}

// ========== Sections API ==========

export const sectionsApi = {
  list: (projectId: string, chapterId: string) =>
    api.get<ChapterSection[]>(`/projects/${projectId}/chapters/${chapterId}/sections`),
  get: (projectId: string, chapterId: string, sectionId: string) =>
    api.get<ChapterSection>(`/projects/${projectId}/chapters/${chapterId}/sections/${sectionId}`),
  create: (projectId: string, chapterId: string, data: Partial<ChapterSection>) =>
    api.post<ChapterSection>(`/projects/${projectId}/chapters/${chapterId}/sections`, data),
  update: (projectId: string, chapterId: string, sectionId: string, data: Partial<ChapterSection>) =>
    api.put<ChapterSection>(`/projects/${projectId}/chapters/${chapterId}/sections/${sectionId}`, data),
  delete: (projectId: string, chapterId: string, sectionId: string) =>
    api.delete<void>(`/projects/${projectId}/chapters/${chapterId}/sections/${sectionId}`),
}

// ========== Choices API ==========

export const choicesApi = {
  list: (projectId: string, chapterId: string, sectionId: string) =>
    api.get<ChoiceDesign[]>(`/projects/${projectId}/chapters/${chapterId}/sections/${sectionId}/choices`),
  get: (projectId: string, chapterId: string, sectionId: string, choiceId: string) =>
    api.get<ChoiceDesign>(`/projects/${projectId}/chapters/${chapterId}/sections/${sectionId}/choices/${choiceId}`),
  create: (projectId: string, chapterId: string, sectionId: string, data: Partial<ChoiceDesign>) =>
    api.post<ChoiceDesign>(`/projects/${projectId}/chapters/${chapterId}/sections/${sectionId}/choices`, data),
  update: (projectId: string, chapterId: string, sectionId: string, choiceId: string, data: Partial<ChoiceDesign>) =>
    api.put<ChoiceDesign>(`/projects/${projectId}/chapters/${chapterId}/sections/${sectionId}/choices/${choiceId}`, data),
  delete: (projectId: string, chapterId: string, sectionId: string, choiceId: string) =>
    api.delete<void>(`/projects/${projectId}/chapters/${chapterId}/sections/${sectionId}/choices/${choiceId}`),
}

// ========== Export API ==========

export const exportApi = {
  export: async (projectId: string, data: { format: string; chapter_ids?: string[] }) => {
    const res = await fetch(`${API_BASE}/projects/${projectId}/export`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    })
    if (!res.ok) {
      const errorBody = await res.json().catch(() => ({ detail: '导出失败' }))
      throw new ApiError(res.status, extractErrorMessage(errorBody))
    }
    const contentType = res.headers.get('content-type') || ''
    if (contentType.includes('application/json') || contentType.includes('text/markdown') || contentType.includes('text/plain') || contentType.includes('text/csv')) {
      const reader = res.body?.getReader()
      const chunks: Uint8Array[] = []
      if (reader) {
        while (true) {
          const { done, value } = await reader.read()
          if (done) break
          chunks.push(value)
        }
      }
      const totalLength = chunks.reduce((acc, chunk) => acc + chunk.length, 0)
      const combined = new Uint8Array(totalLength)
      let offset = 0
      for (const chunk of chunks) {
        combined.set(chunk, offset)
        offset += chunk.length
      }
      return new Blob([combined], { type: contentType })
    }
    return res.blob()
  },
}

// ========== Pipeline API ==========

export const pipelineApi = {
  getStatus: (projectId: string) =>
    api.get<{
      status: string
      current_phase: number
      current_step: number
      template: string
      error_message: string
      task_results: unknown[]
    }>(`/projects/${projectId}/pipeline/status`),
  advance: (projectId: string) =>
    api.post<{ status: string; phase?: string; message?: string }>(`/projects/${projectId}/pipeline/advance`),
  autoRun: (projectId: string) =>
    api.post<{ status: string; message: string }>(`/projects/${projectId}/pipeline/auto-run`),
  cancel: (projectId: string) =>
    api.post<{ status: string; message: string }>(`/projects/${projectId}/pipeline/cancel`),
  approve: (projectId: string) =>
    api.post<{ status: string }>(`/projects/${projectId}/pipeline/approve`),
  reject: (projectId: string, reason?: string) =>
    api.post<{ status: string; reason: string }>(`/projects/${projectId}/pipeline/reject`, { reason }),
  retry: (projectId: string) =>
    api.post<{ status: string; message: string }>(`/projects/${projectId}/pipeline/retry`),
  resume: (projectId: string) =>
    api.post<{ status: string; message: string }>(`/projects/${projectId}/pipeline/resume`),
  rollback: (projectId: string, phase: number, step: number) =>
    api.post<{ status: string; target_phase: number; target_step: number; message: string }>(`/projects/${projectId}/pipeline/rollback`, { phase, step }),
  templates: () =>
    api.get<{ templates: { name: string; description: string; phases: number }[] }>(`/pipeline/templates`),
  getTemplate: (name: string) =>
    api.get<{ name: string; description: string; phases: Array<{ name: string; human_gate: boolean; steps: Array<{ agent: string; skill: string }> }> }>(`/templates/${encodeURIComponent(name)}`),
}
