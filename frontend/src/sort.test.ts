import { describe, expect, it } from 'vitest'
import { sortRows } from './sort'

const rows = [
  { name: 'beta', stations: 7, compliant: false },
  { name: 'alpha', stations: 12, compliant: true },
  { name: 'gamma', stations: 3, compliant: true },
]

describe('sortRows', () => {
  it('sorts text by locale in both directions', () => {
    expect(sortRows(rows, { key: 'name', dir: 'asc' }).map((r) => r.name)).toEqual([
      'alpha',
      'beta',
      'gamma',
    ])
    expect(sortRows(rows, { key: 'name', dir: 'desc' }).map((r) => r.name)).toEqual([
      'gamma',
      'beta',
      'alpha',
    ])
  })

  it('sorts numbers numerically, not as strings', () => {
    expect(sortRows(rows, { key: 'stations', dir: 'asc' }).map((r) => r.stations)).toEqual([
      3, 7, 12,
    ])
  })

  it('sorts booleans true-first ascending', () => {
    expect(sortRows(rows, { key: 'compliant', dir: 'asc' }).map((r) => r.compliant)).toEqual([
      true,
      true,
      false,
    ])
  })

  it('keeps blanks last in both directions — half-loaded rows must not jump', () => {
    const partial = [
      { name: 'a', stations: undefined },
      { name: 'b', stations: 5 },
      { name: 'c', stations: null },
      { name: 'd', stations: 1 },
    ]
    expect(sortRows(partial, { key: 'stations', dir: 'asc' }).map((r) => r.name)).toEqual([
      'd',
      'b',
      'a',
      'c',
    ])
    const desc = sortRows(partial, { key: 'stations', dir: 'desc' }).map((r) => r.name)
    expect(desc.slice(0, 2)).toEqual(['b', 'd'])
    expect(desc.slice(2).sort()).toEqual(['a', 'c'])
  })

  it('does not mutate the input array', () => {
    const original = [...rows]
    sortRows(rows, { key: 'name', dir: 'asc' })
    expect(rows).toEqual(original)
  })

  it('leaves rows in place when the column is missing everywhere', () => {
    expect(sortRows(rows, { key: 'nope', dir: 'asc' }).map((r) => r.name)).toEqual([
      'beta',
      'alpha',
      'gamma',
    ])
  })
})
