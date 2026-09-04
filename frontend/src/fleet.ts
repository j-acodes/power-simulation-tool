import type { FleetKind } from './types'

/**
 * What to CALL a fleet's conversion device: "PCS" or "inverter".
 *
 * Mirrors `powertool.components.conversion_label`, and is presentation only.
 * The result fields are neither renamed nor duplicated per fleet kind — a BESS
 * station's converted power lives in the same `p_inv_kw` a PV station's does,
 * because it is the same quantity computed the same way. Only the word in front
 * of the engineer changes, because a battery project's reviewer expects "PCS".
 *
 * An unknown or absent kind reads as the neutral default rather than throwing:
 * a results panel is the last place to discover an unrecognised fleet kind.
 */
export function conversionLabel(kind: FleetKind | undefined): string {
  return kind === 'bess' ? 'PCS' : 'inverter'
}

/** The plural, for headings that count the devices rather than name one. */
export function conversionLabelPlural(kind: FleetKind | undefined): string {
  return kind === 'bess' ? 'PCS units' : 'inverters'
}

/** The fleet itself, in the capitals a reader expects. */
export function fleetLabel(kind: FleetKind | undefined): string {
  return kind === 'bess' ? 'BESS' : 'PV'
}
