import { createContext, useContext, useState, useEffect, ReactNode } from 'react'
import { getProjects, type Project } from '@/api/projects'

interface ProjectContextType {
  currentProject: Project | null
  projects: Project[]
  setCurrentProject: (project: Project | null) => void
  loading: boolean
  refreshProjects: (options?: { forceRefresh?: boolean }) => Promise<void>
}

const ProjectContext = createContext<ProjectContextType | null>(null)

export function ProjectProvider({ children }: { children: ReactNode }) {
  const [projects, setProjects] = useState<Project[]>([])
  const [currentProject, setCurrentProject] = useState<Project | null>(null)
  const [loading, setLoading] = useState(true)

  const refreshProjects = async (options: { forceRefresh?: boolean } = {}) => {
    try {
      const data = await getProjects(undefined, { forceRefresh: options.forceRefresh })
      setProjects(data)

      const urlProjectId = new URLSearchParams(window.location.search).get('project_id')
      const savedProjectId = localStorage.getItem('currentProjectId')
      setCurrentProject((current) => {
        const selectedId = urlProjectId || savedProjectId || current?.id
        if (!selectedId) return null

        const selected = data.find(p => p.id === selectedId)
        if (selected) {
          localStorage.setItem('currentProjectId', selected.id)
          return selected
        }

        localStorage.removeItem('currentProjectId')
        return null
      })
    } catch (error) {
      console.error('Failed to load projects:', error)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    refreshProjects()
  }, [])

  // 保存项目选择到 localStorage
  const handleSetProject = (project: Project | null) => {
    setCurrentProject(project)
    if (project) {
      localStorage.setItem('currentProjectId', project.id)
    } else {
      localStorage.removeItem('currentProjectId')
    }
  }

  return (
    <ProjectContext.Provider value={{
      currentProject,
      projects,
      setCurrentProject: handleSetProject,
      loading,
      refreshProjects,
    }}>
      {children}
    </ProjectContext.Provider>
  )
}

export function useProject() {
  const context = useContext(ProjectContext)
  if (!context) {
    throw new Error('useProject must be used within ProjectProvider')
  }
  return context
}
