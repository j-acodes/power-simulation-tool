import type { NodeKind, Tier } from '../types'

/** Guess a new edge's tier/length from the kinds of the two blocks it joins —
 * mirrors powertool/graph.py's _edge_role, but doesn't need to know which end
 * is "upstream" (validate_graph roots that later): only the POC<->MV/HV
 * transformer link is ever HV, everything else on the drawn tree is MV. */
export function inferTier(a: NodeKind, b: NodeKind): Tier {
  const pair = new Set([a, b])
  if (pair.has('poc') && pair.has('hv_tx')) return 'hv'
  return 'mv'
}

/** Attachment edges (substation link, aux hookup) carry no length; sized runs
 * (export, MV segment) get a sane positive default the user can edit. */
export function defaultLengthM(a: NodeKind, b: NodeKind): number | undefined {
  const pair = new Set([a, b])
  if (pair.has('aux')) return undefined
  if (pair.has('hv_tx') && pair.has('busbar')) return undefined
  if (pair.has('poc')) return 0 // export run: 0 m is legitimate (POC at the fence)
  return 100
}
