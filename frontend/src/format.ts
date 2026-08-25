/** Small shared number formatters for node/edge annotations. */

export function fmt(value: number | null | undefined, digits = 0): string {
  if (value === null || value === undefined || !Number.isFinite(value)) return '—'
  return value.toLocaleString(undefined, { maximumFractionDigits: digits, minimumFractionDigits: 0 })
}

export function pct(value: number | null | undefined, digits = 0): string {
  if (value === null || value === undefined || !Number.isFinite(value)) return '—'
  return `${fmt(value * 100, digits)}%`
}

/** Power factor from P/Q, for figures the backend reports as P and Q rather
 * than PF directly (e.g. POC delivered power). */
export function powerFactor(pKw: number, qKvar: number): number {
  const s = Math.hypot(pKw, qKvar)
  return s > 0 ? pKw / s : 1
}

/** Mirrors Python's "%g" formatting closely enough for the clean tier voltages
 * this app deals with (0.8, 20, 132, ...) — used to key into the catalogue's
 * voltage-class-grouped cable list. */
export function kvGroupKey(kv: number): string {
  return Number(kv.toPrecision(12)).toString()
}
