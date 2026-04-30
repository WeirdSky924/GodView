import { Suspense, lazy } from 'react'
import { Routes, Route } from 'react-router-dom'
import Layout from './components/Layout'

const Dashboard = lazy(() => import('./pages/Dashboard'))
const Characters = lazy(() => import('./pages/Characters'))
const CharacterVoice = lazy(() => import('./pages/CharacterVoice'))
const Worlds = lazy(() => import('./pages/Worlds'))
const Lore = lazy(() => import('./pages/Lore'))
const Plots = lazy(() => import('./pages/Plots'))
const Hooks = lazy(() => import('./pages/Hooks'))
const Interventions = lazy(() => import('./pages/Interventions'))
const ReaderSimulator = lazy(() => import('./pages/ReaderSimulator'))
const Visualizer = lazy(() => import('./pages/Visualizer'))
const ChapterEvaluator = lazy(() => import('./pages/ChapterEvaluator'))
const Director = lazy(() => import('./pages/Director'))
const NovelView = lazy(() => import('./pages/NovelView'))
const Settings = lazy(() => import('./pages/Settings'))
const DiffTool = lazy(() => import('./pages/DiffTool'))
const WorldMap = lazy(() => import('./pages/WorldMap'))
const WorldView = lazy(() => import('./pages/WorldView'))
const Bootstrap = lazy(() => import('./pages/Bootstrap'))
const ProjectSetup = lazy(() => import('./pages/ProjectSetup'))
const ObservationMode = lazy(() => import('./pages/ObservationMode'))
const Skills = lazy(() => import('./pages/Skills'))
const Prompts = lazy(() => import('./pages/Prompts'))
const AgentTemplates = lazy(() => import('./pages/AgentTemplates'))
const WritingRules = lazy(() => import('./pages/WritingRules'))
const Outlines = lazy(() => import('./pages/Outlines'))

function RouteFallback() {
  return (
    <div className="flex min-h-[50vh] items-center justify-center text-sm text-gray-500">
      页面加载中...
    </div>
  )
}

function App() {
  return (
    <Layout>
      <Suspense fallback={<RouteFallback />}>
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/characters" element={<Characters />} />
          <Route path="/character-voice" element={<CharacterVoice />} />
          <Route path="/worlds" element={<Worlds />} />
          <Route path="/lore" element={<Lore />} />
          <Route path="/plots" element={<Plots />} />
          <Route path="/hooks" element={<Hooks />} />
          <Route path="/interventions" element={<Interventions />} />
          <Route path="/simulator" element={<ReaderSimulator />} />
          <Route path="/visualize" element={<Visualizer />} />
          <Route path="/chapter-evaluator" element={<ChapterEvaluator />} />
          <Route path="/director" element={<Director />} />
          <Route path="/novel" element={<NovelView />} />
          <Route path="/diff" element={<DiffTool />} />
          <Route path="/world-map" element={<WorldMap />} />
          <Route path="/world-view" element={<WorldView />} />
          <Route path="/settings" element={<Settings />} />
          <Route path="/bootstrap" element={<Bootstrap />} />
          <Route path="/bootstrap/:sessionId" element={<Bootstrap />} />
          <Route path="/project-setup" element={<ProjectSetup />} />
          <Route path="/observation" element={<ObservationMode />} />
          <Route path="/skills" element={<Skills />} />
          <Route path="/prompts" element={<Prompts />} />
          <Route path="/agent-templates" element={<AgentTemplates />} />
          <Route path="/writing-rules" element={<WritingRules />} />
          <Route path="/outlines" element={<Outlines />} />
        </Routes>
      </Suspense>
    </Layout>
  )
}

export default App
