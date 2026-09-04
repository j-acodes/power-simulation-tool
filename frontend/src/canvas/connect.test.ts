import { describe, expect, it } from 'vitest'
import { busbarFleetKind, canConnect, defaultLengthM, inferTier } from './connect'
import type { Diagram, DiagramEdge, DiagramNode, NodeKind, NodeProps } from '../types'

function node(id: string, kind: NodeKind, props: NodeProps = {}): DiagramNode {
  return { id, kind, x: 0, y: 0, props }
}

function edge(source: string, target: string): DiagramEdge {
  return { id: `${source}-${target}`, source, target, tier: 'mv', sizing: { mode: 'auto' } }
}

function diagram(nodes: DiagramNode[], edges: DiagramEdge[] = []): Diagram {
  return { schema_version: 1, settings: {} as Diagram['settings'], nodes, edges }
}

/** POC -- hv -- {pv busbar, bess busbar}, each with one station. */
function hybrid(): Diagram {
  return diagram(
    [
      node('poc', 'poc'),
      node('hv', 'hv_tx'),
      node('bus_pv', 'busbar', { fleet_kind: 'pv' }),
      node('bus_b', 'busbar', { fleet_kind: 'bess' }),
      node('s_pv', 'station', { fleet_kind: 'pv' }),
      node('s_b', 'station', { fleet_kind: 'bess' }),
    ],
    [edge('poc', 'hv'), edge('hv', 'bus_pv'), edge('hv', 'bus_b'), edge('bus_pv', 's_pv'), edge('bus_b', 's_b')],
  )
}

describe('inferTier', () => {
  it('marks only the POC <-> MV/HV transformer link as HV', () => {
    expect(inferTier('poc', 'hv_tx')).toBe('hv')
    expect(inferTier('hv_tx', 'poc')).toBe('hv')
    expect(inferTier('hv_tx', 'busbar')).toBe('mv')
    expect(inferTier('busbar', 'station')).toBe('mv')
  })
})

describe('defaultLengthM', () => {
  it('leaves attachments lengthless and gives sized runs a default', () => {
    expect(defaultLengthM('busbar', 'aux')).toBeUndefined()
    expect(defaultLengthM('hv_tx', 'busbar')).toBeUndefined()
    expect(defaultLengthM('poc', 'hv_tx')).toBe(0)
    expect(defaultLengthM('busbar', 'station')).toBe(100)
  })
})

describe('busbarFleetKind', () => {
  it('reads an explicit declaration', () => {
    const d = hybrid()
    expect(busbarFleetKind(d, 'bus_b')).toBe('bess')
    expect(busbarFleetKind(d, 'bus_pv')).toBe('pv')
  })

  it('adopts the kind of its stations when undeclared', () => {
    // Mirrors the server rule (powertool.graph._effective_busbar_kind): every
    // design saved before the hybrid work declares no busbar kind, and a
    // single-fleet BESS plant must still read as BESS.
    const d = diagram(
      [node('bus', 'busbar'), node('s1', 'station', { fleet_kind: 'bess' })],
      [edge('bus', 's1')],
    )
    expect(busbarFleetKind(d, 'bus')).toBe('bess')
  })

  it('is undecided for an undeclared, empty busbar', () => {
    // Nothing has claimed it yet, so the first station to join may be either.
    expect(busbarFleetKind(diagram([node('bus', 'busbar')]), 'bus')).toBeNull()
  })

  it('is undecided when its stations disagree, and stays editable', () => {
    // Deliberate divergence from the server, which answers 'pv' here and
    // reports the disagreement per station. On the canvas a mixed busbar is a
    // state the engineer has to be able to edit their way out of: answering
    // 'pv' would refuse every BESS station on it, including the one being
    // dragged back to fix it.
    const d = diagram(
      [
        node('bus', 'busbar'),
        node('s_pv', 'station', { fleet_kind: 'pv' }),
        node('s_b', 'station', { fleet_kind: 'bess' }),
        node('s_new', 'station', { fleet_kind: 'bess' }),
      ],
      [edge('bus', 's_pv'), edge('bus', 's_b')],
    )
    expect(busbarFleetKind(d, 'bus')).toBeNull()
    expect(canConnect(d, 'bus', 's_new')).toBe(true)
  })

  it('follows a daisy chain to the busbar it hangs from', () => {
    const d = diagram(
      [node('bus', 'busbar'), node('s1', 'station', { fleet_kind: 'bess' }), node('s2', 'station', { fleet_kind: 'bess' })],
      [edge('bus', 's1'), edge('s1', 's2')],
    )
    expect(busbarFleetKind(d, 'bus')).toBe('bess')
  })
})

describe('canConnect', () => {
  it('allows a station onto its own fleet-kind busbar', () => {
    const d = hybrid()
    expect(canConnect(d, 'bus_pv', 's_pv')).toBe(true)
    expect(canConnect(d, 'bus_b', 's_b')).toBe(true)
  })

  it('rejects a station onto the other fleet-kind busbar', () => {
    const d = hybrid()
    expect(canConnect(d, 'bus_pv', 's_b')).toBe(false)
    expect(canConnect(d, 'bus_b', 's_pv')).toBe(false)
  })

  it('rejects the reversed drag just the same', () => {
    // Edges are drawn undirected; the server roots the tree later, so a rule
    // that only fired one way round would be trivially sidestepped.
    const d = hybrid()
    expect(canConnect(d, 's_b', 'bus_pv')).toBe(false)
  })

  it('rejects daisy-chaining a station onto one of the other fleet', () => {
    const d = hybrid()
    expect(canConnect(d, 's_pv', 's_b')).toBe(false)
    expect(canConnect(d, 's_pv', 's_pv')).toBe(false) // self-link is nonsense too
  })

  it('allows a station onto an undeclared, empty busbar', () => {
    const d = diagram([node('bus', 'busbar'), node('s1', 'station', { fleet_kind: 'bess' })])
    expect(canConnect(d, 'bus', 's1')).toBe(true)
  })

  it('allows an aux load onto any busbar', () => {
    const d = hybrid()
    d.nodes.push(node('aux', 'aux'))
    expect(canConnect(d, 'bus_pv', 'aux')).toBe(true)
    expect(canConnect(d, 'bus_b', 'aux')).toBe(true)
  })

  it('leaves every non-fleet connection alone', () => {
    const d = hybrid()
    expect(canConnect(d, 'poc', 'hv')).toBe(true)
    expect(canConnect(d, 'hv', 'bus_b')).toBe(true)
  })

  it('rejects an edge to a node that is not there', () => {
    expect(canConnect(hybrid(), 'bus_pv', 'ghost')).toBe(false)
  })
})
