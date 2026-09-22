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
  bess_solutions: [],
  bess_transformers: [],
} as unknown as CatalogueResponse

vi.mock('../api', () => ({ seedDiagram: (...args: unknown[]) => seedDiagram(...args) }))
vi.mock('../hooks/useCatalogue', () => ({ useCatalogue: () => catalogue }))

describe('SeedWizard inverter arrangement', () => {
  beforeEach(() => {
    seedDiagram.mockReset()
    seedDiagram.mockResolvedValue(EMPTY_DIAGRAM)
    useStore.setState({ diagram: EMPTY_DIAGRAM, selection: null })
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
      station_model: 'SUNGROW_MVS3200',
      pv_inverter: 'sungrow-sg350hx-20',
      inverter_count: 5,
    })
  })
})
