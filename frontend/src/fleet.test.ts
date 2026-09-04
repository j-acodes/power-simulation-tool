import { describe, expect, it } from 'vitest'
import { conversionLabel, conversionLabelPlural, fleetLabel } from './fleet'

describe('conversionLabel', () => {
  it('names the conversion device per fleet kind', () => {
    // Mirrors powertool.components.conversion_label. Presentation only: the
    // result FIELDS are neither renamed nor duplicated, because a PCS's
    // converted power is the same quantity an inverter's is.
    expect(conversionLabel('bess')).toBe('PCS')
    expect(conversionLabel('pv')).toBe('inverter')
  })

  it('falls back to the neutral default for anything else', () => {
    // A results panel is the last place to throw over an unknown fleet kind.
    expect(conversionLabel(undefined)).toBe('inverter')
    expect(conversionLabel('nonsense' as never)).toBe('inverter')
  })

  it('has a plural for the panel headings that need one', () => {
    expect(conversionLabelPlural('bess')).toBe('PCS units')
    expect(conversionLabelPlural('pv')).toBe('inverters')
  })
})

describe('fleetLabel', () => {
  it('names the fleet itself in the capitals a reader expects', () => {
    expect(fleetLabel('bess')).toBe('BESS')
    expect(fleetLabel('pv')).toBe('PV')
  })
})
