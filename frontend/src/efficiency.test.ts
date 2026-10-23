import { describe, expect, it } from 'vitest'
import { downsampleMinMax, formatCliNumber, parseAmbientCsv, summarise, toCliCsv } from './efficiency'
import type { EfficiencyRow } from './types'
import fixture from './efficiency.fixture.json'

describe('parseAmbientCsv', () => {
  it('reads timestamp and ambient °C after a header row', () => {
    const parsed = parseAmbientCsv('timestamp,ambient_c\n2026-01-01 00:00,25\n2026-01-01 01:00,-3.5\n')
    expect(parsed.errors).toEqual([])
    expect(parsed.rows).toEqual([
      { timestamp: '2026-01-01 00:00', ambient_c: 25 },
      { timestamp: '2026-01-01 01:00', ambient_c: -3.5 },
    ])
  })

  it('accepts CRLF line endings, blank lines, extra columns and quoted timestamps', () => {
    const parsed = parseAmbientCsv('ts,t,note\r\n"day 1, ""noon""",30,x\r\n\r\nt1, 12.5 ,y\r\n')
    expect(parsed.errors).toEqual([])
    expect(parsed.rows).toEqual([
      { timestamp: 'day 1, "noon"', ambient_c: 30 },
      { timestamp: 't1', ambient_c: 12.5 },
    ])
  })

  it('reports bad rows by row number instead of skipping them', () => {
    const parsed = parseAmbientCsv('timestamp,ambient\nt0,25\nt1,hot\nt2\nt3,\nt4,0x10\n')
    expect(parsed.rows).toEqual([{ timestamp: 't0', ambient_c: 25 }])
    expect(parsed.errors).toEqual([
      'Row 3: ambient "hot" is not a number.',
      'Row 4: expected timestamp and ambient °C.',
      'Row 5: ambient "" is not a number.',
      'Row 6: ambient "0x10" is not a number.',
    ])
  })

  it('reports a file with no data rows', () => {
    expect(parseAmbientCsv('timestamp,ambient_c\n').errors).toEqual([
      'The CSV has no data rows below its header.',
    ])
  })
})

describe('CLI CSV format', () => {
  it('rounds to 4 decimals and drops trailing zeros, as the CLI does', () => {
    expect(formatCliNumber(100)).toBe('100')
    expect(formatCliNumber(76.00000000000001)).toBe('76')
    expect(formatCliNumber(88.62461234)).toBe('88.6246')
    expect(formatCliNumber(0.23400000001)).toBe('0.234')
    expect(formatCliNumber(0.00004)).toBe('0')
    expect(formatCliNumber(0.00005000001)).toBe('0.0001')
    // Python rounds an exact binary tie to even: round(0.03125, 4) == 0.0312.
    expect(formatCliNumber(0.03125)).toBe('0.0312')
    expect(formatCliNumber(0.09375)).toBe('0.0938')
  })

  it('writes byte-for-byte what the CLI writes for the same run', () => {
    expect(toCliCsv(fixture.rows as EfficiencyRow[])).toBe(fixture.cli_csv)
  })
})

describe('summarise', () => {
  const row = (rte: number, idle: number, pcs: number): EfficiencyRow => ({
    timestamp: 't',
    operating_rte_pct: rte,
    idle_loss_pct: idle,
    pcs_power_pct: pcs,
  })

  it('gives min, average and max operating RTE, average idle loss and the derated count', () => {
    const summary = summarise([row(88, 0.2, 100), row(86, 0.3, 76), row(90, 0.1, 100)])
    expect(summary).toEqual({
      count: 3,
      minRtePct: 86,
      avgRtePct: 88,
      maxRtePct: 90,
      avgIdleLossPct: expect.closeTo(0.2, 12),
      deratedCount: 1,
    })
  })

  it('is null for an empty run', () => {
    expect(summarise([])).toBeNull()
  })
})

describe('downsampleMinMax', () => {
  it('keeps every point when there are fewer than two per column', () => {
    expect(downsampleMinMax([3, 1, 2], 10)).toEqual([
      { i: 0, v: 3 },
      { i: 1, v: 1 },
      { i: 2, v: 2 },
    ])
  })

  it('draws a year of hourly data with at most two points per column, keeping spikes', () => {
    const values = Array.from({ length: 8760 }, (_, i) => 88 + Math.sin(i / 24))
    values[4000] = 70
    values[6000] = 95
    const points = downsampleMinMax(values, 600)
    expect(points.length).toBeLessThanOrEqual(1200)
    expect(points.some((p) => p.i === 4000 && p.v === 70)).toBe(true)
    expect(points.some((p) => p.i === 6000 && p.v === 95)).toBe(true)
    expect(points.map((p) => p.i)).toEqual([...points.map((p) => p.i)].sort((a, b) => a - b))
  })
})
