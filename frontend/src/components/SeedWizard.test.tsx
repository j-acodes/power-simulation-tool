import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { SeedWizard } from './SeedWizard'
import { EMPTY_DIAGRAM, useStore } from '../store'
import type { CatalogueResponse } from '../types'

const seedDiagram = vi.fn()

const catalogue = {
  transformers: [{
    key: 'SUNGROW_MVS3200', display_name: 'MVS3200-LV',
    paired_inverters: { 'sungrow-sg350hx-20': {
      maximum_count: 10,
      count_provenance: 'Engineering interpretation of published LV disconnector quantities',
    } },
  }],
  pv_inverters: [
    { key: 'sungrow-sg350hx-20', display_name: 'SG350HX — SG350HX-20' },
    { key: 'not-paired', display_name: 'Not paired' },
  ],
  cables: {},
  defaults: {
    tiers: { lv_kv: 0.8, mv_kv: 20, hv_kv: 132 },
    rules: { max_utilization: 0.8, collection_loss_pct: 1.3, export_loss_pct_per_km: 0.1 },
  },
  bess_solutions: [
    { key: 'sol-4h', display_name: 'Solution 4h', duration_h: 4 },
    { key: 'sol-2h', display_name: 'Solution 2h', duration_h: 2 },
  ],
  bess_transformers: [
    { key: 'tx-4h', display_name: 'Station for 4h', paired_solutions: { 'sol-4h': 2 }, paired_inverters: {} },
    { key: 'tx-2h', display_name: 'Station for 2h', paired_solutions: { 'sol-2h': 3 }, paired_inverters: {} },
  ],
} as unknown as CatalogueResponse

vi.mock('../api', () => ({ seedDiagram: (...args: unknown[]) => seedDiagram(...args) }))
vi.mock('../hooks/useCatalogue', () => ({ useCatalogue: () => catalogue }))

describe('SeedWizard inverter arrangement', () => {
  beforeEach(() => {
    seedDiagram.mockReset()
    seedDiagram.mockResolvedValue(EMPTY_DIAGRAM)
    useStore.setState({ diagram: EMPTY_DIAGRAM, selection: null, designMeta: null })
  })

  it('narrows inverter selection from the station, defaults the count, and sends all three', async () => {
    render(<SeedWizard onClose={vi.fn()} />)

    await waitFor(() => expect(screen.getByLabelText('PV Transformer Station')).toHaveProperty('value', 'SUNGROW_MVS3200'))
    expect(screen.getByRole('option', { name: 'SG350HX — SG350HX-20' })).toBeTruthy()
    expect(screen.queryByRole('option', { name: 'Not paired' })).toBeNull()
    const count = screen.getByLabelText('Inverters per station')
    expect(count).toHaveProperty('value', '10')
    expect(count.getAttribute('min')).toBe('1')
    expect(count.getAttribute('max')).toBe('10')

    fireEvent.change(count, { target: { value: '5' } })
    fireEvent.click(screen.getByRole('button', { name: 'Seed diagram' }))

    await waitFor(() => expect(seedDiagram).toHaveBeenCalled())
    expect(seedDiagram.mock.calls[0][0]).toMatchObject({
      technology: 'pv',
      station_model: 'SUNGROW_MVS3200',
      pv_inverter: 'sungrow-sg350hx-20',
      inverter_count: 5,
    })
  })

  it('shows no BESS inputs on a PV (or not-yet-loaded) design', async () => {
    render(<SeedWizard onClose={vi.fn()} />)

    await waitFor(() => expect(screen.getByLabelText('PV Transformer Station')).toBeTruthy())
    expect(screen.queryByLabelText('Discharge duration')).toBeNull()
    expect(screen.queryByLabelText('BESS solution')).toBeNull()
    expect(screen.queryByLabelText('BESS station')).toBeNull()
  })
})

describe('SeedWizard on a BESS design', () => {
  beforeEach(() => {
    seedDiagram.mockReset()
    seedDiagram.mockResolvedValue(EMPTY_DIAGRAM)
    useStore.setState({
      diagram: EMPTY_DIAGRAM,
      selection: null,
      designMeta: { id: 1, name: 'BESS design', technology: 'bess', version: 1 },
    })
  })

  it('shows only BESS inputs, cascading duration -> solution -> station', async () => {
    render(<SeedWizard onClose={vi.fn()} />)

    // No PV inputs at all.
    expect(screen.queryByLabelText('PV Transformer Station')).toBeNull()
    expect(screen.queryByLabelText('PV inverter')).toBeNull()
    expect(screen.queryByLabelText('Inverters per station')).toBeNull()

    // Duration defaults to the first on offer, ascending (2h); the solution
    // select narrows to solutions selling it.
    await waitFor(() => expect(screen.getByLabelText('Discharge duration')).toHaveProperty('value', '2'))
    expect(screen.getByRole('option', { name: 'Solution 2h' })).toBeTruthy()
    expect(screen.queryByRole('option', { name: 'Solution 4h' })).toBeNull()
    await waitFor(() => expect(screen.getByLabelText('BESS solution')).toHaveProperty('value', 'sol-2h'))

    // The station select narrows to stations paired with that solution.
    expect(screen.getByRole('option', { name: 'Station for 2h' })).toBeTruthy()
    expect(screen.queryByRole('option', { name: 'Station for 4h' })).toBeNull()
    await waitFor(() => expect(screen.getByLabelText('BESS station')).toHaveProperty('value', 'tx-2h'))

    // Switching duration re-narrows both downstream selects.
    fireEvent.change(screen.getByLabelText('Discharge duration'), { target: { value: '4' } })
    await waitFor(() => expect(screen.getByLabelText('BESS solution')).toHaveProperty('value', 'sol-4h'))
    await waitFor(() => expect(screen.getByLabelText('BESS station')).toHaveProperty('value', 'tx-4h'))

    // Starts at the same reference value the PV power field uses, not 0 —
    // submitting the defaults used to 400 with no field-level indication.
    expect(screen.getByLabelText('Target BESS Active power P (MW)')).toHaveProperty('value', '45')

    fireEvent.change(screen.getByLabelText('Target BESS Active power P (MW)'), { target: { value: '5' } })
    fireEvent.click(screen.getByRole('button', { name: 'Seed diagram' }))

    await waitFor(() => expect(seedDiagram).toHaveBeenCalled())
    expect(seedDiagram.mock.calls[0][0]).toMatchObject({
      technology: 'bess',
      discharge_hours: 4,
      bess_solution: 'sol-4h',
      bess_station_model: 'tx-4h',
      p_poc_bess_mw: 5,
    })
  })
})
