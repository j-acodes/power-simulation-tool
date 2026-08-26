import { useState } from 'react'
import type { ReactNode } from 'react'
import '../App.css'
import { reportPdf } from '../api'
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
  const results = useStore((s) => s.results)
  const designMeta = useStore((s) => s.designMeta)
  const [reporting, setReporting] = useState(false)
  const [reportError, setReportError] = useState<string | null>(null)

  /** Download the PDF sizing report. The browser can't be handed a URL — the
   * diagram has to be POSTed — so the response Blob is saved via an object
   * URL. */
  const downloadReport = async () => {
    setReporting(true)
    setReportError(null)
    try {
      const name = designMeta?.name ?? 'PV Plant'
      const blob = await reportPdf(diagram, name)
      const url = URL.createObjectURL(blob)
      const link = document.createElement('a')
      link.href = url
      link.download = `${name}-sizing-report.pdf`
      link.click()
      setTimeout(() => URL.revokeObjectURL(url), 1000)
    } catch (err) {
      setReportError(err instanceof Error ? err.message : String(err))
    } finally {
      setReporting(false)
    }
  }

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
          <button
            type="button"
            onClick={downloadReport}
            disabled={reporting || !results}
            aria-label="Report (PDF)"
            title={results ? 'Download the PDF sizing report' : 'Solve the plant first'}
          >
            {reporting ? 'Building…' : 'Report (PDF)'}
          </button>
          {headerRight}
        </div>
      </header>
      {reportError && <p className="error">Report: {reportError}</p>}
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
