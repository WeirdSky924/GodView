import { Routes, Route } from 'react-router-dom'
import Layout from './components/Layout'
import Dashboard from './pages/Dashboard'
import Characters from './pages/Characters'
import CharacterVoice from './pages/CharacterVoice'
import Worlds from './pages/Worlds'
import Lore from './pages/Lore'
import Plots from './pages/Plots'
import Hooks from './pages/Hooks'
import Interventions from './pages/Interventions'
import ReaderSimulator from './pages/ReaderSimulator'
import Visualizer from './pages/Visualizer'
import ChapterEvaluator from './pages/ChapterEvaluator'
import Director from './pages/Director'
import NovelView from './pages/NovelView'
import Settings from './pages/Settings'
import DiffTool from './pages/DiffTool'
import WorldView from './pages/WorldView'
import Bootstrap from './pages/Bootstrap'
import ProjectSetup from './pages/ProjectSetup'
import ObservationMode from './pages/ObservationMode'
import Skills from './pages/Skills'
import Prompts from './pages/Prompts'
import AgentTemplates from './pages/AgentTemplates'
import WritingRules from './pages/WritingRules'

function App() {
  return (
    <Layout>
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
      </Routes>
    </Layout>
  )
}

export default App
