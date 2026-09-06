import { fireEvent, render, screen } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { Palette } from './Palette'
import { useStore } from '../store'
import type { BessSolutionInfo, CatalogueResponse, TransformerInfo } from '../types'

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
  key: 'GENERIC_BESS_TX_2750_LV069', display_name: '2750 kVA - Generic', s_rated_kva: 2750,
  hv_kv: null, lv_kv: 0.69, brand: 'Generic', uk_percent: 8, pk_kw: 27.5, p0_kw: 2.75,
  i0_percent: 0, model: null, vector_group: null, cooling: null, datasheet_url: null,
  paired_solutions: { [bessSolution.key]: 1 },
}

const pvTransformer: TransformerInfo = {
  key: 'ACME_1000', display_name: 'ACME 1000', s_rated_kva: 1000,
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

describe('Palette (ticket 06)', () => {
  beforeEach(() => {
    useStore.setState({ selection: null, designMeta: null })
  })

  it('lists BESS solutions as their own selectable, non-draggable palette items', () => {
    render(<Palette />)

    const item = screen.getByText(bessSolution.display_name)
    expect(item).toBeTruthy()
    expect(item.closest('.palette-item')?.getAttribute('draggable')).toBe('false')

    fireEvent.click(item)
    expect(useStore.getState().selection).toEqual({ type: 'palette', key: bessSolution.key })
  })

  it('labels a BESS station transformer by its display name, not its raw catalogue key', () => {
    render(<Palette />)

    expect(screen.getByText(bessTransformer.display_name)).toBeTruthy()
    expect(screen.queryByText(bessTransformer.key)).toBeNull()
  })

  it('labels a PV station transformer by its display name, not its raw catalogue key', () => {
    render(<Palette />)

    expect(screen.getByText(pvTransformer.display_name)).toBeTruthy()
    expect(screen.queryByText(pvTransformer.key)).toBeNull()
  })
})
