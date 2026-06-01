/**
 * Dev Project slice — owns: currentProjectId, projects[].
 * Primary writer: task W3.
 *
 * New code should import from this store directly rather than via the dev-store facade.
 */
import { create } from "zustand";
import { persist } from "zustand/middleware";

export interface DevProject {
  id: string;
  name: string;
  repoUrl?: string;
  localPath?: string;
}

export interface DevProjectState {
  currentProjectId: string | null;
  projects: DevProject[];

  setCurrentProjectId: (id: string | null) => void;
  setProjects: (projects: DevProject[]) => void;
  addProject: (project: DevProject) => void;
  removeProject: (id: string) => void;
}

export const useDevProjectStore = create<DevProjectState>()(
  persist(
    (set) => ({
      currentProjectId: null,
      projects: [],

      setCurrentProjectId: (id) => set({ currentProjectId: id }),
      setProjects: (projects) => set({ projects }),
      addProject: (project) =>
        set((s) => ({ projects: [...s.projects, project] })),
      removeProject: (id) =>
        set((s) => ({
          projects: s.projects.filter((p) => p.id !== id),
          currentProjectId: s.currentProjectId === id ? null : s.currentProjectId,
        })),
    }),
    {
      name: "memex-dev-project-store",
    }
  )
);
