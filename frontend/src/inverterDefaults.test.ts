import { describe, expect, it } from 'vitest'
import { missingInverterSelections } from './inverterDefaults'
import type { Diagram, TransformerInfo } from './types'

const TX = {
  key: 'HUAWEI_JUPITER9000',
  paired_inverters: { 'huawei-sun2000-330ktl-h1': { maximum_count: 30, count_provenance: 'x' } },
} as unknown as TransformerInfo

function diagramOf(props: Array<Record<string, unknown>>): Diagram {
  return {
    schema_version: 1,
    settings: { tiers: { lv_kv: 0.8, mv_kv: 20, hv_kv: 132 }, rules: {} },
    nodes: props.map((p, i) => ({ id: `s${i}`, kind: 'station', x: 0, y: 0, props: p })),
    edges: [],
  } as unknown as Diagram
}

describe('missingInverterSelections', () => {
  it('fills a catalogue PV station that arrived without an inverter', () => {
    // The example plant and pre-pairing saved designs both land here, and the
    // inspector offers no select for a model with one pairing.
    const filled = missingInverterSelections(
      diagramOf([{ mode: 'catalogue', model: 'HUAWEI_JUPITER9000' }]), [TX])
    expect(filled).toEqual([
      { id: 's0', selection: { pv_inverter: 'huawei-sun2000-330ktl-h1', inverter_count: 30 } },
    ])
  })

  it('leaves alone what has no paired inverter to fill', () => {
    const filled = missingInverterSelections(diagramOf([
      { mode: 'catalogue', model: 'HUAWEI_JUPITER9000', pv_inverter: 'other' },
      { mode: 'custom' },
      { mode: 'catalogue', fleet_kind: 'bess', model: 'HUAWEI_JUPITER9000' },
      { mode: 'catalogue', model: 'NOT_IN_CATALOGUE' },
    ]), [TX])
    expect(filled).toEqual([])
  })
})
