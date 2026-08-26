import { useState } from 'react'
import type { ReactNode } from 'react'
import '../App.css'
import { autoArrange } from '../canvas/autoArrange'
import { Editor } from '../canvas/Editor'
import { SeedWizard } from '../components/SeedWizard'
import { EXAMPLE_DIAGRAM } from '../example'
import { useAutoSolve } from '../hooks/useAutoSolve'
import { IssuesBanner } from '../panels/IssuesBanner'
import { Inspector } from '../panels/Inspector'
import { Palette } from '../panels/Palette'
import { ResultsSummary } from '../panels/ResultsSummary'
import { SettingsPanel } from '../panels/SettingsPanel'
import { EMPTY_DIAGRAM, useStore } from '../store'

interface EditorViewProps {
  title: ReactNode
  /** Rendered before the title, e.g. a back-to-projects link. */
  headerLeft?: ReactNode
  /** Rendered after the default Load/Clear/Settings buttons, e.g. Save. */
  headerRight?: ReactNode
}

/** The diagram editor shell — canvas, palette, inspector, settings and
 * results overlay — shared byte-for-byte between the scratch page and the
 * persisted design editor. Only the header's title/actions differ between
 * them, so those are the only customization points. */
export function EditorView({ title, headerLeft, headerRight }: EditorViewProps) {
  useAutoSolve()
  const [showSettings, setShowSettings] = useState(false)
  const [showSeedWizard, setShowSeedWizard] = useState(false)
  const loadDiagram = useStore((s) => s.loadDiagram)
  const diagram = useStore((s) => s.diagram)
  const moveNodes = useStore((s) => s.moveNodes)
  return (
    <div className="app">
      <header className="app-header">
        <div className="app-header-title">
          {headerLeft}
          <h1>{title}</h1>
        </div>
        <div className="app-header-actions">
          <button type="button" onClick={() => setShowSeedWizard(true)}>
            Seed from POC target…
          </button>
          <button type="button" onClick={() => loadDiagram(EXAMPLE_DIAGRAM)}>
            Load example plant
          </button>
          <button type="button" onClick={() => moveNodes(autoArrange(diagram))}>
            Auto-arrange
          </button>
          <button type="button" onClick={() => loadDiagram(EMPTY_DIAGRAM)}>
            Clear
          </button>
          <button type="button" onClick={() => setShowSettings((v) => !v)}>
            Settings
          </button>
          {headerRight}
        </div>
      </header>
      {showSeedWizard && <SeedWizard onClose={() => setShowSeedWizard(false)} />}
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
