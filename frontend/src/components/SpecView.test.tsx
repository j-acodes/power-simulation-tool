import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { SpecView } from './SpecView'
import type { BessSolutionInfo, TransformerInfo } from '../types'

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
    key: 'GENERIC_BESS_TX_2750_LV069', display_name: '2750 kVA - Generic', s_rated_kva: 2750,
    hv_kv: null, lv_kv: 0.69, brand: 'Generic', uk_percent: 8, pk_kw: 27.5, p0_kw: 2.75,
    i0_percent: 0, model: null, vector_group: null, cooling: null, datasheet_url: null,
    paired_solutions: {},
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

describe('SpecView — BESS station transformer', () => {
  it('shows the pairing from the transformer side, resolved to the solution display name', () => {
    const tx = transformer({ paired_solutions: { [fullSpecSolution.key]: 2 } })
    render(<SpecView target={{ kind: 'bess_transformer', item: tx }} solutions={[fullSpecSolution]} transformers={[]} />)
    expect(screen.getByText(fullSpecSolution.display_name)).toBeTruthy()
    expect(screen.getByText('2 container(s)')).toBeTruthy()
  })

  it('shows its own simulated electrical parameters', () => {
    const tx = transformer()
    render(<SpecView target={{ kind: 'bess_transformer', item: tx }} solutions={[]} transformers={[]} />)
    expect(screen.getByText('2,750 kVA')).toBeTruthy()
  })
})
