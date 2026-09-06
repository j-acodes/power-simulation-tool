import { fireEvent, render, screen } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { Inspector } from './Inspector'
import { EMPTY_DIAGRAM, useStore } from '../store'
import type { BessSolutionInfo, CatalogueResponse, DiagramNode, TransformerInfo } from '../types'

const bessSolution: BessSolutionInfo = {
  key: 'sungrow-st6900ux-4h', display_name: 'PowerTitan 3.0 — ST6900UX-4H',
  brand: 'Sungrow', series: 'PowerTitan 3.0', model: 'ST6900UX-4H',
  e_nominal_kwh: 6904, pcs_s_kva: 450, pcs_count: 4, pcs_lv_kv: 0.69, duration_h: 4,
  aux_p_kw: 0, aux_q_kvar: 0,
  datasheet_version: 'Version 3', preliminary: true, datasheet_url: null,
  cell_type: 'LFP', dc_v_min: 1101.6, dc_v_max: 1489.2, ac_v_min: 621.0, ac_v_max: 759.0,
  ac_i_a: 414.0, pf_at_nominal: 0.99, q_range_percent: 100.0, f_nominal_hz: '50 / 60',
  thdi_percent: 1.0, isolation: 'Transformerless', width_mm: 6058, height_mm: 2896,
  depth_mm: 2438, weight_kg: 55000, ip_rating: 'IP55', corrosion_class: 'C4',
  temp_min_c: -30.0, temp_max_c: 45.0, humidity_min_pct: 0.0, humidity_max_pct: 100.0,
  altitude_max_m: 4000.0, cooling: 'Intelligent Liquid Cooling',
}

const bessTransformer: TransformerInfo = {
  key: 'GENERIC_BESS_TX_2750_LV069', display_name: '2750 kVA - Generic', s_rated_kva_at_40c: 2750,
  hv_kv: null, lv_kv: 0.69, brand: 'Generic', uk_percent: 8, pk_kw: 27.5, p0_kw: 2.75,
  i0_percent: 0, model: null, vector_group: null, cooling: null, datasheet_url: null,
  paired_solutions: { [bessSolution.key]: 1 },
}

const pvTransformer: TransformerInfo = {
  key: 'ACME_1000', display_name: 'ACME 1000', s_rated_kva_at_40c: 1000,
  hv_kv: 20, lv_kv: 0.8, brand: 'Acme', uk_percent: 6, pk_kw: 8, p0_kw: 1,
  i0_percent: 0.5, model: null, vector_group: null, cooling: null, datasheet_url: null,
  paired_solutions: {},
}

const catalogue: CatalogueResponse = {
  transformers: [pvTransformer],
  cables: {},
  defaults: {
    tiers: { lv_kv: 0.8, mv_kv: 20, hv_kv: 132 },
    rules: { max_utilization: 0.8, collection_loss_pct: 1.3, export_loss_pct_per_km: 0.1, max_circuit_current_a: 400 },
  },
  bess_solutions: [bessSolution],
  bess_transformers: [bessTransformer],
}

vi.mock('../hooks/useCatalogue', () => ({
  useCatalogue: () => catalogue,
}))

describe('Inspector — palette selection of a catalogue-backed BESS item', () => {
  beforeEach(() => {
    useStore.setState({ selection: null })
  })

  it('offers a control to open the full specification for a selected BESS station transformer', () => {
    useStore.setState({ selection: { type: 'palette', key: bessTransformer.key } })
    render(<Inspector />)

    expect(screen.queryByText('Loading…')).toBeNull()
    // The card heads with the product name, not the raw catalogue key — the
    // key that used to be the headline is still readable, just not as the
    // heading (ticket 06 decision 3).
    expect(screen.getByRole('heading', { name: bessTransformer.display_name })).toBeTruthy()
    expect(screen.getByText(bessTransformer.key)).toBeTruthy()
    // The compact parameter card itself, not just a name-and-button stub.
    expect(screen.getByText('2,750')).toBeTruthy() // s_rated_kva, formatted
    fireEvent.click(screen.getByRole('button', { name: 'View full specification' }))

    // The full spec view is now open, showing the pairing read from the
    // transformer side. A transformer has no DC-side typed group.
    expect(screen.queryByText('DC side')).toBeNull()
    expect(screen.getByText(bessSolution.display_name)).toBeTruthy()
    expect(screen.getByText('1 container(s)')).toBeTruthy()

    fireEvent.keyDown(window, { key: 'Escape' })
    expect(screen.queryByText(bessSolution.display_name)).toBeNull()
  })

  it('offers a control to open the full specification for a selected BESS solution', () => {
    useStore.setState({ selection: { type: 'palette', key: bessSolution.key } })
    render(<Inspector />)

    fireEvent.click(screen.getByRole('button', { name: 'View full specification' }))
    expect(screen.getByText('DC side')).toBeTruthy()
    expect(screen.getByText('Preliminary')).toBeTruthy()
  })
})

function withNode(node: DiagramNode) {
  useStore.setState({
    diagram: { ...EMPTY_DIAGRAM, nodes: [node] },
    selection: { type: 'node', id: node.id },
  })
}

describe('Inspector — expand control for a placed station (ticket 06)', () => {
  beforeEach(() => {
    useStore.setState({ selection: null, diagram: EMPTY_DIAGRAM, designMeta: null })
  })

  it('offers two expand controls for a catalogue-backed BESS station, and closing one leaves the canvas selection intact', () => {
    withNode({
      id: 'n1', kind: 'station', x: 0, y: 0,
      props: { fleet_kind: 'bess', mode: 'catalogue', model: bessTransformer.key, bess_solution: bessSolution.key },
    })
    render(<Inspector />)

    fireEvent.click(screen.getByRole('button', { name: 'Station transformer specification' }))
    expect(screen.getByText('1 container(s)')).toBeTruthy()
    fireEvent.keyDown(window, { key: 'Escape' })
    expect(screen.queryByText('1 container(s)')).toBeNull()
    // The overlay closing did not disturb the canvas selection — the node's
    // properties, including the second control, are still right there.
    expect(useStore.getState().selection).toEqual({ type: 'node', id: 'n1' })
    expect(screen.getByRole('button', { name: 'BESS solution specification' })).toBeTruthy()

    fireEvent.click(screen.getByRole('button', { name: 'BESS solution specification' }))
    expect(screen.getByText('DC side')).toBeTruthy()
  })

  it('names catalogue entries in the property dropdowns the way the product is named', () => {
    // The raw key is what the saved payload stores; it is not what an engineer
    // recognises. A dropdown offering "sungrow-st6900ux-4h" is why a real
    // product can be present in the catalogue and still read as missing.
    withNode({
      id: 'n1', kind: 'station', x: 0, y: 0,
      props: { fleet_kind: 'bess', mode: 'catalogue', model: bessTransformer.key, bess_solution: bessSolution.key },
    })
    render(<Inspector />)

    const named = screen.getAllByRole('option').map((o) => o.textContent)
    expect(named).toContain(bessSolution.display_name)
    expect(named).toContain(bessTransformer.display_name)
    expect(named).not.toContain(bessSolution.key)
    expect(named).not.toContain(bessTransformer.key)
  })

  it('hides both expand controls for a custom BESS station with no solution chosen', () => {
    withNode({
      id: 'n1', kind: 'station', x: 0, y: 0,
      props: {
        fleet_kind: 'bess', mode: 'custom', name: 'Custom BESS station',
        s_rated_kva: 2750, uk_percent: 8, pk_kw: 27.5, p0_kw: 2.75, i0_percent: 0,
      },
    })
    render(<Inspector />)

    expect(screen.queryByRole('button', { name: 'Station transformer specification' })).toBeNull()
    expect(screen.queryByRole('button', { name: 'BESS solution specification' })).toBeNull()
  })

  it('offers one expand control for a catalogue-backed PV station', () => {
    withNode({
      id: 'n1', kind: 'station', x: 0, y: 0,
      props: { fleet_kind: 'pv', mode: 'catalogue', model: pvTransformer.key },
    })
    render(<Inspector />)

    expect(screen.getByRole('button', { name: 'Station transformer specification' })).toBeTruthy()
    expect(screen.queryByRole('button', { name: 'BESS solution specification' })).toBeNull()
  })

  it('hides the expand control for a custom PV station', () => {
    withNode({
      id: 'n1', kind: 'station', x: 0, y: 0,
      props: {
        fleet_kind: 'pv', mode: 'custom', name: 'Custom station',
        s_rated_kva: 1000, uk_percent: 6, pk_kw: 8, p0_kw: 1, i0_percent: 0.5,
      },
    })
    render(<Inspector />)

    expect(screen.queryByRole('button', { name: 'Station transformer specification' })).toBeNull()
  })

  it('hides the BESS solution control for a catalogue-backed BESS station that names no solution yet', () => {
    withNode({
      id: 'n1', kind: 'station', x: 0, y: 0,
      props: { fleet_kind: 'bess', mode: 'catalogue', model: bessTransformer.key },
    })
    render(<Inspector />)

    expect(screen.getByRole('button', { name: 'Station transformer specification' })).toBeTruthy()
    expect(screen.queryByRole('button', { name: 'BESS solution specification' })).toBeNull()
  })
})
