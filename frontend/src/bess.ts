import type { BessSolutionInfo, Diagram } from './types'

/**
 * The discharge duration every BESS solution in this design declares, or an
 * empty list when the design cannot run at any single duration.
 *
 * Mirrors `powertool.graph.supported_durations`. Each solution now declares
 * exactly ONE discharge duration (see `BessSolutionInfo.duration_h`), so the
 * duration is one design-level choice only when every selected solution
 * declares the SAME one: a design mixing two products at different durations
 * cannot be run at either. An empty result means either no BESS station is
 * drawn, or the selected products declare different durations — in which
 * case the design has to change product, not duration.
 *
 * Rendering this as a select is what lets the container count stay a plain
 * read with no rounding or interpolation rule anywhere: the invalid state is
 * unreachable through the interface. The server checks it too, for payloads
 * that did not come through the interface.
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

  const durations = new Set(selected.map((s) => s.duration_h))
  return durations.size === 1 ? [...durations] : []
}
