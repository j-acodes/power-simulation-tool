import type { BessSolutionInfo, Diagram } from './types'

/**
 * The discharge durations every BESS solution in this design tabulates, ascending.
 *
 * Mirrors `powertool.graph.supported_durations`. The duration is ONE
 * design-level choice, so it has to be one that every selected solution sells:
 * a design mixing two products can only run where their tables overlap. An
 * empty result means either no BESS station is drawn, or the selected products
 * share no duration at all — in which case the design has to change product,
 * not duration.
 *
 * Rendering this as a select is what lets the container count stay a plain
 * table lookup with no rounding or interpolation rule anywhere: the invalid
 * state is unreachable through the interface. The server checks it too, for
 * payloads that did not come through the interface.
 */
export function supportedDurations(diagram: Diagram, solutions: BessSolutionInfo[]): number[] {
  const byKey = new Map(solutions.map((s) => [s.key, s]))
  const selected: BessSolutionInfo[] = []
  for (const node of diagram.nodes) {
    if (node.kind !== 'station' || node.props.fleet_kind !== 'bess') continue
    // A station naming a solution the catalogue does not have is already
    // reported as unknown_bess_solution; skipping it here keeps it from
    // emptying the list and making every duration look unavailable.
    const solution = byKey.get(String(node.props.bess_solution))
    if (solution && !selected.includes(solution)) selected.push(solution)
  }
  if (selected.length === 0) return []

  const durations = (s: BessSolutionInfo) => Object.keys(s.containers_by_duration).map(Number)
  let common = new Set(durations(selected[0]))
  for (const solution of selected.slice(1)) {
    const next = new Set(durations(solution))
    common = new Set([...common].filter((h) => next.has(h)))
  }
  return [...common].sort((a, b) => a - b)
}
