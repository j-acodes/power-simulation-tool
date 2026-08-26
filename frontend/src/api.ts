import type {
  CatalogueResponse,
  Diagram,
  DesignFull,
  ProjectDetail,
  ProjectSummary,
  SeedParams,
  SolveResponse,
  Stage1Request,
  Stage1Response,
} from './types'

const JSON_HEADERS = { 'Content-Type': 'application/json' }

async function asJson<T>(res: Response): Promise<T> {
  if (!res.ok) throw new Error(`HTTP ${res.status}`)
  return (await res.json()) as T
}

async function asVoid(res: Response): Promise<void> {
  if (!res.ok) throw new Error(`HTTP ${res.status}`)
}

/** Thrown by `updateDesign` on a 409: carries the server's current copy of
 * the design so the caller can offer "reload theirs" / "save as new". */
export class ConflictError extends Error {
  design: DesignFull
  constructor(design: DesignFull) {
    super('Design was modified by someone else')
    this.name = 'ConflictError'
    this.design = design
  }
}

export function getCatalogue(): Promise<CatalogueResponse> {
  return fetch('/api/catalogue').then(asJson<CatalogueResponse>)
}

export function solveDiagram(diagram: Diagram): Promise<SolveResponse> {
  return fetch('/api/solve', {
    method: 'POST',
    headers: JSON_HEADERS,
    body: JSON.stringify(diagram),
  }).then(asJson<SolveResponse>)
}

/** Seed wizard: POC-level params -> a proposed diagram (see backend.seed.seed_diagram).
 * The response is the bare diagram dict, loaded onto the canvas exactly like a
 * saved design. */
export function seedDiagram(params: SeedParams): Promise<Diagram> {
  return fetch('/api/seed', {
    method: 'POST',
    headers: JSON_HEADERS,
    body: JSON.stringify(params),
  }).then(asJson<Diagram>)
}

/** Stage-1 conceptual sizing: lumped-chain inverter requirement over the
 * element list (see pages/Stage1Page.tsx). */
export function solveStage1(payload: Stage1Request): Promise<Stage1Response> {
  return fetch('/api/stage1', {
    method: 'POST',
    headers: JSON_HEADERS,
    body: JSON.stringify(payload),
  }).then(asJson<Stage1Response>)
}

// --- Projects ----------------------------------------------------------------

export function listProjects(): Promise<ProjectSummary[]> {
  return fetch('/api/projects').then(asJson<ProjectSummary[]>)
}

export function createProject(name: string): Promise<ProjectSummary> {
  return fetch('/api/projects', {
    method: 'POST',
    headers: JSON_HEADERS,
    body: JSON.stringify({ name }),
  }).then(asJson<ProjectSummary>)
}

export function getProject(projectId: number): Promise<ProjectDetail> {
  return fetch(`/api/projects/${projectId}`).then(asJson<ProjectDetail>)
}

export function deleteProject(projectId: number): Promise<void> {
  return fetch(`/api/projects/${projectId}`, { method: 'DELETE' }).then(asVoid)
}

// --- Designs -------------------------------------------------------------

export interface DesignCreateBody {
  name: string
  payload: Diagram
  last_edited_by: string
}

export function createDesign(projectId: number, body: DesignCreateBody): Promise<DesignFull> {
  return fetch(`/api/projects/${projectId}/designs`, {
    method: 'POST',
    headers: JSON_HEADERS,
    body: JSON.stringify(body),
  }).then(asJson<DesignFull>)
}

export function getDesign(designId: number): Promise<DesignFull> {
  return fetch(`/api/designs/${designId}`).then(asJson<DesignFull>)
}

export function deleteDesign(designId: number): Promise<void> {
  return fetch(`/api/designs/${designId}`, { method: 'DELETE' }).then(asVoid)
}

export interface DesignUpdateBody {
  name?: string
  payload: Diagram
  version: number
  last_edited_by: string
}

/** PUT with optimistic locking: rejects with `ConflictError` on a 409 (someone
 * else saved first) — the server's current copy comes back on the error so
 * the caller can offer a reload/save-as-new choice, never a silent overwrite. */
export async function updateDesign(designId: number, body: DesignUpdateBody): Promise<DesignFull> {
  const res = await fetch(`/api/designs/${designId}`, {
    method: 'PUT',
    headers: JSON_HEADERS,
    body: JSON.stringify(body),
  })
  if (res.status === 409) {
    const data = (await res.json()) as { detail: { design: DesignFull } }
    throw new ConflictError(data.detail.design)
  }
  return asJson<DesignFull>(res)
}
