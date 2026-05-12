import { create } from 'zustand'
import type { Project } from '../api/client'

interface ProjectState {
  currentProject: Project | null
  projects: Project[]
  loading: boolean
  unsavedChanges: boolean
  setCurrentProject: (project: Project | null) => void
  setProjects: (projects: Project[]) => void
  setLoading: (loading: boolean) => void
  setUnsavedChanges: (unsaved: boolean) => void
}

export const useProjectStore = create<ProjectState>((set) => ({
  currentProject: null,
  projects: [],
  loading: false,
  unsavedChanges: false,
  setCurrentProject: (project) => set({ currentProject: project }),
  setProjects: (projects) => set({ projects }),
  setLoading: (loading) => set({ loading }),
  setUnsavedChanges: (unsaved) => set({ unsavedChanges: unsaved }),
}))
