import type { Diagram } from '../types'

/**
 * Lay a drawn plant back onto the grid a seeded plant is born on: POC / MV-HV
 * transformer / busbar down the centre column, one column per collection
 * circuit, stations stacked down their circuit, aux parked to the right.
 *
 * Constants mirror backend/seed.py's `_layout_to_diagram`, except the column
 * pitch — widened from 180 so the widest station labels can't touch their
 * neighbour.
 */
const POC_Y = 0
const HV_Y = 110
const BUS_Y = 220
const STATION_Y0 = 320
const STATION_DY = 120
const CIRCUIT_X0 = 100
const CIRCUIT_DX = 200
const AUX_DX = 460
const AUX_Y = BUS_Y + 80

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
  const circuits: string[][] = []
  const placed = new Set<string>()

  const busbar = diagram.nodes.find((n) => n.kind === 'busbar')
  for (const head of busbar ? (children.get(busbar.id) ?? []) : []) {
    if (!isStation(head) || placed.has(head)) continue
    const chain: string[] = []
    let current: string | undefined = head
    while (current && isStation(current) && !placed.has(current)) {
      chain.push(current)
      placed.add(current)
      current = (children.get(current) ?? []).find((id) => isStation(id) && !placed.has(id))
    }
    circuits.push(chain)
  }
  for (const n of diagram.nodes) {
    if (n.kind === 'station' && !placed.has(n.id)) {
      circuits.push([n.id])
      placed.add(n.id)
    }
  }

  const positions: Positions = {}
  circuits.forEach((chain, column) => {
    const x = CIRCUIT_X0 + column * CIRCUIT_DX
    chain.forEach((id, row) => {
      positions[id] = { x, y: STATION_Y0 + row * STATION_DY }
    })
  })

  const centerX = CIRCUIT_X0 + (Math.max(circuits.length, 1) - 1) * (CIRCUIT_DX / 2)
  let hvColumn = 0
  let auxRow = 0
  for (const n of diagram.nodes) {
    if (n.kind === 'poc') positions[n.id] = { x: centerX, y: POC_Y }
    else if (n.kind === 'busbar') positions[n.id] = { x: centerX, y: BUS_Y }
    else if (n.kind === 'hv_tx') positions[n.id] = { x: centerX + hvColumn++ * CIRCUIT_DX, y: HV_Y }
    else if (n.kind === 'aux') positions[n.id] = { x: centerX + AUX_DX, y: AUX_Y + auxRow++ * STATION_DY }
  }
  return positions
}
