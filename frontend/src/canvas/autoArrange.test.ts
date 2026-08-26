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
