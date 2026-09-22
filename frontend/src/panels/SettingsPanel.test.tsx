import { fireEvent, render, screen } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { SettingsPanel } from './SettingsPanel'
import { EMPTY_DIAGRAM, useStore } from '../store'

// SettingsPanel only reads `bess_transformers`/`bess_solutions` off the
// catalogue (to decide whether to show the BESS duration control), and the
// diagram under test draws no BESS station — so a null catalogue (as if the
// fetch had not resolved yet) is enough, without pulling in a full
// CatalogueResponse fixture.
vi.mock('../hooks/useCatalogue', () => ({
  useCatalogue: () => null,
}))

describe('SettingsPanel (ticket 06)', () => {
  beforeEach(() => {
    useStore.setState({ selection: null, designMeta: null, diagram: EMPTY_DIAGRAM })
  })

  it('shows the feeders-per-busbar rule defaulting to 12', () => {
    render(<SettingsPanel />)
    const input = screen.getByLabelText('Feeders per busbar') as HTMLInputElement
    expect(input.value).toBe('12')
  })

  it('honours a saved feeders-per-busbar override', () => {
    useStore.setState({
      diagram: {
        ...EMPTY_DIAGRAM,
        settings: {
          ...EMPTY_DIAGRAM.settings,
          rules: { ...EMPTY_DIAGRAM.settings.rules, feeders_per_busbar: 6 },
        },
      },
    })
    render(<SettingsPanel />)
    const input = screen.getByLabelText('Feeders per busbar') as HTMLInputElement
    expect(input.value).toBe('6')
  })

  it('updates the setting when edited', () => {
    render(<SettingsPanel />)
    const input = screen.getByLabelText('Feeders per busbar') as HTMLInputElement
    fireEvent.change(input, { target: { value: '8' } })
    expect(useStore.getState().diagram.settings.rules.feeders_per_busbar).toBe(8)
  })
})
