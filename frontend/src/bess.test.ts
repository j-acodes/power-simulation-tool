import { describe, expect, it } from 'vitest'
import { supportedDurations } from './bess'
import type { BessSolutionInfo, Diagram, DiagramNode, NodeProps, TransformerInfo } from './types'

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
    aux_p_kw: 40, aux_q_kvar: 10,
    datasheet_version: null, preliminary: false, datasheet_url: null,
    cell_type: null, dc_v_min: null, dc_v_max: null, ac_v_min: null, ac_v_max: null,
    ac_i_a: null, pf_at_nominal: null, q_range_percent: null, f_nominal_hz: null,
    thdi_percent: null, isolation: null, width_mm: null, height_mm: null, depth_mm: null,
    weight_kg: null, ip_rating: null, corrosion_class: null, temp_min_c: null, temp_max_c: null,
    humidity_min_pct: null, humidity_max_pct: null, altitude_max_m: null, cooling: null,
    ...overrides,
  }
}

function transformer(overrides: Partial<TransformerInfo>): TransformerInfo {
  return {
    key: 'TX', display_name: 'TX', s_rated_kva: 2750, hv_kv: null, lv_kv: 0.69,
    brand: 'Generic', uk_percent: 8, pk_kw: 27.5, p0_kw: 2.75, i0_percent: 0,
    model: null, vector_group: null, cooling: null, datasheet_url: null,
    paired_solutions: {},
    ...overrides,
  }
}

const solutions: BessSolutionInfo[] = [
  solution({ key: 'A', duration_h: 4 }),
  solution({ key: 'B', duration_h: 4, pcs_lv_kv: 1.0 }),
  solution({ key: 'C', duration_h: 8 }),
]

const transformers: TransformerInfo[] = [
  transformer({ key: 'TX_A', paired_solutions: { A: 1 } }),
  transformer({ key: 'TX_B', paired_solutions: { B: 1 } }),
  transformer({ key: 'TX_AB', paired_solutions: { A: 1, C: 2 } }),
  transformer({ key: 'TX_C', paired_solutions: { C: 1 } }),
  transformer({ key: 'TX_UNPAIRED', paired_solutions: {} }),
]

const station = (id: string, model: string, sol?: string) =>
  node(id, 'station', { fleet_kind: 'bess', mode: 'catalogue', model, bess_solution: sol })

describe('supportedDurations', () => {
  it('offers the duration paired with the selected station transformer', () => {
    expect(supportedDurations(diagram([station('s1', 'TX_A', 'A')]), transformers, solutions))
      .toEqual([4])
  })

  it('offers the duration when every drawn station\'s transformer sells the same one', () => {
    expect(
      supportedDurations(
        diagram([station('s1', 'TX_A', 'A'), station('s2', 'TX_B', 'B')]),
        transformers,
        solutions,
      ),
    ).toEqual([4])
  })

  it('is empty when the design has no BESS station', () => {
    expect(supportedDurations(diagram([node('s1', 'station')]), transformers, solutions)).toEqual([])
  })

  it('is empty when two stations\' transformers share no duration in common', () => {
    // TX_A sells only 4 h; TX_C sells only 8 h — no duration is valid, the
    // design has to change product (or transformer), not duration.
    expect(
      supportedDurations(
        diagram([station('s1', 'TX_A', 'A'), station('s2', 'TX_C', 'C')]),
        transformers,
        solutions,
      ),
    ).toEqual([])
  })

  it('offers every duration a multi-solution transformer sells', () => {
    expect(supportedDurations(diagram([station('s1', 'TX_AB')]), transformers, solutions))
      .toEqual([4, 8])
  })

  it('ignores a station whose transformer is not a resolvable, paired catalogue key', () => {
    // Already reported as unknown_model or unpaired_bess_solution server-side;
    // it must not silently empty the list and make every duration unavailable.
    expect(
      supportedDurations(
        diagram([station('s1', 'TX_A', 'A'), station('s2', 'TX_UNPAIRED')]),
        transformers,
        solutions,
      ),
    ).toEqual([4])
    expect(
      supportedDurations(
        diagram([station('s1', 'TX_A', 'A'), station('s2', 'GONE')]),
        transformers,
        solutions,
      ),
    ).toEqual([4])
  })
})
