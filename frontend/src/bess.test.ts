import { describe, expect, it } from 'vitest'
import { supportedDurations } from './bess'
import type { BessSolutionInfo, Diagram, DiagramNode, NodeProps } from './types'

function node(id: string, kind: DiagramNode['kind'], props: NodeProps = {}): DiagramNode {
  return { id, kind, x: 0, y: 0, props }
}

function diagram(nodes: DiagramNode[]): Diagram {
  return { schema_version: 1, settings: {} as Diagram['settings'], nodes, edges: [] }
}

const solutions: BessSolutionInfo[] = [
  { key: 'A', e_container_kwh: 5000, pcs_p_kw: 2500, pcs_lv_kv: 0.69, aux_p_kw: 40, aux_q_kvar: 10,
    containers_by_duration: { '2': 4, '4': 8 } },
  { key: 'B', e_container_kwh: 3440, pcs_p_kw: 1725, pcs_lv_kv: 1.0, aux_p_kw: 30, aux_q_kvar: 8,
    containers_by_duration: { '4': 12, '8': 24 } },
]

const station = (id: string, solution: string) =>
  node(id, 'station', { fleet_kind: 'bess', bess_solution: solution })

describe('supportedDurations', () => {
  it('offers what the one selected solution sells', () => {
    expect(supportedDurations(diagram([station('s1', 'A')]), solutions)).toEqual([2, 4])
  })

  it('offers only what BOTH solutions sell', () => {
    // The duration is one design-level choice, so a design mixing two products
    // can only run at a duration they both tabulate.
    expect(supportedDurations(diagram([station('s1', 'A'), station('s2', 'B')]), solutions)).toEqual([4])
  })

  it('is empty when the design has no BESS station', () => {
    expect(supportedDurations(diagram([node('s1', 'station')]), solutions)).toEqual([])
  })

  it('is empty when two solutions share no duration', () => {
    // No duration is valid: the design has to change product, not duration.
    const disjoint: BessSolutionInfo[] = [
      { ...solutions[0], key: 'A', containers_by_duration: { '2': 4 } },
      { ...solutions[1], key: 'B', containers_by_duration: { '8': 24 } },
    ]
    expect(supportedDurations(diagram([station('s1', 'A'), station('s2', 'B')]), disjoint)).toEqual([])
  })

  it('ignores a station naming a solution the catalogue does not have', () => {
    // Already reported as unknown_bess_solution; it must not silently empty the
    // list and make every duration look unavailable.
    expect(supportedDurations(diagram([station('s1', 'A'), station('s2', 'GONE')]), solutions)).toEqual([2, 4])
  })
})
