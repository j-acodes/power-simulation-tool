import type { Diagram } from './types'

/**
 * The 45 MW example plant, drawn by hand — same data as the golden fixture in
 * tests/test_graph.py (_drawn_example over the arrange_plant arrangement:
 * circuit_sizes == [2, 2, 2, 1, 1], models [[9000,3300]]*3 + [[9000]]*2).
 * POC at the substation fence (0 m export), HV interconnection at 132 kV,
 * 20 kV MV collection, 800 m trunk / 350 m inter-station spacing, 120 kW /
 * 40 kvar aux load. This is the M2 acceptance vehicle: "Load example plant"
 * must reproduce the Stage-2 results on screen.
 */

const TRUNK_M = 800
const SPACING_M = 350

// [model key, count] per circuit, in drawn order.
const CIRCUITS: Array<Array<'HUAWEI_JUPITER9000' | 'HUAWEI_JUPITER3000'>> = [
  ['HUAWEI_JUPITER9000', 'HUAWEI_JUPITER3000'],
  ['HUAWEI_JUPITER9000', 'HUAWEI_JUPITER3000'],
  ['HUAWEI_JUPITER9000', 'HUAWEI_JUPITER3000'],
  ['HUAWEI_JUPITER9000'],
  ['HUAWEI_JUPITER9000'],
]

function buildExample(): Diagram {
  const nodes: Diagram['nodes'] = [
    { id: 'poc', kind: 'poc', x: 600, y: 0, props: { p_target_mw: 45.0, pf: 0.95 } },
    { id: 'hv', kind: 'hv_tx', x: 600, y: 110, props: { mode: 'auto', n_parallel: 1 } },
    { id: 'bus', kind: 'busbar', x: 600, y: 220, props: {} },
    { id: 'aux', kind: 'aux', x: 1020, y: 300, props: { p_kw: 120.0, q_kvar: 40.0 } },
  ]
  const edges: Diagram['edges'] = [
    { id: 'e_export', source: 'poc', target: 'hv', tier: 'hv', length_m: 0, sizing: { mode: 'auto' } },
    { id: 'e_sub', source: 'hv', target: 'bus', tier: 'mv', sizing: { mode: 'auto' } },
    { id: 'e_aux', source: 'bus', target: 'aux', tier: 'mv', sizing: { mode: 'auto' } },
  ]

  CIRCUITS.forEach((models, cIdx) => {
    const c = cIdx + 1
    const x = 100 + cIdx * 180
    let previousId: string | null = null
    models.forEach((model, sIdx) => {
      const s = sIdx + 1
      const nodeId = `s${c}_${s}`
      const edgeId = `c${c}_seg${s}`
      nodes.push({
        id: nodeId,
        kind: 'station',
        x,
        y: 320 + sIdx * 120,
        props: { mode: 'catalogue', model },
      })
      edges.push({
        id: edgeId,
        source: previousId ?? 'bus',
        target: nodeId,
        tier: 'mv',
        length_m: previousId === null ? TRUNK_M : SPACING_M,
        sizing: { mode: 'auto' },
      })
      previousId = nodeId
    })
  })

  return {
    schema_version: 1,
    settings: {
      tiers: { lv_kv: 0.8, mv_kv: 20.0, hv_kv: 132.0 },
      rules: {
        max_utilization: 0.8,
        collection_loss_pct: 1.3,
        export_loss_pct_per_km: 0.1,
        max_circuit_current_a: 400.0,
      },
    },
    nodes,
    edges,
  }
}

export const EXAMPLE_DIAGRAM: Diagram = buildExample()
