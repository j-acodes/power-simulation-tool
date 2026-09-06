import type { BessSolutionInfo, Diagram, TransformerInfo } from './types'

/**
 * The discharge durations on offer across every drawn BESS station, ascending,
 * or an empty list when the design cannot run at any single duration.
 *
 * Mirrors `powertool.graph.supported_durations`. Each station transformer is
 * sold with a fixed handful of solutions (`TransformerInfo.paired_solutions`,
 * see ticket 02), each declaring its own single discharge duration
 * (`BessSolutionInfo.duration_h`). The durations a design can run at are the
 * intersection, across every BESS station drawn, of the durations its OWN
 * chosen station transformer is paired to sell — CHANGE PRODUCT (or station
 * transformer), not duration.
 *
 * Rendering this as a select is what lets the container count stay a plain
 * read with no rounding or interpolation rule anywhere: the invalid state is
 * unreachable through the interface. The server checks it too, for payloads
 * that did not come through the interface.
 */
export function supportedDurations(
  diagram: Diagram,
  transformers: TransformerInfo[],
  solutions: BessSolutionInfo[],
): number[] {
  const txByKey = new Map(transformers.map((t) => [t.key, t]))
  const solByKey = new Map(solutions.map((s) => [s.key, s]))
  const sets: Set<number>[] = []

  for (const node of diagram.nodes) {
    if (node.kind !== 'station' || node.props.fleet_kind !== 'bess') continue
    // A station whose transformer is not (yet) a resolvable, paired
    // catalogue key contributes no restriction — it is not yet a data point
    // to intersect against, the same "skip, don't force empty" stance always
    // taken for a station with nothing chosen yet.
    const tx = txByKey.get(String(node.props.model))
    const paired = tx?.paired_solutions
    if (!paired) continue
    const durations = new Set<number>()
    for (const solutionKey of Object.keys(paired)) {
      const sol = solByKey.get(solutionKey)
      if (sol) durations.add(sol.duration_h)
    }
    if (durations.size > 0) sets.push(durations)
  }
  if (sets.length === 0) return []

  let common = sets[0]
  for (const set of sets.slice(1)) {
    common = new Set([...common].filter((d) => set.has(d)))
  }
  return [...common].sort((a, b) => a - b)
}
