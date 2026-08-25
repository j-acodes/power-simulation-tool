import { useState } from 'react'
import './App.css'
import { Editor } from './canvas/Editor'
import { EXAMPLE_DIAGRAM } from './example'
import { useAutoSolve } from './hooks/useAutoSolve'
import { IssuesBanner } from './panels/IssuesBanner'
import { Inspector } from './panels/Inspector'
import { Palette } from './panels/Palette'
import { ResultsSummary } from './panels/ResultsSummary'
import { SettingsPanel } from './panels/SettingsPanel'
import { EMPTY_DIAGRAM, useStore } from './store'

function App() {
  useAutoSolve()
  const [showSettings, setShowSettings] = useState(false)
  const loadDiagram = useStore((s) => s.loadDiagram)

  return (
    <div className="app">
      <header className="app-header">
        <h1>PV Plant Sizing — Diagram Editor</h1>
        <div className="app-header-actions">
          <button type="button" onClick={() => loadDiagram(EXAMPLE_DIAGRAM)}>
            Load example plant
          </button>
          <button type="button" onClick={() => loadDiagram(EMPTY_DIAGRAM)}>
            Clear
          </button>
          <button type="button" onClick={() => setShowSettings((v) => !v)}>
            Settings
          </button>
        </div>
      </header>
      <IssuesBanner />
      <div className="app-body">
        <Palette />
        <div className="canvas-area">
          <Editor />
          {showSettings && (
            <div className="settings-overlay">
              <SettingsPanel />
            </div>
          )}
          <div className="results-overlay">
            <ResultsSummary />
          </div>
        </div>
        <Inspector />
      </div>
    </div>
  )
}

export default App
