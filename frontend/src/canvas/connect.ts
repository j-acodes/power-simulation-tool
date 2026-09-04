import type { Diagram, DiagramNode, FleetKind, NodeKind, Tier } from '../types'

/** A station's fleet, defaulting to PV exactly as the server's `_fleet_kind`
 *  does for props that predate the concept. */
function fleetKindOf(node: DiagramNode): FleetKind {
  return node.props.fleet_kind === 'bess' ? 'bess' : 'pv'
}

const nodesById = (diagram: Diagram) => new Map(diagram.nodes.map((n) => [n.id, n]))

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

/** The fleet kind a busbar stands for, or null when nothing has claimed it yet.
 *
 * Follows `powertool.graph._effective_busbar_kind` on the case that matters: an
 * explicit `fleet_kind` wins, otherwise the busbar adopts the kind of the
 * stations already hanging from it. Every design saved before the hybrid work
 * declares no busbar kind, so reading the bare 'pv' default here instead would
 * make it impossible to draw a BESS station onto an existing single-fleet BESS
 * plant.
 *
 * It DIVERGES from the server on the disputed case, deliberately. Where the
 * stations disagree among themselves the server answers 'pv' — it owes every
 * design a definite reading, and reports the disagreement as an issue against
 * each offending station. Here the answer is null, "undecided", which
 * `canConnect` treats as "either kind may join". The two are not
 * interchangeable and should not be made so: a mixed busbar is a state the
 * engineer has to be able to edit their way out of, and a canvas that answered
 * 'pv' would refuse every BESS station on it — including the one being dragged
 * back to fix it.
 *
 * Null also means an undeclared busbar with no stations yet, which the first
 * station to join is free to define either way.
 */
export function busbarFleetKind(diagram: Diagram, busbarId: string): FleetKind | null {
  const byId = nodesById(diagram)
  const declared = byId.get(busbarId)?.props.fleet_kind
  if (declared === 'pv' || declared === 'bess') return declared

  const kinds = new Set<FleetKind>()
  const frontier = [busbarId]
  const seen = new Set(frontier)
  while (frontier.length) {
    const current = frontier.pop()!
    for (const e of diagram.edges) {
      for (const [from, to] of [
        [e.source, e.target],
        [e.target, e.source],
      ]) {
        if (from !== current || seen.has(to)) continue
        if (byId.get(to)?.kind !== 'station') continue
        seen.add(to)
        kinds.add(fleetKindOf(byId.get(to)!))
        frontier.push(to)
      }
    }
  }
  return kinds.size === 1 ? [...kinds][0] : null
}

/** Whether an edge between these two blocks may be drawn.
 *
 * The only rule beyond "both ends exist" is the fleet one: a station belongs to
 * exactly one cascade, so it cannot join the other fleet's busbar, nor
 * daisy-chain onto a station of the other fleet. This is the canvas half of the
 * `busbar_kind_mismatch` the server rejects — the point is that the invalid
 * state cannot be drawn at all, rather than being drawn and then reported.
 *
 * Everything else stays permissive: the topology rules (radial chains, what may
 * feed what) are the server's to enforce, and duplicating them here would mean
 * two copies to keep in step.
 */
export function canConnect(diagram: Diagram, sourceId: string, targetId: string): boolean {
  if (sourceId === targetId) return false
  const byId = nodesById(diagram)
  const source = byId.get(sourceId)
  const target = byId.get(targetId)
  if (!source || !target) return false

  // Order-independent: edges are drawn undirected and the server roots the tree
  // later, so a rule that only fired one way round would be sidestepped by
  // dragging from the other end.
  const [station, other] =
    source.kind === 'station' ? [source, target] : target.kind === 'station' ? [target, source] : [null, null]
  if (!station || !other) return true

  if (other.kind === 'station') return fleetKindOf(station) === fleetKindOf(other)
  if (other.kind === 'busbar') {
    const busKind = busbarFleetKind(diagram, other.id)
    return busKind === null || busKind === fleetKindOf(station)
  }
  return true
}

/** Which fleet SLOT a busbar occupies, for the "one busbar per kind" rule.
 *
 * This is the total version of `busbarFleetKind`, and it is what the duplicate
 * check must use: `powertool.graph._busbars` owes every busbar a definite slot,
 * so an undecided one (undeclared and empty, or with stations that disagree)
 * counts as PV there. Offering both palette items for an undecided busbar would
 * let a third busbar be drawn — a state the server rejects, which is exactly
 * what this ticket exists to make undrawable.
 *
 * Kept separate from `busbarFleetKind` because the two answer different
 * questions: "which slot is taken" must always answer, while "which stations
 * may join" is allowed to say "either" (see busbarFleetKind).
 */
export function busbarSlot(diagram: Diagram, busbarId: string): FleetKind {
  return busbarFleetKind(diagram, busbarId) ?? 'pv'
}

/** The fleet slots already occupied by a busbar other than `exceptId`. */
export function takenBusbarSlots(diagram: Diagram, exceptId?: string): Set<FleetKind> {
  return new Set(
    diagram.nodes
      .filter((n) => n.kind === 'busbar' && n.id !== exceptId)
      .map((n) => busbarSlot(diagram, n.id)),
  )
}
