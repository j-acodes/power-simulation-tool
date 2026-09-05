import { describe, expect, it } from 'vitest'
import { supportedDurations } from './bess'
import type { BessSolutionInfo, Diagram, DiagramNode, NodeProps } from './types'

function node(id: string, kind: DiagramNode['kind'], props: NodeProps = {}): DiagramNode {
  return { id, kind, x: 0, y: 0, props }
}

function diagram(nodes: DiagramNode[]): Diagram {
  return { schema_version: 1, settings: {} as Diagram['settings'], nodes, edges: [] }
}

function solution(overrides: Partial<BessSolutionInfo>): BessSolutionInfo {
  return {
    key: 'A', display_name: 'Series — Model', brand: 'Brand', series: 'Series', model: 'Model',
    e_nominal_kwh: 5000, pcs_s_kva: 625, pcs_count: 4, pcs_lv_kv: 0.69, duration_h: 4,
    aux_p_kw: 40, aux_q_kvar: 10, containers_per_station: 1,
    datasheet_version: null, preliminary: false, datasheet_url: null,
    ...overrides,
  }
}

const solutions: BessSolutionInfo[] = [
  solution({ key: 'A', duration_h: 4 }),
  solution({ key: 'B', duration_h: 4, pcs_lv_kv: 1.0 }),
  solution({ key: 'C', duration_h: 8 }),
]

const station = (id: string, sol: string) =>
  node(id, 'station', { fleet_kind: 'bess', bess_solution: sol })

describe('supportedDurations', () => {
  it('offers the one selected solution\'s duration', () => {
    expect(supportedDurations(diagram([station('s1', 'A')]), solutions)).toEqual([4])
  })

  it('offers the duration when every selected solution declares the same one', () => {
    // The duration is one design-level choice, so a design mixing two
    // products can only run when they declare the same duration.
    expect(supportedDurations(diagram([station('s1', 'A'), station('s2', 'B')]), solutions)).toEqual([4])
  })

  it('is empty when the design has no BESS station', () => {
    expect(supportedDurations(diagram([node('s1', 'station')]), solutions)).toEqual([])
  })

  it('is empty when two selected solutions declare different durations', () => {
    // No duration is valid: the design has to change product, not duration.
    expect(supportedDurations(diagram([station('s1', 'A'), station('s2', 'C')]), solutions)).toEqual([])
  })

  it('ignores a station naming a solution the catalogue does not have', () => {
    // Already reported as unknown_bess_solution; it must not silently empty the
    // list and make every duration look unavailable.
    expect(supportedDurations(diagram([station('s1', 'A'), station('s2', 'GONE')]), solutions)).toEqual([4])
  })
})
