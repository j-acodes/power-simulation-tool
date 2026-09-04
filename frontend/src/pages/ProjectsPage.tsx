import { useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import '../App.css'
import {
  createDesign,
  createProject,
  deleteDesign,
  deleteProject,
  getCatalogue,
  getDesign,
  getProject,
  listProjects,
  solveDiagram,
} from '../api'
import { evaluateCompliance } from '../compliance'
import { DisplayNameControl } from '../components/DisplayName'
import { useConfirmDialog, usePromptDialog } from '../components/Modal'
import { EXAMPLE_DIAGRAM } from '../example'
import { useStore } from '../store'
import { sortRows, type Sort, type SortDir } from '../sort'
import type { Diagram, DesignSummary, ProjectDetail, ProjectSummary } from '../types'

function formatDate(iso: string): string {
  return new Date(iso).toLocaleString()
}

/** POC target as "45 MW @ pf 0.95", read off the diagram's poc node props
 * (permissive Record, hence the typeof guards). */
function formatPocTarget(diagram: Diagram): string {
  const props = diagram.nodes.find((n) => n.kind === 'poc')?.props
  if (typeof props?.p_target_mw !== 'number') return '—'
  const pf = typeof props.pf === 'number' ? ` @ pf ${props.pf}` : ''
  return `${props.p_target_mw} MW${pf}`
}

/** The design columns that aren't in the list response: read off the design's
 * payload, plus a solve for the compliance verdict. Absent until the row's
 * fetch lands. */
interface DesignExtras {
  poc_target: string
  stations: number
  circuits: number | null
  /** null when the diagram doesn't solve (incomplete, invalid). */
  compliant: boolean | null
}

type DesignRow = DesignSummary & Partial<DesignExtras>

/** Sortable column header — click to sort, click again to flip direction. */
function Th({
  label,
  sortKey,
  sort,
  onSort,
  numeric,
}: {
  label: string
  sortKey: string
  sort: Sort
  onSort: (key: string) => void
  numeric?: boolean
}) {
  const active = sort.key === sortKey
  return (
    <th
      className={numeric ? 'num' : undefined}
      aria-sort={active ? (sort.dir === 'asc' ? 'ascending' : 'descending') : 'none'}
    >
      <button type="button" onClick={() => onSort(sortKey)}>
        {label}
        <span className="sort-arrow">{active ? (sort.dir === 'asc' ? '▲' : '▼') : ''}</span>
      </button>
    </th>
  )
}

function useSort(initialKey: string, initialDir: SortDir = 'asc') {
  const [sort, setSort] = useState<Sort>({ key: initialKey, dir: initialDir })
  const onSort = (key: string) =>
    setSort((s) =>
      s.key === key ? { key, dir: s.dir === 'asc' ? 'desc' : 'asc' } : { key, dir: 'asc' },
    )
  return { sort, onSort }
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
  const [extras, setExtras] = useState<Record<number, DesignExtras>>({})
  const projectSort = useSort('name')
  const designSort = useSort('name')
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

  /** Fill the derived design columns, one row at a time, so the table renders
   * immediately and fills in as the fetches land.
   *
   * ponytail: one GET + one solve per design, fine for the tens of designs a
   * project holds. Fold the derived fields into GET /api/projects/:id if a
   * project ever holds hundreds. */
  useEffect(() => {
    if (!selected) return
    let cancelled = false
    for (const { id } of selected.designs) {
      void (async () => {
        const design = await getDesign(id).catch(() => null)
        if (!design || cancelled) return
        const solved = await solveDiagram(design.payload).catch(() => null)
        if (cancelled) return
        const results = solved?.results ?? null
        setExtras((prev) => ({
          ...prev,
          [id]: {
            poc_target: formatPocTarget(design.payload),
            stations: design.payload.nodes.filter((n) => n.kind === 'station').length,
            circuits: results?.summary.n_circuits ?? null,
            compliant: results ? evaluateCompliance(results, solved?.issues ?? []).compliant : null,
          },
        }))
      })()
    }
    return () => {
      cancelled = true
    }
  }, [selected])

  const openProject = (projectId: number) => {
    setError(null)
    setExtras({})
    getProject(projectId).then(setSelected).catch((err: unknown) => setError(String(err)))
  }

  const handleCreateProject = async () => {
    const result = await prompt({ title: 'New project', label: 'Project name' })
    if (!result) return
    try {
      await createProject(result.value)
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
    const result = await prompt({
      title: 'New design',
      label: 'Design name',
      technologyLabel: 'Technology',
    })
    if (!result || !result.technology) return
    const { value: name, technology } = result
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
        technology,
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

  const designRows: DesignRow[] = selected
    ? selected.designs.map((d) => ({ ...d, ...extras[d.id] }))
    : []

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
            <div className="projects-toolbar">
              <button type="button" onClick={handleCreateProject}>
                New project
              </button>
            </div>
            {projects === null ? (
              <p className="panel-hint">Loading projects…</p>
            ) : projects.length === 0 ? (
              <p className="panel-hint">No projects yet — create one to get started.</p>
            ) : (
              <div className="table-scroll">
                <table className="data-table">
                  <thead>
                    <tr>
                      <Th label="Project" sortKey="name" {...projectSort} />
                      <Th label="Designs" sortKey="design_count" numeric {...projectSort} />
                      <Th label="Created" sortKey="created_at" {...projectSort} />
                      <th className="row-actions">Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {sortRows(projects, projectSort.sort).map((p) => (
                      <tr key={p.id}>
                        <td>
                          <button type="button" className="row-name" onClick={() => openProject(p.id)}>
                            {p.name}
                          </button>
                        </td>
                        <td className="num">{p.design_count}</td>
                        <td>{formatDate(p.created_at)}</td>
                        <td className="row-actions">
                          <button type="button" className="btn-primary" onClick={() => openProject(p.id)}>
                            Open
                          </button>
                          <button
                            type="button"
                            className="danger"
                            onClick={() => handleDeleteProject(p.id, p.name)}
                          >
                            Delete
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        ) : (
          <div className="panel-wide">
            <button type="button" className="header-link" onClick={() => setSelected(null)}>
              ← All projects
            </button>
            <h2>{selected.name}</h2>
            <div className="projects-toolbar">
              <button type="button" onClick={() => handleCreateDesign(selected.id)}>
                New design
              </button>
            </div>
            {selected.designs.length === 0 ? (
              <p className="panel-hint">No designs yet — create one to get started.</p>
            ) : (
              <div className="table-scroll">
                <table className="data-table">
                  <thead>
                    <tr>
                      <Th label="Design" sortKey="name" {...designSort} />
                      <Th label="Technology" sortKey="technology" {...designSort} />
                      <Th label="POC target" sortKey="poc_target" {...designSort} />
                      <Th label="Stations" sortKey="stations" numeric {...designSort} />
                      <Th label="Circuits" sortKey="circuits" numeric {...designSort} />
                      <Th label="Compliance" sortKey="compliant" {...designSort} />
                      <Th label="Version" sortKey="version" numeric {...designSort} />
                      <Th label="Last edited by" sortKey="last_edited_by" {...designSort} />
                      <Th label="Updated" sortKey="updated_at" {...designSort} />
                      <th className="row-actions">Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {sortRows(designRows, designSort.sort).map((d) => (
                      <tr key={d.id}>
                        <td>
                          <Link to={`/design/${d.id}`} className="row-name">
                            {d.name}
                          </Link>
                        </td>
                        <td>{d.technology}</td>
                        <td>{d.poc_target ?? '…'}</td>
                        <td className="num">{d.stations ?? '…'}</td>
                        <td className="num">{d.circuits ?? (d.stations === undefined ? '…' : '—')}</td>
                        <td>
                          {d.compliant === undefined ? (
                            '…'
                          ) : d.compliant === null ? (
                            'not solvable'
                          ) : (
                            <>
                              {d.compliant ? 'COMPLIANT' : 'NOT COMPLIANT'}
                              <span
                                className={`compliance-dot ${d.compliant ? 'ok' : 'bad'}`}
                                aria-hidden="true"
                              />
                            </>
                          )}
                        </td>
                        <td className="num">v{d.version}</td>
                        <td>{d.last_edited_by}</td>
                        <td>{formatDate(d.updated_at)}</td>
                        <td className="row-actions">
                          <button
                            type="button"
                            className="btn-primary"
                            onClick={() => navigate(`/design/${d.id}`)}
                          >
                            Open in editor
                          </button>
                          <button
                            type="button"
                            className="danger"
                            onClick={() => handleDeleteDesign(selected.id, d.id, d.name)}
                          >
                            Delete
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        )}
      </div>
      {promptDialog}
      {confirmDialog}
    </div>
  )
}
