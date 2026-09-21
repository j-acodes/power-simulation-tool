import { fireEvent, render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it, vi } from 'vitest'
import { CataloguePage } from './CataloguePage'
import type { BessSolutionInfo, CableInfo, CatalogueResponse, PvInverterInfo, TransformerInfo } from '../types'

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
  switchgear_rated_current_a: 630, switchgear_rating_published: true,
  i0_percent: 0, model: null, vector_group: null, cooling: null, datasheet_url: null,
  s_rated_kva_at_30c: null,
  mv_kv_min: null, mv_kv_max: null, lv_winding_count: 1, insulation_level: null,
  f_nominal: null, uk_tolerance_pct: null, winding_material_mv: null, winding_material_lv: null,
  ip_rating_transformer: null, ip_rating_enclosure: null,
  rmu_kv_min: null, rmu_kv_max: null, rmu_rated_current_a: null, rmu_units: null,
  rmu_relay_protection: null, rmu_short_time_withstand: null,
  cabinet_protection: null, surge_protection: null, ac_insulation_detection: null,
  cabinet_temp_control: null, ups: null,
  width_mm: null, height_mm: null, depth_mm: null, weight_kg: null, cable_entry: null,
  corrosion_class: null, temp_min_c: null, temp_max_c: null, humidity_min_pct: null,
  humidity_max_pct: null, altitude_max_m: null, communication: null, standards: null,
  datasheet_version: null, preliminary: false,
  paired_solutions: { [bessSolution.key]: 1 }, paired_inverters: {},
}

const pvTransformer: TransformerInfo = {
  key: 'ACME_1000', display_name: 'ACME 1000', s_rated_kva_at_40c: 1000,
  hv_kv: 20, lv_kv: 0.8, brand: 'Acme', uk_percent: 6, pk_kw: 8, p0_kw: 1,
  switchgear_rated_current_a: 630, switchgear_rating_published: true,
  i0_percent: 0.5, model: null, vector_group: null, cooling: null, datasheet_url: null,
  s_rated_kva_at_30c: null,
  mv_kv_min: null, mv_kv_max: null, lv_winding_count: 1, insulation_level: null,
  f_nominal: null, uk_tolerance_pct: null, winding_material_mv: null, winding_material_lv: null,
  ip_rating_transformer: null, ip_rating_enclosure: null,
  rmu_kv_min: null, rmu_kv_max: null, rmu_rated_current_a: null, rmu_units: null,
  rmu_relay_protection: null, rmu_short_time_withstand: null,
  cabinet_protection: null, surge_protection: null, ac_insulation_detection: null,
  cabinet_temp_control: null, ups: null,
  width_mm: null, height_mm: null, depth_mm: null, weight_kg: null, cable_entry: null,
  corrosion_class: null, temp_min_c: null, temp_max_c: null, humidity_min_pct: null,
  humidity_max_pct: null, altitude_max_m: null, communication: null, standards: null,
  datasheet_version: null, preliminary: false,
  paired_solutions: {}, paired_inverters: {},
}

const cable: CableInfo = { name: '3x1x240 Al', cross_section_mm2: 240, rated_current_a: 420 }

const pvInverter: PvInverterInfo = {
  key: 'sungrow-sg350hx-20', display_name: 'SG350HX — SG350HX-20', brand: 'Sungrow',
  series: 'SG350HX', model: 'SG350HX-20', power_kw_at_40c: 320, power_kw_at_30c: 352,
  nominal_ac_voltage_kv: 0.8, minimum_power_factor: 0.8, datasheet_url: 'https://example.invalid/sg350.pdf',
  power_provenance: 'Supplier datasheet',
  datasheet_version: 'Version 12', datasheet_date: '2025-03-12', market: 'Europe', preliminary: false,
  maximum_efficiency_percent: 99.02, european_efficiency_percent: 98.8, dc_voltage_max_v: 1500,
  dc_voltage_min_v: 500, dc_voltage_nominal_v: 1160, mppt_count: 12, strings_per_mppt: 2,
  input_current_per_mppt_a: 40, short_circuit_current_per_mppt_a: 60, rated_ac_power_kw: 320,
  max_ac_apparent_power_kva: 352, max_ac_current_a: 254.1, thdi_percent: 3,
  protection: 'Surge protection', width_mm: 1163, height_mm: 1051, depth_mm: 366,
  weight_kg: 162, ip_rating: 'IP66', temp_min_c: -30, temp_max_c: 60, altitude_max_m: 4000,
  cooling: 'Smart forced-air cooling', communication: 'RS485',
}

const catalogue: CatalogueResponse = {
  transformers: [pvTransformer],
  cables: { '20': [cable] },
  defaults: {
    tiers: { lv_kv: 0.8, mv_kv: 20, hv_kv: 132 },
    rules: { max_utilization: 0.8, collection_loss_pct: 1.3, export_loss_pct_per_km: 0.1 },
  },
  bess_solutions: [bessSolution],
  bess_transformers: [bessTransformer],
  pv_inverters: [pvInverter],
}

// The hook is mocked through a mutable holder so a test can vary the catalogue
// it renders against; renderPage() uses the default fixture.
let served: CatalogueResponse = catalogue

vi.mock('../hooks/useCatalogue', () => ({
  useCatalogue: () => served,
}))

function renderWith(c: CatalogueResponse) {
  served = c
  return render(
    <MemoryRouter>
      <CataloguePage />
    </MemoryRouter>,
  )
}

function renderPage() {
  return renderWith(catalogue)
}

describe('CataloguePage', () => {
  it('lists the PV inverter catalogue without making it a canvas palette item', () => {
    renderPage()
    expect(screen.getByText('PV Transformer Stations')).toBeTruthy()
    expect(screen.getByText('PV Inverters')).toBeTruthy()
    fireEvent.click(screen.getByText(pvInverter.display_name).closest('button')!)
    expect(screen.getByText('352 kW / kVA @ 30 °C; 320 kW / kVA @ 40 °C')).toBeTruthy()
    expect(screen.getByText('DC input')).toBeTruthy()
    expect(screen.getByText('Version 12')).toBeTruthy()
  })

  it('lists the other catalogues', () => {
    renderPage()
    expect(screen.getByText('Cables')).toBeTruthy()
    expect(screen.getByText('BESS solutions')).toBeTruthy()
    expect(screen.getByText('BESS station transformers')).toBeTruthy()
  })

  it('shows a BESS solution\'s brand, series and model via its display name', () => {
    renderPage()
    const section = screen.getByText('BESS solutions').closest('section')!
    expect(section.textContent).toContain(bessSolution.brand)
    expect(screen.getByText(bessSolution.display_name)).toBeTruthy()
  })

  it('opens a PV Transformer Station through the complete specification view', () => {
    renderPage()
    fireEvent.click(screen.getByText(pvTransformer.display_name).closest('button')!)
    expect(screen.getByText('What the simulation uses')).toBeTruthy()
    expect(screen.getByText(/1,000 kVA @ 40 °C/)).toBeTruthy()
    expect(screen.queryByText(/BESS/i, { selector: '.spec-view *' })).toBeNull()
  })

  it('cites the source datasheet on a PV transformer that has one', () => {
    // The PV catalogue's numbers were read off published datasheets whose links
    // used to sit in a loose text file beside the YAML. On the entry, the link
    // sits next to the numbers it justifies.
    renderWith({
      ...catalogue,
      transformers: [{ ...pvTransformer, datasheet_url: 'https://example.invalid/acme.pdf' }],
    })
    fireEvent.click(screen.getByText(pvTransformer.display_name).closest('button')!)
    const link = screen.getByRole('link', { name: 'View datasheet' })
    expect(link.getAttribute('href')).toBe('https://example.invalid/acme.pdf')
  })

  it('shows no source link on a transformer that cites none', () => {
    renderWith(catalogue)
    fireEvent.click(screen.getByText(pvTransformer.display_name).closest('button')!)
    expect(screen.queryByRole('link', { name: 'View datasheet' })).toBeNull()
  })

  it('shows a cable\'s existing parameters without a click affordance', () => {
    renderPage()
    expect(screen.getByText(cable.name)).toBeTruthy()
    expect(screen.queryByRole('button', { name: cable.name })).toBeNull()
  })

  it('opens the full specification when a BESS solution row is selected', () => {
    renderPage()
    fireEvent.click(screen.getByText(bessSolution.display_name).closest('button')!)
    expect(screen.getByText('What the simulation uses')).toBeTruthy()
    expect(screen.getByText('Preliminary')).toBeTruthy()

    fireEvent.keyDown(window, { key: 'Escape' })
    expect(screen.queryByText('What the simulation uses')).toBeNull()
  })

  it('opens the full specification when a BESS station transformer row is selected', () => {
    renderPage()
    fireEvent.click(screen.getByText(bessTransformer.display_name).closest('button')!)
    expect(screen.getByText('What the simulation uses')).toBeTruthy()
    // The pairing is visible from the transformer side too.
    expect(screen.getByText('1 container(s)')).toBeTruthy()
  })

  it('offers no technology filter', () => {
    renderPage()
    expect(screen.queryByText(/technology/i)).toBeNull()
  })

  it('groups BESS station transformers by brand, reusing the palette grouping', () => {
    renderPage()
    const section = screen.getByText('BESS station transformers').closest('section')
    expect(section).toBeTruthy()
    const summaries = [...(section as HTMLElement).querySelectorAll('summary')].map((s) => s.textContent)
    expect(summaries).toContain(bessTransformer.brand)
  })
})
