import { useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import '../App.css'
import {
  createDesign,
  createProject,
  deleteDesign,
  deleteProject,
  getCatalogue,
  getProject,
  listProjects,
} from '../api'
import { DisplayNameControl } from '../components/DisplayName'
import { useConfirmDialog, usePromptDialog } from '../components/Modal'
import { EXAMPLE_DIAGRAM } from '../example'
import { useStore } from '../store'
import type { Diagram, ProjectDetail, ProjectSummary } from '../types'

function formatDate(iso: string): string {
  return new Date(iso).toLocaleString()
}

/** An empty diagram seeded from the catalogue's default tiers/rules — the
 * "blank canvas" option when creating a design (vs. "from example plant"). */
async function emptyDiagramFromCatalogue(): Promise<Diagram> {
  const { defaults } = await getCatalogue()
  return {
    schema_version: 1,
    settings: { tiers: { ...defaults.tiers }, rules: { ...defaults.rules } },
    nodes: [],
    edges: [],
  }
}

/** `/` — Projects → Designs browser: create/open/delete projects and the
 * designs inside them. Opening a design navigates to `/design/:id`. */
export function ProjectsPage() {
  const navigate = useNavigate()
  const displayName = useStore((s) => s.displayName)

  const [projects, setProjects] = useState<ProjectSummary[] | null>(null)
  const [selected, setSelected] = useState<ProjectDetail | null>(null)
  const [error, setError] = useState<string | null>(null)
  const { prompt, dialog: promptDialog } = usePromptDialog()
  const { confirm, dialog: confirmDialog } = useConfirmDialog()

  const refreshProjects = () => {
    listProjects()
      .then(setProjects)
      .catch((err: unknown) => setError(String(err)))
  }

  useEffect(() => {
    refreshProjects()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const openProject = (projectId: number) => {
    setError(null)
    getProject(projectId).then(setSelected).catch((err: unknown) => setError(String(err)))
  }

  const handleCreateProject = async () => {
    const name = await prompt({ title: 'New project', label: 'Project name' })
    if (!name) return
    try {
      await createProject(name)
      refreshProjects()
    } catch (err) {
      setError(String(err))
    }
  }

  const handleDeleteProject = async (projectId: number, name: string) => {
    const ok = await confirm({
      title: 'Delete project',
      message: `Delete project "${name}" and all its designs? This cannot be undone.`,
      danger: true,
      confirmLabel: 'Delete',
    })
    if (!ok) return
    try {
      await deleteProject(projectId)
      if (selected?.id === projectId) setSelected(null)
      refreshProjects()
    } catch (err) {
      setError(String(err))
    }
  }

  const handleCreateDesign = async (projectId: number) => {
    const name = await prompt({ title: 'New design', label: 'Design name' })
    if (!name) return
    const fromExample = await confirm({
      title: 'Start from example plant?',
      message: 'Choose "Example plant" to start pre-populated, or "Empty diagram" for a blank canvas.',
      confirmLabel: 'Example plant',
      cancelLabel: 'Empty diagram',
    })
    try {
      const payload = fromExample ? EXAMPLE_DIAGRAM : await emptyDiagramFromCatalogue()
      const design = await createDesign(projectId, {
        name,
        payload,
        last_edited_by: displayName ?? 'Anonymous',
      })
      navigate(`/design/${design.id}`)
    } catch (err) {
      setError(String(err))
    }
  }

  const handleDeleteDesign = async (projectId: number, designId: number, name: string) => {
    const ok = await confirm({
      title: 'Delete design',
      message: `Delete design "${name}"? This cannot be undone.`,
      danger: true,
      confirmLabel: 'Delete',
    })
    if (!ok) return
    try {
      await deleteDesign(designId)
      openProject(projectId)
      refreshProjects()
    } catch (err) {
      setError(String(err))
    }
  }

  return (
    <div className="app projects-page">
      <header className="app-header">
        <h1>Projects</h1>
        <div className="app-header-actions">
          <Link to="/scratch" className="header-link">
            Scratchpad
          </Link>
          <DisplayNameControl />
        </div>
      </header>

      {error && <p className="error">{error}</p>}
      <p className="panel-hint stage1-link-note">
        Need a quick no-layout estimate instead?{' '}
        <Link to="/stage1">Stage 1 — conceptual sizing</Link> gives the required inverter capacity for a POC
        target without drawing a plant.
      </p>

      <div className="app-body projects-body">
        {!selected ? (
          <div className="panel-wide">
            <button type="button" onClick={handleCreateProject}>
              New project
            </button>
            {projects === null ? (
              <p className="panel-hint">Loading projects…</p>
            ) : projects.length === 0 ? (
              <p className="panel-hint">No projects yet — create one to get started.</p>
            ) : (
              <ul className="entity-list">
                {projects.map((p) => (
                  <li key={p.id} className="entity-row">
                    <button type="button" className="entity-name" onClick={() => openProject(p.id)}>
                      {p.name}
                    </button>
                    <span className="entity-meta">
                      {p.design_count} design{p.design_count === 1 ? '' : 's'} · created {formatDate(p.created_at)}
                    </span>
                    <button type="button" className="danger" onClick={() => handleDeleteProject(p.id, p.name)}>
                      Delete
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </div>
        ) : (
          <div className="panel-wide">
            <button type="button" className="header-link" onClick={() => setSelected(null)}>
              ← All projects
            </button>
            <h2>{selected.name}</h2>
            <button type="button" onClick={() => handleCreateDesign(selected.id)}>
              New design
            </button>
            {selected.designs.length === 0 ? (
              <p className="panel-hint">No designs yet — create one to get started.</p>
            ) : (
              <ul className="entity-list">
                {selected.designs.map((d) => (
                  <li key={d.id} className="entity-row">
                    <Link to={`/design/${d.id}`} className="entity-name">
                      {d.name}
                    </Link>
                    <span className="entity-meta">
                      v{d.version} · {d.last_edited_by} · updated {formatDate(d.updated_at)}
                    </span>
                    <button
                      type="button"
                      className="danger"
                      onClick={() => handleDeleteDesign(selected.id, d.id, d.name)}
                    >
                      Delete
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </div>
        )}
      </div>
      {promptDialog}
      {confirmDialog}
    </div>
  )
}
