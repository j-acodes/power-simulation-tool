import type { CatalogueResponse, Diagram, SolveResponse } from './types'

async function asJson<T>(res: Response): Promise<T> {
  if (!res.ok) throw new Error(`HTTP ${res.status}`)
  return (await res.json()) as T
}

export function getCatalogue(): Promise<CatalogueResponse> {
  return fetch('/api/catalogue').then(asJson<CatalogueResponse>)
}

export function solveDiagram(diagram: Diagram): Promise<SolveResponse> {
  return fetch('/api/solve', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(diagram),
  }).then(asJson<SolveResponse>)
}
