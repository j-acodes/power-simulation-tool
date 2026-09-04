import { describe, expect, it } from 'vitest'
import { autoArrange } from './autoArrange'
import type { Diagram, DiagramEdge, DiagramNode, NodeKind } from '../types'

function node(id: string, kind: NodeKind): DiagramNode {
  // Deliberately scrambled coordinates: auto-arrange must ignore them.
  return { id, kind, x: 999, y: 999, props: {} }
}

function edge(source: string, target: string): DiagramEdge {
  return { id: `${source}-${target}`, source, target, tier: 'mv', sizing: { mode: 'auto' } }
}

/** POC → hv_tx → busbar, then `sizes` circuits of stations hanging off it. */
function plant(sizes: number[]): Diagram {
  const nodes = [node('poc', 'poc'), node('hv', 'hv_tx'), node('bus', 'busbar')]
  const edges = [edge('poc', 'hv'), edge('hv', 'bus')]
  sizes.forEach((size, c) => {
    let previous = 'bus'
    for (let s = 0; s < size; s++) {
      const id = `s${c}_${s}`
      nodes.push(node(id, 'station'))
      edges.push(edge(previous, id))
      previous = id
    }
  })
  return { schema_version: 1, settings: {} as Diagram['settings'], nodes, edges }
}

/** POC -> hv_tx -> two busbars, `pv` and `bess`, each with its own circuits. */
function hybridPlant(pvSizes: number[], bessSizes: number[]): Diagram {
  const nodes = [node('poc', 'poc'), node('hv', 'hv_tx')]
  const edges = [edge('poc', 'hv')]
  for (const [bus, sizes] of [
    ['bus_pv', pvSizes],
    ['bus_b', bessSizes],
  ] as const) {
    nodes.push(node(bus, 'busbar'))
    edges.push(edge('hv', bus))
    sizes.forEach((size, c) => {
      let previous: string = bus
      for (let s = 0; s < size; s++) {
        const id = `${bus}_s${c}_${s}`
        nodes.push(node(id, 'station'))
        edges.push(edge(previous, id))
        previous = id
      }
    })
  }
  return { schema_version: 1, settings: {} as Diagram['settings'], nodes, edges }
}

describe('autoArrange — hybrid', () => {
  it('places both busbars and every station', () => {
    // The regression this ticket exists for: the layout used to find the FIRST
    // busbar only, so the second fleet's stations fell into the unreached-node
    // fallback — placed, but in the wrong band, with nothing reporting it.
    const diagram = hybridPlant([2, 1], [2])
    const positions = autoArrange(diagram)
    for (const n of diagram.nodes) expect(positions[n.id]).toBeDefined()
  })

  it('gives each busbar its own horizontal band, stations beneath it', () => {
    const positions = autoArrange(hybridPlant([2, 1], [2]))
    const pvXs = [positions.bus_pv_s0_0.x, positions.bus_pv_s1_0.x]
    const bessXs = [positions.bus_b_s0_0.x]
    // No overlap between the bands: every BESS column sits right of every PV one.
    expect(Math.min(...bessXs)).toBeGreaterThan(Math.max(...pvXs))
    // Each busbar is centred over its own band, not over the whole plant.
    expect(positions.bus_pv.x).toBeLessThan(positions.bus_b.x)
    expect(positions.bus_pv.y).toBe(positions.bus_b.y)
    for (const id of ['bus_pv_s0_0', 'bus_pv_s1_0', 'bus_b_s0_0']) {
      expect(positions[id].y).toBeGreaterThan(positions.bus_pv.y)
    }
  })

  it('keeps each circuit a column in chain order, per fleet', () => {
    const positions = autoArrange(hybridPlant([3], [2]))
    expect(positions.bus_pv_s0_0.x).toBe(positions.bus_pv_s0_2.x)
    expect(positions.bus_pv_s0_0.y).toBeLessThan(positions.bus_pv_s0_2.y)
    expect(positions.bus_b_s0_0.x).toBe(positions.bus_b_s0_1.x)
    expect(positions.bus_b_s0_0.y).toBeLessThan(positions.bus_b_s0_1.y)
  })

  it('never places two blocks on the same spot', () => {
    const diagram = hybridPlant([2, 2], [1, 1])
    diagram.nodes.push(node('aux', 'aux'), node('aux2', 'aux'))
    diagram.edges.push(edge('bus_pv', 'aux'), edge('bus_b', 'aux2'))
    const seen = new Set<string>()
    for (const { x, y } of Object.values(autoArrange(diagram))) {
      const key = `${x},${y}`
      expect(seen.has(key)).toBe(false)
      seen.add(key)
    }
  })

  it('reserves a column for a busbar with no stations yet', () => {
    // The normal mid-draw state: drop the second busbar, then auto-arrange
    // before wiring anything to it. Without a reserved column its band starts
    // where the next busbar's does and the two land on the same spot — hidden
    // under each other, with nothing to show the second one is there.
    const positions = autoArrange(hybridPlant([], [1]))
    expect(positions.bus_pv).not.toEqual(positions.bus_b)
    expect(positions.bus_pv.x).toBeLessThan(positions.bus_b.x)
  })

  it('leaves a single-fleet layout exactly as it was', () => {
    // The ticket's backward-compatibility criterion, pinned against the literal
    // coordinates the single-busbar path produced before hybrid support.
    const positions = autoArrange(plant([3, 2]))
    expect(positions.poc).toEqual({ x: 210, y: 0 })
    expect(positions.hv).toEqual({ x: 210, y: 160 })
    expect(positions.bus).toEqual({ x: 210, y: 320 })
    expect(positions.s0_0).toEqual({ x: 100, y: 480 })
    expect(positions.s0_2).toEqual({ x: 100, y: 780 })
    expect(positions.s1_0).toEqual({ x: 320, y: 480 })
  })
})

describe('autoArrange', () => {
  it('gives every node a position', () => {
    const diagram = plant([2, 2, 1])
    const positions = autoArrange(diagram)
    for (const n of diagram.nodes) expect(positions[n.id]).toBeDefined()
  })

  it('stacks each circuit in its own column, in chain order', () => {
    const positions = autoArrange(plant([3, 2]))
    // circuit 0
    expect(positions.s0_0.x).toBe(positions.s0_1.x)
    expect(positions.s0_1.x).toBe(positions.s0_2.x)
    expect(positions.s0_0.y).toBeLessThan(positions.s0_1.y)
    expect(positions.s0_1.y).toBeLessThan(positions.s0_2.y)
    // circuit 1 sits in the next column, starting level with circuit 0's head
    expect(positions.s1_0.x).toBeGreaterThan(positions.s0_0.x)
    expect(positions.s1_0.y).toBe(positions.s0_0.y)
  })

  it('runs the spine down the middle, above the stations', () => {
    const positions = autoArrange(plant([2, 2, 2, 2]))
    expect(positions.poc.x).toBe(positions.bus.x)
    expect(positions.hv.x).toBe(positions.bus.x)
    expect(positions.poc.y).toBeLessThan(positions.hv.y)
    expect(positions.hv.y).toBeLessThan(positions.bus.y)
    expect(positions.bus.y).toBeLessThan(positions.s0_0.y)
    // centred over the circuit columns
    expect(positions.bus.x).toBeGreaterThan(positions.s0_0.x)
    expect(positions.bus.x).toBeLessThan(positions.s3_0.x)
  })

  it('never places two blocks on the same spot', () => {
    const diagram = plant([3, 2, 2, 1])
    diagram.nodes.push(node('aux', 'aux'))
    diagram.edges.push(edge('bus', 'aux'))
    const seen = new Set<string>()
    for (const { x, y } of Object.values(autoArrange(diagram))) {
      const key = `${x},${y}`
      expect(seen.has(key)).toBe(false)
      seen.add(key)
    }
  })

  it('still places a station that is wired to nothing', () => {
    const diagram = plant([2])
    diagram.nodes.push(node('orphan', 'station'))
    const positions = autoArrange(diagram)
    expect(positions.orphan).toBeDefined()
    expect(positions.orphan.x).not.toBe(positions.s0_0.x)
  })

  it('keeps the aux column clear of the circuits, however wide the plant', () => {
    // The aux block used to be positioned purely relative to the spine centre,
    // which lands it ON TOP of the last circuit column once a plant has six or
    // more circuits. Hybrids make wide plants markedly more likely (two fleets'
    // columns side by side), so this is reachable in the feature being built,
    // not a hypothetical. Narrow plants — every design that existed before —
    // are unaffected: see the pin below.
    const wide = plant([1, 1, 1, 1, 1, 1])
    wide.nodes.push(node('aux', 'aux'))
    wide.edges.push(edge('bus', 'aux'))
    const positions = autoArrange(wide)
    const lastColumnX = Math.max(...['s0_0', 's5_0'].map((id) => positions[id].x))
    expect(positions.aux.x).toBeGreaterThan(lastColumnX)
  })

  it('leaves the aux column where it was on a plant of ordinary width', () => {
    const diagram = plant([3, 2])
    diagram.nodes.push(node('aux', 'aux'))
    diagram.edges.push(edge('bus', 'aux'))
    // Literal coordinate, as produced before this ticket: centre (210) + 520.
    expect(autoArrange(diagram).aux).toEqual({ x: 730, y: 410 })
  })

  it('handles an empty diagram', () => {
    const empty: Diagram = {
      schema_version: 1,
      settings: {} as Diagram['settings'],
      nodes: [],
      edges: [],
    }
    expect(autoArrange(empty)).toEqual({})
  })

  it('ignores edges pointing at nodes that are gone', () => {
    const diagram = plant([2])
    diagram.edges.push(edge('bus', 'deleted'))
    expect(() => autoArrange(diagram)).not.toThrow()
    expect(autoArrange(diagram).deleted).toBeUndefined()
  })
})
