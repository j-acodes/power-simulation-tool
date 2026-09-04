import { describe, expect, it } from 'vitest'
import { convertDiagramTechnology, legalCloneTargets, narrowingWarning } from './technology'
import type { Diagram, DiagramEdge, DiagramNode, NodeKind, NodeProps, RuleSettings } from './types'

function node(id: string, kind: NodeKind, props: NodeProps = {}): DiagramNode {
  return { id, kind, x: 0, y: 0, props }
}

function edge(source: string, target: string): DiagramEdge {
  return { id: `${source}-${target}`, source, target, tier: 'mv', sizing: { mode: 'auto' } }
}

function diagram(nodes: DiagramNode[], edges: DiagramEdge[] = [], rules: Partial<RuleSettings> = {}): Diagram {
  return {
    schema_version: 1,
    settings: { tiers: { lv_kv: 0.4, mv_kv: 20, hv_kv: null }, rules: rules as RuleSettings },
    nodes,
    edges,
  }
}

/** POC -- MV busbar (PV, two-station circuit) + MV busbar (BESS, one station,
 *  one aux). Mirrors a real hybrid plant closely enough to exercise the
 *  narrowing traversal (daisy chain + attached aux). */
function hybridDiagram(): Diagram {
  return diagram(
    [
      node('poc', 'poc', { p_target_mw: 40, p_target_bess_mw: 10, pf: 0.95 }),
      node('bus_pv', 'busbar', { fleet_kind: 'pv' }),
      node('bus_b', 'busbar', { fleet_kind: 'bess' }),
      node('s_pv1', 'station', { fleet_kind: 'pv' }),
      node('s_pv2', 'station', { fleet_kind: 'pv' }),
      node('s_b', 'station', { fleet_kind: 'bess' }),
      node('aux_b', 'aux', { p_kw: 50, q_kvar: 10 }),
    ],
    [
      edge('poc', 'bus_pv'),
      edge('poc', 'bus_b'),
      edge('bus_pv', 's_pv1'),
      edge('s_pv1', 's_pv2'),
      edge('bus_b', 's_b'),
      edge('bus_b', 'aux_b'),
    ],
    { max_loading: 0.9, max_loading_pv: 0.85, max_loading_bess: 0.8, discharge_hours: 4 },
  )
}

function pvDiagram(): Diagram {
  return diagram(
    [
      node('poc', 'poc', { p_target_mw: 40, pf: 0.95 }),
      node('bus_pv', 'busbar', { fleet_kind: 'pv' }),
      node('s_pv1', 'station', { fleet_kind: 'pv' }),
    ],
    [edge('poc', 'bus_pv'), edge('bus_pv', 's_pv1')],
    { max_loading_pv: 0.85 },
  )
}

function bessDiagram(): Diagram {
  return diagram(
    [
      node('poc', 'poc', { p_target_bess_mw: 10, pf: 0.95 }),
      node('bus_b', 'busbar', { fleet_kind: 'bess' }),
      node('s_b', 'station', { fleet_kind: 'bess' }),
    ],
    [edge('poc', 'bus_b'), edge('bus_b', 's_b')],
    { max_loading_bess: 0.8, discharge_hours: 4 },
  )
}

describe('legalCloneTargets', () => {
  it('offers only hybrid for a single-technology design', () => {
    expect(legalCloneTargets('pv')).toEqual(['hybrid'])
    expect(legalCloneTargets('bess')).toEqual(['hybrid'])
  })

  it('offers pv and bess for a hybrid design, and nothing else', () => {
    expect(legalCloneTargets('hybrid')).toEqual(['pv', 'bess'])
  })

  it('never offers pv <-> bess in either direction', () => {
    expect(legalCloneTargets('pv')).not.toContain('bess')
    expect(legalCloneTargets('bess')).not.toContain('pv')
  })
})

describe('narrowingWarning', () => {
  it('is null for a widening target', () => {
    expect(narrowingWarning('hybrid')).toBeNull()
  })

  it('names the departing fleet for a narrowing target', () => {
    expect(narrowingWarning('pv')).toMatch(/BESS/)
    expect(narrowingWarning('bess')).toMatch(/PV/)
  })

  it('mentions the discharge duration only for hybrid -> pv', () => {
    expect(narrowingWarning('pv')).toMatch(/discharge duration/)
    expect(narrowingWarning('bess')).not.toMatch(/discharge duration/)
  })
})

describe('convertDiagramTechnology', () => {
  it('rejects pv <-> bess in either direction', () => {
    expect(() => convertDiagramTechnology(pvDiagram(), 'pv', 'bess')).toThrow()
    expect(() => convertDiagramTechnology(bessDiagram(), 'bess', 'pv')).toThrow()
  })

  it('rejects a same-technology "conversion"', () => {
    expect(() => convertDiagramTechnology(pvDiagram(), 'pv', 'pv')).toThrow()
  })

  describe('widening', () => {
    it('pv -> hybrid changes no nodes or edges and zeroes the arriving BESS target', () => {
      const original = pvDiagram()
      const result = convertDiagramTechnology(original, 'pv', 'hybrid')

      expect(result.nodes.map((n) => n.id).sort()).toEqual(original.nodes.map((n) => n.id).sort())
      expect(result.edges).toEqual(original.edges)
      const poc = result.nodes.find((n) => n.id === 'poc')!
      expect(poc.props.p_target_bess_mw).toBe(0)
      expect(poc.props.p_target_mw).toBe(40) // untouched

      // original is unmodified
      expect(pvDiagram()).toEqual(original)
    })

    it('bess -> hybrid changes no nodes or edges and zeroes the arriving PV target', () => {
      const original = bessDiagram()
      const result = convertDiagramTechnology(original, 'bess', 'hybrid')

      expect(result.nodes.map((n) => n.id).sort()).toEqual(original.nodes.map((n) => n.id).sort())
      expect(result.edges).toEqual(original.edges)
      const poc = result.nodes.find((n) => n.id === 'poc')!
      expect(poc.props.p_target_mw).toBe(0)
      expect(poc.props.p_target_bess_mw).toBe(10) // untouched
    })
  })

  describe('narrowing', () => {
    it('hybrid -> pv drops the BESS busbar, station, and attached aux, and no other node', () => {
      const original = hybridDiagram()
      const result = convertDiagramTechnology(original, 'hybrid', 'pv')

      const ids = result.nodes.map((n) => n.id).sort()
      expect(ids).toEqual(['bus_pv', 'poc', 's_pv1', 's_pv2'].sort())
      expect(result.nodes.some((n) => n.props.fleet_kind === 'bess')).toBe(false)

      // original untouched
      expect(hybridDiagram()).toEqual(original)
    })

    it('leaves no dangling edge — every surviving edge references a surviving node', () => {
      const result = convertDiagramTechnology(hybridDiagram(), 'hybrid', 'pv')
      const ids = new Set(result.nodes.map((n) => n.id))
      for (const e of result.edges) {
        expect(ids.has(e.source)).toBe(true)
        expect(ids.has(e.target)).toBe(true)
      }
      // specifically: the edges that touched the removed BESS subtree are gone
      expect(result.edges.some((e) => e.source === 'bus_b' || e.target === 'bus_b')).toBe(false)
      expect(result.edges.some((e) => e.source === 'aux_b' || e.target === 'aux_b')).toBe(false)
      expect(result.edges.some((e) => e.source === 's_b' || e.target === 's_b')).toBe(false)
    })

    it('hybrid -> pv clears the BESS poc target, its loading override and discharge duration', () => {
      const result = convertDiagramTechnology(hybridDiagram(), 'hybrid', 'pv')
      const poc = result.nodes.find((n) => n.id === 'poc')!
      expect(poc.props.p_target_bess_mw).toBeUndefined()
      expect(poc.props.p_target_mw).toBe(40) // surviving fleet's target is untouched
      expect(result.settings.rules.max_loading_bess).toBeUndefined()
      expect(result.settings.rules.discharge_hours).toBeUndefined()
      expect(result.settings.rules.max_loading_pv).toBe(0.85) // untouched
      expect(result.settings.rules.max_loading).toBe(0.9) // plant-wide, untouched
    })

    it('hybrid -> bess drops the PV busbar and both PV stations, keeps discharge_hours', () => {
      const original = hybridDiagram()
      const result = convertDiagramTechnology(original, 'hybrid', 'bess')

      const ids = result.nodes.map((n) => n.id).sort()
      expect(ids).toEqual(['aux_b', 'bus_b', 'poc', 's_b'].sort())
      expect(result.nodes.some((n) => n.props.fleet_kind === 'pv')).toBe(false)

      const poc = result.nodes.find((n) => n.id === 'poc')!
      expect(poc.props.p_target_mw).toBeUndefined()
      expect(poc.props.p_target_bess_mw).toBe(10) // surviving fleet's target is untouched
      expect(result.settings.rules.max_loading_pv).toBeUndefined()
      expect(result.settings.rules.discharge_hours).toBe(4) // BESS survives, duration kept

      // original untouched
      expect(hybridDiagram()).toEqual(original)
    })

    it('is a no-op removal when the departing fleet has no busbar yet', () => {
      // A hybrid design whose second fleet was never drawn.
      const bare = diagram(
        [node('poc', 'poc', { p_target_mw: 40, p_target_bess_mw: 0 }), node('bus_pv', 'busbar', { fleet_kind: 'pv' })],
        [edge('poc', 'bus_pv')],
      )
      const result = convertDiagramTechnology(bare, 'hybrid', 'pv')
      expect(result.nodes.map((n) => n.id).sort()).toEqual(['bus_pv', 'poc'])
      expect(result.edges).toEqual(bare.edges)
    })
  })
})
