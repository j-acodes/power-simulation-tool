import type { BranchSummary, Issue, SolveResults } from './types'

export interface ComplianceVerdict {
  compliant: boolean
  reasons: string[]
}

/** Delivered active power must land within this fraction of the POC target. */
const POWER_TOLERANCE = 0.005

const FLEET_LABEL: Record<BranchSummary['kind'], string> = { pv: 'PV', bess: 'BESS' }

/** The hard gates one fleet can fail, phrased so the engineer can see which
 *  gate went and by how much. */
function fleetReasons(branch: BranchSummary): string[] {
  const label = FLEET_LABEL[branch.kind] ?? branch.kind
  const reasons: string[] = []

  if (!branch.loading_ok) {
    reasons.push(
      `The ${label} fleet is overloaded — ${(branch.fleet_loading * 100).toFixed(0)}% of its ` +
        `combined rating, against a ${(branch.max_loading * 100).toFixed(0)}% maximum.`,
    )
  }

  // energy_ok is null when no discharge duration was chosen (every design saved
  // before this gate existed). Judging it against an invented duration would be
  // worse than not judging it.
  if (branch.energy_ok === false && branch.e_delivered_kwh != null && branch.e_required_kwh != null) {
    const short = branch.e_required_kwh - branch.e_delivered_kwh
    reasons.push(
      `The ${label} fleet delivers ${(branch.e_delivered_kwh / 1000).toFixed(1)} MWh, ` +
        `short of the ${(branch.e_required_kwh / 1000).toFixed(1)} MWh its point-of-connection ` +
        `power owes over the discharge duration — ${(short / 1000).toFixed(1)} MWh under.`,
    )
  }

  return reasons
}

/**
 * POC grid-compliance verdict, derived entirely from the last solve's summary
 * flags (already computed by the engine) plus any outstanding validation
 * issues. All criteria must hold for a COMPLIANT verdict:
 *   - delivered active power within 0.5% of the target
 *   - power_balance_ok
 *   - every fleet within its own maximum loading (per-fleet, hard gate)
 *   - every BESS fleet delivering its required energy (per-fleet, hard gate)
 *   - every circuit within its current cap (all_current_ok)
 *   - zero validation issues
 */
export function evaluateCompliance(results: SolveResults, issues: Issue[]): ComplianceVerdict {
  const reasons: string[] = []
  const { summary } = results

  if (issues.length > 0) {
    reasons.push(
      `${issues.length} validation issue${issues.length === 1 ? '' : 's'} on the diagram.`,
    )
  }

  const target = summary.p_poc_target_kw
  const delivered = summary.p_poc_refined_delivered_kw ?? summary.p_poc_delivered_kw
  if (target > 0) {
    const deviation = Math.abs(delivered - target) / target
    if (deviation > POWER_TOLERANCE) {
      reasons.push(
        `Delivered active power (${(delivered / 1000).toFixed(2)} MW) is ` +
          `${(deviation * 100).toFixed(2)}% off the ${(target / 1000).toFixed(2)} MW target ` +
          `(limit 0.5%).`,
      )
    }
  }

  if (!summary.power_balance_ok) {
    reasons.push('The internal power-balance check failed.')
  }

  // Loading and energy are BOTH hard gates, judged per fleet against that
  // fleet's own limits. A hybrid can have a compliant PV fleet beside an
  // overloaded BESS one, and a plant-wide "the fleet is overloaded" would say
  // neither which fleet nor against what maximum.
  for (const branch of summary.branches ?? []) {
    reasons.push(...fleetReasons(branch))
  }

  if (!summary.all_current_ok) {
    reasons.push(
      `A circuit exceeds its current cap — worst trunk current ` +
        `${summary.worst_trunk_current_a.toFixed(0)} A vs. a ` +
        `${summary.max_circuit_current_a.toFixed(0)} A limit.`,
    )
  }

  return { compliant: reasons.length === 0, reasons }
}
