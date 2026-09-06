import type { TransformerInfo } from './types'

/** Groups a transformer catalogue by brand, preserving first-seen order —
 * shared by the Palette (drag sources, grouped per fleet kind) and the
 * catalogue page (browse-only listing) so both group the same way. */
export function groupByBrand(transformers: TransformerInfo[]): Array<[string, TransformerInfo[]]> {
  const groups = new Map<string, TransformerInfo[]>()
  for (const tx of transformers) {
    const brand = tx.brand ?? 'Other'
    if (!groups.has(brand)) groups.set(brand, [])
    groups.get(brand)!.push(tx)
  }
  return [...groups.entries()]
}
