import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { SpecView } from './SpecView'
import type { BessSolutionInfo, PvInverterInfo, TransformerInfo } from '../types'

function inverter(overrides: Partial<PvInverterInfo> = {}): PvInverterInfo {
  return {
    key: 'huawei-sun2000-330ktl-h1', display_name: 'SUN2000 — SUN2000-330KTL-H1',
    brand: 'Huawei', series: 'SUN2000', model: 'SUN2000-330KTL-H1',
    power_kw_at_40c: 300, power_kw_at_30c: 330, nominal_ac_voltage_kv: 0.8,
    minimum_power_factor: 0.8, power_provenance: 'Owner-declared engineering basis',
    datasheet_url: 'https://example.com/huawei.pdf', datasheet_version: '2023-05-15',
    datasheet_date: '2023-05-15', market: 'APAC, LATAM & Europe', preliminary: false,
    maximum_efficiency_percent: 99.03, european_efficiency_percent: null,
    dc_voltage_max_v: 1500, dc_voltage_min_v: 500, dc_voltage_nominal_v: 1080,
    mppt_count: 6, strings_per_mppt: null, input_current_per_mppt_a: 65,
    short_circuit_current_per_mppt_a: 115, rated_ac_power_kw: 300,
    max_ac_apparent_power_kva: 330, max_ac_current_a: 238.2, thdi_percent: 1,
    protection: 'Supplier protection set', width_mm: 1048, height_mm: 732, depth_mm: 395,
    weight_kg: 112, ip_rating: 'IP66', temp_min_c: -25, temp_max_c: 60,
    altitude_max_m: 4000, cooling: 'Smart air cooling', communication: 'MBUS, RS485',
    max_ac_active_power_kw: 330, nominal_ac_current_a: 216.6,
    rated_grid_frequency: '50 / 60 Hz', adjustable_power_factor: '0.8 leading – 0.8 lagging',
    pv_inputs_per_mppt: '4 / 5 / 5 / 4 / 5 / 5', start_voltage_v: 550,
    relative_humidity: '0–100% non-condensing', corrosion_class: 'C5-Medium',
    isolation: 'Transformerless', dc_connector: null, ac_connector: null,
    standards: 'IEC 62109-1/-2', grid_support: null,
    ...overrides,
  }
}

function solution(overrides: Partial<BessSolutionInfo> = {}): BessSolutionInfo {
  return {
    key: 'sungrow-st6900ux-4h', display_name: 'PowerTitan 3.0 — ST6900UX-4H',
    brand: 'Sungrow', series: 'PowerTitan 3.0', model: 'ST6900UX-4H',
    e_nominal_kwh: 6904, pcs_s_kva: 450, pcs_count: 4, pcs_lv_kv: 0.69, duration_h: 4,
    // Matches the real Sungrow entry: the datasheet publishes no auxiliary
    // figure (ticket 07 of component-datasheets).
    aux_p_kw: null, aux_q_kvar: null,
    datasheet_version: 'Version 3', preliminary: true, datasheet_url: null,
    cell_type: null, dc_v_min: null, dc_v_max: null, ac_v_min: null, ac_v_max: null,
    ac_i_a: null, pf_at_nominal: null, q_range_percent: null, f_nominal_hz: null,
    thdi_percent: null, isolation: null, width_mm: null, height_mm: null, depth_mm: null,
    weight_kg: null, ip_rating: null, corrosion_class: null, temp_min_c: null, temp_max_c: null,
    humidity_min_pct: null, humidity_max_pct: null, altitude_max_m: null, cooling: null,
    ...overrides,
  }
}

function transformer(overrides: Partial<TransformerInfo> = {}): TransformerInfo {
  return {
    key: 'GENERIC_BESS_TX_2750_LV069', display_name: '2750 kVA - Generic', s_rated_kva_at_40c: 2750,
    hv_kv: null, lv_kv: 0.69, brand: 'Generic', uk_percent: 8, pk_kw: 27.5, p0_kw: 2.75,
    switchgear_rated_current_a: 630, switchgear_rating_published: true,
    cable_entry_parallel_limit: 2, cable_entry_cross_section_limit_mm2: 300,
    cable_entry_published: false,
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
    cable_entry_cables_per_phase: null, cable_entry_max_cross_section_mm2: null,
    corrosion_class: null, temp_min_c: null, temp_max_c: null, humidity_min_pct: null,
    humidity_max_pct: null, altitude_max_m: null, communication: null, standards: null,
    datasheet_version: null, preliminary: false,
    paired_solutions: {}, paired_inverters: {},
    ...overrides,
  }
}

const fullSpecSolution = solution({
  cell_type: 'LFP', dc_v_min: 1101.6, dc_v_max: 1489.2, ac_v_min: 621.0, ac_v_max: 759.0,
  ac_i_a: 414.0, pf_at_nominal: 0.99, q_range_percent: 100.0, f_nominal_hz: '50 / 60',
  thdi_percent: 1.0, isolation: 'Transformerless', width_mm: 6058, height_mm: 2896,
  depth_mm: 2438, weight_kg: 55000, ip_rating: 'IP55', corrosion_class: 'C4',
  temp_min_c: -30.0, temp_max_c: 45.0, humidity_min_pct: 0.0, humidity_max_pct: 100.0,
  altitude_max_m: 4000.0, cooling: 'Intelligent Liquid Cooling',
  datasheet_url: 'https://example.com/datasheet.pdf',
})

describe('SpecView — BESS solution', () => {
  it('renders the simulated block before the typed specification, in datasheet order', () => {
    const pairedTx = transformer({ paired_solutions: { [fullSpecSolution.key]: 1 } })
    render(<SpecView target={{ kind: 'bess_solution', item: fullSpecSolution }} solutions={[]} transformers={[pairedTx]} />)

    const headings = screen.getAllByRole('heading', { level: 3 }).map((h) => h.textContent)
    expect(headings).toEqual([
      'What the simulation uses',
      'DC side',
      'AC side',
      'Physical',
      'Environmental',
      'Sold with these station transformers',
      'Datasheet',
    ])
  })

  it('shows the simulated figures the engine actually reads', () => {
    render(<SpecView target={{ kind: 'bess_solution', item: fullSpecSolution }} solutions={[]} transformers={[]} />)
    expect(screen.getByText('6,904 kWh')).toBeTruthy()
    expect(screen.getByText('450 kVA x 4')).toBeTruthy()
    expect(screen.getByText('4 h')).toBeTruthy()
  })

  it('renders the comparator for an inequality bound, not a bare number', () => {
    render(<SpecView target={{ kind: 'bess_solution', item: fullSpecSolution }} solutions={[]} transformers={[]} />)
    expect(screen.getByText('> 0.99')).toBeTruthy()
    expect(screen.getByText('< 1%')).toBeTruthy()
  })

  it('says "Not published" for an unpublished auxiliary figure, not "0.0 kW"', () => {
    // fullSpecSolution's aux_p_kw/aux_q_kvar are null — the datasheet publishes
    // no figure, which is not the same value as a real zero (ticket 07).
    render(<SpecView target={{ kind: 'bess_solution', item: fullSpecSolution }} solutions={[]} transformers={[]} />)
    expect(screen.getByText('Not published')).toBeTruthy()
    expect(screen.queryByText(/kW \/.*kvar/)).toBeNull()
  })

  it('shows the actual figures when a solution does publish auxiliary consumption', () => {
    const published = solution({ aux_p_kw: 40, aux_q_kvar: 10 })
    render(<SpecView target={{ kind: 'bess_solution', item: published }} solutions={[]} transformers={[]} />)
    expect(screen.getByText('40 kW / 10 kvar')).toBeTruthy()
    expect(screen.queryByText('Not published')).toBeNull()
  })

  it('marks a preliminary datasheet', () => {
    render(<SpecView target={{ kind: 'bess_solution', item: fullSpecSolution }} solutions={[]} transformers={[]} />)
    expect(screen.getByText('Preliminary')).toBeTruthy()
  })

  it('omits a group entirely when every field in it is null', () => {
    render(<SpecView target={{ kind: 'bess_solution', item: solution() }} solutions={[]} transformers={[]} />)
    expect(screen.queryByText('DC side')).toBeNull()
    expect(screen.queryByText('AC side')).toBeNull()
    expect(screen.queryByText('Physical')).toBeNull()
    expect(screen.queryByText('Environmental')).toBeNull()
  })

  it('shows the datasheet link only when a URL is present', () => {
    const { rerender } = render(
      <SpecView target={{ kind: 'bess_solution', item: fullSpecSolution }} solutions={[]} transformers={[]} />,
    )
    expect(screen.getByRole('link', { name: 'View datasheet' })).toBeTruthy()

    rerender(<SpecView target={{ kind: 'bess_solution', item: solution({ datasheet_url: '', datasheet_version: null }) }} solutions={[]} transformers={[]} />)
    expect(screen.queryByRole('link')).toBeNull()
    expect(screen.queryByText('Datasheet')).toBeNull()
  })

  it('still names the datasheet revision when there is no public URL', () => {
    // The shipped Sungrow entry is exactly this shape: transcribed from
    // "Version 3", with no linkable source. Hiding the revision would leave
    // the numbers undefendable in a design review.
    render(
      <SpecView
        target={{ kind: 'bess_solution', item: solution({ datasheet_url: '', datasheet_version: 'Version 3' }) }}
        solutions={[]}
        transformers={[]}
      />,
    )
    expect(screen.getByText('Datasheet')).toBeTruthy()
    expect(screen.getByText('Version 3')).toBeTruthy()
    expect(screen.queryByRole('link')).toBeNull()
  })

  it('lists the station transformers a solution is paired with, and the containers each serves', () => {
    const transformers = [
      transformer({ key: 'TX_A', paired_solutions: { [fullSpecSolution.key]: 1 } }),
      transformer({ key: 'TX_B', display_name: 'TX_B display', paired_solutions: { [fullSpecSolution.key]: 2 } }),
      transformer({ key: 'TX_UNPAIRED', paired_solutions: {} }),
    ]
    render(<SpecView target={{ kind: 'bess_solution', item: fullSpecSolution }} solutions={[]} transformers={transformers} />)
    expect(screen.getByText('1 container(s)')).toBeTruthy()
    expect(screen.getByText('2 container(s)')).toBeTruthy()
    expect(screen.getByText('TX_B display')).toBeTruthy()
    expect(screen.queryByText('TX_UNPAIRED')).toBeNull()
  })
})

describe('SpecView — BESS transformer station', () => {
  it('shows the pairing from the transformer side, resolved to the solution display name', () => {
    const tx = transformer({ paired_solutions: { [fullSpecSolution.key]: 2 } })
    render(<SpecView target={{ kind: 'transformer_station', fleet_kind: 'bess', item: tx }} solutions={[fullSpecSolution]} transformers={[]} />)
    expect(screen.getByText(fullSpecSolution.display_name)).toBeTruthy()
    expect(screen.getByText('2 container(s)')).toBeTruthy()
  })

  it('shows its own simulated electrical parameters', () => {
    const tx = transformer()
    render(<SpecView target={{ kind: 'transformer_station', fleet_kind: 'bess', item: tx }} solutions={[]} transformers={[]} />)
    expect(screen.getByText(/2,750 kVA @ 40 °C/)).toBeTruthy()
  })
})

describe('SpecView — PV transformer station', () => {
  it('renders the generic product contract without presenting the station as BESS', () => {
    const tx = transformer({
      key: 'ACME_PV_TS_3200',
      display_name: 'Acme PV Transformer Station 3200',
      brand: 'Acme',
      series: 'PV Turnkey',
      model: 'PV-TS-3200',
      vector_group: 'Dy11',
      standards: 'IEC 60076',
      datasheet_version: 'Revision 2',
      datasheet_date: '2026-04-18',
      market: 'Europe',
      datasheet_url: 'https://example.com/pv-transformer-station.pdf',
    })

    const { container } = render(
      <SpecView
        target={{ kind: 'transformer_station', fleet_kind: 'pv', item: tx }}
        solutions={[]}
        transformers={[]}
      />,
    )

    const headings = [...container.querySelectorAll('.spec-view h3')].map((heading) => heading.textContent)
    expect(headings).toEqual([
      'What the simulation uses',
      'Input and LV panel',
      'Output transformer',
      'RMU',
      'Auxiliary transformer',
      'Protection and options',
      'General and environmental',
      'Communications and standards',
      'Datasheet',
    ])
    expect(screen.getByText('PV-TS-3200')).toBeTruthy()
    expect(screen.getByText('PV Turnkey')).toBeTruthy()
    expect(screen.getByText('Revision 2')).toBeTruthy()
    expect(screen.getByText('2026-04-18')).toBeTruthy()
    expect(screen.getByText('Europe')).toBeTruthy()
    expect(screen.queryByText(/BESS/i)).toBeNull()
  })

  it('shows the inverter-count provenance beside the station pairing', () => {
    const pairedInverter = inverter()
    const tx = transformer({
      paired_inverters: {
        [pairedInverter.key]: {
          maximum_count: 11,
          count_provenance: 'Supplier-published maximum LV AC inputs',
        },
      },
    })
    render(
      <SpecView
        target={{ kind: 'transformer_station', fleet_kind: 'pv', item: tx }}
        solutions={[]}
        transformers={[]}
        pvInverters={[pairedInverter]}
      />,
    )
    expect(screen.getByText(/Supplier-published maximum LV AC inputs/)).toBeTruthy()
  })
})

describe('SpecView — PV inverter provenance and missing supplier facts', () => {
  it('keeps Huawei simulation power visibly owner-declared beside supplier facts', () => {
    render(<SpecView target={{ kind: 'pv_inverter', item: inverter() }} solutions={[]} transformers={[]} />)
    expect(screen.getByText('330 kW / kVA @ 30 °C; 300 kW / kVA @ 40 °C')).toBeTruthy()
    expect(screen.getByText('Owner-declared engineering basis')).toBeTruthy()
    expect(screen.getByText('300 kW')).toBeTruthy()
    expect(screen.getAllByText('330 kW').length).toBeGreaterThan(0)
    expect(screen.getByText('330 kVA')).toBeTruthy()
  })

  it('renders a missing typed field as Not published', () => {
    render(<SpecView target={{ kind: 'pv_inverter', item: inverter() }} solutions={[]} transformers={[]} />)
    const row = screen.getByText('European efficiency').closest('.kv-row')
    expect(row?.textContent).toContain('Not published')
  })

  it('shows the inverter-count provenance from the station pairing', () => {
    const item = inverter({ key: 'sungrow-sg350hx-20' })
    const tx = transformer({
      paired_inverters: {
        [item.key]: {
          maximum_count: 10,
          count_provenance: 'Engineering interpretation of published LV disconnector quantities',
        },
      },
    })
    render(
      <SpecView
        target={{ kind: 'pv_inverter', item }}
        solutions={[]}
        transformers={[]}
        pvTransformers={[tx]}
      />,
    )
    expect(screen.getByText(/Engineering interpretation of published LV disconnector quantities/)).toBeTruthy()
  })
})

describe('switchgear rated current', () => {
  it('shows a published rating plainly', () => {
    const tx = transformer({ switchgear_rated_current_a: 630, switchgear_rating_published: true })
    render(<SpecView target={{ kind: 'transformer_station', fleet_kind: 'pv', item: tx }} solutions={[]} transformers={[]} />)
    expect(screen.getByText('Switchgear rated current')).toBeTruthy()
    expect(screen.getByText('630 A')).toBeTruthy()
  })

  it('marks a defaulted rating so it never reads as a supplier claim', () => {
    const tx = transformer({ switchgear_rated_current_a: 630, switchgear_rating_published: false })
    render(<SpecView target={{ kind: 'transformer_station', fleet_kind: 'pv', item: tx }} solutions={[]} transformers={[]} />)
    expect(screen.getByText(/630 A \(not published — standard rating assumed\)/)).toBeTruthy()
  })
})

describe('cable entry (ADR-0007)', () => {
  it('shows the simulated figure the engine reads, distinct from the typed provenance field', () => {
    const tx = transformer({
      cable_entry_parallel_limit: 3, cable_entry_cross_section_limit_mm2: 500,
      cable_entry_published: true, cable_entry_cables_per_phase: 3,
      cable_entry_max_cross_section_mm2: 500, cable_entry: 'Bottom entry',
    })
    render(<SpecView target={{ kind: 'transformer_station', fleet_kind: 'pv', item: tx }} solutions={[]} transformers={[]} />)
    expect(screen.getByText('Cable entry (simulated)')).toBeTruthy()
    expect(screen.getByText('3 x 500 mm²')).toBeTruthy()
    // The typed datasheet-provenance field stays, unrelated to the simulated figure.
    expect(screen.getByText('Cable entry')).toBeTruthy()
    expect(screen.getByText('Bottom entry')).toBeTruthy()
  })

  it('marks a defaulted cable entry so it never reads as a supplier claim', () => {
    const tx = transformer({
      cable_entry_parallel_limit: 2, cable_entry_cross_section_limit_mm2: 300,
      cable_entry_published: false,
    })
    render(<SpecView target={{ kind: 'transformer_station', fleet_kind: 'pv', item: tx }} solutions={[]} transformers={[]} />)
    expect(screen.getByText(/2 x 300 mm² \(not published — standard entry assumed\)/)).toBeTruthy()
  })
})
