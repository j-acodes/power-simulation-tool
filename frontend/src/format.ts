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

/** A transformer station's rating at both ambients it can publish — see
 * ADR-0004 and CONTEXT.md's "AC power at ambient" entry. Catalogue views show
 * both slots always, marking the 30 °C one "not published" rather than
 * omitting it, so a missing figure reads as a gap in the datasheet rather
 * than as the entry never having one. */
export function ratingAtAmbients(tx: { s_rated_kva_at_40c: number; s_rated_kva_at_30c: number | null }): string {
  const at40 = `${fmt(tx.s_rated_kva_at_40c, 0)} kVA @ 40 °C`
  const at30 = tx.s_rated_kva_at_30c != null ? `${fmt(tx.s_rated_kva_at_30c, 0)} kVA @ 30 °C` : 'not published @ 30 °C'
  return `${at40} / ${at30}`
}

/** Mirrors Python's "%g" formatting closely enough for the clean tier voltages
 * this app deals with (0.8, 20, 132, ...) — used to key into the catalogue's
 * voltage-class-grouped cable list. */
export function kvGroupKey(kv: number): string {
  return Number(kv.toPrecision(12)).toString()
}
