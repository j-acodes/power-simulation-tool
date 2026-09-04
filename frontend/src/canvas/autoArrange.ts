import type { Diagram } from '../types'

/**
 * Lay a drawn plant back onto the grid a seeded plant is born on: POC / MV-HV
 * transformer / busbar down the centre column, one column per collection
 * circuit, stations stacked down their circuit, aux parked to the right.
 *
 * The grid is the seeder's (backend/seed.py `_layout_to_diagram`), opened up:
 * every cable carries a two-line label at its midpoint, so each gap has to fit
 * a node plus that label rather than just the node. Seeded plants still use the
 * tighter original pitch.
 */
const POC_Y = 0
const HV_Y = 160
const BUS_Y = 320
const STATION_Y0 = 480
const STATION_DY = 150
const CIRCUIT_X0 = 100
const CIRCUIT_DX = 220
const AUX_DX = 520
const AUX_Y = BUS_Y + 90

export type Positions = Record<string, { x: number; y: number }>

/**
 * Positions for every node in `diagram`, keyed by node id — the diagram itself
 * is not touched.
 *
 * Circuits are read off the graph: each station hanging directly off the busbar
 * starts a column, walked down through station→station edges (edges run
 * upstream→downstream, as drawn by the palette and the seeder). Stations that
 * reach no busbar still get their own column rather than being left where they
 * were, so the result never overlaps.
 *
 * ponytail: no generic graph layout, so a plant with 3+ MV/HV transformers can
 * push one under the aux column. Reach for elkjs if that shape ever turns up.
 */
export function autoArrange(diagram: Diagram): Positions {
  const byId = new Map(diagram.nodes.map((n) => [n.id, n]))
  const children = new Map<string, string[]>()
  for (const e of diagram.edges) {
    if (!byId.has(e.source) || !byId.has(e.target)) continue
    const seen = children.get(e.source)
    if (seen) seen.push(e.target)
    else children.set(e.source, [e.target])
  }

  const isStation = (id: string) => byId.get(id)?.kind === 'station'
  const placed = new Set<string>()

  /** The circuits hanging off one busbar: each station wired directly to it
   *  starts a column, walked down through station->station edges. */
  const circuitsOf = (busbarId: string): string[][] => {
    const chains: string[][] = []
    for (const head of children.get(busbarId) ?? []) {
      if (!isStation(head) || placed.has(head)) continue
      const chain: string[] = []
      let current: string | undefined = head
      while (current && isStation(current) && !placed.has(current)) {
        chain.push(current)
        placed.add(current)
        current = (children.get(current) ?? []).find((id) => isStation(id) && !placed.has(id))
      }
      chains.push(chain)
    }
    return chains
  }

  // One contiguous band of columns per busbar, in the order the busbars appear
  // — a hybrid plant is two independent cascades, so their stations must not
  // interleave. Walking only the FIRST busbar is what used to drop the second
  // fleet's stations into the unreached fallback below.
  const busbars = diagram.nodes.filter((n) => n.kind === 'busbar')
  const bands: Array<{ busbarId: string; from: number; to: number }> = []
  const circuits: string[][] = []
  for (const busbar of busbars) {
    const from = circuits.length
    circuits.push(...circuitsOf(busbar.id))
    // A busbar with no stations yet still needs a column to sit over, and the
    // column has to be RESERVED, not just pointed at: leaving `circuits`
    // untouched means the next busbar's band starts at the same index and the
    // two are laid out on the same spot. This is the normal mid-draw state —
    // drop the second busbar, arrange, and it would hide under the first.
    if (circuits.length === from) circuits.push([])
    bands.push({ busbarId: busbar.id, from, to: circuits.length })
  }
  for (const n of diagram.nodes) {
    if (n.kind === 'station' && !placed.has(n.id)) {
      circuits.push([n.id])
      placed.add(n.id)
    }
  }

  const columnX = (column: number) => CIRCUIT_X0 + column * CIRCUIT_DX
  const positions: Positions = {}
  circuits.forEach((chain, column) => {
    chain.forEach((id, row) => {
      positions[id] = { x: columnX(column), y: STATION_Y0 + row * STATION_DY }
    })
  })

  const centerOf = (from: number, to: number) => (columnX(from) + columnX(to - 1)) / 2
  const centerX = centerOf(0, Math.max(circuits.length, 1))
  const bandCenter = new Map(bands.map((b) => [b.busbarId, centerOf(b.from, b.to)]))
  // Right of the widest column as well as of the spine: with enough circuits
  // the old centre-relative offset alone would land the aux column on top of
  // the last one.
  const auxX = Math.max(centerX + AUX_DX, columnX(Math.max(circuits.length, 1)))

  let hvColumn = 0
  let auxRow = 0
  for (const n of diagram.nodes) {
    if (n.kind === 'poc') positions[n.id] = { x: centerX, y: POC_Y }
    else if (n.kind === 'busbar') positions[n.id] = { x: bandCenter.get(n.id) ?? centerX, y: BUS_Y }
    else if (n.kind === 'hv_tx') positions[n.id] = { x: centerX + hvColumn++ * CIRCUIT_DX, y: HV_Y }
    else if (n.kind === 'aux') positions[n.id] = { x: auxX, y: AUX_Y + auxRow++ * STATION_DY }
  }
  return positions
}
