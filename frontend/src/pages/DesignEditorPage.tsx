import { useEffect, useRef, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { ConflictError, createDesign, getDesign, updateDesign } from '../api'
import { ConflictDialog } from '../components/ConflictDialog'
import { DisplayNameControl } from '../components/DisplayName'
import { ModalShell, usePromptDialog } from '../components/Modal'
import { useStore } from '../store'
import type { DesignFull } from '../types'
import { EditorView } from './EditorView'

/** `/design/:id` — GETs the design on mount, loads its payload into the
 * shared editor store, and adds a Save button (PUT with optimistic locking)
 * with a dirty indicator and a 409 conflict dialog. Never silently
 * overwrites a concurrent edit. */
export function DesignEditorPage() {
  const { id } = useParams<{ id: string }>()
  const designId = Number(id)
  const navigate = useNavigate()

  const diagram = useStore((s) => s.diagram)
  const designMeta = useStore((s) => s.designMeta)
  const dirty = useStore((s) => s.diagram !== s.savedDiagramRef)
  const displayName = useStore((s) => s.displayName)
  const loadDesign = useStore((s) => s.loadDesign)
  const markSaved = useStore((s) => s.markSaved)

  const [loadError, setLoadError] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)
  const [saveError, setSaveError] = useState<string | null>(null)
  const [conflict, setConflict] = useState<DesignFull | null>(null)
  const { prompt, dialog: promptDialog } = usePromptDialog()
  const [leaving, setLeaving] = useState(false)
  // Needed for "save as new design" (POST target); not part of designMeta's
  // {id, name, version} shape, so it's kept as page-local state instead.
  const projectIdRef = useRef<number | null>(null)

  useEffect(() => {
    setLoadError(null)
    setConflict(null)
    getDesign(designId)
      .then((design) => {
        projectIdRef.current = design.project_id
        loadDesign(design.payload, { id: design.id, name: design.name, version: design.version })
      })
      .catch((err: unknown) => setLoadError(String(err)))
  }, [designId, loadDesign])

  /** Tab close / reload / external link — the browser shows its own generic
   * "leave site?" prompt; in-app navigation is guarded by handleLeave. */
  useEffect(() => {
    if (!dirty) return
    const warn = (e: BeforeUnloadEvent) => {
      e.preventDefault()
      e.returnValue = ''
    }
    window.addEventListener('beforeunload', warn)
    return () => window.removeEventListener('beforeunload', warn)
  }, [dirty])

  /** Back to the projects list: ask first if the diagram has unsaved edits
   * (nothing else persists them — there is no autosave). */
  const handleLeave = (e: React.MouseEvent) => {
    if (!dirty) return
    e.preventDefault()
    setLeaving(true)
  }

  /** True when the design was written; false on a conflict or a save error, so
   * callers can keep the user on the page to deal with it. */
  const handleSave = async (): Promise<boolean> => {
    if (!designMeta) return false
    setSaving(true)
    setSaveError(null)
    try {
      const saved = await updateDesign(designMeta.id, {
        payload: diagram,
        version: designMeta.version,
        last_edited_by: displayName ?? 'Anonymous',
      })
      markSaved(saved.version)
      return true
    } catch (err) {
      if (err instanceof ConflictError) {
        setConflict(err.design)
      } else {
        setSaveError(String(err))
      }
      return false
    } finally {
      setSaving(false)
    }
  }

  const handleSaveAndLeave = async () => {
    if (await handleSave()) navigate('/')
    // Otherwise the conflict dialog or the header's error takes over — get out
    // of its way and let the user decide what to do next.
    else setLeaving(false)
  }

  const handleReloadTheirs = () => {
    if (!conflict) return
    loadDesign(conflict.payload, { id: conflict.id, name: conflict.name, version: conflict.version })
    setConflict(null)
  }

  const handleSaveAsNew = async () => {
    if (!conflict || projectIdRef.current == null) return
    const name = await prompt({ title: 'Save as new design', label: 'Design name', initialValue: `${conflict.name} (copy)` })
    if (!name) return
    try {
      const created = await createDesign(projectIdRef.current, {
        name,
        payload: diagram,
        last_edited_by: displayName ?? 'Anonymous',
      })
      setConflict(null)
      navigate(`/design/${created.id}`)
    } catch (err) {
      setSaveError(String(err))
    }
  }

  if (loadError) {
    return (
      <div className="app">
        <p className="error">Could not load design: {loadError}</p>
        <Link to="/">← Back to projects</Link>
      </div>
    )
  }

  if (!designMeta || designMeta.id !== designId) {
    return (
      <div className="app">
        <p className="panel-hint">Loading design…</p>
      </div>
    )
  }

  return (
    <>
      <EditorView
        title={
          <>
            {designMeta.name}
            {dirty && <span className="dirty-dot" title="Unsaved changes" />}
          </>
        }
        headerLeft={
          <Link to="/" className="header-link" onClick={handleLeave}>
            ← Projects
          </Link>
        }
        headerRight={
          <>
            {saveError && <span className="error inline">{saveError}</span>}
            <button type="button" onClick={handleSave} disabled={saving || !dirty}>
              {saving ? 'Saving…' : 'Save'}
            </button>
            <DisplayNameControl />
          </>
        }
      />
      {conflict && (
        <ConflictDialog
          serverDesign={conflict}
          onReloadTheirs={handleReloadTheirs}
          onSaveAsNew={handleSaveAsNew}
          onCancel={() => setConflict(null)}
        />
      )}
      {leaving && (
        <ModalShell onEscape={() => setLeaving(false)}>
          <h2>Unsaved changes</h2>
          <p className="panel-hint">
            "{designMeta.name}" has changes that haven't been saved.
          </p>
          <div className="modal-actions">
            <button type="button" onClick={() => setLeaving(false)}>
              Stay
            </button>
            <button type="button" className="danger" onClick={() => navigate('/')}>
              Leave without saving
            </button>
            <button type="button" className="btn-primary" onClick={handleSaveAndLeave} disabled={saving}>
              {saving ? 'Saving…' : 'Save and leave'}
            </button>
          </div>
        </ModalShell>
      )}
      {promptDialog}
    </>
  )
}
