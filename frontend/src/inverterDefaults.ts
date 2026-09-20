import type { TransformerInfo } from './types'

/** The inverter a PV station is deployed with: its first catalogue pairing,
 * filled to the maximum number of inverters that pairing allows. Shared by the
 * palette (drag onto the canvas), the inspector (model change) and the seed
 * wizard so all three deploy the same station. A station with no pairings — a
 * BESS or custom one — yields an empty selection.
 *
 * ponytail: first pairing wins; every catalogue station lists exactly one.
 * Offer a choice at drop time if a station ever pairs with two inverters. */
export function defaultInverterSelection(tx?: TransformerInfo): {
  pv_inverter: string
  inverter_count: number | undefined
} {
  const [key, pairing] = Object.entries(tx?.paired_inverters ?? {})[0] ?? []
  return { pv_inverter: key ?? '', inverter_count: pairing?.maximum_count }
}
