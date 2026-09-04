import { describe, expect, it } from 'vitest'
import { permitsFleetKind } from './technology'

describe('permitsFleetKind', () => {
  it('a pv design permits only pv', () => {
    expect(permitsFleetKind('pv', 'pv')).toBe(true)
    expect(permitsFleetKind('pv', 'bess')).toBe(false)
  })

  it('a bess design permits only bess', () => {
    expect(permitsFleetKind('bess', 'bess')).toBe(true)
    expect(permitsFleetKind('bess', 'pv')).toBe(false)
  })

  it('a hybrid design permits both', () => {
    expect(permitsFleetKind('hybrid', 'pv')).toBe(true)
    expect(permitsFleetKind('hybrid', 'bess')).toBe(true)
  })

  it('an unknown technology (design not yet loaded) permits everything', () => {
    // Per ADR-0002/ticket 03: a blank editor that hides its own palette is
    // worse than one that shows too much, so a null/undefined technology
    // fails open rather than closed.
    expect(permitsFleetKind(null, 'pv')).toBe(true)
    expect(permitsFleetKind(null, 'bess')).toBe(true)
    expect(permitsFleetKind(undefined, 'pv')).toBe(true)
    expect(permitsFleetKind(undefined, 'bess')).toBe(true)
  })
})
