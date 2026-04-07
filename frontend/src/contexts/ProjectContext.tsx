import { createContext, useContext, useState, useEffect, ReactNode } from 'react'
import { getProjects, type Project } from '@/api/projects'

interface ProjectContextType {
  currentProject: Project | null
  projects: Project[]
  setCurrentProject: (project: Project | null) => void
  loading: boolean
  refreshProjects: () => Promise<void>
}

const ProjectContext = createContext<ProjectContextType | null>(null)

export function ProjectProvider({ children }: { children: ReactNode }) {
  const [projects, setProjects] = useState<Project[]>([])
  const [currentProject, setCurrentProject] = useState<Project | null>(null)
  const [loading, setLoading] = useState(true)

  const refreshProjects = async () => {
    try {
      const data = await getProjects()
      setProjects(data)
      // 从 localStorage 恢复上次选择的项目
      const savedProjectId = localStorage.getItem('currentProjectId')
      if (savedProjectId) {
        const saved = data.find(p => p.id === savedProjectId)
        if (saved) setCurrentProject(saved)
      }
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
