import type { Diagram, TransformerInfo } from './types'

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

/** Catalogue PV stations on the canvas that carry no inverter yet, paired with
 * the selection that fills them. The palette, the inspector and the seed
 * wizard assign an inverter at the moment they deploy a station; a whole
 * diagram can still arrive without one — the example plant, or a design saved
 * before its model had pairings — and the inspector offers no select for a
 * model with a single pairing, so those stations would be stuck empty.
 *
 * BESS and custom stations are skipped: neither has a paired PV inverter. */
export function missingInverterSelections(
  diagram: Diagram,
  transformers: TransformerInfo[],
): Array<{ id: string; selection: ReturnType<typeof defaultInverterSelection> }> {
  const filled = []
  for (const node of diagram.nodes) {
    if (node.kind !== 'station') continue
    const { fleet_kind, mode, model, pv_inverter } = node.props
    if (fleet_kind === 'bess' || mode === 'custom' || pv_inverter) continue
    const selection = defaultInverterSelection(transformers.find((tx) => tx.key === model))
    if (selection.pv_inverter) filled.push({ id: node.id, selection })
  }
  return filled
}
