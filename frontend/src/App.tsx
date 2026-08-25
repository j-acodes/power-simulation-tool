import { Route, Routes } from 'react-router-dom'
import { DisplayNameGate } from './components/DisplayName'
import { DesignEditorPage } from './pages/DesignEditorPage'
import { ProjectsPage } from './pages/ProjectsPage'
import { ScratchPage } from './pages/ScratchPage'

function App() {
  return (
    <DisplayNameGate>
      <Routes>
        <Route path="/" element={<ProjectsPage />} />
        <Route path="/design/:id" element={<DesignEditorPage />} />
        <Route path="/scratch" element={<ScratchPage />} />
      </Routes>
    </DisplayNameGate>
  )
}

export default App
