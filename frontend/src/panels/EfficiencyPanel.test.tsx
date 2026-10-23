import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { EfficiencyPanel } from './EfficiencyPanel'
import { EMPTY_DIAGRAM, useStore } from '../store'
import type { EfficiencyResponse } from '../types'

const runEfficiency = vi.fn()
vi.mock('../api', () => ({ runEfficiency: (...args: unknown[]) => runEfficiency(...args) }))

const RESPONSE: EfficiencyResponse = {
  rows: [
    { timestamp: 't0', operating_rte_pct: 88.62461, idle_loss_kwh_per_h: 416.8964, pcs_power_pct: 100 },
    { timestamp: 't1', operating_rte_pct: 86.10002, idle_loss_kwh_per_h: 1048.256, pcs_power_pct: 76.00000000000001 },
  ],
  warnings: ['1 timestamps had an ambient outside the published range -30 to 50 °C'],
}

function upload(text: string) {
  const input = screen.getByLabelText('Ambient CSV') as HTMLInputElement
  fireEvent.change(input, { target: { files: [new File([text], 'ambient.csv', { type: 'text/csv' })] } })
}

describe('EfficiencyPanel (ticket 17)', () => {
  beforeEach(() => {
    runEfficiency.mockReset()
    useStore.setState({ selection: null, designMeta: null, diagram: EMPTY_DIAGRAM })
  })
  afterEach(() => vi.restoreAllMocks())

  it('reports bad CSV rows and does not offer the run', async () => {
    render(<EfficiencyPanel />)
    upload('timestamp,ambient_c\nt0,25\nt1,hot\n')

    expect(await screen.findByText('Row 3: ambient "hot" is not a number.')).toBeTruthy()
    expect((screen.getByRole('button', { name: 'Run efficiency run' }) as HTMLButtonElement).disabled).toBe(true)
  })

  it('runs the design on the canvas and shows summary, warnings and chart', async () => {
    runEfficiency.mockResolvedValue(RESPONSE)
    render(<EfficiencyPanel />)
    upload('timestamp,ambient_c\nt0,25\nt1,48\n')
    await screen.findByText('2 timestamps read.')
    fireEvent.change(screen.getByLabelText('Cycles per day'), { target: { value: '1.5' } })
    fireEvent.change(screen.getByLabelText(/Cell round-trip efficiency/), { target: { value: '93' } })
    fireEvent.click(screen.getByRole('button', { name: 'Run efficiency run' }))

    await screen.findByRole('heading', { name: 'Summary' })
    expect(runEfficiency).toHaveBeenCalledWith({
      diagram: EMPTY_DIAGRAM,
      rows: [{ timestamp: 't0', ambient_c: 25 }, { timestamp: 't1', ambient_c: 48 }],
      cycles_per_day: 1.5,
      cell_rte_pct: 93,
    })
    const summary = within(screen.getByRole('table', { name: 'Summary' }))
    expect(summary.getByText('Minimum operating RTE').nextSibling?.textContent).toBe('86.10 %')
    expect(summary.getByText('Average operating RTE').nextSibling?.textContent).toBe('87.36 %')
    expect(summary.getByText('Maximum operating RTE').nextSibling?.textContent).toBe('88.62 %')
    expect(summary.getByText('Average idle standby loss').nextSibling?.textContent).toBe('733 kWh per idle hour')
    expect(summary.getByText('Timestamps with PCS derating').nextSibling?.textContent).toBe('1 of 2')
    expect(screen.getByText(RESPONSE.warnings[0])).toBeTruthy()
    expect(screen.getByRole('img', { name: /Operating RTE, idle standby loss and PCS power/ })).toBeTruthy()
  })

  it('leaves the cell RTE to the catalogue when the override is blank', async () => {
    runEfficiency.mockResolvedValue(RESPONSE)
    render(<EfficiencyPanel />)
    upload('timestamp,ambient_c\nt0,25\n')
    await screen.findByText('1 timestamp read.')
    fireEvent.click(screen.getByRole('button', { name: 'Run efficiency run' }))

    await screen.findByRole('heading', { name: 'Summary' })
    expect(runEfficiency.mock.calls[0][0]).toMatchObject({ cycles_per_day: 1, cell_rte_pct: null })
  })

  it("shows the run's error message when the engine refuses the design", async () => {
    runEfficiency.mockRejectedValue(new Error('the design has no BESS fleet'))
    render(<EfficiencyPanel />)
    upload('timestamp,ambient_c\nt0,25\n')
    await screen.findByText('1 timestamp read.')
    fireEvent.click(screen.getByRole('button', { name: 'Run efficiency run' }))

    expect((await screen.findByRole('alert')).textContent).toContain('the design has no BESS fleet')
    expect(screen.queryByRole('heading', { name: 'Summary' })).toBeNull()
  })

  it('downloads the four-column CSV as the CLI writes it', async () => {
    runEfficiency.mockResolvedValue(RESPONSE)
    let blob: Blob | undefined
    URL.createObjectURL = vi.fn((b: Blob) => {
      blob = b
      return 'blob:x'
    })
    URL.revokeObjectURL = vi.fn()
    vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {})
    render(<EfficiencyPanel />)
    upload('timestamp,ambient_c\nt0,25\nt1,48\n')
    await screen.findByText('2 timestamps read.')
    fireEvent.click(screen.getByRole('button', { name: 'Run efficiency run' }))
    fireEvent.click(await screen.findByRole('button', { name: 'Download CSV' }))

    await waitFor(() => expect(blob).toBeDefined())
    expect(await blob!.text()).toBe(
      'timestamp,operating RTE %,idle loss kWh/h,PCS power % of rated\r\n' +
        't0,88.6246,416.896,100\r\n' +
        't1,86.1,1048.26,76\r\n',
    )
  })
})
