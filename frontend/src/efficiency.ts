// Browser side of the efficiency run (ticket 17): reading the engineer's
// ambient CSV, writing the CLI's output CSV, the panel's summary, and the
// chart's downsampling. The physics is the engine's (POST /api/efficiency).
import type { AmbientRow, EfficiencyRow } from './types'

// --- reading the ambient CSV --------------------------------------------------

/** RFC 4180 records: quoted fields may hold commas, doubled quotes and line
 * breaks; CRLF, LF and CR all end a record (as Python's csv.reader). */
function csvRecords(text: string): string[][] {
  const records: string[][] = []
  let record: string[] = []
  let field = ''
  let quoted = false
  for (let i = 0; i < text.length; i++) {
    const c = text[i]
    if (quoted) {
      if (c === '"' && text[i + 1] === '"') {
        field += '"'
        i++
      } else if (c === '"') {
        quoted = false
      } else {
        field += c
      }
    } else if (c === '"') {
      quoted = true
    } else if (c === ',') {
      record.push(field)
      field = ''
    } else if (c === '\r' || c === '\n') {
      if (c === '\r' && text[i + 1] === '\n') i++
      record.push(field)
      records.push(record)
      record = []
      field = ''
    } else {
      field += c
    }
  }
  if (field !== '' || record.length > 0) {
    record.push(field)
    records.push(record)
  }
  return records
}

// What Python's float() accepts for a plain decimal, padding included; not
// hex, not an empty string (both of which JavaScript's Number() would take).
const DECIMAL = /^\s*[+-]?(\d+\.?\d*|\.\d+)([eE][+-]?\d+)?\s*$/

export interface ParsedAmbient {
  rows: AmbientRow[]
  /** One message per bad row; a non-empty list means the run must not start. */
  errors: string[]
}

/** Parse a CSV of `timestamp, ambient °C`: the first record is a header, only
 * the first two columns are read, blank lines are ignored (as the CLI does).
 * Bad rows are reported by row number (the header is row 1), never skipped. */
export function parseAmbientCsv(text: string): ParsedAmbient {
  const rows: AmbientRow[] = []
  const errors: string[] = []
  csvRecords(text).forEach((record, index) => {
    if (index === 0) return
    if (record.length === 1 && record[0] === '') return
    const rowNo = index + 1
    if (record.length < 2) {
      errors.push(`Row ${rowNo}: expected timestamp and ambient °C.`)
      return
    }
    const [timestamp, ambient] = record
    if (!DECIMAL.test(ambient)) {
      errors.push(`Row ${rowNo}: ambient "${ambient}" is not a number.`)
      return
    }
    rows.push({ timestamp, ambient_c: Number(ambient) })
  })
  if (rows.length === 0 && errors.length === 0) {
    errors.push('The CSV has no data rows below its header.')
  }
  return { rows, errors }
}

// --- writing the CLI's output CSV ---------------------------------------------

export const CLI_HEADER = ['timestamp', 'operating RTE %', 'idle loss %', 'PCS power % of rated']

/** Python's `round(value, 4)`: nearest, and an exact binary tie to even. */
function roundHalfEven4(value: number): number {
  const fixed = value.toFixed(4) // nearest; a tie goes away from zero
  const exact = Math.abs(value).toFixed(20)
  const tail = exact.slice(exact.indexOf('.') + 5)
  if (/^50*$/.test(tail)) {
    const lastDigit = Number(exact[exact.indexOf('.') + 4])
    if (lastDigit % 2 === 0) {
      return Math.sign(value) * Number(exact.slice(0, exact.indexOf('.') + 5))
    }
  }
  return Number(fixed)
}

/** The CLI's `f"{round(value, 4):g}"`: 4 decimals, at most 6 significant
 * digits, no trailing zeros. */
export function formatCliNumber(value: number): string {
  const r = roundHalfEven4(value)
  if (r === 0) return Object.is(r, -0) ? '-0' : '0'
  const exponent = Math.floor(Math.log10(Math.abs(r)))
  if (exponent >= -4 && exponent < 6) return String(Number(r.toPrecision(6)))
  const [mantissa, exp] = r.toExponential(5).split('e')
  const digits = mantissa.replace(/\.?0+$/, '')
  const e = Number(exp)
  return `${digits}e${e < 0 ? '-' : '+'}${String(Math.abs(e)).padStart(2, '0')}`
}

/** Python csv.writer's minimal quoting. */
function csvField(value: string): string {
  return /[",\r\n]/.test(value) ? `"${value.replace(/"/g, '""')}"` : value
}

/** The four-column CSV exactly as `python -m powertool.efficiency_cli` writes
 * it: same header, same rounding, CRLF line endings. */
export function toCliCsv(rows: EfficiencyRow[]): string {
  const lines = [CLI_HEADER.join(',')]
  for (const row of rows) {
    lines.push([
      csvField(row.timestamp),
      formatCliNumber(row.operating_rte_pct),
      formatCliNumber(row.idle_loss_pct),
      formatCliNumber(row.pcs_power_pct),
    ].join(','))
  }
  return lines.map((line) => `${line}\r\n`).join('')
}

// --- summary ----------------------------------------------------------------

export interface EfficiencySummary {
  count: number
  minRtePct: number
  avgRtePct: number
  maxRtePct: number
  avgIdleLossPct: number
  /** Timestamps where PCS derating applied (PCS power below 100 % of rated). */
  deratedCount: number
}

/** Summary over every row of the run (never the chart's downsampled points). */
export function summarise(rows: EfficiencyRow[]): EfficiencySummary | null {
  if (rows.length === 0) return null
  let min = Infinity
  let max = -Infinity
  let rteSum = 0
  let idleSum = 0
  let derated = 0
  for (const row of rows) {
    min = Math.min(min, row.operating_rte_pct)
    max = Math.max(max, row.operating_rte_pct)
    rteSum += row.operating_rte_pct
    idleSum += row.idle_loss_pct
    if (row.pcs_power_pct < 100) derated++
  }
  return {
    count: rows.length,
    minRtePct: min,
    avgRtePct: rteSum / rows.length,
    maxRtePct: max,
    avgIdleLossPct: idleSum / rows.length,
    deratedCount: derated,
  }
}

// --- chart downsampling -----------------------------------------------------

export interface SeriesPoint {
  /** Index of the row the point came from. */
  i: number
  v: number
}

/** At most two points per pixel column — each column's minimum and maximum,
 * in row order — so a year of hourly data draws as fast as a week and no
 * spike is lost. Fewer than two rows per column draw every row. */
export function downsampleMinMax(values: number[], columns: number): SeriesPoint[] {
  const n = values.length
  if (n <= 2 * columns) return values.map((v, i) => ({ i, v }))
  const points: SeriesPoint[] = []
  for (let c = 0; c < columns; c++) {
    const start = Math.floor((c * n) / columns)
    const end = Math.floor(((c + 1) * n) / columns)
    let lo = start
    let hi = start
    for (let i = start + 1; i < end; i++) {
      if (values[i] < values[lo]) lo = i
      if (values[i] > values[hi]) hi = i
    }
    if (lo === hi) points.push({ i: lo, v: values[lo] })
    else {
      const [a, b] = lo < hi ? [lo, hi] : [hi, lo]
      points.push({ i: a, v: values[a] }, { i: b, v: values[b] })
    }
  }
  return points
}
