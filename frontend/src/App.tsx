import { Routes, Route } from 'react-router-dom'
import Layout from './components/Layout'
import Dashboard from './pages/Dashboard'
import Characters from './pages/Characters'
import CharacterVoice from './pages/CharacterVoice'
import Worlds from './pages/Worlds'
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

function App() {
  return (
    <Layout>
      <Routes>
        <Route path="/" element={<Dashboard />} />
        <Route path="/characters" element={<Characters />} />
        <Route path="/character-voice" element={<CharacterVoice />} />
        <Route path="/worlds" element={<Worlds />} />
        <Route path="/plots" element={<Plots />} />
        <Route path="/hooks" element={<Hooks />} />
        <Route path="/interventions" element={<Interventions />} />
        <Route path="/simulator" element={<ReaderSimulator />} />
        <Route path="/visualize" element={<Visualizer />} />
        <Route path="/chapter-evaluator" element={<ChapterEvaluator />} />
        <Route path="/director" element={<Director />} />
        <Route path="/novel" element={<NovelView />} />
        <Route path="/diff" element={<DiffTool />} />
        <Route path="/settings" element={<Settings />} />
      </Routes>
    </Layout>
  )
}

export default App
