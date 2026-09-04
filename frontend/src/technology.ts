import { busbarSlot } from './canvas/connect'
import type { Diagram, DiagramNode, FleetKind, Technology } from './types'

/** Legal clone targets for a design's current technology (ticket 04 / ADR-0002).
 *  `pv` <-> `bess` is never offered in either direction: it would delete the
 *  entire diagram and produce a copy of nothing. */
const LEGAL_TARGETS: Record<Technology, Technology[]> = {
  pv: ['hybrid'],
  bess: ['hybrid'],
  hybrid: ['pv', 'bess'],
}

export function legalCloneTargets(technology: Technology): Technology[] {
  return LEGAL_TARGETS[technology]
}

export function technologyLabel(technology: Technology): string {
  return technology === 'pv' ? 'PV' : technology === 'bess' ? 'BESS' : 'Hybrid'
}

/** Words describing what a narrowing clone will not copy, for the clone
 *  dialog to show in place of a confirmation step (no confirmation dialog —
 *  the original survives untouched, so nothing is at risk, but the engineer
 *  should know before they name the copy). `null` for a widening target
 *  (hybrid adds nothing), which needs no warning. */
export function narrowingWarning(to: Technology): string | null {
  if (to !== 'pv' && to !== 'bess') return null
  const departing = technologyLabel(to === 'pv' ? 'bess' : 'pv')
  const dischargeClause = to === 'pv' ? ', and its discharge duration' : ''
  return (
    `This will not copy the ${departing} busbar, its circuits and stations, or any auxiliary ` +
    `load attached to it. The ${departing} point-of-connection target and maximum loading ` +
    `override will be cleared${dischargeClause}.`
  )
}

const nodesById = (diagram: Diagram) => new Map(diagram.nodes.map((n) => [n.id, n]))

function neighborsOf(diagram: Diagram, id: string): string[] {
  const out: string[] = []
  for (const e of diagram.edges) {
    if (e.source === id) out.push(e.target)
    else if (e.target === id) out.push(e.source)
  }
  return out
}

/** Every station reachable from a busbar through the daisy chain — the
 *  busbar's circuits, flattened to node ids. Mirrors the traversal
 *  `busbarFleetKind` (canvas/connect.ts) already does, but returns the ids
 *  themselves rather than the kind they agree on. */
function stationsUnderBusbar(diagram: Diagram, busbarId: string): Set<string> {
  const byId = nodesById(diagram)
  const seen = new Set<string>([busbarId])
  const stations = new Set<string>()
  const frontier = [busbarId]
  while (frontier.length) {
    const current = frontier.pop()!
    for (const next of neighborsOf(diagram, current)) {
      if (seen.has(next) || byId.get(next)?.kind !== 'station') continue
      seen.add(next)
      stations.add(next)
      frontier.push(next)
    }
  }
  return stations
}

/** Aux loads attached directly to a busbar — an aux always feeds nothing and
 *  hangs straight off its busbar (never through a station), so this is a
 *  one-hop lookup, not a traversal. */
function auxUnderBusbar(diagram: Diagram, busbarId: string): Set<string> {
  const byId = nodesById(diagram)
  return new Set(neighborsOf(diagram, busbarId).filter((id) => byId.get(id)?.kind === 'aux'))
}

function clearPocTarget(node: DiagramNode, fleet: FleetKind): DiagramNode {
  const props = { ...node.props }
  delete props[fleet === 'bess' ? 'p_target_bess_mw' : 'p_target_mw']
  return { ...node, props }
}

function setPocTargetZero(node: DiagramNode, fleet: FleetKind): DiagramNode {
  return { ...node, props: { ...node.props, [fleet === 'bess' ? 'p_target_bess_mw' : 'p_target_mw']: 0 } }
}

/** Convert a design's diagram from one technology to another (ticket 04).
 *  Pure: neither argument is mutated, and the result is a new `Diagram`.
 *
 *  Widening (pv/bess -> hybrid) changes no nodes and no edges; it only sets
 *  the arriving fleet's POC target to zero.
 *
 *  Narrowing (hybrid -> pv/bess) drops the departing fleet's busbar, its
 *  circuits, its stations, and any aux load attached to that busbar, plus
 *  every edge that referenced a dropped node. It clears the departing
 *  fleet's POC target and its maximum-loading override, and — for
 *  hybrid -> pv specifically — the discharge duration too.
 *
 *  Throws on any pairing other than the four legal ones; the caller should
 *  only ever offer `legalCloneTargets(from)`. */
export function convertDiagramTechnology(diagram: Diagram, from: Technology, to: Technology): Diagram {
  if (!LEGAL_TARGETS[from].includes(to)) {
    throw new Error(`Cannot clone a ${from} design into ${to}`)
  }

  if (from !== 'hybrid') {
    // Widening: the arriving fleet is whichever of pv/bess `from` isn't.
    const arriving: FleetKind = from === 'pv' ? 'bess' : 'pv'
    const nodes = diagram.nodes.map((n) => (n.kind === 'poc' ? setPocTargetZero(n, arriving) : n))
    return { ...diagram, nodes }
  }

  // Narrowing: the departing fleet is whichever of pv/bess `to` isn't.
  const departing: FleetKind = to === 'pv' ? 'bess' : 'pv'
  const busbar = diagram.nodes.find((n) => n.kind === 'busbar' && busbarSlot(diagram, n.id) === departing)

  const removed = new Set<string>()
  if (busbar) {
    removed.add(busbar.id)
    for (const id of stationsUnderBusbar(diagram, busbar.id)) removed.add(id)
    for (const id of auxUnderBusbar(diagram, busbar.id)) removed.add(id)
  }

  const nodes = diagram.nodes
    .filter((n) => !removed.has(n.id))
    .map((n) => (n.kind === 'poc' ? clearPocTarget(n, departing) : n))
  const edges = diagram.edges.filter((e) => !removed.has(e.source) && !removed.has(e.target))

  const rules = { ...diagram.settings.rules }
  delete rules[departing === 'bess' ? 'max_loading_bess' : 'max_loading_pv']
  if (departing === 'bess') delete rules.discharge_hours

  return { ...diagram, nodes, edges, settings: { ...diagram.settings, rules } }
}

/**
 * Does this design's technology permit drawing a fleet of this kind?
 *
 * `pv` permits only pv, `bess` permits only bess, `hybrid` permits both — the
 * table in docs/adr/0002-technology-declared-not-derived.md and the
 * Technology entry in CONTEXT.md. Every palette, inspector and settings
 * control specific to a fleet kind reads this rather than re-deriving it.
 *
 * A missing technology (the design hasn't loaded yet) permits everything: a
 * blank editor that hides its own palette is worse than one that briefly
 * shows too much.
 */
export function permitsFleetKind(technology: Technology | null | undefined, kind: FleetKind): boolean {
  if (technology == null) return true
  if (technology === 'hybrid') return true
  return technology === kind
}
